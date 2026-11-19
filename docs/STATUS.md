# Status

## 2026-11-19T19:10Z — accepted area snapshot and PS1 condition boundary

- Search audit q19:02Z: **6447/6891 complete +29 no-valid-gr terminals**, all terminal masks have zero positive valid area; **24329.532515432093 summed R14 owned deg²**. All174 registered scan-retry fields accepted, zero live-covered or uncovered retry gaps. Remaining415 registered fields still require terminal accounting; remaining original outside-census arrays are queued/running. This is not a final historical union or a measured-gain footprint.
- Accepted immutable historical working-mask snapshot:6269 ordinary completed masks, excluding four known controls.720-tile union QA passes: **25181.084427368576deg² all ordinary scans**, **18173.912656795765deg² source-clock-qualified production**. Removed overlap183.555661364906 and138.297860178809deg² respectively. The qualified subset contains4220 records;1734 other completed masks await matching qualified source rosters,313 development/2 regression records remain separately accounted. Zero-peak fields are retained. Exact represented WCS working-cell union is neither continuous native-pixel area nor final production area. Census-boundary ambiguity is8.702298/4.426326deg²; labelled overlapping unions must not be summed as disjoint areas. All6891/common-clock final geometry is still required.
- PS1 conditions61589109 completed and passed four-field acquisition, duplicate/sentinel accounting and12 Jy/AB unit checks:82235 valid stack positions,517 split-primary rows discarded,11 invalid coordinates. Observed m22–23/3–20arcmin source-error g m5 medians are23.059/23.434/23.352 in the three physical backgrounds versus23.989 in the COSMOS local control; r23.383/23.417/23.286 versus23.952, while i is closer. These source-selected formal-noise/seeing distributions are not completeness or independent aperture-noise calibration. Their mismatch prevents unvalidated universal transport of the independent reference response; physical PS1 Pdet and physical LS−PS1 increment remain unaccepted, not zero. Preserve failed duplicate-guard61586412 and coordinate-sentinel61587648 attempts; canonical first-row objID policy retained, corrupted DR2 bestDetection unused. See INDEPENDENT_REFERENCE_AUDIT.md and aggregate acceptance/figure QA.
- C actual terminal failures remain explicit: DELVE-extension6 TIMEOUT registered61590980; smallest OOM-retry2 hit its29minute debug walltime without whole-shard provenance, registered regular128G/four-hour fallback **61591390**,98 identical retained seeds/34groups. Existing61584021 other shards and61585731 remain registered; both global release dependencies include the new fallback. Original partial products remain untouched.21 pending C tasks already have128G/four hours; resource changes do not change discovery/C science. Existing two scan arrays now cap6 rather than3 after actual task-limit evidence; pending Priority is not a failure or measured throughput gain.
- All144 native CCD products/288 legacy matched-policy arms and formal baseline144 replay remain accepted. Formal baseline39 spatial/31 highest-distance-correct/35 retained-correct; legacy matched baseline40/deeper64 is a separate policy experiment. No new physical PS1 claim, radius-only interpretation,50% contour or population inference. Blank matches were absent at the three reused sites/two arms, not288 independent FPR trials.
- Final whole-project human release remains false. Preserve original75/273pages and hashes, blank grades; finish terminal production/common-clock source+area+identity/necessary same-record C, selected images, probability sampling and privacy/page QA before one user review. New identity-bearing context/key/crosswalk artifacts stay private until sealed first-stage responses; prior public exposure of original75 remains flagged. No intermediate grading, automatic candidate promotion or manuscript writing.

## 2026-11-19T17:42Z — independent-reference results; production still closing

- n17:29Z actual manifests: **6257/6891 complete**,29 zero-valid-gr terminals; **24170.75825424382 summed R14 owned deg²**. Registered retries171 accepted,3 live-covered,0 uncovered. This remains distinct from historical union, candidate clocks and measured-gain area.
- Independent native PS1-image reference experiments completed:61584655→61584300 (24images,0.687282deg²,2792 labelled stars/212 faint blue) and61585005→61585006 (96images,**2.132757deg²,6800 stars/539 faint blue**,275 faint-blue held-out). Expanded actual coverage is smaller than the nominal1.6degree box. All labels, cuts and source-ID fold rules were preserved; this is exploratory same-field validation, not a new-sky holdout.
- Expanded ordinary LS blue PSF proxies g₀23–23.5:193/502 resolved/SED-galaxy labels,52 stellar,257unknown; g₀23.5–24:583/1155galaxy labels,37stellar,535unknown. Never force unknowns into either class or interpret these as all-sky purity.21 estimator cells/5 LS-blue cells have count support; conservative95% per-cell proxy-versus-stellar difference bounds in all five blue cells include zero. No statistically established universal correction is inferred.
- Native HSC observed and corrected LS magnitudes/colours remain distinct. Physical PS1 transfer still fails the full validation gate: label/IR selection, bandpass/error mapping, conditions and compact-system crowding remain limits. Neither isolated-source curves nor their count intervals establish physical LS−PS1 ΔPdet. See [independent audit](INDEPENDENT_REFERENCE_AUDIT.md) and immutable parent/hash manifests.
- Source/partition checks and both full-raster scientific-figure QA passed. Original executed sources are preserved by exact hashes. Native ASCII-reader failure61584237 preceded all image downloads; explicit whitespace parsing/retry succeeded. No primary144 trial or original75 review file was changed.
- North C61579635 both shards complete. South DELVE primary0/1 completed. DELVE-extension actual OOM0/1/2/4 retry61584021 was released early only after verifying terminal failure, immutable source and disjoint field-hash shards. Newly failed3 is registered61585731 (384seeds/116groups). Remaining original5/6 were live and7 was pending at the resource audit; follow their actual terminal states. Global release dependencies include both retries.
- 21 still-pending C tasks now have verified128G/four-hour resources in their existing jobs, following actual18G OOM/90minute-timeout evidence. The initial scontrol128G input syntax was rejected without mutation; numeric131072MiB succeeded and readback confirms128G. No running scientific task was canceled, threshold changed or fit owner duplicated.
- Final production/area/C freeze and one final human-review package remain pending. Original75 records and blank grades are intact. No candidate promotion, interim grading, population inference or manuscript writing.

