import json
from pathlib import Path
import sys

import pytest

import Local_Lab.profile_128 as profile_128
from Local_Lab.profile_128 import (
    allocation_summary,
    resource_summary,
    render_profile_input,
    validate_configuration,
    write_profile_bundle,
)


ROOT = Path(__file__).resolve().parents[2]


SAMPLE_INPUT = """\
      NtileI ==4  4 ! I tiles
      NtileJ ==8  8 ! J tiles
      NTIMES == 2592  12960 ! steps
        NAVG == 864  4320 ! average
     NDEFAVG == 864  4320 ! average file
"""


def test_render_profile_input_preserves_comments_and_sets_all_run_controls() -> None:
    rendered = render_profile_input(
        SAMPLE_INPUT,
        outer_steps=12,
        inner_steps=60,
        tiles_i=8,
        tiles_j=16,
    )

    assert "NtileI == 8  8 ! I tiles" in rendered
    assert "NtileJ == 16  16 ! J tiles" in rendered
    assert "NTIMES == 12  60 ! steps" in rendered
    assert "NAVG == 12  60 ! average" in rendered
    assert "NDEFAVG == 12  60 ! average file" in rendered


def test_128_rank_configuration_requires_128_tiles_and_nested_step_ratio() -> None:
    validate_configuration(12, 60, 8, 16)

    with pytest.raises(ValueError, match=r"tiles_i \* tiles_j == ranks"):
        validate_configuration(12, 60, 4, 8)
    with pytest.raises(ValueError, match="1:5"):
        validate_configuration(12, 59, 8, 16)


@pytest.mark.parametrize(
    ("nodes", "ranks", "tiles_i", "tiles_j"),
    ((1, 32, 4, 8), (2, 64, 8, 8), (4, 128, 8, 16)),
)
def test_scaling_configurations_fill_nodes_with_matching_tiles(
    nodes: int, ranks: int, tiles_i: int, tiles_j: int
) -> None:
    validate_configuration(
        2592,
        12960,
        tiles_i,
        tiles_j,
        nodes=nodes,
        ranks=ranks,
        preserve_output_cadence=True,
    )


def test_full_profile_preserves_canonical_output_cadence() -> None:
    rendered = render_profile_input(
        SAMPLE_INPUT,
        outer_steps=2592,
        inner_steps=12960,
        tiles_i=4,
        tiles_j=8,
        preserve_output_cadence=True,
    )

    assert "NTIMES == 2592  12960" in rendered
    assert "NAVG == 864  4320" in rendered
    assert "NDEFAVG == 864  4320" in rendered
    with pytest.raises(ValueError, match="only valid for the complete"):
        validate_configuration(
            12,
            60,
            4,
            8,
            nodes=1,
            ranks=32,
            preserve_output_cadence=True,
        )


def test_submit_overrides_sbatch_resources_for_requested_node_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    captured = {}

    class Result:
        returncode = 0
        stdout = "12345\n"

    def fake_run(command, **kwargs):
        captured["command"] = command
        return Result()

    monkeypatch.setattr(profile_128.subprocess, "run", fake_run)
    job_id, status = profile_128.submit(
        run_dir,
        nodes=2,
        ranks=64,
        time_limit="12:00:00",
        job_name="mcc-full-prof-2n",
    )

    command = captured["command"]
    assert (job_id, status) == ("12345", 0)
    assert command[command.index("--nodes") + 1] == "2"
    assert command[command.index("--ntasks") + 1] == "64"
    assert command[command.index("--ntasks-per-node") + 1] == "32"
    assert command[command.index("--time") + 1] == "12:00:00"


def test_submit_exports_bounded_diagnostic_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    captured = {}

    class Result:
        returncode = 0
        stdout = "12345\n"

    def fake_run(command, **kwargs):
        captured["command"] = command
        return Result()

    monkeypatch.setattr(profile_128.subprocess, "run", fake_run)
    profile_128.submit(
        run_dir,
        diagnostic_mode="trace",
        trace_ranks="0,16",
        trace_max_events=321,
    )

    export = next(
        item for item in captured["command"] if item.startswith("--export=")
    )
    assert "MCC_PROFILE_MODE=trace" in export
    assert f"MCC_PROFILE_DIAG_DIR={run_dir}" in export
    assert "MCC_TRACE_RANKS=0:16" in export
    assert "MCC_TRACE_MAX_EVENTS=321" in export


