# MCC 2026 决赛优化约束

## 目标与环境

- 目标：在结果通过精度验证的前提下，缩短 ROMS-CoSiNE15 完整三天模拟的运行时间。公开基准 `01:50:06`。
- 决赛环境：华东一区（昆山），队列 `kshcexclu06`；最多 4 节点 × 32 核 = 128 CPU 核；不使用 DCU。
- 主办方决赛根目录 `/public/share/mcc2026_final/`；本仓库模型源码位于 `ROMS_CoSiNE15/`。

## 当前阶段：Phase 6 计算 kernel 优化

- 开始任何新实验前，必须完整阅读 `Local_Lab/phase6-kernel-optimization-plan.md`。
  该文档是专家建议、ROMS 数值结构、profiler 缺口、正确性双通道和热点路线的长期
  记忆；对话压缩或交接后不得仅凭聊天摘要继续工作。
- Phase 6 从“以通信/嵌套为主”转向“以 ROMS 计算 kernel 为主”，但仍按实测热点
  排序，不为展示特色而修改非热点。一个阶段只细化当前第一热点，一个实验只优化一个
  可证伪假设，完成后重新 profiling 再决定下一项。
- 当前第一计算目标是 Grid-2 R35 `step3d_t/tracer_corrector` 中的 horizontal
  tracer advection；随后按新证据考虑 R22 `pre_step3d`、R09 `step2d`、R34
  `step3d_uv`、R19 GLS 和 halo pack/wait/unpack。

## 服务器访问

- 从 WSL 仓库环境连接登录节点：

  ```bash
  ssh -i ~/.ssh/fangxihong_key -p 65023 fangxihong@cancon.hpccube.com
  ```

- 工作区 `/public/home/fangxihong/MCC-Final-SYSU`。本地代码经 `Local_Lab/sync_to_cluster.sh` 同步；服务器的基线、runs、builds、日志不会被本地同步覆盖（已复测确认）。
- 默认只读探查；上传源码、修改远程文件、提交/取消作业、运行官方验证前，先确认当前实验目标和作业范围。
- 必须用 Slurm 向 `kshcexclu06` 申请计算节点；不要用登录节点的 `lscpu` 代替计算节点实测配置。

## 已确认状态（无需重复验证）

- **Phase 5 当前最佳完整结果**：仓库 HEAD `55b7a9097e2877df670a0ad20cfecdf05d71e7af`，
  累计模型源码锚点 `1ba85ab2149598702c6011e12940612a0a21119c`；4 节点、96 ranks、
  24 ranks/node、`6x16`、L3-balanced NUMA-row binding，完整 `2592/12960` 步。
  job `118852631` 的 no-profile wall 为 **`2205.57 s`（36:45.57）**，26 项内部
  comparison 均为零且官方 `vali.py` PASS。二进制 SHA-256 为
  `1152299ea019b653a4007bca10490c01bb9c0ce8af90c87835eec0167a11a410`。证据见
  `Local_Lab/experiments/assemblef1d-full-validation.md`。团队审核 Phase 6 文档后再创建
  `mcc-phase5-validated-2205s` tag；在此之前不得假定该 tag 已存在。

- 服务器原生基线已生成并封存于 `Local_Lab/baselines/mcc_4x20/`（job `118468694` COMPLETED）；独立全新构建验证通过（job `118469268`，13 变量 `RMSE==0`、`max_abs==0`，PASS）。
- **禁止重新运行 `baseline`**。日常候选默认执行 `build` 后直接进入 4n64
  profiling；`validate` 只在下文列出的风险条件或最终累计候选时运行。
  仅当基线缺失、源码树干净且团队明确要求时才可重建 baseline。
