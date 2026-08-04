# MCC 2026 决赛优化约束

## 目标与环境

- 目标：在结果通过精度验证的前提下，缩短 ROMS-CoSiNE15 完整三天模拟的运行时间。
- 当前公开基准：`01:50:06`。
- 决赛环境：华东一区（昆山），队列 `kshcexclu06`；每队最多 4 节点、每节点 32 核，共 128 CPU 核；不使用 DCU。
- 主办方决赛根目录：`/public/share/mcc2026_final/`。本仓库模型源码位于 `ROMS_CoSiNE15/`。

## 决赛服务器访问

- 从 WSL 仓库环境连接登录节点：

  ```bash
  ssh -i ~/.ssh/fangxihong_key -p 65023 fangxihong@cancon.hpccube.com
  ```

- 已确认该连接可登录到账号的 `/public/home/fangxihong`。默认只做读操作探查；上传源码、修改远程文件、提交/取消作业或运行官方验证前，先确认当前实验目标和作业范围。
- 连接后必须通过 Slurm 向 `kshcexclu06` 申请计算节点；不要用登录节点的 `lscpu` 结果代替计算节点实测配置。
- 服务器门禁工作区：`/public/home/fangxihong/MCC-Final-SYSU`。本地代码通过 `Local_Lab/sync_to_cluster.sh` 同步；服务器的基线、runs、builds 和日志不得被本地同步覆盖。

### 已打通的服务器门禁状态

- 2026-08-03 已在 `kshcexclu06` 计算节点生成服务器原生基线：Slurm job `118468694`，状态 `COMPLETED`。
- 随后使用全新构建独立验证：Slurm job `118469268`，状态 `COMPLETED`；两个输出文件的 13 个变量均为 `RMSE == 0`、`max_abs == 0`，最终日志显示 `PASS`。
- 封存基线位于服务器的 `Local_Lab/baselines/mcc_4x20/`。日常调优只能运行 `validate`，不得重新运行 `baseline`；脚本会拒绝覆盖已有基线。
- 已复测源码同步：远端基线、历史运行、构建和 Slurm 日志均会保留，不会被本地文件覆盖或删除。

### 已验证的 profiling 基线（2026-08-04）

- `feat-improve-profiling` 已完成 wall-only、per-rank min/mean/max、调用次数、I/O/MPI 分类、
  nesting region 39 与子阶段 51--56、JSON/CSV 报告、离线 HTML dashboard 和 128-rank
  运行器。默认 profiler 同节点顺序平衡开销中心估计约 `+0.89%`。
- 4 节点、128 ranks、`8x16`、完整 `2592/12960` 步 profiling：job `118507345`，
  `ROMS/TOMS: DONE`，wall `9589 s`，团队已确认官方 `vali.py` 通过。
- 公开基准 `01:50:06` 与本次 profiler runner 的 `9589 s` 不是同一次运行边界和二进制，
  暂不得直接计算 speedup。wall-only instrumentation 的已测中心开销约 0.89%，不足以单独
  解释该差距；应以同一 runner、同一输入/输出节奏、相同 ranks/tiles 的 accepted 与
  candidate 配对结果判断单项优化，最终再用 no-profile 完整任务对齐比赛计时。
- 2 节点、64 ranks、`8x8`、完整任务：job `118500776`，wall `10588 s`；与 4 节点
  两个平均场的 13 个变量逐位一致。它只用于 scaling 诊断，不是决赛目标配置。
- 1 节点、32 ranks、`4x8` 在首次 nesting 通信处触发
  `MPI_Bcast/MPI_ERR_TRUNCATE`；不得把该失败结果用于 scaling 结论，也不要默认其他
  32-rank tile 形状可用。
- 60/300 步 demo 与完整 4 节点任务的热点排序和占比接近。日常候选可先用固定
  60/300 步、128-rank profiling 筛选；只有最终累计候选才至少运行一次完整三天，时间
  允许时再重复测量。
- 当前可复用的服务器 profiling reference 是
  `Local_Lab/runs/profile128/sections-overhead-a-on_20260803T110240Z_44162`。详细数字和
  region 解释见 `Local_Lab/profiling-analysis.md`。
