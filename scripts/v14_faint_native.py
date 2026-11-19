"""Render the guard's faint stars while retaining the original response-star identities."""
from pathlib import Path

import numpy as np
import v13_native as native


original_render=native.render_tims


def render(*args,**kwargs):
    stage=original_render(*args,**kwargs)
    count=np.load(native.OUT/'injected_exposures.npy',allow_pickle=False)
    response=np.load(native.OUT/'truth.npy',allow_pickle=False)
    rendered=np.load(native.TRUTH,allow_pickle=False)
    if not np.array_equal(rendered[:len(response)],response):
        raise ValueError('Guard lost the original response-star ordering')
    np.save(native.OUT/'injected_exposures_all_rendered.npy',count,allow_pickle=False)
    np.save(native.OUT/'injected_exposures.npy',count[:len(response)],allow_pickle=False)
    return stage


if __name__=='__main__':
    if 'image-v14_faint_guard' not in str(native.OUT):raise ValueError('Guard driver outside its isolated namespace')
    native.TRUTH=Path(native.OUT)/'render_sources.npy'
    if not native.TRUTH.is_file():raise ValueError('Missing registered faint-source rendering table')
    native.runbrick.stage_tims=render
    native.runbrick.stage_srcs=native.source_positions
    raise SystemExit(native.runbrick.main())
