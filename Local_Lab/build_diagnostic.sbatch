#!/bin/bash
#SBATCH -p kshcexclu06
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH -t 00:45:00
#SBATCH -J mcc-build-diagnostic
#SBATCH -o Local_Lab/cluster_logs/%x_%j.out
#SBATCH -e Local_Lab/cluster_logs/%x_%j.err

set -euo pipefail

export LC_ALL=C
export LANG=C

build_root=${MCC_BUILD_ROOT:?MCC_BUILD_ROOT is not set}
repo_root=${SLURM_SUBMIT_DIR:?SLURM_SUBMIT_DIR is not set}
expected_source_sha=${MCC_DIAGNOSTIC_SOURCE_SHA256:?MCC_DIAGNOSTIC_SOURCE_SHA256 is not set}
diagnostic_sources=(
  ROMS_CoSiNE15/ROMS/Modules/mod_parallel.F
  ROMS_CoSiNE15/ROMS/Utility/timers.F
  ROMS_CoSiNE15/ROMS/Utility/distribute.F
  ROMS_CoSiNE15/ROMS/Nonlinear/nesting.F
  ROMS_CoSiNE15/ROMS/Nonlinear/step3d_t.F
  ROMS_CoSiNE15/ROMS/Nonlinear/gls_prestep.F
  ROMS_CoSiNE15/ROMS/Nonlinear/gls_corstep.F
  ROMS_CoSiNE15/ROMS/Nonlinear/Biology/bio_UMAINE15.h
)
actual_source_sha=$(sha256sum "${diagnostic_sources[@]}" | sha256sum | awk '{print $1}')
if [[ "$actual_source_sha" != "$expected_source_sha" ]]; then
  echo "[build-diagnostic] stale source: expected=$expected_source_sha actual=$actual_source_sha" >&2
  exit 3
fi
test ! -e "$build_root"
mkdir -p "$build_root/obj" "$build_root/bin"

ulimit -s unlimited
module purge
module load \
  mathlib/netcdf/4.4.1/intel \
  mpi/hpcx/2.7.4/intel-2017.5.239 \
  mathlib/hdf5/1.8.20/intel \
  compiler/intel/2017.5.239

cd "$repo_root/ROMS_CoSiNE15"
make -j1 \
  ROMS_APPLICATION=BYE24BIO15 \
  MY_CPP_FLAGS=-DPROFILE_DIAGNOSTIC \
  SCRATCH_DIR="$build_root/obj" \
  BINDIR="$build_root/bin" \
  USE_MPI=on \
  USE_NETCDF4=on \
  FORT=ifort \
  USE_MPIF90=on \
  NF_CONFIG="$(command -v nf-config)"

test -x "$build_root/bin/oceanM"