- 第一项优化的 accepted/control 二进制是
  `Local_Lab/runs/validation/candidate_20260803T105345Z_12953/bin/oceanM`，SHA-256 为
  `a9b08b31478da2546ca9ba7dc25ad2401afee78e63457e646a1428d84973a3e5`。每接受一个新
  优化后，下一项实验应把 accepted/control 更新为新提交通过门禁后生成的二进制，避免
  只与最初版本比较而掩盖后续回归。

## 修改边界

**禁止修改：**

- 物理计算方案、模型方程及其科学含义。
- 主办方提供的初始场、边界场、强迫场和比赛输入数据。
- 为获得速度而跳过必需计算、缩短最终模拟时长，或放宽/绕过验证。
- `Local_Lab/baselines/mcc_4x20/outputs_valid/` 及其 `manifest.json`。禁止在日常优化中运行 `baseline` 命令；只有基线缺失、源码树干净且团队明确要求时才可重建。

**允许修改：**

- 不改变物理方案的等价实现优化，例如消除可证明的冗余计算、改善循环/内存访问、减少临时量和数据复制。
- MPI 分块、通信、缓存、同步、聚合及负载均衡优化。
- 编译和运行配置优化，但每一种配置都必须单独验证，且不得依赖比赛禁用的硬件。
- 调试时临时缩短 `NTIMES`；不得把缩短配置当作最终结果。

边界不确定时，先停止修改并向团队确认。ROMS 后续版本的改动（例如相关 tickets）只能作为实现参考，移植后仍须走完整门禁，不能因“官方已有”而默认正确。

## 每次优化的固定流程

以下闭环是下一位工程师/Agent 的强制工作顺序。一个分支只处理一个主要性能假设；
不得把算法改写、编译 flags、MPI 分块等多个变量混在同一次实验中。

1. 从已合并且通过门禁的干净 `main` 创建实验分支，记录回退锚点：

   ```bash
   git status --short
   git switch main
   git switch -c perf/<single-hypothesis>
   accepted_commit=$(git rev-parse HEAD)
   echo "accepted_commit=$accepted_commit"
   ```

   `git status --short` 必须为空，并确认 `main` 已包含 `Local_Lab/profile_128.py` 和
   `Local_Lab/profile_dashboard.html`；否则说明 profiling 分支尚未合并，停止优化。
   将打印出的完整 SHA 写入实验记录，不能只依赖会随终端消失的 shell 变量。先从
   baseline bundle 写下一个可证伪假设、目标 region、预期变化和不应变化的数值行为；
   区分计算、MPI 通信/等待和 I/O，避免凭直觉改动。
2. 一次只做一个可解释的等价实现优化，保留可审查的 diff。普通实验 commit 的硬门禁
   只有本地测试和服务器 demo 正确性；不要求先跑完整三天或官方 `vali.py`。
3. 在 Ubuntu WSL 的仓库根目录运行代码级快速测试：

   ```bash
   python -m pytest -q Local_Lab/tests
   ```

   若当前环境缺少依赖，先在专用 Python 环境中安装
   `Local_Lab/requirements-validation.txt`，不要改动测试来规避环境问题。

4. ROMS 源码、编译选项或运行语义有任何变化后，同步到服务器并运行 demo 正确性门禁：

   ```bash
   bash Local_Lab/sync_to_cluster.sh
   ssh -i ~/.ssh/fangxihong_key -p 65023 fangxihong@cancon.hpccube.com
   cd /public/home/fangxihong/MCC-Final-SYSU
   bash Local_Lab/run_cluster_gate.sh validate
   ```

   不得只运行本地单元测试或在登录节点直接运行模型后就宣称优化有效。
5. 仅在三个条件同时满足时允许形成实验 commit：包装命令退出码为 0、终端明确显示
   `[validate] PASS`、最新 `validation_report.json` 的 `passed` 为 `true`。提交前运行
   `git diff --check`、审查 `git diff -- ROMS_CoSiNE15 Local_Lab`，只用明确文件列表
   `git add`；禁止 `git add .`。commit 信息应描述被 demo 验证的单一优化。
