#!/bin/bash
# Start the full 1/2/4-node PROFILE sweep on the cluster login node.

set -euo pipefail

if [[ $# -lt 1 || $# -gt 3 ]]; then
  echo "usage: bash Local_Lab/start_full_profile_scaling_sweep.sh PROFILE_BINARY [LABEL] [TIME_LIMIT_PER_CASE]" >&2
  exit 2
fi

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd "$script_dir/.." && pwd)
binary=$1
label=${2:-full-scaling}
time_limit=${3:-12:00:00}

cd "$repo_root"
if [[ ! -f "$binary" ]]; then
  echo "PROFILE binary not found: $binary" >&2
  exit 2
fi

source /public/share/mcc2026_final/miniforge3/etc/profile.d/conda.sh
conda activate vali

log_dir="$repo_root/Local_Lab/cluster_logs"
mkdir -p "$log_dir"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
log_path="$log_dir/${label}_${stamp}.log"
pid_path="$log_dir/${label}_${stamp}.pid"

nohup python Local_Lab/profile_scaling_sweep.py \
  --binary "$binary" \
  --label "$label" \
  --time-limit "$time_limit" \
  > "$log_path" 2>&1 < /dev/null &
sweep_pid=$!
echo "$sweep_pid" > "$pid_path"

echo "[profile-scaling] background PID: $sweep_pid"
echo "[profile-scaling] log: $log_path"
echo "[profile-scaling] pid file: $pid_path"
echo "[profile-scaling] SSH may now be disconnected."
echo "[profile-scaling] monitor: tail -f $log_path"
