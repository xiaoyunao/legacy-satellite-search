# Decisions

## 2026-11-19 Human review is a distinct user stage

- Latest 46d21aad review and the user's explicit handoff condition require a complete 40-position priority PDF and 35-position anonymous PDF/image ZIP before human grading. Standardize actual observed errors, member markers, spatial contours, native images, full C-mode tables, deletions and context. Do not substitute assistant triage for the user's responses.
- Anonymous phase 1 hides absolute positions, cohort/field identity, score/rank, C summary statistics, previous decisions and identity-bearing processing/environment labels. The image renderer uses explicit opaque labels; the ZIP strips image metadata and excludes keys/provenance paths. Seal user-supplied phase-1 judgments before revealing identity, then assemble the final follow-up shortlist.
- Final PDF creation refuses missing/mismatched material; incomplete layout drafts stay ignored. Preserve released PDF hashes and any existing response files. Rendering prototypes are real saved C measurements, not simulated review evidence or completed human grades.
- To implement the requested review priority, temporarily lower six registered bulk-scan parents by positive Nice +1000. Existing allocations/retries/unrelated work remain unchanged. Record original Nice values and register an after-C restoration guard with failure handling. Reversibility is an execution requirement, not a new scientific threshold.

## 2026-11-19 Shortlist and registered repeat pilot

- Adopt latest af4ec677 review: prioritize a current 30–50-object shortlist ahead of full-footprint completion. Freeze 40 priority plus 35 exploratory stratified audit positions from eligible R14 production, within-region ranking and 5′ separation. Low-score spatial exclusion means no unweighted claim of global review completeness. Preserve the initial alias-contaminated selection and final frozen queue separately.
- Known-position distance aliases near NGC 6341/1261 exposed a context gap: unknown prioritization now routes every ≤30′ known positional neighbor to context/control review irrespective of DM. This changes follow-up allocation, not discovery cuts or physical membership. P001 is retained after adverse image evidence, not silently removed.
- P001's C centre moved into an SGA ellipse despite its discovery centre being outside. Annotate both centres/modes. Actual galaxy fragments explain why top-three deletion alone does not guarantee a stellar system; no automatic L1 gate based on C.
- Reuse complete same-record C packets before recomputation. Record original source hashes; reuse is neither new measurement nor independent evidence. Keep identity keys separate from blinded grading.
- Freeze three-background 100 kpc repeated CCD pilot in a new namespace, retaining all old products. Native/PS1 templates must share physical rows; each new realization gets a distinct deterministic source-photon seed, with the legacy seed preserved for older experiments. Store finite-stamp truncation and target/realized light explicitly.
- Source-level PS1 holdouts are conditional diagnostics. Full-field response is not automatically local-CCD calibration; retain the separate 20′ check. Physical LS−PS1 comparison awaits supported, validated source response with uncertainty/bounds. Same realization IDs across backgrounds require joint ID resampling, not independent draws by field.

## 2026-11-19 完整评审落实

- 完整读取最新 GPT Pro 评审后，采用“选择函数与普查增量”为稳定论文路线，发现工作继续；按 PRO_REVIEW_CHECKLIST 逐项验收，不以发现数量替代科学判据。
- 正式生产审计首先发布可追溯的 R14 增量子集，历史结果另待资格/面积核对。筛选限定 main、A_base、pilot_eval、0.3 档；仅同一合格 detection_id 的成功 C 计为该记录复核。开发和替代档位保留在总索引。
- 分母用与候选区域汇总相同的 completed evaluation field 时钟。全距离原始峰/去重峰只作为各自口径的计数；它们不能与 main-only 候选串成未经校准的条件概率。缺失人工审查和未标定分区留空。
- 当前正式 μ 上限保持 20.75，不能等同于覆盖已校准的 150 kpc。0.25′ 的既有无额外恢复结论保留；是否缩核由真实图像损失证据决定。
- 已观察到 sacct 漏列一个仍排队的数组元素。补跑判断必须纳入展开 squeue；新增 retry parent 与不可变 CSV/hash 登记，使后续审计识别它，避免新补跑再次成为“无覆盖”。未知状态和改变的工作清单仍拒绝自动推断。


## 2026-11-18 续跑与独立深度核验

