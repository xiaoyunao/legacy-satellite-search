"""Check extended-galaxy context at both discovery and C-refitted centres."""
import os
from pathlib import Path

import fitsio
import numpy as np

from ls_satsearch.run import read_csv,sha,write_csv,write_json
from scripts.v13_context import annotate


def positions(case, modes):
    rows=[dict(case_id=case['case_id'],cohort=case['cohort'],position_type='discovery',
               mode_rank='',ra_deg=case['ra_deg'],dec_deg=case['dec_deg'],dm=case['highest_dm'])]
    rows.extend(dict(case_id=case['case_id'],cohort=case['cohort'],position_type='C_refit',
                     mode_rank=m['rank'],ra_deg=m['fit_ra_deg'],dec_deg=m['fit_dec_deg'],dm=m['fit_dm'])
                for m in modes if m['fit_status']=='complete')
    return rows


def run():
    root=Path(os.environ['LS_DR11_ROOT']);out=Path('results/v14/shortlist')
    cases=read_csv(out/'cases.csv');environments=read_csv(Path('configs/v13/known_environment.csv'))
    rows=[];inputs={}
    for region in ('north','south'):
        path=root/'masking'/f'SGA2025-ellipse-v1.6-dr11-{region}.kd.fits'
        with fitsio.FITS(path) as f:
            galaxies=f[1].read(columns=['ra','dec','pa','ba','diam','ref_id','ref_cat'],upper=True)
        valid=np.isfinite(np.column_stack([galaxies[k] for k in ('RA','DEC','PA','BA','DIAM')])).all(axis=1)
        valid &= (galaxies['DIAM']>0)&(galaxies['BA']>0)&(galaxies['BA']<=1)&(galaxies['PA']>=0)
        galaxies=galaxies[valid]
        names=np.char.add(np.char.strip(galaxies['REF_CAT'].astype(str)),np.char.add(':',galaxies['REF_ID'].astype(str)))
        pts=[]
        for case in cases:
            if ('north' if case['cohort'].startswith('north') else 'south')!=region:continue
            modes=out/'cases'/case['case_id']/'review_modes.csv'
            if not modes.is_file():modes=out/'cached_cases'/case['case_id']/'review_modes.csv'
            pts.extend(positions(case,read_csv(modes) if modes.is_file() else []))
        rows.extend(annotate(pts,galaxies,names,environments));inputs[region]=sha(path)
    write_csv(out/'postfit_context.csv',rows)
    write_json(out/'context_manifest.json',dict(job=os.getenv('SLURM_JOB_ID'),inputs=inputs,
        discovery_centres=sum(r['position_type']=='discovery' for r in rows),
        fitted_centres=sum(r['position_type']=='C_refit' for r in rows),
        scope='Context annotations only. A C fit can move into an extended-galaxy ellipse even when its discovery centre was outside. Keep this identity key separate from blinded grading. No discovery cut, physical membership or automatic evidence promotion.'))


if __name__=='__main__':run()
