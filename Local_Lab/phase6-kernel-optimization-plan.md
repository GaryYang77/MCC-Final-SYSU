# Phase 6：ROMS 计算 kernel 优化计划

## 文档用途

本文档是 Phase 6 的长期决策记录。开始新的 profiler 或模型优化实验前，必须先读
本文档和仓库根目录 `AGENTS.md`。对话上下文被压缩或工程交接时，以这两份文件恢复
目标、边界和下一步，不凭记忆继续实验。

本文档记录 2026-08-11 团队与软件所专家讨论后的方向。它不是对赛题边界的放宽：
任何优化仍不得改变物理方案、离散格式、时间积分方案、网格、时间步长、积分时长、
输入数据、生态变量或双向嵌套关系。

## Phase 5 冻结基点

- 当前仓库 HEAD（制定本计划时）：`55b7a9097e2877df670a0ad20cfecdf05d71e7af`。
- 当前累计模型源码锚点：`1ba85ab2149598702c6011e12940612a0a21119c`。
- 完整任务：4 节点、96 ranks、24 ranks/node、`6x16`、L3-balanced
  NUMA-row binding、外层/内层 `2592/12960` 步。
- job `118852631`，完整 no-profile wall `2205.57 s`（`36:45.57`）。
- 二进制 SHA-256：
  `1152299ea019b653a4007bca10490c01bb9c0ce8af90c87835eec0167a11a410`。
- 26 项内部 comparison 均为 `RMSE=0`、`max_abs=0`，官方 `vali.py` PASS。
- 证据：`Local_Lab/experiments/assemblef1d-full-validation.md`。
- 团队审核本计划后，拟在上述 HEAD 创建 annotated tag
  `mcc-phase5-validated-2205s`；创建前不得把该 tag 当作已经存在。

## 为什么转向计算 kernel

Phase 5 最大收益来自 MPI、嵌套和装配路径，尤其是 `assemblef1d` 原地归约。不过当前
源码并非没有计算优化：已经在 tracer corrector/predictor、GLS、`t3dmix4`、biology、
`step2d` 中完成过缓存、幂特化、mask 快路径和数组布局优化。Phase 6 的变化是把这些
零散工作提升为主线，使优化与 ROMS 的时间积分、输运 stencil、垂向隐式求解等核心
计算结构直接对应。

每轮只处理当前第一实测热点：细化一个热点，优化一个可证伪假设，重新 profiling，
再决定下一个热点。不得为了“覆盖所有 kernel”一次性给所有函数加细粒度计时或同时
改写多个循环。

## 当前数值算法及不可跨越的边界

当前配置是 split-explicit ROMS：

- `step2d` 是快速二维正压模态，采用 Leap-Frog predictor 与 Adams-Moulton
  corrector；第一步使用 Forward/Backward Euler。
- 三维慢模态包含 Adams-Bashforth 历史项。
- 垂向黏性与扩散采用 Crank-Nicolson/隐式三对角求解。
- `step3d_uv` 完成三维动量更新，并隐式处理垂向黏性。
- `step3d_t` 完成 tracer corrector；当前启用 `TS_U3ADV_SPLIT`，包含高阶水平
  stencil、垂向输运和隐式垂向扩散。
- 两层网格保持双向嵌套。

可以优化固定算法的实现：不变量外提、除法/幂/metric 缓存、循环融合或拆分、临时量
消除、连续内存访问、SIMD、三对角系数复用、pack/unpack、通信与计算重叠。不得更换
上述积分方法、stencil 阶数或系数，不得改变方程、时间步长或求解含义。若一个改动
究竟属于“浮点等价实现”还是“计算方案改变”无法证明，停止并请团队/专家判断。

## 当前 profiler 能力与缺口

profiler-v2 的 score、summary、trace 三层结构可以继续使用；`PROFILE_DIAGNOSTIC`
在 no-profile 二进制中完全编译掉。

已经具备：

- R35 `step3d_t/tracer_corrector` 的 setup、horizontal advection、vertical
  advection、vertical diffusion、final update 五段计时。
