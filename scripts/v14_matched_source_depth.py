"""Measure matched-position LS/PS1 10-sigma noise proxies on real CCD backgrounds."""

import argparse
import csv
import json
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import yaml

from ls_satsearch.data import load_bricks, sample_pixels, select
from ls_satsearch.matched import reddening
from ls_satsearch.run import field_cache, read_csv, sha, write_csv, write_json
from scripts.v13_image_trials import match_to
from scripts.v14_production_deeper_replay import MATCHED, load_registration

PS1 = Path('results/v14/repeat_full/ps1_observing_conditions/manifest.json')
SITES = Path('configs/v14_repeat/image_fields.csv')
MIN_CELL_PAIRS = 12
CELL_ARCMIN = 5.


def ps1_sources(record, inputs):
    columns = ['raStack', 'decStack', 'iPSFMag', 'iKronMag']
    columns += [b + k for b in 'gr' for k in ('PSFMag', 'PSFFlux', 'PSFFluxErr', 'psfQfPerfect')]
    data, seen = [], set()
    for page in record['pages']:
        path = Path(page['path'])
        checksum = sha(path)
        if checksum != page['sha256']:
            raise ValueError('Accepted PS1 measurements changed')
        inputs[str(path)] = checksum
        with path.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            mapping = {key.lower(): key for key in reader.fieldnames}
            for row in reader:
                ident = row[mapping['objid']]
                if ident in seen or row[mapping['primarydetection']] not in ('1', 'true', 'True'):
                    continue
                seen.add(ident)
                data.append(tuple(float(row[mapping[k.lower()]] or 'nan') for k in columns))
    if len(seen) != record['unique_primary_sources']:
        raise ValueError('Canonical primary object counts changed')
    data = np.array(data, dtype=[(k, 'f8') for k in columns])
    ra, dec = data['raStack'], data['decStack']
    return data[np.isfinite(ra + dec) & (ra >= 0) & (ra < 360) & (abs(dec) <= 90)]


def q(values):
    return np.quantile(values, [.16, .5, .84]) if len(values) else [None] * 3


def measure(site, record, field, raw, area, cfg, deep, inputs):
    ps1 = ps1_sources(record, inputs)
    xy = np.column_stack(field.xy(ps1['raStack'], ps1['decStack']))
    origin = np.array(field.xy(float(site['ra_deg']), float(site['dec_deg'])))
    offset = xy - origin
    use = (np.hypot(*offset.T) <= 20) & area[sample_pixels(field, area, *xy.T)]
    ps1, offset = ps1[use], offset[use]
    locations = np.column_stack([ps1['raStack'], ps1['decStack']])
    xy_raw = np.column_stack(field.xy(raw['RA'], raw['DEC']))
    raw = raw[np.hypot(*(xy_raw - origin).T) <= 20.1]
    phot_cfg = dict(cfg, g_max=99., r_max=99., min_snr=0.)
    _, _, _, _, psf = select(raw, field, area, phot_cfg)
    _, _, _, _, base = select(raw, field, area, cfg)
    _, _, _, _, deeper = select(raw, field, area, deep)
    ls_sky = np.column_stack([raw['RA'], raw['DEC']])
    pairs = match_to(locations, ls_sky, .8, field)
    linked = pairs >= 0
    pos = pairs[linked]
    ps1, offset = ps1[linked], offset[linked]
    sources = raw[pos]
    ebv = reddening(ps1['raStack'], ps1['decStack'])
    ii, kr = ps1['iPSFMag'], ps1['iKronMag']
    point = (ii > 0) & (ii < 22) & (kr > 0) & (ii - kr < .05)
    core = dict(site=site['field'], primary_PS1_centres_in_LS_mask=len(pairs),
                matched_unique_LS=int(linked.sum()), matched_LS_gr_PSF=int(psf[pos].sum()),
                matched_LS_baseline=int(base[pos].sum()), matched_LS_deeper=int(deeper[pos].sum()),
                matched_PS1_i_point_proxy=int(point.sum()))
    bins = np.floor(offset / CELL_ARCMIN).astype(int)
    result, cells = [], []
    for band, coefficient in zip('gr', (3.172, 2.271)):
        b = band.upper()
        psfmag, flux, error, quality = (ps1[band + k] for k in ('PSFMag','PSFFlux','PSFFluxErr','psfQfPerfect'))
        with np.errstate(divide='ignore', invalid='ignore'):
            ps1_snr = flux / error
            ls_snr = sources[f'FLUX_{b}'] * np.sqrt(sources[f'FLUX_IVAR_{b}'])
            ls_m10 = 22.5 - 2.5 * np.log10(10. / np.sqrt(sources[f'FLUX_IVAR_{b}']))
            ls_m10 += 2.5 * np.log10(sources[f'MW_TRANSMISSION_{b}'])
            ps1_m10 = -2.5 * np.log10(10. * error / 3631.) - coefficient * ebv
            ls_psf_m10 = 22.5 - 2.5 * np.log10(10. / np.sqrt(sources[f'PSFDEPTH_{b}']))
            ls_psf_m10 += 2.5 * np.log10(sources[f'MW_TRANSMISSION_{b}'])
        accepted = (np.isfinite(ls_m10 + ps1_m10 + ls_psf_m10) & (flux > 0) & (error > 0)
                    & (quality >= .95) & (quality <= 1.01) & (psfmag > 0) & (psfmag < 40)
                    & (ps1_snr >= 5.) & (ps1_snr <= 20.) & (ls_snr >= 5.) & psf[pos])
        for group, chosen in (('LS_PSF', accepted), ('LS_PSF_and_PS1_i_point', accepted & point)):
            ls_q, ps_q = q(ls_m10[chosen]), q(ps1_m10[chosen])
            lo, mid, hi = q((ls_m10 - ps1_m10)[chosen])
            result.append(dict(site=site['field'], band=band, selection=group, pairs=int(chosen.sum()),
                LS_source_dereddened_m10_median=ls_q[1], PS1_source_dereddened_m10_median=ps_q[1],
                paired_LS_minus_PS1_m10_p16=lo, paired_LS_minus_PS1_m10_median=mid,
                paired_LS_minus_PS1_m10_p84=hi,
                paired_LS_PSFDEPTH_minus_PS1_source_m10_median=q((ls_psf_m10 - ps1_m10)[chosen])[1],
                baseline_selected_pairs=int((base[pos] & chosen).sum()),
                deeper_selected_pairs=int((deeper[pos] & chosen).sum())))
        for ix, iy in np.unique(bins[accepted], axis=0):
            selected = accepted & (bins[:, 0] == ix) & (bins[:, 1] == iy)
            if selected.sum() >= MIN_CELL_PAIRS:
                cells.append(dict(site=site['field'], band=band, east_arcmin=(ix + .5) * CELL_ARCMIN,
                    north_arcmin=(iy + .5) * CELL_ARCMIN, pairs=int(selected.sum()),
                    LS_minus_PS1_m10_median=q((ls_m10 - ps1_m10)[selected])[1]))
    return result, cells, core


