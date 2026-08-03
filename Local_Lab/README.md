# MCC 本地正确性门禁

这套流程用于在本机修改 ROMS-CoSiNE15 源码后，固定执行：

```text
干净编译 BYE24BIO15
  -> 单 MPI 进程运行 4/20 步双向嵌套案例
  -> 比较 SCS 与 Dongsha60 平均场
  -> 精度通过后记录运行时间
```

## 固定配置

配置从官方 `ROMS/External/ocean_SCS_Dongsha60_bio15.in` 每次自动生成，
不会修改原文件。相对官方配置只改变以下运行参数：

```text
NtileI  == 1  1
NtileJ  == 1  1
NTIMES  == 4  20
NAVG    == 4  20
NDEFAVG == 4  20
```

- `NtileI/NtileJ` 改成 `1/1`，与本地 `mpirun -np 1` 对应。
- `NTIMES=4/20` 让两个网格都模拟 400 秒。
- 只缩短 `NAVG/NDEFAVG`，以便在 4/20 步结束时生成验证所需的平均场。
- `DT`、物理/生态参数、初始场、边界场、强迫场均保持不变。
- `NRST/NHIS/NDEFHIS` 保持官方值，demo 不写无关的 restart/history 大文件。

## 基准

已经封存的基准位于：

```text
Local_Lab/baselines/mcc_4x20/
├── manifest.json
├── ocean_4x20.in
└── outputs_valid/
    ├── SCS_avg_0001.nc
    └── Dongsha60_avg_0001.nc
```

`manifest.json` 记录源码 commit、源码是否干净、输入和二进制 hash、运行参数、
墙钟时间、峰值内存，以及两份基准 NetCDF 的 SHA-256。验证前会重新计算 hash；
基准被移动、删除或改写时，测试会直接失败。

NetCDF 文件体积较大且被 `.gitignore` 排除，不会上传 Git。请另外备份
`outputs_valid/`；`manifest.json` 和 `ocean_4x20.in` 可以提交。

基准创建命令只用于基准不存在且 ROMS 源码树完全干净时：

```bash
python Local_Lab/valid_test.py baseline
```

如果基准目录已经存在，命令会拒绝覆盖。

## 每次优化后的固定测试

在 Ubuntu WSL 中，从仓库根目录执行：

```bash
cd /mnt/e/GaryYang77/MCC-Final-SYSU
python -m pytest -s Local_Lab/valid_test.py
```

也可以使用等价的 CLI：

```bash
python Local_Lab/valid_test.py validate
```

流程会创建全新的 build/run 目录，强制单任务干净编译当前源码，然后运行候选模型。
候选输出不会覆盖基准。

比较对象与主办方 `vali.py` 一致，为两个 `*_avg_0001.nc` 中的 13 个变量：

```text
temp salt u v zeta NO3 NH4 PO4 diatom microzooplankton
detritus oxygen TIC
```

每个变量同时要求：

```text
RMSE    <= 1e-5
max_abs <= 1e-5
```

任一文件/变量缺失、维度或 shape 不同、缺失值掩膜不同、出现 NaN/Inf，或任一误差
超限，pytest 都会失败。详细结果保存在最新候选目录的
`validation_report.json`。

报告中的性能字段包括：

```text
baseline_model_wall_seconds
candidate_model_wall_seconds
saved_seconds
speedup_percent
candidate_build_seconds
candidate_model_cpu_seconds
candidate_max_rss_kib
```

`saved_seconds > 0` 才表示候选运行更快。编译时间单独记录，不计入模型加速。
4/20 步任务中初始化和 Windows 挂载盘 I/O 占比很高，单次墙钟波动只能用于初筛；
确认性能改进时应重复运行，并最终在昆山集群的完整三天任务上计时、执行官方 `vali.py`。

## 快速单元测试

以下命令只创建微型合成 NetCDF，不编译或运行 ROMS：

```bash
python -m pytest -q Local_Lab/tests
```

当前 WSL 环境的固定 Python 依赖记录在 `requirements-validation.txt`。脚本还会在
可用内存低于 8 GiB 时拒绝启动真实模型。
