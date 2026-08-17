#!/usr/bin/env python3
"""
Unit tests for plugin/pythonpath/host_trust.is_trusted_host.

This is the DNS-rebinding guard for ai_interface.py's Host/Origin
validation (see docs/MCP_TOOLING_SCAFFOLD_PLAN.md and the baseline
security review it followed). host_trust.py has no `uno` dependency, so
this runs without a live LibreOffice instance -- unlike ai_interface.py
itself, which can't even be imported outside of one.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugin", "pythonpath"))

from host_trust import is_trusted_host  # noqa: E402


def test_bare_host_header_localhost_variants_are_trusted():
    assert is_trusted_host("localhost:8765")
    assert is_trusted_host("localhost")
    assert is_trusted_host("127.0.0.1:8765")
    assert is_trusted_host("127.0.0.1")
    assert is_trusted_host("[::1]:8765")


def test_origin_header_localhost_variants_are_trusted():
    assert is_trusted_host("http://localhost:8765")
    assert is_trusted_host("http://127.0.0.1:8765")
    assert is_trusted_host("https://localhost")


def test_attacker_domain_is_rejected_even_if_it_resolves_to_localhost():
    # The whole point of DNS rebinding: the attacker's domain can resolve
    # to 127.0.0.1, but the Host/Origin header still names their domain.
    assert not is_trusted_host("evil.example.com")
    assert not is_trusted_host("http://evil.example.com")
    assert not is_trusted_host("localhost.evil.example.com")


def test_missing_or_empty_header_is_rejected():
    assert not is_trusted_host(None)
    assert not is_trusted_host("")


def test_malformed_header_is_rejected_not_raised():
    # Should degrade to "untrusted", never throw, since this guards every request.
    assert not is_trusted_host("not a valid host header !!")
    assert not is_trusted_host("http://")


if __name__ == "__main__":
    tests = [
        test_bare_host_header_localhost_variants_are_trusted,
        test_origin_header_localhost_variants_are_trusted,
        test_attacker_domain_is_rejected_even_if_it_resolves_to_localhost,
        test_missing_or_empty_header_is_rejected,
        test_malformed_header_is_rejected_not_raised,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} host_trust tests passed.")
