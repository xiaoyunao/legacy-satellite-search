# Status

## 第五轮

- 三个弱源扫描 61404654–61404656 已完成。LS–PS1 发回字段冲突已修复，61406369、61406370 替代 61405130、61405131。
- 开发用 0.25′ 对照扫描为 61405232、61405234–61405238，独立标定汇总为 61405239。

- 选区 61404680 已完成。36 个 PS1 分区和 2 个 DES 对照块已登记。覆盖统计目前区分代理面积与计算掩膜有效面积。
- 受控三批的扫描、聚合和复核分别为 61404810–61404812、61404813–61404815、61404817–61404819。最终跨批汇总为 61405179。
- DELVE 3/4/5 的测光全流程控制为 61404654–61404658。双向代理响应试验为 61405130、61405131、61405133、61405134。
- NERSC 新工作目录为 `$HOME/projects/legacy-satellite-search/revisions/discovery-v5`，逐源工作文件位于 `$PSCRATCH/legacy-satellite-search/runs/v5`。

## 第四轮

- 六块独立场和冻结汇总 61400474–61400480 完成。独立条件控制 61400644、61400645 完成。独立场 23 组、49 模式和开发场 18 组、23 模式的 C 复核分别由 61400541、61400540 完成。
- 61402454 完成 Hercules 盲检关联审计。跨巡天选择响应重放 61400619、61400620 完成。
- DELVE 4/5 覆盖预检 61400542 完成。新增匹配场扫描 61400738、61401586、61401587 以及 fresh_05 的重跑 61402598 完成。原 61400737 的 PS1 计数退出错误已修复。更新后的汇总依赖 61401588 完成。
- 核对 20 个任务正常完成、1 个初次失败后重跑。同步 222 张有效 PNG、候选与实验汇总、配置和 manifest，逐源数据和全量峰表保存在 NERSC。
- 工作目录为 `$HOME/projects/legacy-satellite-search/revisions/holdout-v4`，大型结果位于 `$PSCRATCH/legacy-satellite-search/runs/v4`。[科学报告](../fourth_science_report.md) · [作业记录](../results/v4/slurm_jobs.csv)

## 第三轮 · 2026-11-16

- Perlmutter 常规和共享 CPU 分区恢复。核验 18 项第三轮作业完成并返回 0:0。
- 开发场扫描 61395259–61395264，天空组标定 61395362，候选复查 61395411。六个场共 61.100 有效 deg²，含 12 份完成的扫描 manifest。同步 18 个天空组的逐组复查及 66 张诊断 PNG。
- 80 pc 诊断 61395357、61395360、61395361 全部完成。同步真值孔径计数、普通搜索峰链、组标定及投递成员数。
- LS–PS1 对照扫描 61395365–61395368、预算汇总 61395369、配对注入 61395412–61395413 全部完成。同步 12 份配对扫描 manifest、可评估目标的恢复结果和四组注入结果。
- 约 60.705 deg² 独立评价区保留封存。原始 survey 文件、逐源表、FITS、全量峰表和成员数据仍在 NERSC。
- NERSC 工作目录为 `$HOME/projects/legacy-satellite-search/revisions/group-v3`，scratch 为 `$PSCRATCH/legacy-satellite-search/runs/v3`。
- [第三轮科学报告](../third_science_report.md) · [Slurm 完成记录](../results/v3/slurm_jobs.csv)

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
