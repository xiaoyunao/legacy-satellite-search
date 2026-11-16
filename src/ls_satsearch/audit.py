"""Aggregate DR11 processing flags inside and around benchmark systems."""

from pathlib import Path

import fitsio
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial import cKDTree

from .data import Field, load_bricks, make_area, select
from .run import read_csv, settings, write_csv
from .search import CMD, exact_onoff, load_isochrone, point_fit

COLUMNS = ('RA', 'DEC', 'TYPE', 'MASKBITS', 'FITBITS', 'BRICK_PRIMARY') + tuple(
    f'{key}_{band}' for band in 'GR' for key in
    ('FLUX', 'FLUX_IVAR', 'MW_TRANSMISSION', 'NOBS', 'PSFDEPTH', 'PSFSIZE'))


def local_tractors(root, bricks, field):
    use = field.overlap(bricks['RA1'], bricks['RA2'], bricks['DEC1'], bricks['DEC2'])
    parts = []
    for name in bricks['BRICKNAME'][use]:
        name = name.strip()
        p = root / 'south/tractor' / name[:3] / f'tractor-{name}.fits'
        if not p.exists():
            continue
        data = fitsio.read(p, ext=1, columns=list(COLUMNS), upper=True)
        x, y = field.xy(data['RA'], data['DEC'])
        parts.append(data[data['BRICK_PRIMARY'] & (abs(x) < field.limit) & (abs(y) < field.limit)])
    return np.concatenate(parts) if parts else None


def main():
    root, data_root, cfg = settings()
    bricks = load_bricks(root)
    path = data_root / 'resources' / cfg['isochrone']
    model = load_isochrone(path)
    old = load_isochrone(path, legacy_locus=True)
    fig, ax = plt.subplots(figsize=(6, 7), layout='constrained')
    for data, color, label in [(old[2], '#d75d48','Old interpolation'), (model[2], '#287890','Phase segments')]:
        ax.scatter(data[:,0]-data[:,1], data[:,0], s=4, c=color, label=label)
    ax.scatter(model[0][:,0]-model[0][:,1], model[0][:,0], s=7, facecolors='none', edgecolors='black',
               label='Native PARSEC rows')
    ax.set(xlabel='Absolute g − r', ylabel='Absolute g', ylim=(5.5,-2.8))
    ax.legend()
    fig.savefig('results/figures/isochrone_segments.png', dpi=150)
    plt.close(fig)
    result, response = [], []
    for truth in read_csv(Path('references/benchmarks.csv')):
        ra, dec, dist, rh = (float(truth[k]) for k in ('ra_deg','dec_deg','D_kpc','theta_h_arcmin'))
        field = Field(ra, dec, 2 * 6 * max(.5, rh)/60, 1/6, buffer=0)
        coverage, _ = make_area(root, field, bricks, sum(1<<b for b in cfg['reject_maskbits']),
                                cfg['coverage_subdivision'])
        data = local_tractors(root, bricks, field)
        dm = 5*np.log10(dist)+10
        step = field.step/cfg['coverage_subdivision']
        axis = (np.arange(len(coverage))+.5)*step-field.limit
        rho = np.hypot(axis[:, None], axis[None,:])
        core = rho <= 1.5*rh
        ring = (rho >= 3.5*rh) & (rho <= 6*rh)
        summary = dict(name=truth['name'], rh_arcmin=rh, below_scan_grid=rh < min(cfg['radii_arcmin']),
                       core_coverage=float(coverage[core].mean()), annulus_coverage=float(coverage[ring].mean()))
        if data is None or not np.any(coverage):
            result.append(dict(summary, audit_status='no_south_gr'))
            continue
        for depth, delta in (('base',0),('deep',.5)):
            settings_depth = dict(cfg, g_max=cfg['g_max']+delta, r_max=cfg['r_max']+delta)
            sample, _, _, _, chosen = select(data, field, coverage, settings_depth)
            if not len(sample):
                result.append(dict(summary, depth=depth, audit_status='no_usable_psf'))
                continue
            cmd = CMD(sample, model, settings_depth)
            keep, ratio = cmd.weights(dm)
            r = np.hypot(*sample[:,:2].T)
            fit, idx, prob = point_fit(sample,cmd,field,coverage,dict(x=0,y=0,dm=dm,rh_arcmin=rh),ratio=ratio)
            membership = np.zeros(len(sample))
            membership[idx] = prob
            for region, use in [('centre',r<=1.5*rh), ('annulus',(r>=3.5*rh)&(r<=6*rh))]:
                row = dict(summary, depth=depth, region=region, audit_status='measured',
                           psf=int(use.sum()), cmd_psf=int((keep&use).sum()),
                           fitted_membership=float(membership[use].sum()))
                for col, bit, key in [('MASKBITS',17,'resolved'),('MASKBITS',13,'cluster'),
                                       ('FITBITS',0,'forced'),('FITBITS',12,'gaia')]:
                    flag=(data[col][chosen]&(1<<bit))!=0
                    row[f'{key}_psf']=int((flag&use).sum())
                    row[f'{key}_cmd']=int((flag&use&keep).sum())
                    row[f'{key}_membership']=float(membership[use&flag].sum())
                for band in 'GR':
                    dp=data[f'PSFDEPTH_{band}'][chosen][use]
                    t=data[f'MW_TRANSMISSION_{band}'][chosen][use]
                    good=(dp>0)&(t>0)
                    row[f'{band.lower()}5_median']=float(np.median(
                        22.5-2.5*np.log10(5/np.sqrt(dp[good]))+2.5*np.log10(t[good]))) if good.any() else None
                result.append(row)
            if truth['name'] in ('Bootes_I','Coma_Berenices','Pegasus_IV','Virgo_II','Leo_Minor_I'):
                tree=cKDTree(sample[:,:2])
                for style, trial_model in [('segmented',model),('continuous',old)]:
                    audit=CMD(sample,trial_model,settings_depth)
                    for trial_dm in dm+np.arange(-1,1.01,.25):
                        on, off, area_on, area_off=exact_onoff(field,0,0,rh,tree,coverage,audit.weights(trial_dm)[0])
                        response.append(dict(name=truth['name'],depth=depth,locus=style,dm=trial_dm,
                                             on=on,off=off,area_on=area_on,area_off=area_off))
        print(truth['name'], summary['core_coverage'], flush=True)
    write_csv(Path('results/summary/benchmark_processing_audit.csv'),result)
    write_csv(Path('results/summary/benchmark_locus_response.csv'),response)


if __name__ == '__main__':
    main()
