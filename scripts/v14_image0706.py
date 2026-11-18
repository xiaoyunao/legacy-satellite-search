"""Measure public independent gr images at the frozen 0706 position on a CPU node."""
import json
import os
from pathlib import Path

import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.wcs import WCS
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import map_coordinates, minimum_filter
from scipy.spatial import cKDTree

from ls_satsearch.hsc_depth_audit import aperture, candidate_sources, robust_sigma
from ls_satsearch.matched import reddening, PS1_MODEL
from ls_satsearch.run import read_csv, sha, write_csv, write_json
from ls_satsearch.search import load_isochrone
from v12_footprint import save

RA,DEC=165.61216974832084,31.892121971411218


def read_image(path):
    with fits.open(path,memmap=False) as hdus:
        hdu=next((h for h in hdus if h.data is not None and h.data.ndim==2),None)
        if hdu is None:
            raise ValueError('Downloaded product has no 2D science-image HDU')
        image=np.asarray(hdu.data,dtype=float)
        header=hdu.header.copy()
        if 'BSOFTEN' in header:
            image=header.get('BOFFSET',0)+2*header['BSOFTEN']*np.sinh(image*np.log(10)/2.5)
        wcs=WCS(header).celestial
    if path.name.startswith('image-'):
        for kind in ('dq','weight'):
            support=path.with_name(path.name.replace('image-',kind+'-'))
            if support.is_file():
                with fits.open(support,memmap=False) as f:
                    mask=next(h.data for h in f if h.data is not None and h.data.ndim==2)
                    image[(mask!=0) if kind=='dq' else (~np.isfinite(mask)|(mask<=0))]=np.nan
    return image,wcs,header


def pixel_positions(wcs,sky):
    return np.stack(wcs.world_to_pixel(sky), axis=-1)


def safe_pixels(image,coords,margin=16):
    x,y=coords.T
    keep=(x>=margin)&(y>=margin)&(x<image.shape[1]-margin)&(y<image.shape[0]-margin)
    valid=np.zeros(len(coords),bool)
    if keep.any():
        supported=minimum_filter(np.isfinite(image),size=2*margin+1,mode='constant',cval=0)
        valid[keep]=supported[np.rint(y[keep]).astype(int),np.rint(x[keep]).astype(int)]
    return valid


def reference(folder,center):
    rows=read_csv(folder/'ps1.csv')
    values=np.array([[float(r.get(k) or 'nan') for k in ('raStack','decStack','gPSFMag','rPSFMag','gPSFMagErr','rPSFMagErr','iPSFMag','iKronMag')] for r in rows])
    valid_position=np.isfinite(values[:,:2]).all(axis=1)&(abs(values[:,1])<=90)&(values[:,0]>=0)&(values[:,0]<360)
    values=values[valid_position]
    good=np.isfinite(values).all(axis=1)&(values[:,2]>17)&(values[:,2]<21.8)&(values[:,3]>16.5)
    good&=(values[:,4]>0)&(values[:,5]>0)&(values[:,4]<.07)&(values[:,5]<.07)
    good&=(values[:,6]>0)&(values[:,7]>0)&(values[:,6]-values[:,7]<.05)
    sky=SkyCoord(values[:,0],values[:,1],unit='deg')
    radius=sky.separation(center).arcmin
    good&=(radius>1.0)&(radius<2.6)&(values[:,2]-values[:,3]>.0)&(values[:,2]-values[:,3]<1.25)
    return sky[good],values[good,2:4]


