"""Tehran-time helpers for everything the keeper sees.

The keeper reads timestamps in Tehran local time, not UTC. Iran has used a fixed
UTC+3:30 offset since it abolished daylight saving in 2022, so a plain fixed
offset is correct and needs no tzdata package (handy on Windows/serverless).

Internal bookkeeping that must stay monotonic and comparable (vow ``remind_at``,
thread ``ts``) keeps using UTC epochs elsewhere — only human-facing strings and
day buckets use these helpers.
"""

from datetime import datetime, timedelta, timezone

TEHRAN = timezone(timedelta(hours=3, minutes=30))


def tehran_now() -> datetime:
    return datetime.now(TEHRAN)


def tehran_date() -> str:
    """Today's date in Tehran, ``YYYY-MM-DD`` — used for day buckets/first-seen."""
    return tehran_now().strftime("%Y-%m-%d")


def tehran_stamp() -> str:
    """A full keeper-facing timestamp, e.g. ``15:47:35 Tehran · 2026-06-19``."""
    return tehran_now().strftime("%H:%M:%S Tehran · %Y-%m-%d")