- score profiling 基线（`feat-improve-profiling`，2026-08-04）：wall-only、per-rank min/mean/max、调用次数、I/O/MPI 分类、region 39 与子阶段 51–56、JSON/CSV、HTML dashboard。该轻量模式用于日常候选的性能门禁。
- profiler-v2（commit `64cec19`，2026-08-08）已通过 Phase-D：score、summary、trace 三种用途分离；summary 可细分 contact/f2csum 的 plan-pack-MPI-unpack、tracer corrector 五个子阶段、broadcast 和 `put_refine3d`，并记录 rank/node；trace 可为选定 ranks 离线生成 Perfetto JSON。普通 score build 不含 `PROFILE_DIAGNOSTIC`，新增诊断不会进入最终 no-profile 二进制。当前只有 R35 达到子阶段粒度，R22/R09/R34 仍是宽 region；halo2d/3d/4d 的 pack/wait/unpack 名称已注册但源码尚未打桩，不得误称已有分解结果。详见 `Local_Lab/profiler-v2-design.md`、`Local_Lab/profiler-v2-phase-d.md` 和 Phase 6 计划。
- 4 节点 128 ranks `8x16` 完整三天 profiling：job `118507345`，wall `9589 s`，官方 `vali.py` 已通过。注意：`9589 s` 与公开基准 `01:50:06` 不是同一边界/二进制，**不得直接算 speedup**；最终成绩以 no-profile 二进制对齐。
- 2 节点 64 ranks `8x8` 完整三天：job `118500776`，wall `10588 s`，输出与 4 节点逐位一致——仅用于 scaling 诊断。
- 1 节点 32 ranks `4x8` 在首次 nesting 通信处触发 `MPI_Bcast/MPI_ERR_TRUNCATE`：**该结果不得用于任何 scaling 结论，也不要默认其他 32-rank tile 形状可用**。
- **历史 4 节点 64 ranks、每节点 16 核（16ppn）、`8x8` 完整三天**：job `118585284`，wall `4657 s`，官方 `vali.py` 已通过且全部 comparison 为零。该配置仍用于低延迟日常 score DEMO，但不再是最快完整配置，也不代表最终生产绑定。

### 优化前必读证据

- **Phase 6 必读**：`Local_Lab/phase6-kernel-optimization-plan.md`；当前完整最佳证据：
  `Local_Lab/experiments/assemblef1d-full-validation.md`。

- 仓库根目录 profile bundles（可直接载入 `Local_Lab/profile_dashboard.html`）：
  - 优化前完整三天 scaling：`profile_bundle.json`（4 节点 demo）、`2nodes-64ranks_profile_bundle.json`、`4nodes-128ranks_profile_bundle.json`
  - 优化后完整三天：`2nodes-64ranks_optimized_20260804T152030Z_profile_bundle.json`、`4nodes-128ranks_optimized_20260804T152030Z_profile_bundle.json`
  - 历史 4nodes-64ranks-16ppn 完整热点：`4nodes-64ranks-16ppn_optimized_20260805T014345Z_profile_bundle.json`
  - profiler-v2 Phase-D：`profile_bundle_logs/profiler-v2-summary-final_20260808T111308Z_profile_bundle.json`、`profile_bundle_logs/profiler-v2-trace-final_20260808T111910Z_profile_bundle.json`
  - Phase 4 score reference bundle：`profile_bundle_logs/phase-current-paired-on_20260809T052757Z_profile_bundle.json`；Phase 6 当前筛选 reference 以本文“日常配置常量”记录的 exact run 目录为准
- 细节见 `Local_Lab/profiling-analysis.md`；服务器 profiling reference：`Local_Lab/runs/profile128/sections-overhead-a-on_20260803T110240Z_44162`。
- **必须先读 bundle 和分析文档再选热点，不得脱离证据凭直觉优化**；完整任务 bundle 只用于确认热点代表性，不替代日常 reference。
- 当前 profiler-v2 结论见 `Local_Lab/profiler-v2-current-analysis.md`：Grid-2 R35 以 horizontal tracer advection 为主，`put_refine3d` 是第二个明确计算热点；已细分 contact3d/f2csum 只覆盖 R49 的小部分，继续修改 R49 前应先补齐剩余 assemble 模式的诊断覆盖。

