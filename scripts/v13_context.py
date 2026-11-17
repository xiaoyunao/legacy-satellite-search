"""Index South PS1 candidate groups and nearby extended-galaxy background."""
import argparse
import os
from pathlib import Path

from astropy.coordinates import SkyCoord
import fitsio
import numpy as np
from scipy.spatial import cKDTree

from ls_satsearch.expansion import unit
from ls_satsearch.run import read_csv, sha, write_csv, write_json


def cross_field(rows):
    """Reconcile only groups that came from different adjacent search cores."""
    rows = sorted(rows,key=lambda r:(-float(r['ranking']),r['group_id']))
    if not rows:
        return []
    ra,dec,rh = np.array([[float(r[k]) for k in ('ra_deg','dec_deg','rh_arcmin')] for r in rows]).T
    points=unit(ra,dec)
    tree=cKDTree(points)
    used=np.zeros(len(rows),dtype=bool)
    output=[]
    for i,r in enumerate(rows):
        if used[i]:
            continue
        nearby=tree.query_ball_point(points[i],2*np.sin(np.deg2rad(max(1,rh[i])/120)))
        for j in nearby:
            if used[j] or (j != i and r['field']==rows[j]['field']):
                continue
            # North/South RA wrap and cos(dec) are handled in chord distance.
            separation = np.linalg.norm(points[i]-points[j])
            if separation<=2*np.sin(np.deg2rad(max(1,min(rh[i],rh[j]))/120)):
                used[j]=True
                output.append(dict(rows[j],review_group_id=r['group_id'],is_review_anchor=i==j))
    return output


def annotate(members, galaxies, names, environments):
    coords=SkyCoord(galaxies['RA'],galaxies['DEC'],unit='deg')
    tree=cKDTree(coords.cartesian.xyz.value.T)
    maximum = max(8,2*float(np.max(galaxies['DIAM'])))
    known=Path('references/codex_benchmark_sources/offical_delve_census_refgalaxy_list.csv')
    dwarfs=[r for r in read_csv(known) if r.get('ra') and r.get('dec') and r.get('distance_modulus')]
    dwarf_coords=SkyCoord([float(r['ra']) for r in dwarfs],[float(r['dec']) for r in dwarfs],unit='deg')
    locations=SkyCoord([float(r['ra_deg']) for r in environments],
                       [float(r['dec_deg']) for r in environments],unit='deg')
    for row in members:
        sky=SkyCoord(float(row['ra_deg']),float(row['dec_deg']),unit='deg')
        c=tree.query_ball_point(sky.cartesian.xyz.value,2*np.sin(np.deg2rad(maximum/120)))
        result=dict(sga_neighbors=len(c))
        for env,d in zip(environments,sky.separation(locations).arcmin):
            if d <= float(env['context_arcmin']):
                result.update(known_environment=env['name'],known_environment_arcmin=d,
                              known_environment_interpretation=env['interpretation'])
                break
        if c:
            sep=coords[c].separation(sky).arcmin
            near = int(np.argmin(sep))
            near_index=c[near]
            angle=coords[c].position_angle(sky).rad-np.deg2rad(galaxies['PA'][c])
            major = galaxies['DIAM'][c]/2
            radius=sep*np.hypot(np.cos(angle),np.sin(angle)/galaxies['BA'][c])/major
            control=int(np.argmin(radius))
            host=c[control]
            result.update(nearest_sga=names[near_index],nearest_sga_arcmin=sep[near],
                          largest_ellipse_context=names[host] if radius[control]<=3 else None,
                          ellipse_radius_multiple=radius[control],
                          sga_overlap_1x=int(sum(radius<=1)),sga_overlap_3x=int(sum(radius<=3)))
        d = sky.separation(dwarf_coords).arcmin
        i=int(np.argmin(d))
        result.update(census_system=dwarfs[i]['name'],census_arcmin=d[i],
                      census_dm_difference=float(row['dm'])-float(dwarfs[i]['distance_modulus']))
        yield dict(row,**result,evidence='L0')


def run(nersc_root, output):
    discoveries=[p for p in sorted(output.glob('*/*/main/sky_group_candidates.csv'))]
    path=nersc_root/'masking/SGA2025-ellipse-v1.6-dr11-south.kd.fits'
    with fitsio.FITS(path) as f:
        galaxies=f[1].read(columns=['ra','dec','pa','ba','diam','ref_id','ref_cat'],upper=True)
    usable = np.isfinite(np.column_stack([galaxies[k] for k in ('RA','DEC','PA','BA','DIAM')])).all(axis=1)
    usable &= (galaxies['DIAM']>0)&(galaxies['BA']>0)&(galaxies['BA']<=1)&(galaxies['PA']>=0)
    galaxies=galaxies[usable]
    labels=np.char.add(np.char.strip(galaxies['REF_CAT'].astype(str)),
                       np.char.add(':',galaxies['REF_ID'].astype(str)))
    rows=[r for p in discoveries for r in read_csv(p) if r['representative']=='True']
    environment_path=Path('configs/v13/known_environment.csv')
    environments=read_csv(environment_path)
    result=[]
    for budget in ('0.1','0.3'):
        members=cross_field([r for r in rows if r['budget']==budget])
        result.extend(annotate(members,galaxies,labels,environments))
    write_csv(output/'candidate_context.csv',result)
    write_json(output/'candidate_context.json',dict(job=os.getenv('SLURM_JOB_ID'),
               sga_input=str(path),sga_sha256=sha(path),sga_rows=len(galaxies),
               candidate_inputs={str(p):sha(p) for p in discoveries},
               context_catalog_sha256=sha(environment_path),
               meaning='Elliptical separation uses DIAM/2, PA N through E, and BA. The 3x outline '
                       'is a background annotation, without changing any frozen threshold or mask.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('nersc_root',type=Path)
    p.add_argument('output',type=Path)
    run(**vars(p.parse_args()))
