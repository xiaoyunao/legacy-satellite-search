# Legacy Satellite Search

This project searches the North BASS and South DECam photometric catalogs of DESI Legacy Imaging Surveys DR11 for faint Milky Way stellar systems. It measures how often the deeper photometry adds recoveries to PS1 at a comparable review cost. The main science sample spans 20–150 kpc and circularized half-light radii of 3–30 pc. South PS1 is the discovery priority. South DELVE and DES overlap fields provide deeper comparison samples. Nearby and distant search branches have their own calibration.


The first complete human-review material is available: [40 priority positions and 35 anonymous positions](results/v14/human_review/README.md), with 202/71-page versioned PDFs, an isolated anonymous image bundle and blank forms. Begin with the anonymous ZIP; seal those judgments before identity reveal. Material QA does not constitute scientific grading or a new-system confirmation.

## DR11 whole-footprint runs

The [current science report](fourteenth_science_report.md) links the freeze hashes, measured footprint, unified candidate index and selection trials. North BASS and South DECam have native gr models. South uses separate PS1, DELVE and DES thresholds, with independently calibrated extension and census-excluded strata.

Run these commands from the home-directory project revision on NERSC. The dispatchers use the already registered field files and submit Slurm data tasks. The `--resume` option fills incomplete array chunks after all prior tasks in the cohort exit.

```sh
export PYTHONPATH=src
.venv/bin/python scripts/v14_dispatch.py south_ps1 --limit 4
.venv/bin/python scripts/v14_dispatch.py south_ps1 --limit 4 --resume
.venv/bin/python scripts/v14_after_scan.py
```

The seven completed CCD backgrounds are summarized by `scripts/v14_native_summary.py`. `scripts/v14_manifest_audit.py` checks registered hashes and completed manifests without loading survey FITS. The manifest-based retry entry accepts a CSV with `cohort,index` columns and a Slurm array task index; completed fields are skipped. On an allocated CPU node, the frozen 0706 checks run with `scripts/v14_0706_catalogues.py` (local modes), `--ps1-fixed` (fixed hypothesis), and `scripts/v14_image0706.py` (downloaded pixels). `scripts/v14_archive0706.py` and `scripts/v14_download0706.py` query public metadata and transfer bounded products to `$LS_SAT_DATA/resources/v14/`. The aggregate products are in `results/v14/0706/`.

For a fresh metadata checkpoint on NERSC, run `scripts/v14_manifest_audit.py --output <new-checkpoint-dir>`, then `scripts/v14_continue_audit.py --output <new-checkpoint-dir> --extra-jobs <job-id>`. The latter reconciles terminal scan arrays with incomplete manifests and retains live retry coverage; inspect `uncovered_retries.csv` before submitting additional work. `scripts/v14_cadc0706_retry.py --origin nersc --output <json>` records bounded GET/POST/health attempts. Run `scripts/v14_bass0706_depth.py` inside a CPU allocation to measure the available native North images with inverse-variance support, optical masks, frozen colour terms and local extinction. Use `--calibration-outer 2.6` to reproduce the first BASS depth pass; the expanded-reference recheck uses the 5′ default. Raw images remain on NERSC.

The snapshot can be submitted on a CPU allocation with `scripts/v14_finalize.sh snapshot`. Released field areas include only completed optical search masks. The HEALPix atlas and planning table carry the sampled footprint proxy separately. FITS, caches and per-star measurements remain in scratch.

The current paper mainline and complete review requirements are tracked in [PRO_REVIEW_CHECKLIST](docs/PRO_REVIEW_CHECKLIST.md). Run `PYTHONPATH=src .venv/bin/python scripts/v14_production.py` to audit the synchronized aggregate R14 baseline/main/evaluation/primary-budget sample. Its funnel and provenance are in `results/v14/production/`; this incremental audit does not replace historical production reconciliation or visual adjudication. Snapshot/catalogue finalization also refreshes it. Register additional retry array IDs with their immutable CSV path and SHA256 in ignored `logs/v14-retry-jobs.json`; continuation checks use expanded live scheduler coverage as well as accounting.

