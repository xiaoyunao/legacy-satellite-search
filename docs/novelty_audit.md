# 公开新颖性审计

## 2026-11-17 · survey_14 与 survey_63

用两个已冻结的 C 中心分别执行实时核查，查询日为 2026-11-17 UTC。5′ 和 30′ 的 SIMBAD 查询保留对象类型和标识。Hunt & Reffert 2024、VizieR 星团及矮星系表、UCC 260615 和固定 LVDB/DELVE 公开中心均按球面角距计算。两处的 30′ 锥内均未找到目标类型的公开同位置系统。[survey_14 逐库核查](../results/v8/survey14/novelty/novelty_catalog_checks.csv) · [survey_63 逐库核查](../results/v8/survey63/novelty/novelty_catalog_checks.csv)

| 冻结中心 ICRS | SIMBAD 5′ / 30′ | 最近的 Hunt 星团 | 最近的已核近期论文对象 |
| --- | ---: | --- | --- |
| survey_14 · 182.37930°, +19.24349° | 4 / 386 | NGC 4147 · 42.91′ | UMa III / UNIONS 1 · 822.64′ |
| survey_63 · 356.63691°, +27.95930° | 5 / 236 | HSC_778 · 395.88′ | Pegasus VII · 631.24′ |

重新核对 HSC-SSP 最终候选表、UNIONS 的 UMa III 与 Pegasus VII、Gemini I、Aquarius IV、DELVE 7 和 Andromeda XXXVI 的公开中心，使用精确坐标与十进制度数组合检索 arXiv 索引。最近的已核文献系统均远离两个位置。HSC 或 UNIONS 成像覆盖由各自发布和档案确定，真实公开卫星搜索掩膜依然未知。UNIONS 综述里的未公布坐标对象仍无法排除。这里记录公开资料的检索范围与匹配结果，候选分级使用独立观测证据。[survey_14 文献交叉表](../results/v8/survey14/novelty/novelty_published_candidates.csv) · [survey_63 文献交叉表](../results/v8/survey63/novelty/novelty_published_candidates.csv) · [UNIONS 综述](https://arxiv.org/abs/2503.13783)

## 2026-11-17 · expand_03-A_base-0.3-003

以 ICRS `258.077557°, +31.464058°` 作为固定中心。使用球面角距离，主匹配半径为 5′ 和 30′。所有查询的 UTC 时间、版本、完整请求、输入 SHA-256 和最近对象距离保存在匹配表。**截至本轮查询，在下列公开的银河系卫星和星团资料中未找到同位置的已发表对象。候选继续按其独立证据分级。** [逐目录实测](../results/summary/novelty_catalog_checks.csv)

| 数据源 | 带坐标记录数 | 30′ 内目标类型匹配 | 最近对象 |
| --- | ---: | ---: | --- |
| Hunt & Reffert 2024, VizieR J/A+A/686/A42 | 7,167 | 0 | HSC_453，158.42′ |
| UCC 260615, Zenodo 20705026 | 18,299 | 0 | HSC 474，413.97′ |
| VizieR McConnachie Local Group | 102 | 0 | Hercules，1,256.83′ |
| VizieR Harris VII/202, 1997 revision | 147 | 0 | NGC 6205，484.44′ |
| 固定 LVDB 与 DELVE census 五张作者表 | 246 | 0 | Hercules，1,256.84′ |

Hunt 的 12,352 条有内部编号的文献交叉项通过主表中心定位。该交叉表的无编号行没有可联接的中心。UCC 与 Hunt 的各自目录版本和收录规则不同，最近对象可以不同。[Hunt 主表](https://cdsarc.cds.unistra.fr/viz-bin/cat/J/A%2BA/686/A42) · [Hunt 文献交叉表](../results/summary/novelty_hunt_cross_id.csv) · [UCC 快照](https://zenodo.org/records/20705026)

### SIMBAD 实时锥检索

通过 CDS 的 Harvard 镜像 TAP 查询全部对象类型及别名，30′ 内 418 个对象，其中 6 个距中心小于 5′。近处六个结果为三个 QSO、一个星系、一个低质量恒星和一个一般分类恒星。30′ 内的星系群和星系团类型也存档。两锥中均未发现目录标为银河系矮星系、开放或球状星团的同位置系统。[5′ 对象与别名](../results/summary/novelty_simbad_5arcmin.csv) · [30′ 对象与别名](../results/summary/novelty_simbad_30arcmin.csv) · [类型计数](../results/summary/novelty_simbad_types.csv)

### HSC、UNIONS 与新文献

- 核对 HSC-SSP S21A 最终卫星搜索的候选中心及 HSC 1 搜索峰，最近的 HSC 表内候选 Boötes IV 距 22.75°。阅读 Virgo III 的 2026 Rubin 复核。HSC-SSP 公共数据发布、当前候选的 PI 曝光和公开卫星搜索区域是不同证据，已有曝光只支持成像覆盖。[HSC 候选表](https://arxiv.org/html/2311.05439) · [Virgo III 复核](https://arxiv.org/html/2607.25044v4) · [逐对象坐标比较](../results/summary/novelty_published_candidates.csv)
- UNIONS 1/Ursa Major III 的公开中心不匹配。UNIONS 综述提及三项正在研究的额外银河系卫星，文中没有其可核对坐标。公开查询范围内未找到这些项目的候选坐标表，故该部分状态为未核实。低表面亮度背景星系检索结果只作消歧。[UNIONS 1](https://arxiv.org/html/2311.10147) · [UNIONS 综述](https://arxiv.org/abs/2503.13783)
- 对 2020–2026 年使用候选十进制度数、`17:12:18.61 +31:27:50.61`、`J171218+312750` 及 HSC、UNIONS、Milky Way satellite、faint cluster 等组合查阅 arXiv 和公开 ADS 文献索引。结果里没有同位置报告。此轮没有使用有令牌的 ADS 全文 API。未发表、未索引或缺坐标工作保留为未知。

### 后续候选的固定检查

以冻结中心和角尺度保存查询日期与版本。先检查 5′ 和 30′ 的 SIMBAD 各类对象与别名，再交叉匹配带坐标的 VizieR、Hunt、UCC、LVDB、DELVE 和最新论文中的候选表。结合发表中心定义、位置偏差以及测光范围判读匹配。在预印本或投稿前重复实时查询，继续保留未公开资料的边界。

目录查询复现命令

```bash
.venv/bin/python scripts/novelty_audit.py
```
