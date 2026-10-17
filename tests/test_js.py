"""Tests for static/js/app.js, run in QuickJS and checked against dateutil's relativedelta."""
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from dateutil.relativedelta import relativedelta

import utils_dt

quickjs = pytest.importorskip("quickjs")

APP_JS = Path(__file__).resolve().parent.parent / "static" / "js" / "app.js"
EPOCH = datetime(1970, 1, 1)


@pytest.fixture(scope="module")
def js():
    ctx = quickjs.Context()
    ctx.eval("var module = { exports: {} };")
    ctx.eval(APP_JS.read_text())
    ctx.eval("var M = module.exports;")
    return ctx


def ms(dt):
    # Passed as float: QuickJS truncates large Python ints
    return float(int((dt - EPOCH).total_seconds() * 1000))


def call(js, expression):
    return json.loads(js.eval(f"JSON.stringify({expression})"))


def expected_age(birth, now):
    rd = relativedelta(now, birth)
    diff = now - birth
    return {
        "years": rd.years, "months": rd.months, "days": rd.days,
        "weeks": diff.days // 7, "weekDays": diff.days % 7, "totalDays": diff.days,
        "hours": diff.seconds // 3600, "minutes": diff.seconds % 3600 // 60, "seconds": diff.seconds % 60,
    }


@pytest.mark.parametrize("birth, now", [
    (datetime(2024, 1, 31, 10, 0), datetime(2024, 2, 29, 9, 0)),
    (datetime(2024, 1, 31), datetime(2024, 3, 1)),
    (datetime(2024, 2, 29, 12), datetime(2025, 2, 28, 12)),
    (datetime(2024, 2, 29, 12), datetime(2028, 2, 29, 12)),
    (datetime(2025, 12, 31, 23, 59), datetime(2026, 1, 1, 0, 0)),
    (datetime(2026, 10, 17, 15, 0), datetime(2026, 10, 17, 15, 0)),
    (datetime(2026, 3, 29, 1, 30), datetime(2026, 3, 29, 3, 30)),  # DST change in Croatia
])
def test_calculate_age_edge_cases(js, birth, now):
    assert call(js, f"M.calculateAge({ms(birth)}, {ms(now)})") == expected_age(birth, now)


def test_calculate_age_matches_relativedelta(js):
    rng = random.Random(1)
    for _ in range(2000):
        birth = datetime(2015, 1, 1) + timedelta(minutes=rng.randint(0, 6 * 365 * 24 * 60))
        now = birth + timedelta(seconds=rng.randint(0, 5 * 365 * 24 * 3600))
        assert call(js, f"M.calculateAge({ms(birth)}, {ms(now)})") == expected_age(birth, now), (birth, now)


def test_plural_matches_python(js):
    forms = ("one", "few", "many")
    js_forms = call(js, "Array.from({length: 1000}, (_, n) => M.plural(n, ['one', 'few', 'many']))")
    assert js_forms == [utils_dt.plural(n, forms) for n in range(1000)]


@pytest.mark.parametrize("key, one, few, many", [
    ("year", "godina", "godine", "godina"),
    ("month", "mjesec", "mjeseca", "mjeseci"),
    ("week", "tjedan", "tjedna", "tjedana"),
    ("day", "dan", "dana", "dana"),
    ("hour", "sat", "sata", "sati"),
    ("minute", "minuta", "minute", "minuta"),
    ("second", "sekunda", "sekunde", "sekundi"),
])
def test_word_forms(js, key, one, few, many):
    assert call(js, f"[1, 3, 5].map(n => M.plural(n, M.FORMS.{key}))") == [one, few, many]


@pytest.mark.parametrize("date, time, expected", [
    ("2024-02-29", "", datetime(2024, 2, 29)),
    ("2024-02-29", "23:59", datetime(2024, 2, 29, 23, 59)),
    ("2026-09-01", "08:30", datetime(2026, 9, 1, 8, 30)),
    ("2025-02-29", "", None),
    ("2024-02-30", "", None),
    ("2024-13-01", "10:00", None),
    ("2024-01-01", "24:00", None),
    ("", "", None),
    ("01.09.2026", "", None),
])
def test_parse_birth(js, date, time, expected):
    result = call(js, f"M.parseBirth({json.dumps(date)}, {json.dumps(time)})")
    assert result == (ms(expected) if expected else None)


@pytest.mark.parametrize("parts, expected", [
    ([[0, "year"], [0, "month"], [5, "day"]], "5 dana"),
    ([[0, "week"], [0, "day"]], "0 dana"),
    ([[6, "week"], [0, "day"]], "6 tjedana"),
    ([[6, "week"], [1, "day"]], "6 tjedana i 1 dan"),
    ([[1, "year"], [2, "month"], [3, "day"]], "1 godina, 2 mjeseca i 3 dana"),
    ([[21, "day"], [1, "hour"], [22, "minute"], [11, "second"]], "21 dan, 1 sat, 22 minute i 11 sekundi"),
])
def test_join_parts(js, parts, expected):
    assert js.eval(f"M.joinParts({json.dumps(parts)})") == expected
