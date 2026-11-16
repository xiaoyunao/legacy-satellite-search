# LS DR11 暗弱恒星系统搜索第一轮

## Q1 · 现成 gr 目录能恢复哪些系统？

Boötes I、Coma Berenices 和 Pegasus IV 的目标孔径有效覆盖均超过 99%。普通扫描在统一的 37 个距离模数和 6 个角尺度上独立执行。表中的角偏移和距离模数误差按文献真值计算。峰还需经过独立盲场的共同审查预算校准。

| 系统 | A 排名 / 偏移 / Δμ | B 排名 / 偏移 / Δμ |
| --- | --- | --- |
| Boötes I | 1 / 2.50′ / +0.14 mag | 1 / 1.29′ / −0.11 mag |
| Coma Berenices | 1 / 0.45′ / −0.13 mag | 2 / 0.84′ / +0.12 mag |
| Pegasus IV | 1 / 0.35′ / +0.48 mag | 2′ 内没有去重峰 |

Pegasus IV 是固定 DELVE census 中未达到严格阈值的 PS1 对照。A 在 LS 找到它，说明这里的 LS 目录保留了可检测信号。对 LS 相对于 PS1 的灵敏度增益，还需要匹配审查成本的评价和更多阈值对象。[DELVE census](https://arxiv.org/html/2509.12313v2)

Boötes I 中心孔径内，1,526 个基线 PSF 源中 791 个带 RESOLVED，1 个带 FORCED_POINTSOURCE，413 个带 GAIA_POINTSOURCE。已知系统的处理标志需要随恢复表一起解释。[DR11 位定义](https://www.legacysurvey.org/dr11/bitmasks/)

## Q2 · A 和 B 的审查成本

已冻结 28.533 deg² 的 PS1-assigned 有效面积，开发区 14.344 deg²，评价区 14.189 deg²。另有独立的 DES 重叠对照 3.850 deg²。普通与较好条件各有一块开发区和一块评价区。HSC、UNIONS、KiDS 和 Rubin 深搜重叠记录为未知。盲场作业状态见 [STATUS](docs/STATUS.md)。

Boötes I 的 A/B 专用搜索分别用时 41.7/39.5 秒，共用的 CMD 与面积核准备约 17.3 秒。文件和面积准备耗时 897 秒，占该任务主要墙钟时间。C 已运行于 A/B 峰及诊断位置，统计量和成员概率为候选复核结果。

## Q3 · 已观测到的限制和下一项检验

Pegasus IV 已知中心诊断给出 CMD 选星 68 个，按面积缩放的背景约 24.6 个，圆形 Plummer 联合拟合 TS 为 178.2。它的目录有明显可用信号，B 的空间去重前峰表和复核权重值得检查。该中心固定拟合单独记录于 [forced_fit_summary.csv](results/summary/forced_fit_summary.csv)。

Boötes I 的固定中心诊断在两带加深 0.5 mag 后，CMD 超额由 705.6 增至 1205.2，背景由 225.4 增至 366.8。盲场用同一个深度差检验新增过密是否提高审查成本。50/100 kpc 的 20 pc 条件目录注入用于检验给定可用成员数时的恢复差异。

[普通扫描恢复表](results/summary/known_recovery_summary.csv) · [已知中心 CMD 图](results/figures/bootes-known_center_cmd.png) · [冻结场表](configs/fields.yaml)