### 日常配置常量（下文统一引用，不再重复拼写）

- **发现/日常筛选 DEMO**：4 节点、64 ranks、每节点 16 核（16ppn）、`8x8`、外层
  60 步 / 内层 300 步 score profiling。它反馈快，历史上与完整任务热点排序接近，
  但 tile 长度、内存带宽和 MPI 拓扑不同于最终配置，只能作为候选筛选与因果归因，
  不能单独证明生产收益。
- **生产配置**：4 节点、96 ranks、每节点 24 ranks、`6x16`、L3-balanced NUMA-row
  binding。每个 kernel 阶段的累计候选、所有配置/亲和性候选以及最终完整任务必须在
  该配置确认；同 allocation 先跑 60/300 预检，超过当前慢节点阈值则安全退出。
- **reference 规则**：每个 exact-equivalence 新 accepted commit 的 4n64 score DEMO
  直接成为下一项实验的筛选 reference。当前模型的 4n64 score reference 是
  `Local_Lab/runs/profile128/assemblef1d-in-place-4n64-16ppn_20260809T223055Z_41712`
  （commit `1ba85ab`，job `118852220`，26 项 comparison 全零）。生产 reference 是
  job `118852631` 的完整 4n96/`6x16` run。reference 首要用于输出和 region 对照，
  不把一次 wall 当成无误差真值。
- **当前成绩口径**：唯一权威成绩是同源码 no-profile 完整 4n96/`6x16` 的
  `2205.57 s`。旧 4n64 DEMO 的 `69--72 s` 只作历史筛选证据，不再称为当前成绩。
- **4n96 节点差异证据**（jobs `118825725/118825726`）：同工具链重新构建历史最佳 `0458b06` 与当前 `e7e0ce1`，在两个 allocation 内按 ABBA/BAAB 各跑两次。`j04r2n[16-19]` 上旧/新均值为 `68.38/67.74s`；`j04r2n[12-15]` 上同一对二进制变为 `121.29/122.97s`。八次均正常结束且 26 变量 comparison PASS。节点组对两个版本同时造成 `77-82%` 惩罚，不能把单次 90-120s 归因于源码。4n96 完整任务必须在同一 allocation 内先跑 DEMO 预检，慢节点自动退出。证据：`profile_bundle_logs/evidence_0458b06_vs_e7e0ce1_4n96.json`。

### profiler-v2 三层用途

- **no-profile**：唯一的最终成绩口径。只用于阶段性累计候选、完整三天和最终验收，不作为每个小优化的日常门禁。
- **score PROFILE**：唯一的日常性能与正确性门禁。默认每个候选只跑一次 4n64 DEMO；不附带 summary/trace，不要求同次 no-profile 配对，也不因结果接近噪声自动追加作业。
- **diagnostic summary/trace**：只用于形成和解释性能假设，不用于判定候选 speedup。summary 回答子阶段、payload 和 rank/node 不平衡；只有怀疑调用时序、MPI 等待或跨节点差异时才运行 trace，默认每节点选一个 rank 并设置事件上限。

score PROFILE 的提升通常能预测 no-profile 的提升，但不是逻辑保证：插桩可能改变编译布局、cache 和 MPI 时序。因此，日常可用“数值门禁通过 + score total/目标 region 方向有效”接受候选；只有阶段性累计候选和最终提交才用同源码 no-profile 确认真实成绩。不得把 diagnostic wall 与 score reference 直接比较来接受模型优化。

### 数值正确性双通道

- **Exact-equivalence（当前已启用）**：候选输出逐位一致，仍是缓存、不变量外提、
  冗余加载/复制消除等优化的首选证明，但“逐位一致”是优先目标而不是所有候选永久
  唯一准入标准。