def plot(cells, sites, path):
    fig, ax = plt.subplots(len(sites), 2, figsize=(8, 9), layout='constrained')
    scale = max(.5, np.quantile(np.abs([r['LS_minus_PS1_m10_median'] for r in cells]), .98))
    for i, site in enumerate(sites):
        for j, b in enumerate('gr'):
            rows = [r for r in cells if r['site'] == site['field'] and r['band'] == b]
            image = ax[i, j].scatter([r['east_arcmin'] for r in rows], [r['north_arcmin'] for r in rows],
                c=[r['LS_minus_PS1_m10_median'] for r in rows], cmap='RdBu_r', vmin=-scale, vmax=scale,
                marker='s', s=65)
            ax[i, j].set(xlim=(22, -22), ylim=(-22, 22), aspect='equal',
                         title=f"CCD background {i + 1}  ·  {b}", xlabel='East (arcmin)', ylabel='North (arcmin)')
    fig.colorbar(image, ax=ax, label='Paired LS − PS1 10σ source-noise magnitude')
    fig.suptitle(f'Dereddened native-passband depth proxies · cells with ≥{MIN_CELL_PAIRS} matched sources')
    fig.savefig(path, dpi=160)
    plt.close(fig)


def run(output):
    if not os.getenv('SLURM_JOB_ID'):
        raise RuntimeError('Use allocated compute CPUs')
    output.mkdir(parents=True, exist_ok=False)
    config, replay = load_registration()
    original = Path('results/v14/repeat_full/production_replay/registration.json')
    cfg = json.loads(original.read_text())['configuration']
    deep = replay['configuration']
    rows = {r['site']: r for r in json.loads(PS1.read_text())['fields']}
    specs = yaml.safe_load(MATCHED.read_text())['fields']
    root, data = (Path(os.environ[k]) for k in ('LS_DR11_ROOT', 'LS_SAT_DATA'))
    bricks = load_bricks(root, 'south')
    sites = read_csv(SITES)
    inputs = {str(p): sha(p) for p in (config, original, SITES, PS1, MATCHED)}
    depth, maps, counts = [], [], []
    for site in sites:
        spec = next(r for r in specs if r['id'] == site['background'])
        spec = dict(spec, width=replay['width_deg'], buffer_arcmin=replay['buffer_arcmin'], role='injection_control')
        field, raw, area, _ = field_cache(root, data, spec, cfg, bricks)
        result, cells, count = measure(site, rows[site['field']], field, raw, area, cfg, deep, inputs)
        depth.extend(result)
        maps.extend(cells)
        counts.append(count)
        print(count, flush=True)
    if not maps:
        raise ValueError('No supported cell across the three CCD backgrounds')
    write_csv(output / 'depth_summary.csv', depth)
    write_csv(output / 'depth_cells.csv', maps)
    write_csv(output / 'sample_counts.csv', counts)
    plot(maps, sites, output / 'matched_depth.png')
    write_json(output / 'manifest.json', dict(job=os.environ['SLURM_JOB_ID'], inputs=inputs,
        code_sha256=sha(Path(__file__)), outputs={p.name: sha(p) for p in output.iterdir()},
        scope='Matched real detections in the three South PS1 CCD backgrounds. LS and PS1 use the same S/N=10 and dereddened magnitude convention in their native passbands. The differences are conditional flux-error proxies, not background-only sensitivity, independent-sky coverage, source completeness, or calibrated physical LS−PS1 gain. Spatial cells are displayed only when supported by paired sources.'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    run(parser.parse_args().output)
