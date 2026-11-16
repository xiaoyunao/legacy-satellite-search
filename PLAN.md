# Plan

## Current objective

Use LS DR11 to detect previously missed faint Galactic stellar systems and measure the gain against PS1 in the census PS1 assignment. See [current scientific direction](docs/PROJECT_MEMORY.md).

## Completed milestones

- Completed v1/v2 real-data pilots, ordinary processing audit, paired depth injections and five PS1 catalog probes.
- Froze disjoint 61.100 deg² development and 60.705 deg² evaluation cohorts.
- Recomputed old field results by sky group and separated spatial detection, correct mode retention and truth-blind highest mode.

## Current execution

1. Run the six new development fields. Calibrate the A configurations together at matched total sky group cost, evaluate B and A/B on the same two controls, and inspect the generated main-branch group cutouts.
2. Compare the three independent samples, LS baseline, LS deeper and PS1, on two joint development fields and two offset known-system fields. Use the same latent population for a small conditional injection comparison. Check position, distance, delivered N and review burden.
3. Isolate three 80 pc failures to test annulus interference, scanning losses and available members. Use two added delivered-member counts at one site to bracket the threshold.
4. Freeze production configuration from the development results, then open the six independent evaluation blocks. Review one diagnostic set per group. Log actual overlap masks, operating area and limits before any footprint expansion.

## Validation criteria

- Each completed job records input, configuration, effective area, method and timings. Candidate budget calibration checks the entire planned development cohort.
- Survey measurements use independent samples on identical usable masks with explicit native photometry and search settings.
- Decisions about deeper or combined searches depend on matching the same total review budgets. Use the held-out count and its area after the policy is frozen.
- [Execution status](docs/STATUS.md) records scheduler and input availability.
