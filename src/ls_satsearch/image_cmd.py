"""Exploratory independent g-detected HSC+CFHT aperture CMD on a common area."""

import csv
import json
import os
from pathlib import Path

from astropy.coordinates import SkyCoord
from astropy.io import fits
import astropy.units as u
from astropy.wcs import WCS
import matplotlib.pyplot as plt
import numpy as np
import yaml

from .candidate_archives import frozen_positions
from .cfht_cutouts import EXPOSURES
from .compare_candidate_gaia import fixed_case, known_foreground, separation_mask
from .data import Field, sample_pixels
from .hsc_depth_audit import aperture, candidate_sources, image_stamp, robust_sigma
from .matched import PS1_MODEL, reddening
from .run import sha, write_csv, write_json
from .search import load_isochrone
from .verify_candidate import setup


def ps1_refs(path,center,inner,outer,band='r',r_max=21.5,annular=False):
    with path.open(newline='') as f:
        rows=np.array([[float(r[k] or 'nan') for k in ('raStack','decStack','gPSFMag','rPSFMag',
                       'rPSFMagErr','iPSFMag','iKronMag')] for r in csv.DictReader(f)])
    ra,dec,g,r,re,i,k=rows.T
    good=np.isfinite(rows).all(axis=1)&(r>16.5)&(r<r_max)&(re>0)&(re<.06)&(i-k<.05)&(i>0)&(k>0)
    color_range = (.0,1.25) if annular else (.15,.85)
    good&=(color_range[0]<g-r)&(g-r<color_range[1])&(abs(dec)<=90)&(ra>=0)&(ra<360)
    sky=SkyCoord(ra[good],dec[good],unit='deg')
    selected=(sky.separation(center).arcmin>inner)&(sky.separation(center).arcmin<outer)
    return sky[selected],(r if band=='r' else g)[good][selected]


def red_stack(indir,ref,mag,grid,side,pixel_scale,aperture_arcsec):
    stamps,records=[],[]
    for visit in EXPOSURES:
        path=indir/f'{visit}.fits'
        if not path.exists():
            continue
        record={'visit':visit,'sha256':sha(path),'calibrated_extensions':0}
        stamp=np.full((side,side),np.nan)
        with fits.open(path,memmap=False) as exposures:
            for hdu in exposures:
                if hdu.data is None or hdu.data.ndim!=2:
                    continue
                wcs=WCS(hdu.header).celestial
                if not wcs.has_celestial:
                    continue
                pix=np.asarray(hdu.data,dtype=np.float32)
                raw_xy=np.column_stack(wcs.world_to_pixel(ref))
                native_area=abs(np.linalg.det(wcs.pixel_scale_matrix))*3600**2
                detector_radius=aperture_arcsec/np.sqrt(native_area)
                F=np.array([aperture(pix,xy,radius=detector_radius)[0] for xy in raw_xy])
                ok=np.isfinite(F)&(F>0)
                z=mag[ok]+2.5*np.log10(F[ok])
                if len(z)<7:
                    continue
                keep=abs(z-np.median(z))<max(.07,3*robust_sigma(z))
                if keep.sum()<7 or robust_sigma(z[keep])>.16:
                    continue
                scale=10**(.4*(25-np.median(z[keep])))
                projected=image_stamp(pix,np.column_stack(wcs.world_to_pixel(grid)),side,scale,
                                      pixel_scale**2,native_area)
                holes=~np.isfinite(stamp)
                stamp[holes]=projected[holes]
                record.update(calibrated_extensions=record['calibrated_extensions']+1,
                              anchors=int(keep.sum()),scatter_mag=float(robust_sigma(z[keep])))
        if np.isfinite(stamp).any():
            stamps.append(stamp)
        records.append(record)
    if len(stamps)<2:
        raise ValueError('Fewer than two CFHT visits with local zero points')
    a=np.asarray(stamps)
    n=np.isfinite(a).sum(axis=0)
    return np.nansum(a,axis=0)/np.where(n>0,n,np.nan),n,records


