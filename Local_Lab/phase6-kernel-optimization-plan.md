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
- R22 `pre_step3d` 七段，以及 R09 `step2d`、transport/wetdry 和
  advection/rotation 的逐级细分计时。
- contact3d/f2csum 的 plan、pack、MPI、unpack；broadcast；`put_refine3d` 总段。
- rank/node 元数据和按需 Perfetto trace。

仍然缺少：

- R35 最大子段 horizontal advection 内部的 X stencil、Y stencil、flux
  divergence/update 和 nesting flux assembly 拆分。
- R09 当前第一计算子段已细化到第四阶 flux/stencil loops；只有 score 结果使其他
  宽子段成为第一热点且源码审查仍无法区分计算/通信时，才继续拆分。
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

R09 随后通过 sites 199--206 拆成 transport/setup、free surface、pressure gradient、
advection/rotation、viscosity、forcing/coupling、momentum update 和 BC/exchange。
job `118964367` 的 Grid-2 父子覆盖率为 99.62%；最大三个子段分别为
`1.761/1.040/0.666 s`。普通 score build job `118963924` 与 accepted 二进制哈希完全
一致，证明插桩和扩大的 site 存储均已编译掉。下一项先审查 transport/setup 中的
mass-flux 循环、halo 和 volume-conservation 边界，结合 ifort 向量化报告选择单一
计算假设；不得把其中的 MPI 等待误归因于 stencil 算术。

sites 207--212 进一步确认 Grid-2 transport/setup 的 `1.853 s` 中，`wetdry_tile`
占 `1.139 s`（61.5%），mass-flux exchange 占 `0.417 s`，本地 mass-flux 循环仅占
`0.154 s`，子段覆盖 99.39%。因此当前计算目标转为 wet/dry mask kernel；先结合实际
预处理源码与 ifort report 检查重复扫描、连续访问和分支/SIMD，不把 MPI exchange
混入同一模型实验。证据为 job `118965815` 和
`profile_bundle_logs/r09-transport-phases-diagnostic-summary_20260811T174749Z_profile_bundle.json`。

wetdry sites 213--220 最终把 current masks 分成 compute 与 four-array exchange。
job `118967950` 的 Grid-2 current-mask parent 为 `0.706 s`，compute 仅 `0.208 s`，
exchange 为 `0.492 s`，父子覆盖 99.25%。因此 wetdry 主要是通信路径，不是当前最大
计算 kernel；R09 计算优先级回到 advection/rotation（`1.040 s`），其次是 viscosity
（`0.666 s`）。下一模型实验先取得实际 advection loops 的 ifort vectorization report，
只选择一个不改变离散格式或浮点顺序的假设。最终诊断证据为
`profile_bundle_logs/r09-wetdry-compute-exchange-diagnostic-summary_20260811T182131Z_profile_bundle.json`。

R09 advection/rotation sites 221--224 随后拆分 flux/stencil construction、divergence、
Coriolis 和 curvilinear terms。job `118969887` 的 Grid-2 子段分别为
`0.635/0.098/0.148/0.164 s`，父子覆盖 99.26%；flux/stencil 占该父段 60.7%，是下一
计算目标。普通 score build job `118969277` 的 SHA-256 仍与 accepted 二进制逐字节
一致。官方 ifort 2017 对实际预处理源码的 no-IPO report 表明主要内层 `i` 循环已以
vector length 2 向量化，因此第一模型假设应针对 scratch-plane 内存流量或窄范围循环
结构，同时保持第四阶 stencil、系数、表达式顺序和 exact 输出；不得把其他三个子段、
viscosity 或 wetdry MPI 混入。证据为
`profile_bundle_logs/r09-advection-phases-diagnostic-summary_20260811T184250Z_profile_bundle.json`。

首个 R09 flux/stencil 模型实验 commit `818523e` 将 `UFe/VFx` 前的 `Dgrad` 按行生产
并就近消费，不改变任何内层表达式。job `118971429` 的 Grid-2 R09 min/mean/max 从
`5.370619/5.448426/5.641630 s` 降至 `5.280076/5.346913/5.564065 s`，mean 下降
1.86%；Grid-1 R09 也下降 1.42%，26 变量逐位一致。raw total 的 0.73% 改善包含有利
R03/R44 波动，不能全部归功于源码，但 target region 在 ranks 间一致改善，故接受为
新的 exact score reference：
`r09-row-local-dgrad-4n64-16ppn_20260811T190232Z_3600`。累计可信 total 仍远低于 5%，
不得运行完整三天。下一实验仍限制在 site 221 的剩余 scratch-plane 流量，并保持
单一假设。

紧接着的 `UFx` 同行 staging 假设被 job `118972788` 否定：尽管 26 变量仍逐位
一致，Grid-2/Grid-1 R09 分别回退 3.18%/1.45%，raw total 回退 0.85%。该候选未
commit，源码已恢复到 accepted commit `75c60b0`；失败记录保存在
`/tmp/r09-row-local-ufx-failed/`。不得继续机械套用相同的逐行边界条件改写；应先在
accepted 源码上重新取得 diagnostic summary，比较剩余 site 221 与 viscosity 等
子段，再选择下一个假设。