## 2026-11-19T17:10Z — formal-policy replay accepted; independent reference denominator under investigation

- Manifest m16:58Z: **6116/6891 complete +28 no_usable_gr**, all no-usable masks have zero positive valid area. Summed R14 owned area **24023.278130787032 deg²**; this is not the deduplicated historical union or a measured-gain area.174 registered retry fields:168 accepted,6 live-covered,**zero uncovered**. Do not submit duplicates.
- Packed113 retry61575703 and guard61575704 accepted all113 fields; original held fallback tasks retired only after per-field product checks. Original bulk outside-census scans and regional C continue.
- Formal A-baseline same-catalogue replay61579269 **COMPLETED/51:52**; statistics61582141 **COMPLETED/35s** and accepted all144. Spatial39/144, highest-DM correct31/144, retained-correct35/144; selected members1170 unchanged. C was not replayed. Original matched-budget baseline40/deeper64 remains a separate experiment. Never compare formal39 directly with matched-deeper64 as a depth effect.
- Initial statistics61580560 failed because the compact summary lacks model_sha256; corrected the metadata-only validator to verify the accepted raw blind CSVs and their parent hashes. No native realization or scan was repeated for this repair.
- Independent COSMOS2020 Farmer v2.2/DR4.1.1 download61582406 completed and checksum/CRC/schema passed:964506 source rows,198942 observed-HSC-g17–25.5 extracted rows remain exclusively on NERSC. PS1 DR2 nine-cone acquisition61582407 completed. Raw Phase3 coordinate aliases ALPHA_J2000/DELTA_J2000 are explicitly normalized; first alias-read failure61582112 is preserved.
- First reference test61583502 completed, but the common LS/census-PS1 mask leaves only0.00118634 deg²,29 reference positions,2 morphology+SED stars and0 faint-blue stars; **no supported validation bins**. This is not a PS1 calibration or evidence that the full deep reference lacks stars. A compute-node mask diagnostic is investigating the lost denominator before any response use. No physical PS1 transfer or system-level LS−PS1 gain is accepted.
- North C61579635 shard2 completed; shard0 was still running at17:03Z. Area repair61579696 completed first12 shards; remaining12/collector61579698 were live/pending. These are not final provenance/area closure.
- Original75 review files/identities/hash records unchanged; all human grades remain blank. Final release is deferred until terminal production, common-clock union/identity/C, complete evidence, probability sampling and anonymous/page QA pass. No interim user grading, new-system promotion or manuscript writing.

- Follow-up: native reference denominator diagnosis61583938 identifies census FOOT128, not absent LS exposure. Native PS1 exposure/mask acquisition61584237→external validation61584300 is registered separately; no production-mask change. South DELVE-extension C OOM0/1/2/4 registered61584021 (128G), global release dependencies extended. North61579635 both shards now COMPLETED.62 local tests pass,2skip; changed Python modules parse.

## 2026-11-19T15:40Z — real boundary sensitivity and continued production closure

- k checkpoint:5753/6891 complete,25 terminals with zero valid gr area,23363.8834 summed R14 owned deg².11 explicit OOM fields now covered by61579459; prior4 OOM retries completed. Historical union remains separate.
- North C original0/2 actually TIMEOUT; six other shards complete. Retry61579635 is running on the same source/selected modes, with longer walltime and strict reuse. Required C is still incomplete.
- **Accepted:**30pc targeted boundary61579782. Same draw34 across three skies,267→278 rendered, baseline1/3→2/3,deeper3/3→3/3;46/324eligible remain outside. This demonstrates finite-stamp outcome sensitivity, not a corrected population rate.
- **Accepted:**member-origin61581071; original baseline selected sets unchanged, extra2/1/2come from outer members; rendered true-light proxy19.20587→23.56514. No one-case population correction.
- **Accepted:**angular-context integration61580295; all7994 records/7822 provisional positions/75 identities and original numerical columns unchanged.511 source records carry known-position proximity independent of distance-mode agreement.
- Geometry repair pilot61579408 passed original-success and real-failure comparisons;61579696→61579698 awaits the original array. Full area is not accepted yet.
- Formal-policy replay61579269 is running; its acceptance/statistics61580560 is queued. Existing matched-policy144 acceptance and288 measurements remain preserved. Physical PS1 response is still unvalidated.
- Final whole-project human release remains false: terminal production, common-clock area/identities, required C, all selected evidence, probability sampling and anonymity/page QA are still needed. No intermediate grading.

## 2026-11-19T15:10Z — all144 CCD products and288 matched-policy LS arms accepted

- **Completed:** native61572579; full LS owner61576217; acceptance144/288/6048stage rows; statistics61574814; unchanged-numerics figure QA61578492; allfour OOM retries61575366.
- **Actual legacy matched-budget results:** spatial40/144 baseline,64/144 deeper; highest-DM-correct32/144,52/144. These are48 shared populations across three selected skies. Physical PS1 is unvalidated; formal-production completeness is not yet measured by these counts.
- **Completed pilot / submitted full:** production-policy replay61577474 completed18 checks;61579269 runs the same144 native catalogues under the formal A baseline policy, not new CCD realizations. C replay is separate.
- **Area incomplete:** all32 vector shards and index complete;61574869 has GEOS overlay failures.61579303 diagnoses the actual failing tiles.61574870 must not be reported complete while tiles are missing.
- Existing6891-field search, packed retry61575703→61575704 and regional C/release chains continue. Last published search checkpoint remains j until the running k audit finishes; do not combine different candidate/area clocks.
- Original75 review release is frozen and unfilled. Final all-project review still needs terminal production, common-clock geometry/identity integration, required C and full evidence/privacy/page QA.

## 2026-11-19T13:37Z — full-seed C audit, tiled-area validation and controlled retries

