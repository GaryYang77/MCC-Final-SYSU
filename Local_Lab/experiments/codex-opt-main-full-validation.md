# codex/opt-main：4n96/6x16 完整三天 no-profile 全量验证

- 日期：2026-08-13
- 源码 commit：`2236fce`（`codex/opt-main`，含三项已验收 exact R55 优化：
  `drop-cross-zero`、`local-cross-lists`、`scatter-hoist`）
- no-profile 二进制 SHA-256：
  `a67656ea2bf84a0e915da488c184076c31a2bea1a4a47d4216829ba3d38511cc`
- 构建：`Local_Lab/builds/profiling/no_profile_20260812T233649Z_57992`，官方
  Intel 2017.5.239 / HPC-X 2.7.4 / NetCDF 4.4.1，`-DMCC_NO_PROFILE`。
- 配置：4 节点、96 ranks、24 ranks/node、`6x16`、L3-balanced NUMA-row binding。
- Slurm job `119086984`，节点 `j05r2n[04-07]`。

## 结果

- 同 allocation 预检（60/300）：`57.62 s`，慢节点门禁 90 s 通过。
- 完整三天（`2592/12960`）wall：**`2005.86 s`（33:25.86）**。
- 权威基准 job `118852631`（同配置同源码链）：`2205.57 s`（36:45.57）。
- 改善：**`-199.71 s = -9.06%`**。
- `run_report.json`：`passed=true`、`normal_end=true`、`outputs.passed=true`、
  `comparison.passed=true`、mode=exact；26 项 comparison 全部
  `RMSE=0`、`max_abs=0`（相对 4n96 全量参考输出逐位一致）。
- 官方 `vali.py`：SCS 与 Dongsha60 全部 13 变量 `RMSE = 0.000000`，均低于官方
  阈值，最终判定“优化结果无异常”。日志：
  `final-6x16-l3-full-noprofile-20260812T234256Z_20260812T234302Z_60730/vali_official.log`。
- 资源：Elapsed 33:25.86，User time 45436.36 s，max RSS 849 MiB。

## 说明

- 本次全量由团队明确授权（当时 4n64 DEMO 累计约 -3%，未达 5% 常规触发线），
  用于评估三项 exact 计算优化在完整三天上的真实作用并执行官方验证。
- 相对基准的 -9.06% 已超过 AGENTS.md 的 5% 触发线，后续累计候选可在同配置
  确认收益。
- 运行目录：
  `Local_Lab/runs/profile128/final-6x16-l3-full-noprofile-20260812T234256Z_20260812T234302Z_60730`。
