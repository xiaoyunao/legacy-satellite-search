# Legacy Satellite Search

A south-only DECam gr pilot using DESI Legacy Imaging Surveys DR11 photometry. It tests whether the released catalog can recover known faint stellar systems and how often equally sensitive searches flag reviewable peaks where the DELVE census uses PS1. It keeps the near/compact branch separate from the main 20–150 kpc experiment.

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
