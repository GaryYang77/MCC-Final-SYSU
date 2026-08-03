# MCC 2026 决赛优化约束

## 目标与环境

- 目标：在结果通过精度验证的前提下，缩短 ROMS-CoSiNE15 完整三天模拟的运行时间。
- 当前公开基准：`01:50:06`。
- 决赛环境：华东一区（昆山），队列 `kshcexclu06`；每队最多 4 节点、每节点 32 核，共 128 CPU 核；不使用 DCU。
- 主办方决赛根目录：`/public/share/mcc2026_final/`。本仓库模型源码位于 `ROMS_CoSiNE15/`。

## 决赛服务器访问

- 从 WSL 仓库环境连接登录节点：

  ```bash
  ssh -i ~/.ssh/fangxihong_key -p 65023 fangxihong@cancon.hpccube.com
  ```

- 已确认该连接可登录到账号的 `/public/home/fangxihong`。默认只做读操作探查；上传源码、修改远程文件、提交/取消作业或运行官方验证前，先确认当前实验目标和作业范围。
- 连接后必须通过 Slurm 向 `kshcexclu06` 申请计算节点；不要用登录节点的 `lscpu` 结果代替计算节点实测配置。
- 服务器门禁工作区：`/public/home/fangxihong/MCC-Final-SYSU`。本地代码通过 `Local_Lab/sync_to_cluster.sh` 同步；服务器的基线、runs、builds 和日志不得被本地同步覆盖。

### 已打通的服务器门禁状态

- 2026-08-03 已在 `kshcexclu06` 计算节点生成服务器原生基线：Slurm job `118468694`，状态 `COMPLETED`。
- 随后使用全新构建独立验证：Slurm job `118469268`，状态 `COMPLETED`；两个输出文件的 13 个变量均为 `RMSE == 0`、`max_abs == 0`，最终日志显示 `PASS`。
- 封存基线位于服务器的 `Local_Lab/baselines/mcc_4x20/`。日常调优只能运行 `validate`，不得重新运行 `baseline`；脚本会拒绝覆盖已有基线。
- 已复测源码同步：远端基线、历史运行、构建和 Slurm 日志均会保留，不会被本地文件覆盖或删除。

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
3. 在 Ubuntu WSL 的仓库根目录先运行代码级快速测试：

   ```bash
   python -m pytest -q Local_Lab/tests
   ```

   若当前环境缺少依赖，先在专用 Python 环境中安装
   `Local_Lab/requirements-validation.txt`，不要改动测试来规避环境问题。

4. 本地只用于编辑、查看和快速测试。ROMS 源码、编译选项或运行语义有任何变化后，同步到服务器并在 Slurm 计算节点运行正确性门禁：

   ```bash
   bash Local_Lab/sync_to_cluster.sh
   ssh -i ~/.ssh/fangxihong_key -p 65023 fangxihong@cancon.hpccube.com
   cd /public/home/fangxihong/MCC-Final-SYSU
   bash Local_Lab/run_cluster_gate.sh validate
   ```

   不得只运行本地单元测试或在登录节点直接运行模型后就宣称优化有效。
5. 仅在三个条件同时满足时保留候选：包装命令退出码为 0、终端日志明确显示 `[validate] PASS`、最新 `validation_report.json` 中 `passed` 为 `true`。同时记录候选 wall time、相对基线变化和所有误差指标。失败时先回退或修正该项优化，不得提高容差、修改比较变量或重建基线来规避失败。
6. 服务器 1-rank、`4/20` 步 demo 是严格正确性门禁，不是 128 核性能结论。涉及 MPI、分块、通信或同步的改动，还必须先在集群完成一次 128 核缩时调试运行：日志出现正常结束标记、预期输出齐全且关键变量无 NaN/Inf；若已有同配置的未优化缩时输出，还必须比较相同的 13 个变量。该运行只是多 rank 诊断，不替代完整任务和官方验收。
7. 性能结论必须在昆山集群重复测量，最终以 128 核、完整三天任务为准。完整任务正常结束后再运行主办方 `vali.py`；demo `PASS` 不能表述为最终官方验证通过。

`valid_test.py` 在服务器 Slurm 计算节点上使用官方 Intel 2017.5.239、HPC-X 2.7.4 和 NetCDF 4.4.1 环境进行干净编译，以 1 个 MPI rank 运行固定 `4/20` 步双向嵌套样例，并对以下两个文件中的 13 个变量进行比较：

