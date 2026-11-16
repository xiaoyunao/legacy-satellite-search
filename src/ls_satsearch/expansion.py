"""Select and register candidate-independent expansion blocks from imaging metadata."""

import json
from pathlib import Path

from astropy.coordinates import SkyCoord
import numpy as np
from scipy.spatial import cKDTree
import yaml

from .data import Field, load_bricks
from .fields import Census
from .run import config_path, settings, sha, write_json


def unit(ra, dec):
    return np.asarray(SkyCoord(ra,dec,unit='deg').cartesian.xyz).T


def overlaps(ra,dec,regions):
    for west,east,south,north in regions:
        within_ra = (ra>=west)&(ra<=east) if east>=west else (ra>=west)|(ra<=east)
        if np.any(within_ra&(dec>=south)&(dec<=north)):
            return True
    return False


def register_batches(registration, destination=Path('configs/v5')):
    """Materialize per-batch cohort hashes and array order before catalog reads."""
    fields = yaml.safe_load((registration/'fields.yaml').read_text())
    all_policy = json.loads((registration/'production.json').read_text())
    for n in sorted({f['batch'] for f in fields['fields']}):
        folder = destination/f'batch{n}'
        folder.mkdir(exist_ok=True,parents=True)
        specs = [f for f in fields['fields'] if f['batch']==n]
        cohort = folder/'fields.yaml'
        cohort.write_text(yaml.safe_dump(dict(fields,fields=specs),sort_keys=False))
        (folder/'search.yaml').write_bytes(config_path('search.yaml').read_bytes())
        write_json(folder/'production.json',dict(all_policy,field_file_sha256=sha(cohort),
                                              expansion_registration_sha256=sha(registration/'fields.yaml')))
        (folder/'fields.list').write_text(''.join(f["id"]+"\n" for f in specs))


def choose():
    root,data,cfg = settings()
    assert not Path('results/summary').exists() or not list(Path('results/summary').glob('*/manifest.json'))
    plan_path = config_path('expansion.yaml')
    plan = yaml.safe_load(plan_path.read_text())
    atlas = Census(data)
    bricks = load_bricks(root)
    uv = unit(bricks['RA'],bricks['DEC'])
    tree = cKDTree(uv)
    quality = ((bricks['PSFDEPTH_G']>0)&(bricks['PSFDEPTH_R']>0)&
               np.isfinite(bricks['PSFSIZE_G']+bricks['PSFSIZE_R'])&
               (bricks['EBV']<plan['max_ebv']))
    gal_b = SkyCoord(bricks['RA'],bricks['DEC'],unit='deg').galactic.b.deg
    permit = quality & (abs(gal_b)>30) & (abs(bricks['DEC'])<plan.get('max_abs_dec',58))
    possible = {survey:np.flatnonzero(permit & atlas.accept(bricks['RA'],bricks['DEC'],survey))
                for survey in (3,1)}
    metric = bricks['PSFDEPTH_G']+bricks['PSFDEPTH_R']-.3*(bricks['PSFSIZE_G']+bricks['PSFSIZE_R'])
    lower,upper=np.percentile(metric[possible[3]],[35,70])
    previous = [p for f in plan['previous_fields'] for p in
                yaml.safe_load(Path(f).read_text())['fields']]
    visited = [xyz for xyz in unit([f['ra'] for f in previous],[f['dec'] for f in previous])]
    minimum = np.cos(np.deg2rad(plan['minimum_center_separation_deg']))
    rng = np.random.default_rng(plan['seed'])
    width = plan['width_deg']
    grid = np.meshgrid(*[np.linspace(-width*30,width*30,21)]*2)
    fields = []
    requests = [(batch,3) for batch in range(1,plan['batches']+1)
                for _ in range(plan['ps1_fields_per_batch'])]
    requests += [(1,1)]*plan['deep_control_fields']
    queue = {s:list(rng.permutation(possible[s])) for s in possible}
    for batch,survey in requests:
        best = None
        fallback = None
        while queue[survey]:
            j = queue[survey].pop()
            if np.max(np.asarray(visited)@uv[j])>minimum:
                continue
            b=bricks[j]
            f=Field(float(b['RA']),float(b['DEC']),width,1/6,buffer=0)
            ra,dec = f.sky(*grid)
            cls = {k:overlaps(ra,dec,boxes) for k,boxes in plan['overlap_regions'].items()}
            q = tree.query(unit(ra.ravel(),dec.ravel()),k=1)[1]
            if np.max(bricks['EBV'][q])>=plan['max_ebv'] or np.min(abs(gal_b[q]))<25:
                continue
            proxy = float(np.mean(quality[q]&atlas.accept(ra.ravel(),dec.ravel(),survey)))
            if proxy<plan['minimum_proxy_coverage']:
                continue
            if survey==3 and any(cls.values()):
                if fallback is None:
                    fallback=(j,b,f,proxy,cls)
                continue
            best=(j,b,f,proxy,cls)
            break
        if best is None:
            if fallback is None or np.max(np.asarray(visited)@uv[fallback[0]])>minimum:
                raise RuntimeError(f'Insufficient distinct controls for survey {survey}')
            best=fallback
        j,b,f,proxy,cls=best
        visited.append(uv[j])
        layer = 'shallower' if metric[j]<lower else 'deep' if metric[j]>=upper else 'ordinary'
        ident=f"{plan.get('id_prefix','expand')}_{len(fields)+1:02d}"
        fields.append(dict(id=ident,role='pilot_eval',batch=batch,layer=layer,survey=survey,
                           ra=f.ra,dec=f.dec,width=width,proxy_area_deg2=width**2*proxy,
                           proxy_coverage=proxy,phase='discovery' if survey==3 else 'deep_control',
                           rationale=plan['candidate_rationale']['search' if survey==3 else 'deep_control'],
                           overlap_proxy=cls, prior_search_mask='unknown',
                           unions_overlap='unknown_exact',rubin_later_releases='unknown',
                           center_g_depth=float(b['PSFDEPTH_G']),center_r_depth=float(b['PSFDEPTH_R'])))
    out=Path('results/registration')
    out.mkdir(exist_ok=True,parents=True)
    (out/'fields.yaml').write_text(yaml.safe_dump(dict(seed=plan['seed'], selection_sha256=sha(plan_path),
                                 census_sha256=sha(data/'resources/census.fits.gz'),fields=fields),sort_keys=False))
    frozen_path=config_path('production.json')
    frozen=json.loads(frozen_path.read_text())
    frozen.update(field_file_sha256=sha(out/'fields.yaml'),inherited_policy_sha256=sha(frozen_path))
    write_json(out/'production.json',frozen)
    register_batches(out,Path(plan.get('batch_config_dir','configs/v5')))
    print(f"Registered {len(fields)} blocks; proxy area {sum(f['proxy_area_deg2'] for f in fields):.2f} deg²")


if __name__=='__main__':
    choose()