## Current search and selection experiments

The [project memory](docs/PROJECT_MEMORY.md) records the science questions and scope. The [work plan](PLAN.md) defines current tests and acceptance criteria. The [run status](docs/STATUS.md) records completed runs and Slurm IDs. The [thirteenth science report](thirteenth_science_report.md) describes the South PS1 rollout, new matched recovery measurements and the native CCD experiment.

Round 13 uses frozen South PS1 production cuts in `configs/v7/production.json`. Its independent compact-system experiment uses the fixed common-sky costs in `results/v12/matched/` and the observing strata in `configs/v13/matched/strata.csv`. On NERSC, read PS1 inputs through `scripts/v12_ps1_download.sh` with `LS_SAT_VERSION=v13` on a data-transfer node, using the scratch path verified on Perlmutter. Use `scripts/v13_submit.py` on a login node to submit ready fields. The native CCD pilot uses LegacyPipe DR11.1.0 through Shifter in a CPU job. The image trial configuration is `configs/v13/image_trials.yaml`, and `scripts/v13_image_trials.py` prepares and measures injections. Native CCD images, Tractor products and individual source tables stay on NERSC.

## Regional North and South trials

The [eleventh science report](eleventh_science_report.md) describes the regional footprints, North controls, search budgets, and DES-style diagnostic panels. The registered trial cohorts are in `configs/v11/cohorts/`. The North pilot projects a matching PARSEC PS1 model into Bok BASS g and r with the Legacy Surveys colour terms. The two bright-star validation matches and the original template transformation are recorded separately.

On the NERSC v7 revision, use `scripts/v11_regional.sh <cohort> <zero-based start> <count>` within a CPU allocation of one task per concurrent field with four CPUs per task. Preserve the registered `fields.yaml` when resuming. Run `bash scripts/v11_combine.sh <cohort>` after the cohort is complete. Development and evaluation are processed separately for each new survey stratum. Summarize the South PS1 wave using its inherited cut.

Run `bash scripts/v6.sh paper_diagnostic configs/v11/figure_cases.yaml survey63 results/v11/figures` for the archived six-panel example. For a new completed and calibrated cohort, run `scripts/v11_priority_figures.py` in a compute job with the project environment and the named cohort to draw the highest-ranked evaluation groups. PNG, PDF and SVG carry the same diagnostic content.

## Tenth-round independent imaging and compact-system tests

The [tenth science report](tenth_science_report.md) records target-specific archive coverage, the calibrated r depth and the additional matched injection results. The [observing design](docs/survey63_observation.md) documents the photometric limits and instrument ETC. Re-run the public archive metadata audit locally with `PYTHONPATH=src .venv/bin/python scripts/audit_survey63_archives.py configs/v8/survey63_followup.yaml results/v10/imaging/archive_probes.json`.

In the NERSC v7 revision, write the four calibrated CADC CFHT cutouts to `$PSCRATCH/legacy-satellite-search/resources/v10/survey63/cfht/`. The CADC cutout endpoint is `https://ws.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/caom2ops/sync` with product `id=cadc:CFHT/<visit>.fits.fz` and `CIRCLE=356.6369074244 27.95929984997 0.077`. The visit IDs and filenames are in the imaging configuration. The r diagnostic also uses the previously downloaded PS1 calibration cone. Run these commands on Slurm compute nodes:

```bash
bash scripts/v6.sh cfht_depth configs/v10/survey63_imaging.yaml results/v10/imaging/cfht_r_depth.json
bash scripts/v10_compact_trials.sh fresh_01
bash scripts/v10_compact_trials.sh fresh_03
# In a one-node allocation of five tasks with two CPUs per task:
bash scripts/v10_secondary.sh
```

Run the compact-trial summary with `PYTHONPATH=src .venv/bin/python scripts/summarize_physical_trials.py results/v10/compact_trials --fields fresh_01 fresh_03 --compare-depth`. Source catalogs and image pixels are stored on scratch.


## Ninth-round archive and conditional recovery experiments

