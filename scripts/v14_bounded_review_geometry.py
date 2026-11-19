"""Test bounded sky-only review packets on the existing aggregate snapshot."""
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from ls_satsearch.expansion import unit
from ls_satsearch.run import read_csv, sha, write_json
from scripts.v14_catalog import chord


def bounded_groups(points, keys, span_arcmin=5.):
    """Stable greedy complete-link packets; no distance/score/identity selection."""
    if len(set(keys)) != len(keys):
        raise ValueError('Position keys must be unique')
    if not len(keys):
        return []
    tree = cKDTree(points)
    limit = chord(span_arcmin)
    owner, groups = {}, []
    for i in sorted(range(len(keys)), key=lambda j: keys[j]):
        neighbors = tree.query_ball_point(points[i], limit)
        possible = sorted({owner[j] for j in neighbors if j in owner})
        target = next((g for g in possible
                       if np.all(np.linalg.norm(points[groups[g]]-points[i], axis=1) <= limit)), None)
        if target is None:
            target = len(groups)
            groups.append([])
        groups[target].append(i)
        owner[i] = target
    return groups


def run():
    root = Path('results/v14/production_integration/reconciled')
    source = root/'provisional_positions.csv'
    crosswalk = root/'frozen75_crosswalk.csv'
    checksums = {str(p): sha(p) for p in (source, crosswalk)}
    rows = read_csv(source)
    keys = [r['provisional_position_id'] for r in rows]
    points = unit([float(r['ra_deg']) for r in rows], [float(r['dec_deg']) for r in rows])
    groups = bounded_groups(points, keys)
    flattened = [i for group in groups for i in group]
    if sorted(flattened) != list(range(len(rows))):
        raise ValueError('Position lost or duplicated')
    diameter = []
    for g in groups:
        distance = np.linalg.norm(points[g][:,None,:]-points[g][None,:,:], axis=2).max()
        diameter.append(float(2*np.rad2deg(np.arcsin(np.clip(distance/2, 0, 1)))*60))
    if max(diameter, default=0) > 5+1e-8:
        raise ValueError('A review packet chains beyond the fixed span')
    frozen = read_csv(crosswalk)
    preserved = sum(r['provisional_position_id'] in set(keys) for r in frozen)
    if len(frozen) != 75 or preserved != 75 or any(r['human_grade'] for r in frozen):
        raise ValueError('Frozen75 identity or blank-grade invariant failed')
    if any(sha(Path(p)) != value for p,value in checksums.items()):
        raise ValueError('Input snapshot changed')
    write_json(root/'bounded_review_geometry_diagnostic.json', dict(
        inputs=checksums, code_sha256=sha(Path(__file__)), input_positions=len(rows),
        input_source_records=sum(int(r['source_records']) for r in rows),
        retained_positions=len(flattened), unique_positions=len(set(flattened)),
        sky_only_greedy_packets=len(groups), maximum_pairwise_span_arcmin=max(diameter, default=0),
        span_cap_arcmin=5, packet_size_counts=dict(Counter(map(len, groups))),
        largest_packet_positions=max(map(len, groups), default=0),
        original75_crosswalk_rows_retained=preserved, human_grades_unfilled=True,
        ordering='ascending immutable input provisional_position_id; first compatible existing complete-link packet',
        final_review_units_defined=False, sampling_performed=False,
        scope='Diagnostic on the existing provisional aggregate snapshot only. Every position and its unchanged source-record/mode linkage is retained, including incompatible distance hypotheses and known-environment responses. Bounded administrative packets prevent long connected chains; they are neither distinct physical systems nor statistically independent sky trials. Nearby positions can remain in different packets. Final production, grouping rule, certainty cases, strata and positive inclusion probabilities must be frozen before any final draw; no sampled position may be rejected afterwards for proximity.'))
    print(len(rows), 'positions;', len(groups), 'bounded packets; max span', max(diameter, default=0))


if __name__ == '__main__':
    run()
