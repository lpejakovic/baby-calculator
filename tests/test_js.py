"""Tests for static/js/app.js, run in QuickJS and checked against dateutil's relativedelta."""
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from dateutil.relativedelta import relativedelta
from icalendar import Calendar

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
    ("?d=2026-09-01", {"date": "2026-09-01", "time": "", "name": "", "due": ""}),
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
    assert js.eval("M.buildShareUrl('https://bc.example/', '2026-09-01', '08:30')") == "https://bc.example/?d=2026-09-01T08:30"
    assert js.eval("M.buildShareUrl('https://bc.example/', '2026-09-01', '')") == "https://bc.example/?d=2026-09-01"


def test_share_url_round_trip(js):
    url = js.eval("M.buildShareUrl('https://bc.example/', '2024-02-29', '23:59')")
    assert call(js, f"M.readSharedBirth({json.dumps(url[url.index('?'):])})") == {"date": "2024-02-29", "time": "23:59", "name": "", "due": ""}


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
    ("lmp", 295, "Zadnja menstruacija je prije više od 42 tjedna. Ako je beba rođena, odaberite „Beba je rođena”."),
    ("due", 295, "Termin je prošao prije više od dva tjedna. Ako je beba rođena, odaberite „Beba je rođena”."),
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
    ("?t=2026-12-10", {"basis": "due", "date": "2026-12-10"}),
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


def test_normalize_children_migrates_single_birth(js):
    legacy = {"date": "2026-09-01", "time": "08:30"}
    assert call(js, f"M.normalizeChildren(null, {json.dumps(legacy)})") == [child(1, time="08:30")]
    # Existing children win over the old single entry
    stored = [child(4, "2025-01-01", name="Ana")]
    assert call(js, f"M.normalizeChildren({json.dumps(stored)}, {json.dumps(legacy)})") == stored
    assert call(js, "M.normalizeChildren(null, null)") == []


def test_normalize_children_cleans_storage(js):
    stored = [
        {"id": 2, "name": "  Ana  ", "date": "2026-09-01"},   # no time, name with spaces
        {"id": 2, "name": "Marko", "date": "2025-01-01", "time": "10:00"},  # duplicate id
        {"id": 3, "name": "Bad", "date": "2026-02-30"},       # invalid date: dropped
        "junk",
        {"id": 5, "name": "x" * 60, "date": "2024-01-01"},
    ]
    assert call(js, f"M.normalizeChildren({json.dumps(stored)}, null)") == [
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
    assert url == "https://bc.example/?d=2026-09-01T08:30&n=Ana%20Marija"
    assert call(js, f"M.readSharedBirth({json.dumps(url[url.index('?'):])})")["name"] == "Ana Marija"


# --- English texts

def test_text_keys_match(js):
    # Same keys (and nested keys) in both languages
    shape = "(o) => Object.keys(o).sort().map(k => typeof o[k] === 'object' ? [k, Object.keys(o[k]).sort()] : k)"
    assert call(js, f"({shape})(M.TEXT.hr)") == call(js, f"({shape})(M.TEXT.en)")


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
        "The due date was more than two weeks ago. If the baby is born, choose “Baby is born”."


def test_english_child_label_and_fallback(js):
    assert js.eval("M.childLabel({name: ''}, 1, 'en')") == "Child 2"
    assert js.eval("M.childLabel({name: ''}, 1, 'de')") == "Dijete 2"  # unknown language: Croatian


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
    assert url == "https://bc.example/?d=2026-08-01T14:30&n=Ana&due=2026-10-01"
    assert call(js, f"M.readSharedBirth({json.dumps(url[url.index('?'):])})")["due"] == "2026-10-01"
    assert call(js, "M.readSharedBirth('?d=2026-08-01&due=2026-13-01')")["due"] == ""  # invalid due date ignored
    stored = [{"id": 1, "date": "2026-08-01", "due": "2026-10-01"}, {"id": 2, "date": "2026-08-01", "due": "nope"}]
    assert [c["due"] for c in call(js, f"M.normalizeChildren({json.dumps(stored)}, null)")] == ["2026-10-01", ""]
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
