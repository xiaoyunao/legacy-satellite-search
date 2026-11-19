import unittest
from pathlib import Path

from scripts.v14_catalog import bound_supplements,seed_signature


class CBindingTest(unittest.TestCase):
    def test_reused_group_label_does_not_transfer_fits_between_sources_or_modes(self):
        row=dict(field='field',channel='A_base',policy='A_base',budget='.3',
                 ra_deg='10',dec_deg='20',dm='19',rh_arcmin='.5',ranking='8')
        path=Path('results/v14/discovery/north/main/sky_group_candidates.csv')
        fit=('fit.csv',1,dict(ts=9))
        saved={'group':[(fit,str(path),{seed_signature(row)})]}
        self.assertEqual(bound_supplements(saved,path,'group',[row]),[fit])
        parsed=dict(row);parsed['score']=parsed.pop('ranking')
        self.assertEqual(bound_supplements(saved,path,'group',[parsed]),[fit])
        self.assertEqual(bound_supplements(saved,Path('other.csv'),'group',[row]),[])
        for change in (dict(dm='20'),dict(budget='.1'),dict(ra_deg='11')):
            with self.subTest(change=change):
                self.assertEqual(bound_supplements(saved,path,'group',[dict(row,**change)]),[])


if __name__=='__main__':unittest.main()
