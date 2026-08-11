import ast
from pathlib import Path

import netCDF4
import numpy as np
import pytest

import Local_Lab.valid_test as validation
from Local_Lab.valid_test import (
    EXACT_COMPARISON,
    NUMERICAL_COMPARISON,
    OFFICIAL_RMSE_THRESHOLDS,
    VALIDATION_VARIABLES,
    compare_output_directories,
    create_baseline_manifest,
    render_demo_input,
    verify_baseline_integrity,
)


OUTPUT_FILES = ("SCS_avg_0001.nc", "Dongsha60_avg_0001.nc")
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


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


def _add_uniform_difference(
    directory: Path, filename: str, variable_name: str, difference: float
) -> None:
    with netCDF4.Dataset(directory / filename, "a") as dataset:
        dataset.variables[variable_name][:] += difference


def test_comparison_rejects_a_pointwise_error_above_tolerance(tmp_path: Path) -> None:
    reference = tmp_path / "reference"
    candidate = tmp_path / "candidate"
    _write_outputs(reference)
    _write_outputs(candidate, changed_value=2.0e-5)

    report = compare_output_directories(reference, candidate, tolerance=1.0e-5)

    assert not report.passed
    assert report.metrics["SCS_avg_0001.nc"]["temp"].max_abs > 1.0e-5
    metrics = report.metrics["SCS_avg_0001.nc"]["temp"]
    assert metrics.reference.minimum == pytest.approx(1.0)
    assert metrics.reference.mean == pytest.approx(1.5)
    assert metrics.reference.maximum == pytest.approx(2.0)
    assert metrics.candidate.minimum > metrics.reference.minimum
    assert metrics.reference.valid_count == 2
    assert metrics.reference.masked_count == 0


def test_numerical_comparison_accepts_error_allowed_by_official_rmse(
    tmp_path: Path,
) -> None:
    reference = tmp_path / "reference"
    candidate = tmp_path / "candidate"
    _write_outputs(reference)
    _write_outputs(candidate)
    _add_uniform_difference(candidate, "SCS_avg_0001.nc", "temp", 2.0e-5)

    exact = compare_output_directories(
        reference, candidate, comparison_mode=EXACT_COMPARISON
    )
    numerical = compare_output_directories(
        reference, candidate, comparison_mode=NUMERICAL_COMPARISON
    )

    assert not exact.passed
    assert numerical.passed
    metric = numerical.metrics["SCS_avg_0001.nc"]["temp"]
    assert metric.comparison_mode == NUMERICAL_COMPARISON
    assert metric.rmse_threshold == pytest.approx(0.00150)
    assert metric.max_abs_threshold is None
    assert metric.threshold_ratio == pytest.approx(metric.rmse / 0.00150)


def test_numerical_comparison_uses_file_specific_variable_threshold(
    tmp_path: Path,
) -> None:
    reference = tmp_path / "reference"
    candidate = tmp_path / "candidate"
    _write_outputs(reference)
    _write_outputs(candidate)
    _add_uniform_difference(candidate, "Dongsha60_avg_0001.nc", "u", 7.0e-5)

    report = compare_output_directories(
        reference, candidate, comparison_mode=NUMERICAL_COMPARISON
    )

    assert not report.passed
    metric = report.metrics["Dongsha60_avg_0001.nc"]["u"]
    assert metric.rmse == pytest.approx(7.0e-5)
    assert metric.rmse_threshold == pytest.approx(6.0e-5)
    assert metric.max_abs == pytest.approx(7.0e-5)
    assert "official_threshold" in report.failures[0]


def test_numerical_comparison_reports_max_abs_without_using_it_as_official_gate(
    tmp_path: Path,
) -> None:
    reference = tmp_path / "reference"
    candidate = tmp_path / "candidate"
    _write_outputs(reference)
    _write_outputs(candidate)
    with netCDF4.Dataset(candidate / "SCS_avg_0001.nc", "a") as dataset:
        dataset.variables["TIC"][0, 0] += 0.6

    report = compare_output_directories(
        reference, candidate, comparison_mode=NUMERICAL_COMPARISON
    )

    metric = report.metrics["SCS_avg_0001.nc"]["TIC"]
    assert report.passed
    assert metric.rmse < metric.rmse_threshold
    assert metric.max_abs > metric.rmse_threshold
    assert metric.max_abs_threshold is None


