"""
Cloudflare Access identity and the per-user daily ad quota.

Cloudflare Access sits in front of the site and decides who may reach it at all.
Every request it lets through carries a signed JWT (Cf-Access-Jwt-Assertion);
verifying that here is what makes the email inside it trustworthy, since the
origin can also be reached directly with a forged email header.
"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

import jwt

TEAM_DOMAIN = os.environ.get("CF_ACCESS_TEAM_DOMAIN", "https://wild-unit-225c.cloudflareaccess.com")
AUD = os.environ.get("CF_ACCESS_AUD", "")
AUTH_DISABLED = os.environ.get("AUTH_DISABLED") == "1"   # local development only
ADMIN_EMAILS = {
    e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()
}
FRIEND_DAILY_LIMIT = int(os.environ.get("FRIEND_DAILY_LIMIT", "3"))
QUOTA_TZ = ZoneInfo("America/Los_Angeles")

_jwks = jwt.PyJWKClient(f"{TEAM_DOMAIN}/cdn-cgi/access/certs", cache_keys=True)

# (email, YYYY-MM-DD) → ads started that day. In memory: a redeploy resets it.
_usage: dict[tuple[str, str], int] = {}


class AccessDenied(Exception):
    pass


def identify(token: str | None) -> str:
    """Return the verified email for a request's Access JWT, or raise AccessDenied."""
    if AUTH_DISABLED:
        return "dev@localhost"
    if not AUD:
        raise AccessDenied("CF_ACCESS_AUD is not configured")
    if not token:
        raise AccessDenied("missing Cloudflare Access token")
    try:
        key = _jwks.get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, key, algorithms=["RS256"], audience=AUD, issuer=TEAM_DOMAIN)
    except jwt.PyJWTError as e:
        raise AccessDenied(f"invalid Cloudflare Access token: {e}") from e
    email = claims.get("email", "").lower()
    if not email:
        raise AccessDenied("Cloudflare Access token has no email")
    return email


def is_admin(email: str) -> bool:
    return AUTH_DISABLED or email in ADMIN_EMAILS


def _today() -> str:
    return datetime.now(QUOTA_TZ).date().isoformat()


def remaining(email: str) -> int | None:
    """Ads left today; None means unlimited."""
    if is_admin(email):
        return None
    return max(0, FRIEND_DAILY_LIMIT - _usage.get((email, _today()), 0))


def try_consume(email: str) -> bool:
    """Count one ad against today's quota. False if the quota is used up."""
    if is_admin(email):
        return True
    key = (email, _today())
    if _usage.get(key, 0) >= FRIEND_DAILY_LIMIT:
        return False
    _usage[key] = _usage.get(key, 0) + 1
    return True


def refund(email: str) -> None:
    """Give back an ad whose job failed."""
    key = (email, _today())
    if _usage.get(key, 0) > 0:
        _usage[key] -= 1