The [ninth science report](ninth_science_report.md) records the blinded review, calibrated partial NOIRLab g coverage, Euclid footprint, and physical-luminosity pilot. Archive image files, DQ planes and weight maps stay in the Perlmutter scratch directory.

On the v7 NERSC revision, use the archived v4 matched backgrounds and matched group thresholds. Set `LS_SAT_VERSION=v5 LS_SAT_PROFILE=response_v4` when invoking `scripts/v6.sh response_trials`. Pass `--version v4 --archive ../holdout-v4/results/matched --physical-plan configs/v9/physical_trials.yaml` and the field `fresh_05` or `fresh_09`. Run the pair summary with `.venv/bin/python scripts/summarize_physical_trials.py results/v9/physical_trials`.

The optional published census reference uses the pinned author PS1 model, r<22 density map and v2.1 mask. `ls_satsearch.census_reference` uses `xgboost-cpu==2.1.4` in a separate scratch package directory, added to `PYTHONPATH` alongside `src`. Set the same matched profile as `response_trials`. The released model uses the original census thresholds.
The Euclid overlap uses the official Wide and Deep NUNIQ MOCs with the previously measured DR11 masks. Run `remaining_footprint --rollout results/v8/rollout --output results/v9/footprint --moc PATH_WIDE --moc PATH_DEEP` under `LS_SAT_VERSION=v7`. The released MOC download URLs and hashes are in [the probe table](results/v9/archive/euclid_moc_probes.csv).

## Eighth-round candidate and footprint audit

The [eighth science report](eighth_science_report.md) records the completed frozen-policy search, targeted candidate tests and effective-area accounting. See [work log](WORKLOG.md), [plan](PLAN.md) and [scientific direction](docs/PROJECT_MEMORY.md).

From the existing NERSC v7 revision, run the follow-up on a CPU compute node. Use the archived PS1 and Gaia responses or the acquisition step in `verify_candidate` for a new frozen policy.

```bash
bash scripts/v6.sh verify_candidate --gaia-veto --plan configs/v8/survey63_followup.yaml
bash scripts/v6.sh survey14_astrometry --policy configs/v8/survey63.yaml
bash scripts/v6.sh compare_candidate_gaia --policy configs/v8/survey63.yaml
bash scripts/v6.sh image_cmd --calibration-sensitivity
```

