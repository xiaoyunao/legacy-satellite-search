"""Guard the frozen operating point and the matched PS1 i-band selection."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from ls_satsearch.group_budget import evaluate
from ls_satsearch.run import read_csv, write_csv
from ls_satsearch.selection_response import ps1_select


class HoldoutTest(unittest.TestCase):
    def test_frozen_cut_does_not_refit_review_load(self):
        saved = Path('configs/v4/production.json')
        policy = json.loads(saved.read_text())
        with TemporaryDirectory() as temp:
            root = Path(temp)
            field = root/'summary'/'synthetic-base'
            field.mkdir(parents=True)
            (field/'manifest.json').write_text(json.dumps(dict(
                status='complete', field=dict(id='synthetic',role='pilot_eval'),depth='base',
                area_deg2=2,config=dict(policy['recipe'],**policy['limits']['base'],methods=['A']))))
            rows=[dict(method='A',branch='main',x=x,y=0,ra_deg=180+x/60,dec_deg=0,
                       dm=18.5,rh_arcmin=.5,score=v,rank=i+1)
                  for i,(x,v) in enumerate(((0,8),(5,7),(10,6.5),(15,6)))]
            write_csv(field/'deduplicated_peaks.csv',rows)
            evaluate(root/'summary',root/'out',apply=saved)
            result = {float(r['budget']):int(r['evaluation_sky_groups'])
                      for r in read_csv(root/'out/sky_group_comparison.csv')}
            self.assertEqual(result,{.1:2,.3:3})

    def test_ps1_i_snr_is_required(self):
        phot=np.array([[22.,21.5,21.2],[22.,21.5,21.2],[22.,21.5,np.nan]])
        err=np.array([[.1,.1,.1],[.1,.1,.35],[.1,.1,.1]])
        response=(np.array([0,30]),np.array([-np.inf,np.inf]),{(0,0):(1.,1.)})
        accept, stages = ps1_select(phot,err,dict(g_max=24,r_max=23.5,min_snr=5),
                                    response,np.random.default_rng(1))
        self.assertEqual(accept.tolist(),[True,False,False])
        self.assertEqual(stages['N_gr_i_snr'],1)


if __name__=='__main__':
    unittest.main()