def test_resource_summary_exposes_dashboard_measurements(tmp_path: Path) -> None:
    resource_log = tmp_path / "resource.log"
    resource_log.write_text(
        "User time (seconds): 120.5\n"
        "System time (seconds): 7.25\n"
        "Elapsed (wall clock) time (h:mm:ss or m:ss): 4:01.80\n"
        "Maximum resident set size (kbytes): 784868\n",
        encoding="utf-8",
    )

    summary = resource_summary(resource_log)

    assert summary == {
        "elapsed_wall_seconds": pytest.approx(241.8),
        "user_seconds": pytest.approx(120.5),
        "system_seconds": pytest.approx(7.25),
        "max_rss_kib": 784868,
        "error": None,
    }


def test_allocation_summary_preserves_actual_slurm_nodes(tmp_path: Path) -> None:
    allocation_log = tmp_path / "allocation.log"
    allocation_log.write_text(
        "slurm_job_id=12345\n"
        "slurm_job_nodelist=j01r2n[16-19]\n"
        "slurm_job_num_nodes=4\n"
        "slurm_ntasks=128\n",
        encoding="utf-8",
    )

    assert allocation_summary(allocation_log) == {
        "slurm_job_id": "12345",
        "slurm_job_nodelist": "j01r2n[16-19]",
        "slurm_job_num_nodes": "4",
        "slurm_ntasks": "128",
    }


def test_profile_bundle_is_one_self_describing_json_file(tmp_path: Path) -> None:
    run = {"passed": True, "comparison": None}
    profile = {"groups": [], "records": []}
    comparison = {"passed": True, "metrics": {}}

    path = write_profile_bundle(
        tmp_path,
        run_report=run,
        profile=profile,
        comparison=comparison,
        overhead={"overhead_percent": 0.89},
        diagnostics={"schema_version": 2},
    )
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert path.name == "profile_bundle.json"
    assert payload["kind"] == "mcc_roms_profile_bundle"
    assert payload["run"] == run
    assert payload["profile"] == profile
    assert payload["comparison"] == comparison
    assert payload["overhead"]["overhead_percent"] == pytest.approx(0.89)
    assert payload["diagnostics"]["schema_version"] == 2


def test_no_profile_control_build_only_disables_instrumentation() -> None:
    build_source = (ROOT / "Local_Lab" / "build_no_profile.sbatch").read_text(
        encoding="utf-8"
    )
    globaldefs = (
        ROOT / "ROMS_CoSiNE15" / "ROMS" / "Include" / "globaldefs.h"
    ).read_text(encoding="utf-8")

    assert "MY_CPP_FLAGS=-DMCC_NO_PROFILE" in build_source
    assert "ROMS_APPLICATION=BYE24BIO15" in build_source
    assert "#ifdef MCC_NO_PROFILE" in globaldefs
    assert "# undef PROFILE" in globaldefs


def test_main_routes_profile_expectation_to_finalizer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = tmp_path / "oceanM"
    binary.touch()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    captured = {}

    monkeypatch.setattr(profile_128, "stage_run", lambda *args, **kwargs: run_dir)
    monkeypatch.setattr(
        profile_128, "submit", lambda *args, **kwargs: ("123", 0)
    )

    def fake_finalize(*args, **kwargs):
        captured.update(kwargs)
        return {"passed": True}

    monkeypatch.setattr(profile_128, "finalize_report", fake_finalize)
    monkeypatch.setattr(
        sys,
        "argv",
        ["profile_128.py", "--binary", str(binary), "--no-expect-profile"],
    )

    assert profile_128.main() == 0
    assert captured["expect_profile"] is False
    assert captured["reference_run"] is None
