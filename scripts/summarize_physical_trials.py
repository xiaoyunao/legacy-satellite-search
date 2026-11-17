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


def run(directory):
    paths=[directory/f'{name}.csv' for name in ('fresh_05','fresh_09')]
    rows=[r for p in paths for r in read_csv(p)]
    pairs=check_pairs(rows)
    groups=defaultdict(list)
    for arms in pairs.values():
        seed=arms['ls_base']
        groups[('all','all','all')].append(arms)
        groups[(seed['D_kpc'],'all','all')].append(arms)
        groups[tuple(seed[k] for k in ('D_kpc','rh_pc','expected_MV_proxy'))].append(arms)
    table=[]
    for (distance,radius,luminosity),batch in groups.items():
        for subset in ('all','without_preexisting_spatial_match'):
            cells=[arms for arms in batch if subset=='all' or not any(
                r['blank_spatial']=='True' for r in arms.values())]
            if not cells:
                continue
            for criterion in ('spatial','correct_mode_exists','blind_correct'):
                ref=np.array([arms['ps1'][criterion]=='True' for arms in cells])
                for arm in ('ls_base','ls_deep'):
                    ls=np.array([arms[arm][criterion]=='True' for arms in cells])
                    table.append(dict(D_kpc=distance,rh_pc=radius,expected_MV_proxy=luminosity,
                                      subset=subset,criterion=criterion,ls_arm=arm,n_pairs=len(cells),
                                      ls_detected=int(ls.sum()),ps1_detected=int(ref.sum()),
                                      ls_only=int((ls&~ref).sum()),ps1_only=int((~ls&ref).sum()),
                                      delta_p=float(ls.mean()-ref.mean())))
    write_csv(directory/'paired_summary.csv',table)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory',type=Path)
    run(p.parse_args().directory)
