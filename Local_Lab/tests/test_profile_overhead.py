from pathlib import Path

import pytest

import Local_Lab.profile_overhead as profile_overhead
from Local_Lab.profile_overhead import completed_job_status, elapsed_seconds


@pytest.mark.parametrize(
    ("encoded", "expected"),
    (("8:27.05", 507.05), ("1:02:03", 3723.0)),
)
def test_elapsed_seconds_parses_gnu_time_formats(
    tmp_path: Path, encoded: str, expected: float
) -> None:
    resource_log = tmp_path / "resource.log"
    resource_log.write_text(
        "Elapsed (wall clock) time (h:mm:ss or m:ss): " + encoded + "\n",
        encoding="utf-8",
    )
    assert elapsed_seconds(resource_log) == pytest.approx(expected)


def test_elapsed_seconds_rejects_missing_measurement(tmp_path: Path) -> None:
    resource_log = tmp_path / "resource.log"
    resource_log.write_text("no timing here\n", encoding="utf-8")
    with pytest.raises(ValueError, match="elapsed wall time missing"):
        elapsed_seconds(resource_log)


def test_completed_job_status_requires_completed_primary_state(monkeypatch) -> None:
    class Result:
        returncode = 0
        stdout = "COMPLETED|\n"

    monkeypatch.setattr(profile_overhead.subprocess, "run", lambda *args, **kwargs: Result())
    assert completed_job_status("123") == (True, "COMPLETED")
