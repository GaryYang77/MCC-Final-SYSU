#!/bin/bash
#SBATCH -p kshcexclu06
#SBATCH -N 4
#SBATCH -n 128
#SBATCH --cpus-per-task=1
#SBATCH --exclusive
#SBATCH -t 00:30:00
#SBATCH -J mcc-profile128

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

run_dir=${MCC_PROFILE_RUN_DIR:?MCC_PROFILE_RUN_DIR is not set}
cd "$run_dir"

/usr/bin/time -v mpirun -np "${SLURM_NTASKS:?}" \
  ./oceanM ocean_profile.in > model.log 2> resource.log

if ! grep -q 'ROMS/TOMS: DONE' model.log; then
  echo "[profile128] FAIL: normal completion marker is missing" >&2
  tail -80 model.log >&2
  exit 1
fi

test -s output/SCS_avg_0001.nc
test -s output/Dongsha60_avg_0001.nc
