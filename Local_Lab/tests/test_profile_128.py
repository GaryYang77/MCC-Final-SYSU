import json
from pathlib import Path
import sys

import pytest

import Local_Lab.profile_128 as profile_128
from Local_Lab.profile_128 import (
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

    with pytest.raises(ValueError, match=r"tiles_i \* tiles_j == 128"):
        validate_configuration(12, 60, 4, 8)
    with pytest.raises(ValueError, match="1:5"):
        validate_configuration(12, 59, 8, 16)


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
    )
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert path.name == "profile_bundle.json"
    assert payload["kind"] == "mcc_roms_profile_bundle"
    assert payload["run"] == run
    assert payload["profile"] == profile
    assert payload["comparison"] == comparison
    assert payload["overhead"]["overhead_percent"] == pytest.approx(0.89)


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
    monkeypatch.setattr(profile_128, "submit", lambda path: ("123", 0))

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
