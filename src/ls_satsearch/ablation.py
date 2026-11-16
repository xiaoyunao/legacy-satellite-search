"""Replay first-pilot A template peaks with the revised branch and merge policy."""

import csv
import json
from pathlib import Path

import numpy as np

from .evaluate import thresholds
from .run import settings, write_csv
from .search import deduplicate


def read_a(path, raw=False):
    with path.open() as f:
        rows = [r for r in csv.DictReader(f) if r['method']=='A']
    if raw:
        for r in rows:
            for key in ('score','dm','x','y','rh_arcmin'):
                r[key]=float(r[key])
        return [r for r in deduplicate(rows) if r['branch']=='main']
    return [r for r in rows if r['branch']=='main']


def main():
    _,data,cfg=settings()
    root=Path('results/summary')
    output=[]
    for depth in ('base','deep'):
        pools={}
        for field in ('dev_ordinary','dev_deep','eval_ordinary','eval_deep'):
            run=f'{field}-{depth}'
            old_file=data/'runs'/run/'all_template_peaks.csv'
            new_file=root/run/'deduplicated_peaks.csv'
            for label,rows in [('continuous_replayed',read_a(old_file,True)),('segmented',read_a(new_file))]:
                pools.setdefault(label,{})[field]=rows
        total_area=sum(json.loads((root/f'{field}-{depth}'/'manifest.json').read_text())['area_deg2']
                       for field in ('dev_ordinary','dev_deep'))
        for label,fields in pools.items():
            dev=[r for name, rows in fields.items() if name.startswith('dev_') for r in rows]
            cuts=thresholds(dev,total_area,cfg['review_budgets_deg2'])
            for field,rows in fields.items():
                scores=np.array([float(r['score']) for r in rows])
                for (_,budget),(cutoff,_) in ((k,v) for k,v in cuts.items() if k[0]=='A'):
                    output.append(dict(depth=depth, locus=label, field=field, budget=budget,
                                       hypotheses=len(scores), score_p99=float(np.percentile(scores,99)),
                                       max_score=float(scores.max()), cutoff=cutoff,
                                       retained=int(np.count_nonzero(scores>=cutoff)) if cutoff is not None else 0))
    write_csv(root/'locus_empirical_ablation.csv',output)


if __name__=='__main__':
    main()
