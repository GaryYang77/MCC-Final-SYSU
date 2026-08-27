#!/usr/bin/env bash
#SBATCH --job-name=roms-cosine
#SBATCH --nodes=4
#SBATCH --ntasks=96
#SBATCH --ntasks-per-node=24
#SBATCH --cpus-per-task=1
#SBATCH --time=02:00:00
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err

set -euo pipefail
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-1}
ulimit -s unlimited 2>/dev/null || true

# Load the compiler, MPI, HDF5, and NetCDF modules required by your cluster
# here, or submit this job from an environment where they are already loaded.
# Example:
#   module purge
#   module load <compiler> <mpi> <hdf5> <netcdf>

repo_root=${ROMS_REPO_ROOT:-${SLURM_SUBMIT_DIR:?submit this script from the repository root}}
roms_root="$repo_root/ROMS_CoSiNE15"
binary=${ROMS_BINARY:-"$roms_root/bin_local/oceanM"}
inputfiles=${ROMS_INPUTFILES:-"$roms_root/Inputfiles"}
runs_root=${ROMS_RUNS_DIR:-"$repo_root/runs"}
tiles_i=${ROMS_TILES_I:-6}
tiles_j=${ROMS_TILES_J:-16}
ranks=${SLURM_NTASKS:?SLURM_NTASKS is required}
job_id=${SLURM_JOB_ID:?SLURM_JOB_ID is required}

die() {
  echo "ERROR: $*" >&2
  exit 2
}

if [[ ! $tiles_i =~ ^[1-9][0-9]*$ || ! $tiles_j =~ ^[1-9][0-9]*$ ]]; then
  echo "ROMS_TILES_I and ROMS_TILES_J must be positive integers" >&2
  exit 2
fi
if [[ ! $ranks =~ ^[1-9][0-9]*$ || ! $job_id =~ ^[1-9][0-9]*$ ]]; then
  echo "SLURM_NTASKS and SLURM_JOB_ID must be positive integers" >&2
  exit 2
fi
if (( tiles_i * tiles_j != ranks )); then
  echo "tile product $tiles_i x $tiles_j does not match $ranks MPI ranks" >&2
  exit 2
fi

[[ -x $binary ]] || die "ROMS binary is not executable: $binary"
[[ -d $inputfiles ]] || die "Inputfiles directory does not exist: $inputfiles"
[[ -f $inputfiles/SCS/SCS_grd.nc ]] || die "missing SCS grid: $inputfiles/SCS/SCS_grd.nc"
[[ -f $inputfiles/Dongsha60/Dongsha60_grd.nc ]] || die "missing Dongsha60 grid: $inputfiles/Dongsha60/Dongsha60_grd.nc"
command -v srun >/dev/null 2>&1 || die "srun is unavailable; load your Slurm environment"

run_dir="$runs_root/scs_dongsha60_$job_id"
[[ ! -e $run_dir ]] || die "run directory already exists: $run_dir"
mkdir -p "$run_dir/output"
cp "$binary" "$run_dir/oceanM"
ln -s "$roms_root/ROMS" "$run_dir/ROMS"
ln -s "$inputfiles" "$run_dir/Inputfiles"
cp "$roms_root/ROMS/External/ocean_SCS_Dongsha60_bio15.in" "$run_dir/ocean.in"

[[ $(grep -Ec '^[[:space:]]*NtileI[[:space:]]*==' "$run_dir/ocean.in") -eq 1 ]] || die "expected one NtileI line in ocean.in"
[[ $(grep -Ec '^[[:space:]]*NtileJ[[:space:]]*==' "$run_dir/ocean.in") -eq 1 ]] || die "expected one NtileJ line in ocean.in"
sed -Ei \
  -e "s/^([[:space:]]*NtileI[[:space:]]*==).*/\\1 $tiles_i  $tiles_i/" \
  -e "s/^([[:space:]]*NtileJ[[:space:]]*==).*/\\1 $tiles_j  $tiles_j/" \
  "$run_dir/ocean.in"

cd "$run_dir"
set +e
SECONDS=0
srun --ntasks="$ranks" ./oceanM ocean.in >model.log 2>&1
model_status=$?
elapsed_seconds=$SECONDS
set -e
printf 'wall_seconds=%d\n' "$elapsed_seconds" >resource.log

if (( model_status != 0 )) || ! grep -q 'ROMS/TOMS: DONE' model.log; then
  echo "ROMS failed; inspect $run_dir/model.log and resource.log" >&2
  tail -40 model.log >&2 || true
  exit 1
fi

[[ -s output/SCS_avg_0001.nc ]] || die "missing or empty output: $run_dir/output/SCS_avg_0001.nc"
[[ -s output/Dongsha60_avg_0001.nc ]] || die "missing or empty output: $run_dir/output/Dongsha60_avg_0001.nc"
echo "Run complete"
echo "  directory: $run_dir"
cat resource.log
