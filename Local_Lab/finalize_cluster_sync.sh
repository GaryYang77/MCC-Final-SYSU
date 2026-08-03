#!/bin/bash
set -euo pipefail

local_commit="${1:?local commit is required}"
local_status_sha256="${2:?local status hash is required}"
input_root="${3:?input root is required}"
repo_root=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo_root"

test -d "$input_root"
mkdir -p Local_Lab/cluster_logs
if [[ ! -e ROMS_CoSiNE15/Inputfiles ]]; then
  ln -s "$input_root" ROMS_CoSiNE15/Inputfiles
fi
test -d ROMS_CoSiNE15/Inputfiles

printf 'local_commit=%s\nlocal_status_sha256=%s\nsynced_utc=%s\n' \
  "$local_commit" "$local_status_sha256" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  > Local_Lab/deployment_state.txt

if [[ ! -d .git ]]; then
  git init >/dev/null
  git config user.name 'MCC Cluster Gate'
  git config user.email 'mcc-cluster-gate@localhost'
fi
mkdir -p .git/info
grep -qxF '/Local_Lab/baselines/' .git/info/exclude 2>/dev/null || \
  echo '/Local_Lab/baselines/' >> .git/info/exclude

git add -A
if git rev-parse --verify HEAD >/dev/null 2>&1; then
  git commit --amend --no-gpg-sign --allow-empty \
    -m "deploy local ${local_commit}" >/dev/null
else
  git commit --no-gpg-sign -m "deploy local ${local_commit}" >/dev/null
fi

echo "[sync] remote_snapshot=$(git rev-parse HEAD)"
echo "[sync] local_commit=${local_commit}"
echo "[sync] local_status_sha256=${local_status_sha256}"
