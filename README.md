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

The included application is `BYE24BIO15`. The public build script defaults to Intel `ifort`, MPI, NetCDF4, and a clean no-profile build:

```bash
scripts/build_roms.sh
```

Before building, confirm that `mpif90 -show` uses the compiler selected by `ROMS_FORT`. With Intel MPI, set `I_MPI_F90=ifort` if the wrapper does not already invoke `ifort`.

The executable is written to `ROMS_CoSiNE15/bin_local/oceanM`. Build locations, job count, application, compiler rules, CPP flags, and `nf-config` can be overridden with environment variables:

```bash
ROMS_BUILD_JOBS=16 \
ROMS_BUILD_DIR=/path/to/scratch/roms-build \
ROMS_BIN_DIR=/path/to/scratch/roms-bin \
NF_CONFIG=/path/to/nf-config \
  scripts/build_roms.sh
```

Run `scripts/build_roms.sh --help` for the complete interface. The script wraps the existing ROMS makefile with `USE_MPI=on`, `USE_MPIF90=on`, `USE_NETCDF4=on`, and `MY_CPP_FLAGS=-DMCC_NO_PROFILE` by default. Set `ROMS_CPP_FLAGS` to an empty string only when an instrumented build is desired.

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

The delivered package follows this layout, and the `.in` file lists the expected input paths. The checked-in configuration uses a `4x8 = 32` rank decomposition. The following non-Slurm example keeps that file unchanged and creates a runtime copy configured for `6x16 = 96` MPI ranks:

```bash
run_dir=runs/scs_dongsha60_manual
test ! -e "$run_dir"
mkdir -p "$run_dir/output"
cp ROMS_CoSiNE15/bin_local/oceanM "$run_dir/oceanM"
ln -s ../../ROMS_CoSiNE15/ROMS "$run_dir/ROMS"
ln -s ../../ROMS_CoSiNE15/Inputfiles "$run_dir/Inputfiles"
cp ROMS_CoSiNE15/ROMS/External/ocean_SCS_Dongsha60_bio15.in \
  "$run_dir/ocean.in"
sed -Ei \
  -e 's/^([[:space:]]*NtileI[[:space:]]*==).*/\1 6  6/' \
  -e 's/^([[:space:]]*NtileJ[[:space:]]*==).*/\1 16  16/' \
  "$run_dir/ocean.in"
(
  cd "$run_dir"
  mpirun -np 96 ./oceanM ocean.in \
    > roms.log 2>&1
)
```

For each distributed-memory grid, the decomposition must match the MPI rank count:

```text
NtileI(ng) * NtileJ(ng) == MPI ranks
```

When changing the number of ranks, update `NtileI` and `NtileJ` for both nested grids. Replace `mpirun` with the launcher required by your cluster, such as `srun`.

### Slurm example

The repository includes a generic Slurm template at `examples/slurm/scs_dongsha60.sbatch`. It defaults to 4 nodes, 96 MPI ranks, 24 ranks per node, and a `6x16` decomposition. Edit or override the resource directives for your cluster, load its compiler/MPI/NetCDF environment, then submit from the repository root:

```bash
sbatch examples/slurm/scs_dongsha60.sbatch
```

The template accepts alternate binary, dataset, run-directory, and tiling locations through environment variables:

```bash
export ROMS_BINARY=/path/to/oceanM
export ROMS_INPUTFILES=/path/to/Inputfiles
export ROMS_RUNS_DIR=/path/to/runs
export ROMS_REPO_ROOT=/path/to/MCC-Final-SYSU
export ROMS_TILES_I=6
export ROMS_TILES_J=16
sbatch --export=ALL examples/slurm/scs_dongsha60.sbatch
```

The 96-rank layout is an example rather than a requirement; when changing `--ntasks`, set the tiling variables so their product matches the new rank count. Each job creates an isolated run directory, copies its binary and input configuration, links the model and dataset trees, records wall time, and checks for normal completion and both average files.

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
scripts/                Portable build entry points
examples/slurm/         Scheduler templates for the example case
tools/                  Optional output-analysis utilities
tests/                  Tests for the comparison tool and public scripts
LICENSE                 License for the SYSU MCC Team modifications
THIRD_PARTY_NOTICES.md  Upstream licenses, attribution, and citations
```

## Tests

Install the Python dependencies and run the public test suite with:

```bash
python -m pip install -r requirements.txt
python -m pytest -q tests
```

The suite tests the NetCDF comparison metrics and uses mocked `make` and `srun` commands to exercise the public build/run orchestration. It does not compile ROMS, submit a real Slurm job, run the scientific model, or replace output validation on the target system.

## Project history

MCC validation snapshots are available at [`mcc-compute-improved-validated-2005s`](https://github.com/GaryYang77/MCC-Final-SYSU/tree/mcc-compute-improved-validated-2005s), [`mcc-compute-improved-validated-2147s`](https://github.com/GaryYang77/MCC-Final-SYSU/tree/mcc-compute-improved-validated-2147s), and [`mcc-phase5-validated-2205s`](https://github.com/GaryYang77/MCC-Final-SYSU/tree/mcc-phase5-validated-2205s).

## License and attribution

The SYSU MCC Team modifications are released under the MIT License; see [LICENSE](LICENSE). Bundled third-party components retain their respective copyright and license terms; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Questions about the example dataset or ROMS-CoSiNE LuTeam-HPC-Optimized can be sent to **yanggy25@mail2.sysu.edu.cn**.
