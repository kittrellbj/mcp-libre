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


# -- uno_date_to_iso: com.sun.star.util.Date, no time-of-day fields --
# Regression: get_custom_properties_live previously put a Date-typed
# custom property's raw struct straight into the JSON response
# unconverted (only CreationDate/ModificationDate on the standard
# properties path went through a converter).

def _fake_date(year=2026, month=8, day=17):
    return SimpleNamespace(Year=year, Month=month, Day=day)


def test_uno_date_to_iso_converts_a_realistic_date():
    assert uno_date_to_iso(_fake_date()) == "2026-08-17"


def test_uno_date_to_iso_zero_year_is_unset():
    assert uno_date_to_iso(_fake_date(year=0)) is None


def test_uno_date_to_iso_none_input_returns_none():
    assert uno_date_to_iso(None) is None


# -- uno_duration_to_iso: com.sun.star.util.Duration --

def _fake_duration(years=1, months=2, days=3, hours=4, minutes=5, seconds=6, negative=False, nanoseconds=0):
    return SimpleNamespace(Years=years, Months=months, Days=days, Hours=hours,
                            Minutes=minutes, Seconds=seconds, Negative=negative,
                            NanoSeconds=nanoseconds)


def test_uno_duration_to_iso_converts_a_realistic_duration():
    assert uno_duration_to_iso(_fake_duration()) == "P1Y2M3DT4H5M6S"


def test_uno_duration_to_iso_negative_flag_prefixes_a_minus_sign():
    assert uno_duration_to_iso(_fake_duration(negative=True)).startswith("-P")


def test_uno_duration_to_iso_zero_duration_is_a_real_duration_not_none():
    # Unlike Date/DateTime, Duration has no "Year == 0 means unset"
    # sentinel -- an all-zero Duration is a real, valid zero-length value.
    zero = _fake_duration(years=0, months=0, days=0, hours=0, minutes=0, seconds=0)
    assert uno_duration_to_iso(zero) == "P0Y0M0DT0H0M0S"


def test_uno_duration_to_iso_none_input_returns_none():
    assert uno_duration_to_iso(None) is None


# -- uno_temporal_value_to_plain: duck-typed dispatcher --
# Regression: get_custom_properties_live's flat {name: value} dict could
# contain a raw Date, DateTime, or Duration struct depending on what type
# the user picked for that custom property in LibreOffice's UI -- all
# returned through the same getPropertyValue() call with no indication of
# which shape came back.

def test_dispatch_picks_datetime_conversion_for_a_datetime_shaped_value():
    value = SimpleNamespace(Year=2026, Month=8, Day=17, Hours=1, Minutes=2, Seconds=3, NanoSeconds=0, IsUTC=False)
    assert uno_temporal_value_to_plain(value) == "2026-08-17T01:02:03.000000"


def test_dispatch_picks_date_conversion_for_a_date_only_shaped_value():
    assert uno_temporal_value_to_plain(_fake_date()) == "2026-08-17"


def test_dispatch_picks_duration_conversion_for_a_duration_shaped_value():
    assert uno_temporal_value_to_plain(_fake_duration()) == "P1Y2M3DT4H5M6S"


def test_dispatch_passes_through_a_plain_value_unchanged():
    assert uno_temporal_value_to_plain("just a string") == "just a string"
    assert uno_temporal_value_to_plain(42) == 42
    assert uno_temporal_value_to_plain(True) is True
    assert uno_temporal_value_to_plain(None) is None


if __name__ == "__main__":
    tests = [
        test_converts_a_realistic_datetime_to_iso,
        test_utc_flag_appends_z_suffix,
        test_zero_padding_for_small_field_values,
        test_zero_year_is_treated_as_unset,
        test_none_input_returns_none,
        test_malformed_value_returns_none_not_raises,
        test_uno_date_to_iso_converts_a_realistic_date,
        test_uno_date_to_iso_zero_year_is_unset,
        test_uno_date_to_iso_none_input_returns_none,
        test_uno_duration_to_iso_converts_a_realistic_duration,
        test_uno_duration_to_iso_negative_flag_prefixes_a_minus_sign,
        test_uno_duration_to_iso_zero_duration_is_a_real_duration_not_none,
        test_uno_duration_to_iso_none_input_returns_none,
        test_dispatch_picks_datetime_conversion_for_a_datetime_shaped_value,
        test_dispatch_picks_date_conversion_for_a_date_only_shaped_value,
        test_dispatch_picks_duration_conversion_for_a_duration_shaped_value,
        test_dispatch_passes_through_a_plain_value_unchanged,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} uno_datetime tests passed.")
