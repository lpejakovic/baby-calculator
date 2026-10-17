"""Objects shared by the pages (app.py) and the API (api.py)."""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Limits per client IP (app.py trusts nginx's X-Forwarded-For through ProxyFix). One Gunicorn worker, so in-process
# storage is enough; use Redis if workers are added.
limiter = Limiter(
    get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)
