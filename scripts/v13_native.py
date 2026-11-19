"""Add a shared artificial population at the calibrated CCD stage of LegacyPipe."""
import os
from pathlib import Path

import numpy as np
from legacypipe import runbrick
from tractor import NanoMaggies, PointSource, RaDecPos

OUT = Path(os.environ['LS13_NATIVE_DIR'])
TRUTH = Path(os.environ['LS13_TRUTH'])
read_tims = runbrick.stage_tims
detect = runbrick.stage_srcs


def render_tims(*args, **kwargs):
    stage = read_tims(*args, **kwargs)
    tims = stage['tims']
    print('Native exposure count', len(tims), flush=True)
    if not TRUTH.is_file():
        return stage
    table = np.load(TRUTH, allow_pickle=False)
    counts = np.zeros((len(table), 4), dtype=np.int16)
    bands = 'grzi'
    sources = [PointSource(RaDecPos(float(r['ra']), float(r['dec'])),
                          NanoMaggies(**{b: float(r[f'flux_{b}']) for b in bands}))
               for r in table]
    import zlib
    for tim in tims:
        dest = tim.getImage()
        model_image = np.zeros_like(dest)
        inverse_error = tim.getInvError()
        wcs = tim.getWcs()
        for i, source in enumerate(sources):
            x, y = wcs.positionToPixel(source.getPosition(), source)
            ix, iy = int(np.floor(x+.5)), int(np.floor(y+.5))
            if not (0 <= iy < dest.shape[0] and 0 <= ix < dest.shape[1]):
                continue
            model = source.getModelPatch(tim)
            if model is not None:
                model.addTo(model_image)
                counts[i, bands.index(tim.band)] += inverse_error[iy, ix] > 0
        camera = tim.imobj.get_camera(tim.primhdr)
        # The northern CP products are already in electrons/s. DECam uses ADU.
        electrons = (tim.imobj.exptime if camera in ('90prime','mosaic')
                     else tim.imobj.get_gain(tim.primhdr, tim.hdr))
        electron_per_nmgy = float(electrons) * tim.zpscale
        if not np.isfinite(electron_per_nmgy) or electron_per_nmgy <= 0:
            raise ValueError(f'Invalid electron conversion in {tim.name}')
        actual = (model_image != 0) & (inverse_error > 0)
        expected = np.clip(model_image[actual],0,None)*electron_per_nmgy
        exposure_key = zlib.crc32(tim.name.encode())
        rng = np.random.default_rng([int(os.environ.get('LS13_SHOT_SEED','483423')), exposure_key])
        shot_delta = (rng.poisson(expected)-expected)/electron_per_nmgy
        dest[actual] += model_image[actual]+shot_delta
        inverse_error[actual] = 1/np.sqrt(inverse_error[actual]**-2 + expected/electron_per_nmgy**2)
    np.save(OUT/'injected_exposures.npy', counts, allow_pickle=False)
    return stage


def source_positions(*args, **kwargs):
    stage = detect(*args, **kwargs)
    # The returned Tractor catalog includes initial detection plus reference input.
    table = stage['T']
    pos = np.column_stack((table.ra, table.dec))
    np.save(OUT/'initial_detection.npy', pos, allow_pickle=False)
    return stage


if __name__ == '__main__':
    runbrick.stage_tims = render_tims
    runbrick.stage_srcs = source_positions
    raise SystemExit(runbrick.main())
