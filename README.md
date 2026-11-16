# Legacy Satellite Search

A south-only DECam gr pilot using DESI Legacy Imaging Surveys DR11 photometry. It tests whether the released catalog can recover known faint stellar systems and how often equally sensitive searches flag reviewable peaks where the DELVE census uses PS1. It keeps the near/compact branch separate from the main 20–150 kpc experiment.

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
- Within a branch and method, peak merging requires ≤0.5 mag in DM, ≤2 in radius ratio, and separation ≤max(0.5′, 0.75 times the smaller radius). Sky-review groups link retained records across methods, depths and distance hypotheses. Cutoffs are calibrated within each branch and method before any grouping.
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
