# R55 fine2coarse3d: drop redundant Fine3dCross zeroing

- 分支：`perf/r55-f2c3d-drop-cross-zero`（从 `codex/opt-main` 分叉）
- 日期：2026-08-13
- 正确性通道：exact（逐位一致）

## 假设

`fine2coarse3d` 每个变量（每 rank、每 contact region）先对
`Fine3dCross(1:BlockLen,1:Klen,1:Ncross)` 做全量清零，再只填充本 rank tile
内的单元，最后经 `mp_assemble`（CellOwner 路由）交换。exchange 的 unpack 会对
receiver block 的每个单元写入来源 rank 的值，并对无 owner 的单元显式写 0；因此
交换前的全量清零值在 fast path（`NtileI*NtileJ == numthreads`）与 else path 均
不会被读到，属于纯冗余写。

假设：删除该行不改变任何读取值，输出逐位一致，且 R55（fine2coarse3d）墙钟下降。

## 证据

- diagnostic summary `r55-f2c3d-diagnostic-summary_20260812T191105Z_17625`：
  Grid-2 fine2coarse3d（site 252）= 4.2437 s，其中 zero/counts（site 253）
  = 0.8713 s；f2csum（sites 111-115）全程仅 0.0791 s。
- 代码路径：`mp_assemblef_3d` 的 CellOwner 分支在 unpack 阶段对
  `source < 0` 的单元执行 `A(zero_i,:,zero_m)=0.0_r8`，其余 receiver 单元全部
  由 `Arecv` 覆盖；非 receiver rank 的 `Fine3dCross` 副本只经 owned-cell pack
  读取（填充值），从不读取未填充单元。
- 内存流量：每变量每 rank 清零约 `BlockLen*Klen*Ncross*8` 字节（contact 文件
  `Npoints=10213/6813`，`refine_factor=5`，两 contact region 均 refinement），
  12 个 3D 变量 × 60 外层步重复执行。

## 预期

- 目标 region：Grid-2 R55 two-way coupling 及子段 fine2coarse3d 下降，
  主要来自 site 253 的 zero 部分（约 0.8 s）。
- 调用次数不变；26 变量 comparison 保持全零。
- 不改动任何算术、浮点顺序、mask 语义或通信路由。

## 验收

单次 4n64 60/300 score DEMO，reference 为
`r27-second-harmonic-all-wet-4n64-16ppn_20260812T002302Z_53023`。
若 comparison 出现非零或 R55 回退则拒绝并恢复。
