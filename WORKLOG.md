# Work log

## 2026-11-16

- Initialized a dedicated project with a clean Git history. Confirmed GitHub identity and active Perlmutter authentication.
- Matched the standalone prompt and benchmark JSON to their ZIP counterparts by SHA-256. The ZIP reports public product checks.
- Wrote the bounded DR11 loader, independent coadd area raster, fixed 37-by-6 A/B scan and candidate C refit. Local numerical smoke check passed projection across RA=0, ranked peaks, dedup lineage and finite C membership.
- First Slurm probe 61392397 exposed missing NOBS_G/R in the brick summary. Replaced that prefilter with positive brick PSFDEPTH and kept image-level nexp checks in both bands.
- Submitted A/B control jobs 61392446–61392448 and a census selection job 61392449 on CPU/QOS shared. Submitted corrected schema probe 61392470 on debug.
