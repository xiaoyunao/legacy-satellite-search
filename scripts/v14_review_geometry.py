"""Diagnose close-position chains before defining final human-review units."""
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from ls_satsearch.expansion import unit
from ls_satsearch.run import read_csv, sha, write_json
from scripts.v14_catalog import chord


def run():
    source=Path('results/v14/production_integration/reconciled/provisional_positions.csv')
    checksum=sha(source);rows=read_csv(source)
    sky=unit([float(r['ra_deg']) for r in rows],[float(r['dec_deg']) for r in rows])
    parent=list(range(len(rows)))
    def find(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    pairs=cKDTree(sky).query_pairs(chord(5))
    for i,j in pairs:
        a,b=find(i),find(j);parent[max(a,b)]=min(a,b)
    groups=defaultdict(list)
    for i in range(len(rows)):groups[find(i)].append(i)
    largest=[]
    for indices in sorted(groups.values(),key=lambda g:(-len(g),rows[g[0]]['provisional_position_id']))[:20]:
        center=sky[indices].mean(0);center/=np.linalg.norm(center)
        members=[rows[i] for i in indices]
        record=dict(positions=len(indices),center_ra_deg=float(np.rad2deg(np.arctan2(center[1],center[0]))%360),
            center_dec_deg=float(np.rad2deg(np.arcsin(center[2]))),
            max_radius_arcmin=float(np.rad2deg(np.arccos(np.clip(sky[indices]@center,-1,1))).max()*60),
            cohorts=dict(Counter(r['cohorts'] for r in members)),
            position_ids=[r['provisional_position_id'] for r in members])
        for key in ('known_position_contexts','known_environment_contexts','extended_galaxy_contexts'):
            record[key]=sorted({r[key] for r in members if r[key]})
        largest.append(record)
    if sha(source)!=checksum:raise ValueError('Position snapshot changed during diagnosis')
    write_json(source.with_name('review_geometry_diagnostic.json'),dict(input_sha256=checksum,
        code_sha256=sha(Path(__file__)),positions=len(rows),diagnostic_link_arcmin=5,
        close_position_pairs=len(pairs),connected_components=len(groups),
        component_size_counts=dict(Counter(len(g) for g in groups.values())),largest_components=largest,
        final_review_units_defined=False,sampling_performed=False,
        scope='Aggregate metadata diagnostic only. Five-arcmin connected components can chain over tens of arcminutes; they are not physical objects or final review units. Retain constituents/environment and define review units before probability sampling; do not discard selected positions afterwards.'))
    print('REVIEW_GEOMETRY_DIAGNOSTIC',len(rows),len(groups),flush=True)


if __name__=='__main__':run()