accepted 源码的重排 summary job `118973783` 显示 Grid-2 viscosity/site221/momentum
分别为 `0.666/0.615/0.443 s`；221--224 对 site 202 的覆盖仍为 99.26%，26 变量
逐位一致。diagnostic wall 只用于同 run 排序，不用于声称收益。当前第一 R09 计算
热点因此转为宽 site 203 viscosity；下一步在独立 profiler 分支只拆分其实际启用的
stress construction 与 divergence/update loop families，确认父子覆盖后再选择模型
假设。证据为
`profile_bundle_logs/r09-post-dgrad-diagnostic-summary_20260811T193436Z_profile_bundle.json`。

当前 application header 明确启用 `UV_VIS2`。sites 225--228 将 site 203 拆成 PSI
depth、RHO stress flux、PSI stress flux 和 divergence/update；job `118975018` 的
Grid-2 四段为 `0.053/0.145/0.321/0.146 s`，合计覆盖父段 98.88%，调用次数一致且
26 变量逐位相同。普通 score build job `118974398` 与 accepted score SHA 完全一致。
当前具体第一 loop 是 PSI stress flux。下一模型实验先证明 `Drhs_p` 在 active UV_VIS2
路径中是 PSI-depth loop 到 PSI-stress loop 的单生产者/消费者，再只尝试融合这两个
loop、消除 scratch-plane round trip；RHO stress 和 divergence 保持不动。证据为
`profile_bundle_logs/r09-viscosity-phases-diagnostic-summary_20260811T195009Z_profile_bundle.json`。

`Drhs_p` producer-consumer 融合随后被 job `118976241` 否定：26 变量仍逐位一致，但
Grid-2/Grid-1 R09 分别回退 0.93%/1.90%，raw total 回退 1.20%。候选未 commit，
源码已恢复到 accepted commit `2531734`，失败记录保存在
`/tmp/r09-fuse-drhsp-psi-stress-failed/`。这与 ifort report 对 PSI stress loop 的
“vectorization possible but seems inefficient”及高 load/register cost 一致：不能再
通过融合向该 loop 增加工作。下一模型假设只验证该连续 `i` loop 的 Intel
`VECTOR ALWAYS` 成本模型覆盖，不改变表达式；默认 exact，任何非零误差或 R09 回退
都直接拒绝。

PSI stress 强制向量化假设也不成立。compile-only job `118977272` 证明
`!DIR$ VECTOR ALWAYS` 确实使目标 loop 以 vector length 2 向量化，但 ifort 同时给出
scalar/vector cost `74/80.5` 和预估 speedup `0.91`，即静态成本模型预期更慢。唯一
score DEMO job `118977361` 正常结束且 26 变量逐位一致，但分配到的
`j01r2n[12-15]` 对 R19/R22/R35/R49/R54 等无关 region 也造成 25--114% 的系统性
回退，不能把观测到的 R09 增幅归因于该 directive。由于该 run 没有提供正向证据且
编译器证据明确不利，按单次门禁拒绝、不自动复跑；源码已恢复到 accepted commit
`6abbcb5`，失败记录保存在 `/tmp/r09-force-psi-vector-failed/`。下一步停止机械改写
PSI stress loop，回到 accepted score bundle 重排全局计算热点，再决定需要细化的宽
region。

accepted score bundle 的全局重排随后把 Grid-2 R19 GLS vertical mixing 定为首个
尚未细化的宽计算 region（`5.072 s`；R34 仅 `0.986 s`）。sites 229--238 将 R19
拆成 predictor 三段与 corrector 七段；summary job `118978391` 正常结束、26 变量
逐位一致。补齐必需-site 和 R19 父映射后，用同一批日志离线重算得到 Grid-1/Grid-2
父子覆盖率 `99.87%/99.83%`。Grid-2 第一计算段是 corrector mixing-coefficient
construction `1.907 s`，第二是 production/dissipation `1.351 s`；predictor/corrector
BC-exchange 合计约 `0.951 s`，不得混入下一计算实验。下一步先取得实际预处理后的
coefficient loop ifort 向量化报告，再只选择一个关于重复幂、平方根、除法或 GLS
不变量的可证伪假设。证据为
`profile_bundle_logs/r19-phases-diagnostic-summary_20260811T204510Z_profile_bundle.json`。

R19 coefficient `k -> i` 连续化与 `Akt` loop fission 假设被 job `118980068`
明确否定：26 变量仍逐位一致，但 Grid-1/Grid-2 R19 分别回退 `6.66%/7.35%`，
raw total 回退 `1.18%`。accepted/candidate compile-only jobs `118979004/118979979`
显示，fission 后的 `Akt` 连续写回虽成功向量化，但承载 limiter、stability function、
平方根和除法的主 `i` loop 仍被 general `pow` 与 ifort 保守依赖判断阻止 SIMD；连续
访问收益不足以抵消 loop interchange 和 row scratch 成本。候选未 commit，源码已恢复
到 accepted commit `222d298`，失败记录保存在
`/tmp/r19-coefficient-i-contiguous-failed/`。下一步不得继续为 coefficient 主循环增加
scratch 或强制向量化；若转向第二计算段 production/dissipation，只允许先验证一个
保持原乘法顺序的公共子表达式复用假设。

