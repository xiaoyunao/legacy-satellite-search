"""Independent r-shape sensitivity of PS1 reference response; no truth-label claim."""
import hashlib
import json
import os
from pathlib import Path

from astropy.coordinates import SkyCoord
import astropy.units as u
import numpy as np
from scipy.spatial import cKDTree
from scipy.optimize import minimize_scalar
import yaml

from ls_satsearch.data import load_bricks,select
from ls_satsearch.hsc_depth_audit import aperture,candidate_sources,robust_sigma
from ls_satsearch.matched import joint_coverage,ps1_measurements,reddening
from ls_satsearch.run import field_cache,read_csv,settings,sha,write_csv,write_json
from scripts.v13_image_trials import match_to
from scripts.v14_cadc_reference_images import OUT
from scripts.v14_image0706 import pixel_positions,read_image,safe_pixels
from scripts.v14_ps1_response import stage_masks
from scripts.v12_selection_stats import interval


def fluxes(image,xy,scale):
    return np.array([[aperture(image,p,r/scale)[0] for r in (.6,1.5)] for p in xy]).reshape(-1,2)


def run():
    if not os.getenv('SLURM_JOB_ID'):raise ValueError('Use an allocated NERSC CPU node')
    directory=Path('configs/v13/matched/south').resolve();os.environ['LS_SAT_CONFIG_DIR']=str(directory)
    root,data,cfg=settings();plan=yaml.safe_load((directory/'matched.yaml').read_text())
    out=Path('results/v14/repeat_full/cadc_morphology_audit');out.mkdir(parents=True,exist_ok=True)
    rows=[];proof=[]
    for site in read_csv(Path('configs/v14_repeat/image_fields.csv'))[1:]:
        name=site['field'];path=data/'resources/v14/cadc_reference_20261119'/(name+'_alternate')/'image-cfht-r.fits'
        im,wcs,_=read_image(path);scale=np.sqrt(abs(np.linalg.det(wcs.pixel_scale_matrix)))*3600
        peaks=candidate_sources(im,threshold=7);tree=cKDTree(peaks)
        center=SkyCoord(float(site['ra_deg']),float(site['dec_deg']),unit='deg')
        axis=np.linspace(-5.2,5.2,151);xx,yy=np.meshgrid(axis,axis)
        grid=center.spherical_offsets_by(xx.ravel()*u.arcmin,yy.ravel()*u.arcmin)
        xy=pixel_positions(wcs,grid);clear=safe_pixels(im,xy)&(tree.query(xy)[0]*scale>4)
        blank=fluxes(im,xy[clear][::max(1,int(clear.sum()/1800))],scale)
        blank=blank[np.isfinite(blank).all(axis=1)]
        if len(blank)<200:raise ValueError('Insufficient blank covariance support')
        keep=np.all(abs(blank-np.median(blank,axis=0))<3*np.array([robust_sigma(blank[:,k]) for k in (0,1)]),axis=1)
        cov=np.cov(blank[keep].T);noise=np.sqrt(cov[1,1])
        spec=next(r for r in plan['fields'] if r['id']==site['background'])
        raw,_=ps1_measurements(spec,plan,data/'resources/ps1/tiles-v3'/site['background'])
        raw=raw[np.isfinite(raw).all(axis=1)&(raw[:,0]>=0)&(raw[:,0]<360)&(abs(raw[:,1])<=90)]
        sky=SkyCoord(raw[:,0],raw[:,1],unit='deg');px=pixel_positions(wcs,sky)
        distance,nearest=tree.query(px);isolation=tree.query(peaks[nearest],k=2)[0][:,1]*scale
        good=((distance*scale<.7)&(raw[:,3]>17)&(raw[:,3]<21.5)&(raw[:,5]>0)&(raw[:,5]<.05)
              &(raw[:,6]>0)&(raw[:,7]>0)&(raw[:,6]-raw[:,7]<.03)&(isolation>2.5))
        f=fluxes(im,peaks[nearest[good]],scale);f=f[np.isfinite(f).all(axis=1)&(f>0).all(axis=1)&(f[:,1]>30*noise)]
        if len(f)<12:raise ValueError('Insufficient bright independent-shape anchors')
        concentration=-2.5*np.log10(f[:,0]/f[:,1]);star=float(np.median(concentration))
        scatter=max(.025,float(robust_sigma(concentration)))
        objective=lambda s:abs(-2.5*np.log10((1-np.exp(-.6**2/(2*s*s)))/(1-np.exp(-1.5**2/(2*s*s))))-star)
        equivalent_fwhm=2.35482*minimize_scalar(objective,bounds=(.15,1.5),method='bounded').x
        expanded=dict(spec,width=plan['width_deg'],buffer_arcmin=plan['buffer_arcmin'])
        field,src,area,provenance=field_cache(root,data,expanded,cfg,load_bricks(root,'south'))
        area=joint_coverage(field,area,data/'resources/ps1/ps1d_mask_v2.1.fits')
        proxy=dict(cfg,g_max=24.5,r_max=24,min_snr=10);_,_,valid,mags,point=select(src,field,area,proxy)
        ordinary=(src['MASKBITS']&((1<<13)|(1<<17)))==0
        if 'FITBITS' in src.dtype.names:ordinary&=(src['FITBITS']&1)==0
        sky=SkyCoord(src['RA'],src['DEC'],unit='deg');nearby=sky.separation(center).arcmin<=5.2
        take=valid&ordinary&nearby;src=src[take];mags=mags[take];point=point[take]
        px=pixel_positions(wcs,SkyCoord(src['RA'],src['DEC'],unit='deg'))
        supported=safe_pixels(im,px);d,index=tree.query(px);isolated=tree.query(peaks[index],k=2)[0][:,1]*scale>2.5
        phot=fluxes(im,peaks[index],scale);positive=np.isfinite(phot).all(axis=1)&(phot>0).all(axis=1)
        shape=np.full(len(src),'unsupported',dtype='U40');shape[supported]='not_detected_or_low_snr'
        usable=supported&(d*scale<.7)&positive&(phot[:,1]>=15*noise)
        shape[usable&~isolated]='blend_or_close_neighbor'
        use=usable&isolated;indices=np.flatnonzero(use);fs,fl=phot[use].T
        measured=-2.5*np.log10(fs/fl)
        variance=(2.5/np.log(10))**2*(cov[0,0]/fs**2+cov[1,1]/fl**2-2*cov[0,1]/(fs*fl))
        tolerance=np.maximum(.15,3*np.sqrt(scatter**2+np.maximum(variance,0)))
        shape[indices]='point_shape_consistent'
        shape[indices[measured>star+tolerance]]='extended_shape_evidence'
        shape[indices[measured<star-tolerance]]='anomalously_sharp'
        link=match_to(np.column_stack([src['RA'],src['DEC']]),raw[:,:2],.7,field);found=link>=0
        matched=raw[np.maximum(link,0)]
        passed=stage_masks(matched,reddening(matched[:,0],matched[:,1]),dict(cfg,g_max=cfg['g_max']+.5,r_max=cfg['r_max']+.5))['selected']&found
        held=np.array([int(hashlib.sha256(f'{r["RELEASE"]}:{r["BRICKID"]}:{r["OBJID"]}:487219'.encode()).hexdigest()[:8],16)%2 for r in src],bool)
        for split,fold in (('train',~held),('heldout',held)):
            for label in ('PSF','nonPSF'):
                for lo,hi in zip((20,22,22.5,23,23.5),(22,22.5,23,23.5,24)):
                    for clo,chi in ((-10,.4),(.4,.8),(.8,10)):
                        for state in ('unsupported','not_detected_or_low_snr','blend_or_close_neighbor','point_shape_consistent','extended_shape_evidence','anomalously_sharp'):
                            mask=fold&(point if label=='PSF' else ~point)&(mags[:,0]>=lo)&(mags[:,0]<hi)&(mags[:,0]-mags[:,1]>=clo)&(mags[:,0]-mags[:,1]<chi)&(shape==state)
                            n=int(mask.sum());k=int((mask&passed).sum());bounds=interval(k,n) if n else (None,None)
                            rows.append(dict(site=name,split=split,LS_type=label,g_lo=lo,g_hi=hi,color_lo=clo,color_hi=chi,CFHT_shape_state=state,references=n,PS1_selected=k,p_selected=k/n if n else None,interval_lo=bounds[0],interval_hi=bounds[1]))
        proof.append(dict(site=name,CFHT_image_sha256=sha(path),LS_inputs=provenance,bright_shape_anchors=len(f),
            point_concentration_mag=star,point_concentration_scatter_mag=scatter,Gaussian_equivalent_FWHM_arcsec=float(equivalent_fwhm),
            blank_apertures=len(blank),isolated_shape_SNR_min=15,blank_aperture_covariance=cov.tolist(),
            LS_references=len(src),CFHT_shape_counts={s:int((shape==s).sum()) for s in np.unique(shape)}))
    write_csv(out/'conditional_reference_response.csv',rows)
    write_json(out/'manifest.json',dict(job=os.environ['SLURM_JOB_ID'],code_sha256=sha(Path(__file__)),fields=proof,
        scope='Independent CFHT-r concentration evidence conditional on ordinary LS SNR10 references within5.2arcmin. Bright PS1 morphology anchors set the empirical PSF locus; Gaussian equivalent FWHM is a concentration diagnostic, not a measured global PSF. Blank nested-aperture covariance enters shape uncertainty. Point-consistent sources can still be compact galaxies and extended evidence can include blends; labels are not stellar truth. No unseen-LS objects, colour-unknown sources or unsupported/noisy pixels are silently assigned a response. This tests reference sensitivity, not physical PS1 completeness, contamination truth, or LS−PS1 gain.'))
    print('INDEPENDENT_R_SHAPE_AUDIT',[(r['site'],r['Gaussian_equivalent_FWHM_arcsec'],r['CFHT_shape_counts']) for r in proof],flush=True)


if __name__=='__main__':run()
