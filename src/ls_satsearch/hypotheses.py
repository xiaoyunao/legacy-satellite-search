"""Distance branches and non-destructive association of retained peaks."""

import numpy as np

BRANCHES = ('near', 'main', 'far')


def template_branch(dm):
    """Assign grid nodes from mu=16.50 through 20.75 to the main search."""
    if dm < 16.5:
        return 'near'
    if dm <= 20.75:
        return 'main'
    return 'far'


def truth_branch(distance):
    if distance < 20:
        return 'near'
    if distance <= 150:
        return 'main'
    return 'far'


def group_candidates(rows):
    """Assign deterministic sky-review groups while retaining every hypothesis."""
    anchors = []
    for row in sorted(rows, key=lambda r: (
            r['field_id'], float(r['x']), float(r['y']), r['branch'], r['method'], r['depth'])):
        xy = np.array([float(row['x']), float(row['y'])])
        radius = float(row['rh_arcmin'])
        matches = [(np.linalg.norm(xy - pos), gid) for field, pos, rh, gid in anchors
                   if field == row['field_id'] and np.linalg.norm(xy - pos) <= max(1., min(radius, rh))]
        if matches:
            _, gid = min(matches)
        else:
            gid = f"{row['field_id']}-{len(anchors) + 1:03d}"
            anchors.append((row['field_id'], xy, radius, gid))
        row['candidate_group_id'] = gid
