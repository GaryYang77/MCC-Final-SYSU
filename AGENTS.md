# MCC 2026 决赛优化约束

## 目标与环境

- 目标：在结果通过精度验证的前提下，缩短 ROMS-CoSiNE15 完整三天模拟的运行时间。
- 当前公开基准：`01:50:06`。
- 决赛环境：华东一区（昆山），队列 `kshcexclu06`；每队最多 4 节点、每节点 32 核，共 128 CPU 核；不使用 DCU。
- 参考源码：`/public/share/mcc2026_final/mcc2026_source`；本仓库模型源码位于 `ROMS_CoSiNE15/`。

## 修改边界

**禁止修改：**

- 物理计算方案、模型方程及其科学含义。
- 主办方提供的初始场、边界场、强迫场和比赛输入数据。
- 为获得速度而跳过必需计算、缩短最终模拟时长，或放宽/绕过验证。
- `Local_Lab/baselines/mcc_4x20/outputs_valid/` 及其 `manifest.json`。禁止在日常优化中运行 `baseline` 命令；只有基线缺失、源码树干净且团队明确要求时才可重建。

**允许修改：**

- 不改变物理方案的等价实现优化，例如消除可证明的冗余计算、改善循环/内存访问、减少临时量和数据复制。
- MPI 分块、通信、缓存、同步、聚合及负载均衡优化。
- 编译和运行配置优化，但每一种配置都必须单独验证，且不得依赖比赛禁用的硬件。
- 调试时临时缩短 `NTIMES`；不得把缩短配置当作最终结果。

边界不确定时，先停止修改并向团队确认。ROMS 后续版本的改动（例如相关 tickets）只能作为实现参考，移植后仍须走完整门禁，不能因“官方已有”而默认正确。

## 每次优化的固定流程

1. 优化前先定位瓶颈并记录基准；区分计算、MPI 通信/等待和 I/O，避免仅凭直觉改动。
2. 一次只做一个可解释的优化，保留可审查的 diff。
3. 在 Ubuntu WSL 的仓库根目录先运行快速测试：

   ```bash
   python -m pytest -q Local_Lab/tests
   ```

   若当前环境缺少依赖，先在专用 Python 环境中安装
   `Local_Lab/requirements-validation.txt`，不要改动测试来规避环境问题。

4. ROMS 源码、编译选项或运行语义有任何变化后，必须运行本地正确性门禁：

   ```bash
   python Local_Lab/valid_test.py validate
   ```

   等价入口为 `python -m pytest -s Local_Lab/valid_test.py`。不得只运行快速单元测试后就宣称优化有效。
5. 仅在命令退出码为 0 且输出明确显示 `PASS` 时保留候选；查看最新的
   `Local_Lab/runs/validation/*/validation_report.json`，同时记录候选 wall time、相对基线变化和所有误差指标。失败时先回退或修正该项优化，不得提高容差。
6. 本地短任务只用于正确性初筛和粗略性能判断。涉及 MPI、分块、通信或同步的改动还必须先在集群完成一次 128 核缩时调试运行：日志出现正常结束标记、预期输出齐全且关键变量无 NaN/Inf；若已有同配置的未优化缩时输出，还必须比较相同的 13 个变量。该运行只是多 rank 诊断，不是精度验收。之后仍须执行完整任务。性能结论应重复测量，并最终以昆山集群 128 核、完整三天任务为准。

`valid_test.py` 会在 WSL/Linux 中进行干净编译，以 1 个 MPI rank 运行固定 `4/20` 步双向嵌套样例，并对以下两个文件中的 13 个变量进行比较：

- `SCS_avg_0001.nc`、`Dongsha60_avg_0001.nc`
- `temp salt u v zeta NO3 NH4 PO4 diatom microzooplankton detritus oxygen TIC`

本地门禁要求每个变量的 `RMSE <= 1e-5` 且 `max_abs <= 1e-5`，并检查文件、维度、shape、缺失值掩膜及 NaN/Inf。它使用封存的本地基线，不替代主办方最终 `vali.py`。

## 决赛运行与最终验收

- 配置文件：`ROMS_CoSiNE15/ROMS/External/ocean_SCS_Dongsha60_bio15.in`。`NTIMES` 的第一个数对应外层 `SCS` 网格，第二个数对应内层 `Dongsha60` 网格。
- 完整三天：`NTIMES == 2592  12960`。
- 一天调试：`NTIMES == 864  4320`。
- 半天调试：`NTIMES == 432  2160`。
- 缩短时长时两个网格按相同比例调整；最终提交前恢复完整三天配置并复查实际输入文件。
- 以根目录 `sub.sh` 作为提交脚本起点，使用队列 `kshcexclu06`、4 节点和 128 CPU 核。调整 MPI rank 或 `NtileI/NtileJ` 前先理解嵌套网格的进程分配，并用缩时任务实测；不要假设单个网格的 tile 数必然等于总核数。
- 完整三天运行成功并生成最终输出后，在集群执行主办方验证：

  ```bash
  source /public/share/mcc2026_final/miniforge3/etc/profile.d/conda.sh
  conda activate vali
  python /public/share/mcc2026_final/vali.py
  ```

只有“完整任务正常结束 + 官方 `vali.py` 通过”的结果才可作为最终有效成绩。实验记录至少包含 commit/diff、编译器与 flags、节点/rank/分块、输入时长、wall time、重复次数、本地验证报告和官方验证结果。
