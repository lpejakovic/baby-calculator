"""Tests for static/js/app.js, run in QuickJS and checked against dateutil's relativedelta."""
import json
import random
import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from dateutil.relativedelta import relativedelta
from icalendar import Calendar

import utils_dt

quickjs = pytest.importorskip("quickjs")

JS_DIR = Path(__file__).resolve().parent.parent / "static" / "js"
PURE_SCRIPTS = ["texts", "dates", "who-growth", "growth", "calendar", "data", "card"]  # browser-free, in load order
EPOCH = datetime(1970, 1, 1)


@pytest.fixture(scope="module")
def js():
    ctx = quickjs.Context()
    for name in PURE_SCRIPTS:
        ctx.eval((JS_DIR / f"{name}.js").read_text())
    ctx.eval("var M = globalThis.BC;")
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
        "weeks": diff.days // 7, "weekDays": diff.days % 7, "totalDays": diff.days, "elapsedDays": diff.days,
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


def test_calculate_age_uses_real_elapsed_time(js):
    # Born in summer time (CEST), now in winter time (CET): one more real hour has passed than the clocks show
    birth, now = datetime(2026, 7, 1, 12, 0), datetime(2026, 12, 1, 12, 0)
    elapsed = (now - birth + timedelta(hours=1)).total_seconds() * 1000
    age = call(js, f"M.calculateAge({ms(birth)}, {ms(now)}, {elapsed})")
    assert (age["totalDays"], age["weeks"], age["weekDays"], age["months"], age["days"]) == (153, 21, 6, 5, 0)
    assert (age["elapsedDays"], age["hours"], age["minutes"], age["seconds"]) == (153, 1, 0, 0)


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


CLOCK = [[592, "day"], [3, "hour"], [0, "minute"], [7, "second"]]


@pytest.mark.parametrize("lang, parts, expected", [
    ("hr", CLOCK, "592 dana, 03 sata, 00 minuta i 07 sekundi"),
    ("hr", [[0, "day"], [1, "hour"], [21, "minute"], [2, "second"]], "00 dana, 01 sat, 21 minuta i 02 sekunde"),
    ("en", CLOCK, "592 days, 03 hours, 00 minutes and 07 seconds"),
    ("en", [[1, "day"], [1, "hour"], [1, "minute"], [1, "second"]], "01 day, 01 hour, 01 minute and 01 second"),
    ("de", CLOCK, "592 Tage, 03 Stunden, 00 Minuten und 07 Sekunden"),
    ("it", CLOCK, "592 giorni, 03 ore, 00 minuti e 07 secondi"),
])
def test_join_clock(js, lang, parts, expected):
    # The live total: every part shown, two digits at least, words by the real number
    assert js.eval(f"M.joinClock({json.dumps(parts)}, '{lang}')") == expected


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
    ("#d=2026-09-01", {"date": "2026-09-01", "time": "", "name": "", "due": ""}),
    ("#d=2026-09-01T08:30&n=Ana&due=2026-10-01", {"date": "2026-09-01", "time": "08:30", "name": "Ana", "due": "2026-10-01"}),
    ("?d=2026-09-01", {"date": "2026-09-01", "time": "", "name": "", "due": ""}),  # older links
    ("?d=2026-09-01T08:30", {"date": "2026-09-01", "time": "08:30", "name": "", "due": ""}),
    ("?d=2026-09-01T08%3A30", {"date": "2026-09-01", "time": "08:30", "name": "", "due": ""}),
    ("?x=1&d=2026-09-01&y=2", {"date": "2026-09-01", "time": "", "name": "", "due": ""}),
    ("?d=2026-09-01&n=Ana", {"date": "2026-09-01", "time": "", "name": "Ana", "due": ""}),
    ("?d=2026-09-01&n=Ana+Marija", {"date": "2026-09-01", "time": "", "name": "Ana Marija", "due": ""}),
    ("?d=2026-09-01&n=%C4%8Ce%C5%A1%C4%87i%C4%87", {"date": "2026-09-01", "time": "", "name": "Češćić", "due": ""}),
    ("?d=2026-09-01&n=%E0%A4%A", {"date": "2026-09-01", "time": "", "name": "", "due": ""}),  # malformed escape
    ("?d=2026-02-30", None),
    ("?d=2026-09-01T25:00", None),
    ("?d=", None),
    ("?dd=2026-09-01", None),
    ("", None),
])
def test_read_shared_birth(js, search, expected):
    assert call(js, f"M.readSharedBirth({json.dumps(search)})") == expected


def test_build_share_url(js):
    # The data goes after "#", so it is never sent to the server
    assert js.eval("M.buildShareUrl('https://bc.example/', '2026-09-01', '08:30')") == "https://bc.example/#d=2026-09-01T08:30"
    assert js.eval("M.buildShareUrl('https://bc.example/', '2026-09-01', '')") == "https://bc.example/#d=2026-09-01"


def test_share_url_round_trip(js):
    url = js.eval("M.buildShareUrl('https://bc.example/', '2024-02-29', '23:59')")
    assert call(js, f"M.readSharedBirth({json.dumps(url[url.index('#'):])})") == {"date": "2024-02-29", "time": "23:59", "name": "", "due": ""}


# --- Pregnancy mode

def expected_pregnancy(lmp, now):
    days = (now.date() - lmp.date()).days
    due = lmp + timedelta(days=280)
    return {
        "weeks": days // 7, "weekDays": days % 7, "totalDays": days, "week": days // 7 + 1,
        "trimester": 1 if days < 98 else 2 if days < 196 else 3,
        "due": ms(due), "daysToDue": (due.date() - now.date()).days, "progress": min(days, 280),
    }


@pytest.mark.parametrize("lmp, now", [
    (datetime(2026, 3, 1), datetime(2026, 10, 17, 15, 30)),
    (datetime(2026, 10, 17), datetime(2026, 10, 17, 23, 59)),
    (datetime(2026, 1, 1), datetime(2026, 10, 8)),             # exactly 40+0
    (datetime(2025, 12, 1), datetime(2026, 9, 21)),            # 42+0, past the due date
    (datetime(2026, 2, 1), datetime(2026, 3, 29, 3, 0)),       # DST change in Croatia
])
def test_pregnancy_status(js, lmp, now):
    assert call(js, f"M.pregnancyStatus({ms(lmp)}, {ms(now)})") == expected_pregnancy(lmp, now)