def stack_zero_point(image, band, plan, path, center, pixel_scale, blue_positions):
    """Validate and calibrate the final aperture on reference stars outside the core."""
    sky,mag=ps1_refs(path,center,plan['stack_reference_inner_arcmin'],
                     plan['stack_reference_outer_arcmin'],band=band,r_max=plan['stack_reference_r_max'],annular=True)
    east,north=center.spherical_offsets_to(sky)
    xy=np.column_stack((east.arcsec,north.arcsec))/pixel_scale+(len(image)-1)/2
    from scipy.spatial import cKDTree
    sep,nearest=cKDTree(blue_positions).query(xy)
    flux=np.array([aperture(image,p,plan['aperture_arcsec']/pixel_scale)[0]
                   for p in blue_positions[nearest]])
    valid=np.isfinite(flux)&(flux>0)&(sep*pixel_scale<.8)
    offsets=mag[valid]-(25-2.5*np.log10(flux[valid]))
    if len(offsets)<9:
        raise ValueError(f'{band}: only {len(offsets)} usable off-centre stack reference stars')
    order=np.argsort(sky.ra.deg[valid])
    held=np.zeros(len(offsets),dtype=bool)
    held[order[::3]]=True
    training=offsets[~held]
    median=float(np.median(training))
    lower_scatter=robust_sigma(training)
    keep=abs(training-median)<max(.10,3*lower_scatter)
    if keep.sum()<6:
        raise ValueError(f'{band}: only {keep.sum()} uncontaminated training reference stars')
    correction=float(np.median(training[keep]))
    val=offsets[held]-correction
    result=dict(training_n=int(keep.sum()),held_out_n=len(val),correction_mag=correction,
                held_out_median_mag=float(np.median(val)),held_out_robust_sigma_mag=robust_sigma(val))
    if abs(result['held_out_median_mag'])>.14 or result['held_out_robust_sigma_mag']>.2:
        raise ValueError(f'{band}: poor held-out stack zero point {result}')
    return 10**(-.4*correction),result


def comparison_to_ls(sample, sample_sky, shortlist, sources, center):
    """Report aggregate cross-catalog colour shifts on the frozen stars and local controls."""
    declination = abs(sources['DEC']-center.dec.deg) < .045
    raw=sources[declination]
    longitude=abs((raw['RA']-center.ra.deg+180)%360-180)<.055
    raw=raw[longitude]
    psf=np.char.strip(raw['TYPE'].astype('U'))=='PSF'
    raw=raw[psf]
    coords=SkyCoord(raw['RA'],raw['DEC'],unit='deg')
    idx,match,_=sample_sky.match_to_catalog_sky(coords)
    small=raw[idx]
    bands=np.column_stack([small[f'FLUX_{b}']/small[f'MW_TRANSMISSION_{b}'] for b in 'GR'])
    valid=(bands>0).all(axis=1)&(match.arcsec<=.8)&np.isfinite(bands).all(axis=1)
    diff=np.full(bands.shape,np.nan)
    diff[valid]=sample[valid,2:4]-(22.5-2.5*np.log10(bands[valid]))
    members=sample_sky.match_to_catalog_sky(shortlist)[1].arcsec<=.8
    control=(sample_sky.separation(center).arcmin>1.225)&(~members)
    rows={}
    for tag,region in (('LS_high_weight',members),('annulus_controls',control)):
        values=diff[region&valid]
        grand=np.column_stack((values,values[:,0]-values[:,1]))
        rows[tag]=dict(n=len(values))
        for k,arr in zip(('g','r','g_minus_r'),grand.T):
            if len(arr):
                rows[tag][k]=dict(median=float(np.median(arr)),robust_sigma=float(robust_sigma(arr)))
    return rows


