# MCC ROMS-CoSiNE 优化手册与服务器正确性门禁

这份文档用于在每次调优前快速恢复项目上下文，并规定修改、计时、验证和提交的固定流程。比赛规则与不可修改边界以 [`../AGENTS.md`](../AGENTS.md) 为准。

最终目标是在不改变物理计算方案、初始场、边界场和强迫场，并通过主办方精度验证的前提下，缩短完整三天双向嵌套模拟的运行时间。

## 服务器为准的日常流程

本地 WSL 只负责编辑、diff 审查和快速单元测试。编译、demo 运行、精度比较和候选性能记录均以昆山服务器为准。

```bash
# WSL：同步代码，不覆盖服务器基线和运行产物
bash Local_Lab/sync_to_cluster.sh

# 服务器登录节点：提交到 kshcexclu06 并等待 PASS/FAIL
cd /public/home/fangxihong/MCC-Final-SYSU
bash Local_Lab/run_cluster_gate.sh validate
```

服务器初始部署时且仅在基线缺失、源码干净和团队明确要求时运行：

```bash
bash Local_Lab/run_cluster_gate.sh baseline
```

远程工作区是 `/public/home/fangxihong/MCC-Final-SYSU`，输入数据通过符号链接复用 `/public/home/fangxihong/ROMS_CoSiNE15/Inputfiles`。同步脚本保护远程 `Local_Lab/baselines/`、`runs/`、`builds/` 和 `cluster_logs/`。

## 每次开始调优前先检查

```text
确认 Git 状态和当前分支
  -> 确认 MPI ranks 与两个网格的 NtileI*NtileJ 一致
  -> 写下本次唯一的优化假设
  -> 记录未优化基准 wall time
  -> 修改并运行本地快速单元测试
  -> 同步服务器，在计算节点干净编译并执行 4/20 步正确性门禁
  -> 正确性 PASS 后运行一次 2 节点、64-rank、60/300 步 profiling demo
  -> profiling 有效后提交单一 accepted commit
  -> 只有最终累计候选才运行完整三天和官方 vali.py
```

不要同时修改算法、编译参数和 MPI 分块，否则即使变快，也无法判断收益来自哪里。

## Git 安全基线与实验分支

最初建立服务器门禁的历史安全基线提交为：

```text
77a4a4c chore: establish optimization validation baseline
```

该提交没有修改 `ROMS_CoSiNE15/` 源码。当前优化的回退锚点应是 profiling 分支合并后、
已通过门禁的最新 `main`，而不是固定退回这个历史提交。原始代码已经由 Git 保存，不需要
额外复制源码目录。开始一项优化前，从干净的 `main` 创建独立分支：

```bash
git status --short
git switch main
git switch -c perf/ngetd-point-gather
accepted_commit=$(git rev-parse HEAD)
```

一个分支只验证一个主要假设，例如：

```text
perf/ngetd-point-gather    只优化 Grid 1 ngetD / point gather
perf/ticket-861-vweights   只优化垂向权重/冗余插值
perf/ticket-747-assemble   只比较接触点集合通信
perf/tiling-128            只比较 MPI 分块和绑核
```

修改后、进入远端门禁前检查源码差异；此时仍不要 commit：

```bash
git diff --stat
git diff -- ROMS_CoSiNE15
python -m pytest -q Local_Lab/tests
bash Local_Lab/sync_to_cluster.sh
# 随后在服务器工作区运行：bash Local_Lab/run_cluster_gate.sh validate
```

本地测试和服务器 4/20 正确性 demo 通过后，只运行一次 2 节点、64-rank、60/300 步 profiling
demo；两层短 demo 都通过且性能方向有效后，才能执行显式 `git add` 和 `git commit`。
普通 commit 不需要完整三天或官方 `vali.py`。不要使用 `git add .` 把日志、输出或无关
修改一起提交；失败实验先保留测量记录，再恢复 accepted 版本并重新设计。

### 可直接交接的单项优化闭环

下一位工程师/Agent 对每个假设严格执行：

