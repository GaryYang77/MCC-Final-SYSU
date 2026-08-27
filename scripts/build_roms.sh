#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Build ROMS-CoSiNE LuTeam-HPC-Optimized with an MPI Fortran toolchain.

Usage:
  scripts/build_roms.sh

Environment variables:
  ROMS_SOURCE_DIR   Source tree (default: <repo>/ROMS_CoSiNE15)
  ROMS_BUILD_DIR    Object directory (default: <source>/Build_public)
  ROMS_BIN_DIR      Binary directory (default: <source>/bin_local)
  ROMS_BUILD_JOBS   Parallel make jobs (default: 8)
  ROMS_APPLICATION  ROMS application macro (default: BYE24BIO15)
  ROMS_FORT         Compiler rules suffix (default: ifort)
  ROMS_CPP_FLAGS    CPP flags, replacing the default -DMCC_NO_PROFILE;
                    set to an empty string to omit extra flags
  ROMS_CLEAN_BUILD  Set to 0 to reuse the build directory (default: 1)
  NF_CONFIG         nf-config executable (default: resolved from PATH)
  MAKE              GNU Make executable (default: make)
EOF
}

if [[ ${1:-} == "--help" || ${1:-} == "-h" ]]; then
  usage
  exit 0
fi
if (( $# != 0 )); then
  usage >&2
  exit 2
fi

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source_dir=${ROMS_SOURCE_DIR:-"$repo_root/ROMS_CoSiNE15"}
build_dir=${ROMS_BUILD_DIR:-"$source_dir/Build_public"}
bin_dir=${ROMS_BIN_DIR:-"$source_dir/bin_local"}
build_jobs=${ROMS_BUILD_JOBS:-8}
application=${ROMS_APPLICATION:-BYE24BIO15}
fort=${ROMS_FORT:-ifort}
cpp_flags=${ROMS_CPP_FLAGS--DMCC_NO_PROFILE}
clean_build=${ROMS_CLEAN_BUILD:-1}
make_command=${MAKE:-make}
nf_config=${NF_CONFIG:-nf-config}

if [[ ! $build_jobs =~ ^[1-9][0-9]*$ ]]; then
  echo "ROMS_BUILD_JOBS must be a positive integer: $build_jobs" >&2
  exit 2
fi
if [[ $clean_build != 0 && $clean_build != 1 ]]; then
  echo "ROMS_CLEAN_BUILD must be 0 or 1: $clean_build" >&2
  exit 2
fi
if [[ ! -f $source_dir/makefile ]]; then
  echo "ROMS makefile not found: $source_dir/makefile" >&2
  exit 2
fi
if ! command -v realpath >/dev/null 2>&1; then
  echo "required command is unavailable: realpath" >&2
  exit 2
fi

canonical_repo=$(realpath -m "$repo_root")
canonical_source=$(realpath -m "$source_dir")
canonical_build=$(realpath -m "$build_dir")
case "$canonical_build" in
  /|/tmp|"$canonical_repo"|"$canonical_source"|"${HOME:-/nonexistent}")
    echo "refusing unsafe ROMS_BUILD_DIR: $build_dir" >&2
    exit 2
    ;;
esac

for command_name in "$make_command" mpif90 "$nf_config"; do
  if [[ $command_name == */* ]]; then
    if [[ ! -x $command_name ]]; then
      echo "required executable is unavailable: $command_name" >&2
      exit 2
    fi
  elif ! command -v "$command_name" >/dev/null 2>&1; then
    echo "required command is unavailable: $command_name" >&2
    exit 2
  fi
done

mkdir -p "$bin_dir"
staging_dir=$(mktemp -d "$bin_dir/.roms-build.XXXXXX")
trap 'rm -rf -- "$staging_dir"' EXIT
staging_binary="$staging_dir/oceanM"
binary="$bin_dir/oceanM"

make_args=(
  -C "$source_dir"
  "ROMS_APPLICATION=$application"
  "SCRATCH_DIR=$build_dir"
  "MAKE_MACROS=$staging_dir/make_macros.mk"
  USE_MPI=on
  USE_MPIF90=on
  USE_NETCDF4=on
  "FORT=$fort"
  "NF_CONFIG=$nf_config"
)
if [[ -n $cpp_flags ]]; then
  make_args+=("MY_CPP_FLAGS=$cpp_flags")
fi

if [[ $clean_build == 1 ]]; then
  "$make_command" "${make_args[@]}" "BINDIR=$staging_dir" clean
fi

mkdir -p "$build_dir"
"$make_command" "${make_args[@]}" "BINDIR=$staging_dir" -j "$build_jobs"

if [[ ! -x $staging_binary ]]; then
  echo "build completed without producing an executable: $staging_binary" >&2
  exit 1
fi
mv -f "$staging_binary" "$binary"

echo "Build complete"
echo "  application: $application"
echo "  compiler rules: $fort"
echo "  objects: $build_dir"
echo "  binary: $binary"
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "$binary"
fi
