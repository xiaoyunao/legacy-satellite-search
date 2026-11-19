# Work log

## 2026-11-19

### Prevent cross-pass C membership cache overwrite

- Observed source of earlier integrity repairs: legacy scratch membership filenames encode field/depth/rank and can be reused by another C pass. Fixed `src/ls_satsearch/review.py`: each new fitted row records a portable content-addressed membership path/SHA before atomically updating the compatibility cache. No likelihood, seed, member selection or score changes.
- Integrity/evidence readers prefer the bound artifact; rerunning old-75 integrity reuses its existing frozen copy only when shortlist, case table and frozen-file hashes match. Preserve original release_v2 and all its hashes.
- Actual Slurm61572142 COMPLETED/0:0/54s: first ordinary group from previously completed field, both retained modes, same numerical TS/richness/radius/DM/top3 as prior result; new saved arrays reconstruct TS7.374675368021553 and11.242710807950637. Public `results/v14/membership_validation/acceptance.json`; per-source arrays stayNERSC. This is a storage validation, not new discovery or independent evidence.
- Regression reproduces two successive same-rank writes and verifies the old row still resolves its own array; corrupted artifacts are refused. py_compile plus56unittests pass (2skipped). Next: adopt artifact fields in final all-project C/evidence QA and require explicit proof for legacy fits.


### Interim production integration, independent CFHT images and real faint-light guard

- Slurm 61568667 COMPLETED/0:0/43:15; synchronized explicit aggregate-only directories and 100 source/policy paths. Actual registry input hashes all match locally. R14: 6708/6660/1032 records/associations/successful eligible C; all historical qualified sources:7833 records,7665 provisional positions,1671 available successful same-record C; new `v14_integrated_ledger.py` verifies all75 frozen identities and leaves user grades/final gates blank.
- h audit 10:55:08Z:3977 complete,15 no_usable,17871.851998456787 owned deg². Six uncovered terminal gaps submitted as61571922; registry SHA saved and61470263/61470265 dependencies extended, preserving prior live retries. Existing131 retries remain covered61568908.
- CADC local/NERSC probes both return38 metadata rows, not38 independent exposures; no standardg. Downloaded4 CFHT u/r parent artifacts toSCRATCH, exact size/MD5/SHA. First61571304 failed on unsupportedu; fix retains validr,61571692 successful21s: r23.509ap5,93.6%core, u0%core. Originalrawdownloads reused, no L1/L2.
- CFHT physical-background coverage probe61571768 and alternate measurement61571902 completed. Firstsite2stack invalid; firstsite3partial. Alternate2/3cores100%,r23.558/24.025,stamp87.6%/78.2%; no claim these are full PS1 truth. Scripts/artifact manifests preserve exact products and failures.
- Faint-light native61571451 completedpixels but analysis failed duplicate latentID kwargs. Fix dictionary merge;61571693 completed1:56 without repeatingnative. Same311 response stars +5703 faint pixel sources: baseline hard1vs1,deeper3vs4; neither recovered. Control reproducesinitial1/4. Record selected-single-case scope, no primary144 changes.
- Registered30pc finite-radius guard61571822, same original latent4 across3backgrounds, same1536pxframe/blank and3.1′ replacement for both variants; extends only previously truncated magnitude-eligible members. Remainingtails explicit, no independent-population claim.
- Euclid C61570645_282 completed sixgroups/ninefits; code keeps first-group correct-mode metric and adds any-spatial-group diagnostic. `v13_native.py/.sh` original physical engine unchanged.
- Real4 dispatched remaining-arraytasks completed2:32–4:29 with measuredRSS<7GiB; pending throttle61568439 raised2→4,resources/seeds unchanged. Nativeproof count34/144, stillonlynine two-arm blind trials; full61568456→61568539 waitsallnative.
- Validation: py_compile changedscripts; focused2unittests pass; fullunittest discover55 pass (2skip). Initialpytest invocation unavailable inprojectvenv, corrected torepositoryunittest. Registry+catalogue actual source hashes/7833 mode counts/75identity coordinates all validated; no new usergrades. Next: finishlivework and30pcguard, inspect independent r morphology only within measured support, exacthistoricalarea/requiredC/finalreview gates remain.


### PS1 参考敏感性与图像模拟范围的真实诊断

- 61569134 COMPLETED/0:0/51s：三个 CCD 背景周围20′，保持 source-ID train/heldout；实测普通 PSF、较严形态 PSF、Gaia标签和非PSF对照的 gr/i/形态联合响应。暗端22.5≤g0<24 的普通 PSF 留出率为141/590、604/1376、316/814；共同支持的星等/颜色分箱重加权后，较严形态组高2.68、2.64、1.90个百分点。嵌套组差异不是独立样本显著性或已识别的污染率。
- 同暗端 Gaia 标签38/40/56参考全在g-r≥0.8，不能校准目标蓝主序；非PSF对照选中7.3–9.7%也不等于真实星系误分率。保留条件范围，不填物理PS1 Pdet/ΔP。
- 原48星族重放还给出：空间截断前，生成星等阈值仅表示完整IMF V proxy光的68.0–94.1%（遗漏中位14.68%）。此值不等于恢复偏差，也不据此改目标光度或重写144试验。需有限图像对照评估未渲染暗光与30pc截断。
- 核对Tan附录A/B和Euclid一手资料。Tan已测紧致对象、图像注入含未分辨暗光，不能把使用现成方法/紧致搜索本身称新意。Euclid2026-11表中三银河晕系统补入独立已知环境CSV，保留半长轴和派生圆化半径；原18 benchmark不变。
- 实际源表发现3条生产来源组与Ursa Minor II/Euclid UFSS DR1 1在0.81–1.29′内并有宽DM相容模式；最高DM有20.25/17.25，不能说距离都准确或算3个新候选。新已知对象后验环境关联尚无本轮C结果，已提交61570645，单普通字段的6组/9模式盲参考C复核，不向C传已知中心/距离。

### 新轮次：全区收尾、完整物理重复与一次最终人工审查

