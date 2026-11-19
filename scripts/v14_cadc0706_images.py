"""Download verified public CFHT u/r stacks on NERSC and measure actual core support."""
import hashlib
import os
from pathlib import Path
from urllib.request import urlopen

import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.wcs import WCS
import fitsio
import matplotlib.pyplot as plt
import numpy as np

from ls_satsearch.hsc_depth_audit import aperture,robust_sigma
from ls_satsearch.run import read_csv,sha,write_json
if __package__:
    from .v14_image0706 import RA,DEC,measure_band,pixel_positions,reference,safe_pixels,read_image
else:
    from v14_image0706 import RA,DEC,measure_band,pixel_positions,reference,safe_pixels,read_image


def digest(path,kind='md5'):
    h=hashlib.new(kind)
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def download(row,folder):
    relative=row['uri'].removeprefix('cadc:CFHTSG/')
    if relative==row['uri'] or '/' in relative:raise ValueError('Unexpected artifact namespace')
    path=folder/relative;expected=int(row['contentLength']);checksum=row['contentChecksum'].removeprefix('md5:')
    url='https://ws.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/data/pub/CFHTSG/'+relative
    if not path.is_file() or path.stat().st_size!=expected or digest(path)!=checksum:
        temporary=path.with_suffix(path.suffix+'.part')
        size=0;md5=hashlib.md5()
        with urlopen(url,timeout=55) as source,temporary.open('wb') as dest:
            while block:=source.read(1024*1024):
                size+=len(block)
                if size>expected:raise ValueError('Image response larger than registered artifact')
                dest.write(block);md5.update(block)
        if size!=expected or md5.hexdigest()!=checksum:raise ValueError('Public image size/MD5 mismatch')
        temporary.replace(path)
    return path,dict(uri=row['uri'],url=url,bytes=expected,parent_md5=checksum,sha256=sha(path),
                     product_type=row['productType'],filter=row['energy_bandpassName'],verified=True)


def crop(science,weight,folder,band,ra=RA,dec=DEC):
    header=fitsio.read_header(science)
    wcs=WCS(header).celestial
    x,y=wcs.all_world2pix(ra,dec,0);scale=np.sqrt(abs(np.linalg.det(wcs.pixel_scale_matrix)))*3600
    radius=int(np.ceil(5.5*60/scale))
    x0=max(0,int(x)-radius);y0=max(0,int(y)-radius)
    x1=min(int(header['NAXIS1']),int(x)+radius+1);y1=min(int(header['NAXIS2']),int(y)+radius+1)
    if x0>=x1 or y0>=y1:raise ValueError('Metadata overlap does not cover the requested core')
    cut_header=fits.Header(dict(header));cut_header['CRPIX1']-=x0;cut_header['CRPIX2']-=y0
    with fitsio.FITS(science) as f:im=f[0][y0:y1,x0:x1]
    with fitsio.FITS(weight) as f:
        indices=[i for i in range(len(f)) if len(f[i].get_info().get('dims',[]))==2]
        if len(indices)!=1:raise ValueError('Weight image HDU is ambiguous')
        wt=f[indices[0]][y0:y1,x0:x1]
    if im.shape!=wt.shape:raise ValueError('Science/weight crop shapes differ')
    image=folder/f'image-cfht-{band}.fits';support=folder/f'weight-cfht-{band}.fits'
    fits.writeto(image,im,cut_header,overwrite=True);fits.writeto(support,wt,cut_header,overwrite=True)
    return image,header


