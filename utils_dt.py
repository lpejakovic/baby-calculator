from datetime import datetime, timedelta

def generate_years_string(number):
    return "godinu" if (number % 10 == 1) and (number % 100 != 11) else "godina" 

def generate_months_string(number):
    return "mjesec" if (number % 10 == 1) and (number % 100 != 11) else "mjeseci" 

def generate_week_string(number):
    mod10 = number % 10
    mod100 = number % 100
    if mod10 == 1 and mod100 != 11:
        return "tjedan"
    elif (2 <= mod10 <= 4) and (10 <= mod100 <= 14):
        return "tjedna"
    else:
        return "tjedana"

def generate_days_string(number):
    return "dan" if (number % 10 == 1) and (number % 100 != 11) else "dana" 
    
def generate_hours_string(number):
    mod10 = number % 10
    mod100 = number % 100
    if mod10 == 1 and mod100 != 11:
        return "sat"
    elif (2 <= mod10 <= 4) and (10 <= mod100 <= 14):
        return "sata"
    else:
        return "sati"

def generate_minutes_string(number):
    mod10 = number % 10
    mod100 = number % 100
    if mod10 == 1 and mod100 != 11:
        return "minutu"
    elif (2 <= mod10 <= 4) and (10 <= mod100 <= 14):
        return "minute"
    else:
        return "minuta"

def generate_seconds_string(number):
    mod10 = number % 10
    mod100 = number % 100
    if mod10 == 1 and mod100 != 11:
        return "sekundu"
    elif (2 <= mod10 <= 4) and (10 <= mod100 <= 14):
        return "sekunde"
    else:
        return "sekundi"

def format_datetime(dt, format_string="%d.%m.%Y %H:%M:%S"):
    return dt.strftime(format_string)

def diff_in_ymd(start_date, end_date):
    year_diff = end_date.year - start_date.year
    month_diff = end_date.month - start_date.month
    day_diff = end_date.day - start_date.day

    if day_diff < 0:
        month_diff -= 1
        last_day_of_prev_month = (end_date.replace(day=1) - timedelta(days=1)).day
        day_diff += last_day_of_prev_month

    if month_diff < 0:
        year_diff -= 1
        month_diff += 12

    return year_diff, month_diff, day_diff