- 更新 g 审计：3462/6891 complete，10 no_usable，15451.31413001543 owned deg²；发现 131 个新终态未覆盖场。抽查南 DELVE/DES 日志证实 Errno122 写峰表失败；按冻结 manifest 提交 61568908（131×单场，56G/4CPU，%4），已登记 SHA，五个待运行区域汇总依赖增加该补跑。DES 原汇总已完成，另接补跑后刷新与独立命名空间 C，复用完全相同来源/种子且已完成的 C，避免重复计算。
- 新一轮完整 unittest discover 实际 54 项通过、2 项跳过（C 模式复用进一步要求模式表存在且数量与 summary 一致，定向测试通过）；没有宣称未执行的全量物理结果。当前 native 新增三次验收，合计 12/144 原生产品；仍只有原九次/18 arm 完整盲扫测量。
- 明确 final_review_protocol：首批 75 确定纳入、原 35 的非均匀抽样不能追认概率样本；最终独立审查单元/区域分数层在抽样前冻结，种子487241，层内无放回 n/N、不得事后因距离删样，匿名包独立完整 QA 后一次交付。

- 后续实测：61568571/0:0/19s 核验 144 prepared truth、48 共享星族，3/10/30 pc 截断为 3/3004、65/3073、445/3050 个星等合格潜在成员；不是完整 IMF 分母，也不是恢复损失。61568538 首试缺 LS_DR11_ROOT，在科学执行前退出，修复环境后重跑成功。
- HOME 存储修复完成：缓存 593 MiB 可逆迁移；408 份已完成北区峰表 SHA 一致后原路径替换软链，释放 3,792,210,864 bytes，quota 降至 36.23/40 GiB。新 R14 大峰表直接写已有 scratch work 后原子发布逻辑路径；13 项存储/C 溯源/生产资格/CCD 测试通过。
- 剩余真实 CCD 已开始：61568227/nid200004 覆盖任务 0–23，61568439 正式数组 24–134%2；61568456 afterok 两者执行全量测量，61568539 后续全量聚合验收。保留初九表，完整新表写 v14_repeat_full。CMD 真值距离仅用于事后成员损失诊断，不输入盲扫/C 起点；每行加入共享 latent/repetition ID。资源/提交不能当作完成。
- 历史生产 registry 首次在 NERSC 实查 57 张候选源表、6739 个合格来源记录（旧候选时钟）；区分开发、替代预算/距离与跟进索引，逐表绑定冻结策略 SHA。不宣称独立天空组/全量 C 或最终面积并集。生产刷新 61568667 已提交。C 分片新增来源与完整种子集匹配，来源不明的独立 follow-up 包保留原台账，不再凭组名认证生产记录。

- 原生 read_thread 完整读取 GPT Pro 437262c6（5600 字）与 e67e6ee2；新要求优先于此前立即审查建议。新持续 goal 已创建；仅在全正式样本/C/图像/匿名和页面 QA 收敛后一次正式人工判读。
- 实际 manifest f：3296/6891 complete，9 no_usable_gr，14536.704411651232 owned deg²；15 个 retry 请求中 8 已接受、7 活跃覆盖、0 未覆盖，不重复提交。候选快照时钟仍旧，不能由面积更新声称候选完备。
- v14_repeat.py/.sh 登记余下 135 次原冻结输入，phase-major 跨三背景，和首批九次不重叠；不重新生成星族。7 项聚焦测试、py_compile、bash -n 通过；NERSC 135 份原始 truth 存在且无先前已验收余下任务。
- 保留 release_v2 全部字节，增加 final_delivery_status 作为新交付政策；归档六个原始候选源表及 SHA，保护首批 75 的筛选身份不受新区域汇总影响。更新 PLAN/主线/STATUS/DECISIONS/评审清单与入口。
- HOME showquota 40.32/40 GiB，rsync 遇 Disk quota exceeded；正在将已查明的 593 MiB pip 下载缓存可逆迁至个人 scratch，不删科研产物。自有 CPU allocation 61568227/nid200004 有效；科学任务待代码同步核验后开始。
- 未完成：全区生产历史合并/精确面积并集、完整 144 测量、PS1 物理响应及不确定度、30 pc 截断效应和最终审查包。提交任务不算完成。

### 首批九个真实 CCD 实现完成并验收

- 继续 65c60de，恢复 clean main/远端一致状态和活跃 compute 81979；前轮是实质 progress。原先保留的 CCD 数组均为 JobHeldUser/Dependency，未重复提交。第 5–8 个分片继续真实运行，随后 CCD_INITIAL_NINE_COMPLETE、CCD_MEASUREMENT_COMPLETE、PIPELINE_EXIT=0。
- 新增 v14_repeat_accept.py：防 allow_partial 成功被误当完整批次，核对 3 背景/9 试验/18 arm 唯一集、378 阶段行、物理参数/共享星族、注册空白、原生目录 SHA 与选星计数。3 个缺失/重复 arm 和越界计数测试通过，py_compile 通过；计算节点实际验收返回 0。
- 实测基线/加深位置恢复 5/9、6/9；保留正确距离模式 5/9、6/9；最高模式正确均 5/9，空白对照均未在真值处检出。硬切选注入成员合计 103/175。初批为每半径一个共享星族实现，跨三固定背景重复；不是 9 个独立星族，不做显著性检验或选择函数结论。
- 3/10/30 pc 的实现 V proxy 分别 −2.4023/−2.7519/−3.7700，与固定目标 −3 有较大随机差异。3 pc 样本仅 1–3/4–6 个可用成员并未恢复，但半径/星族光度涨落混杂，不能据此拟合纯半径边界。完整 144 和真实 PS1 物理响应尚未完成。
- 验收后才取消原 61556314、61556315 和不再需要的退出 guard 61562541，ledger hold 数组为空。正常 exit 后，61562188 和 .0 均 COMPLETED/0:0；分配 1:50:54，主 step 8 CPU、最大 RSS 38158512K。8 个新原生运行 185.5–385.2 s，原 smoke 只复用不计新运行。实际回读六个 bulk Nice 全为 0。
- 原生、阶段、盲测量与验收聚合均保存 HOME 并白名单同步，本地没有逐源表或 FITS。时间收集辅助命令首次因 SSH 内单引号导致 Python SyntaxError，修正双引号后收集通过，不影响科学进程；没有重跑 CCD。
- 下一步：同步并提交首批验收、科学边界与目标完成审计；用户继续填独立审查表，之后封存匿名判断。后续按原冻结网格运行剩余 135 与 PS1 校准，不依初批有利与否更改参数。

