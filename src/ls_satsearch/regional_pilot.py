"""Register and evaluate real DR11 pilots by observing region and census assignment."""
import argparse
import json
import os
from pathlib import Path

import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy_healpix import HEALPix
import numpy as np
from scipy.spatial import cKDTree
import yaml

from .data import Field, load_bricks, regional_primary
from .expansion import core_disjoint, field_bounds, unit
from .fields import Census
from .group_budget import evaluate
from .run import sha, write_csv, write_json


COHORTS = ('north', 'south_ps1', 'south_delve', 'south_des')


def previous_cores(additional=()):
    files = [Path(f'configs/{v}/fields.yaml') for v in ('v4', 'v5/weak')]
    files += [Path(f'results/v7/{n}/fields.yaml') for n in ('gap_registration','rollout_registration')]
    files += [Path(f'results/{v}/registration/fields.yaml') for v in ('v5', 'v6', 'v7')]
    files += [Path('configs/v11/north/controls.yaml'),*additional]
    rows = [f for path in files for f in yaml.safe_load(path.read_text())['fields']]
    return list(dict.fromkeys(field_bounds(Field(f['ra'],f['dec'],f['width'],1/6,buffer=0))
                              for f in rows)), {str(path):sha(path) for path in files}


def brick_covered(ra, dec, kd, bricks, good):
    _, idx = kd.query(unit(ra,dec),k=4)
    b = bricks[idx]
    dra = (ra[:,None]-b['RA1'])%360
    inside = (dra<(b['RA2']-b['RA1'])%360) & (dec[:,None]>=b['DEC1']) & (dec[:,None]<b['DEC2'])
    return np.any(inside & good[idx],axis=1)


def audit_registration(root, data, files, output):
    atlas = Census(data)
    records = []
    for path in files:
        specs = yaml.safe_load(path.read_text())['fields']
        region = specs[0]['region']
        bricks = load_bricks(root,region)
        kd = cKDTree(unit(bricks['RA'],bricks['DEC']))
        good = (bricks['PSFDEPTH_G']>0)&(bricks['PSFDEPTH_R']>0)&(bricks['EBV']<.10)
        good &= np.isfinite(bricks['PSFSIZE_G']+bricks['PSFSIZE_R'])
        for f in specs:
            field = Field(f['ra'],f['dec'],f['width'],1/6,buffer=0)
            axis = np.linspace(-field.width*30,field.width*30,21)
            ra,dec = field.sky(*np.meshgrid(axis,axis))
            ra,dec = ra.ravel(),dec.ravel()
            covered = brick_covered(ra,dec,kd,bricks,good)
            covered &= regional_primary(ra,dec,region)
            covered &= abs(SkyCoord(ra,dec,unit='deg').galactic.b.deg)>=25
            if f.get('survey') is not None:
                covered &= atlas.accept(ra,dec,f['survey'])
            records.append(dict(field=f['id'],region=region,
                original_proxy_deg2=f['proxy_area_deg2'],
                contained_brick_proxy_deg2=float(covered.mean()*field.width**2)))
    write_csv(output,records)


