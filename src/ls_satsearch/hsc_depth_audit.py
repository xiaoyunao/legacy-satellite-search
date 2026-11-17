"""Measure local depth of raw HSC visits with overscan and external point-source calibration."""

import argparse
import csv
import json
import os
from pathlib import Path

from astropy.coordinates import SkyCoord
from astropy.io import fits
import astropy.units as u
from astropy.wcs import WCS
import numpy as np
from scipy.ndimage import binary_erosion, gaussian_filter, map_coordinates, maximum_filter, median_filter
from scipy.spatial import cKDTree
import yaml

from .matched import reddening
from .run import sha, write_csv, write_json


def robust_sigma(a):
    a = np.asarray(a)
    return 1.4826 * np.median(np.abs(a-np.median(a)))


def read_pixels(path, frame, center):
    with fits.open(path, checksum=True) as fits_file:
        hdu, = fits_file
        header = hdu.header.copy()
        if hdu.verify_datasum()!=1 or hdu.verify_checksum()!=1 or header['FRAMEID']!=frame:
            raise ValueError(f'{frame} FITS validation failed')
        bands = [str(header[k]) for k in ('FILTER01','FILTER','FILTERID','W-FILTER') if k in header]
        if not any(v.upper()=='HSC-G' for v in bands) or header['EXPTIME']!=50:
            raise ValueError(f'{frame}: unexpected band or exposure')
        raw = np.asarray(hdu.data,dtype=np.float32)
    wcs = WCS(header).celestial
    x,y = wcs.world_to_pixel(center)
    radius = 1680
    x0,x1 = max(0,int(x-radius)),min(raw.shape[1],int(x+radius)+1)
    y0,y1 = max(0,int(y-radius)),min(raw.shape[0],int(y+radius)+1)
    active = np.full((y1-y0,x1-x0),np.nan,dtype=np.float32)
    for amp in range(1,5):
        ilo,ihi = (max(x0,header[f'T_EFMN{amp}1']-1),min(x1,header[f'T_EFMX{amp}1']))
        jlo,jhi = (max(y0,header[f'T_EFMN{amp}2']-1),min(y1,header[f'T_EFMX{amp}2']))
        if ihi<=ilo or jhi<=jlo:
            continue
        olo,ohi = header[f'T_OSMN{amp}1']-1,header[f'T_OSMX{amp}1']
        overscan = median_filter(np.median(raw[jlo:jhi,olo:ohi],axis=1),size=31)
        data = raw[jlo:jhi,ilo:ihi]
        corrected = (data-overscan[:,None])*header[f'T_GAIN{amp}']
        active[jlo-y0:jhi-y0,ilo-x0:ihi-x0] = np.where((data>0)&(data<55000),corrected,np.nan)
    return header,wcs,active,np.array([x0,y0])


def candidate_sources(image,threshold=17):
    valid = np.isfinite(image)
    bkg = np.median(image[valid])
    narrow = gaussian_filter(np.where(valid,image,bkg),1.6)
    sharp = narrow-gaussian_filter(narrow,8.)
    interior = binary_erosion(valid,iterations=10)
    limit = threshold*robust_sigma(sharp[interior])
    peaks = (sharp == maximum_filter(sharp,size=9)) & (sharp>limit) & interior
    return np.column_stack(np.where(peaks)[::-1]).astype(float)


def refine(nominal, peaks):
    tree = cKDTree(peaks)
    neighbors = tree.query_ball_point(nominal,r=360.)
    offsets = np.vstack([peaks[idx]-p for p,idx in zip(nominal,neighbors) if idx])
    hist, bx, by = np.histogram2d(*offsets.T,bins=np.arange(-365,366,12))
    m,n = np.unravel_index(np.argmax(hist),hist.shape)
    translation = np.array([(bx[m]+bx[m+1])/2,(by[n]+by[n+1])/2])
    design = np.column_stack((nominal,np.ones(len(nominal))))
    matrix = np.vstack((np.eye(2),translation))
    keep = None
    for limit in (30,18,9,4.5):
        d,idx = tree.query(design@matrix)
        keep = d < limit
        if keep.sum()<8:
            raise ValueError(f'Only {keep.sum()}/{len(nominal)} references match at {limit} pixels, peak offset bin {hist[m,n]}')
        matrix = np.linalg.lstsq(design[keep],peaks[idx[keep]],rcond=None)[0]
    residual = np.linalg.norm(design[keep]@matrix-peaks[idx[keep]],axis=1)
    return matrix,int(keep.sum()),float(np.sqrt(np.mean(residual**2))*.17)