```text
读取 baseline bundle，写下单一可证伪假设
  -> 只实现该项等价优化
  -> 本地 pytest
  -> sync_to_cluster.sh
  -> run_cluster_gate.sh validate
  -> 4/20 正确性 demo PASS
  -> 使用该 candidate/bin/oceanM 做一次 2 节点、64-rank、60/300 profiling demo
  -> 检查数值 comparison 和目标 region
  -> 有效才形成单一 accepted commit；无效则恢复并重新设计
  -> 只有最终累计候选才跑完整三天和官方 vali.py
```

服务器正确性 demo PASS 后，使用刚生成的候选二进制只跑一次 profiling，并与上一个
accepted 的同配置 run 做数值 comparison：

首次优化前若还没有 2 节点、64-rank、60/300 步 reference，只用当前 accepted 二进制
生成一次；以后直接把每个新 accepted 候选的 profiling run 作为下一次 reference，不再
额外跑 control：

```bash
python Local_Lab/profile_128.py \
  --binary Local_Lab/runs/validation/candidate_20260803T105345Z_12953/bin/oceanM \
  --label accepted-2n64-reference \
  --outer-steps 60 --inner-steps 300 \
  --nodes 2 --ranks 64 --tiles-i 8 --tiles-j 8
```

每个候选的唯一 profiling 命令是：

```bash
python Local_Lab/profile_128.py \
  --binary Local_Lab/runs/validation/<new-candidate>/bin/oceanM \
  --label <hypothesis>-2n64 \
  --outer-steps 60 --inner-steps 300 \
  --nodes 2 --ranks 64 --tiles-i 8 --tiles-j 8 \
  --reference-run Local_Lab/runs/profile128/<accepted-2n64-reference-run>
```

这一份 run 同时产生数值 comparison、变量量值、总 wall time、热点、nesting 子阶段和
rank 离散。接受要求 `run_report.json` 的 `passed`、`normal_end`、`comparison.passed`
都为 `true`，并存在 `profile_report.json`；同时目标 region 或总时间应显示有用方向，且
没有明显把耗时转移到其他热点。默认不自动重复；结果接近噪声时由团队决定是否再测。

若正确性 demo、profiling comparison 或性能判据失败，禁止 commit。先记录失败 run，
再把本次明确修改的文件恢复到开始时记录的 `accepted_commit`：

```bash
git status --short
git diff -- ROMS_CoSiNE15 Local_Lab
git restore --source="$accepted_commit" -- <本次候选修改的明确文件列表>
python -m pytest -q Local_Lab/tests
```

`git restore` 不处理本次新增的未跟踪文件；必须先用 `git status --short` 找出它们，按
本次实验的明确文件清单逐个移动到 `/tmp/<experiment>-failed/` 留档，不能使用宽泛的
`git clean`。不要在有无关未提交改动时恢复文件，也不要使用 `git reset --hard`。如果
问题在 commit 后才被发现，则使用 `git revert <bad-commit>` 回到 accepted 状态。
恢复后确认源码 diff 为空，重新同步并让两层短 demo 通过，再从新的实现思路开始；不得
放宽阈值、减少变量、重建基线或修改输入来绕过失败。

## 128 核运行配置必须先对齐

根目录 [`../sub.sh`](../sub.sh) 当前申请 4 节点、128 tasks，并执行：

```bash
mpirun -np 128 ./oceanM ROMS/External/ocean_SCS_Dongsha60_bio15.in
```

但官方输入文件当前是：

```text
NtileI == 4  4
NtileJ == 8  8
```

两个网格的 tile 数都是 `4*8=32`，与 `-np 128` 不一致。本项目 MPI 输入说明要求每个网格满足：

```text
NtileI(ng) * NtileJ(ng) == MPI ranks
```

因此在进行性能优化前，必须先把运行脚本和输入配置对齐。128 ranks 的候选可以包括：

```text
粗网格：16*8，细网格：8*16
两个网格都使用：16*8
两个网格都使用：8*16
```