def run():
    plan=yaml.safe_load(Path('configs/v7/image_cmd.yaml').read_text())
    frozen=yaml.safe_load(Path('configs/v6/followup.yaml').read_text())
    ext=Path(os.environ['LS_SAT_DATA'])/'resources'
    before=ext/'v6'/frozen['candidate']
    now=ext/'v7'/frozen['candidate']
    center=SkyCoord(frozen['ra_deg'],frozen['dec_deg'],unit='deg')
    with np.load(now/'hsc_provisional_stack.npz',allow_pickle=False) as g:
        blue,count,scale=g['image'],g['N'],float(g['pixel_scale'])
    axis=(np.arange(len(blue))-len(blue)//2)*scale
    dx,dy=np.meshgrid(axis,axis)
    grid=center.spherical_offsets_by(dx.ravel()*u.arcsec,dy.ravel()*u.arcsec)
    ref,mag=ps1_refs(before/'ps1.csv',center,plan['reference_inner_arcmin'],plan['reference_outer_arcmin'])
    red,r_count,calibration=red_stack(before/'cfht_wide',ref,mag,grid,len(axis),scale,plan['aperture_arcsec'])
    good=(count>=2)&(r_count>=2)
    blue=np.where(good,blue,np.nan)
    red=np.where(good,red,np.nan)
    pos=candidate_sources(blue,threshold=4.7)
    final_calibration={}
    for band,img in (('g',blue),('r',red)):
        factor,metrics=stack_zero_point(img,band,plan,before/'ps1.csv',center,scale,pos)
        img*=factor
        final_calibration[band]=metrics
    field=Field(center.ra.deg,center.dec.deg,.074,.05,buffer=0)
    h=(np.arange(field.n)+.5)*field.step-field.limit
    yy,xx=np.meshgrid(h,h,indexing='ij')
    iy,ix=np.rint(yy*60/scale+len(axis)//2).astype(int),np.rint(xx*60/scale+len(axis)//2).astype(int)
    inside=(iy>=0)&(ix>=0)&(iy<len(axis))&(ix<len(axis))
    mask=np.zeros(xx.shape,dtype=bool)
    mask[inside]=good[iy[inside],ix[inside]]
    rh=plan['half_light_arcmin']
    geom=np.hypot(xx,yy)
    core=float(mask[geom<=1.5*rh].mean())
    off=float(mask[(geom>3.5*rh)&(geom<=6*rh)].mean())
    if core<plan['minimum_projected_core_fraction'] or off<plan['minimum_projected_annulus_fraction']:
        raise ValueError(f'Joint useful pixels core={core:.3f}, annulus={off:.3f}')

    rng=np.random.default_rng(plan['seed'])
    center_px=(len(axis)-1)/2.
    rad=np.sqrt(rng.uniform((.6*60/scale)**2,(2.1*60/scale)**2,1700))
    phi=rng.uniform(0,2*np.pi,len(rad))
    positions=center_px+np.column_stack((rad*np.cos(phi),rad*np.sin(phi)))
    radius=plan['aperture_arcsec']/scale
    noise=[]
    for img in (blue,red):
        blank=np.array([aperture(img,p,radius)[0] for p in positions])
        noise.append(robust_sigma(blank[np.isfinite(blank)]))
    g,g_inner=np.array([aperture(blue,p,radius) for p in pos]).T
    r=np.array([aperture(red,p,radius)[0] for p in pos])
    snr=np.column_stack((g,r))/noise
    bright=np.all(snr>=plan['min_snr'],axis=1)
    frac=np.divide(g_inner,g,out=np.zeros(len(g)),where=g>0)
    compact=bright&(frac>=plan['morph_inner_fraction_range'][0])&(frac<=plan['morph_inner_fraction_range'][1])
    xy=(pos[compact]-center_px)*scale/60.
    sky=center.spherical_offsets_by(xy[:,0]*u.arcmin,xy[:,1]*u.arcmin)
    ebv=reddening(sky.ra.deg,sky.dec.deg)
    dered=25-2.5*np.log10(np.column_stack((g,r))[compact])-ebv[:,None]*np.array([3.172,2.271])
    err=np.hypot(2.5/np.log(10)/snr[compact],plan['cross_filter_uncertainty_mag'])
    cfg=yaml.safe_load(Path('configs/v6/search.yaml').read_text())
    cfg.update(g_max=plan['g_limit'],r_max=plan['r_limit'])
    keep=(dered<=np.array([cfg['g_max'],cfg['r_max']])).all(axis=1)
    keep&=(np.hypot(*xy.T)<=2.1)&mask[sample_pixels(field,mask,*xy.T)]
    sample=np.column_stack((xy,dered,err))[keep]
    with (before/'gaia-wide.csv').open(newline='') as f:
        _, foreground=known_foreground(list(csv.DictReader(f)),yaml.safe_load(Path('configs/v7/candidate.yaml').read_text()))
    veto=separation_mask(sample,field,foreground,.8)
    model=load_isochrone(ext/PS1_MODEL,bands=('gP1','rP1'))
    rows=[]
    for tag,stars in (('original',sample),('uniform_foreground_veto',sample[~veto])):
        z=np.hypot(*stars[:,:2].T)
        faint=(stars[:,2]>=plan['report_faint_g0_interval'][0])&(stars[:,2]<=plan['report_faint_g0_interval'][1])
        for dm in plan['test_moduli']:
            rows.append(dict(selection=tag,test_dm=dm,selected=len(stars),
                             faint_on=int((faint&(z<=1.5*rh)).sum()),
                             faint_off=int((faint&(z>3.5*rh)&(z<=6*rh)).sum()),
                             **fixed_case(stars,model,field,mask,cfg,dm,rh)))
    _,_,root,_,ls_sources,_=setup()
    shortlist=frozen_positions(frozen,root,ls_sources)
    stage={}
    detection_offset=(pos-center_px)*scale
    detection_sky=center.spherical_offsets_by(detection_offset[:,0]*u.arcsec,
                                               detection_offset[:,1]*u.arcsec)
    for label,stage_sky in (('g_detection',detection_sky),('two_band_snr5',detection_sky[bright]),
                            ('compact_aperture',sky),('test_sample',sky[keep]),('after_gaia',sky[keep][~veto])):
        stage[label]=int((shortlist.match_to_catalog_sky(stage_sky)[1].arcsec<=.8).sum()) if len(stage_sky) else 0
    photometric_offsets=comparison_to_ls(sample,sky[keep],shortlist,ls_sources,center)
    out=Path('results/verification')
    write_csv(out/'provisional_image_fixed_cmd.csv',rows)
    write_json(out/'provisional_image_cmd.json',dict(job=os.environ.get('SLURM_JOB_ID'),
       config_sha256=sha(Path('configs/v7/image_cmd.yaml')),core_fraction=core,annulus_fraction=off,
       g_detected=len(pos),two_band_snr5=int(bright.sum()),compact_shape=int(compact.sum()),
       gaia_removed=int(veto.sum()),ls_shortlist_number=len(shortlist),
       ls_shortlist_by_stage=stage,image_minus_ls_magnitude_differences=photometric_offsets,g5_ps1_equivalent=float(25-2.5*np.log10(5*noise[0])),
       r5_ps1_equivalent=float(25-2.5*np.log10(5*noise[1])),cfht_calibration=calibration,
       stack_photometry_validation=final_calibration,
       limitations=['provisional HSC calibration','PS1 reference system','point-source completeness unmeasured']))
    z=np.hypot(*sample[:,:2].T)
    fig,axes=plt.subplots(1,2,sharey=True,figsize=(7,4),layout='constrained')
    for panel,sel,title in zip(axes,[(z<=1.5*rh),(z>3.5*rh)&(z<=6*rh)],['Fixed core','Background ring']):
        panel.scatter(sample[sel,2]-sample[sel,3],sample[sel,2],s=10)
        for dm,col in zip(plan['test_moduli'],('tab:orange','tab:blue')):
            g,r=model[0].T
            panel.scatter(g-r,g+dm,s=1,color=col,label=f'DM {dm:.2f}')
        panel.set(title=title,xlabel='Provisional PS1-equivalent (g−r)₀',xlim=(-.45,1.55),ylim=(24.5,17))
    axes[0].set_ylabel('Provisional g₀')
    axes[0].legend(loc='upper right')
    fig.savefig(out/'provisional_image_cmd.png',dpi=145)
    plt.close(fig)


if __name__=='__main__':
    run()
