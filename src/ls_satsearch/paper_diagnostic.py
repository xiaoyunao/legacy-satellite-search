"""DES-style display of a fixed LS hypothesis, using independent pixel coverage."""
import argparse
import json
import os
import re
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle
import numpy as np
from scipy.ndimage import gaussian_filter
from scipy.signal import fftconvolve
from scipy.spatial import cKDTree
from scipy.special import ndtri
from scipy.stats import binom, chi2
import yaml

from .data import select
from .run import field_cache, sha, write_json
from .search import CMD, load_isochrone, point_fit


def smooth_density(count, area, sigma, pixel_area):
    blurred_area = gaussian_filter(area,sigma,mode='constant')
    blurred_count = gaussian_filter(count,sigma,mode='constant')
    valid = (area>=.5*pixel_area)&(blurred_area>=.5*pixel_area)
    return np.divide(blurred_count,blurred_area,out=np.full_like(blurred_count,np.nan),where=valid)


def conditional_z(on, off, a, b):
    total = on+off
    fraction = np.divide(a,a+b,out=np.zeros_like(a),where=a+b>0)
    positive = on >= total*fraction
    p = np.where(positive,binom.sf(on-1,total,fraction),binom.cdf(on,total,fraction))
    return np.where(positive,1,-1) * -ndtri(np.clip(p,1.e-12,.5))


def local_z(count, area, rh, step):
    size = int(np.ceil(6*rh/step))
    axis = np.arange(-size,size+1)*step
    rho = np.hypot(axis[:,None],axis[None,:])
    inner = rho<=1.5*rh
    ann = (rho>=3.5*rh)&(rho<=6*rh)
    on,off = (np.rint(fftconvolve(count,k,mode='same')).clip(0) for k in (inner,ann))
    a,b = (fftconvolve(area,k,mode='same').clip(0) for k in (inner,ann))
    good = (a>=.75*inner.sum()*step**2)&(b>=.6*ann.sum()*step**2)&(area>=.5*step**2)
    return np.where(good,conditional_z(on,off,a,b),np.nan)


def histogram(xy, edges):
    return np.histogram2d(xy[:,1],xy[:,0],bins=(edges,edges))[0]


def usable_centers(field, area, x, y, half):
    spacing = 2*field.limit/len(area)
    axis = (np.arange(len(area))+.5)*spacing-field.limit
    ix,iy = [np.flatnonzero(abs(axis-c)<=half) for c in (x,y)]
    mx,my = np.meshgrid(axis[ix]-x,axis[iy]-y)
    keep = area[np.ix_(iy,ix)]
    return np.column_stack((mx[keep],my[keep])),spacing**2


def extended_locus(sources, field, valid, mags, locus, origin):
    types = np.char.strip(sources['TYPE'].astype('U'))
    use = valid & np.isin(types,('REX','EXP','DEV','SER'))
    err = np.column_stack([2.5/np.log(10)/(sources[f'FLUX_{b}'][use]*
                 np.sqrt(sources[f'FLUX_IVAR_{b}'][use])) for b in 'GR'])
    distance, index = cKDTree(locus).query(mags[use],k=16,distance_upper_bound=.52)
    residual = mags[use,None,:]-locus[np.minimum(index,len(locus)-1)]
    chi = np.sum(residual**2/(err[:,None,:]**2+.045**2),axis=2)
    selected = np.flatnonzero(use)[np.any((chi<=2.5**2)&np.isfinite(distance),axis=1)]
    return np.column_stack(field.xy(sources['RA'][selected],sources['DEC'][selected]))-origin


