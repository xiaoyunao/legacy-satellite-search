"""Catalog-level photometric and morphology response in matched development fields."""

import numpy as np
from scipy.spatial import cKDTree

from .data import load_bricks, sample_pixels, select
from .matched import ps1_measurements, reddening
from .run import field_cache, settings


def measurement_curve(mags, errors, target):
    usable = np.isfinite(mags+errors) & (mags>0) & (errors>0)
    m, e = mags[usable], errors[usable]
    if len(m)<30:
        raise ValueError('Insufficient preselection measurements for an error curve')
    order = np.argsort(m)
    m,e = m[order],e[order]
    im = np.searchsorted(m,target)
    return np.array([np.median(e[max(0,i-25):min(len(m),i+25)])
                     for i in im])*10**(.4*np.maximum(target-m[-1],0))


def perturb(mags, pool, pos, rng):
    """Use nearby measured errors before applying sample cuts."""
    xy,values,errors,tree = pool
    ids = np.atleast_1d(tree.query(pos,k=min(2400,len(xy)))[1])
    sig = np.column_stack([measurement_curve(values[ids,b],errors[ids,b],mags[:,b])
                           for b in range(mags.shape[1])])
    noisy = mags + rng.normal(size=mags.shape)*sig
    return noisy, sig*10**(.4*(noisy-mags))


def pool(xy,values,errors):
    return xy,values,errors,cKDTree(xy)


def gr_accept(phot,err,cfg):
    lim = 2.5/np.log(10)/cfg['min_snr']
    return (np.isfinite(phot+err) & (phot>0) & (err>0) & (err<=lim) &
            (phot <= [cfg['g_max'],cfg['r_max']])).all(axis=1)


def models(field,area,spec,matched,cfg):
    root,data,_ = settings()
    spec = dict(spec,width=matched['width_deg'],buffer_arcmin=matched['buffer_arcmin'])
    _,ls,_,_ = field_cache(root,data,spec,cfg,load_bricks(root))
    xy = np.column_stack(field.xy(ls['RA'],ls['DEC']))
    masked = (ls['MASKBITS'] & sum(1<<b for b in cfg['reject_maskbits'])) == 0
    masked &= area[sample_pixels(field,area,*xy.T)]
    mags,errors = [],[]
    for b in 'GR':
        f = ls[f'FLUX_{b}'].astype(float)
        ivar = ls[f'FLUX_IVAR_{b}']
        dust = ls[f'MW_TRANSMISSION_{b}']
        with np.errstate(invalid='ignore',divide='ignore'):
            mags.append(22.5-2.5*np.log10(f/dust))
            errors.append(np.where(ls[f'NOBS_{b}']>0,2.5/np.log(10)/(f*np.sqrt(ivar)),np.nan))
    ls_pool = pool(xy[masked],np.column_stack(mags)[masked],np.column_stack(errors)[masked])
    _,_,_,_,chosen = select(ls,field,area,dict(cfg,g_max=24.5,r_max=24.,min_snr=10))
    if 'FITBITS' in ls.dtype.names:
        chosen &= (ls['FITBITS'] & 1)==0
    chosen &= (ls['MASKBITS'] & ((1<<13)|(1<<17)))==0
    ref_tree = cKDTree(xy[chosen])
    raw,_ = ps1_measurements(spec,matched,data/'resources/ps1/tiles-v3'/spec['id'])
    ps_xy = np.column_stack(field.xy(raw[:,0],raw[:,1]))
    inside = (abs(ps_xy) < field.limit).all(axis=1)
    inside &= area[sample_pixels(field,area,*ps_xy.T)]
    ra,dec,g,r,ge,re,i,kron,ie = raw[inside].T
    ps_xy = ps_xy[inside]
    dust = reddening(ra,dec)
    g,r = g-3.172*dust,r-2.271*dust
    before = pool(ps_xy,np.column_stack([g,r,i]),np.column_stack([ge,re,ie]))
    close = ref_tree.query(ps_xy,distance_upper_bound=.7/60)[0] < np.inf
    gr = gr_accept(np.column_stack([g,r]),np.column_stack([ge,re]),cfg)
    valid_i = np.isfinite(i+ie)&(i>0)&(ie>0)
    good_i = valid_i&(ie<=2.5/np.log(10)/cfg['min_snr'])
    morphology = np.isfinite(kron)&(kron>0)&(i-kron<.05)
    g_edges = np.array([0.,20.,21.,22.,22.5,23.,24.,30.])
    colour_edges = np.array([-np.inf,.4,.8,np.inf])
    bins,rows = {},[]
    gold = close&gr
    if not gold.any():
        raise ValueError('No reliable LS point-source proxies in the joint sample')
    for gidx in range(len(g_edges)-1):
        for cidx in range(len(colour_edges)-1):
            in_bin = gold&(g>=g_edges[gidx])&(g<g_edges[gidx+1])
            in_bin &= (g-r>=colour_edges[cidx])&(g-r<colour_edges[cidx+1])
            measured = in_bin&good_i
            n,ni,ns,nm = (int(v.sum()) for v in (in_bin,in_bin&valid_i,measured,measured&morphology))
            calibrated = n>=20 and ns>=20
            bins[gidx,cidx] = (ni/n,nm/ns) if calibrated else None
            rows.append(dict(g_lo=g_edges[gidx],g_hi=g_edges[gidx+1],color_lo=colour_edges[cidx],
                             color_hi=colour_edges[cidx+1],parent=n,i_valid=ni,i_snr=ns,
                             morphology_pass=nm,response_calibrated=calibrated))
    return ls_pool,before,(g_edges,colour_edges,bins),rows


def ps1_select(phot,err,cfg,response,rng):
    """Apply g/r photometry, independent i availability/SNR, and a morphology proxy."""
    g_edges,c_edges,bins = response
    gi = np.searchsorted(g_edges,phot[:,0],side='right')-1
    ci = np.searchsorted(c_edges,phot[:,0]-phot[:,1],side='right')-1
    # Unsupported bins use the optimistic response and remain explicitly counted.
    rates = [bins.get((g,c)) for g,c in zip(gi,ci)]
    pi,pm = np.asarray([rate if rate is not None else (1.,1.) for rate in rates]).T
    gr = gr_accept(phot[:,:2],err[:,:2],cfg)
    i_valid = (np.isfinite(phot[:,2]+err[:,2]) & (phot[:,2]>0) & (err[:,2]>0) &
               (rng.random(len(phot))<pi))
    i_snr = i_valid & (err[:,2]<=2.5/np.log(10)/cfg['min_snr'])
    psf = rng.random(len(phot))<pm
    return gr&i_snr&psf, dict(N_gr=int(gr.sum()),N_gr_i_valid=int((gr&i_valid).sum()),
                              N_gr_i_snr=int((gr&i_snr).sum()),N_gr_i_psf=int((gr&i_snr&psf).sum()),
                              N_response_unsupported=int(sum(use and rate is None for use,rate in zip(gr,rates))))
