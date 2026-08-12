#!/bin/bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
remote_host="fangxihong@cancon.hpccube.com"
remote_port=65023
remote_key="${HOME}/.ssh/fangxihong_key"
remote_root="${MCC_REMOTE_ROOT:-/public/home/fangxihong/MCC-Final-SYSU}"
remote_inputs="/public/home/fangxihong/ROMS_CoSiNE15/Inputfiles"
local_commit=$(git -C "$repo_root" rev-parse HEAD)
local_status_sha256=$(git -C "$repo_root" status --porcelain | sha256sum | cut -d' ' -f1)

test -f "$remote_key"
cd "$repo_root"

rsync -az --delete --info=stats2 \
  -e "ssh -i ${remote_key} -p ${remote_port}" \
  --exclude '/ROMS_CoSiNE15.tar' \
  --exclude '/miniforge3/' \
  --exclude '/.git/' \
  --exclude '/.git' \
  --exclude '/.agents/' \
  --exclude '/.codex/' \
  --exclude '/__pycache__/' \
  --exclude '/ROMS_CoSiNE15/Inputfiles' \
  --exclude '/ROMS_CoSiNE15/Data/' \
  --exclude '/ROMS_CoSiNE15/plot/Data/' \
  --exclude '/ROMS_CoSiNE15/output/' \
  --exclude '/ROMS_CoSiNE15/Reference/' \
  --exclude '/ROMS_CoSiNE15/Build*/' \
  --exclude '/ROMS_CoSiNE15/bin_local/' \
  --exclude '/ROMS_CoSiNE15/local_demo/' \
  --exclude '/ROMS_CoSiNE15/test/**/Data/' \
  --exclude '/Local_Lab/bin/' \
  --exclude '/Local_Lab/builds/' \
  --exclude '/Local_Lab/runs/' \
  --exclude '/Local_Lab/baselines/' \
  --exclude '/Local_Lab/cluster_logs/' \
  --exclude '/Local_Lab/deployment_state.txt' \
  --exclude '/sysu_official_launch/run_*/' \
  --exclude '/sysu_official_launch/slurm_*.out' \
  --exclude '/sysu_official_launch/slurm_*.err' \
  --exclude '/output/' \
  --exclude '*.nc' \
  --exclude '*.nc4' \
  --exclude '*.o' \
  --exclude '*.mod' \
  --exclude '*.a' \
  --exclude '.svn/' \
  ./ "${remote_host}:${remote_root}/"

ssh -i "$remote_key" -p "$remote_port" "$remote_host" \
  "cd '${remote_root}' && bash Local_Lab/finalize_cluster_sync.sh '${local_commit}' '${local_status_sha256}' '${remote_inputs}'"

echo "[sync] deployed tracked code to ${remote_host}:${remote_root}"
echo "[sync] preserved server baselines, runs, builds, logs, and shared Inputfiles"