### 正式 75 位置审查资料技术验收

- C/环境/实测补页在自有 61562188 上全部完成；全概率核验 75 位置/226 模式通过。资料白名单同步本地，全部 C 表 SHA 与固定 proof 一致，所有 226 模式切图无 image_pending。
- 初版组装优先 202 页＋匿名 71 页。全页 Poppler/23 联系图与 150 dpi 放大检查发现条件页 crop_top=.07 裁掉 g 深度/seeing 标题。去掉该裁切；原版及哈希留 ignored work，正式版本为 release_v2。233 页逐像素相同、仅 40 条件页改变；新 17 优先联系图和 8 高分辨率代表页已实际查看，匿名六联系图与已检查版本字节一致。
- release_v2 material/ready 标志均 true。ZIP CRC/73 条目/70 PNG 无元数据且像素与源图一致；全部 PDF/source hash 通过，40＋35 回答行全部空白。没有科学分级、匿名封存、身份揭示或最终后随名单。
- 原 6 个待运行复核父作业核实 PENDING 后由等价冻结产物替代并取消，未伪称其 COMPLETED；bulk Nice 原值已恢复。61562541 退出回退只保留原 CCD hold。现实际串行初批 CCD 已到索引 4，0–3 通过产品验收（含 1 个复用），盲测量尚未完成。完整 144/物理 PS1 校准仍未完成，持续目标保持 active。
- PDF 定向 6 测试通过、py_compile/bash -n/diff 检查通过。旧含绝对坐标的 blinded_audit.csv 不再作为匿名入口；保留技术验收/复现说明。完整调查新 e 时钟仍 3151 完成/8 空场/13626.117035 owned deg²，6 retry 验收/9 live-covered/0 uncovered；未提交重复补跑。
- NERSC HOME 正式副本的两个 PDF/ZIP/编译源及 903 个源项哈希全部通过；首版原件字节保留。归档首次因父目录不存在失败，改 parents=True 后重试通过，未影响数据或计算。ASCII85 PDF 被 Git 当文本检查空白，新增 PDF/ZIP binary 属性，不改 PDF 字节。
- 下一步：发布并同步已验收版本；继续初批 CCD 与测量，失败按 manifest/活跃覆盖处理。等待用户真实填写并封存匿名判读，再合并科学意见。

### 全部 C 复核与 226 模式完整性验收

- 61562188 / nid200010 内四个原冻结分片全部返回 C_SHARD_COMPLETE，随后 ALL_C_SHARDS_COMPLETE；75/75 位置的 C 表及全部原始诊断图完整。
- 原命令 v14_review_integrity.sh 在计算节点完成：75 位置、226 模式，概率数目/唯一 ID/归一化与重建 TS 全通过；固定数组留 scratch，聚合 proof 已同步。v14_shortlist_context.sh 完成发现与拟合中心环境记录；统一补页和正式 PDF 正在同一分配实际生成，尚不开放人工审查。
- 原 CCD 61556314 九任务再次确认全 PENDING 后加入退出回退账本并 hold；尚未启动物理 CCD 接管，不计新实现。重新读取原生对话，最新仍为 46d21aad，无后续新增要求。
- 运行完整 unittest：46 项、44 通过、2 可选 PDF 环境跳过；两个新 hold 回退测试已实际通过。原始星表、图像 FITS 和成员数组未同步本地。
- 下一步：完成 75 补页、PDF/匿名 ZIP 与全页 QA；在剩余自有分配串行执行首批登记 CCD，验证后再退役对应旧排队步骤，并恢复 bulk Nice。

### 获得本项目独立 CPU 分配并实际启动 C 接管

- 原队列持续等待；核查 shared CPU 分区实际有 idle/mix 资源，未使用其他项目的分配。以 salloc --immediate=30 -A desi -N1 -n1 -c8 -C cpu -q shared_interactive --mem=64G -t03:00:00，并通过 srun 启动计算节点 shell，实际获批 61562188 / nid200010。节点内回读 SLURM_JOB_ID=61562188、CPUS_PER_TASK=8；sacct RUNNING，sstat 已有实际 CPU 和约 6 GB RSS。
- 先登记 afterany 61562188 的独立回退 61562541，再确认原 61556312 四任务均 PENDING，hold 并逐项回读 JobHeldUser，防止重复执行。原数组保留，失败时仅释放记录中的 pending user holds；运行或普通排队任务不触碰。两项回退测试通过。ledger 在 ignored logs/v14-interactive-handoff.json。
- 在自己新计算分配内执行原脚本四个冻结分片，未改变任何科学输入、种子、距离或切选。C_SHARD_START 0 已输出，日志重定向 NERSC 私有 logs/shared-61562188-C-*.log；真实文件检查当前完整 C/图像包 52/75（原 33 加 19 个；06:47 UTC 元数据验收），不是正式全材料验收。
- 停止只监测旧队列的 observer session 15282；实际 compute 会话为 81979，句柄 locator 存 ignored logs/review_compute_handle.json。活 shell 不等于科学程序仍运行，必须结合完成标记、产物、sstat/accounting。新实际分配尚未完成；旧依赖链保留作回退，只有等价冻结产物核验成功后才取消被替代待运行步骤。
- 下一步：完成四个 C 分片；在该分配内按原命令做全模式 integrity、环境、补页和组装，再实际全页 QA/同步。CCD 原数组仍独立排队；若接管它，须先确认其仍 PENDING 并加入已登记回退账本，不能并行重复生成同一物理实现。

### 原作业回填时间窗调整

