"""Collect completed frozen fields and prioritize full-mode follow-up for visual review."""

import argparse
from collections import Counter, defaultdict
import json
import os
from pathlib import Path

import yaml
from astropy.coordinates import SkyCoord
from astropy.table import Table
import numpy as np

from .run import read_csv, sha, write_csv, write_json


def reference_catalog():
    refs = {}
    paths = sorted(Path('references/codex_benchmark_sources').glob('*.csv'))
    supplement = Path('references/known_globular_centres.csv')
    if supplement.exists():
        paths.append(supplement)
    for path in paths:
        for row in read_csv(path):
            if not row.get('ra') or not row.get('dec') or not row.get('key'):
                continue
            refs.setdefault(row['key'], row)
    records = list(refs.values())
    sky = SkyCoord([float(r['ra']) for r in records], [float(r['dec']) for r in records], unit='deg')
    radii = np.array([float(r['rhalf'] or 'nan') for r in records])
    dm = np.array([float(r['distance_modulus'] or 'nan') for r in records])
    return records, sky, radii, dm


CONTEXTS = ('direct_position_and_dm', 'extended_sky_context', 'compact_sky_context',
            'published_stream_context', 'untagged')


def known_context(modes, catalog, stream=None):
    records, sky, radii, dm = catalog
    matches = []
    for mode in modes:
        pos = SkyCoord(float(mode['fit_ra_deg']), float(mode['fit_dec_deg']),unit='deg')
        offset = sky.separation(pos).arcmin
        delta = float(mode['fit_dm']) - dm
        direct = (offset <= np.fmax(2., radii)) & (abs(delta) <= .75)
        fit_rh = float(mode['fit_rh_arcmin'])
        extended = (radii >= 3.) & (offset <= np.maximum(1.5*radii,fit_rh))
        near = offset <= 2.
        for i in np.flatnonzero(direct | extended | near):
            tier = 0 if direct[i] else 1 if extended[i] else 2
            matches.append((tier, offset[i], records[i]['name'], delta[i], mode['rank']))
        if stream is not None:
            track, track_dm = stream
            i, sep, _ = pos.match_to_catalog_sky(track)
            ddm=float(mode['fit_dm'])-track_dm[i.item()]
            if sep.arcmin.item()<=15. and abs(ddm)<=.75:
                matches.append((3,sep.arcmin.item(),'Palomar 5 tidal stream',ddm,mode['rank']))
    if not matches:
        return dict(known_context='untagged', known_context_name='', known_context_offset_arcmin=None,
                    known_context_dm_delta=None, known_context_mode_rank='')
    tier, offset, name, delta, rank = min(matches)
    return dict(known_context=CONTEXTS[tier],
                known_context_name=name, known_context_offset_arcmin=float(offset),
                known_context_dm_delta=float(delta) if np.isfinite(delta) else None,
                known_context_mode_rank=rank)