- Search checkpoint j (13:24:48Z): **4948/6891 complete**,20 no_usable,**21309.497847222217 owned deg²**. Original seven-background56-trial experiment remains complete; the new144-repeat product/measurement clocks are separate. Four newly uncovered fields have explicit44G science-step OOM logs; registered **61575366** retries with128G allocation/120000M step, unchanged detector/configuration. Do not confuse resource failure with no coverage, or completed-step RSS with an allocation-wide safe memory bound.
- Strict catalogue **61573608 COMPLETED/20:32** and independent exact-seed/proof audit **61574874 COMPLETED/1:17**:7994 qualified records/7822 provisional positions;2924 records have **all7140 original retained seeds** complete.5070 records/9968 seeds are not attempted, retained honestly. These include work still covered by scheduled regional C and historical low-priority records; the final review selection and evidence/membership QA are not certified. All75 frozen identities/blank user grades remain.
- Direct versus tiled real32-mask union **61574703 COMPLETED/5:03** agrees to<1e−12deg². Global interim snapshot registers6269 actual ordinary masks: **61574867 vectors →61574868 index →61574869 tiles →61574870 collect**. It is not the final source/area freeze or a gain footprint. Per-tile intermediates stayNERSC; publish aggregate areas, immutable inventory and hashes.
- Packed retry pilot **61575067_0 COMPLETED/6:11**,8/8 field manifests/rasters/peaks verified; measured science-step RSS15.22GiB. Old corresponding held tasks were superseded only after real products passed. Initial guard submission hit the debug submit limit; regular guard61575080 was installed, then retired after the successful metadata finish. Remaining113 original pending quota-recovery fields are registered in **61575703** (8 fields/task,four workers) with guard **61575704**; preserve the old individual holds as per-field fallback. No new truth, grid or discovery threshold.
- Native repeat checkpoint13:37:15Z:133/144 product proofs, still only9 accepted full two-arm blind trials. Existing61568456→61568539→statistics61574814 chain is preserved. The three background measurements can now run independently with `v14_repeat.sh measure_site <field>` only after all144 native proofs; no scientific estimator changes. An additional shared-interactive request was rejected by the actual two-submit limit; another project occupies the other slot and must not be touched. No new measurement owner was acquired or original measurement held at this checkpoint.
- Analysis design `configs/v14_repeat/analysis.yaml` freezes shared-block/background paired resampling plus conditional exact Monte Carlo intervals. Identical shared populations across three skies must not triple the sample size; zero discordances retain nonzero finite-sample uncertainty.62 unittests pass,2 skipped. True V-proxy flux-stage bookkeeping is diagnostic only and awaits real full-grid acceptance; never replace it with fitted-flux accuracy or physical PS1 completeness.
- The source-tagged comparison ledger records DES/PS1 historical masked areas and compact recovery precedents; Tan's compact AppendixA and1–100pc image AppendixB already cover related physics. Current grid has no15pc node, two target V proxies and varying realized light. Do not manufacture continuous completeness contours, new-area claims or population constraints. Independent faint-blue PS1 validation and30pc near-threshold truncation sensitivity remain outstanding.

**User review stays deferred until the full eligible production sample, exact area/identity reconciliation, required same-record C and all evidence/anonymity/page QA converge. Preserve release_v2; no intermediate grading or manuscript writing.**


## 2026-11-19T12:01Z search checkpoint and completed integrity/physics controls

- Actual audit i: **4469/6891 complete**, **18 no_usable_gr**, **20145.297210648143 owned deg²**. This is the R14 registered-mask sum, not the historical union, previously unexplored sky or physically validated gain area. Seven newly terminal, uncovered fields are registered once as **61574390**; pending regional summaries 61470263/61470265 retain all previous dependencies and now include this retry.
- Remaining CCD native work runs on owned **61572579**, one Slurm step/four disjoint CPU workers. `repeat_full/native_progress.json` is the dated product-only count; only the original nine trials currently have accepted two-arm blind measurements. Original pending array 61568439 is deliberately held while the owned job processes the same registered tasks. Guard **61572628** either rebinds existing full measurement61568456 after all144 proofs, or releases the original fallback; do not submit duplicate native tasks. A first nested-step allocation serialized and was retired after preserving its one completed product; no science draws changed.
- **30pc guard61571822 / acceptance61574388** completed. One shared bright draw (realized V proxy −3.770) across three backgrounds, original260→extended274 of300 magnitude-eligible stars;26 still outside. Baseline selected totals61→64, deeper96→98; all six paired arm cases remain detected. This is a ceiling-case stage check, **not a measurement of near-threshold truncation bias**. The primary144 and initial-nine files remain unchanged.
- Independent CFHT-r shape audit **61572239 COMPLETED/40s**: faint-blue held-out reference counts9/10 at backgrounds2/3, but only0/1 have adequate independent point-shape support. The r images cannot validate PS1 response for the target faint blue sequence. Do not lower shape SNR or interpret brightness-conditioned PS1 selection as a measured contamination correction; physical PS1 Pdet/ΔP stays unvalidated.
- Restored missing original historical policy/zero-peak field ledgers by exact source hashes. The interim registry now contains7994 qualified records/7822 provisional positions, all75 identities preserved. **These counts predate the new strict legacy-C refresh61573608**, which is running. Legacy C now needs exact same-source input seed sets plus row-level discovery/position/DM/scale binding; unbound fits remain contextual, never certify production. Available C is still not all-required-seed completeness.
- **61572250 COMPLETED/19s** independently rechecked all75/226 frozen membership modes into a new namespace, using the original frozen proofs. Release_v2 and its source/hash files were not modified. Native-validation reruns now verify existing hashes without rewriting accepted initial proofs;58 unittests pass,2 skipped.
- Actual mask-union pilot **61573759 COMPLETED/3:52**: in the registered8°×8° window, represented qualified-cell union35.5856133406 deg² versus summed source pieces38.8133192874; all ordinary scanned masks52.9569565814 versus62.8946453078. This confirms overlap must be removed geometrically. Exact union is over the original WCS-derived working cells (usually5″), with source area reproduction, RA seam/pole clipping and explicit census-label ambiguity. It is a bounded technical/science-area pilot, **not full-project area**. Pilot inventory/code are archived by SHA before inventory refresh.

**Continue:** finish live search/native/C chains, complete all144 blind measurements and calibrated paired uncertainty, compute full historical mask union from source-qualified records, then define final independent review units and complete evidence/anonymity/page QA. Preserve the first75 and blank grades. No intermediate user review, unsupported physical gain, population inference or manuscript writing.


