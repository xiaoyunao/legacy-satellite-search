"""Calibrate review budgets on development fields and score frozen evaluation data."""

import argparse
import json
import math
from pathlib import Path

import numpy as np
from astropy.coordinates import SkyCoord
from scipy.stats import chi2

from .run import read_csv, write_csv, write_json


def thresholds(dev, area, budgets):
    result = {}
    for method in ('A', 'B'):
        scores = sorted((float(r['score']) for r in dev if r['method'] == method), reverse=True)
        for budget in budgets:
            target = int(math.floor(budget * area))
            if len(scores) <= target:
                cutoff = None
            else:
                cutoff = float(np.nextafter(scores[target], np.inf))
            result[(method, budget)] = (cutoff, target)
    return result


def survives(peak, cutoff):
    return bool(cutoff is not None and float(peak['score']) >= cutoff)


def interval(n, area):
    return (0. if n == 0 else chi2.ppf(.025, 2*n) / (2*area), chi2.ppf(.975, 2*(n+1)) / (2*area))


def csv_or_empty(path):
    return read_csv(path) if path.exists() else []


def source_references():
    files = sorted(Path('references/codex_benchmark_sources').glob('*.csv'))
    rows = []
    for path in files:
        for row in read_csv(path):
            try:
                ra, dec = float(row['ra']), float(row['dec'])
            except (ValueError, TypeError, KeyError):
                continue
            if np.isfinite(ra + dec):
                rows.append((row['name'], ra, dec, path.name))
    return rows