- contact3d/f2csum 的 plan、pack、MPI、unpack；broadcast；`put_refine3d` 总段。
- rank/node 元数据和按需 Perfetto trace。

仍然缺少：

- R35 最大子段 horizontal advection 内部的 X stencil、Y stencil、flux
  divergence/update 和 nesting flux assembly 拆分。
- R22 `pre_step3d` 内的 AB 历史项、tracer predictor、垂向隐式系数/solve、
  forcing/mask 拆分。
- R09 `step2d` 的 predictor/corrector、zeta、ubar/vbar、advection、pressure、
  Coriolis、viscosity 拆分。
- R34 `step3d_uv` 的垂向黏性系数、forward elimination、back substitution、
  barotropic correction、BC/halo 拆分。
- halo2d/3d/4d 的 site 名称虽已在 Python 分析器注册，但模型源码尚无相应
  pack/wait/unpack 调用点，当前不能据此报告真实耗时。

## 热点路线

初始顺序只用于决定第一轮诊断，后续必须按新 profile 重排：

1. R35 `step3d_t`，先细化并优化水平 tracer advection。
2. R22 `pre_step3d` 三维 predictor。
3. R09 `step2d` 二维 predictor/corrector。
4. R34 `step3d_uv` 三维动量 corrector。
5. R19 GLS vertical mixing。
6. halo pack/wait/unpack；只有实测为热点时继续通信改写。

每次只给当前目标增加诊断点。计时点放在阶段或 loop nest 边界，不放入最内层网格点
循环。要求子阶段调用次数符合控制流，累计时间能解释父 region 的绝大部分，并单独
测量 observer effect。profiler 改版和模型优化不得位于同一实验分支。

## Kernel 审查清单

修改前必须回答并写入实验记录：

- 当前最热的具体 loop nest 是什么，在哪个 grid/rank 上占比最高？
- `i` 是否为连续内层访问，ifort 是否向量化，失败/低效原因是什么？
- 除法、指数、幂、`pm*pn`、`1/Hz`、输运系数是否被重复计算？
- 某个量是否对 tracer、垂向层、行或时间步不变，能否安全缓存？
- 多个循环能否融合；融合是否增加寄存器压力、破坏 SIMD 或改变浮点顺序？
- 临时数组是否必须完整写回，是否可以缩小生命周期或复用已存在平面？
- stencil 是否重复加载相同邻点，边界与 mask fallback 是否完整？
- 三对角矩阵系数是否能在相同 `Akt` 的 tracer 间复用？
- pack/unpack 是否重复扫描、复制或进行非连续访问？

源代码运算数减少不等于性能提升。此前 R35 循环融合曾回退约 10--13%，因此计算
候选必须同时检查 ifort vectorization report、目标 region 和稳定 guard regions。

## 数值正确性：两条通道

### Exact-equivalence

候选输出逐位一致。这仍是首选通道，适合不改变浮点顺序的缓存、冗余加载消除和通信
缓冲区优化。它证明最强、日常反馈也最快，但不再是所有候选的唯一准入方式。

### Numerically-equivalent

允许由浮点结合顺序、SIMD/FMA、倒数复用或 reduction 顺序造成非零差异，但必须：

- 保持文件、变量、维度、shape、mask、有限值和输出时刻完整一致。
- 使用官方 `vali.py` 的“文件 × 变量”RMSE 阈值，不得统一伪装成 `1e-5`。
- 继续记录 max_abs、RMSE/阈值比和剩余余量，供风险判断与专家评审；max_abs 不冒充
  官方硬判据。
- DEMO、独立 validate 和生产配置性能证据均通过。
- 除已经启动且接近完成的生产检查外，后续候选只有在同配置、可比的 DEMO 中，
  相对 accepted reference 的可信总时间至少下降 **5%**，才运行完整三天；低于 5%
  只做 DEMO 和触发式 validate。5% 必须排除 I/O、broadcast、文件系统、慢节点和
  异常 MPI 环境噪声，不能以局部 region 降幅替代总时间降幅。达到阈值后，在合入
  accepted `main` 前仍必须使用同源码 no-profile 二进制通过官方 `vali.py`。
