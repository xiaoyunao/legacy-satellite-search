"""Read bounded DR11 products and construct an independent effective-area raster."""

import os
import re
from concurrent.futures import ProcessPoolExecutor
from contextlib import nullcontext
from pathlib import Path
from dataclasses import dataclass

import fitsio
import numpy as np
from astropy.wcs import WCS

RAD = np.pi / 180
REQUIRED = ('RA', 'DEC', 'RELEASE', 'BRICKID', 'OBJID', 'TYPE', 'MASKBITS')
REQUIRED += tuple(f'{key}_{band}' for band in 'GR' for key in
                  ('FLUX', 'FLUX_IVAR', 'MW_TRANSMISSION', 'NOBS', 'PSFDEPTH', 'PSFSIZE'))
OPTIONAL = ('FITBITS', 'REF_CAT', 'EBV', 'NOBS_I', 'FLUX_IVAR_I')
OPTIONAL += tuple(f'{key}_{b}' for b in 'GR' for key in
                  ('FRACMASKED', 'FRACFLUX', 'FRACIN', 'RCHISQ', 'ALLMASK'))


@dataclass
class Field:
    ra: float
    dec: float
    width: float
    step: float
    buffer: float = 102

    @property
    def n(self):
        return 32 * int(np.ceil((self.width * 60 + 2 * self.buffer) / self.step / 32))

    @property
    def limit(self):
        return self.n * self.step / 2

    def xy(self, ra, dec):
        cos = np.cos(self.dec * RAD)
        x = ((ra - self.ra + 180) % 360 - 180) * cos * 60
        y = (np.sin(dec * RAD) - np.sin(self.dec * RAD)) / cos / RAD * 60
        return x, y

    def sky(self, x, y):
        cos = np.cos(self.dec * RAD)
        ra = (self.ra + x / 60 / cos) % 360
        dec = np.arcsin(np.sin(self.dec * RAD) + y / 60 * RAD * cos) / RAD
        return ra, dec

    def pixel(self, x, y):
        ix = np.floor((x + self.limit) / self.step).astype(int)
        iy = np.floor((y + self.limit) / self.step).astype(int)
        return iy, ix

    def overlap(self, a, b, c, d):
        lo = ((a - self.ra + 180) % 360 - 180) * np.cos(self.dec * RAD) * 60
        hi = lo + ((b - a) % 360) * np.cos(self.dec * RAD) * 60
        _, ymin = self.xy(self.ra, c)
        _, ymax = self.xy(self.ra, d)
        return (lo < self.limit) & (hi > -self.limit) & (ymin < self.limit) & (ymax > -self.limit)


def read_table(path, cols):
    with fitsio.FITS(path) as f:
        return f[1].read(columns=list(cols), upper=True)


def sweeps(root, field):
    parts, files, options, headers = [], [], [], []
    for path in sorted((root / 'south/sweep/11.0').glob('sweep-*.fits')):
        m = re.fullmatch(r'sweep-(\d{3})([mp])(\d{3})-(\d{3})([mp])(\d{3})\.fits', path.name)
        if not m:
            continue
        a, s, c, b, t, d = m.groups()
        if not field.overlap(int(a), int(b), int(c) * (-1 if s == 'm' else 1),
                             int(d) * (-1 if t == 'm' else 1)):
            continue
        with fitsio.FITS(path) as f:
            hdu = f[1]
            cols = {k.upper(): k for k in hdu.get_colnames()}
            missing = set(REQUIRED) - cols.keys()
            if missing:
                raise ValueError(f'{path.name} lacks {sorted(missing)}')
            files.append(str(path.relative_to(root)))
            options.append(set(OPTIONAL) & cols.keys())
            headers.append({'path': files[-1], 'rows': hdu.get_nrows(),
                            'columns': sorted(cols), 'size_bytes': path.stat().st_size})
            pos = hdu.read(columns=[cols['RA'], cols['DEC']], upper=True)
            x, y = field.xy(pos['RA'], pos['DEC'])
            rows = np.flatnonzero((abs(x) < field.limit) & (abs(y) < field.limit))
            if rows.size:
                parts.append(hdu.read(columns=[cols[k] for k in (*REQUIRED, *sorted(options[-1]))],
                                      rows=rows, upper=True))
    if not parts:
        raise ValueError('No south sweep rows intersect the padded field')
    shared = set.intersection(*(set(p.dtype.names) for p in parts))
    names = [k for k in (*REQUIRED, *OPTIONAL) if k in shared]
    data = np.empty(sum(map(len, parts)), dtype=[(k, parts[0].dtype[k]) for k in names])
    off = 0
    for part in parts:
        for k in names:
            data[k][off:off + len(part)] = part[k]
        off += len(part)
    _, keep = np.unique(data[['RELEASE', 'BRICKID', 'OBJID']], return_index=True)
    info = {'sweeps': headers, 'missing_optional_by_file':
            {f: sorted(set(OPTIONAL) - opt) for f, opt in zip(files, options)},
            'duplicate_ids': len(data) - len(keep)}
    return data[np.sort(keep)], info


