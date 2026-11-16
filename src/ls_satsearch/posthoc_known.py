"""Audit a known system associated after the frozen holdout scan."""

import argparse
import json
from pathlib import Path

from astropy.coordinates import SkyCoord
import numpy as np

from .data import select
from .run import field_cache, read_csv, settings, write_csv
from .search import CMD, load_isochrone


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('field')
    parser.add_argument('name')
    args = parser.parse_args()
    root,data,cfg = settings()
    manifest = Path('results/summary')/f'{args.field}-base'/'manifest.json'
    spec = json.loads(manifest.read_text())['field']
    table = Path('references/codex_benchmark_sources/offical_delve_census_refgalaxy_list.csv')
    target = next(r for r in read_csv(table) if r['name']==args.name)
    ra,dec,d,dm,rh_pc = (float(target[k]) for k in ('ra','dec','distance','distance_modulus','rhalf_sph_physical'))
    rh = np.degrees(np.arctan(rh_pc/(1000*d)))*60
    field,sources,area,_ = field_cache(root,data,spec,cfg,None)
    sample,_,_,_,selected = select(sources,field,area,cfg)
    cmd = CMD(sample,load_isochrone(data/'resources'/cfg['isochrone']),cfg).weights(dm)[0]
    x,y = field.xy(ra,dec)
    rho = np.hypot(sample[:,0]-x,sample[:,1]-y)
    output = []
    for region,use in [('centre',rho<=1.5*rh),('annulus',(rho>=3.5*rh)&(rho<=6*rh))]:
        counts = {}
        for column,bit,label in [('FITBITS',0,'forced'),('MASKBITS',17,'resolved'),('MASKBITS',13,'cluster')]:
            flag = (sources[column][selected]&(1<<bit))!=0
            counts[label+'_cmd'] = int((flag&use&cmd).sum())
        output.append(dict(name=args.name,field=args.field,region=region,truth_dm=dm,rh_arcmin=rh,
                           psf=int(use.sum()),cmd_psf=int((use&cmd).sum()),**counts))
    ref = SkyCoord(ra,dec,unit='deg')
    groups = []
    for r in read_csv(Path('results/holdout/sky_group_candidates.csv')):
        if r['field']!=args.field or float(r['budget'])!=.3 or r['representative']!='True':
            continue
        offset = ref.separation(SkyCoord(float(r['ra_deg']),float(r['dec_deg']),unit='deg')).arcmin
        if offset <= max(rh,float(r['rh_arcmin'])):
            groups.append(dict(name=args.name,group_id=r['group_id'],offset_arcmin=float(offset),
                               delta_dm=float(r['dm'])-dm,within_reference_rh=offset<=rh,
                               score=r['score'],blind_dm=r['dm'],seed_rh_arcmin=r['rh_arcmin']))
    out = Path('results/holdout')
    write_csv(out/'known_processing_audit.csv',output)
    write_csv(out/'known_association.csv',groups)


if __name__=='__main__':
    main()
