# GPT Pro review: requirements and acceptance

The latest full review in “恢复项目进度” was read through the native conversation tool on 2026-11-19 (message ccd8cf29-9690-46ca-87ef-1feae3c309ed; two turns, no older page). The original text is retained in ignored local logs. This checklist paraphrases the user-adopted scientific requirements. It is not a record that every stage is complete.

The stable paper objective is a measured selection function and census increment for faint compact stellar systems. Continue discovery as a parallel scientific outcome. The immediate question is the actual increment near 100 kpc, radii below about 15 pc and target luminosities around −3 to −1.5, including its dependence on observing conditions.

| ID | Requirement | Current acceptance / remaining work |
| --- | --- | --- |
| A1 | Finish queued R14 scans; reconcile historical and native effective area | In progress. Latest terminal-manifest audit: 3,078 complete fields, 13,323.228 new owned deg². Historical area and current incremental area retain separate ledgers. |
| A2 | Separate production, development, alternative channels and budgets | First incremental R14 audit implemented in `scripts/v14_production.py`: main A baseline, evaluation role, primary 0.3 budget only. Historical production eligibility remains to be reconciled; the pooled index is not the final sample. |
| A3 | Report raw peaks, associations, known contexts, C, visual grades and follow-up | `results/v14/production/candidate_funnel.csv` publishes the available stages. Full-grid peak totals have their own scope. Unknown visual/follow-up stages remain blank. C from an excluded record cannot certify an eligible one. |
| A4 | Measure regional review cost without changing frozen cuts | Incremental baseline table uses its candidate inputs' regional-summary area clock. Report score/condition distributions and independent evaluation after all batches complete; preserve boundary-fragment limitations. |
| A5 | Known-source recovery and identity-blind lower-priority audit | Keep the existing recovery evidence. Extend region/score-stratified blinded review and quantify its sampling/decision losses. Empirical review density is not an exact physical false-positive rate. |
| B1 | Choose 3–5 existing South PS1 backgrounds spanning seeing, depth and density | Pending a frozen repeat design using measured site properties; preserve existing seven-site evidence and field identity. |
| B2 | Repeat shared populations near 100 kpc, 3/10/30 pc and turnover luminosity | Pending. Freeze seeds and comparisons before new evaluation; use common masks, cuts and potential populations. Do not enlarge the grid before testing cross-background stability. |
| B3 | Diagnose detection → PSF → photometric cuts → spatial → distance/C | Existing stage tables available. Next analysis must distinguish faint true injected counterparts, neighbor blending, CMD-background growth and losses of distance/C support. Compare catalogue and CCD levels with explicit denominators. |
| B4 | Prespecify a meaningful gain and uncertainty | Before new trials, use the review's proposed >10 percentage-point gain and background-resampling lower interval >0 as an operational positive criterion. Separate within-field IMF realizations from between-field uncertainty; report negative/inconclusive outcomes. |
| C1 | Review 30–50 strongest independent production positions plus stratified low-priority objects | Pending. Choose after production eligibility is resolved; avoid pooling incomparable native scores as global significance. Preserve multimode/fixed-centre, CMD, spatial, shape, strongest-source deletion and known-environment checks. |
| C2 | Publish priority shortlist and existing independent-data availability | Pending. 0706 stays L0 with weak independent population support. No single old archive target should absorb the whole candidate effort. |
| D1 | Densify catalogue injections only after B, calibrate using real CCD response | Pending. Publish conditional regional detection probabilities with clear interpolation/extrapolation limits before claiming a reusable selection surface. |
| D2 | Compare three distinct references | Retain published Tan PS1 DR1 predictions, matched-sky executed PS1 DR2 and DES/DELVE responses separately. Distinguish new area, new photometric information and real detection gain; shared DECam exposures are not independent confirmation. |
| D3 | Physical luminosity, population and uncertainty definitions | Preserve target integrated luminosity and realized IMF total luminosity. Add limited age/Z mismatch trials, regional responses and held-out validation. Low-latitude/high-extinction layers need their own calibration. |
| D4 | Physical response figures and 50% contours | Pending sufficient sampling and independent checks. Do not infer smooth 50% boundaries from unsupported sparse cells. Keep field variation and uncertainty visible. |
| E1 | Independent deep two-band confirmation of a few high-priority objects | Pending shortlist. Measure actual coverage, masks, depth and population support; service failure means unresolved coverage. Continue public novelty checks including Euclid results. |
| E2 | Structure, luminosity and physical classification | Fit distance, size, luminosity and membership for systems with coherent independent population evidence. Keep dwarf/cluster/ambiguous classifications separate. New observing plans or spectroscopy require scientific justification; existing scope uses public evidence. |
| R1 | Reconcile 150 kpc with the formal distance policy | Main production remains μ≤20.75 (about 141.3 kpc). Audit μ=21.0 results and independent regional review cost before adopting a 150 kpc claim; target scientific range remains 20–150 kpc. |
| R2 | Compact angular scales and extraction losses | Retain the measured no-gain result for the 0.25′ experiment. The production minimum remains 0.5′. Revisit only if CCD results identify a specific scale-dependent loss. |
| R3 | Population inference after selection and review completeness | Pending A–E evidence. Use neutral compact stellar systems before physical classification; do not present abundance/radial-distribution constraints prematurely or equate specific-control recovery with population completeness. |

The five paper figure groups are: (1) actual footprint/conditions/census overlap, (2) blind compact-control recovery and failure reasons, (3) physical selection surfaces and uncertainty, (4) catalogue-versus-CCD losses, and (5) independently supported candidates or validated sample/background statistics. Queue/runtime details belong in technical material.

Current commands for completed aggregate products:

```sh
PYTHONPATH=src .venv/bin/python scripts/v14_production.py
.venv/bin/python -m unittest tests.test_v14_production tests.test_v14_continue_audit
```

NERSC metadata follow-up uses `v14_manifest_audit.py` followed by `v14_continue_audit.py`. New retry arrays must be registered with the immutable worklist and SHA256 in ignored `logs/v14-retry-jobs.json`; expanded live scheduler records take precedence over an accounting omission. Actual FITS reads and science computation remain on Slurm nodes.
