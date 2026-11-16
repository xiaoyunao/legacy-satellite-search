"""Unseal the weak controls and cross-match published spectroscopic members."""

import io
import json
from pathlib import Path
import tarfile

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io import fits

from .data import select
from .run import field_cache, read_csv, runs_path, settings, sha, write_csv, write_json


RECORD = 'https://zenodo.org/records/18688283'
ARCHIVE_SHA256 = '153f21e28406ab9b384fa096cd36ad0450274d11f38543975c15ea6307dfd360'


def main():
    output = Path('results/holdout')
    assessments = output/'preunblind_assessment.csv'
    grades = {r['group_id']:r for r in read_csv(assessments)}
    groups = {r['group_id']:r for r in read_csv(output/'group_review_summary.csv')}
    if grades.keys() != groups.keys():
        raise ValueError('A pre-unblinding disposition is required for every candidate group')
    modes = read_csv(output/'group_review_modes.csv')
    detection = read_csv(output/'sky_group_candidates.csv')
    known = {r['name']:r for r in read_csv(Path('references/benchmarks.csv'))}
    root,data,cfg = settings()
    archive = data/'resources/ufcs-cerny-18688283/MemberCatalogs_v1.1.tar.gz'
    if sha(archive)!=ARCHIVE_SHA256:
        raise ValueError('Unexpected member archive checksum')
    output_rows = []
    with tarfile.open(archive) as members:
        for n in (3,4,5):
            tag = f'DELVE_{n}'
            field_id = f'weak_{n-2:02d}'
            run = field_id+'-base'
            manifest = json.loads((Path('results/summary')/run/'manifest.json').read_text())
            field,sources,area,_ = field_cache(root,data,manifest['field'],cfg,None)
            _,_,_,_,accepted = select(sources,field,area,cfg)
            keys = sources[['RELEASE','BRICKID','OBJID']]
            catalogue = SkyCoord(sources['RA'],sources['DEC'],unit='deg')
            with members.extractfile(f'PublicMemberCatalogs/{tag}_Members_v1.1.fits') as f:
                with fits.open(io.BytesIO(f.read())) as h:
                    sample = h[1].data
                    literature = SkyCoord(sample['Phot_RA'],sample['Phot_DEC'],unit='deg')
                    complete = np.asarray(sample['inCompleteSample'],dtype=bool)
            matched,sep,_ = literature.match_to_catalog_sky(catalogue)
            found = sep.arcsec<=.8
            selected = found & accepted[matched]
            truth = known[tag]
            rh = float(truth['theta_h_arcmin'])
            exact_dm = 5*np.log10(float(truth['D_kpc']))+10
            center = SkyCoord(float(truth['ra_deg']),float(truth['dec_deg']),unit='deg')
            candidates = []
            for r in detection:
                if r['field']==field_id and float(r['budget'])==.3 and r['representative']=='True':
                    offset = center.separation(SkyCoord(float(r['ra_deg']),float(r['dec_deg']),unit='deg')).arcmin
                    if offset<=max(2.,rh):
                        candidates.append((r,offset))
            baseline = dict(object=tag,field=field_id,literature_rh_arcmin=rh,literature_dm=exact_dm,
                            literature_rows=len(literature),complete_sample_rows=int(complete.sum()),
                            matched_ls=int(found.sum()),selected_ls=int(selected.sum()),
                            selected_ls_complete=int((selected&complete).sum()))
            if not candidates:
                output_rows.append(dict(baseline,detected=False))
            for r,offset in candidates:
                for mode in (m for m in modes if m['candidate_group_id']==r['group_id']):
                    values = dict(baseline,detected=True,group_id=r['group_id'],A_anchor_offset_arcmin=float(offset),
                                  A_offset_over_rh=float(offset/rh),blind_A_dm=r['dm'],A_score=r['score'],
                                  grade=grades[r['group_id']]['disposition'],rank=mode['rank'],
                                  preferred_C=mode['rank']==groups[r['group_id']]['best_peak_rank'],
                                  C_status=mode['fit_status'])
                    if mode['fit_status']=='complete':
                        with np.load(runs_path(data)/run/f"membership-main-A-{mode['rank']}.npz",allow_pickle=False) as fit:
                            probs = {tuple(k):float(p) for k,p in zip(fit['source_ids'],fit['probability']) if p>0}
                        top = set(sorted(probs,key=probs.get,reverse=True)[:3])
                        detected = [tuple(keys[i]) for i in matched[selected]]
                        cpos = SkyCoord(float(mode['fit_ra_deg']),float(mode['fit_dec_deg']),unit='deg')
                        values.update(fitted_dm=mode['fit_dm'], C_offset_arcmin=float(center.separation(cpos).arcmin),
                                      C_TS=mode['ts'], C_TS_without_top3=mode['C_refit_TS_without_top3'],
                                      published_with_positive_C_weight=sum(k in probs for k in detected),
                                      published_in_top3=sum(k in top for k in detected),
                                      published_C_weight_sum=sum(probs.get(k,0.) for k in detected))
                    output_rows.append(values)
    write_csv(output/'weak_reference_association.csv',output_rows)
    write_json(output/'weak_reference_provenance.json',dict(reference=RECORD,
               payload_sha256=ARCHIVE_SHA256, preunblind_sha256=sha(assessments),
               matcher_arcsec=.8, complete_column='inCompleteSample'))


if __name__=='__main__':
    main()
