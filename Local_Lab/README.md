# MCC ROMS-CoSiNE 优化手册与本地正确性门禁

这份文档用于在每次调优前快速恢复项目上下文，并规定修改、计时、验证和提交的固定流程。比赛规则与不可修改边界以 [`../AGENTS.md`](../AGENTS.md) 为准。

最终目标是在不改变物理计算方案、初始场、边界场和强迫场，并通过主办方精度验证的前提下，缩短完整三天双向嵌套模拟的运行时间。

## 每次开始调优前先检查

```text
确认 Git 状态和当前分支
  -> 确认 MPI ranks 与两个网格的 NtileI*NtileJ 一致
  -> 写下本次唯一的优化假设
  -> 记录未优化基准 wall time
  -> 修改、干净编译
  -> 本地 4/20 步正确性门禁
  -> 集群缩时、多 rank 性能验证
  -> 重复计时并提交单一优化
  -> 完整三天运行和官方 vali.py
```

不要同时修改算法、编译参数和 MPI 分块，否则即使变快，也无法判断收益来自哪里。

## Git 安全基线与实验分支

优化前的安全基线提交为：

```text
77a4a4c chore: establish optimization validation baseline
```

该提交没有修改 `ROMS_CoSiNE15/` 源码。原始代码已经由 Git 保存，不需要额外复制一个源码目录。开始一项优化前，从干净的 `main` 创建独立分支：

```bash
git status --short
git switch -c perf/profile-nesting
```

一个分支只验证一个主要假设，例如：

```text
perf/profile-nesting       只增加或细化计时
perf/ticket-861-vweights   只优化垂向权重/冗余插值
perf/ticket-747-assemble   只比较接触点集合通信
perf/tiling-128            只比较 MPI 分块和绑核
```

提交前检查源码差异和验证结果：

```bash
git diff --stat
git diff -- ROMS_CoSiNE15
python -m pytest -q Local_Lab/tests
python Local_Lab/valid_test.py validate
git add <本次实际修改的文件>
git commit -m "perf(nesting): reuse vertical interpolation weights"
```

不要使用 `git add .` 把日志、输出或无关修改一起提交。失败实验也不要直接覆盖基线分支；先保留测量记录，再决定修正或放弃该实验。

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

本地门禁会自动生成 `1*1` 分块并使用一个 MPI rank，不受上述 128 核配置影响。

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

本项目已经启用 ROMS 的 `PROFILE`，正常结束时会在模型日志尾部输出各计算区域耗时。现有本地 1-rank、4/20 步基线只能说明代码确实执行了 2D 模式、GLS、三维预测/校正、tracer 混合和 biology 等区域，不能代表 128 核通信瓶颈。

当前老版本 profiler 还有两个重要盲区：

- `mod_strings.F` 虽然定义了 `Multiple-grid nesting processing`，但当前 `nesting.F` 没有完整的对应计时包围。
- `mp_assemble` 等操作被归入较粗的通信区域，难以分辨接触点汇聚、完整场聚合和等待分别占多少。

因此第一个源码实验宜先细分以下计时区域：

```text
ngetD
nputD
nzwgt / z_weights
n2way
mp_assemble
mp_aggregate2d / mp_aggregate3d
MPI barrier 或 collective 等待
```

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
- 同一配置至少 3 次，优先比较中位数；缓存和共享文件系统会造成单次波动。

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
正确性：本地 validation_report.json、集群缩时检查、官方 vali.py
结论：保留、继续调查或放弃，以及原因
```

固定闭环：

```text
定位瓶颈
  -> 一次只实现一个优化
  -> 干净编译
  -> 本地 4/20 步门禁
  -> 集群半天/一天多 rank 调试
  -> 重复性能测量
  -> 单独 commit
  -> 完整三天运行
  -> 官方 vali.py
```

本地短任务适合发现结果错误，不适合直接决定比赛排名；MPI、分块、通信或同步优化必须以昆山集群多 rank 结果为准。

## 本地正确性门禁概览

这套流程用于在本机修改 ROMS-CoSiNE15 源码后，固定执行：

```text
干净编译 BYE24BIO15
  -> 单 MPI 进程运行 4/20 步双向嵌套案例
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

- `NtileI/NtileJ` 改成 `1/1`，与本地 `mpirun -np 1` 对应。
- `NTIMES=4/20` 让两个网格都模拟 400 秒。
- 只缩短 `NAVG/NDEFAVG`，以便在 4/20 步结束时生成验证所需的平均场。
- `DT`、物理/生态参数、初始场、边界场、强迫场均保持不变。
- `NRST/NHIS/NDEFHIS` 保持官方值，demo 不写无关的 restart/history 大文件。

## 基准

已经封存的基准位于：

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

NetCDF 文件体积较大且被 `.gitignore` 排除，不会上传 Git。请另外备份
`outputs_valid/`；`manifest.json` 和 `ocean_4x20.in` 可以提交。

基准创建命令只用于基准不存在且 ROMS 源码树完全干净时：

```bash
python Local_Lab/valid_test.py baseline
```

如果基准目录已经存在，命令会拒绝覆盖。

## 每次优化后的固定测试

在 Ubuntu WSL 中，从仓库根目录执行：

```bash
cd /mnt/e/GaryYang77/MCC-Final-SYSU
python -m pytest -s Local_Lab/valid_test.py
```

也可以使用等价的 CLI：

```bash
python Local_Lab/valid_test.py validate
```

流程会创建全新的 build/run 目录，强制单任务干净编译当前源码，然后运行候选模型。
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
超限，pytest 都会失败。详细结果保存在最新候选目录的
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
4/20 步任务中初始化和 Windows 挂载盘 I/O 占比很高，单次墙钟波动只能用于初筛；
确认性能改进时应重复运行，并最终在昆山集群的完整三天任务上计时、执行官方 `vali.py`。

## 快速单元测试

以下命令只创建微型合成 NetCDF，不编译或运行 ROMS：

```bash
python -m pytest -q Local_Lab/tests
```

当前 WSL 环境的固定 Python 依赖记录在 `requirements-validation.txt`。脚本还会在
可用内存低于 8 GiB 时拒绝启动真实模型。