def aperture(image, xy, radius=6):
    x,y=xy
    a,b = int(round(x)),int(round(y))
    extent = 15
    if a<extent or b<extent or a>=image.shape[1]-extent or b>=image.shape[0]-extent:
        return np.nan,np.nan
    part=image[b-extent:b+extent+1,a-extent:a+extent+1]
    axis = np.arange(-extent,extent+1)
    rr = np.hypot(axis[None,:]+a-x,axis[:,None]+b-y)
    core = rr<=radius
    ring = (rr>=10)&(rr<15)
    if not np.isfinite(part[core]).all() or np.isfinite(part[ring]).sum()<100:
        return np.nan,np.nan
    sky = np.nanmedian(part[ring])
    return float((part[core]-sky).sum()),float((part[rr<=3]-sky).sum())


def references(path, center):
    with path.open(newline='') as f:
        vals=np.array([[float(r[k] or 'nan') for k in ('raStack','decStack','gPSFMag','rPSFMag',
                    'gPSFMagErr','rPSFMagErr','iPSFMag','iKronMag')] for r in csv.DictReader(f)])
    ra,dec,g,r,ge,re,i,k=vals.T
    good=np.isfinite(vals).all(axis=1)&(g>16.8)&(g<21.65)&(r>0)&(ge>0)&(ge<.07)&(re>0)&(re<.07)
    good&=(i>0)&(k>0)&(i-k<.05)&(g-r>.1)&(g-r<.9)
    positions=SkyCoord(ra[good],dec[good],unit='deg')
    isolated=positions.match_to_catalog_sky(positions,nthneighbor=2)[1].arcsec>4
    isolated &= (positions.separation(center).arcmin>2.2)&(positions.separation(center).arcmin<6.0)
    return positions[isolated],g[good][isolated]


def image_stamp(pixels, xy, n, scale, output_pixel_area, input_pixel_area):
    x,y = xy.T
    center = float(np.nanmedian(pixels))
    val = map_coordinates(pixels,[y,x],order=1,mode='constant',cval=np.nan,prefilter=False)
    return ((val-center)*scale*output_pixel_area/input_pixel_area).reshape(n,n)