def test_numerical_comparison_keeps_nonfinite_values_as_hard_failure(
    tmp_path: Path,
) -> None:
    reference = tmp_path / "reference"
    candidate = tmp_path / "candidate"
    _write_outputs(reference)
    _write_outputs(candidate)
    with netCDF4.Dataset(candidate / "SCS_avg_0001.nc", "a") as dataset:
        dataset.variables["temp"][0, 0] = np.nan

    report = compare_output_directories(
        reference, candidate, comparison_mode=NUMERICAL_COMPARISON
    )

    assert not report.passed
    assert any("contains NaN or infinity" in failure for failure in report.failures)


def test_official_threshold_table_matches_organizer_validator() -> None:
    tree = ast.parse((REPOSITORY_ROOT / "vali.py").read_text(encoding="utf-8"))
    assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "var_threshold_dict"
            for target in node.targets
        )
    )
    official_pairs = ast.literal_eval(assignment.value)
    expected = {
        "SCS_avg_0001.nc": {
            variable: thresholds[0]
            for variable, thresholds in official_pairs.items()
        },
        "Dongsha60_avg_0001.nc": {
            variable: thresholds[1]
            for variable, thresholds in official_pairs.items()
        },
    }

    assert OFFICIAL_RMSE_THRESHOLDS == expected


def test_comparison_rejects_unknown_mode(tmp_path: Path) -> None:
    reference = tmp_path / "reference"
    candidate = tmp_path / "candidate"
    _write_outputs(reference)
    _write_outputs(candidate)

    with pytest.raises(ValueError, match="unsupported comparison mode"):
        compare_output_directories(reference, candidate, comparison_mode="relaxed")


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

    def fake_validate_candidate(*, comparison_mode):
        assert comparison_mode == EXACT_COMPARISON
        calls.append("validate")
        return expected, Path("validation_report.json")

    monkeypatch.setattr(validation, "validate_candidate", fake_validate_candidate)

    assert validation._main(["validate"]) == 0
    assert calls == ["validate"]


def test_validate_cli_selects_numerical_comparison(monkeypatch) -> None:
    expected = validation.ValidationReport(
        True, {}, (), comparison_mode=NUMERICAL_COMPARISON
    )
    calls = []

    def fake_validate_candidate(*, comparison_mode):
        calls.append(comparison_mode)
        return expected, Path("validation_report.json")

    monkeypatch.setattr(validation, "validate_candidate", fake_validate_candidate)

    assert validation._main(["validate", "--comparison-mode", "numerical"]) == 0
    assert calls == [NUMERICAL_COMPARISON]


def test_build_cli_dispatches_to_clean_profile_build(monkeypatch) -> None:
    calls = []

    def fake_build_profile_candidate():
        calls.append("build")
        return Path("bin/oceanM"), Path("build_report.json")

    monkeypatch.setattr(validation, "build_profile_candidate", fake_build_profile_candidate)

    assert validation._main(["build"]) == 0
    assert calls == ["build"]


def test_baseline_creation_refuses_to_overwrite_an_existing_baseline(
    tmp_path: Path, monkeypatch
) -> None:
    existing = tmp_path / "mcc_4x20"
    existing.mkdir()
    monkeypatch.setattr(validation, "BASELINE_ROOT", existing)

    with pytest.raises(RuntimeError, match="will not be overwritten"):
        validation.create_baseline()


def test_cluster_profile_uses_official_intel_mpi_toolchain(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv(validation.PROFILE_ENVIRONMENT_VARIABLE, validation.CLUSTER_PROFILE)
    monkeypatch.setattr(validation.shutil, "which", lambda name: f"/tools/{name}")

    command = validation._build_command(tmp_path / "build", tmp_path / "bin")

    assert "FORT=ifort" in command
    assert "USE_MPIF90=on" in command
    assert "NF_CONFIG=/tools/nf-config" in command
    assert not any(argument.startswith("FFLAGS=") for argument in command)
