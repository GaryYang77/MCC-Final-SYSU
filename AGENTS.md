# MCC 2026 决赛优化约束

## 目标与环境

- 目标：在结果通过精度验证的前提下，缩短 ROMS-CoSiNE15 完整三天模拟的运行时间。公开基准 `01:50:06`。
- 决赛环境：华东一区（昆山），队列 `kshcexclu06`；最多 4 节点 × 32 核 = 128 CPU 核；不使用 DCU。
- 主办方决赛根目录 `/public/share/mcc2026_final/`；本仓库模型源码位于 `ROMS_CoSiNE15/`。

## 服务器访问

- 从 WSL 仓库环境连接登录节点：

  ```bash
  ssh -i ~/.ssh/fangxihong_key -p 65023 fangxihong@cancon.hpccube.com
  ```

- 工作区 `/public/home/fangxihong/MCC-Final-SYSU`。本地代码经 `Local_Lab/sync_to_cluster.sh` 同步；服务器的基线、runs、builds、日志不会被本地同步覆盖（已复测确认）。
- 默认只读探查；上传源码、修改远程文件、提交/取消作业、运行官方验证前，先确认当前实验目标和作业范围。
- 必须用 Slurm 向 `kshcexclu06` 申请计算节点；不要用登录节点的 `lscpu` 代替计算节点实测配置。

## 已确认状态（无需重复验证）

- 服务器原生基线已生成并封存于 `Local_Lab/baselines/mcc_4x20/`（job `118468694` COMPLETED）；独立全新构建验证通过（job `118469268`，13 变量 `RMSE==0`、`max_abs==0`，PASS）。
- **禁止重新运行 `baseline`**。日常候选默认执行 `build` 后直接进入 4n64
  profiling；`validate` 只在下文列出的风险条件或最终累计候选时运行。
  仅当基线缺失、源码树干净且团队明确要求时才可重建 baseline。
- score profiling 基线（`feat-improve-profiling`，2026-08-04）：wall-only、per-rank min/mean/max、调用次数、I/O/MPI 分类、region 39 与子阶段 51–56、JSON/CSV、HTML dashboard。该轻量模式用于日常候选的性能门禁。
- profiler-v2（commit `64cec19`，2026-08-08）已通过 Phase-D：score、summary、trace 三种用途分离；summary 可细分 contact/f2csum 的 plan-pack-MPI-unpack、tracer corrector 子阶段、broadcast 和 `put_refine3d`，并记录 rank/node；trace 可为选定 ranks 离线生成 Perfetto JSON。普通 score build 不含 `PROFILE_DIAGNOSTIC`，新增诊断不会进入最终 no-profile 二进制。详见 `Local_Lab/profiler-v2-design.md` 和 `Local_Lab/profiler-v2-phase-d.md`。
- 4 节点 128 ranks `8x16` 完整三天 profiling：job `118507345`，wall `9589 s`，官方 `vali.py` 已通过。注意：`9589 s` 与公开基准 `01:50:06` 不是同一边界/二进制，**不得直接算 speedup**；最终成绩以 no-profile 二进制对齐。
- 2 节点 64 ranks `8x8` 完整三天：job `118500776`，wall `10588 s`，输出与 4 节点逐位一致——仅用于 scaling 诊断。
- 1 节点 32 ranks `4x8` 在首次 nesting 通信处触发 `MPI_Bcast/MPI_ERR_TRUNCATE`：**该结果不得用于任何 scaling 结论，也不要默认其他 32-rank tile 形状可用**。
- **优化后 4 节点 64 ranks、每节点 16 核（16ppn）、`8x8` 完整三天**：job `118585284`，wall **`4657 s`（1.29h）**，官方 `vali.py` 已通过（全部 26 变量 `RMSE==0`、`max_abs==0`）。相比 4node-128rank（6452s）快 27.8%，相比 2node-64rank（6226s）快 25.2%——是当前最快配置，因此**日常 DEMO profiling 切换为此配置**。二进制 SHA-256 `bdcdfeafbd1f48c6c0725c3f336470a451d12a237ebab01ae2768c4c668da08d`，位于 `Local_Lab/runs/validation/candidate_20260804T143831Z_9553/bin/oceanM`。

