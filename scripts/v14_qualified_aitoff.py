"""Galactic Aitoff views sampled from the accepted qualified WCS-mask polygons."""
import argparse
import json
import os
from pathlib import Path

from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy_healpix import HEALPix
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
import numpy as np
from scipy.spatial import cKDTree
import shapely

from ls_satsearch.data import load_bricks, regional_primary
from ls_satsearch.expansion import unit
from ls_satsearch.run import read_csv, sha, write_csv, write_json
from scripts.v14_mask_tiles import cache_key

MASKS=Path('results/v14/production_integration/masks')
COLORS=['#6d7880','#af583d','#2e8679','#5068a4','#7d538a']
LABELS=['Unassigned or census masked','DES Y6','DELVE DR3','PS1 DR1','Boundary ambiguity']


def footprint(nside):
    receipt=json.loads((MASKS/'post_outside_C_registration_20261120.json').read_text())
    path=Path(receipt['registration'])
    if sha(path)!=receipt['registration_sha256']:
        raise ValueError('Area registration changed')
    reg=json.loads(path.read_text())
    tile=Path(reg['output'])
    index=tile/'vector_index.json'
    accepted=json.loads((tile/'overlay_repair_registration.json').read_text())
    if accepted['vector_index_sha256']!=sha(index):
        raise ValueError('Accepted mask index changed')
    by_key={cache_key(r,reg):r['region'] for r in reg['records']}
    grid=HEALPix(nside=nside,order='ring',frame='galactic')
    sky=grid.healpix_to_skycoord(np.arange(grid.npix))
    icrs=sky.icrs
    ra=icrs.ra.deg
    sin_dec=np.sin(icrs.dec.rad)
    order=ra.argsort()
    sorted_ra=ra[order]
    bits=np.zeros(grid.npix,dtype=np.uint8)
    regions=np.zeros_like(bits)
    keys=set()
    for row in json.loads(index.read_text())['records']:
        if row['classification']!='qualified_discovery':
            continue
        key=row['cache_key']
        region=2 if by_key[key]=='north' else 1
        for label,bound in enumerate(row['bounds']):
            if bound is None:
                continue
            lo,hi=np.searchsorted(sorted_ra,[bound[0],bound[2]])
            indices=order[lo:hi]
            use=indices[(sin_dec[indices]>=bound[1])&(sin_dec[indices]<=bound[3])]
            if not len(use):
                continue
            file=Path(reg['cache'])/f'{key}-{label}.wkb'
            raw=file.read_bytes()
            from hashlib import sha256
            if sha256(raw).hexdigest()!=row['geometry_sha256'][file.name]:
                raise ValueError('Accepted geometry changed')
            hit=use[shapely.intersects_xy(shapely.from_wkb(raw),ra[use],sin_dec[use])]
            bits[hit]|=1<<label
            regions[hit]|=region
            keys.add(key)
    return sky,bits,regions,dict(registration_sha256=sha(path),vector_index_sha256=sha(index),
                               mask_keys_sampled=len(keys),nside=nside)


def coordinates(ra,dec):
    sky=SkyCoord(ra,dec,unit='deg').galactic
    return -sky.l.wrap_at(180*u.deg).rad,sky.b.rad


def axes_map(ax,title):
    ax.set_title(title,pad=14)
    ax.grid(color='#858c94',alpha=.35,lw=.5)
    ax.set_xticklabels([f'{x%360}°' for x in range(150,-151,-30)])
    ax.set_xlabel('Galactic longitude',labelpad=9)
    ax.set_ylabel('Galactic latitude')


def depths(sky,regions,root):
    icrs=sky.icrs
    depth=np.full((len(sky),3),np.nan)
    brick_paths={}
    both=regions==3
    north=(regions==2)|(both&regional_primary(icrs.ra.deg,icrs.dec.deg,'north'))
    for region,use in (('north',north),('south',(regions>0)&~north)):
        path=root/region/f'survey-bricks-dr11-{region}.fits.gz'
        brick_paths[str(path)]=sha(path)
        bricks=load_bricks(root,region)
        good=(bricks['PSFDEPTH_G']>0)&(bricks['PSFDEPTH_R']>0)
        bricks=bricks[good]
        sep,idx=cKDTree(unit(bricks['RA'],bricks['DEC'])).query(unit(icrs.ra.deg[use],icrs.dec.deg[use]))
        chosen=bricks[idx]
        depth[use]=np.column_stack([chosen['PSFDEPTH_G']-2.5*np.log10(2),
                                    chosen['PSFDEPTH_R']-2.5*np.log10(2),chosen['EBV']])
        depth[np.flatnonzero(use)[sep>np.deg2rad(.22)]]=np.nan
    return depth,brick_paths


def save(fig,path):
    for suffix in ('.png','.pdf'):
        fig.savefig(path.with_suffix(suffix),dpi=175)
    plt.close(fig)