这些只是待测候选，不是预先确定的最优配置。粗、细网格尺寸及接触点分布不同，允许分别选择方向，但每个网格的乘积都要与实际 ranks 一致。启动后还要检查日志中的 `Parallel Nodes` 和 `Tiling`，确认程序实际采用了预期配置。若比赛最终固定为 64 核，则 `mpirun -np` 和两个网格的 tile 乘积都应同时改为 64。

服务器 demo 门禁会自动生成 `1*1` 分块并使用一个 MPI rank，不受上述 128 核配置影响。

## 从编译到时间步的代码调用链

```text
makefile
  -> ROMS_APPLICATION=BYE24BIO15
  -> ROMS/Include/bye24bio15.h 选择 NESTING、BIO_UMAINE15 等功能
  -> 生成 MPI 可执行文件 oceanM

Master/ocean.h
  -> ROMS_initialize
     -> ROMS/Nonlinear/initial.F
  -> ROMS_run
     -> ROMS/Nonlinear/main3d.F 的时间步循环
        -> step2d / step3d：物理计算
        -> gls：垂向混合
        -> bio_UMAINE15.h：CoSiNE 生态过程
        -> nesting.F：粗细网格交换
  -> ROMS_finalize
     -> 输出计时报告并关闭文件
```

最值得先阅读的文件：

| 作用 | 文件 |
|---|---|
| 编译目标、源码列表和可执行文件 | `../ROMS_CoSiNE15/makefile` |
| 本案例 CPP 功能开关 | `../ROMS_CoSiNE15/ROMS/Include/bye24bio15.h` |
| 程序入口 | `../ROMS_CoSiNE15/Master/ocean.h` |
| 初始化/运行/结束控制 | `../ROMS_CoSiNE15/ROMS/Drivers/nl_ocean.h` |
| 高频三维时间步 | `../ROMS_CoSiNE15/ROMS/Nonlinear/main3d.F` |
| 双向嵌套调度和插值 | `../ROMS_CoSiNE15/ROMS/Nonlinear/nesting.F` |
| MPI 汇聚、广播和规约 | `../ROMS_CoSiNE15/ROMS/Utility/distribute.F` |
| MPI 邻域 halo 交换 | `../ROMS_CoSiNE15/ROMS/Utility/mp_exchange.F` |
| CoSiNE 生态计算 | `../ROMS_CoSiNE15/ROMS/Nonlinear/Biology/bio_UMAINE15.h` |
| 运行参数和数据文件路径 | `../ROMS_CoSiNE15/ROMS/External/ocean_SCS_Dongsha60_bio15.in` |

## 双向嵌套的数据流

同一个网格在不同阶段可能既是 donor（提供信息）又是 receiver（接收信息）。主要流程是：

```text
粗网格 donor
  -> ngetD：提取各 rank 拥有的接触点
  -> mp_assemble：把分散片段合成为接触点数组
  -> nputD：执行水平/垂向插值并写入细网格缓存
  -> 细网格执行更多时间步
  -> n2way：细网格结果平均、反馈到粗网格
```

需要区分三类通信：

- `mp_exchange`：只和相邻 rank 交换 halo 条带。
- `mp_assemble`：每个 rank 提交自己的接触点片段，并让参与者得到汇聚结果。
- `mp_aggregate2d/3d`：把 tiled 场组合成较完整的二维或三维场，常用于细网格向粗网格反馈。

当接触点在 ranks 之间分布不均时，没有数据的 rank 仍可能等待 collective 中最慢的 rank，这就是嵌套负载不均与 scaling 提前饱和的来源之一。

## 能改什么，以及风险等级

