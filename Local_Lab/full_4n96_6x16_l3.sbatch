#!/bin/bash
#SBATCH -p kshcexclu06
#SBATCH -N 4
#SBATCH -n 96
#SBATCH --ntasks-per-node=24
#SBATCH --cpus-per-task=1
#SBATCH --exclusive
#SBATCH -t 02:00:00
#SBATCH -J mcc-full-6x16-l3

set -euo pipefail
export LC_ALL=C LANG=C OMP_NUM_THREADS=1
ulimit -s unlimited
module purge
module load mathlib/netcdf/4.4.1/intel \
  mpi/hpcx/2.7.4/intel-2017.5.239 \
  mathlib/hdf5/1.8.20/intel compiler/intel/2017.5.239

preflight_run=${MCC_PREFLIGHT_RUN_DIR:?}
full_run=${MCC_FULL_RUN_DIR:?}
preflight_limit=${MCC_PREFLIGHT_MAX_SECONDS:-90}
mapfile -t hosts < <(scontrol show hostnames "${SLURM_JOB_NODELIST:?}")
test "${#hosts[@]}" -eq 4
slots=(0 1 2 4 5 6 8 9 10 12 13 14 16 17 18 20 21 22 24 25 26 28 29 30)
rankfile="$preflight_run/l3_balanced.rankfile"
: > "$rankfile"
for ((rank=0; rank<96; rank++)); do
  printf 'rank %d=%s slot=%d\n' "$rank" "${hosts[$((rank/24))]}" "${slots[$((rank%24))]}" >> "$rankfile"
done
mpirun -np 96 --rankfile "$rankfile" /bin/bash -c '
  cpus=$(awk "/^Cpus_allowed_list:/ {print \$2}" /proc/self/status)
  printf "%s %s %s\n" "$OMPI_COMM_WORLD_RANK" "$(hostname)" "$cpus"
' | sort -n > "$preflight_run/l3_mapping.actual"
test "$(wc -l < "$preflight_run/l3_mapping.actual")" -eq 96

run_case() {
  local run_dir=$1 case_name=$2 start end
  cd "$run_dir"
  { echo "case=$case_name"; echo 'mapping=l3-balanced-numa-row';
    echo "slurm_job_id=${SLURM_JOB_ID:?}"; echo "slurm_job_nodelist=${SLURM_JOB_NODELIST:?}";
    echo "start_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"; } > allocation.log
  start=$(date +%s)
  /usr/bin/time -v mpirun -np 96 --rankfile "$rankfile" \
    ./oceanM ocean_profile.in > model.log 2> resource.log
  end=$(date +%s)
  { echo "end_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)";
    echo "elapsed_integer_seconds=$((end-start))"; } >> allocation.log
  grep -q 'ROMS/TOMS: DONE' model.log
  test -s output/SCS_avg_0001.nc
  test -s output/Dongsha60_avg_0001.nc
  printf '%s\n' "$((end-start))"
}

preflight_seconds=$(run_case "$preflight_run" preflight-no-profile)
if (( preflight_seconds > preflight_limit )); then
  echo "[full-6x16-l3] SLOW_NODE_ABORT preflight=${preflight_seconds}s limit=${preflight_limit}s nodes=${SLURM_JOB_NODELIST}" >&2
  exit 42
fi
echo "[full-6x16-l3] preflight PASS: ${preflight_seconds}s nodes=${SLURM_JOB_NODELIST}"
run_case "$full_run" full-no-profile
