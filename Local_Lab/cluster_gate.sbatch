#!/bin/bash
#SBATCH -p kshcexclu06
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH -t 00:45:00
#SBATCH -J mcc-demo-gate
#SBATCH -o Local_Lab/cluster_logs/%x_%j.out
#SBATCH -e Local_Lab/cluster_logs/%x_%j.err

set -euo pipefail

export LC_ALL=C
export LANG=C
export OMP_NUM_THREADS=1
export MCC_VALIDATION_PROFILE=cluster-intel

ulimit -s unlimited
module purge
module load \
  mathlib/netcdf/4.4.1/intel \
  mpi/hpcx/2.7.4/intel-2017.5.239 \
  mathlib/hdf5/1.8.20/intel \
  compiler/intel/2017.5.239

source /public/share/mcc2026_final/miniforge3/etc/profile.d/conda.sh
conda activate vali

cd "${SLURM_SUBMIT_DIR:?SLURM_SUBMIT_DIR is not set}"
test -d ROMS_CoSiNE15/Inputfiles
test -f ROMS_CoSiNE15/ROMS/External/ocean_SCS_Dongsha60_bio15.in

command_name="${MCC_GATE_COMMAND:-validate}"
case "$command_name" in
  baseline|build|validate) ;;
  *) echo "unsupported MCC_GATE_COMMAND: $command_name" >&2; exit 2 ;;
esac

echo "[cluster] job_id=${SLURM_JOB_ID} host=$(hostname) command=${command_name}"
echo "[cluster] worktree=${SLURM_SUBMIT_DIR}"
echo "[cluster] profile=${MCC_VALIDATION_PROFILE}"
python -u Local_Lab/valid_test.py "$command_name"