- **Numerically-equivalent（显式启用）**：允许由浮点结合顺序、SIMD/FMA、倒数
  复用或 reduction 顺序造成非零差异。必须保持文件、变量、维度、shape、mask、
  NaN/Inf 和输出时刻正确，并按官方 `vali.py` 的 SCS/Dongsha、逐变量 RMSE 阈值
  判定；同时报告 max_abs、RMSE/阈值比和精度余量。官方阈值是合格边界，不是应主动
  消耗的误差预算，接近阈值的候选必须由团队明确决定。
- 内部 comparison 已提供显式 `--comparison-mode exact|numerical`：默认始终是
  `exact`，numerical 必须由实验假设主动声明。其阈值表由单元测试直接解析仓库官方
  `vali.py` 并逐项校验；任何阈值变化都会使测试失败，必须作为独立 infra 变更审核。
  `valid_test.py validate --comparison-mode numerical` 和 `profile_128.py
  --comparison-mode numerical` 是唯一允许的内部 numerical 入口，不得临时改常量。
- numerical 候选不得连续叠加未经全量验证的误差。在合入 accepted `main` 前，必须
  使用同源码 no-profile 二进制完成 4n96/`6x16` 三天全量并通过官方 `vali.py`。
  不得修改官方验证脚本本体、阈值、变量集合、参考数据或 comparison 逻辑。

## 修改边界

**禁止：**

- 物理计算方案、模型方程及其科学含义；主办方提供的初始场、边界场、强迫场和输入数据。
- 更换当前 split-explicit、Leap-Frog/Adams-Moulton、Adams-Bashforth、
  Crank-Nicolson/垂向隐式求解或 `TS_U3ADV_SPLIT` 输运方案；改变 stencil 阶数、
  系数、时间步长或求解含义。只能优化这些固定方案的等价实现。
- 为提速跳过必需计算、缩短最终模拟时长、放宽/绕过验证。
- 在模型性能实验分支修改 profiler、region 定义、计时开关、验证器或 comparison 逻辑；profiler 本身的改版必须使用独立分支和独立开销/一致性验收，不能与模型优化混合。
- 修改 `Local_Lab/baselines/mcc_4x20/outputs_valid/` 及其 `manifest.json`；日常运行 `baseline`。
- 用提高容差、减少变量、修改输入、重建基线、跳过计算来挽救失败候选。

**允许：**

- 不改变物理方案的等价实现优化（消除可证明的冗余、改善循环/内存访问、减少临时量与数据复制）。
- 在数值正确性通道允许的范围内，优化 kernel 的循环融合/拆分、SIMD 友好布局、
  不变量与除法/幂/metric 缓存、stencil 数据复用、三对角系数复用；必须用 ifort
  vectorization report 和目标 region 实测，不能把“源代码运算更少”直接当成更快。
- MPI 分块、通信、缓存、同步、聚合、负载均衡优化。
- 编译与运行配置优化（每种配置单独验证，不得依赖比赛禁用硬件）。
- 调试时临时缩短 `NTIMES`，但缩短配置不得作为最终结果。

边界不确定时停止修改并向团队确认。ROMS 上游 tickets 只作实现参考，不能因"官方已有"默认正确。

## 每次优化的固定流程

一个分支只处理一个主要性能假设；不得把算法改写、编译 flags、MPI 分块等多个变量混在同一次实验。