- 不得通过修改官方脚本、阈值、变量集合、参考数据或 comparison 逻辑挽救候选。

内部 comparison 已实现显式 `exact`/`numerical` 模式，默认保持 `exact`。numerical
使用锁定的官方逐文件、逐变量 RMSE 阈值；单元测试直接解析仓库中的官方 `vali.py`
并验证阈值表一致，同时覆盖文件差异、max_abs 仅报告和 NaN/Inf 硬失败。任何官方阈值
变化必须作为独立 infra 变更重新审核，不得修改官方 `vali.py` 本体。

官方阈值是合格边界，不是应主动消耗的误差预算。报告必须展示精度余量；接近阈值的
候选即使 PASS，也必须由团队明确决定是否接受。

## 实验节奏

- 4n64/`8x8`、60/300 score DEMO 保留为低延迟热点发现和日常筛选配置。
- 最终生产配置是 4n96/`6x16`/L3-balanced；短作业受节点差异影响，生产确认需在
  同一 allocation 预检慢节点。
- exact 候选可沿现有日常门禁累计；只有阶段累计 DEMO 达到可信总时间下降 5%，
  才用同源码 4n96 生产配置确认累计收益。
- numerical 候选仍只优化一个假设；低于 5% 时只保留在实验分支，不把多个未经
  全量验证的误差候选连续叠加。达到 5% 后，完整三天和官方验证仍是合入
  accepted `main` 的门禁。
- score PROFILE 用于因果归因，no-profile 才是成绩。diagnostic wall 不用于声称收益。

## Phase 6 第一项工作

1. 团队审核并提交本计划及 `AGENTS.md` 更新，创建 Phase 5 annotated tag。
2. 使用已验收的 exact/numerical comparison；未显式声明时始终走 exact。
3. 在独立 profiler 分支细化 R35 horizontal tracer advection；验收后冻结 profiler。
4. 获取 ifort 对实际 R35 热循环的向量化报告。
5. 基于计时和向量化证据选择一个计算改写，走单假设模型优化流程。

第一轮 C4 X/Y 中心项代数化简已在实验分支 `perf/r35-c4-xy-stencil` 留档：DEMO
Grid-2 R35 仅下降 0.22%，完整 no-profile 仅下降约 0.49%，而完整任务
`Dongsha60/u` 已使用 89.4% 的官方 RMSE 阈值。候选虽通过官方验证，仍因收益/精度
余量比不合理而拒绝合入；accepted exact 源码继续保持在 `bb50230`。

随后 profiler 将 R35 tracer-flux assembly 拆成 setup/pack/MPI/unpack，并据此完成
首个有效计算优化：commit `8e4fc92` 用直接连续循环替换 pack/unpack 的 `RESHAPE`
临时量。Grid-2 pack/unpack 分别下降 28.2%/25.6%，assembly 下降 11.3%，R35
下降 3.84%，score DEMO 总时间下降 0.77%，26 变量逐位一致。该 commit 已成为新的
accepted exact reference；由于总时间不足 5%，按预算规则不运行完整三天。

R22 随后通过 sites 192--198 拆成 tracer setup、horizontal、vertical advection、
vertical diffusion、U/V momentum 和 BC/exchange；job `118958689` 的 Grid-2 父子覆盖
率为 99.96%。horizontal/vertical advection/vertical diffusion 分别为
`2.273/1.407/1.352 s`。C4 direct-flux 候选虽使 R22 下降 2.60%，但 raw total 与稳定
GLS guard 同时回退，按预声明门禁拒绝。commit `952677f` 复用已存在的 predictor
`cffpmnp`，消除 vertical update 中按 tracer/level 重算 `cff*pm*pn`；job `118961520`
的 R22 下降 0.94%，26 变量逐位一致，稳定 compute guards 支持改善方向。raw total
的 0.62% 回退完全被控制 Grid 上 R03/R44 的已知波动覆盖，因此按单次门禁接受、不
自动复跑；新的筛选 reference 是
`r22-vertical-time-metric-4n64-16ppn_20260811T164844Z_21545`。累计可信收益仍不足 5%，
不得运行完整三天。
