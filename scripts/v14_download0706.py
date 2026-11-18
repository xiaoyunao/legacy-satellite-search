"""Download bounded public pixels and reference photometry to NERSC scratch."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
from shutil import copyfileobj
from urllib.parse import urlencode
from urllib.request import urlopen

from ls_satsearch.ps1_tiles import COLUMNS
from ls_satsearch.run import sha, write_json


def run():
    data=Path(os.environ['LS_SAT_DATA'])
    folder=data/'resources/v14/v13r_south_ps1_0706-A_base-0.3-001'
    folder.mkdir(parents=True,exist_ok=True)
    plan=json.loads(Path('results/v14/0706/archive_audit.json').read_text())
    tasks=[]
    for r in plan['archives']['PS1_images']['rows']:
        tasks.append((f"ps1_{r['filter']}.fits",r['cutout_url']))
    sdss = plan['archives'].get('SDSS_images', {})
    if sdss.get('status') != 'complete':
        sdss = plan['archives'].get('SDSS_retry', {})
    for r in sdss.get('rows', []):
        band=r['Title'].split()[-1]
        if band in ('g','r'):
            tasks.append((r['url'].split('/')[-1],r['url']))
    url='https://catalogs.mast.stsci.edu/api/v0.1/panstarrs/dr2/stack.csv?'+urlencode(dict(
        ra=plan['ra_deg'],dec=plan['dec_deg'],radius=.23,primaryDetection=1,
        columns='['+','.join(COLUMNS)+']',pagesize=25000,sort_by='objID.asc'))
    tasks.append(('ps1.csv',url))
    def get(item):
        name,url=item
        path=folder/name
        if not path.is_file():
            tmp=path.with_suffix(path.suffix+'.part')
            with urlopen(url,timeout=150) as response,tmp.open('wb') as stream:
                copyfileobj(response,stream)
            if tmp.stat().st_size>50_000_000:
                raise ValueError(f'Unexpected oversized cutout {name}')
            tmp.replace(path)
        return dict(name=name,bytes=path.stat().st_size,sha256=sha(path),url=url)
    items=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures={pool.submit(get,t):t for t in tasks}
        for future in as_completed(futures):
            name,url=futures[future]
            try:
                items.append(dict(status='downloaded',**future.result()))
            except Exception as exc:
                items.append(dict(name=name,url=url,status='failed',error=str(exc)))
            write_json(folder/'download_manifest.json',dict(products=items))
            print(name,items[-1]['status'],flush=True)


if __name__=='__main__':
    run()
