from flask import Flask, render_template, request, jsonify
from datetime import datetime
from utils_dt import *

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/calculate', methods=['POST'])
def calculate():
    input_date = request.form['date']
    input_time = request.form['time']
    input_datetime_str = f"{input_date} {input_time}"
    input_datetime = datetime.strptime(input_datetime_str, '%d.%m.%Y %H:%M')
    
    current_datetime = datetime.now()
    difference = current_datetime - input_datetime

    days = difference.days
    days_text = generate_days_string(days)
    seconds = difference.seconds
    hours = seconds // 3600
    hours_text = generate_hours_string(hours)
    minutes = (seconds % 3600) // 60
    minutes_text = generate_minutes_string(minutes)
    seconds = seconds % 60
    seconds_text = generate_seconds_string(seconds)

    week_passed = days // 7
    week_text = generate_week_string(week_passed)
    week_days = days % 7
    week_day_text = generate_days_string(week_days)

    years_diff, months_diff, days_diff = diff_in_ymd(input_datetime, current_datetime)
    year_text = generate_years_string(years_diff)
    year_month_text = generate_years_string(months_diff)
    year_day_text = generate_days_string(days_diff) 

    result = {
        "current":f"{format_datetime(current_datetime)}",
        "day_diff":f"{days} {days_text}, {hours} {hours_text}, {minutes} {minutes_text} i {seconds} {seconds_text}",
        "week_diff": f"{week_passed} {week_text} i {week_days} {week_day_text}",
        "year_diff": f"{years_diff} {year_text}, {months_diff} {year_month_text} i {days_diff} {year_day_text}",
    }
    return jsonify(result)



if __name__ == '__main__':
    app.run(debug=True)
