# R55 fine2coarse3d: hoist k-invariant scatter tests and vectorize level loop

- 分支：`perf/r55-f2c3d-scatter-hoist`（从 `codex/opt-main` 分叉）
- 日期：2026-08-13
- 正确性通道：exact（逐位一致）

## 假设

scatter 循环对每个 receiver 点、每个垂向层重复计算 k 不变的 `Fine3dCount(m)>0`、
cross 分支的 `my_count` 掩码求和及 `Cmsk(Ic,Jc)` 乘法与分支判断。

假设：把 owner/count 判定与 cross 掩码求和提出 k 循环，并让 k 层循环变成纯算术
（owner 分支保留逐层除法、cross 分支保留同样的 25 点求和顺序），每个
`C(Ic,Jc,k)` 元素值与运算顺序不变，因此输出逐位一致。

## 证据

- diagnostic summary `r55-f2c3d-diagnostic-summary_20260812T191105Z_17625`：
  scatter 段（site 252 - 253..256）= 约 0.40 s。
- `Fine3dCrossMask(ib,cross_m)` 与 `Fine3dCount(m)`、`Cmsk(Ic,Jc)` 均与 k 无关。

## 预期

- Grid-2 R55 / fine2coarse3d 下降（主要来自 scatter 分支与冗余掩码求和减少、
  k 层循环可向量化）。
- 调用次数不变；26 变量 comparison 保持全零。

## 验收

单次 4n64 60/300 score DEMO，reference 为
`r27-second-harmonic-all-wet-4n64-16ppn_20260812T002302Z_53023`。
任一 comparison 非零或 R55 回退则拒绝并恢复。

## 结果（2026-08-13）

- 4n64 score DEMO `r55-scatter-hoist-4n64-16ppn_20260812T203518Z_52131`：
  exact，26 变量全零。Grid-2 R55 = 3.2578 s（较 H2 运行 3.4031 s 再 -4.3%），
  R39 = 7.2102 s，raw total 64.7844 s。接受并合并 `codex/opt-main`
  （307fa38）。该运行即当前累计堆栈的 4n64 样本。