- `SCS_avg_0001.nc`、`Dongsha60_avg_0001.nc`
- `temp salt u v zeta NO3 NH4 PO4 diatom microzooplankton detritus oxygen TIC`

服务器 demo 门禁要求每个变量的 `RMSE <= 1e-5` 且 `max_abs <= 1e-5`，并检查文件、维度、shape、缺失值掩膜及 NaN/Inf。它使用在官方服务器上重新生成和封存的基线，不使用 WSL 基线，也不替代主办方完整三天 `vali.py`。

## 服务器 demo 门禁的执行管线

```text
WSL 本地源码
  -> sync_to_cluster.sh
     -> rsync 到服务器工作区，并保护基线、运行记录、构建和日志
     -> finalize_cluster_sync.sh 检查输入、建立软链接、记录源码快照
  -> SSH 登录服务器工作区
  -> run_cluster_gate.sh validate
     -> sbatch --wait 提交 cluster_gate.sbatch
  -> kshcexclu06 计算节点
     -> 加载 Intel、MPI、NetCDF/HDF5 和 vali Python 环境
     -> valid_test.py validate
        -> 校验封存基线完整性和工具链类型
        -> 创建独立构建目录并干净编译
        -> 生成 1-rank、4/20 步 demo 输入
        -> mpirun 运行 ROMS-CoSiNE15
        -> 检查正常结束、输出文件和 NaN/Inf
        -> 比较 2 个 NetCDF 文件中的 13 个变量
        -> 写 validation_report.json 并输出 PASS/FAIL
  -> run_cluster_gate.sh 打印 Slurm 日志并原样返回作业退出码
```

各脚本各自只承担一个主要职责：

| 文件 | 运行位置 | 职责 |
| --- | --- | --- |
| `Local_Lab/sync_to_cluster.sh` | WSL | 把本地源码同步到固定服务器工作区；排除输入大文件、本地生成物以及远端基线、runs、builds 和日志。 |
| `Local_Lab/finalize_cluster_sync.sh` | 服务器登录节点 | 检查共享输入，建立 `ROMS_CoSiNE15/Inputfiles` 软链接，并保存与本地提交/diff 对应的远端源码快照；不运行模型。 |
| `Local_Lab/run_cluster_gate.sh` | 服务器登录节点 | 只允许 `baseline` 或 `validate`，提交并等待 Slurm 作业，汇总 stdout/stderr，并把 Slurm 状态转换成调用者可见的退出码；日常只用 `validate`。 |
| `Local_Lab/cluster_gate.sbatch` | Slurm 计算节点 | 声明队列、节点、CPU、内存和时限，加载官方编译/运行环境，然后调用 `valid_test.py`。 |
| `Local_Lab/valid_test.py` | Slurm 计算节点 | 真正执行编译、demo 运行、输出检查、数值比较和 JSON 报告生成，是正确性门禁核心。 |

### 日常最短操作

在 WSL 仓库根目录运行：

```bash
python -m pytest -q Local_Lab/tests
bash Local_Lab/sync_to_cluster.sh
ssh -i ~/.ssh/fangxihong_key -p 65023 fangxihong@cancon.hpccube.com
```

登录服务器后运行：

```bash
cd /public/home/fangxihong/MCC-Final-SYSU
bash Local_Lab/run_cluster_gate.sh validate
```

无需手动查找 job ID 才能判断结果：包装脚本会等待 Slurm 作业结束，并把完整 stdout 和必要的 stderr 打到当前终端。自动化调用仍必须检查该命令的退出码。

### 结果与故障定位

- Slurm 包装日志：`Local_Lab/cluster_logs/mcc-demo-gate_<jobid>.out` 和 `.err`。
- 每次验证的完整产物：`Local_Lab/runs/validation/candidate_*/`。
- `build.log`：编译器、依赖或链接错误。
- `model.log`：MPI 启动、ROMS 运行错误和正常结束标记。
- `resource.log`：作业资源使用情况。
- `validation_report.json`：基线完整性、工具链、两个文件的逐变量误差及最终 `passed` 状态。
- 同步或输入链接失败先看同步脚本输出；编译失败看 `build.log`；模型异常看 `model.log` 和 `.err`；数值失败看 `validation_report.json`。不得通过放宽阈值或重建基线处理数值失败。

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
