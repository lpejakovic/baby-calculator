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

def format_datetime(dt, format_string="%d.%m.%Y %H:%M:%S"):
    return dt.strftime(format_string)

def calculate_date_difference(start_date, end_date):
    difference = relativedelta(end_date, start_date)
    return difference.years, difference.months, difference.days