@pytest.mark.parametrize("days, trimester, week", [(0, 1, 1), (97, 1, 14), (98, 2, 15), (195, 2, 28), (196, 3, 29), (280, 3, 41)])
def test_trimester_boundaries(js, days, trimester, week):
    lmp = datetime(2026, 1, 1)
    status = call(js, f"M.pregnancyStatus({ms(lmp)}, {ms(lmp + timedelta(days=days))})")
    assert (status["trimester"], status["week"]) == (trimester, week)


def test_lmp_from(js):
    due = datetime(2026, 12, 10)
    assert js.eval(f"M.lmpFrom('due', {ms(due)})") == ms(due - timedelta(days=280))
    assert js.eval(f"M.lmpFrom('lmp', {ms(due)})") == ms(due)


@pytest.mark.parametrize("basis, days_ago, expected", [
    ("lmp", -1, "Datum zadnje menstruacije ne može biti u budućnosti."),
    ("due", -1, "Termin je predaleko u budućnosti (više od 40 tjedana)."),
    ("lmp", 0, None),
    ("due", 294, None),
    ("lmp", 295, "Zadnja menstruacija je prije više od 42 tjedna. Ako je beba rođena, odaberite „Beba”."),
    ("due", 295, "Termin je prošao prije više od dva tjedna. Ako je beba rođena, odaberite „Beba”."),
])
def test_pregnancy_error(js, basis, days_ago, expected):
    now = datetime(2026, 10, 17, 12, 0)
    lmp = datetime(2026, 10, 17) - timedelta(days=days_ago)
    assert call(js, f"M.pregnancyError('{basis}', {ms(lmp)}, {ms(now)})") == expected


def test_pregnancy_milestones(js):
    lmp = datetime(2026, 3, 1)  # 32+6 on 17 Oct
    result = call(js, f"M.pregnancyMilestones({ms(lmp)}, {ms(datetime(2026, 10, 17, 15, 30))})")
    assert [(m["label"], m["daysLeft"]) for m in result] == [("Donošena trudnoća", 29), ("Termin poroda", 50)]
    assert result[1]["date"] == ms(lmp + timedelta(days=280))


def test_pregnancy_milestones_early(js):
    lmp = datetime(2026, 9, 1)
    labels = [m["label"] for m in call(js, f"M.pregnancyMilestones({ms(lmp)}, {ms(datetime(2026, 9, 10))})")]
    assert labels == ["2. tromjesečje", "Polovica trudnoće", "3. tromjesečje"]


@pytest.mark.parametrize("days, expected", [(0, "danas"), (1, "sutra"), (50, "za 50 dana"), (-1, "prije 1 dan"), (-3, "prije 3 dana")])
def test_due_countdown(js, days, expected):
    assert js.eval(f"M.dueCountdown({days})") == expected


@pytest.mark.parametrize("search, expected", [
    ("#t=2026-12-10", {"basis": "due", "date": "2026-12-10"}),
    ("?t=2026-12-10", {"basis": "due", "date": "2026-12-10"}),  # older links
    ("?x=1&t=2026-12-10", {"basis": "due", "date": "2026-12-10"}),
    ("?t=2026-02-30", None),
    ("?t=", None),
    ("?d=2026-12-10", None),
    ("", None),
])
def test_read_shared_pregnancy(js, search, expected):
    assert call(js, f"M.readSharedPregnancy({json.dumps(search)})") == expected


# --- Several children

def child(id, date="2026-09-01", time="", name="", due=""):
    return {"id": id, "name": name, "date": date, "time": time, "due": due}


def test_normalize_children_basics(js):
    stored = [child(4, "2025-01-01", name="Ana")]
    assert call(js, f"M.normalizeChildren({json.dumps(stored)})") == stored
    assert call(js, "M.normalizeChildren(null)") == [] and call(js, "M.normalizeChildren('junk')") == []


def test_normalize_children_cleans_storage(js):
    stored = [
        {"id": 2, "name": "  Ana  ", "date": "2026-09-01"},   # no time, name with spaces
        {"id": 2, "name": "Marko", "date": "2025-01-01", "time": "10:00"},  # duplicate id
        {"id": 3, "name": "Bad", "date": "2026-02-30"},       # invalid date: dropped
        "junk",
        {"id": 5, "name": "x" * 60, "date": "2024-01-01"},
    ]
    assert call(js, f"M.normalizeChildren({json.dumps(stored)})") == [
        child(1, name="Ana"), child(2, "2025-01-01", "10:00", "Marko"), child(3, "2024-01-01", name="x" * 40)]


def test_child_ids_and_labels(js):
    children = [child(1, name="Ana"), child(7)]
    assert js.eval(f"M.nextChildId({json.dumps(children)})") == 8
    assert js.eval("M.nextChildId([])") == 1
    assert call(js, f"{json.dumps(children)}.map(M.childLabel)") == ["Ana", "Dijete 2"]


def test_add_shared_child(js):
    children = [child(1, "2025-01-01", name="Ana"), child(2, "2026-09-01", "08:30")]
    # New birth: added with the next id and selected
    added = call(js, f"M.addSharedChild({json.dumps(children)}, {json.dumps({'date': '2024-05-05', 'time': '', 'name': 'Iva'})})")
    assert added == {"children": children + [child(3, "2024-05-05", name="Iva")], "activeId": 3}
    # Same birth: selected, not duplicated; an unnamed child takes the shared name
    same = call(js, f"M.addSharedChild({json.dumps(children)}, {json.dumps({'date': '2026-09-01', 'time': '08:30', 'name': 'Marko'})})")
    assert same == {"children": [children[0], child(2, "2026-09-01", "08:30", "Marko")], "activeId": 2}
    # A named child keeps its name
    kept = call(js, f"M.addSharedChild({json.dumps(children)}, {json.dumps({'date': '2025-01-01', 'time': '', 'name': 'Other'})})")
    assert kept == {"children": children, "activeId": 1}


@pytest.mark.parametrize("remove, expected_ids, active", [(2, [1, 3], 3), (3, [1, 2], 2), (1, [2, 3], 2)])
def test_remove_child(js, remove, expected_ids, active):
    children = [child(1), child(2), child(3)]
    result = call(js, f"M.removeChild({json.dumps(children)}, {remove})")
    assert [c["id"] for c in result["children"]] == expected_ids
    assert result["activeId"] == active


def test_remove_last_child(js):
    assert call(js, f"M.removeChild({json.dumps([child(1)])}, 1)") == {"children": [], "activeId": None}