- 当前 goal 前轮为 verified wait；原 C/CCD 句柄均 live PENDING，没有失败或新增结果。调度器 sdiag 仍约每分钟 5 个主循环；不是将观察超时视为任务停止。
- 依据冻结表扣除 33 个已复用包，四个 C 分片实际为 21/34/15/26 模式、8/14/7/12 个天区；同配置 5 模式 smoke 已实测 92 秒，CCD 单实现 174 秒。原请求 C 2h、CCD 80min 偏宽，允许较短 backfill 窗口有实际资源依据。
- 官方网页请求超时；读取 NERSC 安装的 man sbatch/scontrol 核实 TimeMin 语义。远端没有 rg，改用 grep。对仍全 PENDING 的原数组 61556312/61556314 设 TimeMin=45/20 分钟；scontrol 回读确认最长请求仍 2h/80min，CPU、内存、种子、输入和科学配置未变。实际分配时限可能被 Slurm 缩短；没有把此操作计作启动或完成。
- 参数实录保存 priority_execution/backfill_time_min.json。未创建重复科学作业；若实际 TIMEOUT，按完成产物与活跃覆盖继续定位补跑。后续不继续无依据调度调参，等待原作业并核查真实状态/产物。

### 持续目标：真实补跑验收与逐模式成员绑定

- 以 20282cd 清洁工作树继续；目标未完成。明确核查活跃 C/CCD/材料链，均为 live PENDING，没有将排队当终止或复制任务。61554330_0 COMPLETED 17:55、61469851_19 COMPLETED 13:33；新 d 审计 3151 完成/8 空场/13626.117035108022 owned deg²，6 retry 验收、9 live-covered、0 uncovered。
- 检查 C 实现确认 membership 用全局 field/depth/rank 路径，文件存在不足以证明匹配所用 C 行。新增 v14_review_integrity：实际 NPZ 的计数、唯一 ID、概率归一化与拟合 richness×integral、重建 TS 均需匹配；只做输出一致性，不优化新模型。验证后原始数组固定到 scratch 的 shortlist-hash/case/seed+hash 路径，逐源数据不回本地。
- 61559482 真实原型完成 37 秒，P001 5 模式＋B001 1 模式全部通过，TS 重建误差在约 1e-13；保存聚合 proof，原数组留 NERSC。61559510 全验证已提交，等待 C；证据61558007改读固定源并依赖验证，组装61558755也依赖验证。包含已完成旧 smoke 的更新被 Slurm 拒为 dependency problem；去掉已满足旧项、仅保留活跃任务后成功。
- 全验证版本新增 CSV→JSON 哈希绑定；原型执行源另存 references/run_sources/v14_review_integrity_61559482.py，并与实际作业记录的源码 SHA256 完全比对通过，保留版本差异的可复现性。
- 修补恢复链：C 失败立即恢复 bulk Nice，C 成功登记 afterany integrity guard；验证失败恢复，成功再登记 afterany evidence 恢复。新增失败分支回归，不改变科学切选/种子/搜索器。实际恢复尚未发生，继续核查。
- PDF 发布额外核对冻结列表/模式/计划 hash、全部模式 PNG decode/CRC/hash、补页数组 hash 与全模式 proof 一致。保留材料计数与全体验收分离，原型不是全 cohort pass；没有填写人的等级。
- 原型实际显示外层坐标可能被误读为拟合中心；明确标注 discovery/C 两种坐标，完整模式表增加每个 C 的 RA/Dec。用真实 P001/B001 proof 只在 ignored layout 原型里做局部版面检查，P001 新坐标标题和 11 列模式表均经 Poppler 栅格查看，正式 75 门槛未放宽。空间页新增核心/背景环边界，待全材料任务实际重绘与最终 QA。
- 两项成员一致性测试通过；bundle PDF 六项测试通过；完整科学测试 44 项中 42 passed/2 optional PDF skips。后续运行 Python 编译、shell 与 diff 检查。下一步仍按登记链跟进全 C、完整补页/环境、组装和全页 QA，同时继续初批 CCD。

### 完整人工审查包准备与队列优先级

- 从 c1c0524 清洁 main 开始；status/branch/fetch/15 历史、WORKLOG、PLAN 和规则已恢复。原生工具完整读取 46d21aad（5,020 字符，4 轮，无后页）。用户等完整材料后亲自审核；不替用户写新等级/判断。已建立持续目标，未以排队或部分包为完成。
- 使用 PDF skill 和 bundled workspace runtime。新增 v14_review_evidence、v14_review_pdf、v14_review_seal 与定向测试；review.image_cutouts 增加显式匿名标签，默认原调用行为不变。补页从真实保存 membership、选中测光与原生共加图读取：边缘误差含共享 g 协方差说明，核心/等几何背景、成员标记、半光轮廓、质量统计或匿名掩膜。没有正概率成员时明确只画实际中心图。
- 61557934 完成 B001 实测原型（26s）；61558097 完成 P001/B001 双版式重绘（48s）。哈希绑定 C 表、成员文件、配置和绘图源代码；原始成员/星表仍留 NERSC。61558007 是等待 61556312 和 smoke 成功的全 75 对象证据任务，61556642 随 C 更新拟合中心环境。提交不计完成。
- PDF 正式发布默认检查全部登记 seed、C 完成、原始各模式图、实测补页和发现/拟合中心环境；不齐拒绝发布。优先包与匿名 phase1 分离，匿名 ZIP 不含身份键/环境/分数/绝对坐标/先前判断，去 PNG 元数据。空白表不覆盖现有人类回答；已发布哈希不可静默重写；封存工具拒绝草稿、未填表或变更 PDF。未执行人的封存/揭示步骤。
- 内部缺页 PDF 留 ignored results/work；当前 33 旧 C 包、2 新完整补页，75 包未发布。Poppler 实际栅格查看 P001 证据/像素/环境/模式表及 B001 证据/像素页；修复零贡献源图的大面积空白展示，未制造替代星。pypdf 文本检查匿名原型无 field/cohort/candidate ID/known-name/数值分数泄漏。Fontconfig 提示未阻止渲染，实际页面可读。
- 队列确认 C/CCD 与扩面同优先级。为执行用户审查优先，将本项目六个 bulk parent 的 Nice 从 0 临时改 1000，未取消运行分配、未改补跑、未使用另一个 photdis 项目的交互分配。原 Nice 写 ignored ledger；61558199 afterany C guard 在失败时恢复，成功时登记 afterany 61558007 恢复。恢复失败/完成仍须核对实际状态，不能假定已执行。
- 新 progress_20261119c：3142 完成、8 空场、13623.963586033948 owned deg²；5 retry 验收、10 live-covered、0 uncovered。初批新 CCD 仍仅 1 已测，9 任务仍排队，无新恢复率填表。
- NERSC 环境准备安装可选 reportlab 5.1.0/pypdf 7.1.1，pillow 13 已有；pyproject review extra 记录可选依赖。本地 PDF 用 bundled runtime。科学回归 41 项中 39 通过/2 可选 PDF 测试跳过，bundled runtime 实跑完整 5 项新测试通过；Python 编译和 shell 语法检查通过。
- 独立 CLI 烟测补查 package/脚本两种导入路径：validate 改为按 __package__ 选择相对/同目录导入，避免未安装 scripts namespace 的 bundled Python 无法执行 README 命令。validate/seal 的直接 --help 实跑通过，代码哈希已更新。
- 更新主线、PLAN、STATUS、DECISIONS、逐项验收和报告。新增组装链 61558755，依赖证据和最终环境任务；组装只置 materials_complete，实际全页栅格/匿名检查通过后才设 ready_for_human_review。保留已组装 PDF 哈希，禁止重生成改变用户所审版本。下一步：跟进 C/证据/环境链，按终态 manifest 补缺并核验调度恢复；75 包齐后组装、逐页检查并同步，再交给用户科学判读。同时继续既定 CCD 初批与后续物理 PS1 响应验证。