New C evidence integrity (61572142,54s): two actual unchanged fits now bind content-addressed, SHA-verified membership arrays; reconstructed TS matches saved TS. Legacy cache aliases remain compatible, while later passes cannot replace the row-bound artifact. Original75 frozen files/grades are unchanged. Final material QA must use these bindings or verified historical frozen copies, never assume a field/rank cache is still the correct fit.

## 2026-11-19T10:55Z checkpoint: integrated sources and independent images

- Search manifest h: **3977/6891 complete**, 15 no-usable-gr, **17871.851998456787 owned deg²**. These are R14 registered owned-mask areas, not the final historical union or a measured-gain area. Six newly terminal gaps were registered once in **61571922**; the two affected pending summaries now wait for it. Existing 131-field recovery **61568908** remains active.
- Snapshot **61568667 COMPLETED/0:0/43:15**: R14 incremental production has **6708 records /6660 provisional associations /1032 records with a successful eligible C**. Historical qualification now covers 57 source tables and **7833 records**, reconciled to **7665 provisional positions**, with 1671 records having an available successful same-record C. All **75 frozen identities** cross-match their current source position; all user grades remain blank. This is not a final production freeze: necessary-seed completeness, exact historical mask union, terminal search completion and image QA still remain. See `results/v14/production_integration/reconciled/`.
- Native CCD progress is separately recorded in `results/v14/repeat_full/native_progress.json`: 34/144 native products validated at this checkpoint, while only the original nine have full two-arm blind measurements. Remaining-array concurrency was raised from two to four after four real tasks completed with <7 GiB measured peak RSS; per-task resources, seeds and science cuts remain fixed. Full measurement/acceptance remain **61568456/61568539**, after all native tasks.
- CADC is accessible again from local and NERSC. Four 0706 CFHT u/r science/weight artifacts were downloaded to NERSC and size/MD5/SHA verified. **61571692 COMPLETED/0:0/21s**: independent r has 93.6% full-aperture core coverage and observed PS1-r-equivalent 5σ aperture depth **23.509 mag** (27 references, 9 held out, 0.191 mag scatter); u has zero valid core/annulus support. No standard deep g was found; gri is a different filter. These data do not establish a stellar population; **0706 stays L0**.
- Independent CFHT r measurements at physical-background sites 2/3 completed in **61571902**: alternate stacks fully cover the 0.75′ cores, with aperture depths **23.558/24.025 mag** and held-out scatter **0.042/0.038 mag**. Their 2.47′ stamp supports are only **87.6%/78.2%**, so they are potential local morphology checks, not whole-stamp truth or calibrated PS1 physical response. The first selected site-2 stack has no valid support, and the first site-3 stack covers only 16.3% of the core; retain these failures rather than treating metadata intersection as coverage.
- Single-case faint-light guard **61571693 COMPLETED/0:0/1:56**: original site-1 trial 00 has the same 311 response stars; adding 5703 faint stars to CCD pixels gives detection/PSF/hard-cut counts **30/20/1** versus **35/20/1** at baseline, and **30/20/3** versus **35/20/4** when deeper. Neither variant is spatially recovered. The reused control reproduces the accepted initial counts. This one deliberately chosen shared draw does not estimate a global bias or clear the other cells. The primary 144 are untouched. Separate **30 pc radius guard 61571822** is submitted; it compares the same draw/CCD frame at original and 3.1′ injection radii, leaving residual tails explicit.
- Euclid-context C **61570645_282 COMPLETED/0:0/2:51**, six ordinary groups/nine seeds, all fits complete. The three Ursa-Minor-II-associated groups have best TS **19.38/8.62/11.86**, after-top-three **2.50/0.039/0.597**; no new discovery or user grade is inferred. A new *any spatial group* distance diagnostic preserves, rather than replaces, the registered highest-A-group recovery metric.

**Final delivery remains deferred:** finish the full registered search, exact historical area/position reconciliation, same-record required C seeds and complete evidence/anonymity/page QA before the user's single formal review. No interim manual grading, physical ΔP claim, unsupported completeness contour or manuscript writing.

## 2026-11-19 PS1 条件响应和新增已知环境

61569134/0:0/51s 已完成三个背景20′参考样本敏感性审计：暗端普通PSF入选23.9%、43.9%、38.8%；同星等/颜色支持分箱的较严形态组高1.9–2.7个百分点。所有暗端Gaia标签均较红，不能验证目标蓝主序或识别LS污染率。48潜在星族的生成星等截断遗漏完整IMF V proxy光中位14.68%，恢复偏差未实测；和30pc空间截断分开验证，保持144原样。

Euclid 2026-11三已知系统补入交叉识别（原18恢复集和探测器不变）。已有快照3条来源组靠近Ursa Minor II/Euclid UFSS DR1 1，但最高DM并不都准确；只记后验已知环境，不是3个新发现。单字段6组/9种子的普通A→C复核61570645已提交，缺结果不填零。详见 `docs/COMPARISON_SCOPE_20261119.md`、`results/v14/repeat_full/scope_diagnostics.json` 与 `results/v14/production_integration/euclid_context_matches.csv`。一次最终人工审查政策不变。

**Active execution:** CCD own 61568227 / array61568439 → measure61568456 → accept61568539; scan retry61568908; refreshed production61568667; DES retry summary/C61568973/61568974. Twelve native trials have product validation, but only the original nine have completed two-arm blind measurements. User review remains deferred.

Latest checkpoint g (2026-11-19T09:29:06.064749+00:00): **3462/6891 complete**, 10 no-usable-gr, **15451.314 owned deg²**. The older f checkpoint below predates 131 newly uncovered terminal failures, identified during the HOME quota incident; inspect `results/v14/progress_20261119g/retry_execution.json` for the subsequent registered recovery job. Science candidates still have a separate older summary clock.

## 2026-11-19 authoritative next-round policy (GPT Pro 437262c6)

The user will perform **one final, project-wide human review**. The first frozen 75-position `release_v2` is a technically validated historical batch, not an instruction to begin grading. Preserve every file/hash and blank response; do not seal or reveal identities. Final delivery waits for the full eligible production sample, historical reconciliation and exact owned-mask area, necessary same-record multimode C, complete images/evidence and anonymity/page QA. No intermediate batches require user judgment.

