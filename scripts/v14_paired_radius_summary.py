"""Summarize all registered paired-radius native stages, without blind-search claims."""
import json
from pathlib import Path

import numpy as np

from ls_satsearch.run import read_csv, sha, write_csv, write_json


def run():
    folder = Path('results/v14/paired_radius')
    source = folder / 'full_stage_pairs.csv'
    proof = folder / 'full_stage_acceptance.json'
    accepted = json.loads(proof.read_text())
    rows = read_csv(source)
    populations = sorted({int(r['original_trial']) for r in rows})
    sites = sorted({r['site'] for r in rows})
    arms = ('ls_base', 'ls_deep')
    keys = [(int(r['original_trial']), r['site'], r['arm']) for r in rows]
    if (len(rows) != 48 or len(set(keys)) != 48 or len(populations) != 8
            or len(sites) != 3 or accepted['native_cases'] != 24
            or set(keys) != {(p, s, a) for p in populations for s in sites for a in arms}
            or not accepted['original_stage_counts_reproduced']
            or not accepted['rendered_intrinsic_light_identical']):
        raise ValueError('Require the complete preregistered, validated paired experiment')
    table = dict(zip(keys, rows))
    stages = ('exposed', 'initial', 'final', 'psf', 'used', 'cmd')
    rng = np.random.default_rng(487242)
    # Shared indices preserve both radii, both depths and all stage correlations.
    pop_draws = rng.integers(0, 8, (10000, 8))
    sky_draws = rng.integers(0, 3, (10000, 3))
    output = []
    for arm in arms:
        for stage in stages:
            fractions = []
            sums = []
            for variant in ('parent10', 'paired3'):
                counts = np.array([[int(table[p, s, arm][variant + '_N_' + stage])
                                    for s in sites] for p in populations])
                rendered = np.array([[int(table[p, s, arm][variant + '_N_rendered'])
                                      for s in sites] for p in populations])
                if (rendered <= 0).any() or (counts > rendered).any() or (counts < 0).any():
                    raise ValueError('Invalid native member counts')
                fractions.append(counts / rendered)
                sums.append(int(counts.sum()))
            delta = fractions[1] - fractions[0]
            boot = delta[pop_draws[:, :, None], sky_draws[:, None, :]].mean(axis=(1, 2))
            low, high = np.quantile(boot, [.025, .975])
            output.append(dict(arm=arm, stage=stage, native_pairs=24,
                parent10_total=sums[0], paired3_total=sums[1],
                parent10_mean_rendered_fraction=float(fractions[0].mean()),
                paired3_mean_rendered_fraction=float(fractions[1].mean()),
                paired3_minus_parent10_mean_rendered_fraction=float(delta.mean()),
                exploratory_paired_bootstrap_low=float(low),
                exploratory_paired_bootstrap_high=float(high)))
    write_csv(folder / 'stage_comparison.csv', output)
    write_json(folder / 'stage_comparison_manifest.json', dict(
        inputs={str(p): sha(p) for p in (source, proof, folder / 'registration.json')},
        code_sha256=sha(Path(__file__)), populations=populations, sites=sites,
        seed=487242, bootstrap_draws=10000,
        resampling='Eight shared populations and three fixed selected backgrounds, crossed resampling; radii/depths/stages paired throughout.',
        denominator='Rendered input members in each paired realization; equal weight per population/background pair, not pooled-star completeness.',
        blind_search_performed=False, Pdet_measured=False,
        scope='Conditional finite rendered populations at 100 kpc, originally target MV proxy -3. '
              'Exposure, source extraction/association, PSF and hard cuts are actual native stages. '
              'Initial and final detection are different pipeline products and need not be nested. '
              'Intervals are exploratory with only eight populations and three selected skies; '
              'not broad-sky confidence or a pure mutual-crowding effect. Same intrinsic input light '
              'does not guarantee equal local extinction, exposure, foreground blends or photon pixels. '
              'Original 144 outcomes remain unchanged. No PS1 response or physical recovery probability is inferred.'))
    print('PAIRED_RADIUS_SUMMARY_ACCEPTED', len(output))


if __name__ == '__main__':
    run()
