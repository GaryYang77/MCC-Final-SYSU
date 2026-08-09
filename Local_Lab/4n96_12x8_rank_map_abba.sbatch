#!/bin/bash
#SBATCH -p kshcexclu06
#SBATCH -N 4
#SBATCH -n 96
#SBATCH --ntasks-per-node=24
#SBATCH --cpus-per-task=1
#SBATCH --exclusive
#SBATCH -t 00:15:00
#SBATCH -J mcc-rank-map-abba

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

control_a=${MCC_CONTROL_A:?MCC_CONTROL_A is not set}
mapped_a=${MCC_MAPPED_A:?MCC_MAPPED_A is not set}
mapped_b=${MCC_MAPPED_B:?MCC_MAPPED_B is not set}
control_b=${MCC_CONTROL_B:?MCC_CONTROL_B is not set}

mapfile -t hosts < <(scontrol show hostnames "${SLURM_JOB_NODELIST:?}")
test "${#hosts[@]}" -eq 4
core_slots=(0 8 16 24 1 9 17 25 2 10 18 26 3 11 19 27 4 12 20 28 5 13 21 29)

rankfile=$(realpath "$mapped_a/i_stripe.rankfile")
control_expected=$(realpath "$mapped_a/control_mapping.expected")
mapped_expected=$(realpath "$mapped_a/i_stripe_mapping.expected")
: > "$rankfile"
: > "$control_expected"
: > "$mapped_expected"

for ((rank=0; rank<96; rank++)); do
  node_index=$((rank / 24))
  local_rank=$((rank % 24))
  printf '%d %s %d\n' \
    "$rank" "${hosts[$node_index]}" "${core_slots[$local_rank]}" \
    >> "$control_expected"
done

for ((j=0; j<8; j++)); do
  for ((i=0; i<12; i++)); do
    rank=$((j * 12 + i))
    node_index=$((i / 3))
    local_rank=$((j * 3 + i % 3))
    printf 'rank %d=%s slot=%d\n' \
      "$rank" "${hosts[$node_index]}" "${core_slots[$local_rank]}" >> "$rankfile"
    printf '%d %s %d\n' \
      "$rank" "${hosts[$node_index]}" "${core_slots[$local_rank]}" \
      >> "$mapped_expected"
  done
done
sort -n -o "$mapped_expected" "$mapped_expected"

probe_mapping() {
  local mode=$1
  local expected=$2
  local actual=$3
  local -a mpi_args

  if [[ "$mode" == control ]]; then
    mpi_args=(mpirun -np 96)
  else
    mpi_args=(mpirun -np 96 --rankfile "$rankfile")
  fi
  "${mpi_args[@]}" /bin/bash -c '
    cpus=$(awk "/^Cpus_allowed_list:/ {print \$2}" /proc/self/status)
    printf "%s %s %s\n" "$OMPI_COMM_WORLD_RANK" "$(hostname)" "$cpus"
  ' | sort -n > "$actual"
  test "$(wc -l < "$actual")" -eq 96
  diff -u "$expected" "$actual"
}

probe_mapping control "$control_expected" "$mapped_a/control_mapping.actual"
probe_mapping mapped "$mapped_expected" "$mapped_a/i_stripe_mapping.actual"
echo "[rank-map] mapping and core-binding probes PASS"

run_case() {
  local run_dir=$1
  local case_name=$2
  local mode=$3
  local start_seconds end_seconds elapsed_seconds
  local -a mpi_args

  if [[ "$mode" == control ]]; then
    mpi_args=(mpirun -np 96)
  else
    mpi_args=(mpirun -np 96 --rankfile "$rankfile")
  fi

  cd "$run_dir"
  {
    echo "case=$case_name"
    echo "mapping=$mode"
    echo "slurm_job_id=${SLURM_JOB_ID:?}"
    echo "slurm_job_nodelist=${SLURM_JOB_NODELIST:?}"
    echo "slurm_job_num_nodes=${SLURM_JOB_NUM_NODES:?}"
    echo "slurm_ntasks=${SLURM_NTASKS:?}"
    echo "start_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  } > allocation.log

  start_seconds=$(date +%s)
  /usr/bin/time -v "${mpi_args[@]}" \
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
}

run_case "$control_a" control-a control
run_case "$mapped_a" mapped-a mapped
run_case "$mapped_b" mapped-b mapped
run_case "$control_b" control-b control
echo "[rank-map] ABBA model runs PASS"
