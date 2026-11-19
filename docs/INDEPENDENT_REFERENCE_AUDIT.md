# Independent morphology and PS1 source-response audit

Scientific question: can the LS PSF proxy used for the empirical PS1 response be treated as a sample of true stars at the relevant faint blue magnitudes? This audit tests that assumption with independent deep photometry and morphology. It does not measure compact-system recovery or replace the 144 native CCD experiments.

## Inputs and coverage

COSMOS2020 Farmer v2.2 / UltraVISTA DR4.1.1 provides HSC gr photometry, ACS `mu_class` and LePhare type. The compressed archive has SHA256 `5e51cb525b4a857681afac92ce21af82fae80ed77eb1db94977c5268d391061d`; 198,942 observed-HSC-g17–25.5 sources were extracted on NERSC from 964,506 input rows. Coordinate aliases in the Phase3 FITS are explicitly normalized. Raw images, source tables and joins stay on NERSC.

Stellar references require ACS morphology class2 and SED type1, HSC flag0, valid positive gr fluxes/errors and quoted flux-SNR≥20. Resolved/SED galaxies require classes1/0; everything else remains unknown. These are independent reference labels, not perfect truth. Farmer uses Tractor, but its model choice is not used as a truth label. ACS morphology and HSC/near-IR observations provide the independent information. The catalogue is near-IR detection selected; bright-star saturation/proper motion, ambiguous matches and faint reference selection remain limitations. HSC magnitudes are observed native-band values, not extinction-corrected DECam magnitudes; quoted errors have not been corrected for correlated noise. See [official column definitions](https://irsa.ipac.caltech.edu/data/COSMOS/gator_docs/cosmos2020f_colDescriptions.html) and [release corrections](https://irsa.ipac.caltech.edu/data/COSMOS/tables/cosmos2020/COSMOS2020_DR4_1_1.pdf).

The first strict LS/census-PS1 mask intersection was uninformative: 29 reference positions, two labelled stars, no supported bins. Diagnostic61583938 found census FOOT128 on192,898/192,929 LS-covered reference positions. Preserve this negative branch. Do not remove FOOT from any production/census mask or reinterpret the external field as census search area.

A separate reference branch uses real PS1 g/r/i stack exposure and pixel-mask images and actual LS WCS valid pixels. Require positive finite exposure and the registered pixel-quality bits, union images within each band, then intersect the three bands. Area is never inferred from source density. Native central-pixel coverage is not a PSF-weighted completeness mask. The PS1 public DR1/DR2 products are3pi, not the Medium Deep stacks ([MAST archive](https://outerspace.stsci.edu/spaces/PANSTARRS/overview)); [image-service and auxiliary-product documentation](https://outerspace.stsci.edu/spaces/PANSTARRS/pages/298812251/PS1+Image+Cutout+Service) and [pixel flags](https://outerspace.stsci.edu/spaces/PANSTARRS/pages/298812335/PS1+Pixel+flags+in+Image+Table+Data) define the acquisition.

## Actual results

| Branch | Native files | Common control area | Labelled stars | Faint blue stars | Supported estimator cells |
|---|---:|---:|---:|---:|---:|
| Four fixed positions |24|0.687282 deg²|2792|212|10|
| Sixteen-position expansion |96|2.132757 deg²|6800|539|21|

Faint blue means observed HSC g22.5–24.5 and gr−0.2–0.6. The expanded branch contains275 held-out faint blue references. Its actual valid area is2.132757deg², not the full nominal1.6×1.6degree box. Source-sampled median LS seeing g/r is1.226/1.316arcsec, and formal observed5σ PSF depth25.228/24.602mag; these are neither uniform-sky completeness limits nor representative conditions for all three CCD backgrounds.

The first branch lacked supported LS-blue estimator cells. The expansion increases coverage in the same field with labels, cuts, matching, source-ID fold seed487489 and magnitude/colour bins unchanged. Preserve both branches. It is an exploratory same-field object holdout, including the already-inspected first subset, not new-sky independent validation.

In the expanded ordinary LS PSF proxies with corrected gr<0.4:

| LS g₀ | Proxy sources | Independent stellar labels | Resolved/SED galaxy labels | Unknown |
|---|---:|---:|---:|---:|
|23–23.5|502|52|193|257|
|23.5–24|1155|37|583|535|

Thus galaxy-labelled fractions are38.45% and50.48% in these conditional samples; unknown sources are not counted as galaxies or stars. This supports the need to account for reference contamination. These broad proxy cells are not the CMD-selected search sample or a measured detector false-peak rate; within-bin colour, errors, reference selection and population differences can also affect proxy-versus-star response. The observed response difference cannot be attributed uniquely to contamination. It is not a calibrated all-sky contamination fraction; matching, IR/reference selection and label errors remain.

Five LS-blue cells support a proxy-mixture versus held-out stellar-reference comparison. Their point differences include approximately−0.11 to−0.15 at faint magnitudes, but all conservative95% per-cell finite-reference-count intervals include zero. These bounds use Bonferroni97.5% exact marginal binomial intervals; they do not cover reference-label, spatial, matching, bandpass or transport systematics, or simultaneous inference over all cells. A stellar-only training predictor additionally requires20 stellar training references; some cells still fail that support rule. Do not assert a statistically established estimator correction from these point differences.

The independent HSC-star response curves demonstrate actual isolated-source selection differences, including PS1 i/morphology losses, under this field's conditions. They are not LS−PS1 system detection probabilities. The joint PS1 response already includes gr, i, morphology and magnitude selection once; never apply those losses again.

## Scientific decision and reproducibility

Physical PS1 transfer remains **unvalidated**: native passband/error mapping, independent-label/reference selection, observation-condition transfer to the three CCD backgrounds and compact-system mutual crowding have not all been validated. Do not insert this field's response as a universal stellar probability or use isolated-source curves as physical ΔPdet. The144 LS trials and their finite-stamp/realized-light limits remain unchanged. No source was promoted, no discovery area added and0706 was not confirmed.

Actual jobs: archive acquisition61582406; PS1 catalogue acquisition61582407; strict test61583502; native-image retry61584655 and reference test61584300; expanded images61585005 and test61585006. Failed archive-alias61582112 and first native ASCII-reader61584237 attempts are retained. Exact protocol/code/parent hashes and execution commands are under `results/v14/repeat_full/cosmos_reference/`. Original executed sources are archived where later helper changes would otherwise obscure their hashes.

On a NERSC compute node with the project environment and `LS_DR11_ROOT`, `LS_SAT_DATA`, `PYTHONPATH=src:.` set, the expanded coverage/validation commands are:

```bash
.venv/bin/python -m scripts.v14_cosmos_native_coverage --config configs/v14_cosmos_reference/native_coverage_full.yaml --output results/v14/repeat_full/cosmos_reference/full_native_image_coverage
.venv/bin/python -m scripts.v14_cosmos_validate --native-coverage results/v14/repeat_full/cosmos_reference/full_native_image_coverage/manifest.json --output results/v14/repeat_full/cosmos_reference/full_native_image_coverage_validation
```

The aggregate-only summary/figure can run locally without source data:

```bash
PYTHONPATH=src .venv/bin/python -m scripts.v14_cosmos_reference_summary --source results/v14/repeat_full/cosmos_reference/full_native_image_coverage_validation --output results/v14/repeat_full/cosmos_reference/full_native_summary
```

The next decision is whether a bounded, condition-matched independent reference can validate the remaining response assumptions. More estimator complexity cannot recover absent truth labels or establish PS1 cluster-crowding response. Keep full-search/C/area closure and the final one-time review moving in parallel.
