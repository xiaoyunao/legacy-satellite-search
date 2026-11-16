"""Deterministic pilot-field selection using survey metadata and independent masks."""

import argparse
from pathlib import Path

import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy_healpix import HEALPix
import numpy as np
import yaml

from .data import Field, load_bricks, make_area
from .run import coverage_metrics, read_csv, settings, sha


class Census:
    def __init__(self, root):
        path = root / 'resources/census.fits'
        self.file = fits.open(path, memmap=True)
        hdu = self.file[1]
        hdr = hdu.header
        if (hdr['NSIDE'], hdr['ORDERING'].strip(), hdr['INDXSCHM'].strip()) != (4096, 'RING', 'IMPLICIT'):
            raise ValueError('Unexpected census map layout')
        self.grid = HEALPix(nside=4096, order='ring')
        self.bits = hdu.data['T'].reshape(-1)
        ref = yaml.safe_load((root / 'resources/read_config.yaml').read_text())
        self.bad = sum(ref['maskbits'][k] for k in ('ASSOC', 'STAR', 'EBV', 'DENSITY', 'FOOT'))
        if self.bad != 248:
            raise ValueError('Unexpected census mask convention')

    def accept(self, ra, dec, survey):
        ipix = self.grid.lonlat_to_healpix(ra * u.deg, dec * u.deg)
        bits = self.bits[ipix]
        in_survey = (bits & 3) == survey
        return in_survey & ((bits & self.bad) == 0)


def choose(root, data_root, cfg, output):
    census = Census(data_root)
    bricks = load_bricks(root)
    good = (bricks['EBV'] < .1) & (bricks['PSFDEPTH_G'] > 0) & (bricks['PSFDEPTH_R'] > 0)
    pool = bricks[good]
    sc = SkyCoord(pool['RA'], pool['DEC'], unit='deg')
    good = (np.abs(sc.galactic.b.deg) > 30) & (np.abs(pool['DEC']) < 63)
    central_bits = census.accept(pool['RA'], pool['DEC'], 3)
    rng = np.random.default_rng(cfg['seed'])
    baseline = yaml.safe_load(Path('configs/fields.yaml').read_text())
    fields = [f for f in baseline['fields'] if f['role'] not in ('pilot_dev', 'pilot_eval', 'deep_control')]
    known = read_csv(Path('references/benchmarks.csv'))
    known_sky = SkyCoord([float(p['ra_deg']) for p in known], [float(p['dec_deg']) for p in known], unit='deg')
    metric = pool['PSFDEPTH_G'] + pool['PSFDEPTH_R'] - .3 * (pool['PSFSIZE_G'] + pool['PSFSIZE_R'])
    ordinary, deep = np.percentile(metric[good & central_bits], [35, 70])
    masks = {'ordinary': (metric >= ordinary) & (metric < deep),
             'deep': metric >= deep}
    counts = {}
    for survey, role, layer, width in [(3, 'pilot_dev', 'ordinary', 2.7),
                                        (3, 'pilot_dev', 'deep', 2.7),
                                        (3, 'pilot_eval', 'ordinary', 2.7),
                                        (3, 'pilot_eval', 'deep', 2.7),
                                        (1, 'deep_control', 'deep', 2.)]:
        eligible = good & census.accept(pool['RA'], pool['DEC'], survey)
        eligible &= masks[layer] if survey == 3 else metric >= deep
        for index in rng.permutation(np.flatnonzero(eligible)):
            b = pool[index]
            center = sc[index]
            other = SkyCoord([p['ra'] for p in fields], [p['dec'] for p in fields], unit='deg')
            if min(center.separation(other).deg.min(), center.separation(known_sky).deg.min()) < 8:
                continue
            f = Field(float(b['RA']), float(b['DEC']), width, min(cfg['radii_arcmin']) / 3)
            span = np.linspace(-width * 30, width * 30, 17)
            ra, dec = f.sky(*np.meshgrid(span, span))
            if float(np.mean(census.accept(ra, dec, survey))) < .96:
                continue
            in_box = f.overlap(bricks['RA1'], bricks['RA2'], bricks['DEC1'], bricks['DEC2'])
            x, y = f.xy(bricks['RA'], bricks['DEC'])
            inner = in_box & (abs(x) < width * 30) & (abs(y) < width * 30)
            if not inner.any() or np.max(bricks['EBV'][inner]) >= .10:
                continue
            area, _ = make_area(root, f, bricks, sum(1 << bit for bit in cfg['reject_maskbits']),
                                cfg['coverage_subdivision'], census, survey)
            area_deg2, fraction = coverage_metrics(f, area, cfg)
            if fraction < .85:
                continue
            ident = role.replace('pilot_', '') + '_' + layer if survey == 3 else 'des_control'
            fields.append(dict(id=ident, role=role, layer=layer, survey=survey, ra=f.ra, dec=f.dec,
                               width=width, effective_area_deg2=area_deg2, effective_fraction=fraction,
                               center_brick_g5=float(b['PSFDEPTH_G']), center_brick_r5=float(b['PSFDEPTH_R']),
                               center_brick_g_seeing=float(b['PSFSIZE_G']), max_inner_brick_ebv=float(
                                   np.max(bricks['EBV'][inner])), other_search_overlap='unknown'))
            counts[ident] = area_deg2
            print(f'{ident}: {f.ra:.5f}, {f.dec:.5f}; {area_deg2:.3f} deg2', flush=True)
            break
        else:
            raise RuntimeError(f'No eligible field found for {role}/{layer}')
    record = dict(selection_seed=cfg['seed'], census_sha256=sha(data_root / 'resources/census.fits.gz'),
                  source_commit='1a02f50d25cac74c02ddba8401a5af20aa2db4fe',
                  selection='Seeded eligible brick centers, different sky patches; >=85% gr and census effective '
                            'area, inner brick EBV<0.10, |b_center|>30; depth and seeing proxies from brick summary',
                  other_search_overlap='unknown for HSC, UNIONS, KiDS and Rubin',
                  fields=fields)
    temp = output.with_suffix('.tmp')
    temp.write_text(yaml.safe_dump(record, sort_keys=False))
    temp.replace(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    choose(*settings(), args.output)