def draw(stem, target, field, area, sources, sample, valid, mags, model, cfg,
         peak, fit, members, prob, width=1.5, sigma=1.62):
    x,y,dm,rh = (peak[k] for k in ('x','y','dm','rh_arcmin'))
    half,step = width*30,.25
    pad = np.ceil((half+max(6*rh,4*sigma))/step)*step
    edges = np.arange(-pad,pad+step/2,step)
    sky,cell = usable_centers(field,area,x,y,pad)
    geom = histogram(sky,edges)*cell
    delta = sample[:,:2]-(x,y)
    star,_ = CMD(sample,model,cfg).weights(dm)
    gxy = extended_locus(sources,field,valid,mags,model[2]+dm,(x,y))
    star_image = histogram(delta[star],edges)
    maps = [smooth_density(img,geom,sigma/step,step**2)
            for img in (star_image,histogram(gxy,edges))]
    maps.append(local_z(star_image,geom,rh,step))
    i = np.flatnonzero(abs((edges[1:]+edges[:-1])/2)<half)
    where = np.ix_(i,i)
    fig,ax = plt.subplots(2,3,figsize=(13.7,9),layout='constrained')
    blue = '#26658f'
    for j,(a,arr,title) in enumerate(zip(ax[0],maps,
                ('CMD-selected stars','CMD-selected extended sources','Local on–off excess'))):
        a.set_facecolor('#d9d5cf')
        values = arr[where]
        finite = values[np.isfinite(values)]
        upper = max(.02,np.quantile(finite,.995)) if len(finite) else 1.
        picture = a.imshow(values,origin='lower',extent=[-half,half]*2,
                          cmap='RdBu_r' if j==2 else 'Greys',interpolation='nearest',
                          vmin=-4 if j==2 else 0,vmax=4 if j==2 else upper,rasterized=True)
        a.add_patch(Circle((0,0),rh,color=blue,fill=False,lw=1.2))
        a.plot(0,0,marker='+',color=blue,ms=8)
        if j==2 and len(prob):
            use=prob>=.15
            a.scatter(*delta[members[use]].T,facecolors='none',edgecolors='#645009',
                      s=20+32*prob[use],lw=.8,zorder=4)
        a.set(xlabel='East (arcmin)',ylabel='North (arcmin)',title=title,
              xlim=(half,-half),ylim=(-half,half))
        fig.colorbar(picture,ax=a,shrink=.76,label='Local nominal Z' if j==2 else 'arcmin⁻²')

    radius = np.hypot(*delta.T)
    ar = np.hypot(*sky.T)
    on = radius<=1.5*rh
    off = (radius>=3.5*rh)&(radius<=6*rh)
    a_on = (ar<=1.5*rh).sum()*cell
    a_off = ((ar>=3.5*rh)&(ar<=6*rh)).sum()*cell
    rr = np.r_[0,np.geomspace(max(.13,.3*rh),6*rh,12)]
    n = np.histogram(radius[star],rr)[0]
    av = np.histogram(ar,rr)[0]*cell
    use = av>0
    low = np.where(n>0,chi2.ppf(.15865,2*np.maximum(n,1))/2,0.)
    hi = chi2.ppf(.84135,2*(n+1))/2
    ax[1,0].errorbar(((rr[1:]+rr[:-1])/2)[use],n[use]/av[use],
                    yerr=np.vstack((n-low,hi-n))[:,use]/av[use],
                    marker='o',ls='none',ms=3.8,color='#222222',label='CMD-selected counts')
    if a_off:
        bg=(star&off).sum()/a_off
        ax[1,0].axhline(bg,color='#666666',ls='--',lw=1,label='Annulus density')
        if fit:
            r=np.linspace(0,6*rh,200)
            amplitude=prob[star[members]].sum()/fit['profile_integral']
            profile=bg+amplitude/(np.pi*rh**2)/(1+(r/rh)**2)**2
            ax[1,0].plot(r,profile,color=blue,lw=1.4,label='Plummer + background')
    ax[1,0].set(xlabel='Radius (arcmin)',ylabel='Stars arcmin⁻²',title='Radial profile')
    ax[1,0].legend(frameon=False,fontsize=8)

    c = sample[:,2]-sample[:,3]
    g = sample[:,2]
    c_edges = np.linspace(-.5,1.75,24)
    g0 = max(14.,dm-4)
    g_edges = np.linspace(g0,cfg['g_max'],int(np.ceil((cfg['g_max']-g0)/.25))+1)
    extent=[c_edges[0],c_edges[-1],g_edges[0],g_edges[-1]]
    h1,h2 = (np.histogram2d(g[u],c[u],bins=(g_edges,c_edges))[0] for u in (on,off))
    ax[1,1].imshow(np.log1p(h2),origin='lower',extent=extent,aspect='auto',cmap='Greys',rasterized=True)
    ax[1,1].scatter(c[on],g[on],c='#444444',s=9,alpha=.55,linewidths=0)
    if len(prob):
        use=(prob>=.05)&on[members]
        m=members[use]
        picture=ax[1,1].scatter(c[m],g[m],c=prob[use],s=23,cmap='viridis',vmin=0,vmax=1,
                                zorder=4,linewidths=.25,edgecolors='k')
        fig.colorbar(picture,ax=ax[1,1],shrink=.76,label='C membership')
    hz = conditional_z(h1,h2,np.full_like(h1,a_on),np.full_like(h2,a_off)) if a_on and a_off else np.full_like(h1,np.nan)
    picture=ax[1,2].imshow(hz,origin='lower',extent=extent,aspect='auto',vmin=-3,vmax=3,
                          cmap='RdBu_r',rasterized=True)
    fig.colorbar(picture,ax=ax[1,2],shrink=.76,label='Local nominal Z per bin')
    ax[1,1].set_title('Core CMD and control Hess')
    ax[1,2].set_title('Area-scaled Hess contrast')
    mg,mr=model[2].T
    for a in ax[1,1:]:
        a.scatter(mg-mr,mg+dm,s=1.5,color='#00737d',linewidths=0,alpha=.7)
        a.set(xlabel='(g − r)₀ (mag)',ylabel='g₀ (mag)',xlim=extent[:2],ylim=extent[2:][::-1])
    fig.suptitle(f"{target}   |   μ {dm:.2f}   ·   rₕ {rh:.2f}′   |   {width:g}°   ·   Gaussian σ {sigma:g}′",
                 fontsize=16,fontweight='medium')
    fit_text = f"Fixed C TS {fit['ts']:.2f}" if fit else 'Fixed C unavailable'
    fig.supxlabel(f"LS DR11 {cfg['region']}   ·   g₀ ≤ {cfg['g_max']}   ·   r₀ ≤ {cfg['r_max']}   ·   {fit_text}")
    for suffix in ('png','pdf','svg'):
        output = stem.with_name(stem.name+'.'+suffix)
        fig.savefig(output,dpi=210)
        if suffix=='svg':
            # Generated path attributes contain nonsemantic trailing spaces.
            svg = output.read_text()
            output.write_text(re.sub(r'[ \t]+(?=\n)', '', svg))
    plt.close(fig)
    return dict(area_on_arcmin2=a_on,area_off_arcmin2=a_off,core_cmd_star_count=int((on&star).sum()),
                fixed_C_TS=float(fit['ts']) if fit else None,width_deg=width,sigma_arcmin=sigma,
                map_pixel_arcmin=step)