### 优化前必读证据

- 仓库根目录 profile bundles（可直接载入 `Local_Lab/profile_dashboard.html`）：
  - 优化前完整三天 scaling：`profile_bundle.json`（4 节点 demo）、`2nodes-64ranks_profile_bundle.json`、`4nodes-128ranks_profile_bundle.json`
  - 优化后完整三天：`2nodes-64ranks_optimized_20260804T152030Z_profile_bundle.json`、`4nodes-128ranks_optimized_20260804T152030Z_profile_bundle.json`
  - **优化后 4nodes-64ranks-16ppn（当前最快）**：`4nodes-64ranks-16ppn_optimized_20260805T014345Z_profile_bundle.json`
  - profiler-v2 Phase-D：`profile_bundle_logs/profiler-v2-summary-final_20260808T111308Z_profile_bundle.json`、`profile_bundle_logs/profiler-v2-trace-final_20260808T111910Z_profile_bundle.json`
  - **当前 main score reference**：`profile_bundle_logs/cache-t3dmix4-coefficients-4n64-16ppn_20260808T211002Z_profile_bundle.json`
- 细节见 `Local_Lab/profiling-analysis.md`；服务器 profiling reference：`Local_Lab/runs/profile128/sections-overhead-a-on_20260803T110240Z_44162`。
- **必须先读 bundle 和分析文档再选热点，不得脱离证据凭直觉优化**；完整任务 bundle 只用于确认热点代表性，不替代日常 reference。
- 当前 profiler-v2 结论见 `Local_Lab/profiler-v2-current-analysis.md`：Grid-2 R35 以 horizontal tracer advection 为主，`put_refine3d` 是第二个明确计算热点；已细分 contact3d/f2csum 只覆盖 R49 的小部分，继续修改 R49 前应先补齐剩余 assemble 模式的诊断覆盖。

### 日常配置常量（下文统一引用，不再重复拼写）

- **DEMO**：4 节点、64 ranks、每节点 16 核（16ppn）、`8x8`、外层 60 步 / 内层 300 步 profiling。60/300 步与完整任务的热点排序和占比接近，可作日常筛选。此配置每节点仅 16 ranks，内存带宽充裕、节点内 MPI 争用低，比旧 2 节点 32ppn DEMO 反馈更快。
- **reference 规则**：每个新 accepted commit 的 score DEMO run 直接成为下一项实验的 `--reference-run`。当前 reference 为 `Local_Lab/runs/profile128/cache-t3dmix4-coefficients-4n64-16ppn_20260808T211002Z_63841`（job `118803141`，profile total `71.65s`，26 变量逐位一致；binary SHA-256 `31f788d8f30a95677b939ec4afaac4a1399a37b13c0c3ade5f6581a4977617dd`）。相对此前 `72.41s` reference，目标 R27 双网格下降 `14.65/19.63%`，total 下降约 `1.05%`；独立 1-rank validate job `118803276` 也以全部零误差通过。单次 total 受节点噪声影响；reference 的首要作用是输出基准和 region 对照，不把某一次 wall 当成无误差真值。旧的 2 节点、4 节点 128-rank 和早期 4n64 references 仅作历史对照。
- **当前 no-profile 阶段成绩**（commit `d68e187`）：同 allocation `off-on` 配对 job `118802758`，4n64/16ppn、8x8、60/300；no-profile `75.03s`，score PROFILE `72.44s`，两者均正常结束且 comparison 通过。no-profile binary SHA-256 `6a92f9cd82c97fb341108eb4cd83c0b65bdf99529ee1435fd0f220184dbfb40f`。本次表观 overhead `-3.45%` 是顺序/运行噪声，不能解释为 profiler 加速；阶段成绩以 `75.03s` no-profile 为准。此前 commit `07f8d83` 的配对 no-profile 为 `75.53s`。

### profiler-v2 三层用途

