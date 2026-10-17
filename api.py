"""JSON API: POST /calculate (see the README). The page itself calculates in the browser and doesn't use it."""
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Blueprint, jsonify, request

from extensions import limiter
from i18n import API_ERRORS, LANGUAGES, UNSUPPORTED_LANG
from utils_dt import calculate_date_difference, format_datetime, join_units

api = Blueprint("api", __name__)

API_LIMIT = "1 per second; 8 per minute; 32 per hour"
DEFAULT_TZ = "Europe/Zagreb"


def api_input():
    """Form fields or a JSON object, as a plain dict of strings."""
    if request.is_json:
        data = request.get_json(silent=True)
        return {k: v for k, v in data.items() if isinstance(v, str)} if isinstance(data, dict) else {}
    return request.form


@api.route('/calculate', methods=['POST'])
@limiter.limit(API_LIMIT)
def calculate():
    data = api_input()
    lang = data.get('lang') or 'hr'
    if lang not in LANGUAGES:
        return jsonify({"error": UNSUPPORTED_LANG}), 400
    errors = API_ERRORS[lang]

    try:
        birth_wall = datetime.strptime(data.get('datetime', ''), '%Y-%m-%dT%H:%M')
    except ValueError:
        return jsonify({"error": errors["invalid_datetime"]}), 400

    # IANA time zone of the caller (e.g. "Asia/Tokyo"); the birth time is read in this zone too
    tz_name = data.get('tz') or DEFAULT_TZ
    try:
        zone = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        return jsonify({"error": errors["unknown_tz"]}), 400
    now = datetime.now(zone)
    birth = birth_wall.replace(tzinfo=zone)
    now_wall = now.replace(tzinfo=None)
    if birth_wall > now_wall:
        return jsonify({"error": errors["future"]}), 400

    # Calendar values (years, months, days, weeks) use wall-clock time; the elapsed time is real time, which
    # differs by an hour when a summer/winter time change lies in between
    calendar_days = (now_wall - birth_wall).days
    weeks, week_days = divmod(calendar_days, 7)
    years, months, days = calculate_date_difference(birth_wall, now_wall)
    elapsed = now.astimezone(UTC) - birth.astimezone(UTC)
    hours, rest = divmod(elapsed.seconds, 3600)
    minutes, seconds = divmod(rest, 60)

    return jsonify({
        "current": format_datetime(now_wall, lang=lang),
        "day_diff": join_units(
            [(elapsed.days, "day"), (hours, "hour"), (minutes, "minute"), (seconds, "second")], lang),
        "week_diff": join_units([(weeks, "week"), (week_days, "day")], lang),
        "year_diff": join_units([(years, "year"), (months, "month"), (days, "day")], lang),
        "age": {
            "calendar": {"years": years, "months": months, "days": days},
            "weeks": {"weeks": weeks, "days": week_days},
            "elapsed": {"days": elapsed.days, "hours": hours, "minutes": minutes, "seconds": seconds,
                        "total_seconds": int(elapsed.total_seconds())},
        },
        "birth": birth.isoformat(),
        "now": now.replace(microsecond=0).isoformat(),
        "tz": tz_name,
        "lang": lang,
    })

@api.errorhandler(429)
def rate_limited(e):
    # Only for API requests; pages keep the default 429 response
    data = api_input()
    lang = data.get('lang') if data.get('lang') in LANGUAGES else 'hr'
    return jsonify({"error": API_ERRORS[lang]["rate_limited"]}), 429
