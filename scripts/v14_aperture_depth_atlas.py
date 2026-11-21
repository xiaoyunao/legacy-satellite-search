"""Put the verified three image-weight comparisons on the same colour scale."""

import argparse
import json
from pathlib import Path

from astropy.coordinates import SkyCoord
import matplotlib.pyplot as plt
import numpy as np

from ls_satsearch.run import read_csv, sha, write_json
from scripts.v14_qualified_aitoff import axes_map, save

COMPARISONS = (('DES Y6', 'des'), ('DELVE DR3', 'delve'), ('PS1 stacks', 'ps1'))


def run(results, output):
    tables = []
    inputs = {}
    for name, key in COMPARISONS:
        folder = results / f'{key}_image_depth'
        proof = folder / 'manifest.json'
        receipt = json.loads(proof.read_text())
        table = folder / 'paired_aperture_depth.csv'
        if sha(table) != receipt['outputs'][table.name]:
            raise ValueError(f'{name} source table changed')
        rows = read_csv(table)
        if len(rows) != receipt['measured'] or not rows:
            raise ValueError(f'{name} is missing measured sky positions')
        coords = SkyCoord([float(r['ra_deg']) for r in rows], [float(r['dec_deg']) for r in rows], unit='deg')
        l = -np.deg2rad((coords.galactic.l.deg + 180) % 360 - 180)
        b = coords.galactic.b.rad
        values = [np.array([float(r[f'ls_minus_{key}_{band}_m10']) for r in rows]) for band in 'gr']
        tables.append((name, l, b, values))
        inputs[name] = dict(job=receipt['job'], manifest_sha256=sha(proof), table_sha256=sha(table),
                            measured=receipt['measured'], band_statistics=receipt['band_statistics'])
    fig, axes = plt.subplots(3, 2, figsize=(13, 11), subplot_kw={'projection':'aitoff'}, layout='constrained')
    limit = np.ceil(np.quantile(np.abs(np.concatenate([v for _,_,_,vs in tables for v in vs])), .99) * 4) / 4
    for row, (name, l, b, values) in zip(axes, tables):
        for ax, band, value in zip(row, 'gr', values):
            artist = ax.scatter(l, b, c=value, cmap='RdBu_r', vmin=-limit, vmax=limit,
                                s=13, linewidths=0, rasterized=True)
            axes_map(ax, f'{band} band · DR11 − {name} ({len(value)} positions)')
    fig.colorbar(artist, ax=axes, shrink=.72, extend='both', label='Observed 10σ aperture depth difference (mag)')
    fig.suptitle('Same-sky formal 2″ aperture depth differences in the census assignments')
    output.mkdir(parents=True, exist_ok=False)
    save(fig, output/'common_aperture_depth_atlas')
    write_json(output/'manifest.json', dict(
        inputs=inputs, colour_bounds_mag=[-limit,limit], code_sha256=sha(Path(__file__)),
        outputs={p.name:sha(p) for p in output.iterdir()},
        scope='Sampled images and released survey weight maps. Formal observed AB aperture noise across native passbands. Blank areas have no plotted sample. Covariance, resolved-star selection and system recovery require separate measurements.'))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('results', type=Path)
    p.add_argument('output', type=Path)
    args = p.parse_args()
    run(args.results, args.output)
