"""Summarize paired detection outcomes on a frozen physical pilot."""

import argparse
from collections import defaultdict
from pathlib import Path

import numpy as np

from ls_satsearch.run import read_csv, write_csv


SURVEYS = ('ls_base', 'ls_deep', 'ps1')


def check_pairs(rows):
    pairs=defaultdict(dict)
    for r in rows:
        key=(r['field'],int(r['trial']))
        arm=r['survey']
        if arm in pairs[key]:
            raise ValueError(f'Duplicate trial {key} for {arm}')
        pairs[key][arm]=r
    for key,arms in pairs.items():
        if set(arms)!=set(SURVEYS):
            raise ValueError(f'Incomplete paired trial {key}')
        for k in ('D_kpc','rh_pc','expected_MV_proxy','N_latent','N_in_valid_area'):
            if len({r[k] for r in arms.values()})!=1:
                raise ValueError(f'Mismatched truth {k} for pair {key}')
    return pairs


def run(directory, fields=('fresh_05','fresh_09'), compare_depth=False):
    paths=[directory/f'{name}.csv' for name in fields]
    rows=[r for p in paths for r in read_csv(p)]
    pairs=check_pairs(rows)
    groups=defaultdict(list)
    for arms in pairs.values():
        seed=arms['ls_base']
        groups[('all','all','all')].append(arms)
        groups[(seed['D_kpc'],'all','all')].append(arms)
        groups[tuple(seed[k] for k in ('D_kpc','rh_pc','expected_MV_proxy'))].append(arms)
    table=[]
    comparisons=[('ls_base','ps1'),('ls_deep','ps1')]
    if compare_depth:
        comparisons.append(('ls_deep','ls_base'))
    for (distance,radius,luminosity),batch in groups.items():
        for subset in ('all','without_preexisting_spatial_match'):
            cells=[arms for arms in batch if subset=='all' or not any(
                r['blank_spatial']=='True' for r in arms.values())]
            if not cells:
                continue
            for criterion in ('spatial','correct_mode_exists','blind_correct'):
                for arm,reference in comparisons:
                    ref=np.array([arms[reference][criterion]=='True' for arms in cells])
                    ls=np.array([arms[arm][criterion]=='True' for arms in cells])
                    row=dict(D_kpc=distance,rh_pc=radius,expected_MV_proxy=luminosity,
                             subset=subset,criterion=criterion,ls_arm=arm,n_pairs=len(cells),
                             ls_detected=int(ls.sum()))
                    reference_fields=(dict(reference=reference,reference_detected=int(ref.sum()),
                                           reference_only=int((~ls&ref).sum())) if compare_depth
                                      else dict(ps1_detected=int(ref.sum())))
                    row.update(reference_fields,ls_only=int((ls&~ref).sum()))
                    if not compare_depth:
                        row['ps1_only']=int((~ls&ref).sum())
                    row['delta_p']=float(ls.mean()-ref.mean())
                    table.append(row)
    write_csv(directory/'paired_summary.csv',table)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory',type=Path)
    p.add_argument('--fields',nargs='+',default=('fresh_05','fresh_09'))
    p.add_argument('--compare-depth',action='store_true')
    args=p.parse_args()
    run(args.directory,args.fields,args.compare_depth)