Continue frozen full-DR11 A baseline/regional policies and the remaining 135 of 144 physical CCD trials. Keep shared IMF realization IDs, target/realized light, native exposure/detection/PSF/hard-selection/CMD/blind-distance/C losses, and quantify the finite stamp at 30 pc. Validate the physical PS1 DR2 joint response and reference contamination/support uncertainty before any LS−PS1 gain claim; preserve Tan PS1 DR1 separately. Gains require >0.10 and positive 95% lower bound with shared IDs resampled jointly across backgrounds. No unsupported completeness contours, population inference or manuscript writing.

Latest manifest checkpoint f: 3,296/6,891 complete, nine no-usable-gr, 14,536.704 owned deg²; eight retry fields accepted, seven live-covered, zero uncovered. This is a newer area clock than the 5,614-record incremental candidate snapshot. Historical production integration, full repeated physics, PS1 validation and final review assembly remain outstanding. These requirements supersede older “review now” passages retained below as history.

## 2026-11-19 初批 CCD 已实测验收，计算资源已释放

- 61562188 与主 step 均 COMPLETED/0:0；9 个实现/18 个深度结果/378 阶段行通过完整性验收。原 pending CCD/测量链和退出 guard 已退役，无残留 hold；bulk Nice 实际回读全为 0。
- [首批验收](../results/v14/repeat/initial_nine_acceptance.json)与[逐项结果](../results/v14/repeat/initial_nine_summary.csv)：基线/加深位置恢复 5/9、6/9，最高距离模式正确均 5/9。仅初始软件/资源样本；实际光度与半径混杂，不作完整度或显著性推断。
- 75 位置审查包保持 release_v2 原哈希；没有代填用户判断或执行身份揭示。完整 144、物理 PS1 响应、用户科学判读及全足迹收尾仍为后续项目工作。

## 2026-11-19 正式人工资料已通过技术验收

- [审查入口](../results/v14/human_review/README.md)，正式目录 release_v2。40 优先位置/202 页、35 匿名位置/71 页及独立匿名 ZIP，75/75 实测补页、226/226 成员模式核验通过。
- 全 273 页栅格检查完成；修复条件图标题裁切后保留原未发布哈希，233 页完全相同，40 条件页重排。正式 ready_for_human_review=true。两个回答表共 75 行均空白；人的等级、封存与身份揭示尚未执行。
- 自有 CPU 61562188 继续实际首批 CCD，0–3 产品通过、索引 4 运行中；测量与全部 144 次完成度分别记录。原复核队列已被等价产物替代，bulk Nice 已恢复；原 CCD hold/退出回退保留，当前持续目标未结束。

## 2026-11-19 实际 CPU 执行接管

- 获批本项目独立交互 CPU 分配 61562188，实际计算节点 nid200010。通过 srun 运行，四个 C 分片均已完成；不是登录节点计算，也未占用其他项目现有分配。
- 原 C 数组 61556312 已确认全 PENDING 后 hold，避免重复；退出回退 61562541 已登记。尚未取消原步骤或宣称新分配完成。
- 实际完整 retained-C/PNG 包 75/75；全模式成员核验 75 位置/226 模式通过，发现及拟合中心环境已更新。统一补页正运行，最终组装/全页 QA 未完成，人工包保持未发布。原 CCD 九任务经全 PENDING 复查后加入同一退出回退账本并 hold，等待本分配串行接管。
- [实际接管记录](../results/v14/priority_execution/interactive_handoff.json)。后续依计算产物逐步验收，成功后再退役等价旧步骤；失败释放原 pending hold。

## 2026-11-19 调度资源窗口

- 原数组 61556312 与 61556314 仍未派发。已按实际小任务耗时与分片模式数，允许最小 backfill 时限 45/20 分钟；回读最长请求仍为 2h/80min。输入、种子、CPU/内存和科学配置保持。
- sdiag 确认调度器仍循环工作；待运行队列较大。TimeMin 更新不代表已启动，也没有新增完成产物。完整材料仍未发布。
- [实际请求回读](../results/v14/priority_execution/backfill_time_min.json)。后续继续核查原句柄，分配后以实际时限、终态 manifest 和产物验收。

## 2026-11-19 后续 manifest 与成员一致性验收

- 实际逐场审计 progress_20261119d：3,151 完成场、8 空场、13,626.117035 owned deg²。61554330_0 已完成（17:55）并通过 manifest；补跑 6 验收、9 live-covered、0 uncovered。
- 已确认 C 的成员缓存使用共享“field/depth/rank”路径。补充逐模式一致性验收：源数、无重复 ID、概率和与 richness×profile_integral、从概率重建局部 TS；验证后原始数组固定到 NERSC scratch，不同步逐源数组。
- 61559482 完成（37 秒）：P001 五模式＋B001 一模式均通过，重建 TS 与保存值在浮点精度内一致。仅两对象原型，不计作 75 对象整体验收。
- 61559510 为全模式验证，等待 C；61558007 改为等 C 和验证后从固定数组绘图；61558755 还需验证、全证据和最终环境。添加已完成旧 smoke 到依赖时 Slurm 报 dependency problem，去掉已满足的旧编号、只保留活跃依赖后更新成功。没有重复提交 C 或 CCD。
- 发布新增校验冻结名单/模式/计划哈希、所有模式 PNG decode/CRC 与哈希、补页源数组与验证记录一致。空白人工表和全样本分母保持。C/CCD 仍为正常 Priority 队列，正式审查包未发布，目标继续有效。

## 2026-11-19 人工审查包准备（尚未交付审核）