production/dissipation 的首个窄假设也在 build 阶段被否定：将 Lmy25 wall function
两项中重复的左结合前缀 `gls_power*cmu_fac1*tke_power` 显式缓存后，job
`118980384` 生成的 SHA-256 仍为 accepted
`1522312811585237a7fc3546d88cf5ac2326e72243100a5073557680bebccf37`，证明 Intel
IPO 已完成相同 CSE。该候选没有信息增量，因此未运行 DEMO、未 commit；源码恢复到
`b7508c1`，记录保存在 `/tmp/r19-wall-base-cache-failed/`。后续若继续该子段，应优先
检查 production 中重复的 `Akv-Akv_bak`、`Akt-Akt_bak` 是否同样已被代码生成消除，
仍以候选二进制哈希作为 DEMO 前的低成本证伪门槛。

production 差值复用随后也未达到接受门槛。缓存 `Akv-Akv_bak` 与
`Akt-Akt_bak` 后，build job `118980787` 生成了不同二进制，但 score job
`118981072` 中 Grid-1/Grid-2 R19 仅改善 `0.09%/0.20%`；Grid-2 R09 同时回退
`1.83%`，其绝对代价远大于 R19 节省。raw total 的 `0.12%` 改善伴随有利 R03/R44
波动，不能归因于源码。候选未 commit、未复跑，源码恢复到 `5031759`，记录保存在
`/tmp/r19-production-differences-failed/`。R19 当前已连续排除主循环换序、wall-base
CSE 和 production 差值复用；在没有新的 profiler/编译器证据前停止机械微调，回到
accepted score bundle 重排剩余宽计算 region。

accepted bundle 的再次重排把 Grid-2 R15 CoSiNE biology 定为下一个尚未细分的宽
计算 region（约 `3.406 s`，高于 R27 `2.251 s` 与 R34 `0.986 s`）。sites 239--240
先将其保守拆成局地生化反应与沉降/最终回写两大段。summary job `118981786` 正常
结束、26 变量逐位一致，Grid-1/Grid-2 两段对 R15 的覆盖率分别为
`99.85%/99.82%`。Grid-2 局地生化反应为 `2.689 s`（R15 的 78.7%），沉降/最终
回写为 `0.724 s`（21.2%）。因此下一步只继续细分局地生化反应，优先区分状态提取、
光限制和主 source/sink 方程；不得先凭源码长度修改 sinking，也不得把多个生化公式
改写混入同一实验。证据为 run
`Local_Lab/runs/profile128/r15-biology-phases-diagnostic-summary_20260811T215947Z_63313`
及 bundle
`profile_bundle_logs/r15-biology-phases-diagnostic-summary_20260811T215947Z_profile_bundle.json`。

sites 241--243 继续只细分 R15 的局地反应段。summary job `118982658` 正常结束、
26 变量逐位一致；Grid-2 setup/state、light attenuation、source/sink equations 分别为
`0.417/0.252/2.039 s`，合计覆盖 site 239 的 `99.90%`。Grid-1 覆盖 `99.93%`。
source/sink equations 已占整个 Grid-2 R15 约 59%，但该段仍同时包含单个大点式生化
loop 与其后的 O2/CO2 gas-exchange calls。下一轮只在 loop-nest 边界把这两者分开，
不得在最内层 `i` 循环打计时点。证据为 run
`Local_Lab/runs/profile128/r15-local-reactions-diagnostic-summary_20260811T221600Z_39597`
及 bundle
`profile_bundle_logs/r15-local-reactions-diagnostic-summary_20260811T221600Z_profile_bundle.json`。

sites 244--245 最终在 loop/call 边界把 source/sink 段分成点式 CoSiNE 反应与 O2/CO2
gas exchange。summary job `118983545` 正常结束、26 变量逐位一致；Grid-2 两段分别
为 `1.094/0.951 s`，合计覆盖 site 243 的 `99.91%`。Grid-1 两段为
`0.352/0.234 s`，覆盖同样为 `99.91%`。点式反应 loop 仅略高于 gas exchange，故
下一模型实验先取得实际预处理源码的 ifort report，只选择一个不改变生化方程与浮点
顺序的重复计算/内存假设，并把 gas exchange 作为稳定 guard；两者不得混改。证据为
run `Local_Lab/runs/profile128/r15-source-sink-diagnostic-summary_20260811T222901Z_57614`
及 bundle
`profile_bundle_logs/r15-source-sink-diagnostic-summary_20260811T222901Z_profile_bundle.json`。
