"""Inventory original hypotheses and provisionally reconcile compatible sky detections."""
from collections import Counter
import hashlib
import json
import os
import re
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree
import yaml

from ls_satsearch.data import regional_primary
from ls_satsearch.expansion import unit
from ls_satsearch.run import read_csv, sha, write_csv, write_json


def number(*values):
    for value in values:
        try:
            answer = float(value)
        except (TypeError, ValueError):
            continue
        if np.isfinite(answer):
            return answer
    return None


def seed_signature(row):
    """Bind a C shard to the exact discovery hypotheses, not a reused group label."""
    return (row.get('field'),row.get('channel'),row.get('policy'),
            *(number(row.get(k)) for k in ('budget','ra_deg','dec_deg','dm','rh_arcmin')),
            number(row.get('ranking'),row.get('score')))


def bound_supplements(supplements, path, group, rows):
    current={seed_signature(r) for r in rows}
    return [record for record,source,seeds in supplements.get(group, [])
            if source==str(path) and seeds==current]


def load_modes(paths):
    detections, all_modes = [], []
    supplement_paths = sorted(Path('results/v14/candidate_review').glob('*/*/*/group_review_modes.csv'))
    supplements = {}
    for file in supplement_paths:
        provenance=file.with_name('provenance.json')
        selection=file.with_name('review_modes.csv')
        if not provenance.is_file() or not selection.is_file():
            continue
        saved=json.loads(provenance.read_text())
        if not saved.get('input'):
            # Standalone follow-up packets remain in their own frozen ledger;
            # an unbound packet cannot certify a production discovery record.
            continue
        if saved.get('selection_sha256') and saved['selection_sha256']!=sha(selection):
            raise ValueError('C selection changed after fitting: '+str(selection))
        seeds={}
        for row in read_csv(selection):
            seeds.setdefault(row['group_id'],set()).add(seed_signature(row))
        for i, row in enumerate(read_csv(file), 1):
            group = row['candidate_group_id']
            supplements.setdefault(group, []).append(((file,i,row),saved['input'],seeds.get(group,set())))
    for path in paths:
        fit_path = path.with_name('group_review_summary.csv')
        fits = {r['group_id']: r for r in read_csv(fit_path)} if fit_path.is_file() else {}
        fit_modes_path = path.with_name('group_review_modes.csv')
        model_modes = read_csv(fit_modes_path) if fit_modes_path.is_file() else []
        groups = {}
        for i, r in enumerate(read_csv(path), 1):
            ra, dec = number(r.get('ra_deg'), r.get('fit_ra_deg')), number(r.get('dec_deg'), r.get('fit_dec_deg'))
            if ra is None or dec is None:
                continue
            group = r.get('group_id') or r.get('candidate_id') or f'{r.get("field", "unknown")}-{i:05d}'
            key = f'{path.parent}:{group}'
            common = dict(record_id=f'{path}:{i}', detection_id=key, group_id=group, input=str(path),
                          cohort=path.parent.parent.name if path.parent.name in ('main','near','far') else None,
                          field=r.get('field_id') or r.get('field'), role=r.get('role'),
                          branch=r.get('branch') or (path.parent.name if path.parent.name in ('main','near','far') else None),
                          channel=r.get('channel') or '/'.join(filter(None, (r.get('method'), r.get('depth')))),
                          policy=r.get('policy'), budget=number(r.get('budget'), r.get('budget_per_deg2')),
                          ra_deg=ra, dec_deg=dec, dm=number(r.get('dm'), r.get('best_dm')),
                          rh_arcmin=number(r.get('rh_arcmin'), r.get('best_rh')),
                          score=number(r.get('score'),r.get('ranking')), rank=number(r.get('peak_rank'),r.get('rank')),
                          representative=r.get('representative','True') == 'True', source_kind='blind_peak',
                          raw_peak_id=r.get('raw_peak_id'), n_on=number(r.get('n_on')),
                          n_off=number(r.get('n_off')), area_on_arcmin2=number(r.get('area_on_arcmin2')),
                          area_off_arcmin2=number(r.get('area_off_arcmin2')))
            candidates = groups.setdefault(key, [])
            all_modes.append(common)
            candidates.append(common)
            if 'fit_ra_deg' in r or 'C_ts' in r:
                fits.setdefault(group, r)
        for key, rows in groups.items():
            main = next((r for r in rows if r['representative']), rows[0])
            fit = fits.get(main['group_id'], {})
            modes = sorted({r['dm'] for r in rows if r['dm'] is not None})
            extra = bound_supplements(supplements,path,main['group_id'],rows)
            successful = [r for _, _, r in extra if r['fit_status']=='complete']
            if successful:
                best = max(successful,key=lambda r: float(r['ts']))
                if number(fit.get('best_ts'), fit.get('C_ts'), -1) < float(best['ts']):
                    fit = dict(fit, best_ts=best['ts'], best_dm=best['fit_dm'],
                               best_ts_without_top3=best['C_refit_TS_without_top3'],
                               best_rh=best['fit_rh_arcmin'], review_status='C_completed_visual_pending')
                modes = sorted(set(modes + [float(r['fit_dm']) for r in successful]))
            fitted = number(fit.get('best_dm'), fit.get('C_fit_dm'))
            if fitted is not None:
                modes = sorted(set(modes + [fitted]))
            detections.append(dict(main, modes=modes, c_ts=number(fit.get('best_ts'), fit.get('C_ts')),
                                   c_without_top3=number(fit.get('best_ts_without_top3'), fit.get('C_refit_TS_without_top3')),
                                   image_review=fit.get('review_status'), environment=fit.get('known_context_name'),
                                   best_fit_rh=number(fit.get('best_rh'))))
        all_fits = [(fit_modes_path,i,fit) for i,fit in enumerate(model_modes,1)]
        all_fits.extend(r for key,rows in groups.items()
                        for r in bound_supplements(supplements,path,rows[0]['group_id'],rows))
        for fit_origin, i, fit in all_fits:
            group = fit['candidate_group_id']
            key = f'{path.parent}:{group}'
            if key not in groups:
                continue
            all_modes.append(dict(record_id=f'{fit_origin}:{i}', detection_id=key, group_id=group,
                                  input=str(fit_origin), source_kind='C_followup', branch=fit.get('branch'),
                                  field=fit.get('field'), ra_deg=number(fit.get('fit_ra_deg')),
                                  dec_deg=number(fit.get('fit_dec_deg')), dm=number(fit.get('fit_dm')),
                                  rh_arcmin=number(fit.get('fit_rh_arcmin')),
                                  c_ts=number(fit.get('ts')), c_without_top3=number(fit.get('C_refit_TS_without_top3')),
                                  effective_members=number(fit.get('effective_members')),
                                  image_centre_complete=fit.get('image_centre_complete'), fit_status=fit.get('fit_status')))
    return detections, all_modes


