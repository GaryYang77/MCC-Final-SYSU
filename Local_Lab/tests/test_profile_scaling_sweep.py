import json
from pathlib import Path

import pytest

import Local_Lab.profile_scaling_sweep as sweep


def test_scaling_matrix_is_full_node_occupancy_with_reviewed_tiles() -> None:
    assert [
        (case.nodes, case.ranks, case.tiles_i, case.tiles_j)
        for case in sweep.SCALING_CASES
    ] == [(1, 32, 4, 8), (2, 64, 8, 8), (4, 128, 8, 16)]


def test_sweep_runs_all_cases_in_order_and_collects_one_bundle_each(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = tmp_path / "oceanM"
    binary.touch()
    monkeypatch.setattr(sweep, "SWEEPS_ROOT", tmp_path / "sweeps")
    staged = []
    submitted = []

    def fake_stage(binary_path, **kwargs):
        run_dir = tmp_path / f"run-{kwargs['nodes']}"
        run_dir.mkdir()
        staged.append(kwargs)
        return run_dir

    def fake_submit(run_dir, **kwargs):
        submitted.append(kwargs)
        return f"job-{kwargs['nodes']}", 0

    def fake_finalize(run_dir, **kwargs):
        (run_dir / "profile_bundle.json").write_text(
            json.dumps({"kind": "mcc_roms_profile_bundle"}), encoding="utf-8"
        )
        return {
            "passed": True,
            "normal_end": True,
            "resources": {"elapsed_wall_seconds": 1000.0 / kwargs["nodes"]},
            "comparison": (
                {"passed": True} if kwargs["reference_run"] is not None else None
            ),
        }

    monkeypatch.setattr(sweep, "stage_run", fake_stage)
    monkeypatch.setattr(sweep, "submit", fake_submit)
    monkeypatch.setattr(sweep, "finalize_report", fake_finalize)

    passed, manifest_path = sweep.run_sweep(
        binary, label="nightly", time_limit="12:00:00"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert passed
    assert [item["nodes"] for item in staged] == [1, 2, 4]
    assert [item["ranks"] for item in staged] == [32, 64, 128]
    assert all(item["preserve_output_cadence"] for item in staged)
    assert [item["nodes"] for item in submitted] == [1, 2, 4]
    assert len(manifest["cases"]) == 3
    assert all(Path(item["bundle"]).is_file() for item in manifest["cases"])
    assert manifest["full_simulation"] == {
        "outer_steps": 2592,
        "inner_steps": 12960,
        "preserve_official_output_cadence": True,
    }


def test_background_launcher_is_disconnect_safe_and_never_runs_baseline() -> None:
    launcher = (
        Path(__file__).resolve().parents[1]
        / "start_full_profile_scaling_sweep.sh"
    ).read_text(encoding="utf-8")

    assert "nohup python Local_Lab/profile_scaling_sweep.py" in launcher
    assert "conda activate vali" in launcher
    assert "baseline" not in launcher
    assert "2592" not in launcher  # full steps are owned by the Python orchestrator
