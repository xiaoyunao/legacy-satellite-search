"""Accept all three registered faint-light/control paired measurements."""
import json
import os
from pathlib import Path

import yaml

from ls_satsearch.group_budget import groups, matches
from ls_satsearch.run import read_csv, sha, write_csv, write_json


def run():
    root = Path('results/v14/faint_light')
    registered = read_csv(root/'population_registration.csv')
    expected_sites = {'v14_south_response_'+str(i) for i in (1, 2, 3)}
    if {r['site'] for r in registered} != expected_sites or len(registered) != 3:
        raise ValueError('Registered backgrounds differ')
    inputs = {str(root/'registration.json'):sha(root/'registration.json')}
    pairs = []
    for site in sorted(expected_sites):
        source, proof = root/(site+'-paired.csv'), root/(site+'-acceptance.json')
        metadata = json.loads(proof.read_text())
        rows = read_csv(source)
        if (not metadata['original_extended_controls_reproduced']
                or not metadata['unchanged_bright_members_measured_separately']
                or len(rows) != 4
                or {(r['arm'], r['variant']) for r in rows} != {
                    (a, v) for a in ('ls_base', 'ls_deep')
                    for v in ('extended_bright_control', 'added_faint_light')}):
            raise ValueError('Missing or unaccepted paired measurements')
        for arm in ('ls_base', 'ls_deep'):
            record = dict(site=site, arm=arm, latent_population_id=34)
            for variant in ('extended_bright_control', 'added_faint_light'):
                row = next(r for r in rows if r['arm'] == arm and r['variant'] == variant)
                for key in ('spatial', 'blind_dm', 'blind_correct', 'correct_mode_exists',
                            'c_ts', 'c_after_top3', 'N_bright_rendered', 'N_bright_exposed',
                            'N_bright_final', 'N_bright_psf', 'N_bright_used', 'N_bright_cmd'):
                    record[variant+'_'+key] = row[key]
            if record['extended_bright_control_N_bright_rendered'] != record['added_faint_light_N_bright_rendered']:
                raise ValueError('Bright-member comparison denominator changed')
            pairs.append(record)
        inputs.update({str(p):sha(p) for p in (source, proof)})
    write_csv(root/'paired_comparison.csv', pairs)
    counts = []
    for arm in ('ls_base', 'ls_deep'):
        selected = [r for r in pairs if r['arm'] == arm]
        record = dict(arm=arm, paired_backgrounds=3, independent_latent_populations=1)
        for variant in ('extended_bright_control', 'added_faint_light'):
            for key in ('spatial', 'blind_correct', 'correct_mode_exists'):
                record[variant+'_'+key] = sum(r[variant+'_'+key] == 'True' for r in selected)
            for key in ('N_bright_rendered', 'N_bright_exposed', 'N_bright_final',
                        'N_bright_psf', 'N_bright_used', 'N_bright_cmd'):
                record[variant+'_'+key] = sum(int(r[variant+'_'+key]) for r in selected)
        counts.append(record)
    write_csv(root/'three_background_summary.csv', counts)
    # Diagnose the observed threshold crossing from saved scan hypotheses only.
    # This never reruns the detector or supplies truth to candidate generation.
    cfg = yaml.safe_load(Path('configs/v13/matched/south/search.yaml').read_text())
    data = Path(os.environ['LS_SAT_DATA'])
    margins = []
    for site in sorted(expected_sites):
        outcomes = read_csv(root/(site+'-paired.csv'))
        for row in outcomes:
            folder = data/'image-v14_faint_light'/site/f'trial{int(row["trial"]):02d}'
            source = folder/f'blind_{row["arm"]}'/'all_main_hypotheses.csv'
            truth_path = folder/'truth.json'
            truth = json.loads(truth_path.read_text())
            hypotheses = []
            for original in read_csv(source):
                r = dict(original)
                for key in ('x', 'y', 'ra_deg', 'dec_deg', 'dm', 'rh_arcmin', 'ranking', 'score'):
                    r[key] = float(r[key])
                hypotheses.append(r)
            ranked = groups(hypotheses)
            near = next((g[0] for g in ranked if matches([g], truth, -float('inf'), cfg)['spatial']), None)
            raw_near = next((r for r in sorted(hypotheses, key=lambda r:-r['ranking'])
                             if matches([(r, [r])], truth, -float('inf'), cfg)['spatial']), None)
            cutoff = float(row['cutoff'])
            margins.append(dict(site=site, arm=row['arm'], variant=row['variant'],
                cutoff=cutoff, accepted_spatial=row['spatial'],
                best_matching_raw_score=raw_near['ranking'] if raw_near else None,
                best_matching_group_score=near['ranking'] if near else None,
                best_matching_group_dm=near['dm'] if near else None,
                best_matching_group_scale_arcmin=near['rh_arcmin'] if near else None,
                group_score_minus_cutoff=near['ranking']-cutoff if near else None,
                interpretation='retained_above_cut' if row['spatial']=='True' else
                    'matching_group_below_cut' if near and near['ranking']<cutoff else
                    'no_matching_anchor_in_saved_hypotheses'))
            inputs.update({str(p):sha(p) for p in (source, truth_path)})
    write_csv(root/'saved_peak_margins.csv', margins)
    write_json(root/'acceptance.json', dict(inputs=inputs, code_sha256=sha(Path(__file__)),
        native_cases=3, paired_arm_cases=6, unique_latent_populations=1,
        original_extended_controls_reproduced=True,
        scope='Outcome-targeted single draw34, three selected backgrounds; unchanged bright-member identities '
              'and input light bookkeeping. The original144 and expanded-bright controls are preserved. '
              'Conditional faint-star positions and changed photon pixels contribute to the response. '
              'Residual spatial-tail light remains omitted. No population completeness correction, '
              'independent-three-population confidence interval, calibrated V magnitude or physical PS1 gain.'))
    print('FAINT_LIGHT_THREE_BACKGROUND_ACCEPTED', counts)


if __name__ == '__main__':
    run()
