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

## 调试进展（2026-08-13，暂停于分区 drain）

- 4n64 上批量路径 blowup；1-rank validate（无 cross blocks）通过；batch 禁用的
  控制版 4n64 exact 通过——问题限定在多 rank 批量路径。
- 逐变量全局校验和（`F2CDBG`，cr=2、外层步 1-8、17 个 tracer、owned/cross 拆分）：
  - 顺序路径：owned/cross 均正确。
  - 批量路径：owned 数值与顺序路径一致（correct），cross 数值 ≈ 每个
    (point,k) 约 17.36——与 v 无关，接近每块湿单元计数 my_count；第 2 外层步
    起全部 NaN（粗网格 contact 点被污染后经 put_refine3d 传回细网格边界）。
  - 结论：Fine3dCross4 内容疑似被“计数/掩膜量级”的数据污染，而算术转写经
    逐字符比对与顺序路径完全一致；f2csum/owned 路径正确。
- 待验证假设（需要队列恢复后一次 diagnostic/checksum 周期）：
  1) 掩膜 exchange（mp_assemblef_2d 的 mp_sparse_exchange）与批量 cross
     exchange 的 tag/消息匹配是否串扰；2) 4D section 在 ifort 下的实际
    LBOUND 语义与 v 维对齐；3) per-v-wait 与 single-wait 两版均已失败，
    说明不是并发投递本身，而是填充/交换/散射的 4D 数据流。
- 分区 kshcexclu06 的 96 节点已全部 drain，无法继续集群验证。

## 追加观察（2026-08-13，第二周期）

- cross 校验和 ≈ 每个 (point,k) 恒定 ~17.36（≈每块湿单元计数 my_count），大 tracer
  （13/14/15）略有抬升但远小于真值——更接近“计数量级的常数污染”，而非
  “正确值+常数偏移”。
- 静态复核结论：fill/scatter/plan-build 与已验收代码逐字符一致；counts 用
  MPI_ALLREDUCE（无 tag），掩膜 exchange 与 cross exchange 路由相同但串行
  waitall 完成；4D section 形参与实参维度、LBOUND 语义均与已验证的 3D 模式
  一致。根因仍未找到，需队列恢复后一次数据流诊断（在 exchange 前后打印
  Fine3dCross4 的 checksum）才能定案。
- 队列 kshcexclu06 持续 96 节点 drain，无法运行任何作业。

## 定案诊断（2026-08-13）

- `F2CFILL`（exchange 前，rank 拥有的 fill 单元校验和）：随 tracer 大幅变化
  （v=1: 6.25e6、v=14: 9.63e8、v=15: 1.04e9）——**fill 与 4D 数组关联正确**。
- `F2CXCH`（exchange 后，receiver block 全 25 单元校验和）：v=1..17 几乎恒定
  ~2.54e7（≈ 17.4/单元，即湿单元计数量级），大 tracer 略有抬升——**批量交换
  的接收数据被污染，与 fill 无关**。
- 结论：bug 在 `mp_assemble_cross_batch` 的消息投递/匹配/解包（per-v-wait 与
  single-wait 两版均失败）。下一步应在该例程内打印 Asend/Arecv 前几个元素与
  tag/nsend/nrecv，对比发送与接收端。
