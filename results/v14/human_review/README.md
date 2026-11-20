# 最终人工审查与冻结第一批记录

**最终集中审查以 [最终说明](../../../docs/FINAL_REVIEW_GUIDE.md) 和 `final_delivery_status.json` 的真实就绪状态为准。** 最终版本包含161个生产单元及两个弱源对照，共163个匿名编号；原75个对象全部保留。旧release_v2仅为冻结历史批次，不需要另行填写。

## 以下为冻结第一批的历史说明


正式入口是 `release_v2/`：40 个优先位置（202 页）和 35 个匿名位置（71 页）已全部通过材料与版面检查，`release_v2/package_manifest.json` 的 `ready_for_human_review=true`。`release.json` 保存发布目录和哈希。候选等级仍为 L0；这里没有代填人工判断。

## 先完成匿名阶段

1. 只打开 `release_v2/anonymous_phase1_only.zip`。其中包含 `blind_phase1.pdf`、B001–B035 的匿名 PNG 和 `responses_blank.csv`。
2. 将空白表另存为自己的回答文件，逐个填写 `morphology`、`CMD`、`spatial`、`technical_concern`、`confidence`、`comments`，并填写 `reviewer` 和 `reviewed_utc`。判断可用简短中文；没有问题也请明确写“无”，证据不足请直接记录。保留所有 35 个编号。
3. 将填好的表交回后，由程序绑定实际 PDF 和回答文件的哈希进行封存，再揭示身份、分数和环境资料。不要先打开 shortlist 的坐标表、身份键、C 表或环境索引。

这部分先判断形态、星族相容性和空间聚集；分数、绝对坐标、已知对象及处理环境标签在阶段一隐藏。抽样有分层和空间排除，目前只支持探索性审查，不能直接当作审查完整度的无偏测量。

## 再审查优先位置

打开 `release_v2/priority_review.pdf`，在另存的 `release_v2/priority_responses_blank.csv` 中逐项记录判断。建议 `decision` 使用“值得后随 / 疑似背景污染 / 已知系统环境 / 证据不足”，并说明依据。75 个位置均保留，不删除未过审者。

每个优先位置包括实际测光的空间/CMD 页、原生 g/r 图像和贡献源小图、距离/径向响应、观测条件，以及全部保留 C 解和已知环境表。发现坐标与 C 拟合坐标分别标注，证据图以所注明的 C 中心绘制。完整模式的原始诊断图另外保存在本地/NERSC 的 shortlist `cases/` 或 `cached_cases/`，不属于匿名阶段资料。

`g0/r0` 已去消光；颜色与 g 星等的误差共享 g，不能看成独立误差。`r_h` 是圆化半光角半径，单位角分；DM 为距离模数。C TS 及删去最高贡献源后的 TS 都是局部统计量，不是全搜索显著性。LS 的多个切选或方法不是独立观测确认。

人工回答、匿名封存和后续科学分级是后续步骤；材料生成与技术版面 QA 不代表这些步骤已完成。

## Completion and release checks

1. Every frozen case has every required retained seed represented in its C table and a complete fit outcome; no silent case omission. Recheck the frozen case/mode/policy hashes.
2. Every saved membership reproduces its local count, fitted richness normalization and local C likelihood. Verified per-source arrays are frozen on NERSC scratch. All full-mode diagnostic PNGs pass decode/CRC checks and have recorded hashes; supplementary panels use the verified snapshot and match the C table. Context includes discovery and fitted centres.
3. Both priority and anonymous layouts pass raster inspection; anonymous panel headers and PDF text contain no identity/score/environment leaks. Material image-coverage gaps remain explicitly documented.
4. The assembled `package_manifest.json` first records `materials_complete=true` and `ready_for_human_review=false`. After all PDF pages have been rasterized and inspected, layout/privacy QA sets the final human-release flag. The PDF builder refuses incomplete assembly. Internal drafts go under ignored `results/work/` and are not handed off for grading.

Actual C/integrity/context/evidence execution used owned allocation 61562188. All 75 positions/226 modes passed. The six superseded pending review parents were cancelled only after their equivalent outputs passed; bulk queue order was restored. Initial nine CCD work continues in the same allocation, separately from material readiness. The first unpublished assembly is preserved under ignored work; its cropped condition titles were corrected in release_v2. Only 40 condition pages differ; the other 233 rendered pages are pixel-identical. No user grade or identity reveal has been performed.

## Commands

On NERSC, inside the allocated Slurm CPU environment:

```sh
bash scripts/v14_review_integrity.sh
bash scripts/v14_shortlist_context.sh
bash scripts/v14_review_evidence.sh --require-all
bash scripts/v14_review_package.sh --output results/v14/human_review/release_v2
```

After allowlisted aggregates and PNGs have been synced locally, use the Codex bundled PDF Python runtime or install the optional `review` extra (`pip install -e '.[review]'`). No PDF dependencies are required for search/CCD jobs.

```sh
python scripts/v14_review_pdf.py --output results/v14/human_review/release_v2
python scripts/v14_review_validate.py --package results/v14/human_review/release_v2 --work results/work/v14-review-QA-v2
# Inspect every contact sheet and representative full-resolution pages first:
python scripts/v14_review_validate.py --package results/v14/human_review/release_v2 --work results/work/v14-review-QA-v2 --approve-layout
# Internal layout QA only; this never marks a cohort released:
python scripts/v14_review_pdf.py --allow-incomplete
```

Keep a separate copy of filled response forms; regeneration never overwrites them. After the user has completed all anonymous responses:

```sh
python scripts/v14_review_seal.py path/to/user_completed_blind_responses.csv --package results/v14/human_review/release_v2
```

The seal binds actual user responses to the final PDF hash. Only then merge scientific judgments and reveal identity/score/context keys to build the final follow-up shortlist. Exploratory nonuniform audit sampling does not directly measure an unbiased review-completeness probability; reviewer agreement still requires independent human assessments.
