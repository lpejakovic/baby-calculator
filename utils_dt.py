from dateutil.relativedelta import relativedelta

# Croatian forms: [1, 21, 31…], [2–4, 22–24…], [0, 5–20, 25–30…].
# Accusative, because the API text was written for "Vaše dijete ima …".
YEARS = ("godinu", "godine", "godina")
MONTHS = ("mjesec", "mjeseca", "mjeseci")
WEEKS = ("tjedan", "tjedna", "tjedana")
DAYS = ("dan", "dana", "dana")
HOURS = ("sat", "sata", "sati")
MINUTES = ("minutu", "minute", "minuta")
SECONDS = ("sekundu", "sekunde", "sekundi")


def plural(number, forms):
    number = abs(number)
    mod10 = number % 10
    mod100 = number % 100
    if mod10 == 1 and mod100 != 11:
        return forms[0]
    elif (2 <= mod10 <= 4) and not (12 <= mod100 <= 14):
        return forms[1]
    else:
        return forms[2]

# English forms: [1], [other]
FORMS = {
    "hr": {"year": YEARS, "month": MONTHS, "week": WEEKS, "day": DAYS, "hour": HOURS,
           "minute": MINUTES, "second": SECONDS},
    "en": {key: (key, f"{key}s") for key in ("year", "month", "week", "day", "hour", "minute", "second")},
}
AND = {"hr": "i", "en": "and"}
MONTH_NAMES_EN = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def unit(number, key, lang="hr"):
    forms = FORMS[lang][key]
    word = plural(number, forms) if lang == "hr" else forms[0] if abs(number) == 1 else forms[1]
    return f"{number} {word}"


def join_units(parts, lang="hr"):
    """[(46, "day"), (7, "hour")] -> "46 dana i 7 sati" / "46 days and 7 hours"."""
    texts = [unit(number, key, lang) for number, key in parts]
    return f"{', '.join(texts[:-1])} {AND[lang]} {texts[-1]}" if len(texts) > 1 else texts[0]


def format_datetime(dt, format_string="%d.%m.%Y %H:%M:%S", lang="hr"):
    if lang == "en":
        return f"{dt.day} {MONTH_NAMES_EN[dt.month - 1]} {dt.year} {dt:%H:%M:%S}"
    return dt.strftime(format_string)

def calculate_date_difference(start_date, end_date):
    difference = relativedelta(end_date, start_date)
    return difference.years, difference.months, difference.days