6. 实验 commit 形成后再做性能 profiling，判断它是否值得保留或继续。记录新的
   candidate 目录以及上一个已接受 candidate 的二进制路径。candidate 路径必须来自
   本次 `run_cluster_gate.sh validate` 输出，不能用 `ls ... | head` 猜“最新”目录。运行
   profiling 前检查本次报告和二进制，并记录 SHA-256：

   ```bash
   candidate_dir=Local_Lab/runs/validation/candidate_<exact-timestamp>
   python -c 'import json,sys; assert json.load(open(sys.argv[1]))["passed"] is True' \
     "$candidate_dir/validation_report.json"
   test -x "$candidate_dir/bin/oceanM"
   sha256sum "$candidate_dir/bin/oceanM"
   ```

   用 `profile_overhead.py`
   将“新候选”作为 profile binary、“上一个已接受版本”作为 control binary，在同一
   Slurm allocation 内做 128-rank、60/300 步 A/B 配对。两个二进制都可以启用 PROFILE；
   此处脚本名和 on/off 字段沿用历史命名，实际语义是 candidate/accepted：

   ```bash
   source /public/share/mcc2026_final/miniforge3/etc/profile.d/conda.sh
   conda activate vali
   python Local_Lab/profile_overhead.py \
     --profile-binary Local_Lab/runs/validation/<new-candidate>/bin/oceanM \
     --control-binary Local_Lab/runs/validation/<accepted-candidate>/bin/oceanM \
     --label <hypothesis>-ab --order off-on \
     --outer-steps 60 --inner-steps 300 --tiles-i 8 --tiles-j 16
   python Local_Lab/profile_overhead.py \
     --profile-binary Local_Lab/runs/validation/<new-candidate>/bin/oceanM \
     --control-binary Local_Lab/runs/validation/<accepted-candidate>/bin/oceanM \
     --label <hypothesis>-ba --order on-off \
     --outer-steps 60 --inner-steps 300 --tiles-i 8 --tiles-j 16
   ```

   两组 `overhead_report.json` 必须 `passed=true` 且 comparison 通过；候选一侧必须有
   `profile_report.json`。在这种复用方式下，`overhead_percent < 0` 才表示候选更快。
   两个顺序的 candidate/accepted 比值取几何平均：初筛要求至少快 2%，且任一顺序不得
   慢 1% 以上；否则标为 inconclusive 并增加配对重复，不能宣称加速。还要比较 total
   wall、目标 region wall/调用次数、rank imbalance 和非目标热点；inclusive region
   不得相加成 100%。
7. demo 正确性失败时不得 commit。先保留失败 run 路径和报告用于诊断，然后恢复到
   `accepted_commit` 的代码状态并重新设计：

   ```bash
   git status --short
   git diff -- ROMS_CoSiNE15 Local_Lab
   git restore --source="$accepted_commit" -- <本次候选修改的明确文件列表>
   python -m pytest -q Local_Lab/tests
   ```

   `git restore` 不处理本次新增的未跟踪文件。用 `git status --short` 和实验开始时的
   文件清单识别它们，逐个移动到 `/tmp/<experiment>-failed/` 留档；禁止使用宽泛的
   `git clean`。只有确认工作树中没有其他人的无关修改时才能恢复文件；禁止使用
   `git reset --hard`。如果实验 commit 后的多-rank profiling 出现数值 comparison 失败，
   或证明该优化无效/显著变慢，使用 `git revert <experiment-commit>` 回到上一个已接受
   状态，不要改写共享历史。若只是性能结果受噪声影响，则保留实验记录并增加短测，不要
   因此运行完整三天。恢复后确认源码 diff 和本次新增文件都已清除，再重新同步并让 demo
   门禁 PASS，才能开始下一种设计。
   不得通过提高容差、减少变量、修改输入、重建基线或跳过计算来挽救失败候选。
8. profiling 显示性能方向有效后，才把该实验 commit 标记为新的 accepted commit，并把
   下一项实验的 accepted/control 二进制更新到该版本。profiling 是保留决策，不是普通
   commit 的前置门禁。
9. 服务器 1-rank、`4/20` 步 demo 是严格正确性门禁，不是 128 核性能结论。涉及 MPI、
   分块、通信或同步的改动，还必须完成 128-rank 缩时诊断，检查正常结束、输出齐全、
   NaN/Inf 和同配置 13 变量 comparison，才能判断是否保留该实验 commit。
10. 只有团队选出的少数累计版本进入决赛候选阶段，才运行 128-rank 完整三天任务和
   主办方 `vali.py`。这两项绝不是每个 commit 的门禁；至少一个最终提交候选必须完成，
   时间允许时再重复测量。只有完整任务和官方验证都通过，才能报告最终成绩。