def chord(arcmin):
    return 2 * np.sin(np.deg2rad(arcmin / 120))


def reconcile(detections):
    points = unit([r['ra_deg'] for r in detections], [r['dec_deg'] for r in detections])
    tree = cKDTree(points)
    proposed, links = [], {}
    for i,j in sorted(tree.query_pairs(chord(5.))):
        a,b = detections[i],detections[j]
        sep = 2 * np.rad2deg(np.arcsin(np.linalg.norm(points[i]-points[j])/2)) * 60
        distance = min((abs(x-y) for x in a['modes'] for y in b['modes']), default=None)
        size = min(a['rh_arcmin'] or .5,b['rh_arcmin'] or .5)
        scale = max(a['rh_arcmin'] or .5,b['rh_arcmin'] or .5) / max(.15,size)
        # Allow some astrometric/mode scatter but require a shared spatial scale.
        compatible = (sep <= max(.85, size) and scale <= 4
                      and distance is not None and distance <= .75)
        links[i,j] = compatible
        proposed.append(dict(i=i,j=j,arcmin=float(sep),closest_dm=distance,scale_ratio=scale,
                             jointly_compatible=bool(compatible)))
    adjacency = {i:set() for i in range(len(detections))}
    for (i,j), fit in links.items():
        if fit:
            adjacency[i].add(j)
            adjacency[j].add(i)
    seen, groups = set(), []
    order = sorted(range(len(detections)), key=lambda i: (-(detections[i]['score'] or -1),
                    detections[i]['detection_id']))
    for i in order:
        if i in seen:
            continue
        group = [i]
        js = sorted(adjacency[i], key=lambda j: np.linalg.norm(points[i] - points[j]))
        for j in js:
            if j not in seen and all(j in adjacency[k] for k in group):
                group.append(j)
        seen.update(group)
        groups.append(group)
    return groups, proposed


def environment(detections):
    root = os.getenv('LS_DR11_ROOT')
    if root is None:
        return {}, {}
    import fitsio
    from v13_context import annotate

    catalogs = {}
    positions = {}
    env_path = Path('configs/v13/known_environment.csv')
    environments = read_csv(env_path)
    ra = np.array([m['ra_deg'] for m in detections])
    dec = np.array([m['dec_deg'] for m in detections])
    for region in ('north','south'):
        path = Path(root) / 'masking' / f'SGA2025-ellipse-v1.6-dr11-{region}.kd.fits'
        with fitsio.FITS(path) as f:
            sky = f[1].read(columns=['ra','dec','pa','ba','diam','ref_id','ref_cat'],upper=True)
        usable = np.isfinite(np.column_stack([sky[k] for k in ('RA','DEC','PA','BA','DIAM')])).all(axis=1)
        usable &= (sky['DIAM'] > 0) & (sky['BA'] > 0) & (sky['BA'] <= 1) & (sky['PA'] >= 0)
        sky = sky[usable]
        ids = np.char.add(np.char.strip(sky['REF_CAT'].astype(str)), np.char.add(':',sky['REF_ID'].astype(str)))
        inputs = (dict(m, dm=m['dm'] or 0) for m,on in zip(detections,regional_primary(ra,dec,region)) if on)
        for row in annotate(inputs,sky,ids,environments):
            positions[row['detection_id']] = row
        catalogs[region] = dict(sha256=sha(path),rows=len(sky))
    return positions, catalogs


