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

## Tenth-round results

- Expanded the survey_63 public imaging audit and calibrated four wider CFHT r cutouts. Archive checks and exposure calculator results are in the [tenth science report](tenth_science_report.md).
- Completed 16 realizations on two additional matched development backgrounds at 100–150 kpc, 10–30 pc and expected integrated V proxy −3. The spatial counts were 7/12/11 for LS baseline, deeper LS and PS1 DR2.
- Finished fixed-centre and local blind PS1 diagnostics for the five ambiguous groups. All retain L0. Continue to track DELVE 4/7 as downstream review and upstream detection controls.

## Eleventh-round results

- Completed all 56 newly registered cores (574.044 effective deg²). North calibrations and held-out fields total 253.026 deg². The frozen South PS1 policy covered another 185.468 deg².
- Recovered four North controls at their branch-specific published cuts. The strict North cut yields 0.119 groups per held-out deg² and the primary cut yields 0.420. The South DELVE holdout requires a review of field-dependent contamination before expanding that stratum.
- Ran the exposure-mask seam check, found that the sampled seam has zero duplicate area after regional assignment, and measured the census deep-survey overlap.
- Produced 20 DES-style diagnostic sets including eight high-ranked groups. The two strongest DES responses match Tucana V.

## Next work

1. Apply the frozen South baseline to the remaining PS1-assigned area in disjoint waves. Use the native masks to determine the newly searched area.
2. Extend the North BASS trial after representative blind recoveries and independent review-budget and seam checks. Keep separate South DES and DELVE calibration and evaluation strata for historical comparisons.
3. Use the DES-style diagnostics to review new peaks and archive existing L0 candidates with their public-data evidence. Targeted telescope follow-up and proposal preparation are deferred.
4. Continue measuring image-to-catalog response and compact-system depth benefits where the data support it.

## Validation criteria

- Each completed job records input, configuration, effective area, method and timings. Candidate budget calibration checks the entire planned development cohort.
- Survey measurements use independent samples on identical usable masks with explicit native photometry and search settings.
- Decisions about deeper or combined searches depend on matching the same total review budgets. Use the held-out count and its area after the policy is frozen.
- [Execution status](docs/STATUS.md) records scheduler and input availability.