def measure_band(path,ref,mag,center,seed):
    image,wcs,header=read_image(path)
    scale=np.sqrt(abs(np.linalg.det(wcs.pixel_scale_matrix)))*3600
    peaks=candidate_sources(image,threshold=7)
    if len(peaks)<5:
        raise ValueError(f'Too few independent detections in {path.name}')
    tree=cKDTree(peaks)
    xy=pixel_positions(wcs,ref)
    distances,ids=tree.query(xy)
    f=np.array([aperture(image,p,1.5/scale)[0] for p in peaks[ids]])
    good=(distances*scale<.9)&np.isfinite(f)&(f>0)
    offsets=mag[good]+2.5*np.log10(f[good])
    if len(offsets)<6:
        raise ValueError(f'{path.name} has {len(offsets)} off-core calibration stars')
    retained=abs(offsets-np.median(offsets))<max(.12,3*robust_sigma(offsets))
    offsets=offsets[retained]
    held=np.arange(len(offsets))%3==0
    zeropoint=float(np.median(offsets[~held]))
    residual=offsets[held]-zeropoint
    axis=np.linspace(-2.8,2.8,181)
    xx,yy=np.meshgrid(axis,axis)
    rr=np.hypot(xx,yy)
    sky=center.spherical_offsets_by(xx.ravel()*u.arcmin,yy.ravel()*u.arcmin)
    probe=pixel_positions(wcs,sky)
    covered=safe_pixels(image,probe).reshape(xx.shape)
    rng=np.random.default_rng(seed)
    blank=probe[(covered & (rr>.8)&(rr<2.5)).ravel()]
    blank=blank[tree.query(blank)[0]*scale>4]
    if len(blank)>1800:
        blank=blank[rng.choice(len(blank),1800,replace=False)]
    flux=np.array([aperture(image,p,1.5/scale)[0] for p in blank])
    flux=flux[np.isfinite(flux)]
    if len(flux)<100:
        raise ValueError('Too few source-free full blank apertures')
    noise=robust_sigma(flux)
    flux=flux[abs(flux-np.median(flux))<3*noise]
    noise=robust_sigma(flux)
    core=rr<=.75;ring=(rr>=1.75)&(rr<=2.5)
    return dict(image=image,wcs=wcs,scale=scale,peaks=peaks,noise=noise,zeropoint=zeropoint,
                report=dict(path=path.name,sha256=sha(path),pixel_arcsec=scale,
                    asinh_decoded='BSOFTEN' in header,calibration_n=int(retained.sum()),
                    heldout_n=int(held.sum()),heldout_median_mag=float(np.median(residual)),
                    heldout_scatter_mag=float(robust_sigma(residual)),
                    full_aperture_core_coverage=float(covered[core].mean()),
                    full_aperture_background_coverage=float(covered[ring].mean()),
                    aperture5_mag=zeropoint-2.5*np.log10(5*noise),blank_apertures=len(flux)))


