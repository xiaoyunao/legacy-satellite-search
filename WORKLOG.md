# Work log

## 2026-11-17

### 第十一轮南北分区与 DES 风格诊断

- 完整读取 GPT Pro 对 `07a04f7` 的评审，候选保留公开档案证据，后随移出当前计划。实现原生 North/South 输入和 BASS gr 模板。四个 North 普通盲恢复均过各自发布档；420 个 PS1 亮星对应源验证颜色项。
- 61459498 固定 56 个互斥核心。61459554–61459560 全部扫描完成；North 253.026、South PS1 185.468、South DELVE 68.083、South DES 67.467 有效 deg²。61459725/27/28 初次汇总遇到 YAML 数字键在 JSON 清单中字符串化，归一化后重跑完成，无需重扫。
- 61459712 核对 census 重叠，South 代理面积 67.7% 属于 DES+DELVE。61459805 验证最近砖深度外推；未来用砖边界检查。61459831 在 1.5° 接缝方场测得组合后零面积重叠。
- 61459604 生成 12 套三种格式的大图、紧致放大和控制图。North 留出主档 0.420 组/deg²，严格档 0.119；保留两个冻结档。61459943 完成分区优先图并识别已知 Tucana V。核对产物发现小数档位的文件名被误作后缀，修复后用 61460256 重导出八套。继续 South PS1，额外检验 North 接缝和 DELVE 审查率。
- 本地 18 项单元测试、Python 编译、shell 语法、区域交集和图格式校验通过。

### 第十轮 survey_63 深成像与配对试验

- 完整读取 GPT Pro 对 `aac2ad6` 的评审。优先调查 survey_63 核心独立深 g。用 `scripts/audit_survey63_archives.py` 保存 Gemini、MAST、HSC-SSP、SMOKA 和扩大 NOIRLab 结果；查验正控制。当前公开产品无合格像素，WHIGS 实际访次待查。
- NERSC DTN 下载四帧 CFHT r 的宽切图。61458390 跑 `cfht_depth`，核心与控制环两次完整孔径覆盖 100%/96.9%，r₀ 深度 24.16/24.34。按官方 ETC 查询编制独立 g/r 观测方案。
- 61458469/70 因运行器指向 v6 的配置目录退出。显式固定 v3 背景配置并比对 v4 搜索策略。61458572/61458618 完成 16 个远距配对，位置检出为 7/12/11。修复 PS1 响应的零生成成员边界，加回归测试。
- 61458992 下载并核验官方 UNIONS 规划 HEALPix，接触核心的 4 个像素均为 0。61458979 完成五组 PS1 复核，全部 L0。因共享队列等待，将 61458659 和 61458731 改为 CPU 交互分配。
- 本地 14 项回归单测、Python 编译、Slurm 脚本语法通过，第九轮汇总逐字节重放。第十轮聚合结果与图按白名单同步。
- 下一步争取独立深双色，实测图像检测、混叠和形态响应，再用条件相同的未参与阈值标定背景检验增益。

### 第九轮独立档案、盲审与选择响应

- 完整读取 GPT Pro 对 `6e9d20b` 的评审。冻结 24 组分层样本和弱对照。盲判先提交 `69da653`，再揭示。19 组低优先、5 组疑难。DELVE 3/5 通过，DELVE 4 为疑难，DELVE 7 归上游。保留复核列表。
- SMOKA、CADC、HSCLA、Euclid、NOIRLab 档案实查。HSCLA 401，Computer Use 两次初始化超时。NERSC DTN 下载独立 DECam g CCD、权重和 DQ。61453320 与 61454040 核验与 DR11 重复的曝光；61453646、61454273 测量 WCS，61454570 测量有效孔径覆盖和空孔径深度。仅 51.7% 核心可用，5σ g₀ 约 23，保留 survey_63 L0。
- 61452821 使用 Euclid DR1 官方 MOC 重新计算剩余 PS1 代理面积，重叠 4.511 deg²。Gatto 等三处新系统已进入公开新颖性核查；其发布中心在 Wide MOC 中全部通过正控制。
- 61453177 在真实背景的冻结注入位置计算作者发布的 PS1 DR1 模型概率。61452683 完成全距离网格试跑，61454095 按匹配标定的主距离分支复算。正式比较使用后者的等审查成本结果。32 对位置检出为 20/24/19（LS 基线/加深/PS1 DR2）。
- 重放 `scripts/blind_triage.py` 映射哈希、核对 Euclid 正控制和面积守恒，运行 Python 编译与 13 项单元测试。下一步以深 g 确认和少量实测图像注入校准为主。

