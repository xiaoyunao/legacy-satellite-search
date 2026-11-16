# Decisions

## 第三轮

- 用阈值前的天空组直接标定主分支审查成本。组锚点是最高排名假设，关联半径为 max(1′, 两个拟合尺度的较小者)。组内保留距离解释；对照分别统计位置、通过切点的正确距离模式、锚点距离。每个方法或并集方案独立标定总成本。
- 先扫描六个新开发块，基线和加深均运行 A，普通与较优条件对照 fresh_01、fresh_05 加运行 B。新评价区约 60.705 deg²，候选规则冻结后开启。
- 同天区实验采用实际 LS south DR11 与 PS1 DR2 stack，联合有效区与各自原生通带，使用双方均能支持的 0.5–4′ 尺度。Pegasus IV 和 Aquarius IV 用于恢复，fresh_01 和 fresh_03 校准候选负担。
- 宽系统复核固定三个 v2 失败点位。按已归档阈值比较原叠加与隔离结果。一个点检验 28、45、65 个目录可用成员。真值孔径结果供诊断。

## 2026-11-16 · v1 历史

- Use south-only DECam gr to hold selection and bandpasses fixed. Use standard sweeps with RELEASE/BRICKID/OBJID and map actual gr exposure and source mask bits independently of detected stars. Retain CLUSTER and RESOLVED rows and count them and the forced PSF flags.
- Set the initial PARSEC model to 12 Gyr and Z=0.00010 with the tabulated Chabrier IMF integral. A uses a CMD band and exact local on/off counts for proposed peaks. B uses a regularized CMD ratio and compensated disk/annulus with local variance. Its ranking statistic is empirical.
- **v1 峰合并已由 v2 的兼容尺度规则取代。** Lock position matching to max(2 arcmin, truth circularized half-light radius) and DM within 0.75 mag. Merge within max(0.5 arcmin, 0.75 times the greater fitted scale) in each field and method, ranked by score across all DM and scale trials. Preserve the raw-to-merged assignment.
- **峰记录预算保留为假设量，v3 主比较改用天空组预算。** Compare development-set quantiles at 0.1 and 0.3 reviews per effective square degree. Reserve two spatially disjoint PS1 fields for evaluation, one in each condition layer.
- Use a circular truncated fit window and an outer background annulus for candidate C. Allow a small DM and radius refinement and condition on the observed error class and hard sample limits. This is a candidate refit.
- Boötes I 的固定中心 CMD 超额在两带限深增加 0.5 mag 后从 705.6 增至 1205.2。用同一个改动在各 PS1 盲场复扫，并独立为两种深度标定阈值。
- 基线采用 A 做发现。加深设置保留作下一轮优先对照，因 Virgo II 在相同较紧留出审查量下通过切点。外推前需要普通目录处理的弱对照。
- 现在分开记录 Peg IV 的原始 B 峰、被分配的宽峰和通过审查切点的状态。下一次峰合并试验会在新留出区评价。
- A 的极端尾概率饱和已通过稳定对数求和纠正。Boötes I 加深扫描重新执行并替换正式恢复表。先前输出留在 scratch。

## Branch-aware revision

- Use a frozen near/main/far assignment before merging or calibration. The main template nodes span μ=16.50–20.75. Truth cohorts use 20 and 150 kpc.
- Merge within a method and branch when the position, angular scale and distance are compatible. Use the smaller radius in the merge tolerance. Retain each hypothesis in the review group. The v3 rule calibrates the group budget before applying a discovery cut.
- Split PARSEC interpolation by reported evolutionary phase and the explicit equal-integral RGB tip to ZAHB handoff at entry to stage 4 in the pinned CMD v2.7 tables. Preserve the native rows and IMF weights for B, C and injection. [CMD stage definitions](https://stev.oapd.inaf.it/cmd_3.8/help.html) · [PARSEC tracks](https://stev.oapd.inaf.it/PARSEC/Database/PARSECv1.2/readme.html)
- All four old PS1 fields are regression data. Use their old split for reproducible calibration and regression comparison. Reserve newly frozen fields for independent evaluation.
- Audit centre and annulus processing flags on total PSF, CMD and fitted membership. Run Leo Minor I as the previously missing test. Add Aquarius IV and DELVE 3 after their baseline CMD audit showed no forced/resolved/cluster flags in the central aperture. DELVE 3 checks the compact end near the angular-size floor.
- Pair base/deep catalog injections at 50/100 kpc and 10/30/80 pc. The separate 10 Gyr stress check keeps the 12 Gyr search filter.
