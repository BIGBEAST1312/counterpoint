# Shared settings tests | Built by Aarya Patel (team lead), owned by no feature
# AI disclosure: first version generated with Claude (Anthropic); reviewed and edited by the team.
"""The settings every feature reads. These need nothing else, so they run from the very first merge."""
from app.core import config


def test_desk_time_is_saskatchewan_time():
    assert config.LOCAL_TZ.key == "America/Regina"


def test_eight_problem_types_and_two_counters():
    assert len(config.PROBLEM_TYPES) == 8 and config.PROBLEM_TYPES["wifi"] == "Wi-Fi (eduroam)"
    assert config.COUNTERS == ["Counter 1", "Counter 2"]


def test_default_hours_cover_every_weekday():
    assert sorted(config.DEFAULT_HOURS) == [0, 1, 2, 3, 4, 5, 6]
