"""Check public CFHT exposures against the LS shortlist using small WCS cutouts."""

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import os
from urllib.parse import urlencode
from urllib.request import urlopen

from astropy.coordinates import SkyCoord
from astropy.io import fits
import astropy.units as u
from astropy.wcs import WCS
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import map_coordinates

from .candidate_archives import frozen_positions
from .run import sha, write_csv, write_json
from .verify_candidate import OUT, setup


CADC = 'https://ws.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/caom2ops/sync'
EXPOSURES = ('2159099p','2159100p','2159103p','2160132p','2161338p')


def fetch(product,center,cache,grid):
    query=CADC+'?'+urlencode(dict(id=f'cadc:CFHT/{product}.fits.fz',
                                   CIRCLE=f'{center.ra.deg} {center.dec.deg} 0.026'))
    path=cache/f'{product}.fits'
    try:
        if path.exists():
            payload=path.read_bytes()
        else:
            with urlopen(query,timeout=40) as response:
                payload=response.read(35000001)
        if len(payload)>35000000:
            raise ValueError('Archive response exceeds the small cutout limit')
        stamps=[]
        with fits.open(BytesIO(payload),memmap=False) as h:
            for item in h:
                if item.data is None or item.data.ndim!=2:
                    continue
                wcs=WCS(item.header).celestial
                if not wcs.has_celestial:
                    continue
                x,y=wcs.world_to_pixel(grid)
                image=np.asarray(item.data,dtype=float)
                valid=(x>1)&(y>1)&(x<image.shape[1]-2)&(y<image.shape[0]-2)
                if not valid.any():
                    continue
                pix=np.full(grid.shape,np.nan)
                z=map_coordinates(image,[y[valid],x[valid]],order=1,prefilter=False)
                mid=np.median(z)
                noise=1.4826*np.median(abs(z-mid))
                if noise>0:
                    pix[valid]=(z-mid)/noise
                    stamps.append(pix)
        path.write_bytes(payload)
        stamp=stamps[0].copy() if stamps else np.full(grid.shape,np.nan)
        for part in stamps[1:]:
            holes=~np.isfinite(stamp)
            stamp[holes]=part[holes]
        return dict(product=product,query=query,sha256=sha(path),status='covered' if stamps else 'no_pixels',
                    usable_fraction=float(np.isfinite(stamp).mean())),stamp
    except (ValueError,OSError) as err:
        return dict(product=product,query=query,status='unavailable',error=str(err)),None


def run():
    plan,_,data,_,sources,_=setup()
    cache=data/'resources/v6'/plan['candidate']/'cfht'
    cache.mkdir(exist_ok=True,parents=True)
    OUT.mkdir(exist_ok=True,parents=True)
    center=SkyCoord(plan['ra_deg'],plan['dec_deg'],unit='deg')
    pos=frozen_positions(plan,data,sources)
    east,north=center.spherical_offsets_to(pos)
    d=.3
    axis=np.arange(-265,266)*d
    dx,dy=np.meshgrid(axis,axis)
    sky=center.spherical_offsets_by(dx*u.arcsec,dy*u.arcsec)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(lambda p: fetch(p,center,cache,sky), EXPOSURES))
    rows=[r for r,_ in results]
    write_csv(OUT/'cfht_exposure_status.csv',rows)
    stamps=[a for r,a in results if r['status']=='covered']
    metrics=dict(job=os.environ.get('SLURM_JOB_ID'),band='MegaCam r.MP9602',
                 covering_exposures=len(stamps),requested=len(EXPOSURES),catalogue_members=len(pos))
    if stamps:
        stack=np.asarray(stamps)
        count=np.isfinite(stack).sum(axis=0)
        image=np.ma.median(np.ma.masked_invalid(stack),axis=0).filled(np.nan)
        fig,axes=plt.subplots(1,2,figsize=(8,4),layout='constrained')
        extent=[axis[0]-d/2,axis[-1]+d/2]*2
        axes[0].imshow(image,origin='lower',extent=extent,vmin=-1.7,vmax=7.,cmap='gray')
        axes[0].scatter(east.arcsec,north.arcsec,s=39,facecolor='none',edgecolor='#56cfe1')
        axes[0].set_title('CFHT r · frozen LS positions')
        axes[1].imshow(count,origin='lower',extent=extent,cmap='viridis',vmin=0,vmax=len(stamps))
        axes[1].set_title('Exposure count')
        for ax in axes:
            ax.set(xlabel='East (arcsec)',ylabel='North (arcsec)')
        fig.savefig(OUT/'cfht_r_independent_image.png',dpi=160)
        plt.close(fig)
        metrics.update(central_exposures=int(count[len(axis)//2,len(axis)//2]),
                       fraction_with_two_exposures=float((count>=2).mean()))
    write_json(OUT/'cfht_r_summary.json',metrics)


if __name__=='__main__':
    run()
