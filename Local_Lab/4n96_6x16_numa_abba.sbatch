#!/bin/bash
#SBATCH -p kshcexclu06
#SBATCH -N 4
#SBATCH -n 96
#SBATCH --ntasks-per-node=24
#SBATCH --cpus-per-task=1
#SBATCH --exclusive
#SBATCH -t 00:15:00
#SBATCH -J mcc-numa-abba

set -euo pipefail
export LC_ALL=C LANG=C OMP_NUM_THREADS=1
ulimit -s unlimited
module purge
module load \
  mathlib/netcdf/4.4.1/intel \
  mpi/hpcx/2.7.4/intel-2017.5.239 \
  mathlib/hdf5/1.8.20/intel \
  compiler/intel/2017.5.239

control_a=${MCC_CONTROL_A:?}
bound_a=${MCC_BOUND_A:?}
bound_b=${MCC_BOUND_B:?}
control_b=${MCC_CONTROL_B:?}
mapfile -t hosts < <(scontrol show hostnames "${SLURM_JOB_NODELIST:?}")
test "${#hosts[@]}" -eq 4
control_slots=(0 8 16 24 1 9 17 25 2 10 18 26 3 11 19 27 4 12 20 28 5 13 21 29)
bound_slots=(0 1 2 3 4 5 8 9 10 11 12 13 16 17 18 19 20 21 24 25 26 27 28 29)

write_expected() {
  local output=$1
  local slots_name=$2
  local slot
  : > "$output"
  for ((rank=0; rank<96; rank++)); do
    if [[ "$slots_name" == control_slots ]]; then
      slot=${control_slots[$((rank%24))]}
    else
      slot=${bound_slots[$((rank%24))]}
    fi
    printf '%d %s %d\n' "$rank" "${hosts[$((rank/24))]}" "$slot" >> "$output"
  done
}

probe() {
  local mode=$1 expected=$2 actual=$3
  local -a args=(mpirun -np 96)
  if [[ "$mode" == bound ]]; then
    args+=(--map-by ppr:6:numa:PE=1 --rank-by slot --bind-to core)
  fi
  "${args[@]}" /bin/bash -c '
    cpus=$(awk "/^Cpus_allowed_list:/ {print \$2}" /proc/self/status)
    printf "%s %s %s\n" "$OMPI_COMM_WORLD_RANK" "$(hostname)" "$cpus"
  ' | sort -n > "$actual"
  diff -u "$expected" "$actual"
}

write_expected "$bound_a/control_mapping.expected" control_slots
write_expected "$bound_a/bound_mapping.expected" bound_slots
probe control "$bound_a/control_mapping.expected" "$bound_a/control_mapping.actual"
probe bound "$bound_a/bound_mapping.expected" "$bound_a/bound_mapping.actual"
echo '[numa-abba] mapping probes PASS'

run_case() {
  local run_dir=$1 case_name=$2 mode=$3
  local -a args=(mpirun -np 96)
  if [[ "$mode" == bound ]]; then
    args+=(--map-by ppr:6:numa:PE=1 --rank-by slot --bind-to core)
  fi
  cd "$run_dir"
  {
    echo "case=$case_name"
    echo "mapping=$mode"
    echo "slurm_job_id=${SLURM_JOB_ID:?}"
    echo "slurm_job_nodelist=${SLURM_JOB_NODELIST:?}"
    echo "start_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  } > allocation.log
  /usr/bin/time -v "${args[@]}" ./oceanM ocean_profile.in > model.log 2> resource.log
  echo "end_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> allocation.log
  grep -q 'ROMS/TOMS: DONE' model.log
  test -s output/SCS_avg_0001.nc
  test -s output/Dongsha60_avg_0001.nc
}

run_case "$control_a" control-a control
run_case "$bound_a" bound-a bound
run_case "$bound_b" bound-b bound
run_case "$control_b" control-b control
echo '[numa-abba] ABBA model runs PASS'
