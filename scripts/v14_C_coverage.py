"""Audit attempted C seeds on exact qualified discovery records, without fitting."""
from collections import Counter, defaultdict
import json
from pathlib import Path

from ls_satsearch.run import read_csv, sha, write_csv, write_json
from scripts.v14_catalog import bound_fit_seed, number, seed_signature


def run():
    root = Path('results/v14/production_integration')
    inventory = root/'eligible_record_inventory.csv'
    catalogue = Path('results/v14/catalogue/candidate_modes.csv')
    inputs = {}

    def read(path):
        if str(path) not in inputs:
            inputs[str(path)] = sha(path)
        return read_csv(path)

    qualified = read(inventory)
    catalogue_manifest = Path('results/v14/catalogue/manifest.json')
    inputs[str(catalogue_manifest)] = sha(catalogue_manifest)
    provenance = json.loads(catalogue_manifest.read_text())
    source_groups = {}
    for record in qualified:
        path = Path(record['input'])
        if path not in source_groups:
            groups = defaultdict(list)
            for seed in read(path):
                groups[seed['group_id']].append(seed)
            source_groups[path] = groups
        if inputs[str(path)] != record['source_sha256']:
            raise ValueError('Qualified discovery source changed')
    fits = defaultdict(list)
    originals = {}
    qualified_keys = {f"{Path(r['input']).parent}:{r['group_id']}":r for r in qualified}
    bindings = {}
    for row in read(catalogue):
        if row['source_kind'] != 'C_followup' or row['detection_id'] not in qualified_keys:
            continue
        path = Path(row['input'])
        if path not in originals:
            originals[path] = read(path)
            if provenance['inputs'].get(str(path)) != inputs[str(path)]:
                raise ValueError('Raw C source changed since catalogue snapshot: '+str(path))
        source = Path(qualified_keys[row['detection_id']]['input'])
        binding = (path, source, row['group_id'])
        if binding not in bindings:
            proof = path.with_name('reviewed_group_inputs.csv' if path.parent==source.parent else 'review_modes.csv')
            if path.parent != source.parent:
                provenance_path = path.with_name('provenance.json')
                inputs[str(provenance_path)] = sha(provenance_path)
                saved = json.loads(provenance_path.read_text())
                if saved.get('input') != str(source):
                    raise ValueError('C provenance names another discovery source')
                if saved.get('selection_sha256') and saved['selection_sha256'] != sha(proof):
                    raise ValueError('C selection changed after fitting')
            origin = [r for r in read(proof) if (r.get('group_id') or r.get('candidate_group_id'))==row['group_id']]
            expected = source_groups[source][row['group_id']]
            if {seed_signature(r) for r in origin} != {seed_signature(r) for r in expected}:
                raise ValueError('C source proof does not match the complete discovery seed set')
            bindings[binding] = True
        line = int(row['record_id'].rsplit(':', 1)[1])
        fit = originals[path][line-1]
        if (fit['candidate_group_id'] != row['group_id'] or
                fit['fit_status'] != row['fit_status']):
            raise ValueError('Catalogue and raw C source clocks differ')
        fits[row['detection_id']].append((fit, str(path), line))
    seeds, records = [], []
    for record in qualified:
        path = Path(record['input'])
        key = f"{path.parent}:{record['group_id']}"
        required = [seed for seed in source_groups[path][record['group_id']]
                    if seed['policy'] == 'A_base' and seed['channel'] == 'A_base'
                    and number(seed['budget']) == .3 and seed['role'] == 'pilot_eval'
                    and 16.5 <= number(seed['dm']) <= 20.75]
        if len(required) != int(record['hypothesis_rows']):
            raise ValueError('Required C seed count differs from qualified discovery hypotheses')
        counts = Counter()
        for seed in required:
            matching = [(fit, file, line) for fit, file, line in fits[key]
                        if bound_fit_seed(fit, [seed])]
            status = ('complete' if any(fit['fit_status'] == 'complete' for fit, _, _ in matching)
                      else 'attempted_unavailable' if matching and
                      all(fit['fit_status'] == 'unavailable' for fit, _, _ in matching)
                      else 'other_attempt_status' if matching else 'not_attempted')
            counts[status] += 1
            seeds.append(dict(input=str(path), group_id=record['group_id'], field=seed['field'],
                peak_rank=seed['peak_rank'], seed_ra_deg=seed['ra_deg'], seed_dec_deg=seed['dec_deg'],
                dm=seed['dm'], rh_arcmin=seed['rh_arcmin'], score=seed['score'],
                C_seed_state=status, bound_fit_rows=len(matching),
                C_sources='|'.join(sorted({f'{file}:{line}' for _, file, line in matching}))))
        state = ('all_complete' if counts['complete'] == len(required) else
                 'all_attempted_some_unavailable' if counts['complete']+counts['attempted_unavailable'] == len(required)
                 else 'partial_attempts' if any(k != 'not_attempted' and v for k, v in counts.items())
                 else 'not_attempted')
        records.append(dict(input=str(path), group_id=record['group_id'], field=record['field'],
            required_discovery_seeds=len(required), C_coverage_state=state,
            **{key:counts[key] for key in ('complete','attempted_unavailable','other_attempt_status','not_attempted')}))
    for path, checksum in inputs.items():
        if sha(Path(path)) != checksum:
            raise ValueError('Input changed during C seed audit: '+path)
    out = root/'C_seed_coverage'
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out/'seeds.csv', seeds)
    write_csv(out/'records.csv', records)
    summary = dict(qualified_records=len(records), required_discovery_seeds=len(seeds),
        record_states=dict(Counter(r['C_coverage_state'] for r in records)),
        seed_states=dict(Counter(r['C_seed_state'] for r in seeds)), inputs=inputs,
        code_sha256=sha(Path(__file__)), final_all_required_C_accepted=False,
        all_qualified_C_seeds_complete=all(r['C_coverage_state']=='all_complete' for r in records),
        scope='Exact same-record seed coverage, not candidate quality or physical recovery. Each qualified original A-base hypothesis is accounted for. Unavailable likelihood fits remain terminal attempts distinct from missing computation; no repeated identical fit is automatically requested. This audit neither changes the frozen discovery cut nor asserts all low-priority records need human review. Final human-review selection and evidence QA remain separate.')
    write_json(out/'summary.json', summary)
    print({k:summary[k] for k in ('qualified_records','required_discovery_seeds','record_states','seed_states')}, flush=True)


if __name__ == '__main__':
    run()