- 最新 GPT Pro 46d21aad 已完整读完（4 轮、无后页、5,020 字符）。用户明确等包齐后亲自判读；没有替用户新增人工科学分级。已建立持续执行目标，以 40 优先＋35 匿名材料全部验收并同步为完成条件。
- 当前完整旧 C/诊断包仍 33/75；新实测统一补充页完成 P001、B001 两个原型。61557934（26 秒）、61558097（48 秒）实际完成，从保存的成员概率及测量星表画误差、核心/背景 CMD、空间轮廓和原生 gr。匿名图隐藏绝对坐标、源身份、分数、环境和处理标记；完整材料分别保留在揭示键中。
- 新 PDF 编译器生成两套独立图册、空白表和匿名独立 ZIP；不齐默认拒绝正式发布。已逐页栅格检查原型的证据、像素、环境、模式表版式，并验证匿名 PDF 文本无身份泄漏。内部缺页草稿只在 ignored results/work，不提供给用户审核。正式人工材料与机器初筛结论分开，匿名判断封存后才揭示身份并合并后随名单。
- 61556312 的 4 个 C 分片仍 Priority，61558007 的 75 对象完整证据重绘等 C；61556642 等 C 更新所有拟合中心环境。初批 CCD 61556314/61556315 仍排队/等依赖，没有新增配对结果。
- 本项目六组排队扩面父数组暂设 Nice +1000，让审查链先于它们；既有运行分配、补跑及其他项目未变。61558199 会在 C 失败时恢复，或在 C 成功后登记证据作业结束时的恢复任务。原 Nice 值保存 ignored logs/v14-review-queue-order.json，待核验实际恢复；不是取消全区搜索或绕过账户资源限制。
- 新逐场审计 progress_20261119c：3,142 完成、8 空场、13,623.963586 owned deg²；补跑 5 验收、10 live-covered、0 uncovered。生产候选快照与新面积仍分开。
- NERSC 项目环境增加可选 reportlab 5.1.0、pypdf 7.1.1（pillow 13.0.0 已有）；核心搜索依赖未变。本地用 bundled PDF runtime，pyproject 的 review extra 给出复现入口。

## 2026-11-19 最新评审执行与真实小任务验收

- 已完整读取最新 GPT Pro 消息 af4ec677（三轮，无后页），未用 computer use。NERSC 认证过期后由用户自行更新，现已验证可用。
- 新审计 progress_20261119b：3,117 完成、8 无有效 gr /6,891，13,456.908 owned deg²。补跑 4 验收、11 活跃覆盖、0 未覆盖。候选生产汇总保持独立快照，未把新增面积视为已审候选面积。
- 冻结 40 优先 +35 分层审查位置；同记录旧 C/图像复用 33 个（19 优先/14 审查），复用作业 61557017 COMPLETED。新 P001 复核 61556311 完成，5 个模式；与复用 P001 重叠，不加计位置。优先及审查队列剩余模式复核由 61556312 数组继续等待。
- P001 真实图像呈扩展星系碎片，高 C 仍 L0/背景优先解释。新增发现/C 拟合双中心 SGA 上下文；61556641、61557190 完成，当前 75 个发现中心和 130 个 C 中心已标注。P007 约 44.7′ 邻近 Ursa Minor，未知环境尚未排除，不称新系统。完整模式 PNG 留本地/NERSC，公开最高 C 优先图与聚合表；盲审尚未分级。
- 三背景重复已登记 144 个潜在实现，初批仅 9 个 CCD 作业已提交。61556313 COMPLETED（2:54）；61556503 测量完成（1:40）：唯一新物理实现两深度均恢复正确距离。旧七背景 56 个实现另计。
- 实际 PS1 条件选择审计 61556316、局部 20′ 审计 61556716 均完成，图和统计已同步。尚未得到验证后的三臂物理响应或完整物理曲线。
- P002/P007 公开影像元数据查询：NOIRLab 成功，只返回 90Prime/Mosaic3；CADC SSL/超时失败，独立深双波段覆盖未证实，没有把旧 LS 输入影像当成独立验证或无覆盖结论。
- 当前等待：61556312（4 个 C 分片）、61556314（9 个 CCD 初批）为 PENDING/Priority；61556315（测量）和 61556642（最终中心上下文）为 Dependency。提交不计完成。见 [实际调度快照](../results/v14/priority_execution/scheduler_snapshot.json)、[审查准备度](../results/v14/shortlist/review_readiness.csv)。

## 2026-11-19 最新验收

- 内置对话接口已恢复，完整读取目标对话两轮消息，GPT Pro 最新全文已核对，未使用 computer use。
- 最新逐场审计：3,078 完成场、6 个无有效 gr 场、13,323.228 新 owned deg²。比 11-18 检查点新增 152 场、639.478 deg²。七 CCD 背景的 56 次实现仍完整。
- 61511922 COMPLETED（43:41）。候选索引现含 11,217 记录、31,846 模式、7,000 临时关联；图册使用 2,992 张新栅格，含此前 13 个极区场，均与最新 manifest hash 一致。索引和图册不是最新 3,078 场的同步终态。
- 61510268 已完成 3 个原补跑，剩余 10 个排队。61510268_3 被 sacct 暂漏列，展开 squeue 证实其仍 PENDING。修复后真正新缺口为 2 个 South DELVE extension 超时场，61554330 已提交，61470263 的区域汇总依赖已追加；尚未完成。
- 已输出 R14 增量生产表：5,614 主档记录、5,568 临时关联、1,026 个记录有同资格 C 拟合。开发、历史和替代档分开，人工分级/后随未知留空；不是完整 DR11 物理样本或恢复率。
- [最新审计](../results/v14/progress_20261119/manifest.json) · [生产筛选流程表](../results/v14/production/candidate_funnel.csv) · [评审验收清单](PRO_REVIEW_CHECKLIST.md)

## 2026-11-18 13:55 UTC+8 复核

- 新 progress_20261118c 逐场审计仍为 2,926 完成 / 6,891 登记场，5 个无有效 gr，12,683.750 owned 有效 deg²；与上次 b 快照无新增完成场。
- 七 CCD 背景全部完整。13 个缺失场全由待运行 61510268 覆盖，零个新增未覆盖终止失败；61511922 仍未开始，61510994 为 TIMEOUT。未重复提交作业。
- 逐场、逐层、CCD、补跑及未覆盖清单与 b 的相应表逐字节相同；新快照保留当前 manifest 与 Slurm 核对时钟。
- [最新逐层面积](../results/v14/progress_20261118c/area_by_cohort.csv) · [完整性审计](../results/v14/progress_20261118c/manifest.json) · [续跑核对](../results/v14/progress_20261118c/continuation.json)

## 2026-11-18 BASS 扩展标定验收

