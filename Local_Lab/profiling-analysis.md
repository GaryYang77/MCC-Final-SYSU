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

注意：上述是缩时诊断，不是完整三天性能结论。完整任务仍需重复测量并执行官方
`vali.py`。

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

先通过服务器 demo 门禁得到当前源码的干净二进制，然后做 128-rank 缩时 profiling：

```bash
bash Local_Lab/run_cluster_gate.sh validate

source /public/share/mcc2026_final/miniforge3/etc/profile.d/conda.sh
conda activate vali
python Local_Lab/profile_128.py \
  --binary Local_Lab/runs/validation/candidate_<timestamp>/bin/oceanM \
  --label nesting-profile \
  --outer-steps 432 --inner-steps 2160 \
  --tiles-i 8 --tiles-j 16
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

## 下一轮优化顺序

1. 沿 Grid 1 region 53 进入 `ngetD` 与 region 49 point gather，区分调用频率、payload 和等待。
2. 沿 Grid 2 region 55 进入 `n2way/fine2coarse` 与 region 46 data gather。
3. 对照 `#861` 检查两个网格的 vertical weights 是否存在可证明的重复计算。
4. 用半天或一天输入重复 3 次，确认上述排序、最慢 rank 和 imbalance 稳定。
5. 对照 `#747` 在昆山节点实测 gather/assemble 的 collective 方案，不凭实现直觉替换。
6. 每个候选依次通过 1-rank 门禁、128-rank 缩时诊断、完整三天运行和官方 `vali.py`。