### 第八轮候选复核与扩面验收

- 完整读取 GPT Pro 最新评审。冻结 `survey14.yaml` 的双距离检验及 `survey63`、`survey51` 的独立目录条件。保持生产 A 搜索、掩膜与阈值冻结。
- 61449606 完成 survey_14 Gaia 与共享掩膜测光。61449743 的 DESI 交叉匹配识别 QSO。61449857 第二步提前中止，61450106 完成双目录统一剔除检验。
- 61449743 完成 expand_03 HSC/CFHT 颜色、孔径和空间项测试。两个固定距离的 C TS 为零。CADC TAP 返回标定 r 曝光，限定仪器中心锥未见匹配的标定 g。
- 61449945 完成 survey_63 和 survey_51 的 PS1、Gaia 与 DESI。61450917 完成 survey_63 亮切选与 PS1 局部 C 多模式。61450711 下载四个 CFHT r 小切图，全部覆盖冻结中心。SIMBAD、VizieR、UCC 及文献中心结果见 `docs/novelty_audit.md`。
- 61446693_1 的 A 产物完整、初次 C 超时；61449552_1 重新完成该批 C。61450142 的预览验证了覆盖栅格扣除。61451195 完成严格汇总、逐场 A manifest 与 C 模式核对。195 场 935.213 有效 deg²，619 个 C 模式，24 个重点图像审查。
- 验证用 `.venv/bin/python -m compileall -q src scripts/novelty_audit.py`、`.venv/bin/python -m unittest discover -s tests` 与 `bash -n scripts/v6.sh scripts/v7_rollout.sh`。同步限于版本配置、聚合论文/搜索结果与诊断图。
- 后续优先核实 survey_63 独立双色星族与距离，并按已审查负担决定下一次登记范围。

### 第七轮档案取数与扩面执行

- 完整读取 GPT Pro 最新评审。通过 NERSC DTN 取得三个 SMOKA 包，原始 FITS 和校验文件位于 scratch。三帧 CHECKSUM/DATASUM 通过。
- 61445922 完成 LS 与 PS1 统一 Gaia 切选。LS 100 kpc C TS 21.765，进一步去掉两个自行不相容亮源后为 17.432。
- 61446174 校验 HSC 两帧暂定 g₀,5σ=24.29。61446586 完成 CFHT r 背景环覆盖。早期双色程序因 PS1 坐标占位值退出，随后修复并验证。更换重采样网格时发现需按像素面积保留通量，补回归测试，61446817 重算像素面积后发现共同环带仍有光度尺度偏差。61447140 用中心外匹配和留出验证完成叠加零点，最终 g₀,5σ≈23.64。独立计数有弱反差，C 共同星族证据弱。
- 执行 SIMBAD、VizieR、UCC 和文献中心比较。审计文档及带日期的结果表在仓库。
- 61445835 登记 9 个高覆盖率场，61445946 实扫，61446805 合并和复核。61446055 完成覆盖代理估计。61446606、61446637 相继登记 74 个 3° 场和 112 个 2° 场，随冻结配置保存结果。
- 61446693 和 61446745 分批运行扩面，61446828 为依赖汇总。已验证历史字段去重、冻结配置和队列状态。

### 第六轮独立候选验证