- **no-profile**：唯一的最终成绩口径。只用于阶段性累计候选、完整三天和最终验收，不作为每个小优化的日常门禁。
- **score PROFILE**：唯一的日常性能与正确性门禁。默认每个候选只跑一次 4n64 DEMO；不附带 summary/trace，不要求同次 no-profile 配对，也不因结果接近噪声自动追加作业。
- **diagnostic summary/trace**：只用于形成和解释性能假设，不用于判定候选 speedup。summary 回答子阶段、payload 和 rank/node 不平衡；只有怀疑调用时序、MPI 等待或跨节点差异时才运行 trace，默认每节点选一个 rank 并设置事件上限。

score PROFILE 的提升通常能预测 no-profile 的提升，但不是逻辑保证：插桩可能改变编译布局、cache 和 MPI 时序。因此，日常可用“数值门禁通过 + score total/目标 region 方向有效”接受候选；只有阶段性累计候选和最终提交才用同源码 no-profile 确认真实成绩。不得把 diagnostic wall 与 score reference 直接比较来接受模型优化。

## 修改边界

**禁止：**

- 物理计算方案、模型方程及其科学含义；主办方提供的初始场、边界场、强迫场和输入数据。
- 为提速跳过必需计算、缩短最终模拟时长、放宽/绕过验证。
- 在模型性能实验分支修改 profiler、region 定义、计时开关、验证器或 comparison 逻辑；profiler 本身的改版必须使用独立分支和独立开销/一致性验收，不能与模型优化混合。
- 修改 `Local_Lab/baselines/mcc_4x20/outputs_valid/` 及其 `manifest.json`；日常运行 `baseline`。
- 用提高容差、减少变量、修改输入、重建基线、跳过计算来挽救失败候选。

**允许：**

- 不改变物理方案的等价实现优化（消除可证明的冗余、改善循环/内存访问、减少临时量与数据复制）。
- MPI 分块、通信、缓存、同步、聚合、负载均衡优化。
- 编译与运行配置优化（每种配置单独验证，不得依赖比赛禁用硬件）。
- 调试时临时缩短 `NTIMES`，但缩短配置不得作为最终结果。

边界不确定时停止修改并向团队确认。ROMS 上游 tickets 只作实现参考，不能因"官方已有"默认正确。

## 每次优化的固定流程

一个分支只处理一个主要性能假设；不得把算法改写、编译 flags、MPI 分块等多个变量混在同一次实验。

1. **开分支**：从干净 `main` 创建 `perf/<single-hypothesis>`，记录 `accepted_commit=$(git rev-parse HEAD)` 的完整 SHA 到实验记录（不要只依赖 shell 变量）。`git status --short` 必须为空；确认 `main` 已含 `Local_Lab/profile_128.py`、`Local_Lab/profile_diagnostics.py` 和 `Local_Lab/profile_dashboard.html`，否则停止。先从 bundle 写下可证伪假设：目标 region、预期变化、不应变化的数值行为；区分计算 / MPI 通信等待 / I/O。
2. **改代码**：一次一个可解释的等价实现优化，保留可审查 diff；日常 DEMO 完成前不 commit。
3. **本地快测**（WSL 仓库根目录）：`python -m pytest -q Local_Lab/tests`。该测试通常只需数秒，继续保留以避免把接口、脚本和预处理错误带到集群。缺依赖时用专用环境装 `Local_Lab/requirements-validation.txt`，不得改测试规避环境问题。
4. **干净构建 PROFILE 候选**：同步后只编译，不运行慢速 1-rank 模型——

   ```bash
   bash Local_Lab/sync_to_cluster.sh
   ssh -i ~/.ssh/fangxihong_key -p 65023 fangxihong@cancon.hpccube.com
   cd /public/home/fangxihong/MCC-Final-SYSU
   bash Local_Lab/run_cluster_gate.sh build
   ```

   包装脚本会等待 Slurm 作业并把 stdout/stderr 打到终端；自动化调用必须检查退出码。只有退出码 0、终端显示 `[build] PASS`、`build_report.json` 的 `passed=true` 三者同时满足才可运行模型。不得在登录节点编译或运行模型。
