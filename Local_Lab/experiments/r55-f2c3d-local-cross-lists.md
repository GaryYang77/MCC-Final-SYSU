# R55 fine2coarse3d: cached rank-local cross-cell lists

- 分支：`perf/r55-f2c3d-local-cross-lists`（从 `codex/opt-main` 分叉）
- 日期：2026-08-13
- 正确性通道：exact（逐位一致）

## 假设

`fine2coarse3d` 每个变量都重新扫描全部 contact points（约 17026 个），对每个
cross block 的 25 个单元逐层做 tile 边界判断，但每 rank 只拥有其中约 1/64 的单元
（diagnostic site 255 = 0.8054 s，写命中率极低）。

假设：按 4 种 3D gtype（p/r/u/v 的 Istr/Iend、Jstr/Jend 组合）一次性缓存本 rank
拥有的 `(ii,jj,ib,block)` 单元列表，逐变量 fill 只遍历本地单元并沿 k 连续读 A。
每个单元仍只写一次且值不变，因此输出逐位一致。

## 证据

- diagnostic summary `r55-f2c3d-diagnostic-summary_20260812T191105Z_17625`：
  cross-fill（site 255）= 0.8054 s，调用 72960 次。
- 单元归属与 `F2CcellOwner`/`F2Ccross` 一样在运行期间固定，可缓存。

## 预期

- 目标 region：Grid-2 R55 / fine2coarse3d 的 fill 部分显著下降，总 region 应下降。
- 调用次数不变；26 变量 comparison 保持全零；MPI 路由（`F2CcellOwner`）不修改。

## 验收

单次 4n64 60/300 score DEMO，reference 为
`r27-second-harmonic-all-wet-4n64-16ppn_20260812T002302Z_53023`。
任一 comparison 非零或 R55 回退则拒绝并恢复。

## 结果（2026-08-13）

- 4n64 score DEMO `r55-local-cross-lists-4n64-16ppn_20260812T195421Z_26646`：
  exact，26 变量全零。Grid-2 R55 = 3.4031 s（-34.1% vs 5.1633 s），
  R39 = 7.3530 s（-19.8% vs 9.1690 s），R49 = 2.8118 s。接受并合并
  `codex/opt-main`（d69e52c）。
