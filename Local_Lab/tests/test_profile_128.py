import pytest

from Local_Lab.profile_128 import render_profile_input, validate_configuration


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
