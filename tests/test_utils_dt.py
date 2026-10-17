from datetime import datetime

import pytest

from utils_dt import (YEARS, MONTHS, WEEKS, DAYS, HOURS, MINUTES, SECONDS,
                      plural, format_datetime, calculate_date_difference)


@pytest.mark.parametrize("number, expected", [
    (0, "godina"),
    (1, "godinu"),
    (2, "godine"),
    (4, "godine"),
    (5, "godina"),
    (11, "godina"),
    (12, "godina"),
    (14, "godina"),
    (15, "godina"),
    (21, "godinu"),
    (22, "godine"),
    (25, "godina"),
    (101, "godinu"),
    (111, "godina"),
    (112, "godina"),
    (122, "godine"),
    (-1, "godinu"),
    (-22, "godine"),
])
def test_plural_rules(number, expected):
    assert plural(number, YEARS) == expected


@pytest.mark.parametrize("forms, one, few, many", [
    (MONTHS, "1 mjesec", "3 mjeseca", "5 mjeseci"),
    (WEEKS, "1 tjedan", "3 tjedna", "5 tjedana"),
    (DAYS, "1 dan", "3 dana", "5 dana"),
    (HOURS, "1 sat", "3 sata", "5 sati"),
    (MINUTES, "1 minutu", "3 minute", "5 minuta"),
    (SECONDS, "1 sekundu", "3 sekunde", "5 sekundi"),
])
def test_word_forms(forms, one, few, many):
    assert [f"{n} {plural(n, forms)}" for n in (1, 3, 5)] == [one, few, many]


@pytest.mark.parametrize("start, end, expected", [
    (datetime(2024, 1, 31), datetime(2024, 2, 29), (0, 1, 0)),  # 31 Jan + 1 month is clipped to 29 Feb
    (datetime(2024, 1, 31), datetime(2024, 3, 1), (0, 1, 1)),
    (datetime(2024, 2, 29, 12), datetime(2025, 2, 28, 12), (1, 0, 0)),
    (datetime(2024, 2, 29, 12), datetime(2028, 2, 29, 12), (4, 0, 0)),
    (datetime(2025, 12, 31, 23, 59), datetime(2026, 1, 1, 0, 0), (0, 0, 0)),
    (datetime(2026, 9, 1, 8, 30), datetime(2026, 10, 17, 15, 30), (0, 1, 16)),
])
def test_calculate_date_difference(start, end, expected):
    assert calculate_date_difference(start, end) == expected


def test_format_datetime():
    assert format_datetime(datetime(2026, 3, 4, 5, 6, 7)) == "04.03.2026 05:06:07"
