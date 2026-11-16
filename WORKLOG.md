# Work log

## 2026-11-16

- Initialized a dedicated project with a clean Git history. Confirmed GitHub identity and active Perlmutter authentication.
- Matched the standalone prompt and benchmark JSON to their ZIP counterparts by SHA-256. The ZIP reports public product checks.
- Wrote the bounded DR11 loader, independent coadd area raster, fixed 37-by-6 A/B scan and candidate C refit. Local numerical smoke check passed projection across RA=0, ranked peaks, dedup lineage and finite C membership.
- First Slurm probe 61392397 exposed missing NOBS_G/R in the brick summary. Replaced that prefilter with positive brick PSFDEPTH and kept image-level nexp checks in both bands.
- Submitted A/B control jobs 61392446–61392448 and a census selection job 61392449 on CPU/QOS shared. Submitted corrected schema probe 61392470 on debug.
- 修正探测 61392470 完成。Boötes I 核区可用 gr 99.626%，951 个 PSF。保留切选表和图。
- 基线盲扫 A/B 恢复 Boötes I 和 Coma Berenices，A 恢复 Pegasus IV。中心诊断及方法误差分别记录。
- 使用 61392448 空闲核运行独立面积筛选，冻结 28.533 deg² 的 PS1 盲场及 3.850 deg² DES 对照。提交基础/加深对照和 96 个条件注入试验。下一步用已冻结评价区域评估审查成本，再查看候选。
