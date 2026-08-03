from pathlib import Path

import netCDF4
import numpy as np
import pytest

import Local_Lab.valid_test as validation
from Local_Lab.valid_test import (
    VALIDATION_VARIABLES,
    compare_output_directories,
    create_baseline_manifest,
    render_demo_input,
    verify_baseline_integrity,
)


OUTPUT_FILES = ("SCS_avg_0001.nc", "Dongsha60_avg_0001.nc")


def _write_outputs(directory: Path, changed_value: float = 0.0) -> None:
    directory.mkdir(parents=True)
    for filename in OUTPUT_FILES:
        with netCDF4.Dataset(directory / filename, "w") as dataset:
            dataset.createDimension("ocean_time", 1)
            dataset.createDimension("point", 2)
            for name in VALIDATION_VARIABLES:
                variable = dataset.createVariable(name, "f8", ("ocean_time", "point"))
                variable[:] = np.array([[1.0, 2.0]])
            if filename.startswith("SCS"):
                dataset.variables["temp"][0, 0] += changed_value


def test_comparison_rejects_a_pointwise_error_above_tolerance(tmp_path: Path) -> None:
    reference = tmp_path / "reference"
    candidate = tmp_path / "candidate"
    _write_outputs(reference)
    _write_outputs(candidate, changed_value=2.0e-5)

    report = compare_output_directories(reference, candidate, tolerance=1.0e-5)

    assert not report.passed
    assert report.metrics["SCS_avg_0001.nc"]["temp"].max_abs > 1.0e-5


def test_demo_input_keeps_unneeded_output_settings_at_official_values() -> None:
    source = """\
      NtileI ==4  4 ! partition
      NtileJ ==8  8 ! partition
      NTIMES == 2592  12960 ! three days
          DT == 100.0d0 20.0d0
        NRST == 864 4320
       NINFO == 15 45
        NHIS == 864 4320
     NDEFHIS == 864 4320
        NAVG == 864 4320
     NDEFAVG == 864 4320
"""

    rendered = render_demo_input(source)

    assert "NtileI == 1  1" in rendered
    assert "NtileJ == 1  1" in rendered
    assert "NTIMES == 4  20" in rendered
    assert "NRST == 864 4320" in rendered
    assert "NHIS == 864 4320" in rendered
    assert "NDEFHIS == 864 4320" in rendered
    assert "NAVG == 4  20" in rendered
    assert "NDEFAVG == 4  20" in rendered
    assert "NINFO == 15 45" in rendered
    assert "DT == 100.0d0 20.0d0" in rendered


def test_baseline_integrity_detects_an_overwritten_output(tmp_path: Path) -> None:
    baseline = tmp_path / "mcc_4x20"
    outputs = baseline / "outputs_valid"
    _write_outputs(outputs)
    create_baseline_manifest(baseline, metadata={"source_commit": "abc123"})

    with netCDF4.Dataset(outputs / OUTPUT_FILES[0], "a") as dataset:
        dataset.variables["temp"][0, 0] = 99.0

    failures = verify_baseline_integrity(baseline)

    assert failures == (f"baseline hash mismatch: {OUTPUT_FILES[0]}",)


def test_validate_cli_dispatches_to_the_same_validation_workflow(monkeypatch) -> None:
    expected = validation.ValidationReport(True, {}, ())
    calls = []

    def fake_validate_candidate():
        calls.append("validate")
        return expected, Path("validation_report.json")

    monkeypatch.setattr(validation, "validate_candidate", fake_validate_candidate)

    assert validation._main(["validate"]) == 0
    assert calls == ["validate"]


def test_baseline_creation_refuses_to_overwrite_an_existing_baseline(
    tmp_path: Path, monkeypatch
) -> None:
    existing = tmp_path / "mcc_4x20"
    existing.mkdir()
    monkeypatch.setattr(validation, "BASELINE_ROOT", existing)

    with pytest.raises(RuntimeError, match="will not be overwritten"):
        validation.create_baseline()