def main(output,private,known,nside):
    if not os.getenv('SLURM_JOB_ID') or 'final_private' not in private.parts:
        raise RuntimeError('Use allocated CPUs and private candidate storage')
    output.mkdir(parents=True,exist_ok=True)
    private.mkdir(parents=True,exist_ok=True)
    sky,bits,regions,receipt=footprint(nside)
    longitude=-sky.l.wrap_at(180*u.deg).rad
    latitude=sky.b.rad
    visible=bits>0
    labels=np.full(len(bits),4)
    for i in range(4):
        labels[bits==(1<<i)]=i
    cmap=ListedColormap(COLORS)
    norm=BoundaryNorm(np.arange(-.5,5.5),cmap.N)

    def backdrop(ax):
        ax.scatter(longitude[visible],latitude[visible],c=labels[visible],cmap=cmap,norm=norm,
                   s=.65,rasterized=True,linewidths=0)

    fig,ax=plt.subplots(figsize=(12,6.5),subplot_kw={'projection':'aitoff'},layout='constrained')
    backdrop(ax)
    axes_map(ax,'DR11 qualified search and Tan census assignments')
    for label,color in zip(LABELS,COLORS):
        ax.scatter([],[],c=color,s=20,label=label)
    ax.legend(loc='upper center',bbox_to_anchor=(.5,-.13),ncol=3,frameon=False)
    save(fig,output/'qualified_footprint')

    root=Path(os.environ['LS_DR11_ROOT'])
    depth,paths=depths(sky,regions,root)
    fig,axs=plt.subplots(2,2,figsize=(14,8),subplot_kw={'projection':'aitoff'},layout='constrained')
    for ax,i,band in zip(axs[0],range(2),'gr'):
        use=np.isfinite(depth[:,i])
        m=ax.scatter(longitude[use],latitude[use],c=depth[use,i],cmap='viridis',s=.65,linewidths=0,rasterized=True)
        axes_map(ax,f'LS {band} formal PSF depth · 10σ · brick summary')
        fig.colorbar(m,ax=ax,shrink=.62,label='Observed magnitude')
    for ax,i,title in zip(axs[1],(2,2),('Extinction within qualified footprint','Low latitude and elevated extinction')):
        use=np.isfinite(depth[:,i])
        colors=depth[use,i] if ax is axs[1,0] else ((np.abs(sky.b.deg[use])<25)|(depth[use,i]>=.10))
        m=ax.scatter(longitude[use],latitude[use],c=colors,cmap='magma',s=.65,linewidths=0,rasterized=True)
        axes_map(ax,title)
        bar=fig.colorbar(m,ax=ax,shrink=.62,label='E(B−V)' if ax is axs[1,0] else 'Condition flag')
        if ax is axs[1,1]:
            bar.set_ticks([0,1],labels=['Neither','|b| < 25° or E(B−V) ≥ 0.10'])
    save(fig,output/'ls_depth_and_conditions')

    if known.exists():
        rows=read_csv(known)
        fig,ax=plt.subplots(figsize=(13,7),subplot_kw={'projection':'aitoff'},layout='constrained')
        backdrop(ax)
        for marker,color,caption,condition in (
            ('o','#dbee92','Ordinary A recovery',lambda r:r['status']=='ordinary_spatial_match'),
            ('X','#f26d64','Covered and in-range, no A match',lambda r:r['status']=='no_retained_qualifying_spatial_match'),
            ('+','#292929','Outside coverage or distance',lambda r:r['status'] not in
             {'ordinary_spatial_match','no_retained_qualifying_spatial_match'})):
            selected=[r for r in rows if condition(r)]
            if selected:
                x,y=coordinates([float(r['ra_deg']) for r in selected],[float(r['dec_deg']) for r in selected])
                ax.scatter(x,y,marker=marker,c=color,s=29,label=caption,zorder=5)
        axes_map(ax,'Known-system recovery in the qualified DR11 search')
        ax.legend(loc='upper center',bbox_to_anchor=(.5,-.13),ncol=3,frameon=False)
        save(fig,output/'known_recovery')

    candidate=Path('results/v14/production_integration/reconciled/provisional_positions.csv')
    # Coordinates are held as a separate private layer, with no anonymous aliases.
    table=read_csv(candidate)
    columns=('ra_deg','dec_deg') if 'ra_deg' in table[0] else ('anchor_ra_deg','anchor_dec_deg')
    x,y=coordinates(*[[float(r[k]) for r in table] for k in columns])
    fig,ax=plt.subplots(figsize=(12,6.5),subplot_kw={'projection':'aitoff'},layout='constrained')
    backdrop(ax)
    ax.scatter(x,y,s=1.8,c='#131620',alpha=.55,rasterized=True,linewidths=0)
    axes_map(ax,'Private footprint and provisional production positions')
    save(fig,private/'provisional_positions')
    out_raster=private/'depth_raster.npz'
    np.savez_compressed(out_raster,bits=bits,regions=regions,depth=depth)
    area=4*np.pi*(180/np.pi)**2/len(bits)
    summaries=[]
    for i,label in enumerate(LABELS):
        use=visible&(labels==i)
        row=dict(census=label,display_sample_cells=int(use.sum()),sampled_area_deg2=area*use.sum())
        for j,band in enumerate('gr'):
            d=depth[use,j]
            d=d[np.isfinite(d)]
            row[f'{band}_10sigma_median']=float(np.median(d)) if len(d) else None
            row[f'{band}_valid_cells']=len(d)
        summaries.append(row)
    write_csv(output/'display_sampling.csv',summaries)
    write_json(output/'manifest.json',dict(receipt,job=os.environ['SLURM_JOB_ID'],
        brick_depth_sha256=paths,known_audit_sha256=sha(known) if known.exists() else None,
        output_sha256={p.name:sha(p) for p in output.iterdir() if p.suffix in {'.png','.pdf','.csv'}},
        sampled_qualified_deg2=area*visible.sum(),private_position_figures=True,
        depth_convention='10sigma from DR11 brick-level 5sigma PSF magnitude minus 2.5log10(2). Nearest gr-valid brick within 0.22 degrees on the represented coverage of the relevant hemisphere. Observed magnitudes, prior to extinction correction.',
        scope='Sampled display of accepted WCS mask polygons. Use the existing union ledger for formal solid angle. Formal noise depth and source response remain separate.'))
    print(dict(nside=nside,cells=int(visible.sum()),area_proxy=area*visible.sum()),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--private',type=Path,required=True)
    p.add_argument('--known',type=Path,required=True)
    p.add_argument('--nside',type=int,default=256)
    a=p.parse_args()
    main(a.output,a.private,a.known,a.nside)