1. **开分支**：从干净 `main` 创建 `perf/<single-hypothesis>`，记录 `accepted_commit=$(git rev-parse HEAD)` 的完整 SHA 到实验记录（不要只依赖 shell 变量）。`git status --short` 必须为空；确认 `main` 已含 `Local_Lab/profile_128.py`、`Local_Lab/profile_diagnostics.py` 和 `Local_Lab/profile_dashboard.html`，否则停止。先读 Phase 6 计划和最新 bundle，写下可证伪假设：目标 region/子阶段、预期变化、不应变化的数值行为；区分计算、MPI 通信等待和 I/O。计算候选还必须记录最热 loop nest、连续访问维度、ifort 向量化状态、拟消除的重复计算，以及对寄存器压力和浮点顺序的影响。
2. **改代码**：一次一个可解释的等价实现优化，保留可审查 diff，并在实验记录标明预期走 exact 还是 numerical 通道；日常 DEMO 完成前不 commit。未显式声明时一律走 exact，不能在看到误差后再把失败候选改称 numerical。
3. **本地快测**（WSL 仓库根目录）：`python -m pytest -q Local_Lab/tests`。该测试通常只需数秒，继续保留以避免把接口、脚本和预处理错误带到集群。缺依赖时用专用环境装 `Local_Lab/requirements-validation.txt`，不得改测试规避环境问题。
4. **干净构建 PROFILE 候选**：同步后只编译，不运行慢速 1-rank 模型——

   ```bash
   bash Local_Lab/sync_to_cluster.sh
   ssh -i ~/.ssh/fangxihong_key -p 65023 fangxihong@cancon.hpccube.com
   cd /public/home/fangxihong/MCC-Final-SYSU
   bash Local_Lab/run_cluster_gate.sh build
   ```

   包装脚本会等待 Slurm 作业并把 stdout/stderr 打到终端；自动化调用必须检查退出码。只有退出码 0、终端显示 `[build] PASS`、`build_report.json` 的 `passed=true` 三者同时满足才可运行模型。不得在登录节点编译或运行模型。
5. **唯一日常筛选门禁：一次 4n64 score profiling DEMO**。candidate 目录必须取自本次 build 输出，不能用 `ls | head` 猜。普通候选不额外跑 no-profile、summary/trace 或 1-rank；运行前验证构建报告、二进制并记录 SHA-256：

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

   该单次 DEMO 同时承担并行正确性与日常性能筛选。当前 exact 通道判据：`run_report.json` 满足 `passed=true`、`normal_end=true`、`outputs.passed=true`、`comparison.passed=true`，26 个变量均检查 shape、mask、NaN/Inf、`RMSE <= 1e-5`、`max_abs <= 1e-5`，且存在 `profile_report.json`。性能判断同时看 total wall、目标 region/子阶段 wall、调用次数、rank imbalance、ifort 向量化证据和非目标热点（inclusive region 不得相加成 100%）：目标 region 应按假设改善、调用次数符合设计，稳定计算 region 不得出现足以抵消收益的退化；通常 total 也应改善。如果 total 与目标 region 矛盾，但差额可由 R03 输入分发、R44 broadcast 等已知易受 filesystem/到达时序影响的 region 完整解释，则记录不确定性并由团队直接决定接受、拒绝或复测，默认不自动追加作业。4n64 score 是筛选和因果归因依据，不是 4n96 生产收益或 no-profile 成绩证明。
6. **触发式 1-rank validate 与 numerical 加强门禁**：普通、逐位一致的 exact 候选不再运行。出现以下任一情况时，commit 前仍须运行 `bash Local_Lab/run_cluster_gate.sh validate`，并满足退出码 0、`[validate] PASS`、`validation_report.json passed=true`：
   - DEMO 任一变量出现非零误差，即使仍在 `1e-5` 容限内；
   - 修改数值精度、浮点运算顺序、mask/边界索引、CPP 分支或非 DISTRIBUTE fallback；
   - reference 链不可信、输出元数据异常，或团队明确要求独立复核；
   - 进入完整三天测试的最终累计候选。
   official-tolerance 工具验收并启用后，任何 nonzero numerical 候选都必须运行该独立
   validate；若其目标 region 没有明确收益则直接拒绝，不得用官方较宽阈值挽救无性能
   价值的改写。通过短门禁只允许进入完整候选测试，不等于可合入 accepted `main`。
