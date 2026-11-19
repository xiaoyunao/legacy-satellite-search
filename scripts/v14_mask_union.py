"""Union represented WCS-mask cells in RA/sin(Dec), without sky regridding."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
from time import monotonic

import astropy.units as u
from affine import Affine
import numpy as np
from rasterio.features import shapes
import shapely
from shapely.affinity import translate
from shapely.geometry import box,shape

from ls_satsearch.data import Field,ownership,regional_primary
from ls_satsearch.expansion import field_bounds
from ls_satsearch.fields import Census
from ls_satsearch.run import sha,write_csv,write_json

RAD=np.pi/180
ROOT=Path('results/v14/production_integration/masks')


def normalized(geometry):
    """Resolve the RA seam and clip cell corners to the physical sphere."""
    pieces=[];sky=box(0,-1,360,1)
    lo,_,hi,_=geometry.bounds
    for offset in range(int(np.floor(-hi/360)),int(np.ceil((360-lo)/360))+1):
        part=translate(geometry,xoff=360*offset).intersection(sky)
        if not part.is_empty:pieces.append(part)
    return shapely.union_all(pieces)


def as_geometry(mask,transform):
    polygons=[];repairs=0
    for geometry,value in shapes(mask.astype('uint8'),mask=mask,transform=transform):
        item=shape(geometry)
        if not item.is_valid:
            before=item.area;item=shapely.make_valid(item);repairs+=1
            if not np.isclose(item.area,before,rtol=1e-9,atol=1e-12):raise ValueError('Polygon validity repair changed represented area')
        polygons.append(item)
    return shapely.union_all(polygons),repairs


def extract(record,data,census):
    field=Field(*record['geometry']);path=data/record['raster']
    raster=np.load(path,mmap_mode='r',allow_pickle=False)
    if raster.dtype!=bool or raster.ndim!=2 or raster.shape[0]!=raster.shape[1]:raise ValueError('Not a binary WCS coverage raster')
    sub=record['subdivision'];cell=field.step/sub
    if len(raster)!=field.n*sub:raise ValueError('Raster and manifest sampling differ')
    axis=(np.arange(len(raster))+.5)*cell-field.limit;inner=np.flatnonzero(abs(axis)<field.width*30)
    mask=np.array(raster[np.ix_(inner,inner)],copy=True)
    rule='stored_owned_or_unpartitioned'
    if record['apply_ownership']:
        iy,ix=np.nonzero(mask);ra,dec=field.sky(axis[inner[ix]],axis[inner[iy]])
        chosen=ownership(ra,dec,record['apply_ownership']);mask[iy,ix]&=chosen
        unseamed=mask.sum()*(cell/60)**2
        seamed=mask.copy();seamed[iy,ix]&=regional_primary(ra,dec,record['region'])
        seamed_area=seamed.sum()*(cell/60)**2
        if np.isclose(unseamed,record['source_effective_deg2'],rtol=1e-10,atol=1e-9):rule='original_ownership_without_extra_seam'
        elif np.isclose(seamed_area,record['source_effective_deg2'],rtol=1e-10,atol=1e-9):
            mask=seamed;rule='original_ownership_plus_native_seam'
        else:raise ValueError('Historical ownership cannot reproduce original area: '+record['field'])
    count=int(mask.sum());area=count*(cell/60)**2
    if not np.isclose(area,record['source_effective_deg2'],rtol=1e-10,atol=1e-9):
        raise ValueError('Working-mask cells do not reproduce stored area: '+record['field'])
    iy,ix=np.nonzero(mask);ra,dec=field.sky(axis[inner[ix]],axis[inner[iy]])
    pixels=census.grid.lonlat_to_healpix(ra*u.deg,dec*u.deg);bits=census.bits[pixels]
    labels=np.zeros(mask.shape,dtype='uint8');values=np.where((bits&248)==0,bits&3,0)
    labels[iy,ix]=values
    cos=np.cos(field.dec*RAD);origin=inner[0]*cell-field.limit
    transform=Affine(cell/(60*cos),0,field.ra+origin/(60*cos),
        0,cell*RAD*cos/60,np.sin(field.dec*RAD)+origin*RAD*cos/60)
    geometries=[];repairs=0;before=0
    for label in range(4):
        geometry,n=as_geometry(mask&(labels==label),transform);before+=geometry.area/RAD;repairs+=n
        geometries.append(normalized(geometry) if not geometry.is_empty else geometry)
    if not np.isclose(before,area,rtol=1e-8,atol=1e-7):raise ValueError('Vectorized mask area differs from represented pixels')
    return geometries,dict(field=record['field'],manifest_sha256=record['manifest_sha256'],
        raster=record['raster'],raster_sha256=sha(path),classification=record['classification'],
        ownership_reconstruction=rule,working_pixel_arcsec=cell*60,valid_core_pixels=count,
        source_area_deg2=area,vectorized_area_before_seam_clip_deg2=before,
        normalized_area_deg2=sum(g.area for g in geometries)/RAD,geometry_repairs=repairs)


def run(window,output):
    if not os.getenv('SLURM_JOB_ID'):raise ValueError('Use an allocated NERSC CPU job')
    start=monotonic();data=Path(os.environ['LS_SAT_DATA']);inventory=ROOT/'inventory.json'
    saved=json.loads(inventory.read_text());census=Census(data)
    left,right,lo,hi=window
    if not 0<=left<right<=360 or not -90<=lo<hi<=90:raise ValueError('Pilot window must be a nonwrapping physical RA/Dec box')
    clip=box(left,np.sin(lo*RAD),right,np.sin(hi*RAD));layers={'all_ordinary_scanned':[[] for _ in range(4)],'qualified_production':[[] for _ in range(4)]}
    proofs=[]
    for record in saved['records']:
        center,half,bottom,top=field_bounds(Field(*record['geometry']))
        if bottom>hi or top<lo or abs((center-(left+right)/2+180)%360-180)>half+(right-left)/2:continue
        if record['classification'] in ('missing_actual_mask','known_recovery_control'):continue
        if sha(Path(record['manifest']))!=record['manifest_sha256']:raise ValueError('Mask manifest changed during inventory')
        geometries,proof=extract(record,data,census);proofs.append(proof)
        for label,g in enumerate(geometries):
            piece=g.intersection(clip)
            layers['all_ordinary_scanned'][label].append(piece)
            if record['classification']=='qualified_discovery':layers['qualified_production'][label].append(piece)
        print('ACTUAL_MASK_VECTORIZED',record['field'],proof['source_area_deg2'],flush=True)
    results=[];cache=data/'runs/v14/area_union_pilot';cache.mkdir(parents=True,exist_ok=True)
    for layer,parts in layers.items():
        unions=[shapely.union_all(items) for items in parts];total=shapely.union_all(unions)
        ambiguous=shapely.union_all([unions[i].intersection(unions[j]) for i in range(4) for j in range(i)])
        per_survey=[]
        for label,g in enumerate(unions):
            others=shapely.union_all([v for j,v in enumerate(unions) if j!=label])
            certain=g.difference(others)
            per_survey.append(dict(census_label=label,unambiguous_deg2=certain.area/RAD,
                represented_label_union_deg2=g.area/RAD))
        key=sha(inventory)[:12]+'-'+layer
        path=cache/(key+'.wkb');path.write_bytes(shapely.to_wkb(total))
        results.append(dict(layer=layer,union_deg2=total.area/RAD,
            summed_record_pieces_deg2=sum(g.area for items in parts for g in items)/RAD,
            census_boundary_ambiguity_deg2=ambiguous.area/RAD,census=per_survey,
            scratch_geometry=str(path.relative_to(data)),geometry_sha256=sha(path)))
    output.mkdir(parents=True,exist_ok=True);write_csv(output/'source_mask_checks.csv',proofs)
    write_json(output/'summary.json',dict(job=os.environ['SLURM_JOB_ID'],utc=datetime.now(timezone.utc).isoformat(),
        window_ra_dec_deg=window,mask_records=len(proofs),layers=results,seconds=monotonic()-start,
        input_inventory_sha256=sha(inventory),source_checks_sha256=sha(output/'source_mask_checks.csv'),
        code_sha256=sha(Path(__file__)),versions=dict(numpy=np.__version__,shapely=shapely.__version__),
        scope='Real bounded pilot, not full-project area. Exact planar union of the represented WCS-derived valid cells in equal-area RA/sinDec coordinates; no HEALPix or stellar-density regridding. Source-cell counts must reproduce each original area before union. RA seam/polar corners are handled geometrically. Census labels come from the fixed author map at each source cell center; cross-grid boundary disagreement is retained as an explicit ambiguity area rather than assigned arbitrary priority. This is working-mask area, not infinitely resolved exposure geometry, unexplored sky or a measured physical detectability-gain area.'))
    print('REAL_MASK_UNION_PILOT',results,flush=True)


def geometry_checks(output):
    """Numerical geometry tests only; these are not survey or recovery results."""
    mask=np.ones((7,9),bool);mask[2:5,3:6]=False
    transform=Affine(.01,0,100,0,.01*RAD,.2)
    geom,_=as_geometry(mask,transform)
    assert np.isclose(geom.area/RAD,mask.sum()*.01**2,rtol=1e-10)
    assert np.isclose(shapely.union_all([geom,geom]).area,geom.area,rtol=1e-12)
    seam=box(359.95,-.01,360.05,.01)
    assert np.isclose(normalized(seam).area,seam.area,rtol=1e-10)
    polar=box(10,.99,11,1.01)
    assert np.isclose(normalized(polar).area,.01,rtol=1e-12)
    write_json(output,dict(kind='synthetic_geometry_unit_validation_not_science',
        holes_preserved=True,duplicate_union_idempotent=True,RA_seam_area_preserved=True,
        polar_out_of_sphere_corners_clipped=True,code_sha256=sha(Path(__file__))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--window',type=float,nargs=4,default=[161.6,169.6,27.9,35.9]);p.add_argument('--output',type=Path,default=ROOT/'pilot')
    p.add_argument('--geometry-checks-only',type=Path);a=p.parse_args()
    geometry_checks(a.geometry_checks_only) if a.geometry_checks_only else run(a.window,a.output)