### 最新 GPT Pro 优先级、真实 shortlist 与新 CCD 配对

- 从 1fc30bd 清洁 main/远端同步状态继续。原生 read_thread 完整读取最新 af4ec677（6,831 字符，三轮、无后页）；首次 30,000 超接口上限，改 20,000 成功，原文留 ignored logs。未使用 computer use。认证失效后由用户自行完成 sshproxy，再验证 SSH 可用。
- 新增 shortlist_plan、v14_shortlist/index/context/archives 和定向测试：40 优先+35 分层盲审，按区内经验排名/C 稳定性跨区轮选，5′ 分离；真实最小间距 6.362′，输入/配置 hash 验证通过。旧首选表中已知系统距离别名移至环境审查后再冻结；初表保留。分层抽样有空间排除，尚不能估计统一审查完整度。
- 61556311 完成 P001 五模式新 C；61557017 复用 33 个同记录完整包（19 优先/14 审查，含 P001，不重复计数）。全部模式表同步，完整 PNG 留本地/NERSC，公开每个可用优先位置的最高 C 三联图。实际检查 P001/P007 CMD/像素、P002 像素，另检查 PS1 响应图。人工审查仅记录实际两项优先决策；35 个盲审未分级。
- P001 TS 95.58→去前三 63.16 仍是扩展星系碎片；61556641/61557190 完成发现/C 双中心上下文。P007 C 106.85→80.03，但在 Ursa Minor 约 44.7′ 环境，保持 L0/已知环境待辨。未改冻结阈值，未把新候选名称/物理类型写成发现。
- 新增独立 namespace 的 v14_repeat 三背景/144 潜在实现协议，首批 9 个 CCD 已提交。旧 native code 增加可选 shot seed（默认保持 483423），新 trial 唯一确定性 photon seed；PS1/native M_ini/int_IMF/phase 行逐项验证并保存共星族通带。防旧 namespace 覆盖测试通过。
- 61556313 真实 CCD smoke（2:54）与 61556503 部分测量（1:40）完成：100 kpc/10 pc、目标 V proxy −3、实际 −2.7519，5929 IMF/275 渲染曝光/83 输出匹配/54 PSF，可用成员 13→20；两深度均正确 μ20，C 去前三 23.63/29.81。仅 N=1，旧 56 与新实验分母分开，不声称整体收益。
- 新增实际 PS1 gr/i/形态阶段及 source-ID 留出审计。61556316/61556716 完成全场和 20′ 局部；g0=23–24 条件响应全场 14.8/31.7/29.1%，局部 12.2/29.3/23.6%。这不是恒星真值完备度；PS1 物理响应和三臂物理曲线待验收，不重复施加已含硬切选的最终概率。共享 realization ID 的背景 bootstrap 要保留跨背景依赖。
- P002/P007 CADC 和 NOIRLab 元数据实际查询已保存。NOIRLab 仅找到 North LS 家族 90Prime/Mosaic3，CADC SSL/超时；独立深双波段覆盖仍未知，没有下载无证据的新像素或把服务错误写成无覆盖。
- progress_20261119b 实际审计：3117 完成、8 无 gr、13456.908092206788 owned deg²；4 补跑已验收、11 live-covered、0 uncovered。新作业和实际 Slurm 快照单独保存；61556312 四分片与 61556314 九试验等待 Priority，61556315/61556642 等待 Dependency。
- 更新 README、PLAN、主线/决策/状态、A–E 验收与第十四轮报告。运行 unittest discover：36 passed；改动 Python 编译、5 个 shell 的 bash -n 通过。实际包 hash/75 个独立位置与 33 个复用 C 表验收通过；发布前执行 git diff --check 和暂存白名单检查。
- 下一步：按现有 manifest 继续候选 C 与首批 CCD，失败再扣除 live 覆盖补跑；完成实际盲审/弱控及独立影像筛查，验证 PS1 源响应后再完成注册重复与物理区间。μ≤20.75/0.5′ 保持冻结；无支持的 50% 等值线、种群推断和“新增面积”主张不作。

### 恢复完整评审、验收快照与生产样本分离