def load_bricks(root):
    path = root / 'south/survey-bricks-dr11-south.fits.gz'
    cols = ['BRICKNAME', 'RA', 'DEC', 'RA1', 'RA2', 'DEC1', 'DEC2', 'NOBS_G', 'NOBS_R',
            'PSFDEPTH_G', 'PSFDEPTH_R', 'PSFSIZE_G', 'PSFSIZE_R', 'EBV']
    with fitsio.FITS(path) as f:
        actual = {k.upper(): k for k in f[1].get_colnames()}
        absent = set(cols) - actual.keys()
        if absent:
            cols = [k for k in cols if k in actual]
        return f[1].read(columns=[actual[k] for k in cols], upper=True)


def _sample_brick(task):
    root, name, ix, iy, ras, decs, maskbits = task
    prefix = root / 'south/coadd' / name[:3] / name / f'legacysurvey-{name}'
    paths = [f'{prefix}-{kind}.fits.fz' for kind in ('maskbits', 'nexp-g', 'nexp-r')]
    if not all(Path(p).is_file() for p in paths):
        return name, ix, iy, None
    ra, dec = np.meshgrid(ras, decs)
    with fitsio.FITS(paths[0]) as f:
        image = f[1].read()
        header = dict(f[1].read_header())
    wcs_keys = ('CTYPE', 'CUNIT', 'CRPIX', 'CRVAL', 'CDELT', 'CD1_', 'CD2_', 'PC1_', 'PC2_', 'PV')
    wcs = WCS({k: v for k, v in header.items() if k.startswith(wcs_keys)}, naxis=2)
    xx, yy = wcs.world_to_pixel_values(ra, dec)
    xx, yy = np.rint(xx).astype(int), np.rint(yy).astype(int)
    inside = (xx >= 0) & (yy >= 0) & (xx < image.shape[1]) & (yy < image.shape[0])
    xx = np.clip(xx, 0, image.shape[1] - 1)
    yy = np.clip(yy, 0, image.shape[0] - 1)
    local = inside & ((image[yy, xx].astype(np.int64) & (maskbits | 1)) == 0)
    for path in paths[1:]:
        local &= fitsio.read(path, ext=1)[yy, xx] > 0
    return name, ix, iy, local