- 61514532 已完成（01:11），结果与三种图格式已同步。离核 1–5′ 参考区每波段保留 18 星，各留出 6 星；g₀/r₀ 的 1.5″ 孔径 5σ 深度为 23.67/23.28。完整核心均为 100%，背景环仍为 49.1%。留出中位偏差 g/r=0.047/0.008 mag，散度 0.068/0.014 mag。
- 冻结 μ=19.25 原生模板的最亮 stage-1 主序点 g₀=22.935。图像深度及独立曝光存在不等于共同星族确认；本次没有新增 CMD 检出或完整度测量，0706 保持 L0。
- sacct 核对 61510268 与 61511922 仍 PENDING；61510994 TIMEOUT。原有面积和候选快照沿用各自时钟，本次没有重新审计全部场。
- [新图像测量](../results/v14/0706/bass_images/summary.json) · [本次验收](../results/v14/0706/bass_images/acceptance.json) · [保留初测](../results/v14/0706/bass_images/initial_summary.json)

## 2026-11-18 再次跟进（12:18 起）

- 最新独立审计：2,926 完成场、5 个无有效 gr 场，新增 owned 有效面积 12,683.750 deg²；比前次多 4 个 South DES 场与 37.238 deg²。新表位于 progress_20261118b，原快照保留。
- 61510994 超时（29:07）。十三个缺失场无成功终态，均由 61510268 排队覆盖；逐场与终止数组/活跃数组核对，没有新增未覆盖缺口。61511922 尚未开始，等待已完成分区的单独图册任务后继续正式汇总。
- 61513679 已完成（17:38），更新候选索引及两坐标图册。候选索引含 11,134 记录、30,466 模式、6,938 临时关联；来源含历史开发/多档位记录及部分已汇总分区，不能视为新天体计数。完整分区汇总仍待 61511922。
- 图册验收发现另一组 13 个已完成极区场漏绘，合计 37.893 deg² 已计入表中面积；修复包围盒纬度边界并通过测试。现有图片仍带此已知遗漏，61511922 运行后重绘；扫描数据及阈值未改。
- CADC 本地/NERSC 各三次 GET/POST/健康查询均失败（HTTP 503/TLS EOF），CFHT 覆盖仍未知。本轮没有通过 CADC 获得新深 g 像素。0706 仍 L0。
- 61514438 已完成 BASS 独立曝光核心图像测量：g₀≈23.58、r₀≈23.18（5σ），核心完整、背景环 49.1% 有效。仅 4/5 个标定星，初测有限；扩大离核标定样本的 61514532 仍在排队。共享交互分配尝试因无资源取消，批任务已恢复等待。
- [新审计](../results/v14/progress_20261118b/manifest.json) · [补跑核对](../results/v14/progress_20261118b/retry_followup.csv) · [CADC 实测请求](../results/v14/0706/cadc_followup/summary.json)

## 2026-11-18 当前核查

- 2,922 个场完整，5 个场无有效 owned gr，合计 12,646.511 有效 deg²。North 主层 408/408；South PS1 为 1,038 完成 + 1 无可用；South DELVE 391/993；South DES 372/497。各扩展层详见最新审计表。
- 七个真实 CCD 背景的 7 个空白和 56 个注入产物及测量 manifest 齐全。South PS1 基线/加深 8/24、9/24，North 10/16、6/16，DELVE/DES 基线 2/8、3/8。
- 61510268 为 13 个实际缺失场的高内存补跑。debug 数组提交受本站 QOS 限制拒绝，61510994 先以 debug 两个 worker 尝试这 13 场，正式数组等待它结束并跳过已完成场；相关分区汇总依赖已包含正式补跑。后续密集批次改成每节点两场、每场 44 GB，其他批次四场、每场 24 GB。
- 61510285 的 HOME flock 524 已修复。scratch 锁实测通过，61510733 在 debug 的 30 分钟限额后 TIMEOUT（实际 30:26），已完成分区表保留。计算节点的 DVS/IPC 文件 I/O 等待明显，补跑尚未终态，不能记为完成。100 GB / 4 小时的正式队列汇总兜底 61511922 已解除前序依赖，等待调度；后续分区汇总也已增加资源。
- 0706 的公开目录任务 61510489、61510609 已完成。独立 BASS 与 PS1 星族支持较弱。61510836 已完成独立像素测量，61510733.0 已完成重导出图像及 i 波段对应源统计；取消重复待运行的 61511117。PS1 / SDSS g₀ 深度约 22.13 / 22.45，独立 i₀ 约 22.30，均覆盖核心但未达到暗主序验证需求。下载到 scratch 的图像包含 PS1 gr、SDSS gr 和未进入 DR11 的 DECam i，CADC 仍服务错误。
- 已同步 24 个完成 C 分片的 624 组、1,685 个模式，来自 North、North extension、South DES extension 和 South PS1，均保留人工图像审查待办。
- [逐层实测面积](../results/v14/progress_20261118/area_by_cohort.csv) · [逐场 manifest 审计](../results/v14/progress_20261118/fields.csv) · [七背景 CCD 结果](../results/v14/image_response/seven_background_recovery.csv) · [0706 档案核查](../results/v14/0706/archive_audit.json)

## 第十四轮全足迹执行