`valid_test.py` 在服务器 Slurm 计算节点上使用官方 Intel 2017.5.239、HPC-X 2.7.4 和 NetCDF 4.4.1 环境进行干净编译，以 1 个 MPI rank 运行固定 `4/20` 步双向嵌套样例，并对以下两个文件中的 13 个变量进行比较：

- `SCS_avg_0001.nc`、`Dongsha60_avg_0001.nc`
- `temp salt u v zeta NO3 NH4 PO4 diatom microzooplankton detritus oxygen TIC`

服务器 demo 门禁要求每个变量的 `RMSE <= 1e-5` 且 `max_abs <= 1e-5`，并检查文件、维度、shape、缺失值掩膜及 NaN/Inf。它使用在官方服务器上重新生成和封存的基线，不使用 WSL 基线，也不替代主办方完整三天 `vali.py`。

## 服务器 demo 门禁的执行管线

```text
WSL 本地源码
  -> sync_to_cluster.sh
     -> rsync 到服务器工作区，并保护基线、运行记录、构建和日志
     -> finalize_cluster_sync.sh 检查输入、建立软链接、记录源码快照
  -> SSH 登录服务器工作区
  -> run_cluster_gate.sh validate
     -> sbatch --wait 提交 cluster_gate.sbatch
  -> kshcexclu06 计算节点
     -> 加载 Intel、MPI、NetCDF/HDF5 和 vali Python 环境
     -> valid_test.py validate
        -> 校验封存基线完整性和工具链类型
        -> 创建独立构建目录并干净编译
        -> 生成 1-rank、4/20 步 demo 输入
        -> mpirun 运行 ROMS-CoSiNE15
        -> 检查正常结束、输出文件和 NaN/Inf
        -> 比较 2 个 NetCDF 文件中的 13 个变量
        -> 写 validation_report.json 并输出 PASS/FAIL
  -> run_cluster_gate.sh 打印 Slurm 日志并原样返回作业退出码
```

各脚本各自只承担一个主要职责：

| 文件 | 运行位置 | 职责 |
| --- | --- | --- |
| `Local_Lab/sync_to_cluster.sh` | WSL | 把本地源码同步到固定服务器工作区；排除输入大文件、本地生成物以及远端基线、runs、builds 和日志。 |
| `Local_Lab/finalize_cluster_sync.sh` | 服务器登录节点 | 检查共享输入，建立 `ROMS_CoSiNE15/Inputfiles` 软链接，并保存与本地提交/diff 对应的远端源码快照；不运行模型。 |
| `Local_Lab/run_cluster_gate.sh` | 服务器登录节点 | 只允许 `baseline` 或 `validate`，提交并等待 Slurm 作业，汇总 stdout/stderr，并把 Slurm 状态转换成调用者可见的退出码；日常只用 `validate`。 |
| `Local_Lab/cluster_gate.sbatch` | Slurm 计算节点 | 声明队列、节点、CPU、内存和时限，加载官方编译/运行环境，然后调用 `valid_test.py`。 |
| `Local_Lab/valid_test.py` | Slurm 计算节点 | 真正执行编译、demo 运行、输出检查、数值比较和 JSON 报告生成，是正确性门禁核心。 |

### 日常最短操作

在 WSL 仓库根目录运行：

```bash
python -m pytest -q Local_Lab/tests
bash Local_Lab/sync_to_cluster.sh
ssh -i ~/.ssh/fangxihong_key -p 65023 fangxihong@cancon.hpccube.com
```

登录服务器后运行：

```bash
cd /public/home/fangxihong/MCC-Final-SYSU
bash Local_Lab/run_cluster_gate.sh validate
```

无需手动查找 job ID 才能判断结果：包装脚本会等待 Slurm 作业结束，并把完整 stdout 和必要的 stderr 打到当前终端。自动化调用仍必须检查该命令的退出码。

### 结果与故障定位

- Slurm 包装日志：`Local_Lab/cluster_logs/mcc-demo-gate_<jobid>.out` 和 `.err`。
- 每次验证的完整产物：`Local_Lab/runs/validation/candidate_*/`。
- `build.log`：编译器、依赖或链接错误。
- `model.log`：MPI 启动、ROMS 运行错误和正常结束标记。
- `resource.log`：作业资源使用情况。
- `validation_report.json`：基线完整性、工具链、两个文件的逐变量误差及最终 `passed` 状态。
- 同步或输入链接失败先看同步脚本输出；编译失败看 `build.log`；模型异常看 `model.log` 和 `.err`；数值失败看 `validation_report.json`。不得通过放宽阈值或重建基线处理数值失败。

