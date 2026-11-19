# First human review package - not yet released

The user will review the cohort after the package is complete. Do not treat the old 33 reusable C/image packets as a completed 75-object human-review release. Do not fill scientific grades automatically. Previous assistant triage remains separate from the user's responses.

The registered denominator is unchanged: **40 priority positions and 35 exploratory anonymous audit positions**. No object is dropped because its fit is weak, its imagery is incomplete or its environment appears unfavorable.

## Package being prepared

- `priority_review.pdf`: measured core/background CMDs with marginal errors and member markers; spatial distribution and fitted contour; native gr images and strongest contributors; radial/DM response; depth, seeing and extinction; all retained C modes, source-deletion statistics and known-object context.
- `blind_phase1.pdf` and `anonymous_phase1_only.zip`: B001-B035 only, with relative spatial coordinates, measured CMDs/errors, usable-area masks and native gr pixels. Field identity, absolute coordinates, regional labels, discovery scores/ranks, C summary scores, known environments, processing-flag labels and earlier decisions stay outside this package. The separate image files have opaque names and stripped metadata.
- Separate blank response CSVs. Priority decisions use follow-up / suspected contamination / known environment / insufficient evidence plus reasons. Anonymous phase 1 records morphology, CMD, spatial evidence, technical concerns and confidence before identity reveal.

The new evidence renderer reuses actual saved C membership and measured photometry on Slurm; it does not refit or change the frozen detection policy. Colour and vertical magnitude errors share g: displayed bars are marginal, not independent. Background CMDs have equal geometric area, so exposure masks must also be inspected. No positive C contributors is an actual outcome, not grounds to insert substitute stars.

## Completion and release checks

1. Every frozen case has every required retained seed represented in its C table and a complete fit outcome; no silent case omission.
2. Full-mode diagnostic PNGs exist, the supplementary measured panels match the C table hash, and the context includes discovery and fitted centres.
3. Both priority and anonymous layouts pass raster inspection; anonymous panel headers and PDF text contain no identity/score/environment leaks. Material image-coverage gaps remain explicitly documented.
4. The assembled `package_manifest.json` first records `materials_complete=true` and `ready_for_human_review=false`. After all PDF pages have been rasterized and inspected, layout/privacy QA sets the final human-release flag. The PDF builder refuses incomplete assembly. Internal drafts go under ignored `results/work/` and are not handed off for grading.

Current scheduler dependencies are recorded in `../priority_execution/jobs.json`. Existing C array 61556312 precedes full evidence job 61558007; context job 61556642 follows C. Package assembly 61558755 follows both evidence and context. Small prototype jobs validate the two real layouts. None of those submission records means full cohort completion.

## Commands

On NERSC, inside the allocated Slurm CPU environment:

```sh
bash scripts/v14_review_evidence.sh --require-all
```

After allowlisted aggregates and PNGs have been synced locally, use the Codex bundled PDF Python runtime or install the optional `review` extra (`pip install -e '.[review]'`). No PDF dependencies are required for search/CCD jobs.

```sh
python scripts/v14_review_pdf.py
python scripts/v14_review_validate.py
# Inspect every contact sheet and representative full-resolution pages first:
python scripts/v14_review_validate.py --approve-layout
# Internal layout QA only; this never marks a cohort released:
python scripts/v14_review_pdf.py --allow-incomplete
```

Keep a separate copy of filled response forms; regeneration never overwrites them. After the user has completed all anonymous responses:

```sh
python scripts/v14_review_seal.py path/to/user_completed_blind_responses.csv
```

The seal binds actual user responses to the final PDF hash. Only then merge scientific judgments and reveal identity/score/context keys to build the final follow-up shortlist. Exploratory nonuniform audit sampling does not directly measure an unbiased review-completeness probability; reviewer agreement still requires independent human assessments.
