"""Build an ICRS atlas from DR11 metadata, census masks and observed search rasters."""

import argparse
import hashlib
import json
import os
from pathlib import Path

import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy_healpix import HEALPix
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
from scipy.spatial import cKDTree

from ls_satsearch.data import Field, load_bricks, regional_primary, sample_pixels
from ls_satsearch.expansion import unit
from ls_satsearch.fields import Census
from ls_satsearch.regional_pilot import brick_covered
from ls_satsearch.remaining_footprint import moc_contains
from ls_satsearch.run import read_csv, settings, sha, write_csv, write_json


LAYERS = ('North BASS', 'South PS1', 'South DELVE', 'South DES')
COLORS = ('#345b93','#3c8257','#c18547','#8b507e')
HISTORY_ROOTS = (Path('first_batch'),Path('wide_gaps'),Path('wide_rollout'),
                 Path('../verification-v6'),Path('../discovery-v5'),Path('../holdout-v4'),
                 Path('../group-v3'),Path('../branch-v2'))


def observed(data, ra, dec):
    # Each raster is visited once per distinct field/census geometry. In the
    # cumulative layer, apply the common native region convention to legacy runs.
    all_scanned = np.zeros(len(ra),dtype=bool)
    recent = np.zeros(len(ra),dtype=bool)
    catalog = []
    unique = set()
    native = {k:regional_primary(ra,dec,k) for k in ('north','south')}
    raster_keys = ('geometry','mask','subdivision','census','root')
    for folder in [*sorted(Path('.').glob('regional_v12*')), *sorted(Path('.').glob('regional_*')),
                   *HISTORY_ROOTS]:
        pattern = '**/results/summary/*/manifest.json' if not folder.name.startswith('regional_') else (
            'results/summary/*/manifest.json')
        for path in sorted(folder.glob(pattern)):
            if path.parent.parent.parent.parent.name.startswith(('matched_','table8_')):
                continue
            m=json.loads(path.read_text())
            if m.get('status') != 'complete' or m.get('depth') != 'base':
                continue
            f=m.get('field',{})
            if f.get('role') not in ('pilot_dev','pilot_eval','deep_control'):
                continue
            o=m.get('inputs',{})
            if not all(k in o for k in raster_keys):
                continue
            region=m['config'].get('region','south')
            geometry=o['geometry']
            identity=(*geometry[:3],region,o['census'])
            if identity in unique:
                continue
            unique.add(identity)
            key = {k:o[k] for k in (*raster_keys,'region','regional_primary') if k in o}
            name=f"{f['id']}-{hashlib.sha256(json.dumps(key).encode()).hexdigest()[:12]}"
            cache=data/'cache'/name/'coverage.npy'
            field=Field(*geometry)
            x,y=field.xy(ra,dec)
            core=(abs(x)<field.width*30)&(abs(y)<field.width*30)&native[region]
            new=folder.name.startswith('regional_v12')
            catalog.append(dict(field=f['id'],ra_deg=f['ra'],dec_deg=f['dec'],region=region,
                       cohort=f.get('layer'),width=f['width'],round12=new,usable_raster=cache.is_file(),
                       native_manifest_area_deg2=m['area_deg2'],manifest_sha256=sha(path),
                       job=m.get('slurm_job_id')))
            if cache.is_file():
                raster=np.load(cache,mmap_mode='r',allow_pickle=False)
                ii=np.flatnonzero(core)
                valid=ii[raster[sample_pixels(field,raster,x[ii],y[ii])]]
                all_scanned[valid]=True
                if new:
                    recent[valid]=True
    return recent,all_scanned,catalog


def save(fig, stem):
    for ext in ('pdf','png','svg'):
        dest=stem.with_suffix('.'+ext)
        fig.savefig(dest,dpi=200)
        if ext=='svg':
            dest.write_text('\n'.join(line.rstrip() for line in dest.read_text().splitlines())+'\n')
    plt.close(fig)


