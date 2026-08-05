# ROMS-CoSiNE15 profiling 分析与使用方案

## 结论

原版 ROMS profiler **包含 I/O 计时**：region 3 覆盖输入读取与分发，
region 8 覆盖输出文件定义、写入、同步和关闭；region 40--50 还覆盖多类 MPI
通信。因此它能做单 rank 的初步热点筛选，但不足以直接指导 128 rank 决赛优化。

原实现的主要问题是：

- 所谓 `Elapsed CPU time` 来自 `CPU_TIME`，不是 MPI 作业真正的 elapsed wall time；
- 只输出跨 rank 累加值，看不到 min/mean/max、最慢 rank 和负载不均；
- 没有调用次数，无法区分“少量昂贵调用”和“海量微小调用”；
- region 39 已命名为 multiple-grid nesting，却没有在 `nesting.F` 中启停；
- 输出主要面向人工阅读，难以稳定生成对比报告；
- region 可以嵌套，旧日志没有明确说明百分比不能相加为 100%。

本分支已经把 profiler 改造成面向 128 rank 的低开销证据链。默认只采集 wall
clock；需要研究 CPU/wait 差异时可额外定义 `PROFILE_CPU`，但不应把高开销双时钟
模式用于常规性能测量。

## #735 对本方案的作用

