"""
Pure conversion from a com.sun.star.util.DateTime-shaped value to an
ISO-8601 string.

Split out of uno_bridge.py so it's unit-testable without a live UNO
context -- uno_bridge.py itself can only be imported inside LibreOffice
(it imports `uno`). This function only reads plain Year/Month/Day/Hours/
Minutes/Seconds/NanoSeconds/IsUTC attributes via getattr, so any
object shaped like the UNO struct works, including a plain test double.
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