def render_case(case, output):
    path = Path(case['manifest'])
    manifest = json.loads(path.read_text())
    cfg = manifest['config']
    if manifest['status']!='complete':
        raise ValueError(f'Incomplete reference scan: {path}')
    root,data = (Path(os.environ[k]) for k in ('LS_DR11_ROOT','LS_SAT_DATA'))
    field,sources,area,_ = field_cache(root,data,manifest['field'],cfg,None)
    sample,_,valid,mags,_ = select(sources,field,area,cfg)
    model = load_isochrone(data/'resources'/cfg['isochrone'])
    x,y = field.xy(case['ra_deg'],case['dec_deg'])
    peak=dict(x=x,y=y,dm=case['dm'],rh_arcmin=case['rh'])
    cmd=CMD(sample,model,cfg)
    fit,members,prob=point_fit(sample,cmd,field,area,peak)
    if fit is None:
        members,prob=np.empty(0,dtype=int),np.empty(0)
    output.mkdir(parents=True,exist_ok=True)
    metrics = []
    for panel in case['panels']:
        stem=output/(case['id']+panel.get('suffix',''))
        metrics.append(dict(id=stem.name,**draw(stem,case['label'],field,area,sources,sample,valid,mags,
                              model,cfg,peak,fit,members,prob,panel['width'],panel['sigma'])))
    write_json(output/(case['id']+'.json'),dict(case=case,manifest_sha256=sha(path),
              job=os.environ.get('SLURM_JOB_ID'),figures=metrics,
              scope='Fixed-centre C and local diagnostic on-off tails without trials correction.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('config',type=Path)
    p.add_argument('target')
    p.add_argument('output',type=Path)
    a=p.parse_args()
    cases=yaml.safe_load(a.config.read_text())['targets']
    render_case(next(t for t in cases if t['id']==a.target),a.output)
