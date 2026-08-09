#!/bin/bash
#SBATCH -p kshcexclu06
#SBATCH -N 4
#SBATCH -n 96
#SBATCH --ntasks-per-node=24
#SBATCH --cpus-per-task=1
#SBATCH --exclusive
#SBATCH -t 02:00:00
#SBATCH -J mcc-full-4n96-6x16

set -euo pipefail

export LC_ALL=C
export LANG=C
export OMP_NUM_THREADS=1

ulimit -s unlimited
module purge
module load \
  mathlib/netcdf/4.4.1/intel \
  mpi/hpcx/2.7.4/intel-2017.5.239 \
  mathlib/hdf5/1.8.20/intel \
  compiler/intel/2017.5.239

preflight_run=${MCC_PREFLIGHT_RUN_DIR:?MCC_PREFLIGHT_RUN_DIR is not set}
full_run=${MCC_FULL_RUN_DIR:?MCC_FULL_RUN_DIR is not set}
preflight_limit=${MCC_PREFLIGHT_MAX_SECONDS:-90}

run_case() {
  local run_dir=$1
  local case_name=$2
  local start_seconds end_seconds elapsed_seconds

  cd "$run_dir"
  {
    echo "case=$case_name"
    echo "slurm_job_id=${SLURM_JOB_ID:?}"
    echo "slurm_job_nodelist=${SLURM_JOB_NODELIST:?}"
    echo "slurm_job_num_nodes=${SLURM_JOB_NUM_NODES:?}"
    echo "slurm_ntasks=${SLURM_NTASKS:?}"
    echo "start_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  } > allocation.log

  start_seconds=$(date +%s)
  /usr/bin/time -v mpirun -np "${SLURM_NTASKS:?}" \
    ./oceanM ocean_profile.in > model.log 2> resource.log
  end_seconds=$(date +%s)
  elapsed_seconds=$((end_seconds-start_seconds))
  {
    echo "end_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "elapsed_integer_seconds=$elapsed_seconds"
  } >> allocation.log

  grep -q 'ROMS/TOMS: DONE' model.log
  test -s output/SCS_avg_0001.nc
  test -s output/Dongsha60_avg_0001.nc
  printf '%s\n' "$elapsed_seconds"
}

preflight_seconds=$(run_case "$preflight_run" preflight-no-profile)
if (( preflight_seconds > preflight_limit )); then
  echo "[full-6x16] SLOW_NODE_ABORT preflight=${preflight_seconds}s limit=${preflight_limit}s nodes=${SLURM_JOB_NODELIST}" >&2
  exit 42
fi

echo "[full-6x16] preflight PASS: ${preflight_seconds}s nodes=${SLURM_JOB_NODELIST}"
run_case "$full_run" full-no-profile
