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

# 赛题合规说明：
#   1. 使用 4 个 CPU 节点、96 个 MPI 进程，不申请或使用 DCU。
#   2. 复制官方参数文件，仅修改赛题明确允许调整的 MPI 分块参数：
#      NtileI=6、NtileJ=16。
#   3. 不修改网格、积分时长、时间步长、输出频率、强迫场、初始场、
#      边界场、生态参数、生物模块或双向嵌套方式。
#   4. 下方 rankfile 仅调整 CPU 进程绑核位置，不改变模式区域划分、
#      方程、输入数据或数值运算。
#   5. 计算完成后使用官方 vali.py 和官方 NetCDF 参考结果验证；
#      vali.py 副本仅修改 dir_test，使其指向本次输出目录。

set -euo pipefail
export OMP_NUM_THREADS=1
ulimit -s unlimited

# 加载主办方平台提供的 Intel、MPI 和 NetCDF 运行环境。
module purge
module load mathlib/netcdf/4.4.1/intel \
  mpi/hpcx/2.7.4/intel-2017.5.239 \
  mathlib/hdf5/1.8.20/intel compiler/intel/2017.5.239

# 定义固定路径，并记录已经完成全量验证的无插桩可执行文件 SHA-256。
repo_root=${SLURM_SUBMIT_DIR:?submit this script from the repository root}
launch_dir="$repo_root/sysu_official_launch"
roms_root="$repo_root/ROMS_CoSiNE15"
run_dir="$launch_dir/run_${SLURM_JOB_ID:?}"
binary="$launch_dir/oceanM"
input="$run_dir/ocean.in"
expected_sha=d1a7f5e3e27a0e11084451543410f89121bb2dcc905cc5772425e7b073cc67da

# 为本次作业建立独立结果目录。ROMS 和 Inputfiles 通过软链接引用原目录，
# 不复制、不改写官方源码及输入 NetCDF；新结果只写入 run_<job-id>/output。
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

# 按赛题要求，参数文件仅修改 MPI 分块。其余配置均保持官方原值，包括
# NTIMES=2592/12960、DT、NAVG、NDEFAVG、物理与生态配置、嵌套方式以及
# 所有输入文件名。
test "$(grep -Ec '^[[:space:]]*NtileI[[:space:]]*==' "$input")" -eq 1
test "$(grep -Ec '^[[:space:]]*NtileJ[[:space:]]*==' "$input")" -eq 1
sed -Ei \
  -e 's/^([[:space:]]*NtileI[[:space:]]*==).*/\1 6  6/' \
  -e 's/^([[:space:]]*NtileJ[[:space:]]*==).*/\1 16  16/' \
  "$input"

# 将每组连续 6 个进程（一个分块行）放在同一 NUMA 域，并按每个 L3 缓存
# 3 个进程均衡放置。这是已通过验证的 4 节点、96 进程绑核方案；它只调整
# CPU 亲和性，不改变 ROMS 的 6x16 分块。
mapfile -t hosts < <(scontrol show hostnames "$SLURM_JOB_NODELIST")
test "${#hosts[@]}" -eq 4
slots=(0 1 2 4 5 6 8 9 10 12 13 14 16 17 18 20 21 22 24 25 26 28 29 30)
rankfile="$run_dir/rankfile"
: > "$rankfile"
for ((rank=0; rank<96; rank++)); do
  printf 'rank %d=%s slot=%d\n' \
    "$rank" "${hosts[$((rank/24))]}" "${slots[$((rank%24))]}" >> "$rankfile"
done

# 执行官方完整时长模拟。resource.log 中 GNU time 的 wall-clock 时间为
# 性能计时结果；model.log 必须出现 ROMS/TOMS: DONE 才视为正常结束。
cd "$run_dir"
/usr/bin/time -v mpirun -np 96 --rankfile "$rankfile" \
  ./oceanM ocean.in > model.log 2> resource.log
grep -q 'ROMS/TOMS: DONE' model.log
test -s output/SCS_avg_0001.nc
test -s output/Dongsha60_avg_0001.nc

# 复制主办方验证脚本并且只修改一行：令 dir_test 指向本次输出目录。
# 官方参考目录、误差阈值和比较逻辑均保持不变；diff_status=1 用于确认
# 副本确实存在上述路径差异，同时排除未替换成功或 diff 执行错误。
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

# 执行官方验证，并检查脚本输出的最终通过结论；不只依赖 Python 退出码
# 判断数值结果是否正确。
source /public/share/mcc2026_final/miniforge3/etc/profile.d/conda.sh
conda activate vali
set -o pipefail
python "$validator" 2>&1 | tee vali_official.log
grep -Fq '最终判定：两组文件所有变量RMSE均在阈值范围内，优化结果无异常' vali_official.log

echo "PASS"
echo "run_dir=$run_dir"
grep 'Elapsed (wall clock)' resource.log
