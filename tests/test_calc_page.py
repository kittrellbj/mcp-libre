#!/usr/bin/env python3
"""
Unit tests for all 15 real (status="implemented") calc_page.py tools.

Uses a FakeUnoBridge modeling page layout/print areas/comments/
protection/number formats as plain dicts, mirroring the real UNOBridge
methods' public signatures -- tool-layer plumbing only (argument
passing, applied/skipped property reporting, error-code mapping), not
real PageStyle/XSheetAnnotations/XNumberFormats mechanics, which are
live-verified instead -- see docs/MCP_TOOLING_SCAFFOLD_PLAN.md's
calc_page.py pass.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugin", "pythonpath"))

from tools import context  # noqa: E402
from tools.documents import DocumentRegistry  # noqa: E402
from tools.registry import get_registry  # noqa: E402
from tools.runtime_state import RuntimeState  # noqa: E402


class FakeDocument:
    def __init__(self, doc_type="calc", title="Untitled", url=""):
        self.doc_type = doc_type
        self.title = title
        self.url = url
        self.modified = False


class FakeUnoBridge:
    """Stand-in for uno_bridge.UNOBridge's calc_page.py-facing methods."""

    def __init__(self, active_document=None):
        self.ctx = object()
        self.active_document = active_document
        self.page_layout = {"page_style": "Default", "Width": 21000, "Height": 29700, "IsLandscape": False}
        self.print_areas = None
        self.repeating_rows = None
        self.repeating_columns = None
        self.comments = {}  # cell -> {"text", "author"}
        self.protected = False
        self.cell_protection = {}  # range -> properties
        self.number_formats = {}  # key -> format_code

    def get_active_document(self):
        return self.active_document

    def get_document_info(self, doc):
        return {"type": doc.doc_type, "title": doc.title, "url": doc.url, "modified": doc.modified}

    # -- page layout --

    def get_sheet_page_layout(self, doc, sheet=None):
        return dict(self.page_layout)

    def set_sheet_page_layout(self, doc, sheet=None, width=None, height=None, unit=None,
                               orientation=None, margins=None, scale=None):
        applied = []
        if width is not None:
            self.page_layout["Width"] = width
            applied.append("width")
        if height is not None:
            self.page_layout["Height"] = height
            applied.append("height")
        if orientation is not None:
            self.page_layout["IsLandscape"] = orientation == "landscape"
            applied.append("orientation")
        if margins:
            for k in margins:
                applied.append(f"margins.{k}")
        if scale:
            for k in scale:
                applied.append(f"scale.{k}")
        return applied

    # -- print areas --

    def set_print_area(self, doc, ranges, sheet=None):
        self.print_areas = list(ranges)

    def clear_print_area(self, doc, sheet=None):
        self.print_areas = None

    def set_repeating_print_rows(self, doc, rows, sheet=None):
        self.repeating_rows = list(rows)

    def set_repeating_print_columns(self, doc, columns, sheet=None):
        self.repeating_columns = list(columns)

    # -- comments --

    def add_cell_comment(self, doc, cell, text, sheet=None, author=None):
        self.comments[cell] = {"text": text, "author": author or "Unknown Author"}
        return {"cell": cell, "author_applied": author is not None}

    def list_cell_comments(self, doc, sheet=None, range=None):
        return [{"cell": c, "text": v["text"], "author": v["author"]} for c, v in self.comments.items()]

    def delete_cell_comment(self, doc, cell, sheet=None):
        if cell not in self.comments:
            raise KeyError(f"No comment at cell '{cell}'.")
        del self.comments[cell]

    # -- protection --

    def protect_sheet(self, doc, sheet=None, password=None, options=None):
        self.protected = True
        applied = ["password"] if password else []
        if options:
            applied.extend(k for k in options if k != "InvalidOption")
        return applied

    def unprotect_sheet(self, doc, sheet=None, password=None):
        self.protected = False

    def set_cell_protection(self, doc, range, properties, sheet=None):
        applied = [k for k in properties if k in ("locked", "hidden", "formula_hidden", "print_hidden")]
        self.cell_protection[range] = {k: properties[k] for k in applied}
        return applied

    # -- number formats --

    def list_number_formats(self, doc, locale=None):
        return [
            {"category": "percent", "format_key": 11, "format_code": "0.00%"},
            {"category": "date", "format_key": 37, "format_code": "MM/DD/YY"},
        ]

    def create_number_format(self, doc, format_code, locale=None):
        key = len(self.number_formats) + 100
        self.number_formats[key] = format_code
        return {"format_key": key, "format_code": format_code}

    def apply_number_format(self, doc, range, sheet=None, format_code=None, format_key=None):
        if format_key is not None:
            key = format_key
        elif format_code is not None:
            key = len(self.number_formats) + 100
            self.number_formats[key] = format_code
        else:
            raise ValueError("Either format_code or format_key must be given.")
        return {"format_key": key}