- Slurm TIMEOUT 不能计作恢复成功。终止数组与当前缺失 manifest 交叉后，再扣除活跃主数组/补跑覆盖；只有仍无任务覆盖的场才生成新补跑清单。未知 Slurm 状态中止资格判断。
- 全区汇总排队时，已完成分区可单独更新候选索引与图册；严格保留候选输入、已扫掩膜和图册采样三者的时间/范围差异。
- 极区修复只裁剪矩形包围盒的物理纬度上下界；源投影对球面外像素继续返回无效值。扫描网格、原生掩膜和阈值保持冻结，绘图重放与科学扫描分开验收。
- CADC 查询失败不转为无覆盖。采用官方 GET/POST 端点，从本地与 NERSC 独立网络出口检验 ROI 与健康查询，并保留每次请求和错误。
- BASS 与 South DECam 的观测相互独立，LS 处理家族相同。直接测原生 gr 图像、invvar 和 optical mask，以本地 Tractor 透过率去消光；用冻结 PS1-to-90Prime 色项校准。不能把砖级名义深度当作此次孔径深度或星分类完备度。

## 2026-11-18 恢复规则与独立星族检验

- 补跑集合取终止失败 Slurm 任务中的登记场与缺失/非终态 manifest 的交集。完成场及 no-usable-gr 场沿用已有产物。资源调整响应实际 OOM，保持原科学配置与种子。
- HOME flock 返回 524 后，所有汇总进程共用 scratch 上实际验证过的文件锁。发布文件继续保存在个人目录，并同步本地。
- 0706 使用冻结 ICRS 位置、μ=19.25 和 0.5′ 空间尺度。独立 BASS、PS1 目录与公开像素各留原始测量证据。PS1 图像的重新测光和 PS1 目录共用曝光。NOIRLab 新曝光只有 i，星族结论依赖覆盖、深度、跨通带误差和共同序列。

## 第十四轮全足迹搜索

- 冻结 A 使用各区已标定的原生 g/r 模型与阈值。低银纬、消光较高、条件异常和 census 掩膜外环境采用各自独立开发片区。旧掩膜内真正完成的像素才从新所有权扣除。
- 预注册使用 NSIDE 512 正式 census 与砖元信息；有效面积由完成作业的 5″ 搜索掩膜统计。栅格与整个砖可用性的联合采样单独用于全天图。
- 独立候选索引保留 5′ 内关联边。自动归组需要位置、尺度和距模相容，采用组内全对相容，待成员和形态审查。已知源位置与距模检查、30′ 环境、SGA 三倍椭圆、人工图像判定分列。
- 真实 CCD、等审查成本共同天空目录和作者 PS1 DR1 模型各自产生统计分母。群体约束依赖区域完整度与候选复核完整度。

## 第十三轮分层 South PS1 搜索与原生 CCD 试验

- 生产发现继续用 A 基线及其两档阈值。先选互斥四种宽度，再将碎片分配给互斥天球单元。所有权仅筛选峰中心和面积分母。计数孔径和背景环使用原曝光掩膜。已审查中心保留历史发布归属。
- 跨巡天配对用 100、150 kpc，3、10、30 pc，期望合成 V 代理 −3 与 −1.5；每场每格两次 IMF 采样。三对南北背景共享潜在星族和测量噪声抽样；天空有效位置各自选取。采用第十二轮各区各臂的固定审查阈值，以更深臂单独测留出审查成本。
- 原生 CCD 试验在两块 South PS1 和一块 North 真实校准图像上执行。用容器中真实 PSF、WCS、曝光权重和源 Poisson 噪声注入，用同一管线输出的空白目录区分新增源和既有源。CFS 数据只读。统计采用固定匹配半径，保留对既有源混叠的条件依赖。
- SGA 椭圆与 M33、Hercules、Palomar 14 的文献位置用于标注环境。位置接近不决定成员身份。生产掩膜和阈值沿用冻结值。发布只同步量化汇总、诊断图、策略及输入检验记录。

## 第十二轮紧致系统主线与实验版本

- 冻结 A 原生通带和独立区域生产策略。South PS1 与 North 优先，South DELVE/DES 作为重叠对照。原生产主分支 μ≤20.75。μ≤21.0 的试验从完整原始峰重做合并和阈值，单独记录历史回放与新评价。
- 注册使用实际砖边界及 gr 元数据、|b|≥25°、E(B−V)<0.10、南北分界及互斥历史核心。South PS1 3° 核心仅找到 7 个符合条件的缺口，额外注册 31 个 2° 核心。有效面积从曝光和掩膜量得。
- Tan Table 8 的全部六对象在扫描后按已固定的文献坐标和圆化尺度核对。延用历史 2′ 下限，另记录真实偏移、偏移与半径比及严位置和距离匹配。PS1 DR1 发表模型与内部 PS1 DR2 使用各自阈值。
- 真实图像抽取用 Gaussian PSF、局部实测噪声和空图峰控制。目录配对重放使用原生 g/r 模型、共同潜在 IMF 与保留的 V 代理总光度涨落。候选阶段仅使用公开成像和文献。
- 北区和南区 PS1 的冻结审查成本接近此前独立结果。DELVE 重叠场的实测成本高，优先查 Hydra II 等重复横跨尺度的响应。M 106、NGC 3184 及 LMC 外缘记录为已知背景，原始发现分数与统计分母继续保留。
- 新 South PS1 组在 LS 中的近距峰保留。真实 PS1、Gaia 对照与独立 DECam g 像素均完成目标级检验，证据等级为 L0。其最强的距离解位于主样本外。
- 两个深度臂的总体差值均缺乏稳定增益。μ=21.0 保存已冻结的独立实验，正式采纳依赖目标区域的检出变化和候选复核。当前条件选择函数供比较与诊断。