def combine(allow_incomplete=False, output=Path('results/rollout_index'), pal5_track=None):
    paths=[('first',Path('results/registration/fields.yaml'),[Path('first_batch')])]
    for name in ('rollout','gaps'):
        directory=Path(f'wide_{name}')
        paths.append((name,directory/'results/registration/fields.yaml',sorted(directory.glob('batch*'))))
    output.mkdir(parents=True,exist_ok=True)
    expected={}
    fields,candidates,fits_index,manifests=[],[],[],[]
    completed=set()
    catalog=reference_catalog()
    stream=None
    if pal5_track:
        table=Table.read(pal5_track,format='ascii.ecsv')
        stream=(SkyCoord(table['ra'],table['dec']),5*np.log10(np.asarray(table['distance'])*100))
    history_columns=('hsc_nominal_intersection','kids_nominal_intersection',
                     'rubin_dp1_nominal_intersection','unions_nominal_core_dec_overlap')
    fit_columns=('candidate_group_id','rank','fit_status','field','fit_ra_deg','fit_dec_deg',
                 'seed_dm','seed_rh_arcmin','fit_dm','fit_rh_arcmin','ts',
                 'C_refit_TS_without_top1','C_refit_TS_without_top3','effective_members',
                 'nearest_known','nearest_known_arcmin','image_pending')
    for phase,registry,batches in paths:
        spec=yaml.safe_load(registry.read_text())['fields']
        known={r['id']:r for r in spec}
        expected.update({r['id']:phase for r in spec})
        overlap_file=registry.with_name('external_overlap_audit.csv')
        overlap={r['field']:r for r in read_csv(overlap_file)} if overlap_file.exists() else {}
        for folder in batches:
            holdout=folder/'results/holdout'
            tab=holdout/'holdout_field_summary.csv'
            diagnostic=holdout/'expansion_group_diagnostics.csv'
            if not tab.exists() or not diagnostic.exists():
                continue
            rows=read_csv(tab)
            groups=read_csv(diagnostic)
            ids={r['field'] for r in rows}
            if not ids<=set(known) or ids&completed:
                raise ValueError(f'Unexpected or duplicate fields from {folder}')
            target=sum(int(r['kept_sky_groups']) for r in rows if float(r['budget'])==.3)
            if len(groups)!=target:
                raise ValueError(f'Incomplete C-review table in {folder}')
            for row in rows:
                if float(row['budget'])!=.3:
                    continue
                path=folder/'results/summary'/f"{row['field']}-base"/'manifest.json'
                run=json.loads(path.read_text())
                if run['status']!='complete' or run['field']['id']!=row['field']:
                    raise ValueError(f'Unexpected scan manifest in {path}')
                if not np.isclose(run['area_deg2'],float(row['area_deg2']),atol=1e-9,rtol=0):
                    raise ValueError(f'Area mismatch in {path}')
                manifests.append(dict(field=row['field'],wave=phase,batch=folder.name,
                                  manifest_sha256=sha(path),release=run['release'],config_sha256=run['config_hash'],
                                  fields_sha256=run['fields_sha256'],model_sha256=run['model_sha256'],
                                  seed=run['seed'],job=run['slurm_job_id'],area_deg2=run['area_deg2'],
                                  inner_psf=run['cutflow']['inner_psf'],scan_seconds_A=run['scan_seconds']['A'],
                                  wall_seconds=run['wall_seconds']))
            completed.update(ids)
            for r in rows:
                fields.append(dict(r,wave=phase,batch=folder.name,
                            historical_satellite_search_mask=known[r['field']]['prior_search_mask'],
                            **{k:overlap.get(r['field'],{}).get(k,'unknown') for k in history_columns}))
            fits=read_csv(holdout/'group_review_modes.csv')
            if len(fits)!=sum(int(r['modes_attempted']) for r in groups):
                raise ValueError(f'C mode count differs from group summary in {folder}')
            fits_index.extend({k:r.get(k,'') for k in fit_columns} for r in fits)
            modes={(r['candidate_group_id'],r['rank']):r for r in fits}
            by_group=defaultdict(list)
            for fit in fits:
                if fit.get('fit_ra_deg') and fit.get('fit_dm'):
                    by_group[fit['candidate_group_id']].append(fit)
            for r in groups:
                fit=modes.get((r['group_id'],r['best_peak_rank']),{})
                context=known_context(by_group[r['group_id']],catalog,stream)
                low_context=context['known_context']=='untagged' and r['review_status']!='key_images_pending'
                severity = float(r['best_ts_without_top3'] or 0)
                candidates.append(dict(r,wave=phase,batch=folder.name,fit_ra_deg=fit.get('fit_ra_deg'),
                   fit_dec_deg=fit.get('fit_dec_deg'),manual_priority=int(low_context and severity>=2.),
                   **context,
                   diagnostic_directory=str(folder/'results/figures'/f"{r['field']}-base")))
    missing=sorted(set(expected)-completed)
    report=[]
    for phase in ('first','rollout','gaps','all'):
        for budget in (.1,.3):
            selected=[r for r in fields if float(r['budget'])==budget and (r['wave']==phase or phase=='all')]
            area=sum(float(r['area_deg2']) for r in selected)
            n=sum(int(r['kept_sky_groups']) for r in selected)
            if area:
                report.append(dict(wave=phase,budget=budget,completed_fields=len(selected),
                             effective_area_deg2=area,held_groups=n,groups_per_deg2=n/area))
    if fields:
        write_csv(output/'field_summary.csv',fields)
        write_csv(output/'field_manifest_index.csv',manifests)
        primary=[r for r in fields if float(r['budget'])==.3]
        history=[]
        for column in ('historical_satellite_search_mask', *history_columns):
            for value in sorted({r[column] for r in primary}):
                matching=[r for r in primary if r[column]==value]
                history.append(dict(audit=column,flag=value,fields=len(matching),
                                    field_area_deg2=sum(float(r['area_deg2']) for r in matching),
                                    main_groups=sum(int(r['kept_sky_groups']) for r in matching)))
        write_csv(output/'historical_overlap_summary.csv',history)
    if candidates:
        candidates.sort(key=lambda r:(-r['manual_priority'],-float(r['best_ts_without_top3'] or 0),
                      -float(r['best_ts'] or 0),r['group_id']))
        write_csv(output/'candidate_index.csv',candidates)
        write_csv(output/'c_modes.csv',fits_index)
    if report:
        write_csv(output/'review_load.csv',report)
    if candidates:
        totals=[]
        for phase in ('first','rollout','gaps','all'):
            for context in CONTEXTS:
                selected=[r for r in candidates if (phase=='all' or phase==r['wave']) and r['known_context']==context]
                totals.append(dict(wave=phase,context=context,groups=len(selected),
                                   named_systems='|'.join(sorted({r['known_context_name'] for r in selected if r['known_context_name']})),
                                   manual_priority=sum(r['manual_priority'] for r in selected)))
        write_csv(output/'known_context_summary.csv',totals)
    write_json(output/'status.json',dict(job=os.environ.get('SLURM_JOB_ID'),registered=len(expected),
               completed=len(completed),missing=missing,unfinished_by_wave=Counter(expected[f] for f in missing),
               c_modes_attempted=sum(int(r['modes_attempted']) for r in candidates),
               c_modes_fit=sum(int(r['modes_fit']) for r in candidates),
               automated_review_status=Counter(r['review_status'] for r in candidates),
               published_track_sha256=sha(pal5_track) if pal5_track else None,
               visual_review='pending prioritized manual triage'))
    if missing and not allow_incomplete:
        raise ValueError(f'{len(missing)} registered fields still lack a complete scan and review')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-incomplete',action='store_true')
    parser.add_argument('--output', type=Path, default=Path('results/rollout_index'))
    parser.add_argument('--pal5-track',type=Path)
    args=parser.parse_args()
    combine(args.allow_incomplete,args.output,args.pal5_track)