def _install(active_document=None):
    uno_bridge = FakeUnoBridge(active_document=active_document)
    document_registry = DocumentRegistry(uno_bridge)
    runtime_state = RuntimeState()
    context.install(context.RuntimeContext(
        uno_bridge=uno_bridge, document_registry=document_registry,
        runtime_state=runtime_state, get_tools=lambda: {},
    ))
    return uno_bridge, document_registry, runtime_state


def _handler(name):
    return get_registry()[name]["handler"]


# -- page layout --

def test_get_sheet_page_layout_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("get_sheet_page_layout_live")()
    assert result["success"] is True
    assert result["result"]["page_style"] == "Default"


def test_set_sheet_page_layout_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("set_sheet_page_layout_live")(width=29700, height=21000, orientation="landscape")
    assert result["success"] is True
    assert set(result["result"]["applied"]) == {"width", "height", "orientation"}
    assert uno_bridge.page_layout["IsLandscape"] is True


# -- print areas --

def test_set_and_clear_print_area_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    set_result = _handler("set_print_area_live")(ranges=["A1:C10"])
    assert set_result["success"] is True
    assert uno_bridge.print_areas == ["A1:C10"]
    cleared = _handler("clear_print_area_live")()
    assert cleared["success"] is True
    assert uno_bridge.print_areas is None


def test_set_repeating_print_rows_and_columns_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    rows_result = _handler("set_repeating_print_rows_live")(rows=[0, 1])
    assert rows_result["success"] is True
    assert uno_bridge.repeating_rows == [0, 1]
    cols_result = _handler("set_repeating_print_columns_live")(columns=[0])
    assert cols_result["success"] is True
    assert uno_bridge.repeating_columns == [0]


# -- comments --

def test_cell_comment_lifecycle_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    added = _handler("add_cell_comment_live")(cell="B2", text="Check this", author="Sabrina")
    assert added["success"] is True
    listed = _handler("list_cell_comments_live")()
    assert listed["result"]["count"] == 1
    deleted = _handler("delete_cell_comment_live")(cell="B2")
    assert deleted["success"] is True
    assert _handler("list_cell_comments_live")()["result"]["count"] == 0


def test_delete_cell_comment_live_not_found():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("delete_cell_comment_live")(cell="Z9")
    assert result["success"] is False
    assert result["error"]["code"] == "OBJECT_NOT_FOUND"


def test_add_cell_comment_live_warns_when_author_not_applied():
    """Live-verified Author is read-only in this LibreOffice build --
    the tool still succeeds (the comment text lands) but warns that the
    requested author couldn't be honored, rather than silently dropping
    it or crashing the whole call the way the pre-fix code did."""
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    uno_bridge.add_cell_comment = lambda doc, cell, text, sheet=None, author=None: {"cell": cell, "author_applied": False}
    result = _handler("add_cell_comment_live")(cell="B2", text="Check this", author="Sabrina")
    assert result["success"] is True
    assert "read-only" in result["warnings"][0]


# -- protection --

def test_protect_and_unprotect_sheet_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    protected = _handler("protect_sheet_live")(password="secret")
    assert protected["success"] is True
    assert uno_bridge.protected is True
    unprotected = _handler("unprotect_sheet_live")(password="secret")
    assert unprotected["success"] is True
    assert uno_bridge.protected is False


def test_set_cell_protection_live_skips_unknown_properties():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("set_cell_protection_live")(range="A1:A5", properties={"locked": False, "InvalidProperty": 1})
    assert result["success"] is True
    assert result["result"]["applied"] == ["locked"]
    assert "InvalidProperty" in result["warnings"][0]
    assert uno_bridge.cell_protection["A1:A5"] == {"locked": False}


# -- number formats --

def test_list_number_formats_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("list_number_formats_live")()
    assert result["success"] is True
    assert result["result"]["count"] == 2


def test_create_and_apply_number_format_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    created = _handler("create_number_format_live")(format_code="0.00%")
    assert created["success"] is True
    format_key = created["result"]["format_key"]
    applied = _handler("apply_number_format_live")(range="C1:C5", format_key=format_key)
    assert applied["success"] is True
    assert applied["result"]["format_key"] == format_key


def test_apply_number_format_live_requires_code_or_key():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("apply_number_format_live")(range="C1:C5")
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_PARAMETER"


if __name__ == "__main__":
    tests = [
        test_get_sheet_page_layout_live,
        test_set_sheet_page_layout_live,
        test_set_and_clear_print_area_live,
        test_set_repeating_print_rows_and_columns_live,
        test_cell_comment_lifecycle_live,
        test_delete_cell_comment_live_not_found,
        test_add_cell_comment_live_warns_when_author_not_applied,
        test_protect_and_unprotect_sheet_live,
        test_set_cell_protection_live_skips_unknown_properties,
        test_list_number_formats_live,
        test_create_and_apply_number_format_live,
        test_apply_number_format_live_requires_code_or_key,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} calc_page tests passed.")
