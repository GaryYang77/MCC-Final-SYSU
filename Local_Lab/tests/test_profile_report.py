import csv
import json
from pathlib import Path

import pytest

from Local_Lab.profile_report import build_report, parse_profile_lines, write_csv


SAMPLE = """\
unrelated ROMS output
PROFILE_RANK grid=1 model=1 region=0 kind=total    calls=        128. wall_min=7.0E+01 wall_mean=7.2E+01 wall_max=7.4E+01 wall_max_rank=7 cpu_min=6.0E+01 cpu_mean=6.2E+01 cpu_max=6.4E+01 imbalance=1.027778
PROFILE_RANK grid=1 model=1 region=8 kind=io_write calls=        256. wall_min=0.0E+00 wall_mean=2.0E+00 wall_max=8.0E+00 wall_max_rank=0 cpu_min=0.0E+00 cpu_mean=1.0E+00 cpu_max=4.0E+00 imbalance=4.0
PROFILE_RANK grid=1 model=1 region=15 kind=compute  calls=       1280. wall_min=1.0E+01 wall_mean=1.2E+01 wall_max=1.4E+01 wall_max_rank=9 cpu_min=9.0E+00 cpu_mean=1.1E+01 cpu_max=1.3E+01 imbalance=1.166667
"""


def test_parse_profile_lines_handles_padded_fixed_format_fields() -> None:
    records = parse_profile_lines(SAMPLE.splitlines())

    assert len(records) == 3
    assert records[0].calls == 128
    assert records[1].kind == "io_write"
    assert records[2].wall_max_rank == 9


def test_report_derives_workers_categories_and_per_call_cost() -> None:
    report = build_report(parse_profile_lines(SAMPLE.splitlines()), "model.log", top=2)
    group = report["groups"][0]

    assert report["accounting"] == "inclusive"
    assert report["cpu_timing"] == "enabled"
    assert group["workers"] == 128
    assert group["categories"]["io_write"]["inclusive_wall_mean_sum"] == 2.0
    assert group["hotspots"][0]["region"] == 15
    assert group["hotspots"][0]["region_name"] == "biology_source_sink"
    assert group["hotspots"][0]["calls_per_rank"] == 10.0
    assert group["hotspots"][0]["wall_mean_per_call"] == pytest.approx(1.2)


def test_csv_and_json_reports_are_machine_readable(tmp_path: Path) -> None:
    records = parse_profile_lines(SAMPLE.splitlines())
    csv_path = tmp_path / "profile.csv"
    json_path = tmp_path / "profile.json"

    write_csv(records, csv_path)
    json_path.write_text(json.dumps(build_report(records, "model.log")), encoding="utf-8")

    with csv_path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[1]["kind"] == "io_write"
    assert rows[1]["region_name"] == "output_io_define_write_sync_close"
    assert json.loads(json_path.read_text(encoding="utf-8"))["schema_version"] == 1


def test_malformed_profile_record_is_rejected() -> None:
    with pytest.raises(ValueError, match="missing PROFILE_RANK fields"):
        parse_profile_lines(["PROFILE_RANK grid=1 model=1"])


def test_report_exposes_mutually_exclusive_nesting_section_breakdown() -> None:
    sample = SAMPLE + """\
PROFILE_RANK grid=1 model=1 region=39 kind=compute calls=256 wall_min=20 wall_mean=24 wall_max=28 wall_max_rank=3 cpu_min=0 cpu_mean=0 cpu_max=0 imbalance=1.166667
PROFILE_RANK grid=1 model=1 region=53 kind=compute calls=128 wall_min=8 wall_mean=10 wall_max=12 wall_max_rank=3 cpu_min=0 cpu_mean=0 cpu_max=0 imbalance=1.2
PROFILE_RANK grid=1 model=1 region=54 kind=compute calls=128 wall_min=10 wall_mean=12 wall_max=14 wall_max_rank=4 cpu_min=0 cpu_mean=0 cpu_max=0 imbalance=1.166667
"""
    group = build_report(parse_profile_lines(sample.splitlines()), "model.log")[
        "groups"
    ][0]

    assert [item["region_name"] for item in group["nesting_sections"]] == [
        "nesting_put_receiver_data",
        "nesting_get_donor_data",
    ]
    assert group["nesting_sections"][0]["inclusive_percent_of_nesting"] == 50.0
    assert not any(51 <= item["region"] <= 56 for item in group["hotspots"])
    assert group["categories"]["compute"]["inclusive_wall_mean_sum"] == 36.0
    assert group["nesting_coverage"]["calls_match"] is True
    assert group["nesting_coverage"]["detail_percent_of_nesting"] == pytest.approx(
        100.0 * 22.0 / 24.0
    )