- 完整读取 GPT Pro 对 `8f96b23` 的评审。先冻结候选位置、星族尺度、PS1 切选及对照，随后获取独立目录。PS1 61414189 和统一 Gaia 前景剔除 61415314 完成。61416790 补齐局部 A→C 多模式与亮源自行差。
- 61415584 核验四个有效 CFHT r 切图。Subaru SMOKA 精确到 CCD 的公开头信息支持三个候选核心 g 曝光，标定科学像素待取得。DESI DR2 目标匹配为零。亮源污染和距离多解并存，保留优先 L0。
- 61414956 完成 96 组掩膜随机对照。2′ 内实测 61 组，匹配随机期望 54.15，逐块区间跨零。维持生产掩膜。
- 61415699.0 完成 DELVE 7，另两背景首次运行发现过小切块筛选前需要裁剪母目录。修复后 61415987 完成八对，空间过线 3/8 与 5/8。DELVE 7 加深臂只有位置相容，最佳距离模数较文献值低 1.62 mag。
- 严格历史重叠代理下的前两次选区未达到目标数量。61415505 使用调整后的 3° 选区注册 20 块。61415574 完成第一批。两批复核重试采用 `srun bash` 和与分配一致的 CPU 请求。61416781 完成第二批扩面和两批复核。20 个完整 manifest 与冻结配置逐一通过核对，168.204 有效 deg²、39/6 组、48 个 C 模式。核查全部 39 组图像，无 L1。

### 第五轮实测跟进

- 三批盲扫、C 和总表完成。PS1 339.769 有效 deg² 留下 96/35 组，DES 20.526 有效 deg² 留下 3/0 组。完成 99 个组的图像检查和 193 个过线模式。第三批 61409947，第三批 C 和汇总 61411315。沿用两个冻结阈值。
- 优先验证组 `expand_03-A_base-0.3-003`。61409662 的亮限与 S/N 检查均保留信号。PS1 有 9/9 个高权重源对应体，其中 7 个符合其点源切选。M33 邻域的宽响应保留审查计数；结果继续作为 L0 报告。
- 完成四场 24 对结果。双方入样代理下 LS 基线、LS 加深、PS1 空间检出为 12/24、20/24、12/24。0.25′ 同成本在两个真实对照及 8 对新注入中没有新增空间恢复。记录实际调度和每组诊断。

- 共享批处理候补期间改用共享交互 CPU 分配。61407330 首次直接执行脚本遇到可执行位限制，改用 `srun bash`。61407356 复核 10 个弱源组的 30 个模式。预揭示分级 commit `d7d0250` 冻结后，61408397 完成公开成员匹配，三系统均进入跟进档。
- 61407380 完成首批剩余九块。61408545 的第 0 步以冻结切点汇总首批。12 个 PS1 分区合计 104.538 有效 deg²、35/17 组，两个 DES 对照合计 20.526 有效 deg²、3/0 组。该分配随后启动第二批扫描。首批 C 复核并行在 61408674 执行。
- LS–PS1 的 `fresh_05` 作业 61405133 完成并同步六个真实背景配对的聚合产物。两层选择分别得到 2/6、6/6、3/6 和 0/6、4/6、2/6 的空间检出。其他背景继续处理。

## 2026-11-16

### 第五轮受控扩面

- 61404654–61404656 三个弱源扫描完成。首批扩面前五块实际有效面积 37.429 deg²，其中 expand_02 为 3.618 deg²。保留完整场与生产掩膜。
- 前两个对称响应作业 61405130/31 写试验记录时重复提供 PS1 的未校准计数。修复记录字段，并用 LS 自身加深上限校准条件形态响应。已有 11 项测试通过，以 61406369/70 重提两块。另两块启动前已同步修订。