5. **唯一日常运行门禁：一次 4n64 score profiling DEMO**。candidate 目录必须取自本次 build 输出，不能用 `ls | head` 猜。普通候选不额外跑 no-profile、summary/trace 或 1-rank；运行前验证构建报告、二进制并记录 SHA-256：

   ```bash
   candidate_dir=Local_Lab/runs/validation/candidate_<exact-timestamp>
   python -c 'import json,sys; assert json.load(open(sys.argv[1]))["passed"] is True' \
     "$candidate_dir/build_report.json"
   test -x "$candidate_dir/bin/oceanM" && sha256sum "$candidate_dir/bin/oceanM"

   source /public/share/mcc2026_final/miniforge3/etc/profile.d/conda.sh
   conda activate vali
   python Local_Lab/profile_128.py \
     --binary "$candidate_dir/bin/oceanM" \
     --label <hypothesis>-4n64-16ppn \
     --outer-steps 60 --inner-steps 300 \
     --nodes 4 --ranks 64 --tiles-i 8 --tiles-j 8 \
     --reference-run Local_Lab/runs/profile128/<accepted-4n64-16ppn-reference-run>
   ```

   该单次 DEMO 同时承担并行正确性与日常性能门禁。判据：`run_report.json` 满足 `passed=true`、`normal_end=true`、`outputs.passed=true`、`comparison.passed=true`，26 个变量均检查 shape、mask、NaN/Inf、`RMSE <= 1e-5`、`max_abs <= 1e-5`，且存在 `profile_report.json`。性能判断同时看 total wall、目标 region wall/调用次数、rank imbalance 和非目标热点（inclusive region 不得相加成 100%）：目标 region 应按假设改善、调用次数符合设计，稳定计算 region 不得出现足以抵消收益的退化；通常 total 也应改善。如果 total 与目标 region 矛盾，但差额可由 R03 输入分发、R44 broadcast 等已知易受 filesystem/到达时序影响的 region 完整解释，则记录不确定性并由团队直接决定接受、拒绝或复测，默认不自动追加作业。score 是日常筛选依据而非 no-profile 成绩证明。
6. **触发式 1-rank validate**：普通、逐位一致的候选不再运行。出现以下任一情况时，commit 前仍须运行 `bash Local_Lab/run_cluster_gate.sh validate`，并满足退出码 0、`[validate] PASS`、`validation_report.json passed=true`：
   - DEMO 任一变量出现非零误差，即使仍在 `1e-5` 容限内；
   - 修改数值精度、浮点运算顺序、mask/边界索引、CPP 分支或非 DISTRIBUTE fallback；
   - reference 链不可信、输出元数据异常，或团队明确要求独立复核；
   - 进入完整三天测试的最终累计候选。
7. **失败恢复**：任一适用门禁失败不得 commit。保留失败 run 路径与报告后恢复：

   ```bash
   git restore --source="$accepted_commit" -- <本次修改的明确文件列表>
   python -m pytest -q Local_Lab/tests
   ```

   `git restore` 不处理新增未跟踪文件：用 `git status --short` 对照实验开始时的文件清单，逐个移到 `/tmp/<experiment>-failed/` 留档。**禁止 `git clean`、禁止 `git reset --hard`**；确认工作树无他人修改才可恢复；commit 后才发现问题用 `git revert <bad-commit>`。恢复后确认 diff 与新增文件已清除，重新同步并让适用门禁 PASS，才能开始下一设计。结果接近噪声由团队决定是否复测，默认不加作业。
8. **commit**：4n64 DEMO 及任何触发的 validate 通过且性能方向有效后，运行 `git diff --check`、审查 diff，用明确文件列表 `git add`（禁止 `git add .`）。该 commit 成为新 accepted commit，本次 profiling run 成为下一实验的 reference。MPI/分块/通信/同步类改动，commit 前额外检查正常结束、输出齐全、NaN/Inf、26 变量 comparison、rank 离散。
9. **完整三天与官方验证不是普通 commit 的门禁**：只有团队选出的最终累计候选才运行（见下节），至少一个候选必须完成，时间允许再重复测量。

