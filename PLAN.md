# Plan

## Current objective

Use LS DR11 to detect previously missed faint Galactic stellar systems and measure the gain against PS1 in the census PS1 assignment. See [current scientific direction](docs/PROJECT_MEMORY.md).

## Completed milestones

- Completed v1/v2 real-data pilots, ordinary processing audit, paired depth injections and five PS1 catalog probes.
- Froze disjoint 61.100 deg² development and 60.705 deg² evaluation cohorts.
- Recomputed old field results by sky group and separated spatial detection, correct mode retention and truth-blind highest mode.

## Third-round measurements

- Six fresh development fields completed at both depths (61.100 effective deg²), including A/B controls on two blocks. Group budget calibration and the visual review of 18 baseline groups are published.
- The three 80 pc diagnostics reproduced the overlay runs. Isolation made little difference. One nested ladder crossed the fixed cut between 45 and 65 usable members.
- The matched survey experiment completed on four fields. Pegasus IV is recovered by all three samples; the Aquarius IV centre is outside the shared usable mask. Four shared-population trials give positional detection counts of 2, 2 and 3 for LS baseline, LS deeper and PS1.

## Fourth-round results

- Completed the frozen 60.705 deg² evaluation. A baseline selected 23 primary-budget groups, including the blind recovery of Hercules. Reviewed 49 modes and visually assessed all 23 groups.
- Completed two preregistered independent controls and four matched-survey response replays. Expanded the matched development calibration to 16.851 deg². LS baseline and deep both recover DELVE 4 and DELVE 5 at the common budget.

## Fifth-round results

- Completed all three frozen discovery batches. Their 36 PS1 fields contain 339.769 effective deg² and 96 primary groups. Separate DES controls contain 20.526 deg² and three primary groups. Completed 193 modes and visually triaged all 99 groups.
- DELVE 3/4/5 passed candidate triage before the published-member associations. One new L0 position merits targeted follow-up.
- Completed 24 field-matched LS–PS1 trials and eight paired fine-grid injections. The depth comparison supports a compact follow-up experiment. The 0.25 arcmin grid yielded no extra positional recoveries in the tested controls.

## Sixth-round verification

- PS1 reproduces the leading L0 position. Its fixed-distance likelihood is weak, and the highest local C mode is closer. Gaia indicates bright-source contamination. Public CFHT r imaging and Subaru g header coverage are recorded.
- Matched random locations explain much of the mask proximity. The next 20 frozen fields cover 168.204 effective deg² and yield 39 primary groups. All 48 C modes and 39 representative images were inspected.
- In eight paired compact injections, baseline and deeper LS recovered 3 and 5 positions. The DELVE 7 deeper peak recovered position alone.

## Seventh-round verification and expansion

- Three raw HSC CCDs passed archive and FITS checks. Two visits support provisional local calibration. The fixed HSC+CFHT image test gives limited common-population evidence for both distances.
- In the matched Gaia cuts, the stronger 100 kpc response remains specific to LS. The candidate stays L0. The public novelty audit is updated.
- Three nonoverlapping registries contain 195 fields and about 989 deg² of metadata proxy area under the frozen A recipe. The scheduler and measured completed area are tracked separately.

## Eighth-round verification

- On the existing frozen A cohort, report the native searched area, C fit completion, sky groups, known-system and stream context, and the prioritized visual review. The remaining PS1 footprint uses a HEALPix/brick eligibility proxy sampled against completed core masks.
- Tested survey_14 at both frozen distances with shared Gaia and secure DESI QSO vetoes. Completed one bounded HSC g plus CFHT r calibration sensitivity check for expand_03.
- Across the rollout, survey_63 is the leading new compact L0. PS1 local spatial support and mobility constraints are measured. Survey_51 remains secondary after the full Gaia shortlist fails a common proper-motion fit.

## Ninth-round verification

- Completed blinded review of 24 low-priority groups and three weak survey controls that entered the baseline queue. DELVE 7 informs the upstream detection boundary.
- Audited public archive coverage for survey_63. Downloaded and measured a partial independent DECam g exposure. Only 51.7% of the core is usable, and measured dereddened five-sigma depth is approximately 23.
- Applied official Euclid DR1 imaging MOCs to the remainder and evaluated the published PS1 DR1 census classifier at the two matched physical-pilot backgrounds. See the ninth science report for the measured comparison and its limits.

## Tenth-round priority

- Expanded the survey_63 public imaging audit and calibrated four wider CFHT r cutouts. Archive checks and exposure calculator results are in the [tenth science report](tenth_science_report.md).
- Completed 16 realizations on two additional matched development backgrounds at 100–150 kpc, 10–30 pc and expected integrated V proxy −3. The spatial counts were 7/12/11 for LS baseline, deeper LS and PS1 DR2.
- Finished fixed-centre and local blind PS1 diagnostics for the five ambiguous groups. All retain L0. Continue to track DELVE 4/7 as downstream review and upstream detection controls.

## Next work

1. Ask WHIGS for the actual g visit/usable-pixel footprint through an authorized channel, and prioritize a full-core deep two-band observation with the specified background annulus. Keep the three distance hypotheses distinct pending matched-mask CMD evidence.
2. Measure faint detection and morphology response on a small image-injection set with original catalog settings. Use the additional real backgrounds and exact native templates to identify where extending the physical grid will change the incremental LS constraint.
3. Reconcile the ranked PS1 cells with exact HSC, UNIONS and Rubin historical search coverage when available. Choose the next frozen A cohort based on measured incremental sensitivity.

## Validation criteria

- Each completed job records input, configuration, effective area, method and timings. Candidate budget calibration checks the entire planned development cohort.
- Survey measurements use independent samples on identical usable masks with explicit native photometry and search settings.
- Decisions about deeper or combined searches depend on matching the same total review budgets. Use the held-out count and its area after the policy is frozen.
- [Execution status](docs/STATUS.md) records scheduler and input availability.
