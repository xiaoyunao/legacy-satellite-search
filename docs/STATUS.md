# Status

## 第八轮 · 2026-11-17

- Perlmutter CPU 完成冻结 A 搜索全部 195 场，实测有效 935.213 deg²。初始数组子任务超时后，保留扫描结果并由 61449552_1 完成 C。61446745 全部补隙任务完成。
- 61451195 完成严格汇总、逐场扫描清单和真实覆盖栅格扣除。271 个主档组，619 个模式均完成 C 拟合，24 个重点组人工审图。剩余合格 PS1 足迹约 1,765.716 代理 deg²。
- 61449606/61450106 完成 survey_14 Gaia、DESI QSO 和两个冻结距离对比。61449743 完成 expand_03 的一次性浅栈定标。61449945、61450917 和 61450711 完成新优先 L0 survey_63 的 PS1、Gaia、DESI 查询及四帧 CFHT r 实测覆盖。
- NERSC 项目为 `$HOME/projects/legacy-satellite-search/revisions/verification-v7`，FITS 和逐源结果保存在 scratch。聚合报告、配置、审查表、附带校验的公开目录来源及图像同步到项目。
- [第八轮科学报告](../eighth_science_report.md) · [Slurm 记录](../results/v8/slurm_jobs.csv) · [实测汇总](../results/v8/rollout/)

## 第七轮 · 2026-11-17

- NERSC 工作目录为 `$HOME/projects/legacy-satellite-search/revisions/verification-v7`。三帧 HSC 原始 FITS 与三个包只在 `$PSCRATCH/legacy-satellite-search/external/smoka/`。档案 MD5、FITS 内部校验均通过。逐源与像素产品位于 scratch。首批及头四批已实扫 49 场、341.739 有效 deg²。
- 61445922 完成 LS/PS1 同一 Gaia 切选，61446174 和 61446676 完成 HSC 深度及局部图像准备，61446586 完成 CFHT 背景环，61446817 检查通量重采样，61447140 完成中心外零点和留出验证后的双色试验。
- 61445835 与 61445946 完成首批九场登记和搜索，61446805 完成冻结汇总及 C 复核。61446055 完成 PS1/DELVE/DES 剩余面积代理。61446606 与 61446637 完成后续登记。
- 74 个 3° 场由 `61446693` 执行，112 个 2° 场由 `61446745` 执行，汇总 `61446828`。已完成的 49 场中，68 个组的 149 个模式已复核。后续状态见 [当前同步快照](../results/v7/slurm_active_at_sync.csv) 和 [本轮报告](../seventh_science_report.md)。
- [候选公开目录审计](novelty_audit.md)

## 第六轮 · 2026-11-17

- Perlmutter 登录与 LS DR11 数据访问通过。项目为 `$HOME/projects/legacy-satellite-search/revisions/verification-v6`。原始文件、逐源、FITS 和峰链位于 NERSC scratch，研究结果按允许名单同步。
- PS1 固定检验 61414189，前景剔除 61415314，Gaia/DESI 初核 61414885，运动学与 PS1 局部 A→C 61416790，匹配掩膜 61414956，CFHT 图像 61415584。Subaru 已查公开头，标定 (g) 科学数据待获取。
- 紧致弱对照 DELVE 7 使用 61415699.0，配对背景使用 61415987。注册 61415505，首批扫描 61415574，第二批及 C 复核 61416781 全部完成。20 个场 168.204 有效 deg²，39 个主档组的 48 个模式已拟合，39 组图像已审查。早期重试记录及最终状态见 [Slurm 表](../results/v6/slurm_jobs.csv)。
- [第六轮科学报告](../sixth_science_report.md) · [扩面登记](../results/v6/registration) · [逐组验证](../results/v6/verification)

## 第五轮 · 2026-11-17

- 选区作业 61404680 已完成，冻结 36 个 PS1 分区块和两个 DES 深搜对照。三批均已完成。首批使用 61404810 的前五个任务和并行分配 61407380，第二批与首批冻结合并使用 61408545，第三批用 61409947。实测面积分别为 339.769 与 20.526 deg²。
- 三批 C 复核及总表为 61408674、61409948、61411315。99 个组、193 个模式及关键图像均已完成。紧致组的质量/PS1 对应检查为 61409662。已同步逐组判断和图像。
- DELVE 弱源扫描 61404654–61404656、固定切点汇总 61404657、盲复核 61407356 与公开成员核验 61408397 完成。锁定测光分级 commit 为 `d7d0250`。
- 四个 LS–PS1 匹配背景作业 61406369、61406370、61405133、61405134 完成。61405130、61405131 的首次运行在写结果时遇到重复字段，修复后重跑。0.25′ 对照、共同预算汇总 61405239 和配对注入 61411109 完成。
- 共享批处理中的重复队列项已撤销。61407330 的首次交互启动因脚本权限退出，改用 `srun bash` 后完成。原始输入、逐源表、成员文件、FITS 和完整模板峰表留在 NERSC。
- NERSC 工作目录为 `$HOME/projects/legacy-satellite-search/revisions/discovery-v5`，大型工作目录为 `$PSCRATCH/legacy-satellite-search/runs/v5`。本机和 GitHub 同步代码、聚合结果和诊断图。[第五轮科学报告](../fifth_science_report.md) · [Slurm 记录](../results/v5/slurm_jobs.csv)

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
