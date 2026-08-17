#!/usr/bin/env python3
"""
Unit tests for uno_datetime.uno_datetime_to_iso.

No `uno` dependency -- runs without live LibreOffice. Found because a live
smoke test showed get_document_properties_live returning the raw UNO
struct repr ("(com.sun.star.util.DateTime){ NanoSeconds = ... }") instead
of a readable date for creation_date/modification_date.
"""

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugin", "pythonpath"))

from uno_datetime import (  # noqa: E402
    uno_datetime_to_iso,
    uno_date_to_iso,
    uno_duration_to_iso,
    uno_temporal_value_to_plain,
)


def _fake_datetime(year=2026, month=8, day=16, hours=23, minutes=56, seconds=32,
                    nanoseconds=123456000, is_utc=False):
    return SimpleNamespace(Year=year, Month=month, Day=day, Hours=hours, Minutes=minutes,
                            Seconds=seconds, NanoSeconds=nanoseconds, IsUTC=is_utc)


def test_converts_a_realistic_datetime_to_iso():
    value = _fake_datetime()
    assert uno_datetime_to_iso(value) == "2026-08-16T23:56:32.123456"


def test_utc_flag_appends_z_suffix():
    value = _fake_datetime(is_utc=True)
    assert uno_datetime_to_iso(value).endswith("Z")


def test_zero_padding_for_small_field_values():
    value = _fake_datetime(year=2026, month=1, day=2, hours=3, minutes=4, seconds=5, nanoseconds=0)
    assert uno_datetime_to_iso(value) == "2026-01-02T03:04:05.000000"


def test_zero_year_is_treated_as_unset():
    # UNO's convention for "no value" on this struct is Year == 0, not a
    # missing/None field.
    value = _fake_datetime(year=0)
    assert uno_datetime_to_iso(value) is None


def test_none_input_returns_none():
    assert uno_datetime_to_iso(None) is None


def test_malformed_value_returns_none_not_raises():
    # Has a Year but nothing else -- must degrade gracefully, not throw.
    assert uno_datetime_to_iso(SimpleNamespace(Year=2026)) is None


if __name__ == "__main__":
    tests = [
        test_converts_a_realistic_datetime_to_iso,
        test_utc_flag_appends_z_suffix,
        test_zero_padding_for_small_field_values,
        test_zero_year_is_treated_as_unset,
        test_none_input_returns_none,
        test_malformed_value_returns_none_not_raises,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} uno_datetime tests passed.")