def run():
    data=Path(os.environ['LS_SAT_DATA'])
    folder=data/'resources/v14/v13r_south_ps1_0706-A_base-0.3-001'
    out=Path('results/v14/0706/images');out.mkdir(exist_ok=True,parents=True)
    center=SkyCoord(RA,DEC,unit='deg')
    ref,mag=reference(folder,center)
    ebv=float(reddening([RA],[DEC])[0])
    summaries={}; products={}; attempts=[]
    for survey in ('ps1','sdss'):
        for j,band in enumerate('gr'):
            paths=[folder/f'ps1_{band}.fits'] if survey=='ps1' else sorted(folder.glob(f'frame-{band}-*.fits.bz2'))
            choices=[]
            for path in paths:
                try:
                    result=measure_band(path,ref,mag[:,j],center,487182+j)
                    choices.append(result)
                    attempts.append(dict(survey=survey,band=band,status='measured',**result['report']))
                except (ValueError,StopIteration) as exc:
                    attempts.append(dict(survey=survey,band=band,path=path.name,status='unusable',reason=str(exc)))
            if not choices:
                continue
            best=max(choices,key=lambda r:(r['report']['full_aperture_core_coverage'],r['report']['full_aperture_background_coverage'],r['report']['aperture5_mag']))
            key=survey+'_'+band
            products[key]=best
            summaries[key]=dict(best['report'],aperture0_5_mag=best['report']['aperture5_mag']-[3.172,2.271][j]*ebv,
                                calibration_system='PS1 point-source aperture equivalent')
    irows=read_csv(folder/'ps1.csv')
    selected=[r for r in irows if r['raStack'] and r['decStack'] and
              0<=float(r['raStack'])<360 and abs(float(r['decStack']))<=90]
    isky=SkyCoord([float(r['raStack']) for r in selected],[float(r['decStack']) for r in selected],unit='deg')
    idx,sep,_=ref.match_to_catalog_sky(isky)
    imag=np.array([float(selected[i]['iPSFMag']) for i in idx])
    if np.any(sep.arcsec>.05):
        raise ValueError('Independent i calibration cannot rematch off-core PS1 references')
    independent_i=[]
    for path in sorted((folder/'decam_i').glob('*/image-*.fits')):
        try:
            result=measure_band(path,ref,imag,center,487184)
            independent_i.append(result)
            attempts.append(dict(survey='independent_decam',band='i',visit=path.parent.name,
                                 status='measured',**result['report']))
        except (ValueError,StopIteration) as exc:
            attempts.append(dict(survey='independent_decam',band='i',visit=path.parent.name,
                                 path=path.name,status='unusable',reason=str(exc)))
    if independent_i:
        best=max(independent_i,key=lambda r:(r['report']['full_aperture_core_coverage'],r['report']['aperture5_mag']))
        products['independent_i']=best
        summaries['independent_i']=dict(best['report'],aperture0_5_mag=best['report']['aperture5_mag']-1.682*ebv,
                                        calibration_system='PS1 i point-source aperture equivalent')
    write_csv(out/'image_product_measurements.csv',attempts)
    if not all(k in products for k in ('ps1_g','ps1_r')):
        write_json(out/'summary.json',dict(job=os.getenv('SLURM_JOB_ID'),products=summaries,status='incomplete'))
        return
    g,r=products['ps1_g'],products['ps1_r']
    sky=g['wcs'].pixel_to_world(*g['peaks'].T).icrs
    xy=pixel_positions(r['wcs'],sky)
    gf=np.array([aperture(g['image'],p,1.5/g['scale'])[0] for p in g['peaks']])
    rf=np.array([aperture(r['image'],p,1.5/r['scale'])[0] for p in xy])
    large=np.array([aperture(g['image'],p,2.2/g['scale'])[0] for p in g['peaks']])
    valid=np.isfinite(gf+rf)&(gf>5*g['noise'])&(rf>5*r['noise'])
    delta=2.5*np.log10(np.maximum(large,1e-20)/np.maximum(gf,1e-20))
    bright=valid&(gf>25*g['noise'])&(abs(sky.separation(center).arcmin)>1)
    median=float(np.median(delta[bright]));spread=max(.08,float(robust_sigma(delta[bright])))
    shape=abs(delta-median)<max(.2,3*spread)
    keep=valid&shape
    g0=g['zeropoint']-2.5*np.log10(gf[keep])-3.172*ebv
    r0=r['zeropoint']-2.5*np.log10(rf[keep])-2.271*ebv
    ge=1.0857362*g['noise']/gf[keep];re=1.0857362*r['noise']/rf[keep]
    positions=sky[keep];radius=positions.separation(center).arcmin
    model=load_isochrone(data/'resources'/PS1_MODEL,bands=('gP1','rP1'))
    # Distance from the segmented template is evaluated by the shared CMD model.
    from ls_satsearch.search import CMD
    offsets=positions.transform_to(center.skyoffset_frame())
    east,north=offsets.lon,offsets.lat
    sample=np.column_stack([east.arcmin,north.arcmin,g0,r0,ge,re])
    cfg=dict(g_max=26,r_max=25,background_tile_arcmin=120)
    import yaml
    cfg=yaml.safe_load(Path('configs/v7/search.yaml').read_text())|cfg
    population=CMD(sample,model,cfg).weights(19.25)[0]
    on=radius<=.75;off=(radius>=1.75)&(radius<=2.5)
    summary=dict(job=os.getenv('SLURM_JOB_ID'),ebv=ebv,products=summaries,
                 independently_detected_gr=int(valid.sum()),aperture_shape_selected=int(keep.sum()),
                 core_gr_sources=int(on.sum()),core_cmd_sources=int((on&population).sum()),
                 off_gr_sources=int(off.sum()),off_cmd_sources=int((off&population).sum()),
                 area_on_arcmin2=float(np.pi*.75**2),area_off_arcmin2=float(np.pi*(2.5**2-1.75**2)),
                 shape_calibration_n=int(bright.sum()),aperture_concentration_median=median,
                 conditional_cmd_scope='Image-detected source CMD at frozen mu=19.25. PS1-derived zero points. No production detection claim or independent confirmation from remeasuring the PS1 catalogue exposures.')
    if 'independent_i' in products:
        iv=products['independent_i']
        ixy=pixel_positions(iv['wcs'],positions)
        iflux=np.array([aperture(iv['image'],p,1.5/iv['scale'])[0] for p in ixy])
        available=safe_pixels(iv['image'],ixy)&np.isfinite(iflux)
        detected=available&(iflux>=5*iv['noise'])
        summary['independent_i_matches']=dict(
            core_gr_measured=int((on&available).sum()),
            core_gr_detected=int((on&detected).sum()),
            core_cmd_measured=int((on&population&available).sum()),
            core_cmd_detected=int((on&population&detected).sum()),
            scope='Independent i aperture flux at PS1 image detections; no gi population model or new discovery cut.')
    write_json(out/'summary.json',summary)
    # Per-source photometry stays in scratch.
    scratch=folder/'image_photometry.npy'
    np.save(scratch,sample,allow_pickle=False)
    fig,axes=plt.subplots(2,4,figsize=(16,7),layout='constrained')
    angular=np.linspace(-65,65,360)
    xx,yy=np.meshgrid(angular,angular)
    grid=center.spherical_offsets_by(xx*u.arcsec,yy*u.arcsec)
    for ax,key in zip(list(axes.flat)[:5],('ps1_g','ps1_r','sdss_g','sdss_r','independent_i')):
        v=products.get(key)
        if v is None:
            ax.text(.5,.5,'No calibrated coverage',transform=ax.transAxes,ha='center');continue
        xy=pixel_positions(v['wcs'],grid)
        image=map_coordinates(v['image'],[xy[:,:,1],xy[:,:,0]],order=1,mode='constant',cval=np.nan)
        z=(image-np.nanmedian(image))/robust_sigma(image[np.isfinite(image)])
        ax.imshow(z,origin='lower',extent=[-65,65,-65,65],cmap='gray',vmin=-2,vmax=7)
        ax.add_patch(plt.Circle((0,0),45,fill=False,color='#ddad54',lw=.8))
        ax.set_title(f'{key.upper()} · 5σ {summaries[key]["aperture0_5_mag"]:.2f}')
        ax.set(xlabel='East (arcsec)',ylabel='North (arcsec)')
    for ax,mask,label in zip(list(axes.flat)[5:7],(on,off),('Core aperture','Background annulus')):
        ax.scatter(g0[mask]-r0[mask],g0[mask],s=16,c='#36598c')
        track=model[2]+19.25
        ax.scatter(track[:,0]-track[:,1],track[:,0],s=.25,c='#b2522d')
        ax.set(xlabel='g₀−r₀',ylabel='g₀',xlim=(-.6,1.6),ylim=(25,16),title=label)
    note=axes.flat[7]
    note.axis('off')
    note.text(.03,.95,'0706 frozen population test\nICRS 165.61217°, 31.89212°\nμ = 19.25; core radius = 45″\n\nAll selected images cover the core.\nIndependent i background coverage: 67%\nPS1 g₀ aperture depth: 22.13\nIndependent i₀ aperture depth: 22.30\n\nDepth is insufficient for a deep\nturnoff-sequence confirmation.\nCandidate remains L0.',
              va='top',transform=note.transAxes,fontsize=10)
    with plt.rc_context({'font.family':'serif','pdf.fonttype':42,'svg.fonttype':'none'}):
        save(fig,out/'independent_images_and_cmd')


if __name__=='__main__':
    run()
