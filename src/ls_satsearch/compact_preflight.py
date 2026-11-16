"""Measure joint LS–PS1 aperture coverage before requesting PS1 photometry."""

from pathlib import Path

import yaml

from .data import load_bricks, make_area
from .matched import joint_coverage
from .ps1_tiles import design
from .run import config_path, coverage_metrics, read_csv, recovery, settings, write_csv


def main():
    root,data,cfg = settings()
    matched = yaml.safe_load(config_path('matched.yaml').read_text())
    controls = yaml.safe_load(config_path('compact_controls.yaml').read_text())['fields']
    cfg = dict(cfg,radii_arcmin=matched['radii_arcmin'])
    mask = data/'resources/ps1/ps1d_mask_v2.1.fits'
    truths = {r['name']:r for r in read_csv(Path('references/benchmarks.csv'))}
    bricks = load_bricks(root)
    results = []
    for spec in controls:
        field,_ = design(spec,matched)
        ls_area,_ = make_area(root,field,bricks,sum(1<<bit for bit in cfg['reject_maskbits']),
                              cfg['coverage_subdivision'])
        joint = joint_coverage(field,ls_area,mask)
        truth = truths[spec['truth']]
        r = recovery([],truth,field,joint,cfg,'joint')[0]
        results.append(dict(name=spec['truth'],ls_deg2=coverage_metrics(field,ls_area,cfg)[0],
                            joint_deg2=coverage_metrics(field,joint,cfg)[0],
                            joint_core_fraction=r['core_valid_fraction'],
                            joint_off_fraction=r['off_valid_fraction'],usable=r['covered'],
                            scale_below_grid=r['scale_below_grid']))
    write_csv(Path('results/compact_coverage.csv'),results)


if __name__ == '__main__':
    main()
