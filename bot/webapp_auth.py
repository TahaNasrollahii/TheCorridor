"""Validate Telegram Mini App ``initData``.

A Mini App (web app launched from the bot) sends a signed ``initData`` string
with every request. Unlike webhook updates — which Telegram POSTs to us over a
channel only Telegram knows — a Mini App runs in the user's browser, so we must
verify that the ``initData`` really came from Telegram and names a real user
before trusting it. This is the auth layer for ``api/app.py``.

The actual signature check is delegated to aiogram's well-tested
``safe_parse_webapp_init_data`` (HMAC-SHA256 against the bot token), so we don't
maintain our own crypto. We add an optional freshness check and normalise the
result down to a plain dict the API handlers consume.
"""

from datetime import datetime, timezone

from aiogram.utils.web_app import safe_parse_webapp_init_data

from bot.config import TOKEN


class InitDataError(Exception):
    """Raised when initData is missing, forged or stale."""


def validate_init_data(init_data: str, max_age_seconds: int = 86400) -> dict:
    """Verify ``init_data`` and return ``{"id", "username", "first_name"}``.

    Raises :class:`InitDataError` if the signature is invalid, no user is
    present, or the payload is older than ``max_age_seconds`` (0 disables the
    age check).
    """
    if not init_data:
        raise InitDataError("missing init data")

    try:
        data = safe_parse_webapp_init_data(TOKEN, init_data)
    except ValueError as exc:
        raise InitDataError(str(exc)) from exc

    user = data.user
    if user is None or not user.id:
        raise InitDataError("no user in init data")

    if max_age_seconds and data.auth_date:
        try:
            auth_date = data.auth_date
            if auth_date.tzinfo is None:
                auth_date = auth_date.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - auth_date).total_seconds()
            if age > max_age_seconds:
                raise InitDataError("init data expired")
        except InitDataError:
            raise
        except Exception:  # noqa: BLE001 — never let a date quirk reject a valid user
            pass

    return {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
    }