def test_share_url_with_name(js):
    url = js.eval("M.buildShareUrl('https://bc.example/', '2026-09-01', '08:30', 'Ana Marija')")
    assert url == "https://bc.example/#d=2026-09-01T08:30&n=Ana%20Marija"
    assert call(js, f"M.readSharedBirth({json.dumps(url[url.index('#'):])})")["name"] == "Ana Marija"


# --- English texts

def test_text_keys_match(js):
    # Same keys (and nested keys) in both languages
    shape = "(o) => Object.keys(o).sort().map(k => typeof o[k] === 'object' ? [k, Object.keys(o[k]).sort()] : k)"
    assert call(js, "Object.keys(M.TEXT)") == ["hr", "en", "de", "it"]
    for lang in ["en", "de", "it"]:
        assert call(js, f"({shape})(M.TEXT.hr)") == call(js, f"({shape})(M.TEXT.{lang})"), lang


@pytest.mark.parametrize("n, key, expected", [
    (0, "day", "0 days"), (1, "day", "1 day"), (2, "day", "2 days"), (21, "day", "21 days"),
    (1, "week", "1 week"), (11, "month", "11 months"), (1, "year", "1 year"), (59, "second", "59 seconds"),
])
def test_english_units(js, n, key, expected):
    assert js.eval(f"M.unit({n}, '{key}', 'en')") == expected


@pytest.mark.parametrize("parts, expected", [
    ([[1, "year"], [7, "month"], [13, "day"]], "1 year, 7 months and 13 days"),
    ([[84, "week"], [4, "day"]], "84 weeks and 4 days"),
    ([[0, "week"], [0, "day"]], "0 days"),
])
def test_english_join(js, parts, expected):
    assert js.eval(f"M.joinParts({json.dumps(parts)}, 'en')") == expected


@pytest.mark.parametrize("days, expected", [(0, "today"), (1, "tomorrow"), (2, "in 2 days"), (21, "in 21 days")])
def test_english_countdown(js, days, expected):
    assert js.eval(f"M.countdown({days}, 'en')") == expected


@pytest.mark.parametrize("days, expected", [(-1, "1 day ago"), (-3, "3 days ago"), (5, "in 5 days")])
def test_english_due_countdown(js, days, expected):
    assert js.eval(f"M.dueCountdown({days}, 'en')") == expected


def test_english_birthday_ordinals(js):
    birth = datetime(2000, 6, 15)
    labels = {}
    for years in [1, 2, 3, 4, 11, 12, 13, 21, 22, 23, 101, 111, 112]:
        now = datetime(2000 + years, 6, 15)
        labels[years] = call(js, f"M.upcomingMilestones({ms(birth)}, {ms(now)}, 1, 'en')")[0]["label"]
    assert labels == {1: "1st birthday", 2: "2nd birthday", 3: "3rd birthday", 4: "4th birthday", 11: "11th birthday",
                      12: "12th birthday", 13: "13th birthday", 21: "21st birthday", 22: "22nd birthday",
                      23: "23rd birthday", 101: "101st birthday", 111: "111th birthday", 112: "112th birthday"}


def test_english_dates(js):
    assert js.eval(f"M.formatDate({ms(datetime(2025, 3, 4))}, 'en')") == "4 Mar 2025"
    assert js.eval(f"M.formatDate({ms(datetime(2026, 12, 25))}, 'en')") == "25 Dec 2026"
    assert js.eval(f"M.formatBirth({ms(datetime(2025, 3, 4, 17, 5))}, true, 'en')") == "4 Mar 2025 at 17:05"
    assert js.eval(f"M.formatBirth({ms(datetime(2025, 3, 4, 17, 5))}, true)") == "04.03.2025. u 17:05"


def test_english_milestones(js):
    result = call(js, f"M.upcomingMilestones({ms(datetime(2026, 9, 1, 8, 30))}, {ms(datetime(2026, 10, 17, 15, 30))}, 3, 'en')")
    assert [m["label"] for m in result] == ["2 months", "3 months", "100 days"]
    lmp = datetime(2026, 9, 1)
    labels = [m["label"] for m in call(js, f"M.pregnancyMilestones({ms(lmp)}, {ms(datetime(2026, 9, 10))}, 5, 'en')")]
    assert labels == ["Second trimester", "Halfway", "Third trimester", "Full term", "Due date"]


def test_english_pregnancy_texts(js):
    status = call(js, f"M.pregnancyStatus({ms(datetime(2026, 3, 1))}, {ms(datetime(2026, 10, 17))})")
    assert js.eval(f"M.TEXT.en.pregnancyDetail({json.dumps(status)})") == "32+6 · week 33 · third trimester"
    assert js.eval(f"M.TEXT.hr.pregnancyDetail({json.dumps(status)})") == "32+6 · 33. tjedan · 3. tromjesečje"
    now = datetime(2026, 10, 17, 12)
    assert call(js, f"M.pregnancyError('lmp', {ms(datetime(2026, 10, 18))}, {ms(now)}, 'en')") == \
        "The first day of the last period can’t be in the future."
    assert call(js, f"M.pregnancyError('due', {ms(datetime(2025, 12, 1))}, {ms(now)}, 'en')") == \
        "The due date was more than two weeks ago. If the baby is born, choose “Baby”."


def test_english_child_label_and_fallback(js):
    assert js.eval("M.childLabel({name: ''}, 1, 'en')") == "Child 2"
    assert js.eval("M.childLabel({name: ''}, 1, 'fr')") == "Dijete 2"  # unknown language: Croatian
    assert js.eval("M.childLabel({name: ''}, 1, 'constructor')") == "Dijete 2"  # not a key inherited by every object


# --- Corrected age (premature babies)

def corrected(js, birth, due, now):
    return call(js, f"M.correctedAge({ms(birth)}, {ms(due)}, {ms(now)})")


def test_corrected_age_after_due_date(js):
    # 61 days early: 280 - 61 = 219 days = 31+2
    result = corrected(js, datetime(2026, 8, 1, 14, 30), datetime(2026, 10, 1), datetime(2026, 12, 15, 12))
    assert {k: result[k] for k in ("premature", "daysEarly", "gestationWeeks", "gestationDays", "started")} == \
        {"premature": True, "daysEarly": 61, "gestationWeeks": 31, "gestationDays": 2, "started": True}
    age = result["age"]
    assert (age["years"], age["months"], age["days"], age["weeks"], age["weekDays"]) == (0, 2, 14, 10, 5)


