"""Audit named imaging overlap proxies for a frozen expansion registry."""

import argparse
from pathlib import Path

import numpy as np
import yaml

from .data import Field
from .expansion import overlaps
from .run import write_csv


def audit(registry,settings,output):
    frozen=yaml.safe_load(registry.read_text())
    plan=yaml.safe_load(settings.read_text())
    rows=[]
    for s in frozen['fields']:
        f=Field(s['ra'],s['dec'],s['width'],1/6,buffer=0)
        span=np.linspace(-s['width']*30,s['width']*30,21)
        ra,dec=f.sky(*np.meshgrid(span,span))
        tests={k:overlaps(ra,dec,boxes) for k,boxes in plan['overlap_regions'].items()}
        rows.append(dict(field=s['id'],phase=s['phase'],census_survey=s['survey'],
                         proxy_area_deg2=s['proxy_area_deg2'],
                         hsc_nominal_intersection=tests['hsc_coarse'],
                         kids_nominal_intersection=tests['kids_coarse'],
                         rubin_dp1_nominal_intersection=tests['rubin_dp1_coarse'],
                         rubin_proxy_changed=tests['rubin_dp1_coarse']!=s['overlap_proxy']['rubin_dp1_coarse'],
                         unions_nominal_core_dec_overlap=bool(np.any(dec>=30)),
                         prior_satellite_search_mask='unknown',unions='unknown_exact',
                         rubin_post_dp1='unknown'))
    write_csv(output,rows)
    return rows


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('registry',type=Path)
    parser.add_argument('settings',type=Path)
    parser.add_argument('output',type=Path)
    a=parser.parse_args()
    audit(a.registry,a.settings,a.output)