## 决赛运行与最终验收

- 配置文件：`ROMS_CoSiNE15/ROMS/External/ocean_SCS_Dongsha60_bio15.in`。`NTIMES` 的第一个数对应外层 `SCS` 网格，第二个数对应内层 `Dongsha60` 网格。
- 完整三天：`NTIMES == 2592  12960`。
- 一天调试：`NTIMES == 864  4320`。
- 半天调试：`NTIMES == 432  2160`。
- 缩短时长时两个网格按相同比例调整；最终提交前恢复完整三天配置并复查实际输入文件。
- 以根目录 `sub.sh` 作为提交脚本起点，使用队列 `kshcexclu06`、4 节点和 128 CPU 核。调整 MPI rank 或 `NtileI/NtileJ` 前先理解嵌套网格的进程分配，并用缩时任务实测；不要假设单个网格的 tile 数必然等于总核数。
- `start_full_profile_scaling_sweep.sh` 是节点 scaling 诊断工具，不是日常决赛候选入口；
  它会包含已知失败的 1 节点 `4x8` case。正式候选只运行 4 节点、128 ranks。
- profiler 用于定位热点，最终成绩计时使用相同源码的 no-profile 二进制。先构建并记录
  `run_build_no_profile.sh` 输出的 exact binary 路径，再用 60/300 步同 allocation 配对
  确认 profile/no-profile 输出 comparison 通过。下面每次命令只提交一个 4 节点 case，
  不会触发 1/2 节点 sweep：

  ```bash
  bash Local_Lab/run_build_no_profile.sh
  no_profile_binary=Local_Lab/builds/profiling/<exact-build>/bin/oceanM
  test -x "$no_profile_binary"
  sha256sum "$no_profile_binary"

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

  记录该命令打印的 exact `run_dir`，后续 `full_run` 必须指向这里，不能用通配符猜目录。
  这一步只用于团队挑出的最终累计版本，不属于普通 commit 流程。至少完成一次；若比赛
  时间和机时允许，可在独立 allocation 重复并报告中位数。每次 `run_report.json` 都必须
  满足 `passed=true`、`normal_end=true`、`comparison.passed=true`，且分别执行下面的
  官方 `vali.py` 检查。每次只运行 4 节点 case，不重新运行 scaling sweep。
- 完整三天运行成功并生成最终输出后，在集群执行主办方验证。官方脚本当前没有命令行
  参数，且 `dir_test` 是占位路径；不得修改共享的 `/public/share/.../vali.py` 本体。
  复制脚本到候选 run 目录，只替换这一行，并用 `diff` 确认其余逻辑未变：

  ```bash
  source /public/share/mcc2026_final/miniforge3/etc/profile.d/conda.sh
  conda activate vali
  full_run=/public/home/fangxihong/MCC-Final-SYSU/Local_Lab/runs/profile128/<full-run>
  test "$(grep -c '^dir_test = ' /public/share/mcc2026_final/vali.py)" -eq 1
  cp /public/share/mcc2026_final/vali.py "$full_run/vali_official.py"
  sed -i "s|^dir_test = .*|dir_test = '$full_run/output/'|" "$full_run/vali_official.py"
  set +e
  diff -u /public/share/mcc2026_final/vali.py "$full_run/vali_official.py"
  vali_diff_status=$?
  set -e
  test "$vali_diff_status" -eq 1
  set -o pipefail
  python "$full_run/vali_official.py" 2>&1 | tee "$full_run/vali_official.log"
  ```

  `grep` 先保证官方脚本恰好有一个 `dir_test` 定义；复制后只有该行会被 `sed` 替换。
  `diff` 必须显示仅这一处变化并返回 1；返回 0 表示路径未替换，返回大于 1 表示命令
  错误，两者都会停止。该脚本数值失败时不保证返回非零退出码，必须检查所有 RMSE 行
  和最终文本
  `最终判定：两组文件所有变量RMSE均在阈值范围内，优化结果无异常`。

只有“完整任务正常结束 + 官方 `vali.py` 通过”的结果才可作为最终有效成绩。实验记录至少包含 commit/diff、编译器与 flags、节点/rank/分块、输入时长、wall time、重复次数、本地验证报告和官方验证结果。