def test_corrected_age_before_due_date(js):
    result = corrected(js, datetime(2026, 8, 1), datetime(2026, 10, 1), datetime(2026, 9, 15, 23, 59))
    assert (result["started"], result["daysUntilDue"]) == (False, 16)
    assert "age" not in result


@pytest.mark.parametrize("due, weeks, days", [(datetime(2026, 8, 1), 40, 0), (datetime(2026, 7, 30), 40, 2)])
def test_corrected_age_not_needed(js, due, weeks, days):
    result = corrected(js, datetime(2026, 8, 1, 9), due, datetime(2026, 12, 1))
    assert (result["premature"], result["gestationWeeks"], result["gestationDays"]) == (False, weeks, days)
    assert "age" not in result


def test_corrected_age_matches_relativedelta(js):
    rng = random.Random(3)
    for _ in range(500):
        birth = datetime(2018, 1, 1) + timedelta(minutes=rng.randint(0, 6 * 365 * 24 * 60))
        due = datetime.combine(birth.date() + timedelta(days=rng.randint(1, 140)), datetime.min.time())
        now = due + timedelta(minutes=rng.randint(0, 3 * 365 * 24 * 60))
        rd = relativedelta(now, due)
        age = corrected(js, birth, due, now)["age"]
        assert (age["years"], age["months"], age["days"]) == (rd.years, rd.months, rd.days), (birth, due, now)
        assert age["totalDays"] == (now - due).days


@pytest.mark.parametrize("days_early, lang, expected", [
    (140, "hr", None),
    (141, "hr", "Termin poroda može biti najviše 20 tjedana nakon rođenja."),
    (141, "en", "The due date can be at most 20 weeks after the birth."),
])
def test_corrected_age_limit(js, days_early, lang, expected):
    birth = datetime(2026, 8, 1, 10)
    due = datetime(2026, 8, 1) + timedelta(days=days_early)
    assert call(js, f"M.correctedAgeError({ms(birth)}, {ms(due)}, '{lang}')") == expected


def test_corrected_age_texts(js):
    assert js.eval("M.TEXT.hr.gestationAtBirth(31, 2)") == "Gestacijska dob pri rođenju:\u00a031+2"
    assert js.eval("M.TEXT.en.gestationAtBirth(31, 2)") == "Born at 31+2\u00a0weeks"


def test_due_date_in_share_links_and_storage(js):
    url = js.eval("M.buildShareUrl('https://bc.example/', '2026-08-01', '14:30', 'Ana', '2026-10-01')")
    assert url == "https://bc.example/#d=2026-08-01T14:30&n=Ana&due=2026-10-01"
    assert call(js, f"M.readSharedBirth({json.dumps(url[url.index('#'):])})")["due"] == "2026-10-01"
    assert call(js, "M.readSharedBirth('?d=2026-08-01&due=2026-13-01')")["due"] == ""  # invalid due date ignored
    stored = [{"id": 1, "date": "2026-08-01", "due": "2026-10-01"}, {"id": 2, "date": "2026-08-01", "due": "nope"}]
    assert [c["due"] for c in call(js, f"M.normalizeChildren({json.dumps(stored)})")] == ["2026-10-01", ""]
    # A shared due date fills in a matching child that has none
    shared = {"date": "2026-09-01", "time": "", "name": "", "due": "2026-10-20"}
    result = call(js, f"M.addSharedChild({json.dumps([child(1)])}, {json.dumps(shared)})")
    assert result["children"][0]["due"] == "2026-10-20"


# --- Backup and restore

def backup_json(**overrides):
    data = {"app": "baby-calculator", "version": 1, "exportedAt": "2026-10-17T12:00:00Z",
            "children": [child(1, name="Ana", due="2026-09-20")], "activeChild": 1,
            "pregnancy": {"basis": "due", "date": "2027-03-01"}, "mode": "baby"}
    data.update(overrides)
    return json.dumps(data)


def test_make_and_parse_backup(js):
    state = {"children": [child(3, name="Ana")], "activeChild": 3,
             "pregnancy": {"basis": "lmp", "date": "2026-09-01"}, "mode": "pregnancy"}
    backup = call(js, f"M.makeBackup({json.dumps(state)}, '2026-10-17T12:00:00Z')")
    assert backup == {"app": "baby-calculator", "version": 1, "exportedAt": "2026-10-17T12:00:00Z",
                      "children": [child(3, name="Ana")], "activeChild": 3,
                      "pregnancy": {"basis": "lmp", "date": "2026-09-01"}, "mode": "pregnancy"}
    assert call(js, f"M.parseBackup({json.dumps(json.dumps(backup))})") == {
        "children": [child(3, name="Ana")], "pregnancy": {"basis": "lmp", "date": "2026-09-01"}, "mode": "pregnancy"}


@pytest.mark.parametrize("text", [
    "not json", "null", "[]", "{}",
    backup_json(app="other-app"),
    backup_json(version=2),
])
def test_parse_backup_rejects(js, text):
    assert call(js, f"M.parseBackup({json.dumps(text)})") is None


def test_parse_backup_cleans_data(js):
    text = backup_json(children=[{"id": 1, "name": "Ana", "date": "2026-02-30"}, {"id": 1, "name": "Iva", "date": "2025-01-01"},
                                 "junk"], pregnancy={"basis": "other", "date": "2027-01-01"}, mode="weird")
    assert call(js, f"M.parseBackup({json.dumps(text)})") == {
        "children": [child(1, "2025-01-01", name="Iva")], "pregnancy": None, "mode": "baby"}


def test_merge_children(js):
    local = [child(1, "2025-01-01", name="Ana"), child(2, "2026-09-01", "08:30")]
    imported = [
        child(1, "2026-09-01", "08:30", name="Marko", due="2026-10-01"),  # same birth: fills name and due date
        child(2, "2025-01-01", name="Other"),                            # same birth, already named: unchanged
        child(1, "2024-05-05", name="Iva"),                              # new; its id 1 is already taken
    ]
    result = call(js, f"M.mergeChildren({json.dumps(local)}, {json.dumps(imported)})")
    assert (result["added"], result["changed"]) == (1, 1)
    assert result["children"] == [child(1, "2025-01-01", name="Ana"), child(2, "2026-09-01", "08:30", "Marko", "2026-10-01"),
                                  child(3, "2024-05-05", name="Iva")]
    again = call(js, f"M.mergeChildren({json.dumps(result['children'])}, {json.dumps(imported)})")
    assert (again["added"], again["changed"]) == (0, 0)