def source_order(m):
    matched = re.match(r'results/v(\d+)(?:/|$)', m['input'])
    return (int(matched[1]) if matched else (8 if m['input'].startswith('wide_') else 1),
            m['detection_id'])


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    config = Path('configs/v14/catalog_inputs.yaml')
    spec = yaml.safe_load(config.read_text())
    paths = sorted({p for pattern in spec['modes'] for p in Path('.').glob(pattern)})
    detected, modes = load_modes(paths)
    groups, potential = reconcile(detected)
    inspected, sga = environment(detected)
    known = [r for name in spec['known'] for r in read_csv(Path(name))
             if number(r.get('ra')) is not None and number(r.get('dec')) is not None]
    sky = unit([float(r['ra']) for r in known], [float(r['dec']) for r in known])
    tree = cKDTree(sky)
    output_rows, ids, mapping = [], {}, {}
    for group in groups:
        members = [detected[j] for j in group]
        main = members[0]
        earliest = min(members,key=source_order)['detection_id']
        cid = 'DR11-' + hashlib.sha256(earliest.encode()).hexdigest()[:12]
        points = unit([m['ra_deg'] for m in members], [m['dec_deg'] for m in members])
        all_dms = sorted({dm for m in members for dm in m['modes']})
        recognized, nearby = [], []
        for m, p in zip(members, points):
            for j in tree.query_ball_point(p, chord(30)):
                sep = 120 * np.rad2deg(np.arcsin(np.linalg.norm(p-sky[j])/2))
                dm0 = number(known[j].get('distance_modulus'))
                consistent = dm0 is not None and any(abs(x-dm0)<=.75 for x in m['modes'])
                name = known[j]['name']
                nearby.append((float(sep),name))
                if sep <= 5 and consistent:
                    recognized.append((float(sep),name))
        nearest = min(nearby,default=(None,None))
        by_ref = min(recognized,default=(None,None))
        priority = bool({m['group_id'] for m in members}.intersection(spec['priority_groups']))
        c_best = max(members, key=lambda m: m['c_ts'] if m['c_ts'] is not None else -1)
        contextual = [inspected.get(m['detection_id'],{}) for m in members]
        contexts = {m['environment'] for m in members if m['environment']}
        contexts.update(r['known_environment'] for r in contextual if r.get('known_environment'))
        outlines = sorted({r['largest_ellipse_context'] for r in contextual if r.get('largest_ellipse_context')})
        environments = '|'.join(sorted(contexts))
        grade = ('known_system_response' if recognized else 'known_complex_background' if environments or outlines else
                 'priority_L0' if priority else 'L0')
        output_rows.append(dict(candidate_id=cid, anchor_detection=main['detection_id'],
                       ra_deg=main['ra_deg'], dec_deg=main['dec_deg'], search_score=main['score'],
                       rh_arcmin=main['rh_arcmin'], dm_modes='|'.join(map(str, all_dms)), records=len(group),
                       grade=grade, known_system_match=by_ref[1], known_system_arcmin=by_ref[0],
                       nearest_within_30arcmin=nearest[1], nearest_arcmin=nearest[0],
                       environments=environments, extended_galaxy_ellipse_3x='|'.join(outlines),
                       sga_automated=bool(sga), c_ts=c_best['c_ts'], c_without_top3=c_best['c_without_top3'],
                       has_frozen_eval_record=any(m['role']=='pilot_eval' and m['budget']==.3 for m in members),
                       any_C_review=any(m['c_ts'] is not None for m in members),
                       merge_status='candidate_association_requires_membership_check' if len(group)>1 else 'single_record'))
        for j in group:
            ids[j] = cid
            mapping[detected[j]['detection_id']] = cid

    write_csv(output/'candidate_catalogue.csv', output_rows)
    write_csv(output/'candidate_modes.csv', [dict(r, candidate_id=mapping[r['detection_id']]) for r in modes])
    links = []
    for row in potential:
        i,j = row.pop('i'),row.pop('j')
        links.append(dict(row, left_detection=detected[i]['detection_id'],
                          right_detection=detected[j]['detection_id'], left_candidate=ids[i],right_candidate=ids[j],
                          provisional_merge=ids[i] == ids[j]))
    write_csv(output/'potential_associations_within_5arcmin.csv', links)
    source_paths = sorted({*paths, *(Path(r['input']) for r in modes)})
    write_json(output/'manifest.json', dict(job=os.getenv('SLURM_JOB_ID'), config_sha256=sha(config),
               inputs={str(p):sha(p) for p in source_paths}, records=len(detected), modes=len(modes),
               physical_candidate_associations=len(groups), sga=sga, classifications=dict(Counter(r['grade'] for r in output_rows)),
               review_note='Provisional cross-version linkage. Complete-link groups combine sky, scales, and distance modes. '
               'Potential 5 arcmin pairs and all surviving input hypotheses are available. '
               'No membership or image adjudication is implied by a provisional association.'))


if __name__ == '__main__':
    run(Path('results/v14/catalogue'))
