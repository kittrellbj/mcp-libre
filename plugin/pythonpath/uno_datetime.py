"""
Pure conversions from com.sun.star.util.{Date,DateTime,Duration}-shaped
values to readable strings, plus a dispatcher that picks the right one by
duck-typing (or leaves a value alone if it isn't one of these).

Split out of uno_bridge.py so it's unit-testable without a live UNO
context -- uno_bridge.py itself can only be imported inside LibreOffice
(it imports `uno`). These functions only read plain attributes via
getattr, so any object shaped like the corresponding UNO struct works,
including a plain test double.
"""

from typing import Any, Optional


def uno_datetime_to_iso(value: Any) -> Optional[str]:
    """Convert a com.sun.star.util.DateTime struct to an ISO-8601 string.

    str(value) on the raw UNO struct produces its repr
    ("(com.sun.star.util.DateTime){ NanoSeconds = ... }"), not a readable
    date -- this builds the string from its fields instead.

    Returns None for a zero/unset DateTime (Year == 0, UNO's convention
    for "no value" on this struct), a None input, or a value missing the
    expected fields.
    """
    if value is None or getattr(value, "Year", 0) == 0:
        return None
    try:
        microseconds = getattr(value, "NanoSeconds", 0) // 1000
        return (
            f"{value.Year:04d}-{value.Month:02d}-{value.Day:02d}T"
            f"{value.Hours:02d}:{value.Minutes:02d}:{value.Seconds:02d}.{microseconds:06d}"
            f"{'Z' if getattr(value, 'IsUTC', False) else ''}"
        )
    except AttributeError:
        return None


def uno_date_to_iso(value: Any) -> Optional[str]:
    """Convert a com.sun.star.util.Date struct (date only, no time-of-day
    fields -- distinct from DateTime) to an ISO-8601 date string.

    Same rationale as uno_datetime_to_iso: str(value) on the raw struct
    produces an unreadable repr. Returns None for a zero/unset Date
    (Year == 0), a None input, or a value missing the expected fields.
    """
    if value is None or getattr(value, "Year", 0) == 0:
        return None
    try:
        return f"{value.Year:04d}-{value.Month:02d}-{value.Day:02d}"
    except AttributeError:
        return None


def uno_duration_to_iso(value: Any) -> Optional[str]:
    """Convert a com.sun.star.util.Duration struct to an ISO-8601 duration
    string (e.g. "P1Y2M3DT4H5M6S"). Distinguishing shape vs. Date/DateTime:
    Duration has a "Negative" flag and plural Years/Months/Days fields,
    never a "Year" (singular) field -- these two never collide.

    Returns None for a None input or a value missing the expected fields.
    A duration of exactly zero returns "PT0S" (a real ISO-8601 duration),
    not None -- unlike Date/DateTime, Duration has no UNO "unset" sentinel
    grabbing the zero value.
    """
    if value is None:
        return None
    try:
        sign = "-" if getattr(value, "Negative", False) else ""
        seconds = value.Seconds
        nanoseconds = getattr(value, "NanoSeconds", 0)
        if nanoseconds:
            seconds = f"{seconds}.{nanoseconds:09d}".rstrip("0")
        date_part = f"{value.Years}Y{value.Months}M{value.Days}D"
        time_part = f"{value.Hours}H{value.Minutes}M{seconds}S"
        return f"{sign}P{date_part}T{time_part}"
    except AttributeError:
        return None


def uno_temporal_value_to_plain(value: Any) -> Any:
    """Best-effort duck-typed dispatcher: if `value` looks like a UNO
    Date/DateTime/Duration struct, convert it to a readable string;
    otherwise return it unchanged.

    Intended for values whose type isn't known ahead of time -- e.g. a
    LibreOffice custom document property, which a user can set to Text,
    Number, Date, Time (DateTime), Duration, or Yes/No via the UI, all
    read back through the same getPropertyValue() call.
    """
    if hasattr(value, "Negative") and hasattr(value, "Years"):
        return uno_duration_to_iso(value)
    if hasattr(value, "Year") and hasattr(value, "Hours"):
        return uno_datetime_to_iso(value)
    if hasattr(value, "Year") and hasattr(value, "Month") and hasattr(value, "Day"):
        return uno_date_to_iso(value)
    return value