def plan_all(root, data, params, output, cohorts, additional=()):
    spec = yaml.safe_load(params.read_text())
    old, inputs = previous_cores(additional)
    atlas = Census(data)
    rng = np.random.default_rng(spec['seed'])
    grid = HEALPix(nside=64, order='ring')
    lon,lat = grid.healpix_to_lonlat(np.arange(grid.npix))
    ra,dec = lon.deg,lat.deg
    high = abs(SkyCoord(ra,dec,unit='deg').galactic.b.deg) >= spec['min_abs_b']
    chosen = []
    for region in ('north','south'):
        bricks = load_bricks(root, region)
        kd = cKDTree(unit(bricks['RA'],bricks['DEC']))
        good = (bricks['PSFDEPTH_G']>0)&(bricks['PSFDEPTH_R']>0)&(bricks['EBV']<spec['max_ebv'])
        good &= np.isfinite(bricks['PSFSIZE_G']+bricks['PSFSIZE_R'])
        eligible = high & (abs(dec)<74)
        eligible &= regional_primary(ra,dec,region)
        _, index = kd.query(unit(ra,dec))
        eligible &= good[index]
        # Fixed, seeded order independent of all density peaks in LS.
        ordering = rng.permutation(np.flatnonzero(eligible))
        for name in cohorts:
            rule = spec[name]
            if rule['region']!=region:
                continue
            width = rule['width']
            axis = np.linspace(-width*30,width*30,21)
            xy = np.meshgrid(axis,axis)
            block = []
            for pos in ordering:
                f = Field(float(ra[pos]),float(dec[pos]),width,1/6,buffer=0)
                bounds = field_bounds(f)
                if not core_disjoint(bounds,old):
                    continue
                a,d = f.sky(*xy)
                a,d = a.ravel(),d.ravel()
                _, nearest = kd.query(unit(a,d))
                primary = regional_primary(a,d,region)
                # North has an explicit native boundary. New South cores are
                # kept strictly on the opposite side; no production mask change.
                if not primary.all():
                    continue
                if spec.get('check_brick_geometry', False):
                    covered = brick_covered(a,d,kd,bricks,good)
                else:
                    covered = good[nearest]
                valid = covered & (abs(SkyCoord(a,d,unit='deg').galactic.b.deg)>=spec['min_abs_b'])
                census = {k:atlas.accept(a,d,k) for k in (1,2,3)}
                if 'survey' in rule:
                    valid &= census[rule['survey']]
                fraction = float(valid.mean())
                if fraction < rule['minimum']:
                    continue
                i = len(block)
                block.append(dict(id=f'v11_{name}_{i+1:02d}',ra=f.ra,dec=f.dec,width=width,
                                  role='pilot_dev' if i<rule['development'] else 'pilot_eval',
                                  layer=name,region=region,proxy_area_deg2=width**2*fraction,
                                  proxy_coverage=fraction,proxy_census_fractions={k:float(v.mean()) for k,v in census.items()},
                                  **({'survey':rule['survey']} if 'survey' in rule else {})))
                old.append(bounds)
                if len(block)==rule['count']:
                    break
            folder = output/name
            folder.mkdir(parents=True,exist_ok=True)
            cohort = folder/'fields.yaml'
            cohort.write_text(yaml.safe_dump(dict(seed=spec['seed'],plan_sha256=sha(params),
                                                  previous_fields_sha256=inputs,fields=block),sort_keys=False))
            cfg_path = 'configs/v11/north/search.yaml' if region=='north' else 'configs/v7/search.yaml'
            (folder/'search.yaml').write_bytes(Path(cfg_path).read_bytes())
            if name=='south_ps1':
                policy = json.loads(Path('configs/v7/production.json').read_text())
                write_json(folder/'production.json',dict(policy,field_file_sha256=sha(cohort)))
            print(f'{name}: {len(block)}/{rule["count"]} cores, '
                  f'{sum(f["proxy_area_deg2"] for f in block):.1f} proxy deg²',flush=True)
            chosen.extend(block)
    write_json(output/'registration.json', dict(job=os.environ.get('SLURM_JOB_ID'),
               plan_sha256=sha(params), cores=len(chosen)))


def footprint(root, data, output):
    grid = HEALPix(nside=256,order='ring')
    lon,lat = grid.healpix_to_lonlat(np.arange(grid.npix))
    ra,dec = lon.deg,lat.deg
    coords = unit(ra,dec)
    gal_b = SkyCoord(ra,dec,unit='deg').galactic.b.deg
    atlas = Census(data)
    survey = np.zeros(len(ra),dtype=int)
    for k in (1,2,3):
        survey[atlas.accept(ra,dec,k)] = k
    pixel = grid.pixel_area.to_value(u.deg**2)
    raw = {}
    rows = []
    for region in ('north','south'):
        bricks = load_bricks(root,region)
        distance,index = cKDTree(unit(bricks['RA'],bricks['DEC'])).query(coords)
        valid = (distance<np.deg2rad(.23))&(bricks['PSFDEPTH_G'][index]>0)&(bricks['PSFDEPTH_R'][index]>0)
        raw[region] = valid
        owned = valid & regional_primary(ra,dec,region)
        clean = owned & (abs(gal_b)>=25) & (bricks['EBV'][index]<.1)
        for code,label in enumerate(('masked_or_unassigned','DES_Y6','DELVE_DR3','PS1_DR1')):
            group = survey==code
            rows.append(dict(region=region,census=label,raw_region_gr_proxy_deg2=float((valid&group).sum()*pixel),
                             assigned_region_gr_proxy_deg2=float((owned&group).sum()*pixel),
                             high_lat_low_ebv_proxy_deg2=float((clean&group).sum()*pixel)))
    output.mkdir(parents=True,exist_ok=True)
    write_csv(output/'regional_proxy_area.csv',rows)
    write_json(output/'regional_proxy_area.json',dict(job=os.getenv('SLURM_JOB_ID'),nside=grid.nside,
               overlapping_raw_gr_proxy_deg2=float((raw['north']&raw['south']).sum()*pixel),
               scope='Nearest DR11 brick metadata, not effective search pixels. Census codes after its BADBITS; '
                     'raw visit sharing and historical search methods are separate questions.'))