| 层次 | 示例 | 风险与要求 |
|---|---|---|
| 运行配置 | MPI ranks、`NtileI/NtileJ`、绑核和进程映射 | 低风险，但必须实测且保持任务合法 |
| 编译配置 | 优化等级、向量化、IPO、体系结构选项 | 中低风险；任何 flags 变化都要重新验证精度 |
| Profiling | 新增 timer、细分 nesting/MPI 区域 | 低风险；用于建立证据，不直接计入最终加速 |
| 嵌套实现 | 缓存垂向权重、减少重复插值和复制 | 中风险；必须证明数学等价 |
| MPI 集合通信 | 替换或选择 assemble/aggregate 的 collective | 中风险；重点检查死锁、数组完整性和多 rank 结果 |
| 物理/生态 kernel | 循环顺序、内存布局、临时数组和向量化 | 高风险；不得改变方程、参数或计算方案 |
| 初始/边界/强迫场 | 修改 NetCDF 或用不同输入绕开计算 | 禁止 |

“不能改物理方案”不等于所有物理源码都不能碰；可以做数学等价的实现优化，但不能更换离散格式、改变参数、跳过必要过程或用降低精度换取未经验证的速度。

## Profiling：先回答时间花在哪里

本仓库已实现的 rank 统计、128-rank 运行方法、overhead 对照和实测热点见
[`profiling-analysis.md`](profiling-analysis.md)。

本项目已经启用 ROMS 的 `PROFILE`，正常结束时会在模型日志尾部输出各计算区域耗时。现有服务器 1-rank、4/20 步 demo 只能说明代码确实执行了 2D 模式、GLS、三维预测/校正、tracer 混合和 biology 等区域，不能代表 128 核通信瓶颈。

上游 2017 版本 profiler 原本有两个重要盲区：

- `mod_strings.F` 虽然定义了 `Multiple-grid nesting processing`，但 `nesting.F` 没有完整的对应计时包围。
- `mp_assemble` 等操作被归入较粗的通信区域，难以分辨接触点汇聚、完整场聚合和等待分别占多少。

当前分支已经补上 region 39 总计时、51--56 nesting 子阶段，以及 region 46/49 的
gather/point-gather rank 统计。对应关系如下：

```text
ngetD                         -> region 53
nputD                         -> region 54
nzwgt / z_weights             -> region 51
n2way                         -> region 55
mp_aggregate2d / 3d gather    -> region 46
mp_assemble point gather      -> region 49
collective / rank waiting     -> wall min/mean/max 与 imbalance
```

每次新 profiling 运行还会生成 `profile_bundle.json`。把它下载到本地后，直接用浏览器
打开 [`profile_dashboard.html`](profile_dashboard.html)，拖入这一份 JSON，即可离线查看：

- 外部 wall time、节点/rank/tile、正常结束和数值比较状态；
- Grid 1/2 的 compute、MPI、读/写 I/O 分类和 hotspot；
- region 51--56 nesting 分解以及 rank min/mean/max、最慢 rank、imbalance；
- reference/candidate 每个验证变量的 min/mean/max、有效/掩膜点数、RMSE 和 max_abs；
- 可搜索的完整 region 表及常用函数提示。

页面不上传文件、不访问网络，也不需要在集群上启动 Web 服务。旧的
`profile_report.json` 或 `run_report.json` 也能单独打开，但旧报告从未采集的变量量值
会显示为 unavailable，不能事后从 RMSE 推导。

完整三天的 1/2/4 节点顺序 profiling 仅用于 scaling 研究，不是日常最终候选入口。已知
1 节点 `32 ranks / 4x8` 会在首次 nesting 通信触发 `MPI_ERR_TRUNCATE`；不要为每个优化
重复该 sweep。需要复现实验时使用：

```bash
bash Local_Lab/start_full_profile_scaling_sweep.sh \
  Local_Lab/runs/validation/candidate_<timestamp>/bin/oceanM \
  full-3day-scaling \
  12:00:00
```

该后台启动器保持官方 `2592/12960` 步和输出节奏，依次使用
`1节点/32 ranks/4x8`、`2节点/64 ranks/8x8`、`4节点/128 ranks/8x16`，并把三份
可视化 bundle 收集到 `Local_Lab/runs/profile_scaling/<sweep>/bundles/`。详细语义、
结果目录和验证边界见 [`profiling-analysis.md`](profiling-analysis.md)。正式候选应按
[`../AGENTS.md`](../AGENTS.md) 的“决赛运行与最终验收”只运行 4 节点 no-profile 完整任务。