- 从 452d7f3 恢复；status/branch/fetch/15 条历史、WORKLOG、PLAN 和项目规则已核对，main 与远端一致。
- 内置 read_thread 恢复。以 turnLimit=10、每消息最多 20,000 字符完整读取“恢复项目进度”两轮、无后续游标；最新评审 9,387 字符，完整副本留 ignored logs。首次请求 60,000 超限，被拒后按接口上限重试成功。未使用 computer use。
- 按完整评审将路线 B 设为稳定论文主线，发现路线继续；新增 PRO_REVIEW_CHECKLIST 对应 A–E、距离/角尺度、光度随机实现、区域/场际不确定度、种群推断前提及五组论文图。未完成项明确待验收。
- 61511922 已完成（43:41）。同步区域聚合、候选索引和两坐标图册。索引 11,217 记录、31,846 模式、7,000 临时关联；图册 2,992 个新栅格、13 个极区场已包括，逐场 hash 与后续审计相符，ICRS PNG 已目视检查。新审计 3,078 完成、6 空场、13,323.227843364195 owned deg²；比前次增加 152 场、639.4782484567901 deg²。图册、候选汇总与最新面积仍各有时钟。
- 七 CCD 背景的 7 个空白、56 个物理实现持续完整。原补跑 3 场完成。sacct 暂漏掉仍 PENDING 的 61510268_3，导致旧审计误报一个缺口；改为展开 squeue 与记账交叉，新增防重复回归测试，并支持新补跑 CSV/hash 登记。
- 真正新缺口为 South DELVE extension 0142/0143（原 61469850_17 TIMEOUT）。第一次请求采用内部有效 QOS regular_1 被拒，无作业产生；改用已有脚本中经过实际提交的用户入口 regular，成功提交 61554330（2 单场、每场 56 GB/2h），登记不可变清单并追加 61470263 依赖。新审计原 3 场验收、12 场有活跃补跑覆盖、零新增未覆盖失败。尚未计作完成。
- 新增 v14_production.py 与针对开发/替代档泄漏的测试。实际运行仅计 R14 已完成评价场、A 基线 main/0.3：5,614 记录、5,568 临时关联、1,026 个同资格成功 C。按候选汇总时钟计算分区面积与审查成本。历史记录留总索引；缺失人工审查、后随及未标定分区计数留空。全距离原始峰与主分支候选分开标注，不冒充端到端概率。
- 更新 finalize 的 catalogue/snapshot 阶段自动生成增量生产表；更新主线、决策、状态、报告与图册说明。新 Python 编译、6 项定向测试及真实聚合表重放通过；完整回归与 shell 检查见本次验收。原始像素和逐源表仍留 NERSC。
- 下一步：完成队列和历史生产资格/面积对账；依清单冻结 3–5 背景重复与跨背景标准，再收敛 30–50 个统一候选。μ≤20.75 生产边界保持不变，0706 保持 L0。

## 2026-11-18

### 13:55 UTC+8 逐场复核

- 以 a8801b8 开始；fetch 后 main 与远端一致。重新运行 v14_manifest_audit.py 与 v14_continue_audit.py，结果保存 progress_20261118c，保留 a/b 快照。
- 6,891 个登记场中 2,926 完成、5 个无有效 gr，owned 面积仍为 12,683.749594907405 deg²；13 个原缺失场均由 61510268 活跃队列覆盖，零新增未覆盖失败。61511922 仍 PENDING，61510994 TIMEOUT。没有新补跑提交。
- 七背景的 7 个空白、56 个 CCD 注入及测量继续完整。逐场、逐层、CCD、补跑与未覆盖清单五张表与 b 快照逐字节一致；只更新审计和队列时钟。九项聚合/元数据文件按白名单同步本地。
- 目标新对话为“恢复项目进度”6afc5b3b-3174-83e9-a31b-c698b4767c0e。其预览的最新回复仅引用占位符，未取得 GPT Pro 正文。确认应用日志中另一聊天存在 read_thread 成功记录，但本聊天当前工具清单未暴露该接口；连接入口搜索未找到替代读取能力。未使用 computer use，未把推测当作最新要求修改科学范围。
- 更新 STATUS、PLAN、第十四轮报告；下步保留现有队列、按终态 manifest 验收，并在完整新建议可读取后逐条落实。

### BASS 扩大标定已完成与对话访问边界

- sacct 再查：61514532 COMPLETED（01:11），61511922 和 61510268 仍 PENDING；61510994 保持 TIMEOUT。没有重复提交已有覆盖的补跑。
- 按明确文件白名单同步 BASS summary、逐产品聚合表及 PNG/PDF/SVG；原始像素与逐源表仍留 NERSC。18 个参考星/波段、各 6 个留出，g₀/r₀ 的 1.5″ 孔径 5σ 深度为 23.6717/23.2785。核心完整、单砖背景环 49.1%。原生冻结模板最亮 stage-1 主序点 g₀=22.9351；不能据孔径深度认定星族确认或完备度。
- 更新 PLAN、STATUS、PROJECT_MEMORY 和第十四轮报告；保留 initial_summary 及之前的验收快照，新验收独立记录当前产物 hash。核对 JSON/CSV 数字、图像标注及五项远端 hash，未改搜索或切点。
- 用户要求停止 computer use，已停止。当前工具列表没有 read_thread，所给 ChatGPT 预览截断，不能声称读完最新 GPT Pro 全文。新建议依赖的范围改动等待完整消息，已授权的续跑与同步继续。
- 下一步：跟进现有正式补跑/汇总并按 manifest 验收；0706 保持 L0。取得完整新建议后逐条与当前实测产物核对。

### 第十四轮再次跟进（12:18 起）

