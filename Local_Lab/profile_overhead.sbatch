#!/bin/bash
#SBATCH -p kshcexclu06
#SBATCH -N 4
#SBATCH -n 128
#SBATCH --cpus-per-task=1
#SBATCH --exclusive
#SBATCH -t 00:30:00
#SBATCH -J mcc-profile-overhead

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

profile_run_dir=${MCC_PROFILE_ON_RUN_DIR:?MCC_PROFILE_ON_RUN_DIR is not set}
control_run_dir=${MCC_PROFILE_OFF_RUN_DIR:?MCC_PROFILE_OFF_RUN_DIR is not set}
run_order=${MCC_PROFILE_RUN_ORDER:-off-on}
profile_mode=${MCC_PROFILE_MODE:-score}

run_case() {
  local run_dir=$1
  local case_name=$2
  local mode=score
  if [[ "$case_name" == profile-on ]]; then
    mode=$profile_mode
  fi
  export MCC_PROFILE_MODE=$mode
  export MCC_PROFILE_DIAG_DIR=$run_dir
  export MCC_TRACE_RANKS=${MCC_TRACE_RANKS:-0}
  export MCC_TRACE_MAX_EVENTS=${MCC_TRACE_MAX_EVENTS:-100000}
  cd "$run_dir"
  {
    echo "case=$case_name"
    echo "slurm_job_id=${SLURM_JOB_ID:?}"
    echo "slurm_job_nodelist=${SLURM_JOB_NODELIST:?}"
    echo "start_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  } > allocation.log
  /usr/bin/time -v mpirun -np "${SLURM_NTASKS:?}" \
    ./oceanM ocean_profile.in > model.log 2> resource.log
  echo "end_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> allocation.log
  grep -q 'ROMS/TOMS: DONE' model.log
  test -s output/SCS_avg_0001.nc
  test -s output/Dongsha60_avg_0001.nc
}

case "$run_order" in
  off-on)
    run_case "$control_run_dir" profile-off
    run_case "$profile_run_dir" profile-on
    ;;
  on-off)
    run_case "$profile_run_dir" profile-on
    run_case "$control_run_dir" profile-off
    ;;
  *)
    echo "invalid MCC_PROFILE_RUN_ORDER: $run_order" >&2
    exit 2
    ;;
esac
