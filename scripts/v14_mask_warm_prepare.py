"""Register immutable completed-field geometry for reusable cache preparation.

Source qualification will be refreshed after final regional C/production; the
cache key is independent of qualification, so warming does not freeze an area.
"""
from collections import Counter
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
from ls_satsearch.run import sha,write_json
from scripts.v14_production_masks import run as inventory
from scripts.v14_mask_tiles import prepare,cache_key


def main():
    if not os.getenv('SLURM_JOB_ID'):raise RuntimeError('Allocated CPU required')
    inventory()
    capture=io.StringIO()
    with redirect_stdout(capture):
        prepare(8,Path('results/v14/production_integration/masks/inventory.json'))
    registration=Path(capture.getvalue().strip().splitlines()[-1])
    m=json.loads(registration.read_text());cache=Path(m['cache'])
    keys=Counter(cache_key(r,m) for r in m['records'])
    missing=[k for k in keys if not (cache/(k+'.json')).is_file()]
    write_json(Path('results/v14/production_integration/masks/warm_registration_20261120.json'),dict(
        job=os.environ['SLURM_JOB_ID'],registration=str(registration),registration_sha256=sha(registration),
        records=len(m['records']),unique_geometry_keys=len(keys),new_geometry_keys=len(missing),
        duplicate_missing_keys=sum(keys[k]>1 for k in missing),cached_keys=len(keys)-len(missing),
        final_production_frozen=False,scope='Completed-field cache registration only. Qualification/source roster is still interim; no final union area or gain claim. Reuse immutable geometry after the final production clock closes.'))
    print(registration)


if __name__=='__main__':main()