## 第十一轮南北足迹与审查

- North 使用原生 BASS gr，以 PS1 同源等龄线应用官方 90Prime 色项。North 与 South 使用传统分界；历史 South 结果按原掩膜保留。新核心与历史注册区块几何去重。
- South PS1 延用生产 A 阈值。North、South DES 和 South DELVE 各自留出评价，保存阈值、经验审查成本和来源。后续 South 边缘注册需要砖边界内的 gr 覆盖代理，正式面积用实际曝光及掩膜。
- 稀疏候选继续对照可直接取得的公开数据，保留 L0 与多解档案。望远镜后随、曝光方案和申请已移出当前计划。
- 用 DES 风格图检查星场、非点源、背景与掩膜。平滑密度和逐点计数统计分别计算，只有完整搜索及校准用于发现分级。

## 第十轮候选确认与远距紧致增量

- 优先下载覆盖 survey_63 核心的独立深 g。用实际产品掩膜与空孔径检验覆盖和深度，分别记录档案无匹配、查询权限和待核实的产品。已知浅 DECam g 结束定量分析。
- 四帧独立 CFHT r 达到近距试验所需初步深度。若检验 μ≈21 的暗主序，应补新 g 和 r。冻结中心、核心、背景环和三个距离模式；采用原生通带与图像注入评估双色星族结果。
- 在额外两个已有匹配测光背景重复 100–150 kpc、10/30 pc、期望光度代理 −3 的事先固定试验。采用原四场等审查成本切点，继续报告背景偶合、位置过线、正确距离模式和首选模式。两块背景同时属于既往阈值开发样本，统计结论限定为条件响应。
- 对五个疑难组应用统一公开 PS1 局部试验。DELVE 4 和 7 延续原先的下游、上游对照角色。

## 第九轮档案与科学增量判据

- 优先复核 survey_63 的主序和距离多解。和原搜索逐曝光去重。使用真实 CCD WCS、DQ、权重和孔径边界判定独立图像能否进入联合分析。保留 562858 的实测边界。
- 以 24 个分层样本和弱系统对照校准人工分级。继续使用冻结发现器，保留疑难队列供第二遍复核。分别记录上游落选和下游人审降级。
- 跨巡天物理参数先导保持相同生成星和真实背景。用同成本 PS1 DR2 内部对照量化目录条件差值，同时另列发表 PS1 DR1 模型。完整度外推依赖目录检出和混叠的实测响应。
- 以官方 Euclid 成像覆盖更新剩余 PS1 区域的次序。历史深搜边界未知的场保持现有证据标签。

## 第八轮候选与覆盖判据

- 使用公开固定谱线分类检查 `survey_14` 的背景类星体，在相同中心、尺度、距离与有效掩膜上对 LS 和 PS1 都剔除该源。报告保留初始、Gaia 前景排除、再排类星体三种记录。
- `survey_63` 作为最优先验证的 L0。冻结 LS 坐标、角尺度和距离模数，再取 PS1、Gaia、DESI 与公开文献。PS1 的空间响应并入证据，但成员与 CMD 支持仍需独立验证。相邻模板分组保留在正式审查账目中。
- 对 `expand_03` 只完成一次浅栈经验通带与位置修正试验，留出数据决定是否采纳复杂零点。确认主序的验证转向有足够 g、r 完备度的独立成像。
- 扩面在原 195 场登记范围内执行。已知球状星团和矮星系几何/距离判据与已发表 Palomar 5 轨迹用于结果注释。未知历史搜索掩膜保留未知状态。

## 第七轮档案与扩面

- LS 的候选信号在一致 Gaia 排前景后仍在。HSC＋CFHT 暂定双色结果在 56 与 100 kpc 均缺少共同星族证据，保留 L0。深层定标与完备度决定后续复验价值。
- 由全中心间距改为新一批中心搜索矩形去重。两个尺寸加上首批共冻结 195 场，允许部分有效覆盖。正式扫描台账继续使用原切点、测光、模板和掩膜。
- 新颖性核查按候选持久化并保留公开覆盖边界。后续投稿前重复锥检索和近期文献核对。