def plot(output, ra, dec, eligible, recent, searched, depths, density, purity, external, candidates):
    x, y = np.deg2rad(180-ra), np.deg2rad(dec)
    fig,axes=plt.subplots(3,2,figsize=(12,12.3),layout='constrained',
                         subplot_kw=dict(projection='mollweide'))
    ax=axes[0,0]
    for layer,color,mask in zip(LAYERS,COLORS,eligible):
        ax.scatter(x[mask],y[mask],s=1,c=color,label=layer,edgecolors='none',rasterized=True)
    ax.set_title('Primary science footprint (brick proxy)')
    ax.legend(loc='lower center',bbox_to_anchor=(.5,-.27),ncol=2,fontsize=7,frameon=False)
    ax=axes[0,1]
    inside=np.logical_or.reduce(eligible)
    for mask,color,label in ((inside & ~searched,'#d9dce0','Eligible proxy, not scanned'),
                             (searched & ~recent,'#98a5be','Prior measured cores'),
                             (recent,'#254775','Round 12 measured cores')):
        ax.scatter(x[mask],y[mask],s=1,c=color,edgecolors='none',rasterized=True,label=label)
    if external.any():
        use=external&inside
        ax.scatter(x[use],y[use],marker='.',s=2,c='#bf7970',alpha=.45,rasterized=True,label='Euclid imaging coverage')
    candidate_legend=[]
    for code,shape,c in (('L0','o','#cc630c'),('known','^','#325328'),('Tan Table 8','D','#6c528e')):
        sub=[r for r in candidates if r['plot_level']==code]
        if sub:
            ax.scatter(np.deg2rad([180-float(r['ra_deg']) for r in sub]),
                       np.deg2rad([float(r['dec_deg']) for r in sub]),s=9,c=c,marker=shape,zorder=3)
            candidate_legend.append(Line2D([0],[0],marker=shape,color=c,ls='',label=code))
    seam_ra=np.arange(0.,360.,1.)
    seam_dec=np.full_like(seam_ra,32.375)
    use=regional_primary(seam_ra,seam_dec,'north')
    ax.plot(np.deg2rad(180-seam_ra),np.where(use,np.deg2rad(seam_dec),np.nan),
            c='black',lw=.6,ls=':',label='Native boundary (declination segment)')
    ax.set_title('Observed search masks and round 12 groups')
    ax.legend(handles=ax.get_legend_handles_labels()[0]+candidate_legend,fontsize=7,
              bbox_to_anchor=(.5,-.14),loc='upper center',frameon=False,ncol=2)
    for ax,values,title,cm,limits in (
        (axes[1,0],depths[0],r'$g$ brick PSF depth (5σ, mag)','viridis',(22,26)),
        (axes[1,1],depths[1],r'$r$ brick PSF depth (5σ, mag)','viridis',(22,26)),
        (axes[2,0],density,r'$log_{10}$ selected PSF density (deg$^{-2}$)','magma',(2,4)),
        (axes[2,1],purity,'PSF fraction of quality-cut sources','cividis',(0,1))):
        use=np.isfinite(values)
        ax.scatter(x[inside],y[inside],s=.8,c='#e6e8eb',edgecolors='none',rasterized=True)
        sc=ax.scatter(x[use],y[use],c=values[use],s=2 if ax in axes[2] else 1,
                      cmap=cm,vmin=limits[0],vmax=limits[1],edgecolors='none',rasterized=True)
        fig.colorbar(sc,ax=ax,orientation='horizontal',fraction=.05,pad=.08)
        ax.set_title(title)
    for ax in axes.flat:
        ax.grid(alpha=.25)
        ax.set_xticklabels([])
        ax.tick_params(labelsize=7)
    save(fig,output/'dr11_search_atlas')


