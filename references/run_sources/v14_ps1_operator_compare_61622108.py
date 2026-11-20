"""Aggregate same-cell DR2 versus blank native g measurements; no response claim."""
import csv
import json
import os
from pathlib import Path

import numpy as np
from astropy.io import fits
from scipy.spatial import cKDTree
from ls_satsearch.expansion import unit
from ls_satsearch.run import sha, write_csv, write_json


def quantiles(values):
    a = np.asarray(values, dtype=float)
    a = a[np.isfinite(a)]
    return dict(n=len(a), q16=float(np.quantile(a, .16)), median=float(np.median(a)),
                q84=float(np.quantile(a, .84))) if len(a) else dict(n=0)


def main():
    if not os.getenv('SLURM_JOB_ID'):
        raise RuntimeError('Native catalogue comparison requires Slurm')
    base = Path('results/v14/ps1_ipp/blank_pilot')
    proof = base / 'preflight_61621698.json'
    m = json.loads(proof.read_text())
    acquisition = base / 'acquisition.json'
    a = json.loads(acquisition.read_text())
    path = Path(m['raw_output_root']) / 'native_g.fpa.cmf'
    if sha(path) != m['artifacts'][path.name]['sha256']:
        raise ValueError('Native source table changed')
    with fits.open(path) as hd:
        native = hd['SkyChip.psf'].data.copy()
        header = hd[0].header.copy()
    references = []
    for p in a['reference_pages']:
        source = Path(p['path'])
        if sha(source) != p['sha256']:
            raise ValueError('Same-cell reference changed')
        with source.open() as stream:
            references.extend(csv.DictReader(stream))
    get = lambda name: np.array([float(r[name]) for r in references])
    nr, nd = native['RA_PSF'], native['DEC_PSF']
    native_valid = np.isfinite(nr + nd) & (abs(nd) <= 90) & (nr >= 0) & (nr < 360)
    ni = np.flatnonzero(native_valid)
    rr, rd = get('raStack'), get('decStack')
    ref_valid = np.isfinite(rr + rd) & (abs(rd) <= 90) & (rr >= 0) & (rr < 360)
    ri = np.flatnonzero(ref_valid)
    npoints, rpoints = unit(nr[ni], nd[ni]), unit(rr[ri], rd[ri])
    distance, near = cKDTree(npoints).query(rpoints)
    reverse = cKDTree(rpoints).query(npoints)[1]
    separation = np.rad2deg(2 * np.arcsin(np.clip(distance / 2, 0, 1))) * 3600
    mutual = (reverse[near] == np.arange(len(ri))) & (separation <= .8)
    matched = np.zeros(len(references), dtype=bool)
    matched[ri[mutual]] = True
    index = np.full(len(references), -1, dtype=int)
    index[ri[mutual]] = ni[near[mutual]]
    g = get('gPSFMag')
    valid_g = ref_valid & np.isfinite(g) & (g > 0) & (g < 35) & (get('gPSFFlux') > 0)
    quality_g = valid_g & (get('gpsfQfPerfect') >= .85)
    rows = []
    for selection, use in [('finite_positive_g', valid_g), ('g_qf_ge_0p85', quality_g)]:
        for lo, hi in zip([17, 20, 21, 22, 23, 24], [20, 21, 22, 23, 24, 25.5]):
            selected = use & (g >= lo) & (g < hi)
            both = selected & matched
            ii = index[both]
            calibrated = native['CAL_PSF_MAG'][ii]
            usable = np.isfinite(calibrated) & (calibrated > 0) & (calibrated < 35)
            residual = calibrated[usable] - g[both][usable]
            rows.append(dict(selection=selection, g_min=lo, g_max=hi,
                reference_rows=int(selected.sum()), matched_mutual_0p8arcsec=int(both.sum()),
                native_valid_cal_mag=int(usable.sum()),
                **{'native_minus_DR2_mag_' + k: v for k, v in quantiles(residual).items()}))
    out = base / 'single_g_comparison'
    out.mkdir(exist_ok=True)
    write_csv(out / 'by_magnitude.csv', rows)
    good = matched & quality_g
    ii = index[good]
    summary = dict(job=os.environ['SLURM_JOB_ID'], inputs={str(p): sha(p) for p in (proof, acquisition, path)},
        runner_sha256=sha(Path(__file__)), native_sources=len(native), native_astrometric_rows=int(native_valid.sum()),
        reference_rows=len(references), reference_g_positive_rows=int(valid_g.sum()),
        all_band_reference_rows_mutually_matched=int(matched.sum()),
        native_header=dict(PSF_OK=header.get('PSF_OK'), NPSFSTAR=header.get('NPSFSTAR'),
                           PSFMODEL=header.get('PSFMODEL'), FPA_ZP=header.get('FPA.ZP')),
        separations_arcsec=quantiles(separation[mutual]),
        native_cal_minus_inst_mag=quantiles(native['CAL_PSF_MAG'][ii] - native['PSF_INST_MAG'][ii]),
        native_vs_DR2_quality_g_mag=quantiles(native['CAL_PSF_MAG'][ii] - g[good]),
        native_g_image_ids=sorted({r['gstackImageID'] for r in references if float(r['gstackImageID']) > 0}),
        matching_rule='Mutual nearest sky coordinates, radius <= 0.8 arcsec; no fitted position or magnitude shift.',
        physical_PS1_response_validated=False, DR2_operator_equivalence_validated=False,
        scope='Descriptive real blank g comparison, using catalogued objects rather than injected stellar truth. '
              'Five-band detection, morphology/quality selection, faint blue populations, other backgrounds and '
              'DR2 configuration equivalence remain unvalidated. Multiple references can share source identities; '
              'row denominators are not an independent-star completeness estimate. No zero point fitted.')
    write_json(out / 'summary.json', summary)
    print(json.dumps({k: summary[k] for k in ('native_sources', 'reference_rows', 'all_band_reference_rows_mutually_matched',
                                              'native_vs_DR2_quality_g_mag')}))


if __name__ == '__main__':
    main()