def test_backup_link_round_trip(js):
    backup = json.loads(backup_json(children=[child(1, name="Ana Marija Č", due="2026-09-20")]))
    link = js.eval(f"M.buildBackupLink('https://bc.example/', {json.dumps(backup)})")
    assert link.startswith("https://bc.example/#backup=%7B")
    assert call(js, f"M.readBackupLink({json.dumps(link[link.index('#'):])})")["children"] == backup["children"]
    for bad in ["", "#backup=", "#backup=%E0%A4%A", "#backup=%7Bnope", "#other=1"]:
        assert call(js, f"M.readBackupLink({json.dumps(bad)})") is None, bad


# --- Calendar export (.ics)



def ics_events(text):
    calendar = Calendar.from_ical(text)
    return calendar, [e for e in calendar.walk("VEVENT")]


@pytest.mark.parametrize("text, expected", [
    ("Ana; Marko, Iva", r"Ana\; Marko\, Iva"),
    (r"back\slash", r"back\\slash"),
    ("two\nlines", r"two\nlines"),
])
def test_ics_escape(js, text, expected):
    assert js.eval(f"M.icsEscape({json.dumps(text)})") == expected


def test_ics_fold_counts_bytes(js):
    line = "SUMMARY:" + "Ćićo i Đurđa žive u Čakovcu, " * 6
    folded = js.eval(f"M.icsFold({json.dumps(line)})")
    parts = folded.split("\r\n")
    assert len(parts) > 1
    assert all(len(p.encode()) <= 75 for p in parts)
    assert all(p.startswith(" ") for p in parts[1:])
    assert "".join([parts[0]] + [p[1:] for p in parts[1:]]) == line  # unfolding gives the original


def test_baby_calendar(js):
    birth, now = datetime(2026, 9, 1, 8, 30), datetime(2026, 10, 17, 15, 30)
    events = call(js, f"M.babyCalendarEvents({ms(birth)}, 'Ana', {ms(now)}, 'hr', 'https://bc.example/')")
    expected = [m for m in expected_milestones(birth, now, count=1000) if m["daysLeft"] <= 730]
    assert [e["date"] for e in events] == [m["date"] for m in expected]
    assert [e["summary"] for e in events][:3] == ["Ana: 2 mjeseca", "Ana: 3 mjeseca", "Ana: 100 dana"]
    assert "Ana: 1. rođendan" in [e["summary"] for e in events]
    uids = [e["uid"] for e in events]
    assert len(set(uids)) == len(uids) and uids[0] == "2026-09-01-m2@bc.luka-pejakovic.from.hr"
    # Stable: exporting again later gives the same id for each milestone that is in both exports
    later = call(js, f"M.babyCalendarEvents({ms(birth)}, 'Ana', {ms(now + timedelta(days=40))}, 'hr', 'https://bc.example/')")
    first_ids = {e["date"]: e["uid"] for e in events}
    shared = [e for e in later if e["date"] in first_ids]
    assert shared and all(first_ids[e["date"]] == e["uid"] for e in shared)


def test_ics_file_is_valid(js):
    birth, now = datetime(2026, 9, 1, 8, 30), datetime(2026, 10, 17, 15, 30)
    events = f"M.babyCalendarEvents({ms(birth)}, 'Ana Đurđević; mala', {ms(now)}, 'hr', 'https://bc.example/')"
    text = js.eval(f"M.buildIcs({events}, {ms(datetime(2026, 10, 17, 13, 30, 5))})")
    assert text.endswith("\r\n") and "\n" not in text.replace("\r\n", "")
    assert all(len(line.encode()) <= 75 for line in text.split("\r\n"))
    calendar, parsed = ics_events(text)
    assert (str(calendar["VERSION"]), str(calendar["METHOD"])) == ("2.0", "PUBLISH")
    first = parsed[0]
    assert str(first["SUMMARY"]) == "Ana Đurđević; mala: 2 mjeseca"
    assert first.decoded("DTSTART") == datetime(2026, 11, 1).date()
    assert first.decoded("DTEND") == datetime(2026, 11, 2).date()
    assert first.decoded("DTSTAMP").isoformat() == "2026-10-17T13:30:05+00:00"
    assert str(first["TRANSP"]) == "TRANSPARENT"
    alarm = first.walk("VALARM")[0]
    assert alarm.decoded("TRIGGER") == timedelta(hours=9)


def test_pregnancy_calendar(js):
    lmp, now = datetime(2026, 3, 1), datetime(2026, 10, 17, 15, 30)
    events = call(js, f"M.pregnancyCalendarEvents({ms(lmp)}, {ms(now)}, 'en', 'https://bc.example/en/')")
    assert [e["summary"] for e in events] == ["Pregnancy: Full term", "Pregnancy: Due date"]
    assert events[1]["date"] == ms(lmp + timedelta(days=280))
    assert events[1]["uid"] == "pregnancy-2026-03-01-due@bc.luka-pejakovic.from.hr"
    assert events[0]["description"] == "Baby Calculator · https://bc.example/en/"


# --- Pregnancy dating: IVF transfer and ultrasound

@pytest.mark.parametrize("embryo_days, days_to_due", [(3, 263), (5, 261), (6, 260)])
def test_lmp_from_ivf(js, embryo_days, days_to_due):
    transfer = datetime(2026, 5, 10)
    lmp = js.eval(f"M.lmpFrom('ivf', {ms(transfer)}, {{embryoDays: {embryo_days}}})")
    assert lmp == ms(transfer - timedelta(days=14 + embryo_days))
    assert lmp + 280 * 86400000 == ms(transfer + timedelta(days=days_to_due))  # the usual IVF due dates


def test_lmp_from_ultrasound(js):
    scan = datetime(2026, 6, 1)
    assert js.eval(f"M.lmpFrom('ultrasound', {ms(scan)}, {{gaWeeks: 8, gaDays: 3}})") == ms(scan - timedelta(days=59))