## 第六轮独立验证

- 候选有独立位置响应、较弱的共同星族距离证据以及明亮混入。等级保留优先 L0，以深 (g-r) 核心与同条件背景的主序增量作为后续分级依据。
- 两项掩膜近邻比例的逐场区间覆盖零。保持 A 基线切点、掩膜、分组和 C 复核。保留环境注记以便后续累积对照。本轮新增 168.204 有效 deg² 的主档工作量为 0.232 组/deg²。扩面继续采用冻结策略，优先记录真实历史深搜覆盖。
- 两个补充背景中加深的增量仅见于其中一块，真实 DELVE 7 缺少文献距离相容的过线模式。继续定向测试紧致范围，保留 A 基线作为生产。

## 第五轮盲搜后的决定

- 固定阈值扩面完成。以 339.769 有效 deg²、96 个主档组的实测成本支持继续使用 A 基线。大掩膜边缘和 M33 等已知环境保留在真实审查计数中。
- 优先验证 `expand_03-A_base-0.3-003`。已有独立源识别与收紧 LS 切选的稳定性，星群整体待独立 CMD/空间验证。
- 24 对结果支持在紧致条件下复验加深。0.25′ 细网格未增加空间恢复，保留为开发设置。

## 第五轮弱源审查

- 三个控制均达到测光跟进档。五个入选组对应三个已知系统。保留初始组数和成员级重叠证据，把同一天体的多个响应合并为一项人工跟进。
- DELVE 4 的两个近邻距离解释都保留。未来未知系统的跟进优先级共同参考点源形态、核心 CMD、空间聚集和去除强贡献源后的残余。

## 第五轮登记

- 扩面维持原冻结 A 策略。通过 census 分区、独立测光质量代理和高银纬筛选，分三批推进。两块 DES 深搜对照不计入面向 PS1 的新增有效面积。名义成像重叠只作分层标签，精确既往搜索深度未知的块保留未知标签。
- 对 DELVE 3/4/5 逐模式生成与未知候选一致的诊断。先保存基于图像、CMD、局部聚集及高权重源的审查判断，再对照公开成员。去掉前三源的结果提供证据脆弱性，综合判断保留真实稀疏系统的跟进机会。
- 新配对试验以 50 kpc、10 pc 和 100 kpc、15 pc 两组为紧致弱源的局部检出压力测试。用同一潜在星族和标准化随机数。双向代理形态响应以已有检测和两巡天匹配参考样本为条件，无法单独估计全目录进入概率。

## 第四轮实测决定

- 固定 A 基线在 60.705 deg² 独立评估中产生 23 个主档组，盲恢复 Hercules。保持已冻结的发现流程。已知系统关联保留原候选计数，另作科学鉴别标注。
- 多模式 C 保留逐假设拟合并检查源的脆弱性。目录中只有 Hercules 对应组在排除三颗贡献源后保持强信号。未关联组保留 L0。
- 实测同成本差异目前限定于 DELVE 4/5 两个紧致对照。后续优先测试这种参数范围及源选择，双边均校准后再考虑 0.25′ 研究分支。

## 第四轮冻结

- 采用 A 基线为唯一独立发现策略。固定主切点 6.137901371660258 与辅助切点 6.9232059661508565，策略保存在 `configs/v4/production.json`。开发档位对应的组数作为标定来源，独立场不调整切点。
- C 以过线距离—尺度假设为逐个起点，固定局部调整及前三贡献源去除诊断。候选图像缺口单列。目录选择响应与同天空 LS–PS1 的 0.5′–4′ 搜索使用独立标定。
- Pegasus IV 是三套已发布目录的功能与参数对照。旧中心 CMD 基线样本 64 颗里 51 颗标记为强制 PSF。DELVE 4/5 先检查共同掩膜，可评估时按当前最小 0.5′ 核作紧致对照。

## 第三轮实测后的决定

- 保留 A 基线作为主分支生产备选。开发场同预算下，加深和并集改变了候选位置并增加组内假设；基线 18 组复查均为 L0。独立评价仍在冻结后开启。
- 保留 80 pc 低成员数范围的敏感性边界。原峰通过合并，隔离复跑只在一个点产生 0.036 的分数变化；增加可用成员提高了过线分数。当前保持搜索器。
- 同天区只计可评估的恢复对照。Pegasus IV 可用，Aquarius IV 有效中心被联合掩膜排除。后续选择更多同覆盖的普通处理弱系统再估相对探测能力。

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
