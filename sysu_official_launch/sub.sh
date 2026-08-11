#!/bin/bash
#SBATCH -p kshcexclu06
#SBATCH -N 4
#SBATCH -n 96
#SBATCH --ntasks-per-node=24
#SBATCH --cpus-per-task=1
#SBATCH --exclusive
#SBATCH -t 02:00:00
#SBATCH -J sysu-final
#SBATCH -o sysu_official_launch/slurm_%j.out
#SBATCH -e sysu_official_launch/slurm_%j.err

set -euo pipefail
export OMP_NUM_THREADS=1
ulimit -s unlimited

module purge
module load mathlib/netcdf/4.4.1/intel \
  mpi/hpcx/2.7.4/intel-2017.5.239 \
  mathlib/hdf5/1.8.20/intel compiler/intel/2017.5.239

repo_root=${SLURM_SUBMIT_DIR:?submit this script from the repository root}
launch_dir="$repo_root/sysu_official_launch"
roms_root="$repo_root/ROMS_CoSiNE15"
run_dir="$launch_dir/run_${SLURM_JOB_ID:?}"
binary="$launch_dir/oceanM"
input="$run_dir/ocean.in"
expected_sha=1152299ea019b653a4007bca10490c01bb9c0ce8af90c87835eec0167a11a410

cd "$repo_root"
test -x "$binary"
printf '%s  %s\n' "$expected_sha" "$binary" | sha256sum -c -
test -d "$roms_root/Inputfiles"
test ! -e "$run_dir"
mkdir -p "$run_dir/output"
cp "$binary" "$run_dir/oceanM"
ln -s "$roms_root/ROMS" "$run_dir/ROMS"
ln -s "$roms_root/Inputfiles" "$run_dir/Inputfiles"
cp "$roms_root/ROMS/External/ocean_SCS_Dongsha60_bio15.in" "$input"

test "$(grep -Ec '^[[:space:]]*NtileI[[:space:]]*==' "$input")" -eq 1
test "$(grep -Ec '^[[:space:]]*NtileJ[[:space:]]*==' "$input")" -eq 1
test "$(grep -Ec '^[[:space:]]*NTIMES[[:space:]]*==' "$input")" -eq 1
sed -Ei \
  -e 's/^([[:space:]]*NtileI[[:space:]]*==).*/\1 6  6/' \
  -e 's/^([[:space:]]*NtileJ[[:space:]]*==).*/\1 16  16/' \
  -e 's/^([[:space:]]*NTIMES[[:space:]]*==).*/\1 2592  12960/' \
  "$input"

mapfile -t hosts < <(scontrol show hostnames "$SLURM_JOB_NODELIST")
test "${#hosts[@]}" -eq 4
slots=(0 1 2 4 5 6 8 9 10 12 13 14 16 17 18 20 21 22 24 25 26 28 29 30)
rankfile="$run_dir/rankfile"
: > "$rankfile"
for ((rank=0; rank<96; rank++)); do
  printf 'rank %d=%s slot=%d\n' \
    "$rank" "${hosts[$((rank/24))]}" "${slots[$((rank%24))]}" >> "$rankfile"
done

cd "$run_dir"
/usr/bin/time -v mpirun -np 96 --rankfile "$rankfile" \
  ./oceanM ocean.in > model.log 2> resource.log
grep -q 'ROMS/TOMS: DONE' model.log
test -s output/SCS_avg_0001.nc
test -s output/Dongsha60_avg_0001.nc

official=/public/share/mcc2026_final/vali.py
validator="$run_dir/vali_official.py"
test "$(grep -c '^dir_test = ' "$official")" -eq 1
cp "$official" "$validator"
sed -i "s|^dir_test = .*|dir_test = '$run_dir/output/'|" "$validator"
set +e
diff -u "$official" "$validator" > vali_official.diff
diff_status=$?
set -e
test "$diff_status" -eq 1

source /public/share/mcc2026_final/miniforge3/etc/profile.d/conda.sh
conda activate vali
set -o pipefail
python "$validator" 2>&1 | tee vali_official.log
grep -Fq '最终判定：两组文件所有变量RMSE均在阈值范围内，优化结果无异常' vali_official.log

echo "PASS"
echo "run_dir=$run_dir"
grep 'Elapsed (wall clock)' resource.log
