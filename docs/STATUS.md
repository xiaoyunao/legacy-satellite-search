# Status

## 第三轮 · 2026-11-16

- 完成 v2 真实归档的天空组重算，保留 v1/v2 原结果。六个新开发块开始排队。独立评价区保留封存。
- 新开发场 Slurm 61395259–61395264；三处宽系统诊断 61395357、61395360、61395361。最近核验均因 Perlmutter CPU `PartitionDown` 待运行。
- 四场 PS1 分页下载已在 NERSC scratch 执行。配对 61395365–61395368 在对应下载通过校验后自动释放。比较 61395369 和共享潜在星族注入 61395412、61395413 等待前置任务。
- 新开发场校准 61395362 与候选诊断 61395411 已提交依赖。当前仅有归档重算的科学结果；新区恢复、LS–PS1 相对增益与宽系统隔离试验结果待计算。
- NERSC 新版工作目录为 `$HOME/projects/legacy-satellite-search/revisions/group-v3`。Scratch 工作目录为 `$PSCRATCH/legacy-satellite-search/runs/v3`。PS1 页文件只存 scratch。
- [科学报告](../third_science_report.md) · [Slurm 快照](../results/v3/slurm_jobs.csv)


## 2026-11-16

- Perlmutter SSH and CFS access verified. Project venv installed under personal project. Input model and census files passed SHA-256 validation.
- The first schema probe opened live standard south sweep and brick catalog and identified the absent brick NOBS summary. The area loader now uses positive brick PSFDEPTH for preselection and coadd nexp images for actual coverage.
- Public GitHub project created. The A/B/point-fit mini scan passed a local deterministic numerical test. Real results are recorded in the run manifests after compute jobs finish.
- 完成探测作业 61392470 与 Boötes I、Coma Berenices、Pegasus IV 基线盲扫。三者均有 >99% 的中心可用 gr 覆盖。A 恢复三者，B 恢复前两者。表中记录距离和位置误差。
- 在 61392448 的计算节点步骤冻结 4 块 PS1 场和 1 块 DES 场。PS1 有效面积 28.533 deg²。原选区作业 61392449 和备用排队 61392521 已取消。
- PS1 盲场基础深度和单轮限深消融作业 61392821、61392822、61392825、61392828，DES 对照 61392829。两组条件注入 61392834、61392835 依赖开发区作业。

## 第一轮结果

- 完成并核验 18 份扫描 manifest。包含 4 个主分支基准的两套深度、UMa III、4 块 PS1 盲场的两套深度和 1 块 DES 对照。PS1 有效面积 28.533 deg²。
- 盲场 61392821、61392822、61392825、61392828 及 DES 61392829 完成。评估及 21 条 L0 的诊断与 C 复核作业 61392884 完成。
- 61392448 到时结束，保留了 Pegasus IV、冻结场和中心诊断产物。Virgo II 基线由 61393098 复用缓存完成，加深由 61393230 完成。
- 61393180 用修正的二项尾概率重跑 Boötes I 加深扫描。61393012 完成单列的 UMa III 近距对照。
- 注入组 61392834、61392835 的八个试验批全部完成，共 96 个注入位置。合并统计在 `results/summary/injection_summary.csv`。
- 当前 21 条审查记录均保留 L0。尚未执行独立观测确认、C 独立全区扫描、北区或 i 波段分析、图像级注入及扩展面积。其他深搜重叠地图保持未知。第一轮实测证据和下一步见 [科学报告](../first_science_report.md)。

## Branch-aware revision

- 26 real scans completed in NERSC `$HOME/projects/legacy-satellite-search/revisions/branch-v2`. V1 results are archived in their original locations.
- Audited 18 benchmarks, reran Leo Minor I, and added Aquarius IV and DELVE 3. Paired jobs 61394241–61394247 completed. Job 61394663 repeated six paired systems for the old/new locus check. Footprint 61394348 froze 121.805 deg².
- Completed selected C review under 61394330. The 73 retained hypotheses form 37 sky groups. 34 fits have diagnostic outputs and three have inspected g/r images.
- Counters and calibration were reproduced locally when the Slurm shared partition went down. The source catalogs, full peak tables and PS1 cone files remain on NERSC. See the v2 Slurm accounting for the cancelled duplicate table job and interrupted auxiliary step.
- LS/PS1 matched-area threshold comparison and new-field candidate scans are next. Actual PS1 acquisition and schema checks covered five cones.
