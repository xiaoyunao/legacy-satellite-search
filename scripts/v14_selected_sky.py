"""Map the realized faint baseline point-source sample using archived cutflows."""

import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

from astropy.coordinates import SkyCoord
from astropy_healpix import HEALPix
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import numpy as np

from ls_satsearch.run import sha, write_csv, write_json
from scripts.v14_missed_controls import MASK
from scripts.v14_qualified_aitoff import axes_map, save

SAMPLE_NSIDE = 16
FOOTPRINT_NSIDE = 256


def run(output, raster_path):
    if not os.getenv('SLURM_JOB_ID'):
        raise RuntimeError('Read the accepted DR11 field manifests on an allocated CPU')
    receipt = MASK / 'post_outside_C_registration_20261120.json'
    binding = json.loads(receipt.read_text())
    registration = Path(binding['registration'])
    if sha(registration) != binding['registration_sha256']:
        raise ValueError('Accepted mask registration changed')
    fields = [r for r in json.loads(registration.read_text())['records']
              if r['classification'] == 'qualified_discovery' and r['region'] in ('north','south')]
    positions = np.array([r['geometry'][:2] for r in fields])
    sky = SkyCoord(*positions.T, unit='deg').galactic
    coarse = HEALPix(nside=SAMPLE_NSIDE, order='ring', frame='galactic')
    fine = HEALPix(nside=FOOTPRINT_NSIDE, order='ring', frame='galactic')
    with np.load(raster_path) as raster:
        labels = raster['bits'][fine.skycoord_to_healpix(sky)]
    group = coarse.skycoord_to_healpix(sky)
    delta = coarse.healpix_to_skycoord(group).separation(sky).rad
    order = np.lexsort((np.arange(len(fields)), delta, group))
    rows, used, excluded = [], set(), Counter()
    for i in order:
        pixel = int(group[i])
        if not labels[i] or pixel in used:
            continue
        record = fields[i]
        path = Path(record['manifest'])
        if sha(path) != record['manifest_sha256']:
            raise ValueError(f'Accepted source scan changed: {path}')
        report = json.loads(path.read_text())
        config = report['config']
        if (config['g_max'],config['r_max'],config['min_snr']) != (23.5,23.,5):
            excluded['different_catalogue_limits'] += 1
            continue
        if 'background_core_deg2' in report:
            area = float(report['background_core_deg2'])
            area_role = 'full_background_core'
        elif not report['field'].get('ownership'):
            area = float(report['area_deg2'])
            area_role = 'unpartitioned_core'
        else:
            excluded['missing_full_core_area'] += 1
            continue
        counts = report['cutflow']
        if area <= 0 or not {'inner_psf_faint','inner_other_faint'} <= counts.keys():
            excluded['missing_faint_classification_counts'] += 1
            continue
        stellar = counts['inner_psf_faint']
        other = counts['inner_other_faint']
        if not stellar or stellar + other < 20:
            excluded['insufficient_faint_counts'] += 1
            continue
        rows.append(dict(field=record['field'], sample_pixel=pixel, gal_l_deg=sky[i].l.deg,
                         gal_b_deg=sky[i].b.deg, native_region=record['region'], census_bits=int(labels[i]),
                         core_area_deg2=area, area_role=area_role, n_psf_faint=stellar,
                         n_non_psf_faint=other, faint_psf_per_deg2=stellar/area,
                         faint_sample_psf_fraction=stellar/(stellar+other), source_sha256=record['manifest_sha256']))
        used.add(pixel)
    if not rows:
        raise ValueError('No realized stellar counts passed the coverage and sample gates')
    output.mkdir(parents=True, exist_ok=False)
    write_csv(output/'selected_faint_sources.csv', rows)
    x = -np.deg2rad((np.array([r['gal_l_deg'] for r in rows])+180)%360-180)
    y = np.deg2rad([r['gal_b_deg'] for r in rows])
    density = np.array([r['faint_psf_per_deg2'] for r in rows])
    fraction = np.array([r['faint_sample_psf_fraction'] for r in rows])
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), subplot_kw={'projection':'aitoff'}, layout='constrained')
    for ax, values, scale, title, caption in (
           (axes[0], density, LogNorm(*np.quantile(density,[.02,.98])), 'Retained faint point sources', 'Sources per usable deg²'),
           (axes[1], fraction, None, 'Fraction classified as point sources', 'Fraction of eligible faint g/r entries')):
        artist = ax.scatter(x, y, c=values, cmap='viridis', norm=scale, s=12, linewidths=0, rasterized=True)
        axes_map(ax, title)
        fig.colorbar(artist, ax=ax, shrink=.68, label=caption)
    fig.suptitle('Baseline catalogue sample at 22.5 < g₀ ≤ 23.5, r₀ ≤ 23.0 and g/r S/N ≥ 5')
    save(fig, output/'selected_faint_sky')
    picked = hashlib.sha256(''.join(r['source_sha256'] for r in rows).encode()).hexdigest()
    write_json(output/'manifest.json', dict(
        job=os.environ['SLURM_JOB_ID'], registration_sha256=sha(registration), raster_sha256=sha(raster_path),
        code_sha256=sha(Path(__file__)), sampled_source_hashes_sha256=picked, sample_nside=SAMPLE_NSIDE,
        samples=len(rows), excluded=dict(excluded),
        bands_by_region=dict(Counter(r['native_region'] for r in rows)),
        median_faint_psf_per_deg2=float(np.median(density)),
        median_faint_sample_psf_fraction=float(np.median(fraction)),
        outputs={p.name:sha(p) for p in output.iterdir()},
        scope='Nearest eligible field centre per sampled Galactic cell on represented WCS coverage. Counts and full usable core areas come from the same archived field masks before ownership partitions. Per-field samples need not be independent. Point-source fractions include classification and foreground variation. No stellar truth, completeness, or brightness threshold inference.'))
    print(dict(samples=len(rows), excluded=dict(excluded)), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output', type=Path)
    p.add_argument('raster', type=Path)
    args = p.parse_args()
    run(args.output, args.raster)