- 61469764 用 1,484 张已完成的搜索掩膜重算全场登记。冻结了 6,884 个残余单元，South PS1 主层有 1,039 个；北区、South DELVE、South DES 主层分别有 408、993、497 个。记录区块空间所有权和旧掩膜来源。
- 61470501 的已同步快照包含 71 个 South PS1 实际完成区块、0.9316 有效 deg²、1,336 个全模板峰和 565 个去重峰。两个冻结档均为 0 组。
- 首批运行发现残余所有权模块漏导入 `unit`，已修复并添加基本所有权回归测试。61470438 的四个首批任务均已成功复跑，61470439 补跑次批。61470417 在 8 个真实砖块逐点核对可共享的掩膜缓存，194,488 个采样值完全一致。暖缓存已启用。
- 61470317 核出约 9.78 代理 deg² 的唯一北区灰缝，补登了 7 场，由 61470504/06 完成 6 个有效场与 1 个无有效 gr 场，合计 7.8453 有效 deg²。开发样本尚未给出有限主阈值。最新总汇作业为 61470508。
- South PS1 61469829 先运行，后续三层为 61469832/61469835/61469842。各扩展和 census 外天区为 61469845/47/48/49/50/51。各数组结束后按已完成 manifest 汇总，C 与全区汇总链接至 61470247–61470267。完成状态与资源数据见 [Slurm 快照](../results/v14/slurm_job_status.csv)。
- 61469723 在同一实际光学掩膜试验里从两套原生目录恢复 Boötes V。61469874 已完成 240 个共同注入位置的 Tan PS1 DR1 发布模型计算。已注册 7 个真实 CCD 背景，用 61469705/06/07 分别处理空白、56 次注入与盲搜复核。61470535 完成首个真实场的 6 个注入，共同基线和加深分别恢复 3/6 与 3/6，入选人工源为 53 和 71。
- 历史候选 C 补审 61469805/06 已完成 231 组、274 个模式。61470672 的三组新优先 L0 诊断与 LS g/r 小图已生成。统一候选表保留组、模式、5′ 关联、已知中心与 30′ 环境。低优先级组按预定哈希抽样，人工图像定级单列。
- 61469680 在系统统计结束后因 NumPy 标量写 YAML 失败。将 HEALPix 像素面积转换成 Python 标量后的 61469764 已通过。历史搜索结果和冻结阈值均保留。

## 第十三轮 · 2026-11-17

- 61464521、61465403 注册两批。61464563 的 43 个任务和 61465477 的 93 个任务全部完成，实际盲扫 1,077 个核心，1,636.598 有效 deg²。61465404、61465478 的 49 组、228 个 C 模式均完成。
- 7 个 South 和 3 个 North 背景取得实际 PS1 DR2，240 次三臂物理参数试验全部完成。61466782 汇总配对差异与固定阈值的留出成本，61467622 为复核后的同比例坐标图。
- 61465088–61465090 完成三个空白 CCD 对照。61465310 完成 18 个原生注入，61465459–61465461 完成分类、选星和盲扫。61465619 校验相同 CCD 集合，61465620 生成概率表和图。
- 61466534、61466649 完成主关注组独立 PS1 和 Gaia 前景消融，61466569 完成局部两尺度图，61466785 完成首批重点对象公开交叉识别。已知 Palomar 14 环境标注已纳入，L1 晋级数为零。
- 61467823 汇总跨区候选及背景。61468590 以精确 census 分区重采样累计足迹并审计残余面积，South PS1 资格代理覆盖约 94.6%。
- [第十三轮报告](../thirteenth_science_report.md) · [Slurm 记录](../results/v13/slurm_jobs.csv) · [候选与环境](../results/v13/discovery/candidate_context.csv)

## 第十二轮 · 2026-11-17

- 四区 78 场和 DES 修复作业 61462399 均已完成，新增 691.838 有效 deg²、268 个主档组。50 组共 273 个模式完成 C。61463931 发布 407 个历史与新核区的共同 ICRS 图册。
- 61461656、61461657、61464112 完成 Tan Table 8 原生双深度实测和绝对孔径分母核查。18 个共同背景/控制场取得完整 PS1 本身的 DR2 星表，61464109、61464111 完成六源的同成本最终比较。
- 61461687/89、61462654–61462656 完成旧峰回放与新留出检验。61461738/39 完成实际共加图像注入。
- 61462725–61462728、61462697/98、61463274/75/87/88 完成 170 个物理配对。61462894/95 完成 8 个变星族条件试验。61464044 完成 170 个位置的作者 DR1 模型。
- 新 South PS1 强峰的 61462491、61462755、61462985 独立 PS1、Gaia 和匹配对照均完成。61462707 测得新取得的独立 DECam g 在目标处零可用覆盖。候选保留 L0。
- [科学报告](../twelfth_science_report.md) · [Slurm 记录](../results/v12/slurm_jobs.csv) · [GitHub](https://github.com/xiaoyunao/legacy-satellite-search)

## 第十一轮 · 2026-11-17

- 61459465 完成 North 四个盲恢复控制，61459729 完成公共 PS1 校准，61459498 登记 56 个互斥新核心。61459554–61459560 完成实际扫描，有效面积 574.044 deg²。61459930、61459931、61459932、61459942 完成分区候选阈值和留出统计。
- 61459604 完成 DES 风格图与空白/深度对照。61459943 与 61460256 完成每区前两组的优先图，其中两条 DES 响应关联 Tucana V。61459712、61459805、61459831 依次完成 census 重叠、边缘代理复核和实际接缝掩膜检查。
- [第十一轮科学报告](../eleventh_science_report.md) · [Slurm 作业记录](../results/v11/slurm_jobs.csv)

## 第十轮 · 2026-11-17

- 61458390 完成四帧 CFHT r 宽切图定标和空孔径深度。61458992 核验 UNIONS 计划范围。补充公开档案无合格独立深 g 产品，WHIGS 实际访次待确认。已记录 CFHT 双色参数和 ETC，未提交观测申请。
- 61458572 与 61458618 完成 16 对远距紧致注入，位置检出为 7/12/11（LS 基线/加深/PS1 DR2）。61458979 完成五个次级组的 PS1 定点与盲峰复核，均为 L0。
- [第十轮报告](../tenth_science_report.md) · [Slurm 作业记录](../results/v10/slurm_jobs.csv) · [观测设计](survey63_observation.md)

## 第九轮 · 2026-11-17

- 61454095 完成双背景 32 组等成本物理配对试验。LS 基线、LS 加深、PS1 DR2 分别检出 20、24、19 组位置。61453177 完成同位置的作者发布 PS1 DR1 选择模型。初始独立试跑 61452683 在 NERSC 留档。
- 61453320、61453646、61454040、61454273、61454570 完成公开曝光去重、实际 CCD WCS 和点源深度。survey_63 只有部分独立 g 覆盖，正式核心可用 51.7%，实测去消光 5σ 深度约 22.94–23.00。保留 L0。HSCLA 需要认证，此次无法连接 Computer Use 浏览器。
- 61452821 完成 Euclid DR1 与剩余 PS1 代理面积的实际交集。27 个盲审面板完成分级与揭示，其中 24 个新低优先样本。原始独立影像保存在 Perlmutter scratch。
- [第九轮科学报告](../ninth_science_report.md) · [作业记录](../results/v9/slurm_jobs.csv)

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