def run():
    if not os.getenv('SLURM_JOB_ID'):raise ValueError('Image download/processing requires an allocated NERSC CPU job')
    data=Path(os.environ['LS_SAT_DATA'])
    parent=data/'resources/v14/v13r_south_ps1_0706-A_base-0.3-001'
    folder=parent/'cadc_20261119';folder.mkdir(parents=True,exist_ok=True)
    out=Path('results/v14/0706/cadc_images_20261119');out.mkdir(parents=True,exist_ok=True)
    metadata=Path('results/v14/0706/cadc_followup/20261119-stack-artifacts.csv')
    rows=[r for r in read_csv(metadata) if r['productType'] in ('science','weight')]
    if len(rows)!=4:raise ValueError('Expected exactly two public stacks and their weights')
    files={};proof=[]
    for row in rows:
        path,entry=download(row,folder);files[row['energy_bandpassName'][0],row['productType']]=path;proof.append(entry)
        write_json(out/'download_manifest.json',dict(job=os.getenv('SLURM_JOB_ID'),metadata_sha256=sha(metadata),
            files=proof,all_four_verified=len(proof)==4,scope='Public CFHT MegaPipe u/r products only; no dedicated g image and no classification promotion. Full raw images stay on NERSC.'))
        print('VERIFIED_PUBLIC_IMAGE',row['energy_bandpassName'],row['productType'],entry['bytes'],flush=True)
    center=SkyCoord(RA,DEC,unit='deg');ref,mags=reference(parent,center,outer_arcmin=5)
    path_r,header_r=crop(files['r','science'],files['r','weight'],folder,'r')
    r=measure_band(path_r,ref,mags[:,1],center,487251)
    path_u,header_u=crop(files['u','science'],files['u','weight'],folder,'u')
    u_image,u_wcs,_=read_image(path_u)
    u_scale=np.sqrt(abs(np.linalg.det(u_wcs.pixel_scale_matrix)))*3600
    axis=np.linspace(-2.8,2.8,181);xx,yy=np.meshgrid(axis,axis);rr=np.hypot(xx,yy)
    sky=center.spherical_offsets_by(xx.ravel()*u.arcmin,yy.ravel()*u.arcmin)
    coords=pixel_positions(u_wcs,sky);covered=safe_pixels(u_image,coords)
    ring=(rr.ravel()>=1.75)&(rr.ravel()<=2.5);core=rr.ravel()<=.75
    # Off-source support is defined by valid weights, never by detected-star density.
    from scipy.spatial import cKDTree
    ref_peaks=r['wcs'].pixel_to_world(*r['peaks'].T).icrs
    u_sources=pixel_positions(u_wcs,ref_peaks)
    clear=cKDTree(u_sources).query(coords)[0]*u_scale>4
    positions=coords[covered&ring&clear]
    if len(positions)>1800:positions=positions[np.random.default_rng(487252).choice(len(positions),1800,replace=False)]
    flux=np.array([aperture(u_image,p,1.5/u_scale)[0] for p in positions]);flux=flux[np.isfinite(flux)]
    noise=None
    if len(flux)>=100:
        noise=float(robust_sigma(flux));noise=float(robust_sigma(flux[abs(flux-np.median(flux))<3*noise]))
    zp={k:header_u[k] for k in ('MAGZERO','MAGZP','PHOTZP','PHOT_C') if k in header_u}
    report=dict(job=os.getenv('SLURM_JOB_ID'),ra_deg=RA,dec_deg=DEC,
        r_PS1_aperture_equivalent=r['report'],u_native=dict(zeropoint_header_candidates=zp,blank_aperture_sigma=noise,
        measurement_state='noise_measured' if noise is not None else 'insufficient_supported_blank_apertures',
        full_aperture_core_coverage=float(covered[core].mean()),full_aperture_background_coverage=float(covered[ring].mean()),
        blank_apertures=len(flux)),
        independent_instrument='CFHT MegaPrime; LS discovery uses DECam and BASS comparison uses 90Prime',
        scope='Actual independent u/r image support and aperture noise. No standard g product recovered in the ROI. Native u zeropoint is recorded without inventing a PS1-g transformation, extinction correction or independent CMD detection. Candidate remains L0.')
    write_json(out/'summary.json',report)
    fig,axes=plt.subplots(1,2,figsize=(8,4),layout='constrained')
    from scipy.ndimage import map_coordinates
    axis=np.linspace(-65,65,360);xx,yy=np.meshgrid(axis,axis);grid=center.spherical_offsets_by(xx*u.arcsec,yy*u.arcsec)
    for ax,band,image,wcs in ((axes[0],'CFHT u',u_image,u_wcs),(axes[1],'CFHT r',r['image'],r['wcs'])):
        xy=pixel_positions(wcs,grid);im=map_coordinates(image,[xy[:,:,1],xy[:,:,0]],order=1,mode='constant',cval=np.nan)
        if not np.isfinite(im).any():
            ax.text(.5,.5,'No valid core pixels',ha='center',transform=ax.transAxes)
            continue
        im=(im-np.nanmedian(im))/robust_sigma(im[np.isfinite(im)])
        ax.imshow(im,origin='lower',extent=[-65,65,-65,65],cmap='gray',vmin=-2,vmax=7)
        ax.add_patch(plt.Circle((0,0),45,fill=False,color='#d9a33b'))
        ax.set(title=band,xlabel='East (arcsec)',ylabel='North (arcsec)')
    fig.savefig(out/'native_cfht_core.png',dpi=160);plt.close(fig)
    print('CFHT_CORE_MEASURED',r['report']['aperture5_mag'],flush=True)


if __name__=='__main__':run()