- 完整读取 GPT Pro 对 `0b31cc5` 的最新评审。复用 A 基线测光、模板、掩膜、分组及两个切点；冻结 38 个新块。36 个 PS1 分区搜索块的代理面积 371.987 deg²，2 个 DES 深搜对照合计代理面积 20.55 deg²。科学报告以逐场掩膜实测为准。
- 选区作业 61404680。保留实际选择快照和哈希。用 Rubin DP1 正式中心表复核粗略重叠，只有深搜对照 expand_37 的 DP1 标记改变，生产几何和 36 块的优先标记保持登记时状态。HSC、KiDS、Rubin 预览仅审计名义成像重叠，UNIONS、后续 Rubin 及实际卫星搜索掩膜仍缺精确覆盖。
- 三批固定发现依次为 61404810/11/12、61404813/14/15、61404817/18/19。上一批候选整理完成后下一批扫描；组内 C 与下一批扫描可并行。汇总 61405179。实测图像与审查明确保留原始候选组计数。
- 三个弱源重新按相同完整网格和切点盲扫 61404654–61404656，候选整理与盲复核为 61404657、61404658。先冻结测光图像判断，然后用 Cerny 等公开成员表核验。主流程不会收到文献中心、距离、成员或 Gaia 先验。
- 四个实测匹配场各 6 次共享潜在系统，条件光度与双向代理响应共用标准化噪声、合格者随机数。已提交 61405130、61405131、61405133、61405134。弱端误差另按源类型统计。0.25′ 匹配先导在同一高分辨率网格对照 4 个开发块及 DELVE 4/5，单独标定审查成本。
- 通过 Python 语法、Slurm 脚本和已有 11 项测试。原始逐源与成员表留在 scratch。

### 第四轮冻结与执行

- 完整读取 GPT Pro 对 `48238a4` 的评审。使用六个既定独立场，A 基线主切点 6.137901371660258，辅助切点 6.9232059661508565。冻结配置、掩膜、网格、分组和提交后备规则；评价区候选组数由固定切点决定。
- 按冻结规则提交 61400474–61400479 与汇总 61400480。新增两处预登记检出控制 61400644、61400645，保持真实盲扫输入与注入输入彼此独立。
- C 复核改为查询组内每条过线距离—尺度假设，逐模式记录拟合及前三贡献源敏感性，按目标与源位置分别提取共加图。开发场复核 61400540，独立场复核 61400541。
- 实现原四个跨巡天案例的逐层重放与显式 PS1 i 波段响应。以同区 LS 高信噪点源作形态测量代理，并输出筛选前后误差曲线。作业 61400619、61400620。
- 优先对 DELVE 4/5 做联合孔径覆盖预检 61400542。新匹配阈值开发补场 fresh_05 和 fresh_09 已开始分页获取。LS 搜索阈值与 0.5′–4′ 跨巡天阈值各自固定。
- `python -m py_compile`、十项单元测试和 Slurm shell 语法通过。等待真实作业产物后才能更新数值结论。
- 完成开发场 18 组、23 模式重审。一个组的最高 TS 改为 0.069，所有模式去除前三贡献源后最高 TS 0.499。两处紧致对照均有完整共同中心，获取与搜索作业 61401586、61401587 已提交，扩大匹配校准 61401588 等待扫描结果。
- 四例 v3 重放全部匹配原可用成员与空间恢复。测量与 PS1 i/形态修正后空间恢复为 1/4、2/4、0/4。该四例确定了结果对入样响应的敏感性。
- 独立盲扫六场全部完成，冻结主档 23 组、辅助档 5 组。最高分盲恢复 Hercules，提交 61402454 审计目录标记。两处独立条件控制均完工，38 颗可用成员的一处通过主切点。
- 新匹配场 fresh_05 初作业 61400737 在记录 PS1 逐阶段样本数时引用了抽取函数的局部变量。修复为已去重的测量行数，加回归测试。以 61402598 重跑，并更新扩大匹配汇总 61401588 的依赖。十一项测试通过。

- 完成独立复核的 23 组、49 模式，逐组检查图像。22:10 作业 61400541 和 61401588 都已完成。保留 23 个原始组计数，标记 3 个 Hercules 相关响应与 20 个 L0。
- 匹配阈值开发面积 16.851 deg²。等成本下 LS 基线和加深都恢复了两个新紧致对照。重放、科学报告、逐模板复查、222 张图与 `sacct` 审计完成核验。

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