def run(output):
    root,data,_=settings()
    output.mkdir(exist_ok=True,parents=True)
    grid=HEALPix(nside=256,order='ring')
    lon,lat=grid.healpix_to_lonlat(np.arange(grid.npix))
    ra,dec=lon.deg,lat.deg
    cell=grid.pixel_area.to_value(u.deg**2)
    high=abs(SkyCoord(ra,dec,unit='deg').galactic.b.deg)>=25
    atlas=Census(data)
    census={k:atlas.accept(ra,dec,k) for k in (1,2,3)}
    depths=np.full((2,len(ra)),np.nan)
    eligibility, raw, owned = {}, {}, {}
    for region in ('north','south'):
        bricks=load_bricks(root,region)
        tree=cKDTree(unit(bricks['RA'],bricks['DEC']))
        gr=(bricks['PSFDEPTH_G']>0)&(bricks['PSFDEPTH_R']>0)
        good=gr&(bricks['EBV']<.1)&np.isfinite(bricks['PSFSIZE_G']+bricks['PSFSIZE_R'])
        owning=regional_primary(ra,dec,region)
        raw[region] = brick_covered(ra,dec,tree,bricks,np.ones(len(bricks),dtype=bool))
        owned[region]=owning&brick_covered(ra,dec,tree,bricks,gr)
        selected=owning&high&brick_covered(ra,dec,tree,bricks,good)
        eligibility[region]=selected
        ids=np.flatnonzero(owned[region])
        _,index=tree.query(unit(ra[ids],dec[ids]))
        for j,k in enumerate('GR'):
            depths[j,ids]=bricks[f'PSFDEPTH_{k}'][index]
        depths[depths<=0]=np.nan
    layers = [eligibility['north']]+[eligibility['south']&census[k] for k in (3,2,1)]
    recent, searched, catalog=observed(data,ra,dec)
    mocs=sorted((data/'resources/v9/mocs').glob('*.fits'))
    external=[(p.name,moc_contains(p,ra,dec)) for p in mocs]
    union=np.logical_or.reduce([r[1] for r in external]) if external else np.zeros(len(ra),dtype=bool)
    metrics, candidates = {}, []
    for path in sorted(Path('results/v12/discovery').glob('*/*/field_metrics.csv')):
        metrics.update({r['field']: r for r in read_csv(path)})
        good_ref=path.parent/'main/group_review_summary.csv'
        checked={r['group_id']:r for r in read_csv(good_ref)} if good_ref.exists() else {}
        for r in read_csv(path.parent/'main/sky_group_candidates.csv'):
            if r['representative']!='True' or r['budget']!='0.3':
                continue
            fit=checked.get(r['group_id'],{})
            known=fit.get('nearest_known_arcmin')
            possible_known=bool(known) and float(known)<2
            candidates.append({**r,**fit,'layer':path.parent.name,'evidence_level':'L0',
                               'plot_level':'known' if possible_known else 'L0',
                               'near_known_catalog_position':possible_known})
    # Approximate display of the per-field source diagnostics. The actual field
    # denominators are the manifest area rather than the HEALPix rendering.
    density=np.full(len(ra),np.nan); purity=density.copy()
    for meta in catalog:
        if meta['field'] not in metrics:
            continue
        m=metrics[meta['field']]
        f=Field(meta['ra_deg'],meta['dec_deg'],meta['width'],1/6,buffer=0)
        x,y=f.xy(ra,dec)
        here=(abs(x)<f.width*30)&(abs(y)<f.width*30)&recent
        psf,total=int(m['inner_psf']),int(m['inner_psf'])+int(m['inner_non_psf'])
        if total and psf and float(m['area_deg2'])>0:
            density[here]=np.log10(psf/float(m['area_deg2']))
            purity[here]=psf/total
    write_csv(output/'searched_field_manifest_index.csv',catalog)
    write_csv(output/'candidate_index.csv',candidates)
    write_csv(output/'sky_area.csv',[dict(layer=l,eligible_brick_proxy_deg2=p.sum()*cell,
                scanned_in_eligible_proxy_deg2=(p&searched).sum()*cell,
                remaining_brick_proxy_deg2=(p&~searched).sum()*cell,
                round12_raster_sample_deg2=(p&recent).sum()*cell,
                euclid_public_imaging_proxy_deg2=(p&union).sum()*cell) for l,p in zip(LAYERS,layers)])
    write_csv(output/'geometry.csv',[dict(region=r,brick_geometric_proxy_deg2=raw[r].sum()*cell,
                    region_owned_gr_proxy_deg2=owned[r].sum()*cell,
                    high_b_low_ebv_gr_proxy_deg2=eligibility[r].sum()*cell)
                    for r in ('north','south')])
    write_json(output/'manifest.json',dict(nside=grid.nside,frame='ICRS',job=os.getenv('SLURM_JOB_ID'),
               measured_field_count=sum(r['usable_raster'] for r in catalog),
               mocs={p.name:sha(p) for p in mocs},
               area_notes='Brick geometric footprint is a metadata proxy. Round 12 native areas are in the field tables. '
                  'The cumulative raster union uses only available cached search masks; missing rasters are flagged. '
                  'Euclid is public imaging coverage, not a published satellite search mask. Two-arcminute catalog proximity '
                  'is a visual overlay and not a confirmed identity.'))
    with plt.rc_context({'font.family':'serif','font.size':9,'svg.fonttype':'none','pdf.fonttype':42}):
        table8={r['key'] for r in read_csv(Path('configs/v12/table8/benchmarks.csv'))}
        known=[dict(ra_deg=r['ra'],dec_deg=r['dec'],plot_level='Tan Table 8') for r in read_csv(Path(
            'references/codex_benchmark_sources/offical_delve_census_refgalaxy_list.csv')) if r['key'] in table8]
        plot(output,ra,dec,layers,recent,searched,depths,density,purity,union,candidates+known)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('output',type=Path)
    run(p.parse_args().output)
