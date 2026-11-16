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
- 盲场作业 61392821–61392829 完成，冻结 28.533 deg²，外加 3.850 deg² DES 对照。0.3 档基线 A/B 留出峰 3/10，主分支恢复 3/4 和 2/4。
- Virgo II 初作业到时，通过缓存重跑 61393098 和预定加深 61393230 完成。A 加深将 Virgo II 纳入两个预算，较紧档留出峰仍为 1。查明中心大量强制 PSF 标记。
- 从 Pegasus IV 原始 B 峰追溯去重失败。修复强对照二项尾概率在 300 饱和的问题，并用 61393180 重扫。修正后 Boötes I 加深 A 排名第 1。
- 96 次条件注入和 21 条 L0 复核完成。最高 C TS 18.97，剔除前三贡献源后各峰 TS ≤ 2.11。下一轮验证加深收益的外推性，另测尺度感知合并。
- 审计 18 份 manifest、各区有效面积、两档阈值留出密度、每次注入的成员计数和主要诊断图。只同步汇总文件、元数据和 PNG。