集群运行时同时记录外部 wall time。示例：

```bash
/usr/bin/time -v -o time.log \
  mpirun -np 128 ./oceanM ROMS/External/ocean_SCS_Dongsha60_bio15.in \
  > run.log 2>&1
```

如果节点允许使用 `perf`，可增加硬件计数器初筛：

```bash
perf stat -e task-clock,cycles,instructions,cache-misses \
  mpirun -np 128 ./oceanM ROMS/External/ocean_SCS_Dongsha60_bio15.in
```

`perf`、MPI profiling 工具和计数器权限取决于比赛集群，使用前先确认可用性。至少记录：

- 模型 wall time，不把编译和排队时间算进加速。
- 每个网格、nesting 和 biology 等区域的耗时。
- collective 通信耗时，以及最快/最慢 rank 的差距。
- 节点数、ranks、tile、绑核、编译器和 flags。
- 准备宣称稳定性能收益时再做同配置重复并比较中位数；这不是普通 commit 的前置条件。

## 老版本 tickets 的建议顺序

这些编号来自 [ROMS/TOMS 官方 Trac](https://www.myroms.org/projects/src/)。老师给出的 tickets 应当按“先可观测、再优化、最后补充正确性”的顺序使用：

1. [`#735`](https://www.myroms.org/projects/src/ticket/735)：参考新版的 profiling 区域和通信计时，先看清 nesting/MPI 时间。
2. [`#861`](https://www.myroms.org/projects/src/ticket/861)：优先研究垂向权重的预计算/复用，以及可证明无需重复执行的垂向插值。这是首个高价值源码候选。
3. [`#747`](https://www.myroms.org/projects/src/ticket/747)：比较 `mp_assemble` 等操作的 `Allgather`、`Allreduce` 或低层点对点实现；官方也明确要求针对实际机器 benchmark。
4. [`#887`](https://www.myroms.org/projects/src/ticket/887)、[`#920`](https://www.myroms.org/projects/src/ticket/920)：包含 `get_Vweights` 条件、双向嵌套边界平均、`WET_DRY` 下的 `Dcrit` 约束等正确性修订；移植性能改动时检查是否需要一起带入。
5. [`#387`](https://www.myroms.org/projects/src/ticket/387)：与本次非线性正向模拟的直接性能关系较弱，不作为前期重点。

不要整批复制新版文件。每次只移植一个逻辑完整的变化，并结合当前 2017 年左右的源码接口手工审查。

## 一项优化的完整实验记录

建议每个实验至少记录以下内容：

```text
假设：哪段代码为什么慢
改动：具体文件、函数和策略
环境：commit、编译器、flags、节点、ranks、tile、绑核
任务：4/20 步、半天、一天或完整三天
性能：每次 wall time、中位数、相对基线加速
正确性：每个 commit 记录正确性 demo 和 profiling demo；只有最终候选记录官方 vali.py
结论：保留、继续调查或放弃，以及原因
```

固定闭环：

```text
定位瓶颈
  -> 一次只实现一个优化
  -> 同步服务器并干净编译
  -> 服务器 4/20 步门禁
  -> 一次 2 节点、64-rank、60/300 步 profiling demo
  -> 两层短 demo 通过且性能有效后单独 commit
  -> 仅最终累计候选：完整三天运行和官方 vali.py
```

服务器单 rank 短任务适合发现结果错误，不适合直接决定比赛排名；MPI、分块、通信或同步优化必须以昆山集群多 rank 结果为准。

## 服务器 demo 正确性门禁概览

这套流程用于在本地修改 ROMS-CoSiNE15 源码后，将代码同步到官方服务器并固定执行：

```text
干净编译 BYE24BIO15
  -> 在 Slurm 计算节点单 MPI 进程运行 4/20 步双向嵌套案例
  -> 比较 SCS 与 Dongsha60 平均场
  -> 精度通过后记录运行时间
```

## 固定配置

配置从官方 `ROMS/External/ocean_SCS_Dongsha60_bio15.in` 每次自动生成，
不会修改原文件。相对官方配置只改变以下运行参数：

```text
NtileI  == 1  1
NtileJ  == 1  1
NTIMES  == 4  20
NAVG    == 4  20
NDEFAVG == 4  20
```

- `NtileI/NtileJ` 改成 `1/1`，与计算节点上的 `mpirun -np 1` 对应。
- `NTIMES=4/20` 让两个网格都模拟 400 秒。
- 只缩短 `NAVG/NDEFAVG`，以便在 4/20 步结束时生成验证所需的平均场。
- `DT`、物理/生态参数、初始场、边界场、强迫场均保持不变。
- `NRST/NHIS/NDEFHIS` 保持官方值，demo 不写无关的 restart/history 大文件。

## 基准

正式封存基准位于服务器工作区的：

```text
Local_Lab/baselines/mcc_4x20/
├── manifest.json
├── ocean_4x20.in
└── outputs_valid/
    ├── SCS_avg_0001.nc
    └── Dongsha60_avg_0001.nc
```

`manifest.json` 记录源码 commit、源码是否干净、输入和二进制 hash、运行参数、
墙钟时间、峰值内存，以及两份基准 NetCDF 的 SHA-256。验证前会重新计算 hash；
基准被移动、删除或改写时，测试会直接失败。

NetCDF 文件体积较大且被 `.gitignore` 排除，不会上传 Git。服务器同步脚本明确保护
`outputs_valid/`、`manifest.json` 和历史运行结果。本地同名目录是迁移前的遗留基线，
不能替代服务器基线，也不能用于正式接受候选。

基准创建命令只用于基准不存在且 ROMS 源码树完全干净时：

```bash
# 只允许在服务器工作区执行
bash Local_Lab/run_cluster_gate.sh baseline
```

如果基准目录已经存在，命令会拒绝覆盖。

## 每次优化后的固定门禁

在 Ubuntu WSL 仓库根目录同步：

```bash
bash Local_Lab/sync_to_cluster.sh
```

登录服务器后提交到计算节点：

```bash
cd /public/home/fangxihong/MCC-Final-SYSU
bash Local_Lab/run_cluster_gate.sh validate
```

`valid_test.py` 仍保留本地 profile 供工具开发诊断，但本地直接执行不属于正式门禁，
不得据此接受优化候选。服务器流程会创建全新的 build/run 目录，使用官方 Intel/MPI
工具链强制单任务干净编译当前源码，然后运行候选模型。
候选输出不会覆盖基准。

比较对象与主办方 `vali.py` 一致，为两个 `*_avg_0001.nc` 中的 13 个变量：

```text
temp salt u v zeta NO3 NH4 PO4 diatom microzooplankton
detritus oxygen TIC
```

每个变量同时要求：

```text
RMSE    <= 1e-5
max_abs <= 1e-5
```

任一文件/变量缺失、维度或 shape 不同、缺失值掩膜不同、出现 NaN/Inf，或任一误差
超限，门禁都会失败。详细结果保存在最新候选目录的
`validation_report.json`。

报告中的性能字段包括：

```text
baseline_model_wall_seconds
candidate_model_wall_seconds
saved_seconds
speedup_percent
candidate_build_seconds
candidate_model_cpu_seconds
candidate_max_rss_kib
```

`saved_seconds > 0` 才表示候选运行更快。编译时间单独记录，不计入模型加速。
4/20 步任务中初始化和共享文件系统 I/O 占比很高，单次墙钟波动只能用于初筛。普通
commit 不要求完整任务；只有团队选出的最终累计候选才至少在昆山集群运行一次完整三天
并执行官方 `vali.py`，时间允许时再重复测量。

## 快速单元测试

以下命令只创建微型合成 NetCDF，不编译或运行 ROMS：

```bash
python -m pytest -q Local_Lab/tests
```

当前 WSL 环境的固定 Python 依赖记录在 `requirements-validation.txt`。脚本还会在
可用内存低于 8 GiB 时拒绝启动真实模型。