def combine(summary, fields_path, output, controls=None, policy=None):
    # JSON manifests serialize YAML's numeric census-code keys as strings.
    specs = json.loads(json.dumps(yaml.safe_load(fields_path.read_text())['fields']))
    expected = {r['id']:r for r in specs}
    manifests = {}
    for path in summary.glob('*/manifest.json'):
        m = json.loads(path.read_text())
        if m['status']=='complete' and m['field']==expected.get(m['field']['id']):
            manifests[m['field']['id']] = path
    if manifests.keys()!=expected.keys():
        raise ValueError(f'Missing completed fields: {sorted(expected.keys()-manifests.keys())}')
    output.mkdir(parents=True,exist_ok=True)
    rows = []
    for field,path in sorted(manifests.items()):
        m = json.loads(path.read_text())
        cond = m['observing_conditions_source_sample']
        rows.append(dict(field=field,role=m['field']['role'],area_deg2=m['area_deg2'],
                         proxy_area_deg2=m['field']['proxy_area_deg2'],job=m['slurm_job_id'],
                         inner_psf=m['cutflow']['inner_psf'],inner_non_psf=m['cutflow']['inner_other'],
                         inner_psf_faint=m['cutflow']['inner_psf_faint'],
                         inner_non_psf_faint=m['cutflow']['inner_other_faint'],
                         g_depth=(cond['G']['depth5_dered'] or [None]*3)[1],
                         r_depth=(cond['R']['depth5_dered'] or [None]*3)[1],
                         g_seeing=(cond['G']['seeing'] or [None]*3)[1],
                         wall_seconds=m['wall_seconds'],model_sha256=m['model_sha256'],
                         fields_sha256=m['fields_sha256'],manifest_sha256=sha(path)))
    write_csv(output/'field_metrics.csv',rows)
    branches = ('main',) if policy or controls is None else ('main','near','far')
    for branch in branches:
        target = output/branch
        if policy is not None:
            evaluate(summary,target,apply=policy,channels_only=('A_base',))
            continue
        dev = target/'development_input'
        dev.mkdir(parents=True,exist_ok=True)
        for field,path in manifests.items():
            if expected[field]['role']=='pilot_dev':
                link = dev/path.parent.name
                if not link.exists():
                    link.symlink_to(path.parent.resolve(),target_is_directory=True)
        evaluate(dev,target/'calibration',branch=branch,channels_only=('A_base',))
        used = target/'evaluation_input'
        used.mkdir(exist_ok=True)
        evaluation = [p.parent for k,p in manifests.items() if expected[k]['role']=='pilot_eval']
        if controls:
            evaluation.extend(p.parent for p in controls.glob('*/manifest.json'))
        for path in evaluation:
            link = used/path.name
            if not link.exists():
                link.symlink_to(path.resolve(),target_is_directory=True)
        evaluate(used,target,branch=branch,apply=target/'calibration/sky_group_policy.json',
                 channels_only=('A_base',))


if __name__=='__main__':
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='mode',required=True)
    reg = sub.add_parser('register')
    reg.add_argument('--output',type=Path,required=True)
    reg.add_argument('--plan',type=Path,default=Path('configs/v11/regional_plan.yaml'))
    reg.add_argument('--exclude-fields',type=Path,action='append',default=[])
    reg.add_argument('--cohorts',nargs='+',choices=COHORTS,default=COHORTS)
    fp = sub.add_parser('footprint')
    fp.add_argument('--output',type=Path,required=True)
    audit = sub.add_parser('audit-registration')
    audit.add_argument('output',type=Path)
    audit.add_argument('fields',type=Path,nargs='+')
    cc = sub.add_parser('combine')
    cc.add_argument('summary',type=Path)
    cc.add_argument('fields',type=Path)
    cc.add_argument('output',type=Path)
    cc.add_argument('--controls',type=Path)
    cc.add_argument('--policy',type=Path)
    args = p.parse_args()
    if args.mode=='register':
        plan_all(Path(os.environ['LS_DR11_ROOT']), Path(os.environ['LS_SAT_DATA']),
                 args.plan,args.output,args.cohorts,args.exclude_fields)
    elif args.mode=='footprint':
        footprint(Path(os.environ['LS_DR11_ROOT']),Path(os.environ['LS_SAT_DATA']),args.output)
    elif args.mode=='audit-registration':
        audit_registration(Path(os.environ['LS_DR11_ROOT']),Path(os.environ['LS_SAT_DATA']),args.fields,args.output)
    else:
        combine(args.summary,args.fields,args.output,args.controls,args.policy)
