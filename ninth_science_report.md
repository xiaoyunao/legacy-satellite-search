# 第九轮科学报告

本轮检验两个直接关系发现能力的问题：优先级是否放过可能的少成员系统，以及 LS 在可对照的 PS1 天区增加了多少紧致系统检出。候选确认仍以独立星族证据为准。

## survey_63 的独立成像

以 ICRS 356.63691°、+27.95930° 查询 SMOKA、HSCLA、CADC/UNIONS、Euclid、NOIRLab 和 Rubin 档案。SMOKA 的 2.1′ HSC-g CCD 查询无结果，宽区 29 个曝光的最近中心距目标 69.5′。UNIONS+ 的目标赤纬范围包含该位置，CADC 在这里提供已验证的 CFHT r。HSCLA 切图和浏览器入口返回 401，这次亦未能连接 Computer Use 的浏览器会话，因此保留其已发布 HSC-g 产品状态为待核实。Euclid DR1 Wide、Deep 的实际发布 MOC 都没有覆盖该中心。[档案记录](results/v9/archive/survey63_queries.csv) · [UNIONS+ 状态](https://www.cfht.hawaii.edu/en/science/SAC/reports/SAC_report_Dec2025.php) · [Euclid 中心探针](results/v9/archive/euclid_moc_probes.csv)

NOIRLab 原生 CCD 接口的 g 产品按曝光合并后有三帧。764217 和 680146 已在中心 DR11 砖的曝光清单中，其中 680146 原始名称在查询响应中被截断，通过另取 CCD 的 FITS 头确认了编号。独立曝光 562858 为 175 秒 g。实际下载其四个相邻 CCD。最初两个档案返回 CCD 合计只覆盖核心约 9.6%；补查相邻 N2 后，几何核心覆盖增至 61.2%，中心落在 N2 的芯片边缘。[DR11 曝光核对](results/v9/archive/dr11_brick_exposures.csv) · [四 CCD WCS](results/v9/archive/adjacent/noirlab_ccd_coverage.csv)

加入权重、质量位和完整孔径要求后，可用核心和背景环比例为 51.7% 和 74.2%，中心整孔径不可用。PS1 参考星留出残差的稳健散布为 0.047 和 0.059 mag，N1、N2 实测去消光 5σ 孔径深度分别为 **g₀≈23.00 和 22.94**。相对 μ=18.75 假设的转折点仅深约 0.5–0.6 mag，对 μ=20 或 21 的转折点偏浅。当前拟合仍为 L0。停止用这帧边缘浅图作共同星族确认，保留已验证的 CFHT r 作后续深 g 的配对数据。[掩膜与实测深度](results/v9/archive/noirlab_g_depth.json)

## 候选盲审

从第八轮无已知关联、未进入重点审查的主档组中，以 C TS 的层内三分位、角半径 1.5′ 和距掩膜空洞 2′ 分层，每层抽两组，共 24 组。随机混入三组已经过线的公开弱源，审阅去掉组名、天球坐标和目录标签的图像、CMD、径向剖面、A 距离响应及局部观测条件。C 的总分与前三源剔除分数不提供给评审。分级先提交，再揭示组名。一个评审者判读，部分弱源档案图的环境面板和生产图存在版式差别，故这里验证的是排序流程能否漏掉明显信号。

24 个低优先组中，19 个维持低优先级、5 个为疑难、0 个达到定向跟进标准。混入的 DELVE 3 和 5 达到定向跟进标准，DELVE 4 为疑难。DELVE 7 没有进入既有基线候选表，加深时只得到位置相容的峰，记作上游检出缺口。保留现行生产阈值，为疑难组保留次级复核，包括真实弱源可能被保守的人审规则降级这一情形。这次抽样无法给出总体真实系统漏检率。[盲审分级](results/v9/triage/blind_grades.csv) · [揭示后记录](results/v9/triage/unblinded_audit.csv)

## 真实新增覆盖与前人工作比较

Tan 等的 DELVE census 已结合 DES Y6、DELVE DR3、PS1 DR1 做统一普查、模拟和人口统计。它的主要人口样本从约 15 pc 起，作者也专门分析了更紧致的系统，并用 DELVE 7 等说明这类对象在既有流程中可以检出。Gemini I 在 120 kpc、圆化约 8.6 pc，是紧致卫星的直接先例。LS 在相同背景、相同审查预算下恢复现用 PS1 DR2 流程漏掉的 DELVE 4/5，是目前最直接的目录增量。LS DR11 与 DES/DELVE 共享不少原始曝光，跨目录比较可检验目录处理、通带与样本切选，独立确认要求核对曝光。[DELVE census](https://arxiv.org/html/2509.12313v2) · [DELVE DR3 紧致卫星](https://arxiv.org/abs/2510.11684) · [Gemini I](https://arxiv.org/abs/2606.09975) · [LS DR11 数据](https://www.legacysurvey.org/dr11/description/)

HSC-SSP 的约 1,140 deg² 深搜提供更深的可用星源。Euclid DR1 的三处银河系晕恒星系统与本项目三个优先位置均相隔 52° 以上。Rubin 的 Aquarius IV 与 Rubin-GC1 进一步拓展了远距超暗弱和高消光紧致体系。对 LS 而言，优先科学空间仍是约几至十几 pc、可在普通目录处理中可靠检出、且位于深搜增量区域的系统。目前没有完成这一空间的全域选择函数。[HSC 深搜](https://arxiv.org/html/2311.05439) · [Euclid 发现论文表 2](https://arxiv.org/html/2611.16025#S4.T2) · [位置交叉核查](results/v9/archive/euclid_novelty.csv) · [Aquarius IV](https://arxiv.org/abs/2608.02601) · [Rubin-GC1](https://arxiv.org/abs/2609.15872)

使用官方 Euclid DR1 宽场与深场 MOC 排查剩余 1,765.716 deg² 的 PS1 合格区域代理，实测重叠 4.511 deg²，与深场重叠为零。约 1,761.205 代理 deg² 落在两份发布成像 MOC 外。按两度经纬格粗排的产物供下一轮取舍，每格记载当前可用面积和发布成像重叠。已有 DELVE/DES/PS1 历史统一普查遮罩继续取作者官方资料；HSC 的 S21A 精确搜寻遮罩、UNIONS 实际 g 联合搜索遮罩和 Rubin EDP2 的搜索遮罩仍未核实。UNIONS 公开边界记录计划范围，Euclid MOC 记录发布成像范围，暗弱卫星审查和完备度另待测。[Euclid DR1 发布](https://euclid.caltech.edu/page/euclid-dr1-foundation) · [UNIONS 计划范围](https://www.skysurvey.cc/survey/) · [Rubin DP2 资料](https://dp2.lsst.io/products/index.html) · [逐格覆盖](results/v9/footprint/ps1_ranked_proxy_cells.csv)

## 小范围物理参数灵敏度

在已保存真实背景与共同掩膜的 fresh_05 和 fresh_09 使用同一套模拟星。每场 16 个方案，日心距离为 20、50、100、150 kpc，圆化 Plummer 半光半径 3、10、30 pc，并补两个 80 pc 对照。12 Gyr 贫金属 PARSEC 的 IMF 用全部恒星光度归一化。约定的输入亮度为 Mᵥ 代理 0、−1.5、−3，使用 DECam g、r 的固定近似颜色转换 (V = g − 0.59(g−r) − 0.01)。每次泊松采样两巡天测光限附近的可用星，保留同一颗潜在恒星的空间位置与标准化测光随机数。此处的 V 是期待亮度，有限采样的真实输出亮度有波动。该颜色关系原针对 SDSS 星等，这里只作为 DECam 光度代理。[Jester 等的颜色关系](https://www.sdss4.org/dr12/algorithms/sdssubvritransform/)

在三种真实背景目录分别注入并盲扫，采用已有 0.3 组/有效 deg² 的标定切点。与这个标定一致的主距离网格为 μ=16.5–20.75，步长 0.25。在位置匹配后另计是否保留距离真值容差内的模式。局部误差模型由真实星表测量。PS1 i 质量和三臂形态入样概率以已测源代理，稀疏测量箱以以前的默认响应处理。本轮未标定源提取、混叠和完全漏测造成的损失。位置容差至少 2′，角半光半径显著小于 0.5′ 的情形依然受核尺度下限。旧的全距离试跑产物保留在 NERSC，正式比较采用主距离分支重算。[冻结物理参数](configs/v9/physical_trials.yaml)

另将相同 32 个注入点的物理参数和作者发布的 r<22 星密度输入 DELVE census 的 PS1 DR1 模型，使用原始 v2.1 掩膜及列顺序，32 个位置均满足掩膜。其预测区间是 20 kpc 的 0.400–0.963、50 kpc 的 0.001–0.719、100 kpc 的 0.0002–0.272、150 kpc 的 0.001–0.022。作者模拟覆盖 1–2,000 pc，采用 15 pc 边界的是主要人口样本。该列用于比较公开搜索条件和相应差距，采用论文阈值，单独报告。等审查成本差值取本项目的同场 PS1 DR2 对照。[作者发布模型](https://github.com/delve-survey/delve_mw_census/tree/1a02f50d25cac74c02ddba8401a5af20aa2db4fe) · [逐点预测与哈希](results/v9/physical_trials/published_ps1_dr1_reference.csv)

| 距离 | 配对数 | LS 基线位置检出 | LS 加深位置检出 | PS1 DR2 位置检出 |
| --- | ---: | ---: | ---: | ---: |
| 20 kpc | 6 | 6 | 6 | 6 |
| 50 kpc | 12 | 9 | 9 | 9 |
| 100 kpc | 8 | 2 | 4 | 2 |
| 150 kpc | 6 | 3 | 5 | 2 |
| 合计 | 32 | 20 | 24 | 19 |

32 个原背景均无已过线的位置匹配。LS 基线比 PS1 多 1 对，LS 加深多 5 对，位置检出的描述性差值为 +3.1 和 +15.6 个百分点。5 个加深独有案例都在 100–150 kpc，期待 Mᵥ 代理 −3，包括 150 kpc、10 pc 的两个重复、两个 30 pc 例及一个 80 pc 例。达到 ±0.25 mag 距离模式的数目为 LS 基线 19、加深 22、PS1 18，最高排名模式准确的数目为 17、20、10。这组有限背景与 IMF 实验由相同位置和随机星族成对构造，位置检出差值描述的是这 32 对试验的条件结果。低光度、极紧致目标的实测完整度仍需更深参考星表或少量图像注入。[配对汇总](results/v9/physical_trials/paired_summary.csv) · [逐试验结果](results/v9/physical_trials/)

## 下一步

优先取得 survey_63 的完整核心 g，配对已验证的 CFHT r；达到 g₀≈26–26.5 才能更有力地检验更远模式的转折点以下星群。选择函数校准优先复测 100–150 kpc 及代理亮度 −3 的检出转折，加入实际目录检出、混叠、年龄和金属丰度变化。大面积任务的选区以实测增量和补齐历史搜索掩膜为依据。主报告、盲审、覆盖和可复现的两臂比较已同步。[Slurm 实测记录](results/v9/slurm_jobs.csv)
