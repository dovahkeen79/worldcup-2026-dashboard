"""
Kick-off time handling — everything is presented in London time.

Wikipedia footballboxes carry a date (dtstart, e.g. 2026-07-10) and a local
kick-off with a UTC offset (e.g. "12:00p.m.UTC-7"). We combine them into a
UTC instant, then convert to Europe/London (BST in summer) for display.
"""

import re
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    _LONDON = ZoneInfo("Europe/London")
except Exception:  # pragma: no cover - zoneinfo/tzdata missing
    _LONDON = None

_ISO_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
# Matches "12:00p.m.UTC-7", "7:00 p.m. UTC-6", "16:00 UTC-4", etc.
_TIME_RE = re.compile(
    r"(\d{1,2}):(\d{2})\s*(a\.?m\.?|p\.?m\.?)?.*?UTC\s*([+-−]\d{1,2})",
    re.IGNORECASE,
)


def to_london(date_text, time_text):
    """Return (london_datetime, iso_utc_string) or (None, None) if unparseable."""
    date_m = _ISO_RE.search(date_text or "")
    if not date_m:
        return None, None
    year, month, day = (int(x) for x in date_m.groups())

    hh, mm, offset = _parse_time(time_text or "")
    if hh is None:
        # Date known but no time — anchor to midday UTC so the date is stable.
        utc_dt = datetime(year, month, day, 12, 0, tzinfo=timezone.utc)
    else:
        local = datetime(year, month, day, hh, mm,
                         tzinfo=timezone(timedelta(hours=offset)))
        utc_dt = local.astimezone(timezone.utc)

    london = utc_dt.astimezone(_LONDON) if _LONDON else utc_dt
    return london, utc_dt.isoformat()


def _parse_time(text):
    m = _TIME_RE.search(text)
    if not m:
        return None, None, 0
    hh, mm, ampm, off = int(m.group(1)), int(m.group(2)), m.group(3), m.group(4)
    if ampm:
        ampm = ampm.lower().replace(".", "")
        if ampm == "pm" and hh != 12:
            hh += 12
        elif ampm == "am" and hh == 12:
            hh = 0
    offset = int(off.replace("−", "-"))
    return hh, mm, offset


def london_label(date_text, time_text, with_time=True):
    """Human label in London time, e.g. 'Fri 10 Jul 2026, 20:00 BST'."""
    london, _ = to_london(date_text, time_text)
    if london is None:
        return date_text or "Date TBC"
    if with_time and _has_time(time_text):
        return london.strftime("%a %d %b %Y, %H:%M %Z")
    return london.strftime("%a %d %b %Y")


def _has_time(time_text):
    return bool(_TIME_RE.search(time_text or ""))
