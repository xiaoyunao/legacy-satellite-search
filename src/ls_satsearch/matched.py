"""Compare independent DR11 and PS1 stack catalogs over the same valid sky."""

import argparse
import csv
import json
import os
from pathlib import Path
from time import monotonic

import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.wcs import WCS
from astropy_healpix import HEALPix
import numpy as np
from scipy.ndimage import map_coordinates
import yaml

from .data import load_bricks, sample_pixels, select
from .group_budget import evaluate
from .ps1_tiles import COLUMNS, design, RADIUS
from .run import (config_path, coverage_metrics, field_cache, read_csv, recovery,
                  runs_path, settings, sha, write_csv, write_json)
from .search import load_isochrone, scan

PS1_MODEL = 'isochrones/ps1/bressan2012/iso_a12.0_z0.00010.dat'
DUST = Path('/global/cfs/cdirs/cosmo/data/dust/v0_0/maps')
SURVEYS = ('ls_base', 'ls_deep', 'ps1')
DEST = Path('results/matched')


def joint_coverage(field, area, path):
    grid = HEALPix(nside=4096, order='ring')
    cell = 2 * field.limit / len(area)
    axis = (np.arange(len(area)) + .5) * cell - field.limit
    with fits.open(path, memmap=True) as f:
        hdu = f[1]
        if (hdu.header['NSIDE'], hdu.header['ORDERING'], hdu.header['INDXSCHM']) != (4096, 'RING', 'IMPLICIT'):
            raise ValueError('Unexpected PS1 mask geometry')
        bits = hdu.data['T'].reshape(-1)
        joint = area.copy()
        for start in range(0, len(axis), 96):
            part = joint[start:start+96]
            row, col = np.nonzero(part)
            ra, dec = field.sky(axis[col], axis[row+start])
            pix = grid.lonlat_to_healpix(ra*u.deg, dec*u.deg)
            part[row, col] &= (bits[pix].astype(np.int64) & 248) == 0
    return joint


def reddening(ra, dec):
    sky = SkyCoord(ra, dec, unit='deg').galactic
    lon, lat = sky.l.deg, sky.b.deg
    ebv = np.empty(len(ra))
    for pole, use in [('ngp', lat >= 0), ('sgp', lat < 0)]:
        if not use.any():
            continue
        with fits.open(DUST / f'SFD_dust_4096_{pole}.fits', memmap=True) as f:
            px, py = WCS(f[0].header).all_world2pix(lon[use], lat[use], 0)
            ebv[use] = map_coordinates(f[0].data, [py, px], order=1, mode='constant', cval=np.nan)
    return ebv


