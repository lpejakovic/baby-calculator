from dateutil.relativedelta import relativedelta

def generate_years_string(number):
    number = abs(number)
    mod10 = number % 10
    mod100 = number % 100
    if mod10 == 1 and mod100 != 11:
        return "godinu"
    elif (2 <= mod10 <= 4) and not (10 <= mod100 <= 14):
        return "godine"
    else:
        return "godina"

def generate_months_string(number):
    number = abs(number)
    mod10 = number % 10
    mod100 = number % 100
    if mod10 == 1 and mod100 != 11:
        return "mjesec"
    elif (2 <= mod10 <= 4) and not (10 <= mod100 <= 14):
        return "mjeseca"
    else:
        return "mjeseci"

def generate_week_string(number):
    number = abs(number)
    mod10 = number % 10
    mod100 = number % 100
    if mod10 == 1 and mod100 != 11:
        return "tjedan"
    elif (2 <= mod10 <= 4) and not (10 <= mod100 <= 14):
        return "tjedna"
    else:
        return "tjedana"

def generate_days_string(number):
    number = abs(number)
    return "dan" if (number % 10 == 1) and (number % 100 != 11) else "dana" 
    
def generate_hours_string(number):
    number = abs(number)
    mod10 = number % 10
    mod100 = number % 100
    if mod10 == 1 and mod100 != 11:
        return "sat"
    elif (2 <= mod10 <= 4) and not (10 <= mod100 <= 14):
        return "sata"
    else:
        return "sati"

def generate_minutes_string(number):
    number = abs(number)
    mod10 = number % 10
    mod100 = number % 100
    if mod10 == 1 and mod100 != 11:
        return "minutu"
    elif (2 <= mod10 <= 4) and not (10 <= mod100 <= 14):
        return "minute"
    else:
        return "minuta"

def generate_seconds_string(number):
    number = abs(number)
    mod10 = number % 10
    mod100 = number % 100
    if mod10 == 1 and mod100 != 11:
        return "sekundu"
    elif (2 <= mod10 <= 4) and not (10 <= mod100 <= 14):
        return "sekunde"
    else:
        return "sekundi"

def format_datetime(dt, format_string="%d.%m.%Y %H:%M:%S"):
    return dt.strftime(format_string)

def calculate_date_difference(start_date, end_date):
    difference = relativedelta(end_date, start_date)
    
    years = difference.years
    months = difference.months
    days = difference.days
    
    return years, months, days