@pytest.mark.parametrize("state, expected", [
    ({"basis": "due", "date": "2026-12-06"}, {"basis": "due", "date": "2026-12-06"}),
    ({"basis": "due", "date": "2026-12-06", "embryoDays": 5}, {"basis": "due", "date": "2026-12-06"}),  # extras dropped
    ({"basis": "ivf", "date": "2026-05-10", "embryoDays": 3}, {"basis": "ivf", "date": "2026-05-10", "embryoDays": 3}),
    ({"basis": "ivf", "date": "2026-05-10", "embryoDays": 4}, None),
    ({"basis": "ivf", "date": "2026-05-10"}, None),
    ({"basis": "ultrasound", "date": "2026-06-01", "gaWeeks": 8, "gaDays": 3},
     {"basis": "ultrasound", "date": "2026-06-01", "gaWeeks": 8, "gaDays": 3}),
    ({"basis": "ultrasound", "date": "2026-06-01", "gaWeeks": 43, "gaDays": 0}, None),
    ({"basis": "ultrasound", "date": "2026-06-01", "gaWeeks": 8, "gaDays": 7}, None),
    ({"basis": "ultrasound", "date": "2026-06-01", "gaWeeks": 8.5, "gaDays": 1}, None),
    ({"basis": "ultrasound", "date": "2026-06-01", "gaWeeks": None, "gaDays": 1}, None),
    ({"basis": "other", "date": "2026-06-01"}, None),
    ({"basis": "lmp", "date": "2026-02-30"}, None),
])
def test_valid_pregnancy(js, state, expected):
    assert call(js, f"M.validPregnancy({json.dumps(state)})") == expected


def test_convert_pregnancy_keeps_the_pregnancy(js):
    now = ms(datetime(2026, 10, 17, 12))
    start = {"basis": "due", "date": "2026-12-06"}
    lmp = call(js, f"M.pregnancyLmp({json.dumps(start)})")
    states = [start]
    for basis in ["lmp", "ivf", "ultrasound", "due", "ultrasound", "ivf"]:
        states.append(call(js, f"M.convertPregnancy({json.dumps(states[-1])}, '{basis}', {now})"))
    assert all(call(js, f"M.pregnancyLmp({json.dumps(s)})") == lmp for s in states), states
    assert states[2] == {"basis": "ivf", "date": "2026-03-20", "embryoDays": 5}
    # Ultrasound from another basis: a scan today with the matching age (32+6 on 17 Oct)
    assert states[3] == {"basis": "ultrasound", "date": "2026-10-17", "gaWeeks": 32, "gaDays": 6}


def test_convert_ultrasound_keeps_scan_and_embryo_age(js):
    now = ms(datetime(2026, 10, 17, 12))
    scan = {"basis": "ultrasound", "date": "2026-06-01", "gaWeeks": 8, "gaDays": 3}
    assert call(js, f"M.convertPregnancy({json.dumps(scan)}, 'ultrasound', {now})") == scan
    ivf = {"basis": "ivf", "date": "2026-05-10", "embryoDays": 3}
    assert call(js, f"M.convertPregnancy({json.dumps(ivf)}, 'ivf', {now})") == ivf


@pytest.mark.parametrize("basis, extra, event_offset, lmp_days_ago, expected", [
    ("ivf", {"embryoDays": 5}, 1, 0, "Datum ne može biti u budućnosti."),
    ("ultrasound", {"gaWeeks": 8, "gaDays": 0}, 1, 55, "Datum ne može biti u budućnosti."),
    ("ultrasound", {"gaWeeks": 42, "gaDays": 6}, -30, 330, "Prema ovim podacima trudnoća traje više od 42 tjedna. "
                                                           "Ako je beba rođena, odaberite „Beba”."),
    ("ivf", {"embryoDays": 5}, -10, 29, None),
])
def test_pregnancy_error_for_new_bases(js, basis, extra, event_offset, lmp_days_ago, expected):
    today = datetime(2026, 10, 17)
    event, lmp = today + timedelta(days=event_offset), today - timedelta(days=lmp_days_ago)
    result = call(js, f"M.pregnancyError('{basis}', {ms(lmp)}, {ms(today + timedelta(hours=12))}, 'hr', {ms(event)})")
    assert result == expected


def test_backup_keeps_new_pregnancy_details(js):
    text = backup_json(children=[], pregnancy={"basis": "ultrasound", "date": "2026-06-01", "gaWeeks": 8, "gaDays": 3})
    assert call(js, f"M.parseBackup({json.dumps(text)})")["pregnancy"] == \
        {"basis": "ultrasound", "date": "2026-06-01", "gaWeeks": 8, "gaDays": 3}


def test_app_js_loads_after_the_pure_scripts():
    # Without a DOM the page code doesn't run, but syntax errors and names missing from BC fail here
    ctx = quickjs.Context()
    for name in [*PURE_SCRIPTS, "app"]:
        ctx.eval((JS_DIR / f"{name}.js").read_text())
    app_js = (JS_DIR / "app.js").read_text()
    imported = re.search(r"const \{([^}]*)\} = globalThis\.BC;", app_js).group(1)
    missing = [n.strip() for n in imported.split(",") if n.strip() and ctx.eval(f"typeof BC.{n.strip()}") == "undefined"]
    assert missing == []


# --- Share card layout (card.js)

# Stand-in for canvas text measuring: every character is 0.55 × the font size wide
MEASURE = "(text, font) => text.length * parseInt(font.split(' ')[1]) * 0.55"


def card(js, content):
    return call(js, f"M.layoutCard({json.dumps(content)}, {MEASURE})")


def card_width(op):
    return len(op["text"]) * op["size"] * 0.55


BABY_CARD = {"title": "Ana", "main": "1 godina, 7 mjeseci i 13 dana",
             "lines": ["84 tjedna i 4 dana", "Rođenje: 04.03.2025."], "footer": "bc.example"}


def test_card_layout_fits_and_keeps_order(js):
    layout = card(js, BABY_CARD)
    assert layout["size"] == 1080
    texts = [op["text"].replace("\u00a0", " ") for op in layout["ops"]]
    assert texts[0] == "Ana" and texts[-1] == "bc.example"
    assert texts.index("84 tjedna i 4 dana") < texts.index("Rođenje: 04.03.2025.")
    body, footer = layout["ops"][:-1], layout["ops"][-1]
    for op in layout["ops"]:
        assert card_width(op) <= 1080 - 2 * 96, op  # centred, so inside the 96 px margins
    ys = [op["y"] for op in body]
    assert ys == sorted(ys) and ys[0] >= layout["icon"]["y"] + layout["icon"]["size"]
    last = body[-1]
    assert last["y"] + last["size"] * 1.2 <= footer["y"]  # nothing runs into the footer


