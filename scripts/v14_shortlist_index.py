"""Index actual C packets and visual decisions without altering the frozen queue."""
from pathlib import Path
import shutil

from ls_satsearch.run import read_csv, sha, write_csv, write_json


def run():
    out = Path('results/v14/shortlist')
    rows = []
    published_images = {}
    for case in read_csv(out / 'cases.csv'):
        folder = out / 'cases' / case['case_id']
        origin = 'new_C'
        if not (folder / 'review_modes.csv').is_file():
            folder = out / 'cached_cases' / case['case_id']
            origin = 'existing_same_record_C'
        table = folder / 'review_modes.csv'
        modes = read_csv(table) if table.is_file() else []
        complete = [m for m in modes if m['fit_status'] == 'complete']
        best = max(complete, key=lambda m: float(m['ts']), default={})
        images = [folder / f'seed-{int(float(m["rank"]))}{suffix}.png'
                  for m in complete for suffix in ('', '-environment', '-images')]
        published = []
        if best and case['queue'] == 'priority':
            target = out / 'priority_figures'
            target.mkdir(exist_ok=True)
            rank = int(float(best['rank']))
            for suffix in ('', '-environment', '-images'):
                source = folder / f'seed-{rank}{suffix}.png'
                if source.is_file():
                    dest = target / f'{case["case_id"]}{suffix}.png'
                    shutil.copy2(source, dest)
                    published.append(str(dest))
                    published_images[str(dest)] = sha(dest)
        rows.append(dict(case_id=case['case_id'], queue=case['queue'],
            cohort=case['cohort'], candidate_id=case['candidate_id'],
            ra_deg=case['ra_deg'], dec_deg=case['dec_deg'],
            C_origin=origin if modes else 'pending', C_complete_modes=len(complete),
            best_C_TS=best.get('ts'), best_C_after_top3=best.get('C_refit_TS_without_top3'),
            best_C_DM=best.get('fit_dm'), best_C_seed_rank=best.get('rank'),
            table=str(table) if modes else '',
            published_best_mode_panels='|'.join(published),
            complete_diagnostic_set=bool(images) and all(p.is_file() for p in images),
            table_sha256=sha(table) if modes else '', evidence_level='L0'))
    write_csv(out / 'review_readiness.csv', rows)
    write_json(out / 'readiness_manifest.json', dict(
        shortlist_manifest_sha256=sha(out / 'manifest.json'),
        positions=len(rows), C_ready=sum(r['C_complete_modes'] > 0 for r in rows),
        priority_C_ready=sum(r['queue']=='priority' and r['C_complete_modes']>0 for r in rows),
        diagnostic_sets_ready=sum(r['complete_diagnostic_set'] for r in rows),
        published_image_hashes=published_images,
        scope='Operational index only. Reused C is not a new observation; C completion and image availability do not imply visual approval or independent population evidence. Do not expose this identity key during blinded audit grading.'))


if __name__ == '__main__':
    run()
