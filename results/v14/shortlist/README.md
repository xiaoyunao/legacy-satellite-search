# Frozen first production follow-up queue

The queue is 40 priority positions and 35 exploratory region/score-stratified audit positions. All positions are separated by at least 5′. Selection uses eligible R14 A baseline/main/evaluation/primary-budget records and within-cohort score ranks; it does not define a new discovery threshold. The initial alias-contaminated selection is retained separately. Nearby known positions route to context review irrespective of distance alias; unknown does not mean exhaustive novelty established.

Start with `priority_shortlist.csv`, then `review_readiness.csv` and `priority_figures/Pxxx*.png`. The published panels are the highest-C mode for each available priority position; the full retained C mode tables are in `cases/` or `cached_cases/`. All mode images remain locally and on NERSC. `cache_manifest.json` identifies exact same-record reuse, not new evidence. `postfit_context.csv` checks both discovery and refitted centres, including the nearest census object beyond the 30′ shortlist-routing radius.

`priority_visual_decisions.csv` contains only actual, single-reviewer triage. In particular P001's strong C is galaxy-fragment contamination; P007 needs Ursa Minor environmental identification before novelty follow-up. Neither is promoted from L0. Unreviewed positions have no invented decisions.

For identity-blind audit, use `blinded_audit.csv` and opaque B IDs only. Seal visual grades before opening `audit_selection_key.csv`, this readiness index, C/context identity keys or catalogue associations. These 35 objects have not yet been graded. The score-stratified sample and spatial exclusions are exploratory, with nonuniform inclusion. No review-completeness probability or reviewer-agreement statistic has yet been measured.

`archive_checks/` holds bounded metadata results. For P002/P007 the successful NOIRLab query returns only 90Prime/Mosaic3 products, which are not established as independent of the North LS input exposures. CADC errors leave its coverage unresolved. No independently deep two-band population measurement or raw-image download is asserted.

Regenerate the operational index after syncing actual packets:

```sh
PYTHONPATH=src .venv/bin/python scripts/v14_shortlist_index.py
```

`manifest.json` freezes the selection, input mode hashes and production snapshot. Pending C and context jobs do not change the frozen queue. Completed/rejected entries remain in the denominator.