def test_card_main_text_shrinks_and_wraps(js):
    short = card(js, {**BABY_CARD, "main": "5 dana"})["ops"][1]
    long_main = "10 godina, 11 mjeseci i 30 dana, 11 mjeseci i 30 dana"
    long_ops = [op for op in card(js, {**BABY_CARD, "main": long_main})["ops"] if op["color"] == "#4f46b8"]
    assert short["size"] == 104
    assert 1 < len(long_ops) <= 3 and long_ops[0]["size"] < 104


def test_card_clips_a_word_that_cannot_fit(js):
    ops = card(js, {**BABY_CARD, "title": "Ana" * 40})["ops"]
    assert ops[0]["text"].endswith("…") and card_width(ops[0]) <= 1080 - 2 * 96


def test_card_long_title_wraps_to_two_lines(js):
    title = "Ana Marija Kovačević Horvat Novak Babić"
    title_ops = [op for op in card(js, {**BABY_CARD, "title": title})["ops"] if op["color"] == "#2b2838" and op["size"] >= 48]
    assert 1 <= len(title_ops) <= 2
    assert " ".join(op["text"] for op in title_ops) == title


def test_card_very_long_content_still_fits(js):
    content = {"title": "Ana Marija Kovačević Horvat", "main": "10 godina, 11 mjeseci i 30 dana",
               "lines": ["573 tjedna i 6 dana", "Korigirana dob: 10 godina, 9 mjeseci i 2 dana", "Rođenje: 04.03.2015. u 17:45"],
               "footer": "bc.example"}
    layout = card(js, content)
    body, footer = layout["ops"][:-1], layout["ops"][-1]
    assert body[-1]["y"] + body[-1]["size"] * 1.2 <= footer["y"]
    assert all(card_width(op) <= 1080 - 2 * 96 for op in layout["ops"])


@pytest.mark.parametrize("main", ["1 godina, 7 mjeseci i 13 dana", "32 weeks and 6 days", "10 godina, 11 mjeseci i 30 dana"])
def test_card_keeps_numbers_with_their_units(js, main):
    lines = [op["text"] for op in card(js, {**BABY_CARD, "main": main})["ops"] if op["color"] == "#4f46b8"]
    assert " ".join(lines).replace("\u00a0", " ") == main
    for line in lines:
        assert not re.search(r"(\d| i| and)$", line.replace("\u00a0", " ")), lines


def test_keep_together(js):
    assert js.eval("M.keepTogether('1 godina, 7 mjeseci i 13 dana')") == "1\u00a0godina, 7\u00a0mjeseci i\u00a013\u00a0dana"
    assert js.eval("M.keepTogether('32+6 · week 33')") == "32+6 · week 33"  # numbers at the end stay as they are



# --- German and Italian

@pytest.mark.parametrize("lang, n, key, expected", [
    ("de", 1, "day", "1 Tag"), ("de", 2, "day", "2 Tage"), ("de", 0, "week", "0 Wochen"), ("de", 1, "year", "1 Jahr"),
    ("de", 7, "month", "7 Monate"), ("de", 21, "hour", "21 Stunden"),
    ("it", 1, "day", "1 giorno"), ("it", 2, "day", "2 giorni"), ("it", 1, "week", "1 settimana"),
    ("it", 3, "week", "3 settimane"), ("it", 1, "month", "1 mese"), ("it", 5, "hour", "5 ore"),
])
def test_units_de_it(js, lang, n, key, expected):
    assert js.eval(f"M.unit({n}, '{key}', '{lang}')") == expected


@pytest.mark.parametrize("lang, expected", [
    ("de", "1 Jahr, 7 Monate und 13 Tage"), ("it", "1 anno, 7 mesi e 13 giorni"),
])
def test_join_de_it(js, lang, expected):
    assert js.eval(f"M.joinParts([[1, 'year'], [7, 'month'], [13, 'day']], '{lang}')") == expected


@pytest.mark.parametrize("lang, days, expected", [
    ("de", 0, "heute"), ("de", 1, "morgen"), ("de", 2, "in 2 Tagen"), ("de", -1, "vor 1 Tag"), ("de", -5, "vor 5 Tagen"),
    ("it", 0, "oggi"), ("it", 1, "domani"), ("it", 2, "tra 2 giorni"), ("it", -1, "1 giorno fa"), ("it", -5, "5 giorni fa"),
])
def test_countdown_de_it(js, lang, days, expected):
    assert js.eval(f"M.dueCountdown({days}, '{lang}')") == expected


@pytest.mark.parametrize("lang, birthday, date, at", [
    ("de", "3. Geburtstag", "4. März 2025", "4. März 2025 um 17:05"),
    ("it", "3° compleanno", "4 marzo 2025", "4 marzo 2025 alle 17:05"),
])
def test_dates_and_birthdays_de_it(js, lang, birthday, date, at):
    birth = datetime(2000, 6, 15)
    label = call(js, f"M.upcomingMilestones({ms(birth)}, {ms(datetime(2003, 6, 15))}, 1, '{lang}')")[0]["label"]
    assert label == birthday
    assert js.eval(f"M.formatDate({ms(datetime(2025, 3, 4))}, '{lang}')") == date
    assert js.eval(f"M.formatBirth({ms(datetime(2025, 3, 4, 17, 5))}, true, '{lang}')") == at


@pytest.mark.parametrize("lang, detail, milestones", [
    ("de", "32+6 · 33.\u00a0SSW · 3.\u00a0Trimester", ["Termingerecht", "Geburtstermin"]),
    ("it", "32+6 · 33ª\u00a0settimana · 3°\u00a0trimestre", ["A termine", "Data presunta del parto"]),
])
def test_pregnancy_texts_de_it(js, lang, detail, milestones):
    lmp, now = datetime(2026, 3, 1), datetime(2026, 10, 17)
    status = call(js, f"M.pregnancyStatus({ms(lmp)}, {ms(now)})")
    assert js.eval(f"M.TEXT.{lang}.pregnancyDetail({json.dumps(status)})") == detail
    assert [m["label"] for m in call(js, f"M.pregnancyMilestones({ms(lmp)}, {ms(now)}, 3, '{lang}')")] == milestones


def test_card_keeps_units_together_de_it(js):
    assert js.eval("M.keepTogether('1 Jahr, 7 Monate und 13 Tage')") == "1\u00a0Jahr, 7\u00a0Monate und\u00a013\u00a0Tage"
    assert js.eval("M.keepTogether('7 mesi e 13 giorni')") == "7\u00a0mesi e\u00a013\u00a0giorni"


