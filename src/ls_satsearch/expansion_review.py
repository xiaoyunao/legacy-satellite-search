"""Run the existing C reviewer and add bounded, source-independent mask diagnostics."""

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from .review import review_sky_groups
from .run import field_cache, read_csv, settings, write_csv


def mask_metrics(field,mask,x,y):
    scale = 2*field.limit/len(mask)
    radius = 6.
    axis = (np.arange(len(mask))+.5)*scale-field.limit
    i,j = np.flatnonzero(abs(axis-y)<=radius),np.flatnonzero(abs(axis-x)<=radius)
    distances = np.hypot(axis[i,None]-y,axis[None,j]-x)
    inside = distances<radius
    lost = distances[(~mask[np.ix_(i,j)])&inside]
    return dict(mask_invalid_fraction_in_6arcmin=(len(lost)/int(inside.sum())),
                nearest_mask_hole_arcmin=float(lost.min()) if len(lost) else None)


def contact_sheets(groups,output):
    for start in range(0,len(groups),8):
        subset = groups[start:start+8]
        w,h = 594,237
        grid = Image.new('RGB',(2*w,h*((len(subset)+1)//2)), 'white')
        label = ImageDraw.Draw(grid)
        for i,r in enumerate(subset):
            x,y = (i%2)*w,(i//2)*h
            label.text((x+3,y+2),f"{r['group_id']} · rank {r['best_peak_rank']}",fill='black')
            if r['best_peak_rank']:
                label_path = f"candidate-main-A-{r['best_peak_rank']}-images.png"
                path = Path('results/figures')/f"{r['field']}-base"/label_path
                if path.exists():
                    with Image.open(path) as im:
                        im.thumbnail((w-8,h-23))
                        grid.paste(im,(x+3,y+20))
        grid.save(output/f'contact-{start//8+1:02d}.png',optimize=True)


def main():
    output = Path('results/holdout')
    table = output/'sky_group_candidates.csv'
    review_sky_groups(table,'A_base',.3)
    groups = read_csv(output/'group_review_summary.csv')
    mode_table = read_csv(output/'group_review_modes.csv')
    fits = {(r['candidate_group_id'],r['rank']):r for r in mode_table}
    root,data,cfg = settings()
    diagnostics = []
    fields = sorted({r['group_id'].split('-')[0] for r in groups})
    for name in fields:
        manifest = json.loads((Path('results/summary')/f'{name}-base'/'manifest.json').read_text())
        field,_,mask,_ = field_cache(root,data,manifest['field'],cfg,None)
        for r in groups:
            if r['group_id'].split('-')[0]!=name:
                continue
            best = fits.get((r['group_id'],r['best_peak_rank']),{})
            geom = {}
            known = False
            if best:
                x,y = field.xy(float(best['fit_ra_deg']),float(best['fit_dec_deg']))
                geom = mask_metrics(field,mask,x,y)
                if best['nearest_known_arcmin']:
                    known = float(best['nearest_known_arcmin']) <= max(2.,float(best['seed_rh_arcmin']))
            nearby = geom.get('nearest_mask_hole_arcmin')
            diagnostics.append(dict(r,field=name,phase=manifest['field']['phase'],
                                    known_catalog_nearby=known,near_mask_hole_2arcmin=(
                                        nearby is not None and nearby<=2),**geom))
    write_csv(output/'expansion_group_diagnostics.csv',diagnostics,
              keys=('group_id','field','phase','review_status'))
    contact_sheets(diagnostics,output)


if __name__=='__main__':
    main()