### profiler-v2 按需诊断流程

只有 score 的宽 region 无法回答下一步优化问题时才构建 diagnostic binary；该流程用于诊断，不替代上面的 score 门禁：

```bash
bash Local_Lab/run_build_diagnostic.sh
diagnostic_binary=Local_Lab/builds/profiling/diagnostic_<exact-build>/bin/oceanM
test -x "$diagnostic_binary" && sha256sum "$diagnostic_binary"

# 默认先跑 summary；仍使用相同 4n64、60/300 配置。
python Local_Lab/profile_128.py \
  --binary "$diagnostic_binary" \
  --label <hypothesis>-diagnostic-summary \
  --outer-steps 60 --inner-steps 300 \
  --nodes 4 --ranks 64 --tiles-i 8 --tiles-j 8 \
  --diagnostic-mode summary \
  --reference-run Local_Lab/runs/profile128/<accepted-score-run>

# 仅当 summary 指向时序/等待问题时使用；先每节点一个 rank。
python Local_Lab/profile_128.py \
  --binary "$diagnostic_binary" \
  --label <hypothesis>-diagnostic-trace \
  --outer-steps 60 --inner-steps 300 \
  --nodes 4 --ranks 64 --tiles-i 8 --tiles-j 8 \
  --diagnostic-mode trace --trace-ranks 0,16,32,48 \
  --trace-max-events 150000 \
  --reference-run Local_Lab/runs/profile128/<accepted-score-run>
```

summary/trace 必须满足正常结束、26 变量 comparison 通过、`diagnostics_validation.passed=true`、真实 node/local-rank 元数据完整、父子 region 一致性通过；trace 还必须 `events_dropped=0` 且 artifact 不超过 256 MiB。诊断开销只记录为 observer effect，不设低开销硬门槛。只有修改 profiler 本身并准备固定新版时，才需要用 `profile_overhead.py` 做 score/no-profile 或 diagnostic/no-profile 配对开销验收；普通模型优化不跑这类配对。

### 触发式 1-rank 正确性门禁判定标准

`valid_test.py` 在计算节点用官方 Intel 2017.5.239、HPC-X 2.7.4、NetCDF 4.4.1 干净编译，1 rank 跑固定 `4/20` 步双向嵌套样例，比较 `SCS_avg_0001.nc`、`Dongsha60_avg_0001.nc` 中 13 个变量（`temp salt u v zeta NO3 NH4 PO4 diatom microzooplankton detritus oxygen TIC`）：每变量 `RMSE <= 1e-5` 且 `max_abs <= 1e-5`，并检查文件、维度、shape、缺失值掩膜、NaN/Inf。使用服务器封存基线，不替代主办方完整三天 `vali.py`。

### 日常门禁管线速查

`sync_to_cluster.sh`（WSL 同步，排除输入大文件与远端基线/runs/builds/日志）→ `finalize_cluster_sync.sh`（检查输入、建 `Inputfiles` 软链、存源码快照）→ `run_cluster_gate.sh build`（提交并等待 Slurm，透传退出码）→ `cluster_gate.sbatch`（队列/官方环境）→ `valid_test.py build`（干净编译、SHA-256、报告）→ `profile_128.py`（4n64 并行运行、数值 comparison、profiling 报告）。触发风险条件时，在 commit 前额外执行 `run_cluster_gate.sh validate`。

故障定位：同步/输入链接失败看同步脚本输出；编译看 `build.log` 和 `build_report.json`；MPI/运行异常看 `model.log` 和 Slurm stderr；数值失败看 profiling run 的 `run_report.json`，触发式 1-rank 门禁失败再看 `validation_report.json`；资源看 `resource.log`；diagnostic 看 `profile_diagnostics.json`、`diagnostics_validation` 和各 rank 的 `profile_diag_rank_*.log`，trace 再看 `profile_trace.perfetto.json`。构建产物目录 `Local_Lab/runs/validation/candidate_*/`，DEMO 产物目录 `Local_Lab/runs/profile128/<label>_*/`。

## 决赛运行与最终验收

