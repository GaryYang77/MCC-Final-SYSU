from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = REPOSITORY / "scripts" / "build_roms.sh"
SLURM_EXAMPLE = REPOSITORY / "examples" / "slurm" / "scs_dongsha60.sbatch"
ROMS_BUILD_HELPERS = (
    REPOSITORY / "ROMS_CoSiNE15" / "ROMS" / "Bin" / "cpp_clean",
    REPOSITORY / "ROMS_CoSiNE15" / "ROMS" / "Bin" / "sfmakedepend",
)


def _executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def test_public_shell_scripts_have_valid_syntax() -> None:
    for script in (BUILD_SCRIPT, SLURM_EXAMPLE):
        subprocess.run(["bash", "-n", str(script)], check=True)


def test_roms_build_helpers_are_executable() -> None:
    for helper in ROMS_BUILD_HELPERS:
        assert os.access(helper, os.X_OK), f"build helper is not executable: {helper}"


def test_build_script_passes_portable_make_configuration(tmp_path: Path) -> None:
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    make_log = tmp_path / "make.log"
    _executable(
        fake_bin / "make",
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "$FAKE_MAKE_LOG"
bin_dir=
clean=0
for argument in "$@"; do
  case "$argument" in
    BINDIR=*) bin_dir=${argument#BINDIR=} ;;
    clean) clean=1 ;;
  esac
done
if (( clean == 0 )); then
  mkdir -p "$bin_dir"
  printf '#!/usr/bin/env bash\\nexit 0\\n' > "$bin_dir/oceanM"
  chmod +x "$bin_dir/oceanM"
fi
""",
    )
    for command in ("mpif90", "nf-config"):
        _executable(fake_bin / command, "#!/usr/bin/env bash\nexit 0\n")

    build_dir = tmp_path / "objects"
    bin_dir = tmp_path / "output-bin"
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{fake_bin}:{environment['PATH']}",
            "FAKE_MAKE_LOG": str(make_log),
            "ROMS_BUILD_DIR": str(build_dir),
            "ROMS_BIN_DIR": str(bin_dir),
            "ROMS_BUILD_JOBS": "3",
        }
    )

    result = subprocess.run(
        [str(BUILD_SCRIPT)],
        cwd=REPOSITORY,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    calls = make_log.read_text(encoding="utf-8").splitlines()
    assert len(calls) == 2
    assert " clean" in f" {calls[0]}"
    assert f"BINDIR={bin_dir}" not in calls[0].split()
    assert "USE_MPI=on" in calls[1]
    assert "USE_MPIF90=on" in calls[1]
    assert "USE_NETCDF4=on" in calls[1]
    assert "FORT=ifort" in calls[1]
    make_macros_argument = next(
        argument for argument in calls[1].split() if argument.startswith("MAKE_MACROS=")
    )
    make_macros = Path(make_macros_argument.removeprefix("MAKE_MACROS="))
    assert make_macros.parent.parent == bin_dir
    assert make_macros.parent.name.startswith(".roms-build.")
    assert "MY_CPP_FLAGS=-DMCC_NO_PROFILE" in calls[1]
    assert "-j 3" in calls[1]
    assert (bin_dir / "oceanM").is_file()
    assert "Build complete" in result.stdout


def test_build_script_rejects_an_unsafe_clean_directory() -> None:
    environment = os.environ.copy()
    environment["ROMS_BUILD_DIR"] = str(REPOSITORY)

    result = subprocess.run(
        [str(BUILD_SCRIPT)],
        cwd=REPOSITORY,
        env=environment,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "refusing unsafe ROMS_BUILD_DIR" in result.stderr


def test_failed_build_preserves_the_previous_binary(tmp_path: Path) -> None:
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    for command in ("make", "mpif90", "nf-config"):
        _executable(fake_bin / command, "#!/usr/bin/env bash\nexit 0\n")

    bin_dir = tmp_path / "output-bin"
    bin_dir.mkdir()
    previous_binary = bin_dir / "oceanM"
    _executable(previous_binary, "#!/usr/bin/env bash\necho previous\n")
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{fake_bin}:{environment['PATH']}",
            "ROMS_BUILD_DIR": str(tmp_path / "objects"),
            "ROMS_BIN_DIR": str(bin_dir),
            "ROMS_CLEAN_BUILD": "0",
        }
    )

    result = subprocess.run(
        [str(BUILD_SCRIPT)],
        cwd=REPOSITORY,
        env=environment,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert previous_binary.read_text(encoding="utf-8").endswith("echo previous\n")


def test_slurm_example_prepares_and_checks_an_isolated_run(tmp_path: Path) -> None:
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    _executable(
        fake_bin / "srun",
        """#!/usr/bin/env bash
set -euo pipefail
mkdir -p output
printf 'scs\\n' > output/SCS_avg_0001.nc
printf 'dongsha\\n' > output/Dongsha60_avg_0001.nc
echo 'ROMS/TOMS: DONE'
""",
    )

    binary = tmp_path / "oceanM"
    _executable(binary, "#!/usr/bin/env bash\nexit 0\n")
    inputfiles = tmp_path / "Inputfiles"
    (inputfiles / "SCS").mkdir(parents=True)
    (inputfiles / "Dongsha60").mkdir()
    (inputfiles / "SCS" / "SCS_grd.nc").touch()
    (inputfiles / "Dongsha60" / "Dongsha60_grd.nc").touch()
    runs_root = tmp_path / "runs"

    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{fake_bin}:{environment['PATH']}",
            "SLURM_SUBMIT_DIR": str(REPOSITORY),
            "SLURM_JOB_ID": "12345",
            "SLURM_NTASKS": "96",
            "ROMS_BINARY": str(binary),
            "ROMS_INPUTFILES": str(inputfiles),
            "ROMS_RUNS_DIR": str(runs_root),
        }
    )

    result = subprocess.run(
        ["bash", str(SLURM_EXAMPLE)],
        cwd=REPOSITORY,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    run_dir = runs_root / "scs_dongsha60_12345"
    ocean_input = (run_dir / "ocean.in").read_text(encoding="utf-8")
    assert "NtileI == 6  6" in ocean_input
    assert "NtileJ == 16  16" in ocean_input
    assert (run_dir / "output" / "SCS_avg_0001.nc").stat().st_size > 0
    assert (run_dir / "output" / "Dongsha60_avg_0001.nc").stat().st_size > 0
    assert "Run complete" in result.stdout


def test_slurm_example_rejects_a_tile_rank_mismatch(tmp_path: Path) -> None:
    environment = os.environ.copy()
    environment.update(
        {
            "SLURM_SUBMIT_DIR": str(REPOSITORY),
            "SLURM_JOB_ID": "54321",
            "SLURM_NTASKS": "96",
            "ROMS_TILES_I": "4",
            "ROMS_TILES_J": "8",
            "ROMS_RUNS_DIR": str(tmp_path / "runs"),
        }
    )

    result = subprocess.run(
        ["bash", str(SLURM_EXAMPLE)],
        cwd=REPOSITORY,
        env=environment,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "does not match 96 MPI ranks" in result.stderr