- 起点 07d2467 与 origin/main 一致，工作树干净；按 Git、WORKLOG、PLAN、项目规则恢复上下文。
- 61510994 为 TIMEOUT（29:07）；61511922 仍在正式队列等待。新增逐场与 Slurm 数组交叉审计，十三个原缺失场均由 61510268 覆盖，零个新未覆盖终止缺口。完整场和有效面积现为 2,926 / 12,683.750 deg²，比前次多 4 场、37.238 deg²。新审计放在 progress_20261118b，保留原快照。
- 61513679 在 CPU 节点完成已完成分区的候选索引和图册（17:38）；61511922 等待其结束以避免写入竞争。候选目录已有 11,134 记录、30,466 模式、6,938 个临时关联，仍含开发/多档位记录，人工审查未完成。
- CADC 本地与 NERSC 两个出口各试 ROI GET、ROI POST、最小健康查询，共六次均 503/TLS EOF。记录完整请求、方法、错误和端点；CFHT 覆盖保持未知，没有新深 g 像素可下载。0706 继续 L0。
- 61514438 在 58 秒内完成既有独立 BASS 原生图像的覆盖、掩膜和孔径深度测量。初测 g₀/r₀≈23.58/23.18，核心完整、背景环 49.1%；使用冻结官方颜色项及本地 Tractor 透过率。4/5 个标定星偏少，将离核参考半径扩大至 5′，61514532 排队。原始图像与逐源值仍留 NERSC。
- 为小型标定试验尝试 shared_interactive 分配 61514571，返回节点 down/drained/reserved 且未获得资源；取消该分配，释放暂时挂起的 61514532，恢复正式批队列等待。全区任务未改阈值或几何。
- 图册输入 hash 核验与目视验收后追查 arcsin 警告：13 个极区场的包围盒纬度为 NaN，导致完成掩膜漏绘 37.8929783951 deg²；原生面积仍在。修复 field_bounds 的物理纬度裁剪，保留 Field.sky 对无效像素的 NaN。修正版待 61511922 重绘，现有图像保留已标注限制。
- 尝试为 dense/extension 数组增加时限时，NERSC 因用户剩余额度拒绝 outside-census 整组扩时请求。恢复整批任务的原有 80 分钟上限，不扩大整组预算；仅十三个具体补跑保留已接受的 2 小时限额。
- 25 项单元测试通过，其中新测试验证完成结果优先、活跃补跑不重复提交、未知 Slurm 状态不推断补跑资格。图像支持测试确认保留 CLUSTER/RESOLVED 位、排除 WISE_GAIA 与零逆方差；编译检查通过。

### 第十四轮实测核查与 0706 独立成像

- 恢复 `abd47db`、WORKLOG、PLAN 和分区/注入 manifest。对 6,891 个登记单元逐场检查定义 hash、终态、去重表和 owned coverage，七个图像背景的 56 次 Tractor 注入及测量全部完整。审计表在 `results/v14/progress_20261118`。
- 核验 2,922 个实际完成场，新增有效面积 12,646.511 deg²。North 主区和 South PS1 残余场已处理完，South DELVE、DES 及扩展数组继续。依据终止失败任务与 manifest 的交集，只登记 13 个缺失场补跑为 61510268。提升内存并减少同节点并发，避免重复已完成场。
- 61510285 在 HOME 上的 flock 返回 524。锁移至 scratch，并实际验证加锁成功，随后以 61510733 重提汇总。考虑已测约 16 GB 的汇总内存和文件系统延迟，待运行汇总改为 100 GB / 4 小时；61510733 最终为 TIMEOUT，运行 30:26，分区产物已保留；61511922 现等待正式队列调度兜底。debug 数组重试因 QOSMaxSubmitJobPerUserLimit 被 Slurm 拒绝，原正式重试数组保留。
- PS1、SDSS、NOIRLab、HSC、SMOKA、Gemini 与空间望远镜档案围绕冻结 0706 实查。CADC 返回 503/TLS 错误，CFHT 覆盖仍未知。DTN 连接提前关闭，改由登录节点传输，像素分析继续在 Slurm。
- 下载 PS1 gr、8 帧 SDSS gr 和 3 次独立 DECam i 的有限 CCD 产品到 scratch。61510489 完成独立 BASS 和 PS1 多模式，61510609 完成 PS1 冻结检验。BASS C TS=4.964、去前三源 TS=0，PS1 固定 C TS=0，保留 L0。
- 61510836 完成像素深度和实际 CMD，完整核心的 PS1 / SDSS g₀ 深度约 22.13 / 22.45，独立 DECam i₀ 约 22.30，不能确认暗端星族。排除无效 PS1 坐标并统一 sky-offset frame；目视发现二维 WCS 网格拼接造成图像拉伸，改用 stack(axis=-1)，由 61510733.0 重导出并加入独立 i 对应源统计，重复的待运行作业 61511117 取消。原始像素和逐源测光留在 scratch。
- 61510994 以 112 GB、双 worker、29 分钟优先补跑这 13 场，正式数组 61510268 设为 afterany 兜底。相关分区汇总已追加重试依赖，避免先汇总漏掉补跑结果。两个运行中的 Python 进程出现 DVS/IPC 的 D 状态，8 分钟的 CPU 分别约 49/18 秒，记录为共享文件系统 I/O 延迟，未认定官方故障。
- South DELVE 当前完成场的冻结主档为 2,240 组 / 3,005.425 deg²，0.745 组/deg²；South PS1 残余碎片 1.223 组/deg²。记录审查成本迁移，未按新候选数重调阈值。
- 本地提交 c948908 已推送。远程 verification-v7 是运行快照目录，git fetch 返回非 Git 工作树；没有修改其 Git 元数据，继续用同步文件及执行代码 hash 追溯。
- 按完成 provenance 白名单同步 24 个第十四轮 C 分片，含 624 组、1,685 个成功模式；这些结果仍待图像审查，不能据此晋级。
- 本地 20 项回归测试、编译和 shell 语法检查通过；合成二维 WCS 回环和带孔洞像素支持烟测通过。七背景配对汇总核验逐实现的物理参数、模型、种子和位置相同，输出 trial-level 保守区间，未替代场际不确定度。NERSC 原生 bash 入口使用 mock srun 验证双 worker 的成功路径和失败退出码传递。


## 2026-11-17

### 第十四轮全 DR11 首批结果