def evaluate(summary):
    manifests = {}
    for path in sorted(summary.glob('*/manifest.json')):
        m = json.loads(path.read_text())
        canonical = f"{m['field']['id']}-{m['depth']}"
        if path.parent.name == canonical and m['status'] in ('complete', 'no_usable_gr'):
            manifests[path.parent] = m
    recovery = []
    forced = []
    for path, m in manifests.items():
        recovery.extend(dict(r, field=m['field']['id'], role=m['field']['role']) for r in
                        csv_or_empty(path / 'recovery.csv'))
        forced.extend(dict(r, field=m['field']['id']) for r in csv_or_empty(path / 'forced_fit.csv'))
    if recovery:
        write_csv(summary / 'known_recovery_summary.csv', recovery)
    if forced:
        write_csv(summary / 'forced_fit_summary.csv', forced)
    report, candidates, cuts, foot = [], [], [], []
    references = source_references()
    coords = SkyCoord([p[1] for p in references], [p[2] for p in references], unit='deg')
    for path, m in manifests.items():
        f = m['field']
        counts = m['cutflow']
        foot.append(dict(field=f['id'], role=f['role'], depth=m['depth'],
                         ra_deg=f['ra'], dec_deg=f['dec'], area_deg2=m['area_deg2'],
                         area_fraction=m['area_fraction'], n_psf=counts['inner_psf'],
                         n_non_psf=counts['inner_other'],
                         n_psf_faint=counts['inner_psf_faint'], n_non_psf_faint=counts['inner_other_faint'],
                         g5_dered=(m['observing_conditions_source_sample']['G']['depth5_dered'] or [None]*3)[1],
                         g_seeing=(m['observing_conditions_source_sample']['G']['seeing'] or [None]*3)[1]))
    if foot:
        write_csv(summary / 'field_conditions.csv', foot)
    for depth in ('base', 'deep'):
        dev = {p: m for p, m in manifests.items() if m['status'] == 'complete' and m['depth'] == depth and m['field']['role'] == 'pilot_dev'}
        ev = {p: m for p, m in manifests.items() if m['status'] == 'complete' and m['depth'] == depth and m['field']['role'] == 'pilot_eval'}
        if not dev:
            continue
        ctrl = {p: m for p, m in manifests.items() if m['status'] == 'complete' and
                m['depth'] == depth and m['field']['role'] == 'deep_control'}
        control_area = sum(m['area_deg2'] for m in ctrl.values())
        dev_area = sum(m['area_deg2'] for m in dev.values())
        ev_area = sum(m['area_deg2'] for m in ev.values())
        fmt_peak = lambda p, r: dict(r, field=p.name, field_id=manifests[p]['field']['id'])
        dp = [fmt_peak(p, r) for p in dev for r in read_csv(p / 'deduplicated_peaks.csv')]
        ep = [fmt_peak(p, r) for p in ev for r in read_csv(p / 'deduplicated_peaks.csv')]
        cp = [fmt_peak(p, r) for p in ctrl for r in read_csv(p / 'deduplicated_peaks.csv')]
        budgets = next(iter(dev.values()))['config']['review_budgets_deg2']
        thresholds_by_method = thresholds(dp, dev_area, budgets)
        for (method, budget), (cutoff, target) in thresholds_by_method.items():
            dev_kept = [r for r in dp if r['method'] == method and survives(r, cutoff)]
            ev_kept = [r for r in ep if r['method'] == method and survives(r, cutoff)]
            ctrl_kept = [r for r in cp if r['method'] == method and survives(r, cutoff)]
            eligible = [r for r in recovery if r['method'] == method and r['depth'] == depth and
                        r['covered'] == 'True' and r['role'] in ('recovery', 'recovery_evaluation')]
            kept = [r for r in eligible if r.get('score') and survives(r, cutoff)]
            retained = {r['name'] for r in kept}
            for row in recovery:
                if row['method'] == method and row['depth'] == depth and row in eligible:
                    row[f'passes_budget_{budget}'] = row['name'] in retained
            lo, hi = interval(len(ev_kept), ev_area) if ev_area else (None, None)
            matched_recovery = [float(r['offset_arcmin']) for r in kept]
            dm = [abs(float(r['delta_dm'])) for r in kept]
            cfg = dict(depth=depth, method=method, budget_per_deg2=budget, cutoff=cutoff,
                       dev_target_peaks=target, dev_area_deg2=dev_area,
                       dev_peaks=len(dev_kept), dev_peaks_per_deg2=len(dev_kept)/dev_area,
                       evaluation_peaks=len(ev_kept) if ev_area else None,
                       evaluation_area_deg2=ev_area,
                       evaluation_peaks_per_deg2=len(ev_kept)/ev_area if ev_area else None,
                       count_interval95_low=lo, count_interval95_high=hi,
                       des_control_area_deg2=control_area,
                       des_control_peaks=len(ctrl_kept) if control_area else None,
                       development_fields=len(dev), evaluation_fields=len(ev),
                       benchmark_eligible=len(eligible), benchmark_recovered=len(kept),
                       heldout_benchmark_eligible=sum(r['role'] == 'recovery_evaluation' for r in eligible),
                       heldout_benchmark_recovered=sum(r['role'] == 'recovery_evaluation' for r in kept),
                       median_offset_arcmin=np.median(matched_recovery) if matched_recovery else None,
                       median_abs_dm_error=np.median(dm) if dm else None,
                       evaluation_search_seconds=sum(m['scan_seconds'][method] for m in ev.values()),
                       evaluation_shared_and_cmd_seconds=sum(m['scan_seconds']['cmd'] + m['scan_seconds']['shared']
                                                             for m in ev.values()))
            report.append(cfg)
            cuts.append(dict(depth=depth, method=method, budget=budget, cutoff=cutoff))
        # Publish the fixed 0.3-budget L0 list. Keep A/B as separate entries with cross-association.
        highest_budget = max(budgets)
        chosen = [r for r in ep if survives(r, thresholds_by_method[(r['method'], highest_budget)][0])]
        for r in chosen:
            position = SkyCoord(float(r['ra_deg']), float(r['dec_deg']), unit='deg')
            sep = position.separation(coords).arcmin
            i = int(sep.argmin())
            peers = [q for q in chosen if q['field_id'] == r['field_id'] and q['method'] != r['method']]
            refs = csv_or_empty(summary / r['field'] / 'candidate_refits.csv')
            refit = next((q for q in refs if q['method'] == r['method'] and q['rank'] == r['rank']), {})
            checks = csv_or_empty(summary / r['field'] / 'review.csv')
            review = next((q for q in checks if q['method'] == r['method'] and q['rank'] == r['rank']), {})
            matches = []
            for q in peers:
                other = SkyCoord(float(q['ra_deg']), float(q['dec_deg']), unit='deg')
                if position.separation(other).arcmin <= max(1., float(r['rh_arcmin']), float(q['rh_arcmin'])):
                    matches.append(f"{q['method']}-{q['rank']}")
            candidates.append(dict(**r, depth=depth, evidence_level='L0', budget_per_deg2=highest_budget,
                                   nearest_known=references[i][0], nearest_known_arcmin=float(sep[i]),
                                   nearest_known_catalog=references[i][3], other_method=';'.join(matches),
                                   C_ts=review.get('ts', refit.get('ts')),
                                   C_fit_rh=review.get('fit_rh_arcmin', refit.get('fit_rh_arcmin')),
                                   C_fit_dm=review.get('fit_dm', refit.get('fit_dm')),
                                   C_richness=review.get('richness', refit.get('richness')),
                                   C_refit_TS_without_top1=review.get('C_refit_TS_without_top1'),
                                   C_refit_TS_without_top3=review.get('C_refit_TS_without_top3'),
                                   C_fixed_fit_ts_drop_top3=refit.get('fixed_fit_ts_drop_top3'),
                                   cmd_on_snr5=review.get('cmd_on_snr5'),
                                   cmd_on_snr7=review.get('cmd_on_snr7'),
                                   diagnostic_reviewed=bool(review)))
    if recovery:
        write_csv(summary / 'known_recovery_summary.csv', recovery)
    if report:
        write_csv(summary / 'method_comparison.csv', report)
        write_json(summary / 'review_cutoffs.json', cuts)
        if any(r['evaluation_fields'] for r in report):
            write_csv(summary / 'pilot_candidate_summary.csv', candidates,
                      ('field_id', 'method', 'rank', 'ra_deg', 'dec_deg', 'dm', 'rh_arcmin', 'score', 'evidence_level'))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--summary', type=Path, default=Path('results/summary'))
    evaluate(p.parse_args().summary)