- 配置文件 `ROMS_CoSiNE15/ROMS/External/ocean_SCS_Dongsha60_bio15.in`。`NTIMES` 第一个数对应外层 `SCS`，第二个对应内层 `Dongsha60`：完整三天 `2592  12960`；一天 `864  4320`；半天 `432  2160`。缩短时两网格同比例调整；最终提交前恢复完整三天并复查实际输入文件。
- 以根目录 `sub.sh` 为提交脚本起点，队列 `kshcexclu06`、4 节点 128 核。调整 rank 或 `NtileI/NtileJ` 前先理解嵌套网格进程分配并用缩时任务实测；不要假设单网格 tile 数等于总核数。
- `start_full_profile_scaling_sweep.sh` 是 scaling 诊断工具（含已知失败的 1 节点 case），**不是候选入口**；正式候选只跑 4 节点 128 ranks。
- 最终成绩用相同源码的 **no-profile 二进制**计时。流程（每条命令只提交一个 4 节点 case，不触发 sweep）：

  ```bash
  bash Local_Lab/run_build_no_profile.sh
  no_profile_binary=Local_Lab/builds/profiling/<exact-build>/bin/oceanM
  test -x "$no_profile_binary" && sha256sum "$no_profile_binary"

  # 60/300 步同 allocation 配对，确认 profile/no-profile 输出 comparison 通过
  python Local_Lab/profile_overhead.py \
    --profile-binary Local_Lab/runs/validation/<accepted-candidate>/bin/oceanM \
    --control-binary "$no_profile_binary" \
    --label final-no-profile-check --order off-on \
    --outer-steps 60 --inner-steps 300 --tiles-i 8 --tiles-j 16

  python Local_Lab/profile_128.py \
    --binary "$no_profile_binary" \
    --label final-4node-full \
    --outer-steps 2592 --inner-steps 12960 \
    --nodes 4 --ranks 128 --tiles-i 8 --tiles-j 16 \
    --time-limit 12:00:00 --preserve-output-cadence --no-expect-profile \
    --reference-run Local_Lab/runs/profile128/full-3day-scaling-4nodes-128ranks_20260803T172422Z_17347
  ```

  记录命令打印的 exact `run_dir`（`full_run` 必须指向它，不能用通配符猜）。每次 `run_report.json` 必须 `passed=true`、`normal_end=true`、`comparison.passed=true`。至少完成一次；机时允许可在独立 allocation 重复并报告中位数。

- 官方 `vali.py` 无命令行参数，`dir_test` 是占位路径；**不得修改 `/public/share/.../vali.py` 本体**。复制到 run 目录只替换一行，并用 `diff` 确认仅此处变化（`diff` 必须返回 1；返回 0 表示未替换，大于 1 表示命令错误，均停止）：

  ```bash
  source /public/share/mcc2026_final/miniforge3/etc/profile.d/conda.sh
  conda activate vali
  full_run=/public/home/fangxihong/MCC-Final-SYSU/Local_Lab/runs/profile128/<full-run>
  test "$(grep -c '^dir_test = ' /public/share/mcc2026_final/vali.py)" -eq 1
  cp /public/share/mcc2026_final/vali.py "$full_run/vali_official.py"
  sed -i "s|^dir_test = .*|dir_test = '$full_run/output/'|" "$full_run/vali_official.py"
  set +e; diff -u /public/share/mcc2026_final/vali.py "$full_run/vali_official.py"; vali_diff_status=$?; set -e
  test "$vali_diff_status" -eq 1
  set -o pipefail
  python "$full_run/vali_official.py" 2>&1 | tee "$full_run/vali_official.log"
  ```

  该脚本数值失败时不保证非零退出码，必须检查所有 RMSE 行和最终文本 `最终判定：两组文件所有变量RMSE均在阈值范围内，优化结果无异常`。

- 只有"完整任务正常结束 + 官方 `vali.py` 通过"才可作为最终成绩。实验记录至少包含：commit/diff、编译器与 flags、节点/rank/分块、输入时长、wall time、重复次数、本地验证报告、官方验证结果。
