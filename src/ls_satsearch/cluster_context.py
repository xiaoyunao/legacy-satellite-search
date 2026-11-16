"""Annotate the spatial context of candidate C fits with classical clusters."""

import argparse
from pathlib import Path

from astropy.coordinates import SkyCoord
from astropy import units as u
import numpy as np

from .run import read_csv, sha, write_csv


HARRIS_URL = 'https://physics.mcmaster.ca/~harris/mwgc.dat'
HARRIS_SHA = 'b457a690adc422fb2e8e05a23e1de50b62d1d5ac10dce99963c956c1b17ca658'


def audit(catalogue, mode_files, output):
    if sha(catalogue) != HARRIS_SHA:
        raise ValueError('Expected the published Harris 1996 catalog, December 2010 edition')
    lines = catalogue.read_text(encoding='latin-1').splitlines()
    first = next(i for i,line in enumerate(lines) if 'ID        Name' in line)
    end = next(i for i,line in enumerate(lines[first:],first) if 'Part II:' in line)
    clusters = [(line[:11].strip(), line[25:].split()) for line in lines[first+1:end]
                if len(line[25:].split())==13]
    if len(clusters)!=157:
        raise ValueError('Unexpected length of Harris catalog Part I')
    positions = SkyCoord([' '.join(r[:3]) for _,r in clusters],[' '.join(r[3:6]) for _,r in clusters],
                         unit=(u.hourangle,u.deg))
    rows = []
    for modes in mode_files:
        best = {}
        for r in read_csv(modes):
            if r['fit_status']!='complete':
                continue
            key = r['candidate_group_id']
            if key not in best or float(r['ts'])>float(best[key]['ts']):
                best[key] = r
        for key,r in best.items():
            pos = SkyCoord(float(r['fit_ra_deg']),float(r['fit_dec_deg']),unit='deg')
            sep = pos.separation(positions).arcmin
            i = int(sep.argmin())
            name, details = clusters[i]
            dm = 5*np.log10(float(details[8]))+10
            rows.append(dict(group_id=key,rank=r['rank'],nearest_harris_2010=name,
                             separation_arcmin=sep[i],cluster_dm=dm,fit_dm=float(r['fit_dm']),
                             in_review_aperture=sep[i]<=max(2.,3*float(r['fit_rh_arcmin'])),
                             input_url=HARRIS_URL,input_sha256=HARRIS_SHA))
    write_csv(output,rows)


if __name__=='__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('catalogue',type=Path)
    p.add_argument('output',type=Path)
    p.add_argument('modes',nargs='+',type=Path)
    args = p.parse_args()
    audit(args.catalogue,args.modes,args.output)