def make_area(root, field, bricks, maskbits, subsample, census=None, survey=None):
    """Sample g/r exposure and maskbits using primary brick boundaries and image WCS."""
    size = field.n * subsample
    cell = field.step / subsample
    axis = (np.arange(size) + 0.5) * cell - field.limit
    rafull, decfull = field.sky(axis, axis)
    good = np.zeros((size, size), dtype=bool)
    brick_ok = field.overlap(bricks['RA1'], bricks['RA2'], bricks['DEC1'], bricks['DEC2'])
    brick_ok &= (bricks['PSFDEPTH_G'] > 0) & (bricks['PSFDEPTH_R'] > 0)
    tasks = []
    for b in bricks[brick_ok]:
        name = b['BRICKNAME'].strip()
        dra = (rafull - b['RA1']) % 360
        ix = np.flatnonzero(dra < (b['RA2'] - b['RA1']) % 360)
        iy = np.flatnonzero((decfull >= b['DEC1']) & (decfull < b['DEC2']))
        if ix.size and iy.size:
            tasks.append((root, name, ix, iy, rafull[ix], decfull[iy], maskbits))
    absent = []
    seen = 0
    ncpu = min(len(tasks), int(os.getenv('SLURM_CPUS_PER_TASK', '1')))
    context = ProcessPoolExecutor(ncpu) if ncpu > 1 else nullcontext()
    with context as pool:
        for name, ix, iy, local in (pool.map(_sample_brick, tasks) if pool else map(_sample_brick, tasks)):
            if local is None:
                absent.append(name)
                continue
            if census is not None:
                local &= census.accept(*np.meshgrid(rafull[ix], decfull[iy]), survey)
            good[np.ix_(iy, ix)] = local
            seen += 1
    return good, {'area_bricks_read': seen, 'area_bricks_missing_products': absent,
                  'area_sample_arcmin': cell}


def select(data, field, coverage, config):
    g = data['TYPE'].astype('U')
    psf = np.char.strip(g) == 'PSF'
    mask = data['MASKBITS'].astype(np.int64)
    x, y = field.xy(data['RA'], data['DEC'])
    si, sj = sample_pixels(field, coverage, x, y)
    steps = {'raw': len(data)}
    ok = np.ones(len(data), dtype=bool)

    def cut(name, passed):
        ok[:] &= passed
        steps[name] = int(ok.sum())

    mags, errors = [], []
    for b, lim in zip('GR', ('g_max', 'r_max')):
        flux = data[f'FLUX_{b}'].astype(float)
        ivar = data[f'FLUX_IVAR_{b}'].astype(float)
        t = data[f'MW_TRANSMISSION_{b}'].astype(float)
        good = np.isfinite(flux) & (flux > 0) & np.isfinite(ivar) & (ivar > 0)
        good &= np.isfinite(t) & (t > 0) & (data[f'NOBS_{b}'] > 0)
        cut(f'valid_{b}', good)
        with np.errstate(divide='ignore', invalid='ignore'):
            snr = flux * np.sqrt(ivar)
            m = 22.5 - 2.5 * np.log10(flux / t)
            err = 2.5 / np.log(10) / snr
        cut(f'snr_{b}', snr >= config['min_snr'])
        cut(f'mag_{b}', m <= config[lim])
        mags.append(m)
        errors.append(err)
    for b in config['reject_maskbits']:
        cut(f'exclude_bit_{b}', (mask & (1 << b)) == 0)
    cut('area', coverage[si, sj])
    valid_gr = ok.copy()
    cut('psf', psf)
    fitbits = data['FITBITS'] if 'FITBITS' in data.dtype.names else None
    steps['selected_maskbit_counts'] = {str(b): int(np.sum(ok & ((mask & (1 << b)) != 0)))
                                        for b in range(20)}
    steps['selected_fitbit_counts'] = (None if fitbits is None else
        {str(b): int(np.sum(ok & ((fitbits & (1 << b)) != 0))) for b in (0, 4, 12)})
    steps['raw_maskbit_counts'] = {str(b): int(np.sum((mask & (1 << b)) != 0)) for b in range(20)}
    sample = np.column_stack([x[ok], y[ok], mags[0][ok], mags[1][ok], errors[0][ok], errors[1][ok]])
    return sample, steps, valid_gr, np.column_stack(mags), ok


def sample_pixels(field, coverage, x, y):
    sub = coverage.shape[0] // field.n
    cell = field.step / sub
    return (np.clip(((y + field.limit) / cell).astype(int), 0, len(coverage) - 1),
            np.clip(((x + field.limit) / cell).astype(int), 0, len(coverage) - 1))
