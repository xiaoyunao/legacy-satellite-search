# Work log

## 2026-11-16

### 第三轮恢复跟进

- 19:05 实查常规与共享 CPU 分区为 down；19:08 共享作业开始调度。已看到六个开发场、三个宽系统诊断及三块 LS–PS1 场为 RUNNING。
- 重查 Pegasus IV 第 13 个锥的发回数据，第一页尾与第二页首恰有一个相同 objID，其余顺序正常。放行向前推进的等边界，继续拒绝倒序和停滞，保留重复计数。八项本地测试通过。用已校验的相邻页断点续传，Pegasus IV 搜索在其输入就绪时自动释放。
- 六个开发场的 12 份扫描 manifest 与三个隔离注入诊断同步完成。61.100 有效 deg²。80 pc 的 26–28 颗可用成员组在隔离后仍低于旧场切点；一处 45 颗未过线、65 颗过线。
- 同步并核验四块 LS–PS1 场和四套共享潜在成员注入。Pegasus IV 三样本均恢复，Aquarius IV 缺少共同有效中心。四组注入的空间检出结果为 2/4、2/4、3/4。
- 同步 18 个 A 基线组的复核表和 66 张有效 PNG，人工核查 g/r 面板。无候选晋级 L1。核验 `sacct` 第三轮 18 项作业全部 COMPLETED、0:0。更新第三轮科学报告、项目主线与下一步计划。

### 第三轮评审与执行

- 完整读取 GPT Pro 对 `9c3ab33` 的评审。将 `docs/PROJECT_MEMORY.md` 更新为当前科学主线入口。
- 新增 `group_budget`，用 v2 真实峰表的有界前缀重算天空组预算。截断检查通过。A 两种深度均检出 6/7 个位置，旧回归场入组 0 和 5。最高排名的正确距离分别为 2/7 和 4/7。
- 新增 `matched`、`ps1_tiles`、`matched_inject`、`wide_diagnostic` 与 v3 Slurm 入口。已验证 25 锥几何、真实 PS1 分页返回和两套 PARSEC 物理行散列一致。
- 运行 `python -m unittest discover -s tests` 六项通过，`py_compile` 和 bash 语法检查通过。0.90° API 查询超时后收敛到 0.49° 分页；共享任务使用 `sbatch -A desi -q shared` 路由到实际 CPU 分区。已提交脚本读取快照 configs 根层，隔离版已镜像 v3 配置以兼容队列中的脚本；新版脚本直接引用 configs/v3。
- 已同步隔离版到 NERSC 和提交任务。开发和宽系统作业等待 `PartitionDown` 解除，PS1 正在分场下载。实际运行状态见 `docs/STATUS.md`。完成新开发场比较和候选审查后冻结政策，再打开评价场。

### 第一、二轮

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
- Read the latest GPT Pro review and inspected the v1 outputs. Preserved the v1 files and isolated the revised NERSC workspace and scratch peaks.
- Implemented segmented evolutionary loci, branch-specific peak preservation and budgets, position versus DM recovery criteria, candidate groups, C offsets and coadd cutouts. Three focused numerical tests passed.
- Submitted branch-aware Slurm reruns, the 18-source processing audit, paired depth trials and a small real PS1 source probe. The audit found measurable south gr around Leo Minor I and identified Aquarius IV and DELVE 3 as low-special-flag weak comparison objects.
- Ran the branch-aware regression, 26 verified LS manifests, 36+6 depth pairs and an additional six old/new-locus pairs. Local tests covered protected compact solutions, sky groups, alternate strict DM recovery and the RGB-to-HB break.
- Verified 121.805 deg² of new effective footprint with disjoint calibration and evaluation splits. Five real MAST cones were processed as input checks. The first PS1 template parse used DECam field names. Corrected it to gP1/rP1 and verified the probe.
- Inspected three actual C coadd cutouts. A clipped single-brick image of a repeated location was replaced by a WCS-aligned mosaic.
- Shared Slurm partitions went down after the search jobs. Recomputed the final metrics locally from verified scan manifests, the calibration order statistics and only the needed retained/near-benchmark peak hypotheses. Next run a small survey-matched LS/PS1 comparison before expanding.