# --- Growth (growth.js, WHO data in who-growth.js)

from statistics import NormalDist  # noqa: E402


def test_normal_cdf_matches_python(js):
    for z in [-4, -3, -2.5, -1.88, -1, -0.3, 0, 0.5, 1.036, 2, 3.5]:
        assert abs(js.eval(f"M.normalCdf({z})") - NormalDist().cdf(z)) < 1e-6, z


def test_who_data_shape(js):
    assert call(js, "Object.keys(M.WHO_GROWTH)") == ["boys", "girls"]
    for sex in ["boys", "girls"]:
        assert call(js, f"Object.keys(M.WHO_GROWTH.{sex})") == ["weight", "length", "head"]
        for measure in ["weight", "length", "head"]:
            table = call(js, f"M.WHO_GROWTH.{sex}.{measure}")
            assert len(table) == 25 and all(len(row) == 3 for row in table)
            medians = [row[1] for row in table]
            assert medians == sorted(medians), (sex, measure)  # medians grow with age


@pytest.mark.parametrize("value, expected", [
    (3.3464, "P50"),            # the WHO median for a newborn boy
    (2.459312, "P2"),           # published 2nd (2.3rd) percentile; decimals only below P1 and above P99
    (4.419354, "P98"),          # published 98th (97.7th) percentile
    (1.5, "<P0.1"), (6.5, ">P99.9"),
])
def test_newborn_boy_weight_percentiles(js, value, expected):
    p = js.eval(f"M.measurePercentile(M.WHO_GROWTH.boys.weight, 0, {value})")
    assert js.eval(f"M.formatPercentile({p})") == expected


def test_lms_interpolation_and_range(js):
    table = call(js, "M.WHO_GROWTH.girls.length")
    assert call(js, "M.lmsAt(M.WHO_GROWTH.girls.length, 6)") == pytest.approx(table[6])
    mid = call(js, "M.lmsAt(M.WHO_GROWTH.girls.length, 6.5)")
    assert mid == pytest.approx([(a + b) / 2 for a, b in zip(table[6], table[7], strict=True)])
    assert call(js, "M.lmsAt(M.WHO_GROWTH.girls.length, 24)") == pytest.approx(table[24])
    assert call(js, "[M.lmsAt(M.WHO_GROWTH.girls.length, -0.1), M.lmsAt(M.WHO_GROWTH.girls.length, 24.1)]") == [None, None]


def test_value_and_z_score_round_trip(js):
    for z in [-2.5, -1, 0, 1.2, 3]:
        value = js.eval(f"M.valueAt(M.lmsAt(M.WHO_GROWTH.boys.head, 9.3), {z})")
        assert js.eval(f"M.zScore({value}, M.lmsAt(M.WHO_GROWTH.boys.head, 9.3))") == pytest.approx(z, abs=1e-9)


def test_age_in_months(js):
    birth = datetime(2026, 1, 1)
    # Whole days only: 6 WHO months are 182.6 days, so 182 days is a little under 6
    assert js.eval(f"M.ageInMonths({ms(birth)}, {ms(birth + timedelta(days=183))})") == pytest.approx(6, abs=1 / 30.4375)
    assert js.eval(f"M.ageInMonths({ms(birth)}, {ms(birth)})") == 0


@pytest.mark.parametrize("p, expected", [(50.4, "P50"), (2.34, "P2"), (0.54, "P0.5"), (99.42, "P99.4"), (0.05, "<P0.1"), (99.95, ">P99.9")])
def test_format_percentile(js, p, expected):
    assert js.eval(f"M.formatPercentile({p})") == expected


def test_growth_chart_geometry(js):
    points = [{"months": 0, "value": 3.3}, {"months": 6, "value": 7.9}, {"months": 30, "value": 13}]
    chart = call(js, f"M.growthChart(M.WHO_GROWTH.boys.weight, {json.dumps(points)}, 600, 360)")
    assert [c["percentile"] for c in chart["curves"]] == [3, 15, 50, 85, 97]
    top, bottom = chart["pad"]["top"], 360 - chart["pad"]["bottom"]
    for curve in chart["curves"]:
        ys = [float(part.split()[1]) for part in curve["d"].split(" L")]
        assert len(ys) == 97 and all(top - 0.1 <= y <= bottom + 0.1 for y in ys)
    assert [p["months"] for p in chart["points"]] == [0, 6]  # the 30-month point is outside the chart
    assert chart["xTicks"][0]["months"] == 0 and chart["xTicks"][-1]["months"] == 24
    values = [t["value"] for t in chart["yTicks"]]
    assert values == sorted(values) and [t["y"] for t in chart["yTicks"]] == sorted([t["y"] for t in chart["yTicks"]], reverse=True)


def test_clean_measurements(js):
    stored = [
        {"date": "2026-03-01", "weight": 5.2, "length": 57},
        {"date": "2026-01-01", "weight": 3.4},
        {"date": "2026-03-01", "head": 39.5},          # same date: merged
        {"date": "2026-02-01", "weight": 4200},        # grams by mistake: dropped
        {"date": "nope", "weight": 4}, "junk",
    ]
    assert call(js, f"M.cleanMeasurements({json.dumps(stored)})") == [
        {"date": "2026-01-01", "weight": 3.4},
        {"date": "2026-03-01", "weight": 5.2, "length": 57, "head": 39.5},
    ]


def test_child_growth_fields_are_optional_and_merged(js):
    plain = child(1, name="Ana")
    assert call(js, f"M.normalizeChildren({json.dumps([plain])})") == [plain]  # unchanged when unused
    local = {**child(1, name="Ana"), "sex": "f", "measurements": [{"date": "2026-02-01", "weight": 4.5}]}
    imported = {**child(1, name="Ana"), "sex": "m",
                "measurements": [{"date": "2026-02-01", "weight": 9.9}, {"date": "2026-03-01", "weight": 5.6}]}
    merged = call(js, f"M.mergeChildren({json.dumps([local])}, {json.dumps([imported])})")
    assert merged["children"][0]["sex"] == "f"  # the existing value wins
    assert merged["children"][0]["measurements"] == [{"date": "2026-02-01", "weight": 4.5}, {"date": "2026-03-01", "weight": 5.6}]
    assert (merged["added"], merged["changed"]) == (0, 1)
