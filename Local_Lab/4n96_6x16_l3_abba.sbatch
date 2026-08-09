#!/bin/bash
#SBATCH -p kshcexclu06
#SBATCH -N 4
#SBATCH -n 96
#SBATCH --ntasks-per-node=24
#SBATCH --cpus-per-task=1
#SBATCH --exclusive
#SBATCH -t 00:15:00
#SBATCH -J mcc-l3-abba

set -euo pipefail
export LC_ALL=C LANG=C OMP_NUM_THREADS=1
ulimit -s unlimited
module purge
module load mathlib/netcdf/4.4.1/intel \
  mpi/hpcx/2.7.4/intel-2017.5.239 \
  mathlib/hdf5/1.8.20/intel compiler/intel/2017.5.239

control_a=${MCC_CONTROL_A:?}
candidate_a=${MCC_CANDIDATE_A:?}
candidate_b=${MCC_CANDIDATE_B:?}
control_b=${MCC_CONTROL_B:?}
mapfile -t hosts < <(scontrol show hostnames "${SLURM_JOB_NODELIST:?}")
test "${#hosts[@]}" -eq 4
control_slots=(0 1 2 3 4 5 8 9 10 11 12 13 16 17 18 19 20 21 24 25 26 27 28 29)
candidate_slots=(0 1 2 4 5 6 8 9 10 12 13 14 16 17 18 20 21 22 24 25 26 28 29 30)
rankfile="$candidate_a/l3_balanced.rankfile"
: > "$rankfile"
: > "$candidate_a/control_mapping.expected"
: > "$candidate_a/candidate_mapping.expected"
for ((rank=0; rank<96; rank++)); do
  node=${hosts[$((rank/24))]}
  local_rank=$((rank%24))
  printf '%d %s %d\n' "$rank" "$node" "${control_slots[$local_rank]}" >> "$candidate_a/control_mapping.expected"
  printf '%d %s %d\n' "$rank" "$node" "${candidate_slots[$local_rank]}" >> "$candidate_a/candidate_mapping.expected"
  printf 'rank %d=%s slot=%d\n' "$rank" "$node" "${candidate_slots[$local_rank]}" >> "$rankfile"
done

probe() {
  local mode=$1 expected=$2 actual=$3
  local -a args=(mpirun -np 96 --map-by ppr:6:numa:PE=1 --rank-by slot --bind-to core)
  if [[ "$mode" == candidate ]]; then args=(mpirun -np 96 --rankfile "$rankfile"); fi
  "${args[@]}" /bin/bash -c '
    cpus=$(awk "/^Cpus_allowed_list:/ {print \$2}" /proc/self/status)
    printf "%s %s %s\n" "$OMPI_COMM_WORLD_RANK" "$(hostname)" "$cpus"
  ' | sort -n > "$actual"
  diff -u "$expected" "$actual"
}
probe control "$candidate_a/control_mapping.expected" "$candidate_a/control_mapping.actual"
probe candidate "$candidate_a/candidate_mapping.expected" "$candidate_a/candidate_mapping.actual"
echo '[l3-abba] mapping probes PASS'

run_case() {
  local run_dir=$1 case_name=$2 mode=$3
  local -a args=(mpirun -np 96 --map-by ppr:6:numa:PE=1 --rank-by slot --bind-to core)
  if [[ "$mode" == candidate ]]; then args=(mpirun -np 96 --rankfile "$rankfile"); fi
  cd "$run_dir"
  { echo "case=$case_name"; echo "mapping=$mode"; echo "slurm_job_id=${SLURM_JOB_ID:?}";
    echo "slurm_job_nodelist=${SLURM_JOB_NODELIST:?}"; echo "start_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"; } > allocation.log
  /usr/bin/time -v "${args[@]}" ./oceanM ocean_profile.in > model.log 2> resource.log
  echo "end_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> allocation.log
  grep -q 'ROMS/TOMS: DONE' model.log
  test -s output/SCS_avg_0001.nc
  test -s output/Dongsha60_avg_0001.nc
}
run_case "$control_a" control-a control
run_case "$candidate_a" candidate-a candidate
run_case "$candidate_b" candidate-b candidate
run_case "$control_b" control-b control
echo '[l3-abba] ABBA model runs PASS'
