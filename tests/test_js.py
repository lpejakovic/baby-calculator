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


DAY_MILESTONES = [100, 200, 300, 500, 1000, 2000, 3000, 5000, 10000]
NOMINATIVE = {"day": ("dan", "dana", "dana"), "month": ("mjesec", "mjeseca", "mjeseci")}


def expected_milestones(birth, now, count=3):
    """Reference implementation with relativedelta (same month-end clipping as the page)."""
    birth_day, today = birth.date(), now.date()
    items = [(birth_day + timedelta(days=n), f"{n} {utils_dt.plural(n, NOMINATIVE['day'])}") for n in DAY_MILESTONES]
    items += [(birth_day + relativedelta(months=m), f"{m} {utils_dt.plural(m, NOMINATIVE['month'])}")
              for m in range(1, 24) if m % 12]
    items += [(birth_day + relativedelta(years=y), f"{y}. rođendan") for y in range(1, 121)]
    upcoming = sorted((item for item in items if item[0] >= today), key=lambda item: item[0])[:count]
    return [{"date": ms(datetime.combine(d, datetime.min.time())), "label": label, "daysLeft": (d - today).days}
            for d, label in upcoming]


def milestones(js, birth, now):
    return call(js, f"M.upcomingMilestones({ms(birth)}, {ms(now)})")


def test_milestones_example(js):
    result = milestones(js, datetime(2026, 9, 1, 8, 30), datetime(2026, 10, 17, 15, 30))
    assert [(m["label"], m["daysLeft"]) for m in result] == [("2 mjeseca", 15), ("3 mjeseca", 45), ("100 dana", 54)]
    assert [js.eval(f"M.formatDate({m['date']})") for m in result] == ["01.11.2026.", "01.12.2026.", "10.12.2026."]


def test_milestone_today(js):
    # Still "today" late in the evening, even though the birth time has passed
    result = milestones(js, datetime(2025, 10, 17, 6, 0), datetime(2026, 10, 17, 23, 59))
    assert result[0] == {"date": ms(datetime(2026, 10, 17)), "label": "1. rođendan", "daysLeft": 0}


def test_leap_day_birthday(js):
    result = milestones(js, datetime(2024, 2, 29, 12), datetime(2025, 2, 1))
    assert {"date": ms(datetime(2025, 2, 28)), "label": "1. rođendan", "daysLeft": 27} in result


def test_milestones_match_reference(js):
    rng = random.Random(2)
    for _ in range(500):
        birth = datetime(2010, 1, 1) + timedelta(minutes=rng.randint(0, 16 * 365 * 24 * 60))
        now = birth + timedelta(minutes=rng.randint(0, 12 * 365 * 24 * 60))
        assert milestones(js, birth, now) == expected_milestones(birth, now), (birth, now)


@pytest.mark.parametrize("days, expected", [(0, "danas"), (1, "sutra"), (2, "za 2 dana"), (21, "za 21 dan"), (100, "za 100 dana")])
def test_countdown(js, days, expected):
    assert js.eval(f"M.countdown({days})") == expected


@pytest.mark.parametrize("search, expected", [
    ("?d=2026-09-01", {"date": "2026-09-01", "time": ""}),
    ("?d=2026-09-01T08:30", {"date": "2026-09-01", "time": "08:30"}),
    ("?d=2026-09-01T08%3A30", {"date": "2026-09-01", "time": "08:30"}),
    ("?x=1&d=2026-09-01&y=2", {"date": "2026-09-01", "time": ""}),
    ("?d=2026-02-30", None),
    ("?d=2026-09-01T25:00", None),
    ("?d=", None),
    ("?dd=2026-09-01", None),
    ("", None),
])
def test_read_shared_birth(js, search, expected):
    assert call(js, f"M.readSharedBirth({json.dumps(search)})") == expected


def test_build_share_url(js):
    assert js.eval("M.buildShareUrl('https://bc.example/', '2026-09-01', '08:30')") == "https://bc.example/?d=2026-09-01T08:30"
    assert js.eval("M.buildShareUrl('https://bc.example/', '2026-09-01', '')") == "https://bc.example/?d=2026-09-01"


def test_share_url_round_trip(js):
    url = js.eval("M.buildShareUrl('https://bc.example/', '2024-02-29', '23:59')")
    assert call(js, f"M.readSharedBirth({json.dumps(url[url.index('?'):])})") == {"date": "2024-02-29", "time": "23:59"}
