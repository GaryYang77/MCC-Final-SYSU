# ROMS-CoSiNE LuTeam-HPC-Optimized

[中文说明](README.zh-CN.md)

ROMS-CoSiNE LuTeam-HPC-Optimized is a high-performance implementation of ROMS-CoSiNE15, developed from an entry to the 2026 Marine Computing Challenge (MCC). It preserves the original scientific equations and numerical schemes while optimizing MPI communication, two-way nesting, memory access, and computational kernels.

## Highlights

- Optimized distributed-memory MPI execution
- Faster two-way nesting and fine-to-coarse data movement
- Improved tracer, momentum, mixing, wet/dry, and biology kernels
- Reduced temporary-array, redundant-computation, and memory-access overhead

ROMS-CoSiNE LuTeam-HPC-Optimized is designed to be evaluated with existing ROMS-CoSiNE applications. Performance varies with the case, CPP options, compiler, MPI implementation, hardware, and grid decomposition, so the most useful benchmark is your own workload.

## Requirements

- Linux or a compatible HPC environment
- An MPI-enabled Fortran compiler; the reference build uses Intel `ifort`
- MPI and NetCDF C/Fortran libraries built with a compatible toolchain
- GNU Make, a C preprocessor, and Perl
- Python 3.10 or newer for the optional NetCDF comparison tool

Compiler configurations are available under `ROMS_CoSiNE15/Compilers/`.

Run the following commands from the repository root.

## Build

The included application is `BYE24BIO15`. A typical Intel MPI build using `nf-config` is:

```bash
make -C ROMS_CoSiNE15 clean
make -C ROMS_CoSiNE15 -j 8 \
  FORT=ifort USE_NETCDF4=on NF_CONFIG=nf-config
```

The executable is written to `ROMS_CoSiNE15/oceanM` by default.

## SCS-Dongsha60 example

The repository includes the runtime configuration:

```text
ROMS_CoSiNE15/ROMS/External/ocean_SCS_Dongsha60_bio15.in
```

The accompanying NetCDF dataset contains the SCS outer grid, the Dongsha60 inner grid, initial and boundary conditions, atmospheric and tidal forcing, biogeochemical fields, and the two-way nesting contact file. The dataset is distributed separately because of its size. Contact **yanggy25@mail2.sysu.edu.cn** to request it.

Place the dataset under:

```text
ROMS_CoSiNE15/Inputfiles/
├── SCS/
└── Dongsha60/
```

The delivered package follows this layout, and the `.in` file lists the expected input paths. The checked-in configuration uses a `4x8 = 32` rank decomposition. The following example keeps that file unchanged and creates a runtime copy configured for `6x16 = 96` MPI ranks:

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

For each distributed-memory grid, the decomposition must match the MPI rank count:

```text
NtileI(ng) * NtileJ(ng) == MPI ranks
```

When changing the number of ranks, update `NtileI` and `NtileJ` for both nested grids. Replace `mpirun` with the launcher required by your cluster, such as `srun`.

## Evaluate ROMS-CoSiNE LuTeam-HPC-Optimized on your own case

1. Build your existing ROMS-CoSiNE and ROMS-CoSiNE LuTeam-HPC-Optimized with the same compiler, precision, CPP options, and libraries.
2. Run both implementations with the same inputs, MPI ranks, tiling, node allocation, affinity, and output schedule.
3. Compare their NetCDF outputs for numerical consistency.
4. Time the complete model command, including configured I/O, and compare the median of at least three completed runs per implementation.

Install the comparison-tool dependencies:

```bash
python -m pip install -r requirements.txt
```

Compare one or more matching NetCDF files:

```bash
python tools/compare_netcdf.py \
  runs/baseline/output runs/luteam-optimized/output \
  --file SCS_avg_0001.nc \
  --file Dongsha60_avg_0001.nc \
  --json comparison.json
```

The first directory is the reference and the second is the candidate. The tool checks file structure, dimensions, shapes, data types, masks, NaN/Inf values, and numeric variables. It reports exact equality of numeric values and masks, RMSE, maximum absolute error, valid and masked element counts, and summary statistics. The report provides comparison metrics; choose scientific tolerances appropriate for your application.

## Repository layout

```text
ROMS_CoSiNE15/          ROMS-CoSiNE source and application configuration
tools/                  Optional output-analysis utilities
tests/                  Tests for the public utilities
LICENSE                 License for the SYSU MCC Team modifications
THIRD_PARTY_NOTICES.md  Upstream licenses, attribution, and citations
```

## Project history

MCC validation snapshots are available at [`mcc-compute-improved-validated-2005s`](https://github.com/GaryYang77/MCC-Final-SYSU/tree/mcc-compute-improved-validated-2005s), [`mcc-compute-improved-validated-2147s`](https://github.com/GaryYang77/MCC-Final-SYSU/tree/mcc-compute-improved-validated-2147s), and [`mcc-phase5-validated-2205s`](https://github.com/GaryYang77/MCC-Final-SYSU/tree/mcc-phase5-validated-2205s).

## License and attribution

The SYSU MCC Team modifications are released under the MIT License; see [LICENSE](LICENSE). Bundled third-party components retain their respective copyright and license terms; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Questions about the example dataset or ROMS-CoSiNE LuTeam-HPC-Optimized can be sent to **yanggy25@mail2.sysu.edu.cn**.
