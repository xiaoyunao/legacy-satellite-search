"""Unweighted full-extent gr and radial supplement for large saved hypotheses."""
from functools import cache
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
from ls_satsearch.review import coadd_stamp
from ls_satsearch.run import sha

image_digest = cache(sha)


def render(path, sample, area, field, mode, root, region, bricks):
    x,y = field.xy(float(mode['fit_ra_deg']),float(mode['fit_dec_deg']))
    rh = float(mode['fit_rh_arcmin'])
    halfwidth = max(30.,2*rh*60)
    pixel = max(.524,2*halfwidth/1400)
    bx,by = field.xy(bricks['RA'],bricks['DEC'])
    distance = np.hypot(bx-x,by-y)
    # Include all native bricks intersecting the square, plus their half-diagonal.
    nearby = np.flatnonzero(distance <= np.sqrt(2)*halfwidth/60+12)
    fig,axes = plt.subplots(1,3,figsize=(13,4.5),layout='constrained')
    images = {}
    for band,ax in zip('gr',axes[:2]):
        paths = []
        for i in nearby[np.argsort(distance[nearby])]:
            name = bricks['BRICKNAME'][i].strip()
            p = root/region/'coadd'/name[:3]/name/f'legacysurvey-{name}-image-{band}.fits.fz'
            if p.is_file():paths.append(p)
        stamp,extent = coadd_stamp(paths,field,x,y,halfwidth,pixel)
        finite = np.isfinite(stamp)
        lo,hi = np.nanpercentile(stamp,(8,99.5)) if finite.any() else (0,1)
        ax.imshow(stamp,origin='lower',extent=np.asarray(extent)/60,cmap='gray',vmin=lo,vmax=hi)
        ax.add_patch(plt.Circle((0,0),rh,fill=False,color='#e6ae58',lw=.7))
        ax.set(title=f'Observed {band}: full hypothesis extent',xlabel='East (arcmin)',ylabel='North (arcmin)')
        images[band] = dict(finite_pixel_fraction=float(finite.mean()),
                           image_inputs_sha256={str(p):image_digest(p) for p in paths})
    edges = np.linspace(0,6*rh,13)
    radius = np.linalg.norm(sample[:,:2]-(x,y),axis=1)
    counts = np.histogram(radius,bins=edges)[0]
    step = 2*field.limit/len(area)
    axis = (np.arange(len(area))+.5)*step-field.limit
    ix = np.flatnonzero(abs(axis-x)<=6*rh)
    iy = np.flatnonzero(abs(axis-y)<=6*rh)
    rr = np.hypot(axis[ix][None,:]-x,axis[iy][:,None]-y)
    exposed = np.histogram(rr,bins=edges,weights=area[np.ix_(iy,ix)])[0]*step**2
    valid = exposed>0
    middle = (edges[:-1]+edges[1:])/2
    axes[2].errorbar(middle[valid]/rh,counts[valid]/exposed[valid],
                    yerr=np.sqrt(counts[valid])/exposed[valid],fmt='o',ms=4)
    axes[2].set(xlabel='Radius / hypothesis half-light radius',ylabel='Selected sources / usable arcmin²',
                title='Unweighted observed radial profile')
    fig.suptitle('Full spatial hypothesis; adaptive image sampling. Poisson count bars omit background uncertainty.')
    fig.savefig(path,dpi=150);plt.close(fig)
    return dict(halfwidth_arcsec=halfwidth,pixel_arcsec=pixel,full_two_rh_square=True,images=images,
                radial_counts=counts.tolist(),radial_usable_arcmin2=exposed.tolist(),
                probabilities_or_scores_rendered=False,renderer_sha256=sha(Path(__file__)))
