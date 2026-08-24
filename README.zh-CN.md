# ROMS-CoSiNE LuTeam-HPC-Optimized

[English README](README.md)

ROMS-CoSiNE LuTeam-HPC-Optimized 是一个面向 ROMS-CoSiNE15 的高性能实现，源于 MCC 2026 海洋计算挑战赛作品。它保持原有科学方程和数值方案，同时优化 MPI 通信、双向嵌套、内存访问和计算 kernel。

## 主要特点

- 优化分布式内存 MPI 执行
- 加速双向嵌套及 fine-to-coarse 数据传递
- 改进示踪物、动量、混合、干湿处理和生态 kernel
- 减少临时数组、冗余计算和内存访问开销

ROMS-CoSiNE LuTeam-HPC-Optimized 可用于评估现有 ROMS-CoSiNE 应用的性能。实际表现会随案例、CPP 选项、编译器、MPI 实现、硬件和网格分块变化，因此最有价值的测试是在自己的工作负载上进行对比。

## 环境要求

- Linux 或兼容的 HPC 环境
- 支持 MPI 的 Fortran 编译器；参考构建使用 Intel `ifort`
- 使用兼容工具链构建的 MPI、NetCDF C/Fortran 库
- GNU Make、C 预处理器和 Perl
- 使用可选 NetCDF 比较工具时需要 Python 3.10 或更高版本

其他编译器配置位于 `ROMS_CoSiNE15/Compilers/`。

下列命令均从仓库根目录执行。

## 编译

仓库内应用为 `BYE24BIO15`。使用 Intel MPI 和 `nf-config` 的典型构建命令为：

```bash
make -C ROMS_CoSiNE15 clean
make -C ROMS_CoSiNE15 -j 8 \
  FORT=ifort USE_NETCDF4=on NF_CONFIG=nf-config
```

默认可执行文件为 `ROMS_CoSiNE15/oceanM`。

## SCS-Dongsha60 示例

仓库已包含运行配置：

```text
ROMS_CoSiNE15/ROMS/External/ocean_SCS_Dongsha60_bio15.in
```

配套 NetCDF 数据集包含 SCS 外层网格、Dongsha60 内层网格、初始场、边界场、大气和潮汐强迫、生物地球化学场以及双向嵌套 contact 文件。由于数据量较大，数据集单独分发。请联系 **yanggy25@mail2.sysu.edu.cn** 获取。

将数据放在：

```text
ROMS_CoSiNE15/Inputfiles/
├── SCS/
└── Dongsha60/
```

交付的数据包遵循上述目录结构，`.in` 文件列出了所需输入路径。仓库内配置使用 `4x8 = 32` ranks 分块。下列示例保持原文件不变，并创建一个使用 `6x16 = 96` MPI ranks 的运行副本：

```bash
cp ROMS_CoSiNE15/ROMS/External/ocean_SCS_Dongsha60_bio15.in \
  ROMS_CoSiNE15/ocean.luteam.in
sed -Ei \
  -e 's/^([[:space:]]*NtileI[[:space:]]*==).*/\1 6  6/' \
  -e 's/^([[:space:]]*NtileJ[[:space:]]*==).*/\1 16  16/' \
  ROMS_CoSiNE15/ocean.luteam.in
mkdir -p ROMS_CoSiNE15/output
(
  cd ROMS_CoSiNE15
  mpirun -np 96 ./oceanM ocean.luteam.in \
    > roms.log 2>&1
)
```

每个分布式内存网格的分块都必须与 MPI ranks 数量一致：

```text
NtileI(ng) * NtileJ(ng) == MPI ranks
```

改变 ranks 数量时，请同步调整两个嵌套网格的 `NtileI` 和 `NtileJ`。如果集群要求使用 `srun` 等启动器，请相应替换 `mpirun`。

## 在自己的案例上评估 ROMS-CoSiNE LuTeam-HPC-Optimized

1. 使用相同编译器、精度、CPP 选项和依赖库构建现有 ROMS-CoSiNE 与 ROMS-CoSiNE LuTeam-HPC-Optimized。
2. 使用相同输入、MPI ranks、分块、节点、绑核和输出频率运行两个实现。
3. 比较两组 NetCDF 输出的数值一致性。
4. 对包含配置 I/O 的完整模型命令计时，每个实现至少完成三次运行并比较 wall-clock 时间中位数。

安装比较工具依赖：

```bash
python -m pip install -r requirements.txt
```

比较一对或多对同名 NetCDF 文件：

```bash
python tools/compare_netcdf.py \
  runs/baseline/output runs/luteam-optimized/output \
  --file SCS_avg_0001.nc \
  --file Dongsha60_avg_0001.nc \
  --json comparison.json
```

第一个目录是 reference，第二个是 candidate。工具会检查文件结构、dimensions、shape、dtype、mask、NaN/Inf 和数值变量，并报告数值与 mask 是否完全一致、RMSE、最大绝对误差、有效与掩膜元素数量及统计信息。报告提供对比指标，科学容差应根据具体应用确定。

## 仓库结构

```text
ROMS_CoSiNE15/          ROMS-CoSiNE 源码和应用配置
tools/                  可选输出分析工具
tests/                  公开工具测试
LICENSE                 SYSU MCC Team 修改部分的许可证
THIRD_PARTY_NOTICES.md  上游许可、署名和引用信息
```

## 项目历史

MCC 验证快照位于 [`mcc-compute-improved-validated-2005s`](https://github.com/GaryYang77/MCC-Final-SYSU/tree/mcc-compute-improved-validated-2005s)、[`mcc-compute-improved-validated-2147s`](https://github.com/GaryYang77/MCC-Final-SYSU/tree/mcc-compute-improved-validated-2147s) 和 [`mcc-phase5-validated-2205s`](https://github.com/GaryYang77/MCC-Final-SYSU/tree/mcc-phase5-validated-2205s)。

## 许可与署名

SYSU MCC Team 的修改采用 MIT License，见 [LICENSE](LICENSE)。仓库内第三方组件继续遵循各自的版权与许可条款，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

关于示例数据或 ROMS-CoSiNE LuTeam-HPC-Optimized 的问题，请联系 **yanggy25@mail2.sysu.edu.cn**。
