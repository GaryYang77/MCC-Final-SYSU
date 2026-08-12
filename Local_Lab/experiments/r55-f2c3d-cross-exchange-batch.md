# R55 fine2coarse3d: batch tracer cross exchange into one wait

- 分支：`perf/r55-cross-exchange-batch`（从 `codex/opt-main` 分叉）
- 日期：2026-08-13
- 正确性通道：exact（逐位一致）

## 假设

diagnostic site 258 显示 cross 交换 93% 是 MPI 等待（1.675 s），且 per-call
wait 约 1.5 ms。10 个 tracer 共享同一 cell 路由，但当前每个 tracer 单独
pack→exchange→wait→scatter，12 次串行同步。

假设：把 10 个 tracer 的 crossing-block 打包与消息全部先投递，再用一次
`MPI_Waitall` 完成，随后逐 tracer 做 f2csum 与 scatter。每变量的消息内容与
scatter 算术完全不变，因此输出逐位一致。

## 实现

- `mod_nesting.F`：新增 `Fine3dCross4(:,:,:,:)`（每 tracer 一个 crossing 缓冲）。
- `distribute.F`：新增 `mp_assemble_cross_batch`（复用同一 cached route plan，
  nvars 组 pack + 全部 irecv/isend + 单次 waitall + 逐变量 unpack）。
- `nesting.F`：新增 `fine2coarse3d_batch`（rho contact 快路径）；`fine2coarse`
  在 `NtileI*NtileJ==numthreads` 且两层 N 相同时走批量路径，否则回退原逐变量循环。

## 预期

- Grid-2 R55（fine2coarse3d）下降，主要来自 cross 交换等待减少。
- 调用次数变化符合设计；26 变量 comparison 保持全零。

## 验收

单次 4n64 60/300 score DEMO，reference 为
`r27-second-harmonic-all-wet-4n64-16ppn_20260812T002302Z_53023`。
任一 comparison 非零、R55 回退或 total 显著回退则拒绝并恢复。