def run(write_stack=False):
    plan = yaml.safe_load(Path('configs/v7/candidate.yaml').read_text())
    old = yaml.safe_load(Path('configs/v6/followup.yaml').read_text())
    center=SkyCoord(old['ra_deg'],old['dec_deg'],unit='deg')
    data=Path(os.environ['LS_SAT_DATA'])
    scratch=data/'external/smoka'
    transfer=json.loads((scratch/'transfer_manifest.json').read_text())
    ref=data/'resources/v6'/old['candidate']/'ps1.csv'
    positions,g = references(ref,center)
    rng=np.random.default_rng(481711)
    rr=np.sqrt(rng.uniform(.3**2,2.1**2,2700))
    theta=rng.uniform(0,2*np.pi,len(rr))
    blanks=center.spherical_offsets_by(rr*np.cos(theta)*u.arcmin,rr*np.sin(theta)*u.arcmin)
    xg=np.linspace(-2.2,2.2,181)
    xx,yy=np.meshgrid(xg,xg)
    grid=center.spherical_offsets_by(xx*u.arcmin,yy*u.arcmin)
    ebv=float(reddening([center.ra.deg],[center.dec.deg])[0])
    frames,fluxes,areas=[],[],[]
    stamps = []
    spacing_arcsec = .24
    if write_stack:
        mesh_axis = np.arange(-582,583)*spacing_arcsec
        mesh_x,mesh_y = np.meshgrid(mesh_axis,mesh_axis)
        mesh_coords = center.spherical_offsets_by(mesh_x.ravel()*u.arcsec,mesh_y.ravel()*u.arcsec)
    for frame in plan['hsc_frame_ids']:
        tr=transfer[frame]
        path=scratch/tr['file']
        if sha(path)!=tr['sha256']:
            raise ValueError(f'{frame} differs from the transfer manifest')
        hdr,wcs,pixels,origin=read_pixels(path,frame,center)
        nominal=np.column_stack(wcs.world_to_pixel(positions))-origin
        inside=np.all((nominal>100)&(nominal<np.array(pixels.shape[::-1])-100),axis=1)
        peaks=candidate_sources(pixels)
        base=dict(frame=frame,detector=int(hdr['DET-ID']),filter='HSC-g',exposure_s=hdr['EXPTIME'],
                  date_obs=hdr['DATE-OBS'],airmass=hdr['AIRMASS'],sha256=tr['sha256'],
                  archive_md5_verified=tr['archive_md5_verified'],fits_checksum_verified=True)
        try:
            mat,astrom_n,astrom_rms=refine(nominal[inside],peaks)
        except ValueError as error:
            frames.append(dict(base,status='astrometry_failed',reason=str(error)))
            continue

        def project(sky):
            xy=np.column_stack(wcs.world_to_pixel(sky))-origin
            return np.column_stack((xy,np.ones(len(xy))))@mat

        cal_flux, core_flux = np.asarray([aperture(pixels,x) for x in project(positions[inside])]).T
        ok=(cal_flux>0)&(core_flux/cal_flux>.4)&(core_flux/cal_flux<1.05)
        zp = g[inside][ok]+2.5*np.log10(cal_flux[ok])
        accepted=np.abs(zp-np.median(zp))<max(.075,3*robust_sigma(zp))
        base.update(astrom_n=astrom_n,astrom_rms_arcsec=astrom_rms,
                    acceptable_anchor_profiles=int(ok.sum()),matched_ps1_anchors=int(accepted.sum()))
        if accepted.sum()<8 or robust_sigma(zp[accepted])>.18:
            frames.append(dict(base,status='photometry_failed',reason='Too few or inconsistent local zero points',
                               preclip_zero_point_scatter_mag=robust_sigma(zp) if len(zp) else None))
            continue
        zp0=float(np.median(zp[accepted]))
        scale=10**(.4*(25-zp0))
        flux = np.array([aperture(pixels,v)[0] for v in project(blanks)])*scale
        sigma = robust_sigma(flux[np.isfinite(flux)])
        gx,gy=np.rint(project(grid.reshape(-1))).astype(int).T
        safe=(gx>15)&(gy>15)&(gx<pixels.shape[1]-15)&(gy<pixels.shape[0]-15)
        grid_valid=np.zeros(len(gx),dtype=bool)
        grid_valid[safe]=np.isfinite(pixels[gy[safe],gx[safe]])
        record=dict(base,status='provisional_photometry',aperture_zero_point=zp0,
                    zero_point_robust_scatter_mag=robust_sigma(zp[accepted]),
                    central_pixel_usable=bool(grid_valid[len(gx)//2]),usable_blank_apertures=int(np.isfinite(flux).sum()),
                    provisional_aperture_g5=float(25-2.5*np.log10(5*sigma)),
                    median_inner_aperture_fraction=float(np.median((core_flux/cal_flux)[ok][accepted])))
        frames.append(record)
        fluxes.append((flux,sigma))
        areas.append(grid_valid.reshape(xx.shape))
        if write_stack:
            native_area=abs(np.linalg.det(wcs.pixel_scale_matrix)) * 3600**2
            native_area/=abs(np.linalg.det(mat[:2,:]))
            stamps.append(image_stamp(pixels,project(mesh_coords),len(mesh_axis),scale,
                                      spacing_arcsec**2,native_area))
    out=Path('results/verification')
    out.mkdir(exist_ok=True,parents=True)
    write_csv(out/'hsc_raw_frame_qa.csv',frames)
    if not fluxes:
        write_json(out/'hsc_provisional_depth.json',dict(job=os.environ.get('SLURM_JOB_ID'),
                   status='no_calibrated_visit',needed=['master bias','flat field','astrometric calibration']))
        return
    f=np.array([a[0] for a in fluxes])
    w=np.array([a[1]**-2 for a in fluxes])[:,None]
    usable=np.isfinite(f)
    count=usable.sum(axis=0)
    stack=np.nansum(f*w,axis=0)/np.maximum((usable*w).sum(axis=0),1.e-20)
    area=np.asarray(areas).sum(axis=0)
    dist=np.hypot(xx,yy)
    metrics={}
    for minimum in range(1,len(fluxes)+1):
        val=(count>=minimum)
        if val.sum()<50:
            continue
        depth=25-2.5*np.log10(5*robust_sigma(stack[val]))
        metrics[f'at_least_{minimum}_visits']=dict(blank_positions=int(val.sum()),
            g5_ps1_calibrated_aperture=float(depth),g5_dereddened=float(depth-3.172*ebv),
            core_fraction=float((area[dist<=.525]>=minimum).mean()),
            annulus_fraction=float((area[(dist>1.225)&(dist<=2.1)]>=minimum).mean()))
    if write_stack:
        cache = data/'resources/v7'/old['candidate']
        cache.mkdir(exist_ok=True,parents=True)
        image = np.asarray(stamps,dtype=np.float32)
        validity = np.isfinite(image)
        weight=np.array([t[1]**-2 for t in fluxes])[:,None,None]
        weight_map=(validity*weight).sum(axis=0)
        stacked=np.full(weight_map.shape,np.nan,dtype=np.float32)
        np.divide(np.nansum(image*weight,axis=0),weight_map,out=stacked,where=weight_map>0)
        np.savez_compressed(cache/'hsc_provisional_stack.npz',image=stacked,N=validity.sum(axis=0),
                            pixel_scale=spacing_arcsec)
    write_json(out/'hsc_provisional_depth.json',dict(job=os.environ.get('SLURM_JOB_ID'),eligible_visits=len(fluxes),config_sha256=sha(
       Path('configs/v7/candidate.yaml')),reference_sha256=sha(ref),aperture_arcsec=1.02,ebv=ebv,
       calibration='Overscan, nominal amplifier gains, local PS1-band astrometry and aperture zero points',
       missing_calibration=['master bias','flat field','deep source classification'],
       depth_definition='5 sigma from MAD of random off-centre aperture fluxes; includes unresolved confusion',**metrics))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-stack',action='store_true')
    run(parser.parse_args().write_stack)