7. **失败恢复**：任一适用门禁失败不得 commit。保留失败 run 路径与报告后恢复：

   ```bash
   git restore --source="$accepted_commit" -- <本次修改的明确文件列表>
   python -m pytest -q Local_Lab/tests
   ```

   `git restore` 不处理新增未跟踪文件：用 `git status --short` 对照实验开始时的文件清单，逐个移到 `/tmp/<experiment>-failed/` 留档。**禁止 `git clean`、禁止 `git reset --hard`**；确认工作树无他人修改才可恢复；commit 后才发现问题用 `git revert <bad-commit>`。恢复后确认 diff 与新增文件已清除，重新同步并让适用门禁 PASS，才能开始下一设计。结果接近噪声由团队决定是否复测，默认不加作业。
8. **commit**：exact 候选在 4n64 DEMO 及任何触发的 validate 通过且性能方向有效后，运行 `git diff --check`、审查 diff，用明确文件列表 `git add`（禁止 `git add .`）。该 commit 成为新的筛选 reference；kernel 阶段累计候选只有达到下一条的 5% 触发阈值，才用同源码 4n96/`6x16` 生产配置确认累计收益。MPI/分块/通信/同步类改动，commit 前额外检查正常结束、输出齐全、NaN/Inf、26 项 comparison、rank 离散。numerical 候选在完整三天和官方验证通过前不得合入 accepted `main`，可保留在实验分支形成待验收 commit。
9. **完整三天与官方验证的触发条件**：除团队已经启动且接近完成的任务外，后续候选只有在同配置、可比的 DEMO 中，相对 accepted reference 的可信总时间至少下降 **5%**，才允许运行完整三天。低于 5% 的候选只做 DEMO 和触发式 validate，不消耗完整任务机时；numerical 候选可保留在实验分支，但在满足该触发阈值并通过完整三天与官方验证前不得合入 accepted `main`。5% 必须排除 R03 输入分发、R44 broadcast、文件系统抖动、慢节点和异常 MPI 环境等非源码收益，不能用目标 region 的局部降幅替代总时间降幅。达到 5% 只是允许启动完整任务的必要条件，不替代同源码 no-profile、4n96/`6x16`/L3-balanced 和官方 `vali.py` 门禁，也不得用 diagnostic wall 作为触发依据。

### profiler-v2 按需诊断流程

只有 score 的宽 region 无法回答下一步优化问题时才构建 diagnostic binary；该流程用于诊断，不替代上面的 score 门禁：

Phase 6 采用逐热点扩展：一次 profiler 分支只细化当前第一热点，计时点放在阶段或
loop nest 边界，不进入最内层网格点循环。第一轮只继续拆分 R35 horizontal tracer
advection；R22/R09/R34 和 halo 等到成为第一热点时再分别扩展。新增 sites 必须验证
调用次数、父子覆盖率、rank/node 元数据和 observer effect；仅在 Python 注册 site
名称而 Fortran 源码没有 `profile_site_on/off` 调用，不算已实现诊断。

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

### Exact 通道的触发式 1-rank 正确性门禁

`valid_test.py` 在计算节点用官方 Intel 2017.5.239、HPC-X 2.7.4、NetCDF 4.4.1 干净编译，1 rank 跑固定 `4/20` 步双向嵌套样例，比较 `SCS_avg_0001.nc`、`Dongsha60_avg_0001.nc` 中 13 个变量（`temp salt u v zeta NO3 NH4 PO4 diatom microzooplankton detritus oxygen TIC`）：每变量 `RMSE <= 1e-5` 且 `max_abs <= 1e-5`，并检查文件、维度、shape、缺失值掩膜、NaN/Inf。使用服务器封存基线，不替代主办方完整三天 `vali.py`。

numerical 通道仍保留所有结构检查，但数值判定使用经单元测试锁定的官方逐文件、
逐变量 RMSE 阈值，并额外输出 max_abs 和阈值占用比例。不能在模型候选分支临时修改
comparison 模式、阈值表或判定逻辑。

