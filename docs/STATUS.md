# Status

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