- 对照全足迹任务书和 `fa8ff0e`。新增 `coverage_history.py` 和 `scripts/v14_*`，用含真实图像掩膜的旧搜索结果进行像素去重，独立登记高纬主样本、扩展层和 census 外天区。
- 61469680 的 YAML 写入失败源于 NumPy float64 标量，已把面积标量标准化。61469764 完成 1,484 份历史栅格的重算并成功冻结 6,884 个残余单元。
- 61469829 已开始 South PS1。其他分区、历史候选复核、7 个图像背景和后续汇总均在正式 NERSC 批处理执行或等待依赖，详见 `docs/STATUS.md`。
- 61469723 的 Boötes V 对照在原生南北共同天空恢复同一距离模式，两个峰相隔约 0.34′。61470535 完成首个物理图像场的六次盲扫，基线和加深均为 3/6。61469874 用作者冻结 PS1 DR1 模型比较 240 个已执行的注入位置。
- 统一候选目录完成第一版。保留原始过线模式、候选复核和跨版本关联。已运行 20 项测试、Python 编译和批处理语法检查。
- 继续同步实际搜索栅格和测量结果，按新图像背景与固定审核预算重估分区选择响应。此次快照供续跑和先行科学比较。


- 首批真实盲扫触发残余所有权 `unit` 未导入，修复后增加实际砖元信息所有权测试并重试 61470438/39。61470501 快照已验收 71 场、0.9316 有效 deg² 和零新增过线组。
- 8 砖真实数据逐像素验证共享位掩膜缓存。缓存与原 FITS 路径全部一致。61469805/06 补审 231 组及 274 模式，统一目录使用南北真实 SGA 交叉表。61470672 生成三个紧致 L0 诊断和图像。初次快照未找到其他历史 revision 的弱源聚合表，按文件白名单补齐后 61470501 重放。

### 第十三轮 South PS1 补扫与源检测校准

- 完整读完 GPT Pro 对 `b70e5ae` 的评估并设 goal。冻结南区 A 主档和共同天空试验的三条臂。分层登记七南三北背景，按双波段深度、g seeing 和点源密度配出三对。
- 61464521 登记 339 个互斥核。61465403 登记 738 个碎片所有权单元，代理面积分别为 411.795 和 945.254 deg²。61464563、61465477 执行盲扫。碎片注册的 YAML 数值类型已转为 Python 标量，原失败作业 61465151、61465295 已替换。
- 61465088–61465090 完成三块真实曝光的 LegacyPipe 空白复跑。修复正式 Gaia DR3 分块前缀和 CCD 标头字段后，61465310 完成 18 个 CCD 图像注入。检测与形态分类通过原生联合光学流程，三场统计和盲搜由 61465459–61465461 执行。
- 本地单元测试与注册哈希、几何、RA 缝核查通过。PS1 原始页，注入源和 Tractor 产品留在 Perlmutter scratch。
- 两批全部完成 1,077 个核心、1,636.598 有效 deg²。合并主档 370 组和严格档 127 组。61465404/61465478 的 228 个 C 模式均拟合完成。SGA FITS 使用真实小写字段和 REF_CAT/REF_ID，修复初次别名误用。
- 240 次配对完成。南区 59/68/48，北区 23/27/22。三对南北背景整数成员数及完整 IMF 实现逐试验相同。原生注入流程下固定盲扫基线 8/18、加深 5/18。选择函数优先扩充 South PS1 约 100 kpc 的真实响应测量。
- 核对 Palomar 14 的文献坐标、距模与延展结构。先前重点组和相邻核心响应均在约 5′ 内。Hercules 再恢复，M33 周边高分峰标为已知背景，未晋级 L1。生产切点保持冻结。
- 61468590 修正图册中最近栅格采样跨 census 边界的显示计数，并核查残余几何和实际有效掩膜。盲扫分数和每场实际曝光面积沿用原成果。

### 第十二轮紧致系统主线

- 阅读完整 GPT Pro 五阶段任务书并设 goal。核对 Tan Table 8、公开 PS1 DR1 选择函数、Gaussian 诊断图样式和近期 Euclid 公布坐标。冻结四层 A 的旧生产策略。
- 61461645 注册第一批 47 场。61461759 额外注册 31 个 2° South PS1 缺口。61461693、61461695、61461697、61461698、61461830 运行新扫描。出现单场内存不足后以 61462399 单独提高步内存，复用其它 DES 场结果。
- 61461656/61461657 完成六个 Tan 对照的两种深度盲扫。61461783 实测正式匹配、正确距模、掩膜和目录处理。61461687/61461689 用历史原始峰复现并重新标定 μ=21.0。61461738/61461739 完成六个真实砖块的共加图像注入。
- 新共同有效天空的 PS1 DR2 取数改到 DTN 并用已验证的 Perlmutter scratch 路径。文件锁与校验 manifest 使下载可并行并安全重启。发布的 PS1 DR1 模型单独计算。
- 四层和补隙 78 场盲扫全部完成，691.838 有效 deg²。新 South PS1 首要 L0 的独立 PS1 固定中心似然较弱。61462491 完成 PS1 与 Gaia 过滤对照，61462589 核对 NOIRLab 拟独立 DECam g 访次。
- 初次配对试验发现模拟天球坐标赋值顺序错误，已修正并重提受影响的 North 与 South 作业。18 项本地回归测试、脚本编译和 shell 语法通过。
- 完成 170 个物理配对与 8 个星族敏感性对照。新 South 68 对中基线/加深/PS1 为 22/30/22，North 68 对为 29/28/32。作者 DR1 模型 61464044 在 170 个相同位置计算完毕，依赖沿用已验证归档版本。
- 同天空六对照 18 个目标场全部完成，五个目标可比较。固定审查量通过 LS 基线/加深/PS1 为 3/4/1。主盲搜、C、PS1 和 Gaia 档案试验分开验收。M 106 等真背景产生多个很高的 A/C 模式。
- 检查绝对有效孔径分母并重跑 61464109/11/12，宽尺度 Boötes III 保留与扫描上限并列的质量列。校验 78 个冻结 manifest、268 个唯一组、配对成员数、三种图格式和公开发布白名单。科学报告给出新增、限制及下一步。

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
