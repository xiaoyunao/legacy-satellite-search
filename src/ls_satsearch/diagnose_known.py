"""Measure known-centre CMD excess and depth response after freezing the blind search."""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial import cKDTree
import yaml

from .data import select
from .run import config_path, field_cache, read_csv, settings, write_csv
from .search import CMD, exact_onoff, load_isochrone


def main(field_id):
    root, data_root, base = settings()
    spec = next(s for s in yaml.safe_load(config_path('fields.yaml').read_text())['fields']
                if s['id'] == field_id and s.get('truth'))
    truth = next(r for r in read_csv(Path('references/benchmarks.csv')) if r['name'] == spec['truth'])
    # Diagnostics follow the scan's extraction and reuse its scratch inputs.
    field, sources, area, _ = field_cache(root, data_root, spec, base, None)
    x, y = field.xy(float(truth['ra_deg']), float(truth['dec_deg']))
    dm = 5*np.log10(float(truth['D_kpc'])) + 10
    rh = float(truth['theta_h_arcmin'])
    model = load_isochrone(data_root/'resources'/base['isochrone'])
    fig, axes = plt.subplots(2, 2, figsize=(8, 8), sharex=True, sharey=True, layout='constrained')
    results = []
    sx, sy = field.xy(sources['RA'], sources['DEC'])
    raw_inside = np.hypot(sx-x, sy-y) <= 1.5*rh
    for offset, row in zip((0., .5), axes):
        cfg = dict(base, g_max=base['g_max']+offset, r_max=base['r_max']+offset)
        sample, flow, valid, mags, chosen = select(sources, field, area, cfg)
        if not len(sample):
            continue
        cmd = CMD(sample, model, cfg)
        on_cmd, _ = cmd.weights(dm)
        n1, n2, a1, a2 = exact_onoff(field, x, y, rh, cKDTree(sample[:, :2]), area, on_cmd)
        bg = n2*a1/a2 if a2 else None
        entry = dict(name=truth['name'], field=field_id, dm=dm, radius_arcmin=rh,
                     g_max=cfg['g_max'], r_max=cfg['r_max'], cmd_on=n1, cmd_off=n2, area_on=a1,
                     area_off=a2, scaled_background=bg, cmd_excess=n1-bg if bg is not None else None,
                     all_gr_in_aperture=int((valid & raw_inside).sum()), selected_psf_in_aperture=int((chosen & raw_inside).sum()))
        for bit, label in ((13,'cluster'), (17,'resolved')):
            entry[label] = int((chosen & raw_inside & ((sources['MASKBITS'] & (1 << bit)) != 0)).sum())
        if 'FITBITS' in sources.dtype.names:
            for bit, label in ((0,'forced_psf'), (12,'gaia_psf')):
                entry[label] = int((chosen & raw_inside & ((sources['FITBITS'] & (1 << bit)) != 0)).sum())
        results.append(entry)
        r = np.hypot(sample[:,0]-x, sample[:,1]-y)
        for ax, (use, label) in zip(row, ((r <= 1.5*rh, 'Known centre'),
                ((r >= 3.5*rh)&(r <= np.sqrt(3.5**2+1.5**2)*rh), 'Equal geometric area annulus'))):
            g, red = sample[use,2:4].T
            ax.scatter(g-red, g, s=10, c=np.where(on_cmd[use], '#c15338', '#63788e'), alpha=.64)
            ax.plot(model[0][:,0]-model[0][:,1], model[0][:,0]+dm, color='black', lw=.8)
            ax.set(xlim=(-.7,2.1), ylim=(24.1,15.), ylabel='$g_0$ (mag)', xlabel='$(g-r)_0$ (mag)',
                   title=f'{label} · g₀ ≤ {cfg["g_max"]:.1f}')
    home = Path('results')
    write_csv(home/'summary'/f'{field_id}-known_center_diagnostic.csv', results)
    fig.suptitle(f'{truth["name"]} · fixed-centre diagnostic · DM {dm:.2f}')
    fig.savefig(home/'figures'/f'{field_id}-known_center_cmd.png', dpi=150)
    plt.close(fig)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('field')
    main(p.parse_args().field)
