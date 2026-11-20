"""Verify mandatory old-75 private materials, without grading or releasing them."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path

from PIL import Image

from ls_satsearch.run import read_csv, sha, write_json
from scripts.v14_review_integrity import mode_table


def run(case_id=None):
    if not os.getenv('SLURM_JOB_ID'):
        raise RuntimeError('Saved-source validation requires Slurm')
    base=Path('results/v14/human_review')
    source=Path('results/v14/shortlist')
    original=source/'manifest.json'
    registration=json.loads(original.read_text())
    if any(sha(Path(p))!=d for p,d in registration['packet_hashes'].items()):
        raise ValueError('Original case/mode registration changed')
    release=base/'release_v2/package_manifest.json'
    if sha(release)!='7900621c7b3974629dce4501deb3393797893c8779cee5aee3b57d8a758b29b8':
        raise ValueError('Original frozen release manifest changed')
    released=json.loads(release.read_text())
    for artifact in [*released['packages'].values(),released['anonymous_zip']]:
        if sha(Path(artifact['file']))!=artifact['sha256']:
            raise ValueError('Original frozen release artifact changed')
    cases=read_csv(source/'cases.csv')
    if len(cases)!=75 or len({c['case_id'] for c in cases})!=75:
        raise ValueError('Original case roster changed')
    if case_id:
        cases=[c for c in cases if c['case_id']==case_id]
        if len(cases)!=1:raise ValueError('Unknown original case')
    integrity=base/'membership_integrity.json'
    saved=json.loads(integrity.read_text())
    if sha(integrity.with_suffix('.csv'))!=saved['csv_sha256']:
        raise ValueError('Original member integrity ledger changed')
    frozen={(r['case_id'],int(r['seed_rank'])):r for r in read_csv(integrity.with_suffix('.csv'))}
    roots=base/'final_private/prepared75'
    records=[];pngs=set();all_hashes={}
    for case in cases:
        p=roots/case['case_id']/'accepted.json'
        try:
            m=json.loads(p.read_text());table,modes=mode_table(case)
            assert m['original_registration_sha256']==sha(original)
            assert m['case_id']==case['case_id'] and not m['refitted']
            assert m['mode_table_sha256']==sha(table) and m['modes']==len(modes)
            assert m['phase1_renderer_sha256']==sha(Path('scripts/v14_phase1_panels.py'))
            expected={int(float(r['rank'])) for r in modes}
            assert len(m['mode_status'])==len(modes) and {r['seed_rank'] for r in m['mode_status']}==expected
            for filename,digest in m['outputs'].items():
                assert sha(Path(filename))==digest, filename
                all_hashes[filename]=digest
                if filename.endswith('.png') and filename not in pngs:
                    with Image.open(filename) as im:im.verify()
                    pngs.add(filename)
            gaps=[]
            for r in m['mode_status']:
                c=json.loads(Path(r['context_manifest']).read_text())
                f=frozen[case['case_id'],r['seed_rank']]
                assert c['membership_integrity']['verified'] and not c['refitted']
                assert c['membership_sha256']==f['membership_sha256']
                assert sha(Path(os.environ['LS_SAT_DATA'])/f['frozen_path'])==f['membership_sha256']
                assert c['plot_renderer_sha256']==sha(Path('src/ls_satsearch/plots.py'))
                assert c['image_renderer_sha256']==sha(Path('src/ls_satsearch/review.py'))
                assert not r['phase1_status']['probabilities_or_scores_rendered']
                assert not r['phase1_status']['source_overlay_or_contributor_order_rendered']
                assert r['extent_status']['full_two_rh_square']
                assert not r['extent_status']['probabilities_or_scores_rendered']
                assert Path(r['phase1_path']).is_file() and Path(r['extent_path']).is_file()
                if c['image_pending'] or not c['image_centre_complete'] or c['image_missed_member_stamps']:
                    gaps.append(dict(seed_rank=r['seed_rank'],reason='context_centre_or_contributor_image_gap'))
                for band in 'gr':
                    if r['extent_status']['images'][band]['finite_pixel_fraction']<=0:
                        gaps.append(dict(seed_rank=r['seed_rank'],reason='no_full_extent_'+band+'_pixels'))
            records.append(dict(case_id=case['case_id'],state='verified_with_image_gaps' if gaps else 'verified',
                modes=len(modes),acceptance_sha256=sha(p),image_gaps=gaps))
        except Exception as e:
            records.append(dict(case_id=case['case_id'],state='failed',error_type=type(e).__name__,error=str(e)))
    for path,digest in all_hashes.items():
        if sha(Path(path))!=digest:raise ValueError('Private evidence changed during audit')
    output=base/('prepared75_acceptance.json' if case_id is None else f'prepared75_pilot_{case_id}.json')
    write_json(output,dict(job=os.environ['SLURM_JOB_ID'],runner_sha256=sha(Path(__file__)),
        requested_cases=len(cases),verified_case_states=dict(Counter(r['state'] for r in records)),
        modes=sum(r.get('modes',0) for r in records),PNG_integrity_verified=len(pngs),cases=records,
        original75_preserved=True,final_review_release=False,human_grades_filled=False,
        scope='Saved source/config/member and private raster integrity for mandatory original cases only. Physical image gaps stay explicit. Not final population/sampling/PDF/privacy/full-page visual QA or human judgment.'))
    print(dict(cases=len(cases),states=dict(Counter(r['state'] for r in records)),PNG=len(pngs)))
    if any(r['state']=='failed' for r in records):raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--case')
    run(parser.parse_args().case)