For a strict rollout audit, use `summarize_rollout --pal5-track references/published_tracks/pal5.ecsv --output results/v8/rollout`. Then use `LS_SAT_VERSION=v7 bash scripts/v6.sh remaining_footprint --rollout results/v8/rollout`. The [published track](https://github.com/cmateu/galstreams/blob/6a304c05bea7f774390a11082ea127719e99b70a/galstreams/tracks/track.st.Pal5.ibata2021.ecsv) is pinned to SHA-256 `b475bb0729ab07e07a5e63a54469add57615b857df8f5a2bddef760841e90461`. The round fixes the review and association procedure after scanning while retaining the complete frozen search counts.

## Seventh-round archive and expansion

The [seventh science report](seventh_science_report.md) records the bounded HSC and CFHT experiment and the frozen A-baseline expansion. The [novelty audit](docs/novelty_audit.md) documents the public coordinate checks.

The Slurm jobs in `revisions/verification-v7` use the v6 dependencies and the archived v5 candidate inputs. Original SMOKA FITS files and transfer hashes remain in `$PSCRATCH/legacy-satellite-search/external/smoka/`. The verified CFHT cutouts and provisional image stack also remain in scratch.

```bash
mkdir -p logs
sbatch -A desi -q shared scripts/v6.sh compare_candidate_gaia
sbatch -A desi -q shared scripts/v6.sh cfht_cutouts --background-ring
sbatch -A desi -q shared scripts/v6.sh hsc_depth_audit --write-stack
# Submit after both imaging preparations complete.
sbatch -A desi -q shared scripts/v6.sh image_cmd
```

Before submitting any production batch, rebuild its per-batch settings from the corresponding registered fields with `register_batches`, using `configs/v7/rollout` or `configs/v7/gaps` as the destination and configuration root. The actual v7 revision already contains the frozen batch settings. From that revision root, use `scripts/v7_rollout.sh` on Slurm and set the array bounds to the registered profile directories. See [execution status](docs/STATUS.md) for submitted jobs and the report for achieved effective area.

## Candidate verification

The [sixth science report](sixth_science_report.md) records independent PS1 photometry, CFHT imagery, Gaia and DESI follow-up, fixed-policy expansion, and additional compact depth controls. The [registered fields](results/v6/registration) were frozen before opening the new scans.

From the NERSC v6 revision with v4 and v5 results installed next to it, submit the verification modules on Slurm. The raw archives and source tables remain in scratch.

```bash
mkdir -p logs
sbatch -A desi -q shared scripts/v6.sh verify_candidate
sbatch -A desi -q shared scripts/v6.sh verify_candidate --gaia-veto
sbatch -A desi -q shared scripts/v6.sh verify_candidate --gaia-veto --review-local
sbatch -A desi -q shared scripts/v6.sh candidate_archives
sbatch -A desi -q shared scripts/v6.sh cfht_cutouts
sbatch -A desi -q shared scripts/v6.sh mask_controls
sbatch -A desi -q shared scripts/v6.sh depth_followup expand_13
```

The expansion reuses `holdout FIELD`, `holdout combine` and `expansion_review` in each batch working directory with `LS_SAT_V6_PROFILE=batch1` or `batch2`. Reconstruct per-batch settings with the registry:

```bash
export LS_SAT_WORKSPACE="$PWD" LS_SAT_CONFIG_DIR="$PWD/configs/v6"
PYTHONPATH=src .venv/bin/python -c "from pathlib import Path; from ls_satsearch.expansion import register_batches; register_batches(Path('results/v6/registration'), Path('configs/v6'))"
```

After the first batch is combined, the second scan and both C reviews can run in one 96-CPU allocation using `scripts/v6_expansion_allocation.sh`. Actual job IDs are in [the execution record](docs/STATUS.md).

## Controlled discovery expansion

The [fifth science report](fifth_science_report.md) follows the expanded A-baseline search, the compact-control review, and the matched LS and PS1 selection-response experiment. The [expansion registry](results/v5/registration) records fields and immutable policy digests. DES deep controls carry a separate phase in the results.

On NERSC, `scripts/v5.sh` runs each stage on Slurm with the project environment. In a fresh NERSC checkout with the input resources prepared, reconstruct the per-batch configurations from the published registry before submitting the arrays:

```bash
export LS_SAT_WORKSPACE="$PWD"
export LS_SAT_CONFIG_DIR="$PWD/configs/v5"
PYTHONPATH=src .venv/bin/python -c "from pathlib import Path; from ls_satsearch.expansion import register_batches; register_batches(Path('results/v5/registration'))"
bash scripts/v5_submit_batches.sh
```

The submitter links the scan arrays and frozen summaries in order. Each per-batch C review uses the saved significant modes. See [run status](docs/STATUS.md) for the actual job IDs.

## Frozen independent evaluation

The [fourth science report](fourth_science_report.md) records the first independent 60.705 deg² evaluation. The main and auxiliary A-baseline cutoffs are fixed in `configs/v4/production.json`. The holdout runner checks the registered field definition and search recipe. The matching experiment uses its own angular grid and review-budget calibration.

Run these commands from the NERSC `revisions/holdout-v4` checkout with the project environment. Submit the combine step after all six scan IDs complete, followed by mode review once candidate tables are available.

```bash
sbatch -A desi -q shared scripts/v4.sh holdout fresh_02
sbatch -A desi -q shared scripts/v4.sh holdout combine
sbatch -A desi -q shared scripts/v4.sh review --groups results/holdout/sky_group_candidates.csv
```

The independent field IDs are fresh_02, fresh_04, fresh_06, fresh_08, fresh_10 and fresh_12. See [the run status](docs/STATUS.md) for the matched-input acquisition and processing locations. Aggregate outputs and images live under `results/v4/` in the repository.

## Third-round experiment

Read the [current science objective](docs/PROJECT_MEMORY.md) and [third science report](third_science_report.md). In the NERSC revision checkout at `$HOME/projects/legacy-satellite-search/revisions/group-v3`, the v3 wrapper snapshots source and configuration at job start and writes scratch products under `$PSCRATCH/legacy-satellite-search/runs/v3`. Submission and acquisition status are linked from [STATUS](docs/STATUS.md).

```bash
mkdir -p logs
sbatch -A desi -q shared scripts/v3.sh search fresh_01
sbatch -A desi -q shared scripts/v3.sh wide_diagnostic dev_ordinary 5
# Once all six development jobs finish, calibrate and review main-branch groups.
sbatch -A desi -q shared scripts/v3.sh dev_groups
sbatch -A desi -q shared scripts/v3.sh review \
  --groups results/development_groups/all_A/sky_group_candidates.csv --policy A_base
```

For the matched comparison, stage the pinned PS1 mask (compressed file and decompressed FITS) and native model under scratch. Submit `scripts/v3.sh matched FIELD` with `sbatch --hold`, then run `bash scripts/acquire_ps1_v3.sh FIELD JOB_ID` on the login node. The acquisition releases its held job after all pages pass validation. Run `scripts/v3.sh matched combine` on Slurm after the four matched jobs finish. The two `matched_inject` runs use the resulting group cutoffs. Field names, buffer and supported scales are fixed in `configs/v3/matched.yaml`.

Archived comparison reproduces from the v2 summary manifests and de-duplicated peak tables on Perlmutter. Set `--archive` and use a separate output directory.

```bash
sbatch -A desi -q shared scripts/v3.sh group_budget --archive \
  --summary ../branch-v2/results/summary --output results/group-regression
```

The frozen-policy evaluator accepts `--apply path/to/sky_group_policy.json`. Select the production channels and group budget from the completed development experiment before submitting the evaluation blocks.

## Branch-aware revision

The current code writes branch-aware results. See the [second science report](second_science_report.md) for the completed regression, audit and paired results. The original scientific report and baseline files remain under their original paths and are reproducible from commit `4e9f4f2`. The revision is deployed in `$HOME/projects/legacy-satellite-search/revisions/branch-v2` and writes source-level work products under `$PSCRATCH/legacy-satellite-search/runs/v2`. The original four PS1 fields are now regression data.

From the NERSC revision directory with its own `src`, `configs`, `references`, `scripts` and `.venv`:

```bash
mkdir -p logs
sbatch -A desi -q shared scripts/v2.sh search leo_minor
sbatch -A desi -q shared scripts/v2.sh audit
sbatch -A desi -q shared scripts/v2.sh search dev_ordinary
# Submit after the matching background scans have finished.
sbatch -A desi -q shared scripts/v2.sh paired dev_ordinary 30
sbatch -A desi -q shared scripts/v2.sh regression
```

Run `python -m ls_satsearch.paired` in the revision directory after the paired jobs and branch-specific cutoffs are available. `scripts/v2.sh fields configs/fields-fresh.yaml --expansion` selects new disjoint block geometry without evaluating candidate peaks. Keep the new field manifest in a distinct results workspace when evaluating.

### Branches and matching

- Template nodes below μ=16.50 form the near branch. Nodes from 16.50 to 20.75 form the main branch and represent the 20–150 kpc design. Nodes from 21.00 form the far branch. Truth cohorts use 20 and 150 kpc.
- Within a branch and method, peak merging requires ≤0.5 mag in DM, ≤2 in radius ratio, and separation ≤max(0.5′, 0.75 times the smaller radius). Sky-review groups link retained records across methods, depths and distance hypotheses. V2 calibrated its hypothesis cutoffs within each branch and method before grouping. The v3 main comparison calibrates the group count directly.
- Recovery tables report spatial passage and both the original 0.75 mag and stricter 0.25 mag distance match diagnostics. Source audit flags are recorded in total PSF, CMD and fitted membership weights. The sample selection retains these measurements.
- The two depth injection arms share latent stars, local noise draws, positions and mask. Paired recovery groups are conditional on catalog availability. Candidate C uses bounded local centres and retained hypotheses. Cutout generation and scientific assessment have independent status fields.

## Reproduce the original pilot

Use commit `4e9f4f2` for the commands in this section.

Run setup and Slurm submission from the project's home-directory checkout. Shared CFS is read-only. The run writes source caches, full peak lineage, and member probabilities to `$LS_SAT_DATA` (default `$PSCRATCH/legacy-satellite-search`). It writes aggregate summaries and PNGs beneath the home-directory checkout.

```bash
cd "$HOME/projects/legacy-satellite-search"
mkdir -p logs results/summary results/figures
python3 -m venv .venv
.venv/bin/pip install -r requirements-perlmutter.txt
bash scripts/fetch_resources.sh
sbatch -A desi -q shared scripts/slurm.sh bootes
sbatch -A desi -q shared -c 8 scripts/freeze_fields.sh
```

The field selection job writes `configs/fields-frozen.yaml` before running a detector. The repository's final `fields.yaml` records the frozen selection when available. For a new selection, preserve the previous field manifest and copy the frozen file into `configs/fields.yaml` before submitting pilot jobs. To rerun frozen pilot results, use IDs in the committed field manifest. `LS_DR11_ROOT` can override the shared survey path. Materialize the pinned census file on scratch before PS1/DECam comparison jobs by running the field job or decompressing `resources/census.fits.gz` in place.

```bash
sbatch -A desi -q shared scripts/slurm.sh --both-depths dev_ordinary
sbatch -A desi -q shared scripts/slurm.sh --both-depths dev_deep
sbatch -A desi -q shared scripts/slurm.sh --both-depths eval_ordinary
sbatch -A desi -q shared scripts/slurm.sh --both-depths eval_deep
sbatch -A desi -q shared --array=0-3%2 scripts/injections.sh dev_ordinary
```

Submit injections after the base scan of the same field. After the blind scans and controls finish, run `sbatch -A desi -q shared scripts/pilot_analysis.sh` in the NERSC checkout to select retained peaks, produce candidate diagnostics and build the main tables. The injection and plotting commands below also work on the Mac from the synced aggregates.

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python -m ls_satsearch.inject
.venv/bin/python -m ls_satsearch.summarize
```

## Measurement and comparison

- Exact usable-area samples come from the DR11 primary brick boundaries, masks and positive g/r exposure at a five-arcsec equal-area lattice. Pilot uses valid survey assignment bits from the pinned census map.
- Common selection requires valid g/r measurement, S/N ≥ 5, extinction-corrected g ≤ 23.5 and r ≤ 23.0, and TYPE=PSF. Source- and pixel-level excluded mask bits are named in the config and documented in [the release bit definitions](https://www.legacysurvey.org/dr11/bitmasks/). CLUSTER and RESOLVED are retained. The deeper trial extends each working magnitude cutoff by 0.5 mag.
- A proposes CMD top-hat aperture peaks and ranks exact counts by conditional binomial tail. Spatial proposal aperture diameter is based on the common Plummer radius parameter. B uses the same apertures on regularized CMD likelihood-ratio weights and ranks the compensated excess against local weighted variance. Calibrate both rankings against real control fields to estimate whole-scan review densities.
- Both scan 37 distance moduli by six angular scales, with position grid spacing one-third of each scale. The background annulus spans 3.5–6 radii, and the inner aperture spans 1.5 radii. Field buffers admit backgrounds outside the analysis rectangle. Sources and area use the same census assignment rule inside and outside the rectangle.
- Peaks meeting the proposal floor are saved before spatial de-duplication. The scratch-only full peak table preserves each template peak's merged rank. Evaluation matches the highest-ranked merged peak within the frozen spatial and distance tolerances in `docs/DECISIONS.md`. The benchmark JSON holds the original field-level literature provenance.
- C refits candidate richness using a local-annulus background, masked spatial normalization and the CMD density ratio conditional on observed error class. Reported radii and DM from C come from a small grid centred on the A/B peak. Nearby background gradients, unmeasured classification completeness and the conditional error model limit interpretation.
- Cutoffs retain up to the integer review budget in real development fields, then apply to untouched evaluation fields. Count intervals describe sparse review counts under a Poisson working model. Spatial clustering and block-to-block variance can broaden the uncertainty.
- Injections sample the visible tail of an IMF-weighted CMD and a 20 pc circular Plummer profile at 50 and 100 kpc. Local catalog errors and common magnitude, S/N and area cuts determine surviving members. Recovery is conditioned on the number present in the search catalog.

## Locations and outputs

Program, rules and reproducibility docs are in `src/`, `scripts/`, `configs/`, `docs/` and `references/`. `results/summary/` records manifests, cuts, known recovery, matched review costs and candidate statistics. `results/figures/` contains static diagnostics. Slurm stdout stays under `logs/` on Perlmutter. Raw LS measurements, catalogs, coverage caches, full template peaks and candidate-member tables stay on NERSC. Sync only the approved summary tables and figures to the Mac.

Read the [first science report](first_science_report.md) for measured recovery, candidate review and the next experiment. [Slurm accounting](results/summary/slurm_jobs.csv) records control, pilot, review and injection job outcomes.

### Round 12 regional and matched experiments

Keep the existing v7 and v11 production policies. The four-stratum registration uses the plan in `configs/v12/regional_plan.yaml`. The narrower South PS1 supplement uses `configs/v12/ps1_gap_plan.yaml` and the version `v12g`. Each registry records the historical field inputs and hash. Use the saved registries to rerun the exact blocks.

From the NERSC project revision, submit the CPU array with an appropriate Slurm account and launch `scripts/v12_batches.sh <region> <field-count>`. Its index selects eight disjoint fields and skips completed manifests. Use `LS_SAT_VERSION=v12g` for the supplement. After each successful array, use `scripts/v12_discovery.py` on a compute node to apply the frozen candidate policies and review priority groups.

Run `scripts/v12_ps1_download.sh <north|south> <Perlmutter scratch>` from a data transfer node to acquire and checksum the common-area PS1 DR2 catalog pages. The actual Perlmutter scratch path is reported by the login environment. From the project revision on a Perlmutter login node, `PYTHONPATH=src .venv/bin/python scripts/v12_matched_submit.py <north|south>` submits only ready fields. It records submitted job IDs and starts calibration and physical trials when the required inputs become available. Compute steps remain on Slurm. The small selection and paper-figure tables are described in the [round 12 report](twelfth_science_report.md).
## Latest review-driven checkpoint (2026-11-19)

The [science report](fourteenth_science_report.md) and [A–E acceptance checklist](docs/PRO_REVIEW_CHECKLIST.md) track the current measured selection/census objective and parallel discovery work. The [first 40-position priority queue](results/v14/shortlist/README.md) contains actual C tables, images and explicit pending stages; a separate 35-position audit is not yet graded. The [registered three-background repeat protocol](configs/v14_repeat/protocol.yaml) distinguishes 144 planned CCD realizations, nine submitted initial trials and one measured pair. These are not completed physical completeness curves.

NERSC compute commands after entering this snapshot's configured environment:

```sh
# Run through Slurm allocations, not on a login node.
bash scripts/v14_shortlist.sh reuse
# An existing four-shard Slurm array supplies SLURM_ARRAY_TASK_ID.
bash scripts/v14_shortlist.sh 4
bash scripts/v14_repeat.sh smoke
bash scripts/v14_repeat.sh trial
bash scripts/v14_repeat.sh measure
```

These commands reuse registered inputs; first inspect `results/v14/priority_execution/scheduler_snapshot.json` and live Slurm state to avoid duplicating queued work. Keep raw science files on NERSC. After syncing allowlisted aggregates and diagnostic PNGs, `PYTHONPATH=src .venv/bin/python scripts/v14_shortlist_index.py` builds the operational review index; it does not perform or approve human review. The current scripts add no new runtime dependencies.
