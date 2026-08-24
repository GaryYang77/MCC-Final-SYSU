from __future__ import annotations

import json
from pathlib import Path

import netCDF4
import numpy as np

from tools.compare_netcdf import compare_directories, main


def _write_dataset(
    path: Path,
    *,
    values: np.ndarray | None = None,
    dtype: str = "f8",
    dimension: str = "x",
    fill_value: float | None = None,
    include_salt: bool = True,
) -> None:
    values = np.asarray([1.0, 2.0, 3.0] if values is None else values)
    path.parent.mkdir(parents=True, exist_ok=True)
    with netCDF4.Dataset(path, "w") as dataset:
        dataset.createDimension(dimension, values.size)
        kwargs = {"fill_value": fill_value} if fill_value is not None else {}
        temp = dataset.createVariable("temp", dtype, (dimension,), **kwargs)
        temp[:] = values
        if include_salt:
            salt = dataset.createVariable("salt", "f8", (dimension,))
            salt[:] = np.arange(values.size, dtype=np.float64)
        label = dataset.createVariable("label", str, (dimension,))
        label[:] = np.asarray(["a"] * values.size, dtype=object)


def test_identical_and_changed_values_report_metrics(tmp_path: Path) -> None:
    reference = tmp_path / "reference"
    candidate = tmp_path / "candidate"
    _write_dataset(reference / "avg.nc")
    _write_dataset(candidate / "avg.nc", values=np.asarray([1.0, 2.0, 4.0]))

    report = compare_directories(reference, candidate, [Path("avg.nc")])

    temp = report["files"]["avg.nc"]["variables"]["temp"]
    salt = report["files"]["avg.nc"]["variables"]["salt"]
    assert temp["exact_equal"] is False
    assert temp["rmse"] == np.sqrt(1.0 / 3.0)
    assert temp["max_abs"] == 1.0
    assert salt["exact_equal"] is True
    assert "label" not in report["files"]["avg.nc"]["variables"]


def test_exact_equal_uses_bit_patterns_not_only_numeric_equality(tmp_path: Path) -> None:
    reference = tmp_path / "reference"
    candidate = tmp_path / "candidate"
    _write_dataset(reference / "avg.nc", values=np.asarray([0.0]))
    _write_dataset(candidate / "avg.nc", values=np.asarray([-0.0]))

    report = compare_directories(reference, candidate, [Path("avg.nc")], ["temp"])
    result = report["files"]["avg.nc"]["variables"]["temp"]

    assert result["rmse"] == 0.0
    assert result["max_abs"] == 0.0
    assert result["exact_equal"] is False


def test_variable_selection_and_missing_variable_are_reported(tmp_path: Path) -> None:
    reference = tmp_path / "reference"
    candidate = tmp_path / "candidate"
    _write_dataset(reference / "avg.nc")
    _write_dataset(candidate / "avg.nc", include_salt=False)

    report = compare_directories(reference, candidate, [Path("avg.nc")], ["salt"])

    result = report["files"]["avg.nc"]["variables"]["salt"]
    assert result["issues"] == ["missing from candidate"]
    assert result["rmse"] is None


def test_dimension_shape_and_dtype_differences_are_reported(tmp_path: Path) -> None:
    reference = tmp_path / "reference"
    candidate = tmp_path / "candidate"
    _write_dataset(reference / "avg.nc", dtype="f8", dimension="x")
    _write_dataset(candidate / "avg.nc", values=np.asarray([1.0, 2.0]), dtype="f4", dimension="y")

    report = compare_directories(reference, candidate, [Path("avg.nc")], ["temp"])
    result = report["files"]["avg.nc"]["variables"]["temp"]

    assert result["issues"] == ["dimensions differ", "shape differs", "dtype differs"]
    assert result["rmse"] is None


def test_mask_difference_is_reported(tmp_path: Path) -> None:
    reference = tmp_path / "reference"
    candidate = tmp_path / "candidate"
    fill = -9999.0
    _write_dataset(reference / "avg.nc", values=np.asarray([1.0, fill, 3.0]), fill_value=fill)
    _write_dataset(candidate / "avg.nc", values=np.asarray([1.0, 2.0, 3.0]), fill_value=fill)

    report = compare_directories(reference, candidate, [Path("avg.nc")], ["temp"])
    result = report["files"]["avg.nc"]["variables"]["temp"]

    assert result["mask_equal"] is False
    assert "missing-value mask differs" in result["issues"]
    assert result["rmse"] is None


def test_nan_and_infinity_are_reported_without_nonstandard_json(tmp_path: Path) -> None:
    reference = tmp_path / "reference"
    candidate = tmp_path / "candidate"
    _write_dataset(reference / "avg.nc", values=np.asarray([1.0, np.nan, 3.0]))
    _write_dataset(candidate / "avg.nc", values=np.asarray([1.0, np.inf, 3.0]))

    report = compare_directories(reference, candidate, [Path("avg.nc")], ["temp"])
    result = report["files"]["avg.nc"]["variables"]["temp"]

    assert "reference contains NaN or infinity" in result["issues"]
    assert "candidate contains NaN or infinity" in result["issues"]
    encoded = json.dumps(report, allow_nan=False)
    assert '"rmse": null' in encoded
    assert '"max_abs": null' in encoded


def test_cli_writes_json_and_does_not_assign_pass_fail(tmp_path: Path, capsys) -> None:
    reference = tmp_path / "reference"
    candidate = tmp_path / "candidate"
    report_path = tmp_path / "reports" / "comparison.json"
    _write_dataset(reference / "avg.nc")
    _write_dataset(candidate / "avg.nc")

    exit_code = main([
        str(reference), str(candidate), "--file", "avg.nc", "--json", str(report_path)
    ])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert report_path.is_file()
    assert json.loads(report_path.read_text(encoding="utf-8"))["schema_version"] == 1
    assert "PASS" not in output
    assert "FAIL" not in output


def test_cli_returns_nonzero_for_missing_file(tmp_path: Path, capsys) -> None:
    exit_code = main([
        str(tmp_path / "reference"), str(tmp_path / "candidate"), "--file", "missing.nc"
    ])

    assert exit_code == 2
    assert "does not exist" in capsys.readouterr().err


def test_cli_returns_nonzero_for_unreadable_netcdf(tmp_path: Path, capsys) -> None:
    reference = tmp_path / "reference"
    candidate = tmp_path / "candidate"
    reference.mkdir()
    candidate.mkdir()
    (reference / "broken.nc").write_text("not NetCDF", encoding="utf-8")
    (candidate / "broken.nc").write_text("not NetCDF", encoding="utf-8")

    exit_code = main([
        str(reference), str(candidate), "--file", "broken.nc"
    ])

    assert exit_code == 2
    assert "cannot read NetCDF pair" in capsys.readouterr().err