def ps1_measurements(spec, matched, directory):
    manifest = json.loads((directory / 'manifest.json').read_text())
    _, centers = design(spec, matched)
    tiles = {(p['ra_deg'], p['dec_deg'], p['radius_deg']) for p in manifest['pages']}
    if (tiles != {(ra,dec,RADIUS) for ra,dec in centers}
            or manifest['matched_config_sha256'] != sha(config_path('matched.yaml'))):
        raise ValueError('PS1 input does not cover the frozen field and buffer')
    rows, seen = [], set()
    columns = [key for key in COLUMNS if key not in ('objID', 'primaryDetection')]
    for page in manifest['pages']:
        path = directory / page['path']
        if sha(path) != page['sha256']:
            raise ValueError(f'PS1 page failed its checksum: {path.name}')
        with path.open(encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                ident = row['objID']
                if ident in seen or row['primaryDetection'] not in ('1', 'true', 'True'):
                    continue
                seen.add(ident)
                rows.append(tuple(float(row[key] or 'nan') for key in columns))
    return np.asarray(rows, dtype=float).reshape(-1, len(columns)), manifest


def ps1_catalog(field, area, cfg, spec, matched, directory):
    rows, manifest = ps1_measurements(spec,matched,directory)
    ra, dec, g, r, ge, re, i, kron, ie = rows.T
    finite = np.isfinite([ra,dec,g,r,ge,re,i,kron,ie]).all(axis=0)
    limit = 2.5 / np.log(10) / cfg['min_snr']
    quality = (finite & (ge > 0) & (re > 0) & (ie > 0) & (ge <= limit) & (re <= limit) &
               (ie <= limit) & (g > 0) & (r > 0) & (i > 0) & (kron > 0))
    x, y = field.xy(ra[quality], dec[quality])
    use = (abs(x) < field.limit) & (abs(y) < field.limit)
    index = np.flatnonzero(quality)[use]
    x, y = x[use], y[use]
    in_area = area[sample_pixels(field, area, x, y)]
    psf = i[index] - kron[index] < .05
    ebv = reddening(ra[index], dec[index])
    g0, r0 = g[index] - 3.172*ebv, r[index] - 2.271*ebv
    accept = in_area & psf & np.isfinite(ebv) & (g0 <= cfg['g_max']) & (r0 <= cfg['r_max'])
    sample = np.column_stack([x,y,g0,r0,ge[index],re[index]])[accept]
    return sample, dict(unique_primary=len(seen), valid_gr_i=int(quality.sum()),
                        buffered_rows=int(use.sum()), area=int(in_area.sum()),
                        area_psf=int((in_area & psf).sum()), selected=len(sample)), manifest


def run(field_id):
    root,data_root,cfg = settings()
    matched = yaml.safe_load(config_path('matched.yaml').read_text())
    spec = next(s for s in matched['fields'] if s['id']==field_id)
    spec = dict(spec, width=matched['width_deg'], buffer_arcmin=matched['buffer_arcmin'])
    cfg.update(dm=[16.5,20.75,.25], radii_arcmin=matched['radii_arcmin'], methods=['A'],
               review_budgets_deg2=matched['review_budgets_deg2'])
    field, sources, ls_area, info = field_cache(root,data_root,spec,cfg,load_bricks(root))
    ps1_root = data_root/'resources/ps1'
    area = joint_coverage(field,ls_area,ps1_root/'ps1d_mask_v2.1.fits')
    effective,fraction = coverage_metrics(field,area,cfg)
    ls_effective,_ = coverage_metrics(field,ls_area,cfg)
    if effective <= 0:
        raise RuntimeError(f'No usable joint area for {field_id}')
    # The survey-specific catalogs never require a counterpart.
    for survey in SURVEYS:
        begin = monotonic()
        survey_cfg = cfg.copy()
        if survey in ('ls_deep', 'ps1'):
            for band in 'gr':
                survey_cfg[f'{band}_max'] += .5
        if survey == 'ps1':
            sample,cuts,ps1_inputs = ps1_catalog(field,area,survey_cfg,spec,matched,
                                                 ps1_root/'tiles-v3'/field_id)
            model_path = data_root/'resources'/PS1_MODEL
            bands = ('gP1','rP1')
            inputs = dict(acquisition=ps1_inputs, extinction_coefficients=[3.172,2.271],
                          morphology='iPSF-iKron < 0.05 with valid i and S/N >=5')
        else:
            sample,cuts,*_ = select(sources,field,area,survey_cfg)
            model_path = data_root/'resources'/cfg['isochrone']
            bands = ('g','r')
            inputs = info
        if not len(sample):
            raise RuntimeError(f'No {survey} sample in {field_id}')
        model = load_isochrone(model_path, bands=bands)
        summary = DEST/survey/'summary'/f'{field_id}-base'
        work = runs_path(data_root)/'matched'/survey/field_id
        for path in (summary,work):
            path.mkdir(exist_ok=True,parents=True)
        manifest = dict(field=spec,survey=survey,depth='base',config=survey_cfg, bands=bands,
                        release='PS1 DR2 stack' if survey=='ps1' else 'LS DR11 south',
                        area_deg2=effective, area_fraction=fraction,ls_area_deg2=ls_effective,
                        cutflow=cuts, inputs=inputs, model_sha256=sha(model_path),
                        matched_config_sha256=sha(config_path('matched.yaml')),
                        ps1_mask_sha256=sha(ps1_root/'ps1d_mask_v2.1.fits.gz'),
                        slurm_job_id=os.environ.get('SLURM_JOB_ID'), status='running')
        write_json(summary/'manifest.json',manifest)
        print(f'{field_id} {survey}: {len(sample)} stars, {effective:.3f} joint deg2',flush=True)
        np.save(work/'sample.npy',sample,allow_pickle=False)
        np.save(work/'coverage.npy',area,allow_pickle=False)
        raw,peaks,timing,_ = scan(sample,field,area,model,survey_cfg)
        write_csv(work/'raw_peaks.csv',raw)
        write_csv(summary/'deduplicated_peaks.csv',peaks)
        if spec.get('truth'):
            truth = next(b for b in read_csv(Path('references/benchmarks.csv')) if b['name']==spec['truth'])
            write_csv(summary/'recovery.csv',recovery(peaks,truth,field,area,survey_cfg,survey))
        write_json(summary/'manifest.json',dict(manifest,status='complete',timing=timing,
                   raw_peaks=len(raw),deduplicated_peaks=len(peaks),wall_seconds=monotonic()-begin))


def combine():
    matched = yaml.safe_load(config_path('matched.yaml').read_text())
    expected = {f['id'] for f in matched['fields']}
    if matched.get('coverage_preflight'):
        unusable = {row['name'] for row in read_csv(Path(matched['coverage_preflight']))
                    if row['usable']=='False'}
        expected -= {f['id'] for f in matched['fields'] if f.get('truth') in unusable}
    rows, recoveries = [], []
    for survey in SURVEYS:
        summary = DEST/survey/'summary'
        complete = {m['field']['id'] for p in summary.glob('*/manifest.json')
                    if (m:=json.loads(p.read_text()))['status']=='complete'}
        if complete != expected:
            raise ValueError(f'{survey} is missing completed fields: {sorted(expected-complete)}')
        output = DEST/survey/'groups'
        evaluate(summary,output)
        rows.extend(dict(survey=survey,**r) for r in read_csv(output/'sky_group_comparison.csv'))
        recoveries.extend(dict(survey=survey,**r) for r in read_csv(output/'sky_group_recovery.csv'))
    write_csv(DEST/'matched_survey_comparison.csv', rows)
    write_csv(DEST/'matched_survey_recovery.csv', recoveries)


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('field')
    field_id = parser.parse_args().field
    combine() if field_id=='combine' else run(field_id)
