#!/bin/bash
#SBATCH -p kshcexclu06
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH -t 00:45:00
#SBATCH -J mcc-build-no-profile
#SBATCH -o Local_Lab/cluster_logs/%x_%j.out
#SBATCH -e Local_Lab/cluster_logs/%x_%j.err

set -euo pipefail

export LC_ALL=C
export LANG=C

build_root=${MCC_BUILD_ROOT:?MCC_BUILD_ROOT is not set}
repo_root=${SLURM_SUBMIT_DIR:?SLURM_SUBMIT_DIR is not set}
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
  MY_CPP_FLAGS=-DMCC_NO_PROFILE \
  SCRATCH_DIR="$build_root/obj" \
  BINDIR="$build_root/bin" \
  USE_MPI=on \
  USE_NETCDF4=on \
  FORT=ifort \
  USE_MPIF90=on \
  NF_CONFIG="$(command -v nf-config)"

test -x "$build_root/bin/oceanM"
