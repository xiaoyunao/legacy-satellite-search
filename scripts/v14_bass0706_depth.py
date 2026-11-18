"""Measure native independent BASS core depth with optical masks and native colour terms."""
import argparse
import os
from pathlib import Path

import astropy.units as u
from astropy.coordinates import SkyCoord
import fitsio
import matplotlib.pyplot as plt
import numpy as np
from numpy.polynomial.polynomial import polyval
from scipy.ndimage import map_coordinates

from bass_template import CORRECTION
from ls_satsearch.data import Field, load_bricks
from ls_satsearch.run import read_csv, sha, write_csv, write_json
from v12_footprint import save
from v14_image0706 import DEC, RA, measure_band, pixel_positions, reference, robust_sigma


def run(calibration_outer=5.):
    root=Path(os.environ['LS_DR11_ROOT']);data=Path(os.environ['LS_SAT_DATA'])
    folder=data/'resources/v14/v13r_south_ps1_0706-A_base-0.3-001'
    out=Path('results/v14/0706/bass_images');out.mkdir(parents=True,exist_ok=True)
    center=SkyCoord(RA,DEC,unit='deg');ref,mag=reference(folder,center,outer_arcmin=calibration_outer)
    rows=[r for r in read_csv(folder/'ps1.csv') if 0<=float(r['raStack'])<360 and abs(float(r['decStack']))<=90]
    sky=SkyCoord([float(r['raStack']) for r in rows],[float(r['decStack']) for r in rows],unit='deg')
    ids,sep,_=ref.match_to_catalog_sky(sky)
    if np.any(sep.arcsec>.05):
        raise ValueError('PS1 off-core reference rematch failed')
    color=np.clip(mag[:,0]-np.array([float(rows[i]['iPSFMag']) for i in ids]),.4,2.7)
    for j,b in enumerate('gr'):
        mag[:,j]+=polyval(color,CORRECTION[b])
    area=Field(RA,DEC,.12,1/6,buffer=0)
    bricks=load_bricks(root,'north')
    bricks=bricks[area.overlap(bricks['RA1'],bricks['RA2'],bricks['DEC1'],bricks['DEC2'])]
    attempts=[];chosen={};inputs={}
    for j,band in enumerate('gr'):
        choices=[]
        for brick in bricks:
            name=str(brick['BRICKNAME']).strip()
            path=root/'north/coadd'/name[:3]/name/f'legacysurvey-{name}-image-{band}.fits.fz'
            if not path.is_file():
                continue
            try:
                result=measure_band(path,ref,mag[:,j],center,487190+j)
                tractor=root/'north/tractor'/name[:3]/f'tractor-{name}.fits'
                sources=fitsio.read(tractor,columns=['RA','DEC',f'MW_TRANSMISSION_{band.upper()}'],upper=True)
                nearby=SkyCoord(sources['RA'],sources['DEC'],unit='deg').separation(center).arcmin<=.75
                transmission=sources[f'MW_TRANSMISSION_{band.upper()}'][nearby]
                transmission=transmission[np.isfinite(transmission)&(transmission>0)&(transmission<=1)]
                if not len(transmission):
                    raise ValueError('No core extinction references in native Tractor')
                extinction=float(np.median(-2.5*np.log10(transmission)))
                ccd=path.with_name(f'legacysurvey-{name}-ccds.fits')
                visits=fitsio.read(ccd,columns=['camera','expnum','filter'],upper=True)
                selected=visits[np.char.strip(visits['FILTER'].astype(str))==band]
                cameras=sorted(set(np.char.strip(selected['CAMERA'].astype(str))))
                if cameras!=['90prime']:
                    raise ValueError(f'Unexpected native gr input cameras: {cameras}')
                result['report'].update(brick=name,band=band,extinction_mag=extinction,
                    aperture0_5_mag=result['report']['aperture5_mag']-extinction,
                    formal_brick_psfdepth0_5=float(brick['PSFDEPTH_'+band.upper()])-extinction,
                    calibration_system='BASS via frozen official PS1-to-90Prime colour polynomials',
                    mask_reject_bits=[1,5,6,10,19],native_cameras=cameras,
                    expnums=sorted(set(map(int,selected['EXPNUM']))),source=str(path.relative_to(root)),
                    ccd_provenance_sha256=sha(ccd))
                choices.append(result);attempts.append(dict(status='measured',**result['report']))
            except (ValueError,StopIteration) as exc:
                attempts.append(dict(brick=name,band=band,status='unusable',reason=str(exc)))
        if choices:
            chosen[band]=max(choices,key=lambda r:(r['report']['full_aperture_core_coverage'],r['report']['full_aperture_background_coverage']))
            inputs[band]=chosen[band]['report']
    write_csv(out/'all_products.csv',attempts)
    model=data/'resources/isochrones/bass/ps1_projected12_z0.00010.dat'
    with model.open() as handle:
        for line in handle:
            if line.startswith('#') and 'M_ini' in line and 'int_IMF' in line:
                header=line[1:].split();break
        else:
            raise ValueError('Missing native BASS PARSEC header')
    stage='stage' if 'stage' in header else 'label'
    model_g,phase=np.loadtxt(model,usecols=[header.index('g'),header.index(stage)],unpack=True)
    ms_tip=float(np.min(model_g[phase==1])+19.25)
    write_json(out/'summary.json',dict(job=os.getenv('SLURM_JOB_ID'),ra_deg=RA,dec_deg=DEC,
        frozen_dm=19.25,model_sha256=sha(model),brightest_stage1_main_sequence_g0=ms_tip,
        products=inputs,calibration_annulus_arcmin=[1.,calibration_outer],scope='Independent 90Prime exposures; same LS processing family. Native masked aperture depths, not a new population detection or a completeness measurement.'))
    if not chosen:
        return
    fig,axes=plt.subplots(1,2,figsize=(8,4),layout='constrained')
    axis=np.linspace(-65,65,360);xx,yy=np.meshgrid(axis,axis)
    grid=center.spherical_offsets_by(xx*u.arcsec,yy*u.arcsec)
    for ax,band in zip(axes,'gr'):
        if band not in chosen:
            ax.text(.5,.5,'No calibrated product',ha='center',transform=ax.transAxes);continue
        value=chosen[band];xy=pixel_positions(value['wcs'],grid)
        pixels=map_coordinates(value['image'],[xy[:,:,1],xy[:,:,0]],order=1,mode='constant',cval=np.nan)
        image=(pixels-np.nanmedian(pixels))/robust_sigma(pixels[np.isfinite(pixels)])
        ax.imshow(image,origin='lower',extent=[-65,65,-65,65],cmap='gray',vmin=-2,vmax=7)
        ax.add_patch(plt.Circle((0,0),45,fill=False,color='#d3a340',lw=.8))
        ax.set(xlabel='East (arcsec)',ylabel='North (arcsec)',
               title=f'BASS {band} · 5σ {value["report"]["aperture0_5_mag"]:.2f}')
    save(fig,out/'native_bass_core')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--calibration-outer',type=float,default=5.)
    run(parser.parse_args().calibration_outer)