### 日常门禁管线速查

`sync_to_cluster.sh`（WSL 同步，排除输入大文件与远端基线/runs/builds/日志）→ `finalize_cluster_sync.sh`（检查输入、建 `Inputfiles` 软链、存源码快照）→ `run_cluster_gate.sh build`（提交并等待 Slurm，透传退出码）→ `cluster_gate.sbatch`（队列/官方环境）→ `valid_test.py build`（干净编译、SHA-256、报告）→ `profile_128.py`（4n64 筛选运行、数值 comparison、profiling 报告）→ kernel 阶段边界执行 4n96/`6x16` 生产确认。触发风险条件时，在 commit 前额外执行 `run_cluster_gate.sh validate`；numerical 候选按双通道规则增加完整任务门禁。

故障定位：同步/输入链接失败看同步脚本输出；编译看 `build.log` 和 `build_report.json`；MPI/运行异常看 `model.log` 和 Slurm stderr；数值失败看 profiling run 的 `run_report.json`，触发式 1-rank 门禁失败再看 `validation_report.json`；资源看 `resource.log`；diagnostic 看 `profile_diagnostics.json`、`diagnostics_validation` 和各 rank 的 `profile_diag_rank_*.log`，trace 再看 `profile_trace.perfetto.json`。构建产物目录 `Local_Lab/runs/validation/candidate_*/`，DEMO 产物目录 `Local_Lab/runs/profile128/<label>_*/`。

## 决赛运行与最终验收

- 配置文件 `ROMS_CoSiNE15/ROMS/External/ocean_SCS_Dongsha60_bio15.in`。`NTIMES` 第一个数对应外层 `SCS`，第二个对应内层 `Dongsha60`：完整三天 `2592  12960`；一天 `864  4320`；半天 `432  2160`。缩短时两网格同比例调整；最终提交前恢复完整三天并复查实际输入文件。
- 当前正式配置是队列 `kshcexclu06`、4 节点、96 ranks、每节点 24 ranks、`6x16`、
  L3-balanced NUMA-row binding，不使用 DCU。调整 ranks、`NtileI/NtileJ` 或绑核前先
  理解嵌套网格进程分配并用缩时任务实测；不要假设单网格 tile 数等于总核数。
- `start_full_profile_scaling_sweep.sh` 是历史 scaling 诊断工具（含已知失败的 1 节点
  case），**不是候选或正式入口**。内部完整候选使用
  `Local_Lab/run_full_4n96_6x16_l3.sh`；现场简洁提交使用
  `sysu_official_launch/sub.sh`。
- 最终成绩用相同源码的 **no-profile 二进制**计时。内部累计候选流程如下；每次只提交
  一个 4n96 case，脚本会在同 allocation 先做 60/300 慢节点预检，再运行完整任务：

  ```bash
  bash Local_Lab/run_build_no_profile.sh
  no_profile_binary=Local_Lab/builds/profiling/<exact-build>/bin/oceanM
  test -x "$no_profile_binary" && sha256sum "$no_profile_binary"

  MCC_FULL_BINARY="$no_profile_binary" \
  MCC_FULL_BINARY_SHA256="$(sha256sum "$no_profile_binary" | awk '{print $1}')" \
  MCC_COMPARISON_MODE=exact \
    bash Local_Lab/run_full_4n96_6x16_l3.sh
  ```

  记录命令打印的 exact `full_run`，不能用通配符猜。必须满足
  `full_run_report.json passed=true`、`run_report.json passed=true`、
  `normal_end=true`、适用正确性通道的 comparison 通过，并完成官方验证。numerical
  完整候选必须把上例改为 `MCC_COMPARISON_MODE=numerical`；若报告仍显示 exact，
  不得把它当作 numerical 门禁证据。

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