ROMS 官方 ticket [`#735`](https://www.myroms.org/projects/src/ticket/735) 的方向对本版本很有价值：先补齐 nesting/通信的可观测性，
再做算法或 collective 优化。本次没有整文件移植新版 ROMS，而是按当前 2017 源码接口
做了最小改动：启用已有的 nesting region 39，并保留 region 40--50 的 MPI 细分。

`#735` 解决的是“在哪里计时”的一部分问题；决赛分析还需要本分支补充的真实 wall
clock、rank 统计、调用次数、机器可读输出、合法 128-rank 运行器和同节点 overhead
对照。两者结合后，才足以判断热点究竟是计算、I/O、MPI 本身还是 rank 等待。

## 输出语义

每个 `PROFILE_RANK` 记录包含：

- `grid/model/region/kind`：网格、模型、区域编号和 `compute/io_read/io_write/mpi` 分类；
- `calls`：所有 ranks 的总调用次数；
- `wall_min/mean/max`：各 rank 的区域 wall time 统计；
- `wall_max_rank`：最慢 rank；
- `imbalance = wall_max / wall_mean`；
- `cpu_min/mean/max`：仅在编译时定义 `PROFILE_CPU` 时有效，否则为 0。

Nesting 另有互斥子阶段：region 51 `nzwgt/z_weights`、52 mask weights、53
`ngetD` donor extraction、54 `nputD` receiver interpolation、55 `n2way`
fine-to-coarse coupling、56 其余 section。region 39 是这些阶段的 inclusive 总计；JSON
中的 `nesting_coverage` 会检查 51--56 的调用数之和是否与 region 39 完全一致，并给出
子阶段 wall time 对 nesting 总时间的覆盖率。

统计只在模型结束时做 MPI reduction，不在热点路径中增加 collective。region 39、MPI
区域和许多计算区域可能互相嵌套，所以 JSON 报告明确标记为 `inclusive`；分类占比和
hotspot 占比不能相加来构造 100% 的互斥时间线。

## 已得到的 128-rank 线索

在 4 节点、128 ranks、`NtileI=8`、`NtileJ=16`、12/60 步诊断中：

| 网格 | 主要信号 | inclusive wall 占比 |
| --- | --- | ---: |
| Grid 1 | MPI point-data gathering，region 49 | 32.47% |
| Grid 1 | MPI broadcast，region 44 | 7.75% |
| Grid 1 | 输入 / 输出 I/O，region 3 / 8 | 3.84% / 3.79% |
| Grid 2 | MPI data gathering，region 46 | 21.30% |
| Grid 2 | tracer corrector，region 35 | 15.67% |
| Grid 2 | 输入 / 输出 I/O，region 3 / 8 | 0.61% / 1.78% |

这说明首轮计算优化不应从 NetCDF 写出开始。优先调查 nesting 中由 region 49/46
代表的 contact-point gather、数据布局、调用频率和 rank 不均；region 39 的新增整体
计时用于确认这些通信在完整 nesting 路径中的权重。I/O 仍需保留观察，但目前是第二
优先级。

注意：上述是缩时诊断，不是完整三天性能结论。只有团队选出的最终累计候选才至少运行
一次完整任务并执行官方 `vali.py`；时间允许时再重复测量。

最终 wall-only 候选的 60/300 步运行进一步直接量出了 region 39：Grid 1 nesting
为 34.07 s / 242.01 s（14.08%），Grid 2 为 114.89 s / 242.03 s（47.47%）。
同一次运行中 Grid 1 region 49 为 35.25%，Grid 2 region 46 为 26.60%。这些数字是
inclusive 的：MPI gather 发生在 nesting 内部，不能与 region 39 相加。它们把下一轮
目标进一步收敛到 Grid 2 nesting 路径和 Grid 1 point-data gathering。

加入 51--56 子阶段后的最终 128-rank 运行 `118494857` 给出了更具体的 nesting
分解：

| 网格 | Nesting 子阶段 | 占 region 39 wall time |
| --- | --- | ---: |
| Grid 1 | `ngetD` donor extraction，region 53 | 83.77% |
| Grid 1 | vertical weights，region 51 | 15.65% |
| Grid 2 | `n2way` fine-to-coarse coupling，region 55 | 58.12% |
| Grid 2 | vertical weights，region 51 | 31.40% |
| Grid 2 | remaining sections，region 56 | 5.78% |
| Grid 2 | `nputD` receiver interpolation，region 54 | 4.69% |

Grid 1/2 的子阶段调用覆盖率分别为 99.9996% 和 99.9967%，调用数均与 region 39
完全一致。由此可见，后续不应笼统地“优化 nesting”：Grid 1 应先进入 `ngetD` 及其
point gather 路径，Grid 2 应先进入 `n2way/fine2coarse` 及 data gather 路径；vertical
weights 是两个网格共同的第二候选。

## 使用方法

先通过服务器 4/20 正确性 demo 得到当前源码的干净候选二进制，然后在 commit 前只运行
一次 2 节点、64-rank、`8x8`、60/300 步 profiling demo，并通过 `--reference-run` 与
上一个 accepted 的同配置 run 做数值 comparison。这一份 run 同时给出正确性、总 wall、
热点和 rank 离散。两层短 demo 都通过且性能方向有效后才 commit；普通 commit 不要求
完整三天或官方 `vali.py`。

日常候选的单次 profiling 命令如下；必须显式提供上一个 accepted 的 2 节点同配置
reference：

```bash
bash Local_Lab/run_cluster_gate.sh validate

source /public/share/mcc2026_final/miniforge3/etc/profile.d/conda.sh
conda activate vali
python Local_Lab/profile_128.py \
  --binary Local_Lab/runs/validation/candidate_<timestamp>/bin/oceanM \
  --label <hypothesis>-2n64 \
  --outer-steps 60 --inner-steps 300 \
  --nodes 2 --ranks 64 --tiles-i 8 --tiles-j 8 \
  --reference-run Local_Lab/runs/profile128/<accepted-2n64-reference-run>
```

运行目录会生成：

- `model.log`、`resource.log` 和 Slurm stdout/stderr；
- `profile_report.json`：分类、可读 region 名、hotspots 和 per-call 代价；
- `profile_records.csv`：所有 region 记录及可读 `region_name`；
- `run_report.json`：二进制哈希、配置、资源摘要、正常结束和 NaN/Inf 检查；有 reference
  时还包含每个变量两侧的 min/mean/max、有效/掩膜点数、RMSE 和 max_abs；
- `profile_bundle.json`：把 run、profile、comparison 和可选 overhead 合并成一个本地可视化输入。

将 `profile_bundle.json` 下载到本地，用浏览器打开
`Local_Lab/profile_dashboard.html` 并拖入文件。页面完全离线；热点类型、nesting 分解、
rank 离散和变量物理量范围都在同一页展示。Overhead 配对 bundle 会在顶层携带 on/off
comparison，不再需要到 off 目录寻找 RMSE/max_abs。旧报告仍可载入，但不会伪造当时
没有采集的变量范围。

决赛的 128 ranks 要求每个网格满足 `NtileI*NtileJ == 128`。原输入中的 `4*8`
只对应 32 ranks，不能直接用于 128-rank 任务；运行器会拒绝这种非法配置。

## 完整三天的 1/2/4 节点 Scaling Sweep

完整 scaling 使用同一个已通过门禁的 PROFILE 二进制，保持官方
`NTIMES=2592/12960` 以及原始 `NRST/NHIS/NAVG` 输出节奏，依次运行：

| 节点 | MPI ranks | `NtileI x NtileJ` |
| ---: | ---: | ---: |
| 1 | 32 | `4 x 8` |
| 2 | 64 | `8 x 8` |
| 4 | 128 | `8 x 16` |

在服务器登录节点执行（脚本只负责提交 Slurm 作业，不在登录节点运行模型）：

```bash
bash Local_Lab/start_full_profile_scaling_sweep.sh \
  Local_Lab/runs/validation/candidate_<timestamp>/bin/oceanM \
  full-3day-scaling \
  12:00:00
```

启动器在 `vali` 环境下用 `nohup` 运行，打印后台 PID 和日志路径，SSH 断开后继续工作。
三个 Slurm allocation 严格顺序执行；某个 case 失败时仍会继续后续节点数，以保留一晚
能取得的诊断信息。每个 case 的时限默认为 12 小时。

结果位于：

```text
Local_Lab/runs/profile_scaling/full-3day-scaling_<timestamp>_<pid>/
  sweep_report.json
  bundles/
    1node-32ranks_profile_bundle.json
    2nodes-64ranks_profile_bundle.json
    4nodes-128ranks_profile_bundle.json
```

`sweep_report.json` 记录各 case 的 job ID、实际 wall time、run 目录、comparison 和 bundle。
第一个成功 case 作为后续 case 的数值 reference。当前自动 comparison 延续 2 个
`*_avg_0001.nc`、13 个变量的门禁合同；它不是完整官方验收。只有当这次 4 节点结果被
选为最终累计候选时，才需要单独运行主办方 `vali.py`。

1/2/4 节点是不同 Slurm allocation，适合看强扩展趋势，但节点硬件状态和排队时间会带来
噪声。64 ranks 的 `8x8` 是本 sweep 固定的中间分块；若它表现异常，应另测 `4x16`，
不要把节点数效应与 tile 形状效应混为一谈。

### 2026-08-03 完整 sweep 结果（优化前基线）

| 配置 | Job | Wall | 结果 |
| --- | ---: | ---: | --- |
| 1 节点 / 32 ranks / `4x8` | `118500755` | 23.16 s | FAIL：首次 nesting 通信触发 `MPI_Bcast/MPI_ERR_TRUNCATE` |
| 2 节点 / 64 ranks / `8x8` | `118500776` | 10588 s | PASS |
| 4 节点 / 128 ranks / `8x16` | `118507345` | 9589 s | PASS；官方 `vali.py` 通过 |

1 节点失败发生在两个网格初始化和第 0 步 history 写出之后、首次 nesting 通信期间，
不是 OOM，也不能当作有效性能点。2 到 4 节点只从约 2:56:28 缩短到 2:39:49，新增一倍
ranks 仅节省约 15.7 分钟，说明当前强扩展已经明显受 nesting/MPI 路径限制。

### 2026-08-04/05 优化后完整三天结果

累计 6 项渐进优化（#861 vertical weights、mask reuse、distributed fine2coarse、
sparse Allgatherv、Scatterv input tiles、owner-aware fsum）后的完整三天结果：

| 配置 | Job | Wall | vs 优化前 | 官方 vali.py |
| --- | ---: | ---: | ---: | --- |
| 2 节点 / 64 ranks / `8x8` | `—` | 6226 s | -41.2% | 全部 RMSE=0 ✅ |
| 4 节点 / 128 ranks / `8x16` | `118566851` | 6452 s | -32.7% | 全部 RMSE=0 ✅ |
| **4 节点 / 64 ranks / 16ppn / `8x8`** | **`118585284`** | **4657 s（1.29h）** | **—** | **全部 RMSE=0 ✅** |

4nodes-64ranks-16ppn 是当前最快配置：每节点仅 16 ranks，内存带宽充裕、节点内 MPI
争用低，相比 4node-128rank（6452s）快 27.8%，相比 2node-64rank（6226s）快 25.2%。
**日常 DEMO profiling 已切换为此配置**。最终提交仍使用 4 节点 128 ranks。

### 优化后 DEMO 与完整任务热点对比（4nodes-64ranks-16ppn）

首个 4nodes-64ranks-16ppn DEMO：job `118597954`，Slurm wall **122.0 s**，PASS。
相比旧 2nodes-64ranks 优化后 DEMO（162.99s）快 **25.1%**，验证了新配置的优势。

| 信号 | DEMO (122s) | 完整三天 (4657s) |
| --- | ---: | ---: |
| Grid 1 total wall | 119.2s | 4657.3s |
| Grid 1 region 49 point gather / total | 27.0% | 28.2% |
| Grid 1 region 39 nesting / total | 11.9% | 12.6% |
| Grid 1 region 53 ngetD / nesting | 99.3% | 99.5% |
| Grid 2 region 39 nesting / total | 19.8% | 21.6% |
| Grid 2 region 55 n2way / nesting | 70.8% | 71.0% |
| Grid 2 region 35 tracer corrector / total | 17.2% | 17.9% |
| Grid 2 region 49 point gather / total | 13.6% | 14.8% |

热点排序及占比高度一致，因此日常优化使用固定 4 节点、64 ranks、16ppn、`8x8`、60/300 步
profiling 足以筛选方向。它仍不能证明最终加速：候选必须保持相同配置与 reference
comparison；只有团队选出的最终累计版本才进入完整三天和官方验证。

## 测量 profiler 自身开销

先构建只关闭 instrumentation 的控制二进制：

```bash
bash Local_Lab/run_build_no_profile.sh
```

再在**同一个 Slurm allocation** 中顺序运行 on/off，避免不同节点组造成的巨大假差异：

```bash
python Local_Lab/profile_overhead.py \
  --profile-binary <validated-profile-binary> \
  --control-binary <no-profile-binary> \
  --label overhead \
  --order off-on \
  --outer-steps 60 --inner-steps 300
```

双时钟原型的一次同节点配对结果为 261.83 s 对 248.56 s，即 `+5.34%`。这促使默认
模式改为 wall-only。最终 nesting 子阶段版本在同一节点组 `j01r2n[16-19]` 上完成了
顺序互换的两组测量：`off-on` 为 241.75/235.97 s（`-2.39%`），`on-off` 为
241.80/231.89 s（`+4.27%`）。两组 on/off 比值的几何平均为 `+0.89%`。符号随顺序
翻转说明短任务的缓存/运行次序噪声约为数个百分点，因此不应把单次 overhead 当成
精确常数。结论是默认 wall-only 的中心开销低于 1%，适合热点排序；最终成绩计时仍
使用 no-profile 二进制。

## 验证记录

| 内容 | Job / 结果 |
| --- | --- |
| wall/CPU 分离版本 1-rank 门禁 | `118479557`，PASS，26 组指标全零误差 |
| rank 统计版本 1-rank 门禁 | `118481626`，PASS |
| I/O/MPI 分类版本 1-rank 门禁 | `118483703`，PASS |
| 128-rank 报告工具 | `118484908`，正常结束、26 个变量有限值 |
| 默认开关控制门禁 | `118485448`，PASS |
| 双时钟同节点 overhead | `118489077`，PASS，输出逐位一致，`+5.34%` |
| wall-only + nesting region 39 最终门禁 | `118489720`，PASS，26 组指标全零误差 |
| wall-only 同节点 overhead（on-off） | `118490435`，PASS，输出逐位一致，`+3.62%` |
| wall-only 同节点 overhead（off-on） | `118492122`，PASS，输出逐位一致，`-2.55%` |
| wall-only 顺序平衡中心估计 | 两组配对比值几何平均，约 `+0.48%` |
| nesting 51--56 初始门禁 | `118493091`，PASS，26 组指标全零误差 |
| nesting 51--56 最终门禁 | `118493856`，PASS，26 组指标全零误差 |
| nesting 子阶段 128-rank 诊断 / overhead（off-on） | `118494857`，PASS，输出逐位一致，调用覆盖率大于 99.996%，`-2.39%` |
| nesting 子阶段 overhead（on-off） | `118495221`，作业及两个模型进程均正常退出，`+4.27%`；远程额度中断后未生成配对汇总 JSON |
| nesting 子阶段顺序平衡中心估计 | 同一节点组两组比值的几何平均，约 `+0.89%` |
| 完整 2 节点 profiling | `118500776`，10588 s，PASS |
| 完整 4 节点 profiling | `118507345`，9589 s，PASS，官方 `vali.py` 通过 |
| 优化后完整 4 节点 128-rank | `118566851`，6452 s，PASS，官方 `vali.py` 全部 RMSE=0 |
| **优化后完整 4 节点 64-rank 16ppn** | **`118585284`，4657 s，PASS，官方 `vali.py` 全部 RMSE=0** |

## 下一轮优化顺序（基于 4nodes-64ranks-16ppn 完整三天热点）

以下热点排序来自优化后的 4nodes-64ranks-16ppn 完整三天数据（`4nodes-64ranks-16ppn_optimized_20260805T014345Z_profile_bundle.json`）。注意 region 可嵌套，百分比不能相加为 100%。

### P0 —— 必定有收益的方向

1. **Grid 1 r49 `mpi_point_data_gathering`（1311s，28.2%）**：当前最大单项。`270e69a`
   已将 Allreduce 改为 Allgatherv，但仍占近三成时间。方向：分析 contact 稀疏性和
   owner 分布，评估非阻塞 MPI 重叠通信与计算；对照 ROMS `#747` 实测 gather/assemble
   替代方案。

2. **Grid 2 r55 `nesting_two_way_coupling`（711s，71.0% of nesting）**：`0cc1920`
   混合方案已将 region 46 消除、r55 从 2826s 降到 1888s（128-rank），现在进一步
   降到 711s（64-rank 16ppn）。方向：检查 fine-grid block sum 的循环向量化、减少
   临时数组分配、评估 non-blocking MPI 在 n2way 中的可行性。

3. **Grid 2 r35 `tracer_corrector`（835s，17.9%）**：**纯计算热点**，在低争用
   配置下暴露出来。方向：循环合并/展开、缓存优化、检查冗余的水平/垂直 advection
   计算；编译器 flags 微调需单独实验。

### P1 —— 收益中等或依赖前置改动的方向

4. **Grid 2 r49 `mpi_point_data_gathering`（690s，14.8%）**：与 Grid 1 r49 同类
   问题但规模较小。Grid 1 r49 的改进方案可能直接复用。

5. **Grid 1 r53 `nesting_get_donor_data`（586s，99.5% of Grid 1 nesting）**：
   已从 1154s（优化前 128-rank）显著下降。需区分内部的计算 vs 通信占比。

### P2 —— 计算热点，值得关注但不紧急

6. **Grid 2 r19 `gls_vertical_mixing`（361s，7.7%）** 和 **Grid 2 r22
   `3d_equations_predictor`（360s，7.7%）**：纯计算。方向：向量化、循环融合、
   减少临时量。

7. **Grid 2 r42 `mpi_4d_halo_exchange`（270s，5.8%）**：imbalance=1.14，
   rank 分布不均值得排查。

### 工作约定

- 每个普通 commit 必须先通过本地测试、1-rank 正确性 demo 和一次 4 节点、64-rank、
  16ppn、60/300 步 profiling demo。
- 对未提交候选只跑一次 profiling；接近噪声时由团队决定是否复测，不自动增加作业。
- 只有团队选出的最终累计候选才运行完整三天和官方 `vali.py`。
