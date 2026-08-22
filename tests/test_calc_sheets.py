#!/usr/bin/env python3
"""
Unit tests for the 42 real (status="implemented") calc_sheets.py tools.

Uses a FakeUnoBridge modeling sheets as a list of plain dicts and cells
as a per-sheet dict keyed by A1-notation string -- enough to exercise
the tool-layer logic (parameter plumbing, sheet-name-or-index resolution,
error-code mapping, warnings for skipped properties) without reimplementing
real Calc arithmetic, formula evaluation, or cell-address math. Sheet
name-or-index resolution itself is exercised for real (this fake defers
to the exact same UNOBridge._resolve_sheet_by_name_or_index()-shaped
logic drawing_objects.py's tests already established the pattern for),
but the deeper cell/range mechanics (getCellRangeByName, setFormulaArray,
XCellSeries.fillSeries, queryPrecedents/queryDependents, NumberFormats)
are live-verified instead -- see docs/MCP_TOOLING_SCAFFOLD_PLAN.md's
calc_sheets.py pass, not something a fake can usefully assert.
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
    """Stand-in for uno_bridge.UNOBridge's calc_sheets.py-facing methods."""

    def __init__(self, active_document=None, sheet_names=None):
        self.ctx = object()
        self.active_document = active_document
        self.sheets = [{"name": n, "visible": True, "protected": False} for n in (sheet_names or ["Sheet1"])]
        self.active_sheet_name = self.sheets[0]["name"]
        self.cells = {n: {} for n in (sheet_names or ["Sheet1"])}  # {sheet: {cell: {"value", "formula"}}}
        self.row_heights = {}
        self.col_widths = {}
        self.hidden_rows = set()
        self.hidden_cols = set()
        self.frozen_at = None
        self.recalculated = None

    def get_active_document(self):
        return self.active_document

    def get_document_info(self, doc):
        return {"type": doc.doc_type, "title": doc.title, "url": doc.url, "modified": doc.modified}

    # -- sheet resolution --

    def _resolve_sheet_name(self, sheet):
        if sheet is None:
            return self.active_sheet_name
        for s in self.sheets:
            if s["name"] == sheet:
                return sheet
        if sheet.isdigit() and 0 <= int(sheet) < len(self.sheets):
            return self.sheets[int(sheet)]["name"]
        raise KeyError(f"No such sheet '{sheet}'.")

    # -- sheets --

    def list_sheets(self, doc):
        return [{"index": i, **s} for i, s in enumerate(self.sheets)]

    def get_active_sheet(self, doc):
        idx = next(i for i, s in enumerate(self.sheets) if s["name"] == self.active_sheet_name)
        return {"index": idx, "name": self.active_sheet_name, "visible": True}

    def activate_sheet(self, doc, sheet):
        self.active_sheet_name = self._resolve_sheet_name(sheet)

    def insert_sheet(self, doc, name, position=None):
        idx = position if position is not None else len(self.sheets)
        self.sheets.insert(idx, {"name": name, "visible": True, "protected": False})
        self.cells[name] = {}

    def delete_sheet(self, doc, sheet):
        name = self._resolve_sheet_name(sheet)
        self.sheets = [s for s in self.sheets if s["name"] != name]
        del self.cells[name]

    def rename_sheet(self, doc, sheet, new_name):
        name = self._resolve_sheet_name(sheet)
        for s in self.sheets:
            if s["name"] == name:
                s["name"] = new_name
        self.cells[new_name] = self.cells.pop(name)
        if self.active_sheet_name == name:
            self.active_sheet_name = new_name

    def move_sheet(self, doc, sheet, destination_index):
        name = self._resolve_sheet_name(sheet)
        entry = next(s for s in self.sheets if s["name"] == name)
        self.sheets.remove(entry)
        self.sheets.insert(destination_index, entry)

    def copy_sheet(self, doc, sheet, new_name, destination_index=None):
        name = self._resolve_sheet_name(sheet)
        idx = destination_index if destination_index is not None else len(self.sheets)
        self.sheets.insert(idx, {"name": new_name, "visible": True, "protected": False})
        self.cells[new_name] = dict(self.cells[name])

    def hide_sheet(self, doc, sheet):
        name = self._resolve_sheet_name(sheet)
        next(s for s in self.sheets if s["name"] == name)["visible"] = False

    def show_sheet(self, doc, sheet):
        name = self._resolve_sheet_name(sheet)
        next(s for s in self.sheets if s["name"] == name)["visible"] = True

    # -- cells / ranges --

    def get_cell(self, doc, cell, sheet=None):
        name = self._resolve_sheet_name(sheet)
        data = self.cells[name].get(cell, {"value": 0.0, "formula": "", "display": "", "error": 0})
        return {"cell": cell, **data}

    def set_cell(self, doc, cell, sheet=None, value=None, formula=None):
        name = self._resolve_sheet_name(sheet)
        if formula is not None:
            entry = {"value": 0.0, "formula": formula, "display": formula, "error": 0}
        elif value is not None:
            entry = {"value": value, "formula": "", "display": str(value), "error": 0}
        else:
            entry = {"value": 0.0, "formula": "", "display": "", "error": 0}
        self.cells[name][cell] = entry
        return {"cell": cell, "display": entry["display"]}

    def get_range(self, doc, range, sheet=None, mode="values"):
        return {"range": range, "values": [[1, 2], [3, 4]]}

    def set_range(self, doc, values, sheet=None, range=None, start_cell=None):
        if range is None and start_cell is None:
            raise ValueError("Either range or start_cell must be given.")
        return {"applied_rows": len(values)}

    def clear_range(self, doc, range, sheet=None, what="contents"):
        if what not in ("contents", "formats", "comments", "objects", "all"):
            raise ValueError(f"Unknown 'what' value '{what}'.")

    def get_used_range(self, doc, sheet=None):
        return {"start_column": 0, "start_row": 0, "end_column": 3, "end_row": 5}

    def get_sheet_summary(self, doc, sheet=None):
        name = self._resolve_sheet_name(sheet)
        idx, entry = next((i, s) for i, s in enumerate(self.sheets) if s["name"] == name)
        used = self.get_used_range(doc, sheet)
        return {
            "index": idx, "name": name, "visible": entry["visible"], "protected": entry["protected"],
            "used_range": used,
            "row_count": used["end_row"] - used["start_row"] + 1,
            "column_count": used["end_column"] - used["start_column"] + 1,
            "frozen": self.get_freeze_panes(doc, sheet),
        }

    def find_cells(self, doc, query, sheet=None, range=None, look_in="values", match="contains",
                    case_sensitive=False, max_results=100):
        if look_in not in ("values", "formulas", "comments", "all"):
            raise ValueError(f"look_in must be one of values/formulas/comments/all, got {look_in!r}")
        if match not in ("contains", "exact", "regex"):
            raise ValueError(f"match must be one of contains/exact/regex, got {match!r}")
        self.last_find_cells_call = {
            "query": query, "sheet": sheet, "range": range, "look_in": look_in,
            "match": match, "case_sensitive": case_sensitive, "max_results": max_results,
        }
        matches = [{"sheet": sheet or "Sheet1", "address": "B2", "value": query, "formula": None}]
        return {"matches": matches, "count": len(matches), "truncated": False}

    def insert_rows(self, doc, index, sheet=None, count=1):
        pass

    def delete_rows(self, doc, index, sheet=None, count=1):
        pass

    def insert_columns(self, doc, index, sheet=None, count=1):
        pass

    def delete_columns(self, doc, index, sheet=None, count=1):
        pass

    def insert_cells(self, doc, range, shift, sheet=None):
        if shift.lower() not in ("right", "down"):
            raise ValueError(f"shift must be one of right/down, got '{shift}'")

    def delete_cells(self, doc, range, shift, sheet=None):
        if shift.lower() not in ("left", "up"):
            raise ValueError(f"shift must be one of left/up, got '{shift}'")

    def copy_range(self, doc, source_range, dest_cell, source_sheet=None, dest_sheet=None, include=None):
        pass

    def move_range(self, doc, source_range, dest_cell, source_sheet=None, dest_sheet=None):
        pass

    def fill_series(self, doc, range, direction, mode, sheet=None, start=None, step=None, end=None):
        if direction.lower() not in ("down", "up", "left", "right"):
            raise ValueError(f"direction must be one of down/up/left/right, got '{direction}'")

    def autofill(self, doc, source_range, destination_range, sheet=None):
        pass

    def set_range_format(self, doc, range, properties, sheet=None):
        return [k for k in properties if k != "InvalidProperty"]

    def get_range_format(self, doc, range, sheet=None):
        return {"CellBackColor": 16777215, "CharWeight": 100.0}

    def merge_cells(self, doc, range, sheet=None, center=False):
        pass

    def unmerge_cells(self, doc, range, sheet=None):
        pass

    def set_row_height(self, doc, rows, sheet=None, height=None, unit=None, optimal=False):
        for r in rows:
            self.row_heights[r] = "optimal" if optimal else height

    def set_column_width(self, doc, columns, sheet=None, width=None, unit=None, optimal=False):
        for c in columns:
            self.col_widths[c] = "optimal" if optimal else width

    def hide_rows(self, doc, rows, sheet=None):
        self.hidden_rows.update(rows)

    def show_rows(self, doc, rows, sheet=None):
        self.hidden_rows.difference_update(rows)

    def hide_columns(self, doc, columns, sheet=None):
        self.hidden_cols.update(columns)

    def show_columns(self, doc, columns, sheet=None):
        self.hidden_cols.difference_update(columns)

    def freeze_panes(self, doc, cell, sheet=None):
        self.frozen_at = cell

    def unfreeze_panes(self, doc, sheet=None):
        self.frozen_at = None

    def get_freeze_panes(self, doc, sheet=None):
        if self.frozen_at is None:
            return {"frozen": False, "columns": 0, "rows": 0}
        return {"frozen": True, "columns": 1, "rows": 1, "cell": self.frozen_at}

    def recalculate(self, doc, hard=False):
        self.recalculated = "hard" if hard else "soft"

    def evaluate_formula(self, doc, formula, sheet=None):
        return {"formula": formula, "value": 42.0, "display": "42", "error": 0}

    def get_formula_dependencies(self, doc, range, sheet=None, direction="both"):
        result = {"range": range}
        if direction in ("precedents", "both"):
            result["precedents"] = ["Sheet1.A1"]
        if direction in ("dependents", "both"):
            result["dependents"] = ["Sheet1.C1"]
        return result

    def get_formula_errors(self, doc, sheet=None, range=None):
        return [{"cell": "B2", "error_code": 532, "display": "#DIV/0!"}]


def _install(active_document=None, sheet_names=None):
    uno_bridge = FakeUnoBridge(active_document=active_document, sheet_names=sheet_names)
    document_registry = DocumentRegistry(uno_bridge)
    runtime_state = RuntimeState()
    context.install(context.RuntimeContext(
        uno_bridge=uno_bridge, document_registry=document_registry,
        runtime_state=runtime_state, get_tools=lambda: {},
    ))
    return uno_bridge, document_registry, runtime_state


def _handler(name):
    return get_registry()[name]["handler"]


# -- sheet CRUD --

def test_list_sheets_live():
    context.reset()
    _install(active_document=FakeDocument(), sheet_names=["Sheet1", "Sheet2"])
    result = _handler("list_sheets_live")()
    assert result["success"] is True
    assert result["result"]["count"] == 2


def test_get_active_sheet_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("get_active_sheet_live")()
    assert result["success"] is True
    assert result["result"]["name"] == "Sheet1"


def test_activate_sheet_live_by_name_and_index():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument(), sheet_names=["Sheet1", "Sheet2"])
    result = _handler("activate_sheet_live")(sheet="Sheet2")
    assert result["success"] is True
    assert uno_bridge.active_sheet_name == "Sheet2"
    result2 = _handler("activate_sheet_live")(sheet="0")
    assert result2["success"] is True
    assert uno_bridge.active_sheet_name == "Sheet1"


def test_activate_sheet_live_unknown_sheet_is_object_not_found():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("activate_sheet_live")(sheet="NoSuchSheet")
    assert result["success"] is False
    assert result["error"]["code"] == "OBJECT_NOT_FOUND"


def test_insert_and_delete_sheet_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    inserted = _handler("insert_sheet_live")(name="NewSheet")
    assert inserted["success"] is True
    assert any(s["name"] == "NewSheet" for s in uno_bridge.sheets)
    deleted = _handler("delete_sheet_live")(sheet="NewSheet")
    assert deleted["success"] is True
    assert not any(s["name"] == "NewSheet" for s in uno_bridge.sheets)


def test_rename_sheet_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("rename_sheet_live")(sheet="Sheet1", new_name="Renamed")
    assert result["success"] is True
    assert uno_bridge.sheets[0]["name"] == "Renamed"


def test_move_sheet_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument(), sheet_names=["Sheet1", "Sheet2", "Sheet3"])
    result = _handler("move_sheet_live")(sheet="Sheet3", destination_index=0)
    assert result["success"] is True
    assert uno_bridge.sheets[0]["name"] == "Sheet3"


def test_copy_sheet_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("copy_sheet_live")(sheet="Sheet1", new_name="Sheet1 Copy")
    assert result["success"] is True
    assert any(s["name"] == "Sheet1 Copy" for s in uno_bridge.sheets)


def test_hide_and_show_sheet_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    hidden = _handler("hide_sheet_live")(sheet="Sheet1")
    assert hidden["success"] is True
    assert uno_bridge.sheets[0]["visible"] is False
    shown = _handler("show_sheet_live")(sheet="Sheet1")
    assert shown["success"] is True
    assert uno_bridge.sheets[0]["visible"] is True


# -- cells / ranges --

def test_get_and_set_cell_live():
    context.reset()
    _install(active_document=FakeDocument())
    set_result = _handler("set_cell_live")(cell="A1", value=42)
    assert set_result["success"] is True
    get_result = _handler("get_cell_live")(cell="A1")
    assert get_result["success"] is True
    assert get_result["result"]["value"] == 42


def test_set_cell_live_with_formula():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("set_cell_live")(cell="B1", formula="=A1+1")
    assert result["success"] is True


def test_get_range_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("get_range_live")(range="A1:B2")
    assert result["success"] is True
    assert result["result"]["values"] == [[1, 2], [3, 4]]


def test_set_range_live_requires_range_or_start_cell():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("set_range_live")(values=[[1, 2]])
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_PARAMETER"


def test_set_range_live_with_range():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("set_range_live")(values=[[1, 2], [3, 4]], range="A1:B2")
    assert result["success"] is True
    assert result["result"]["applied_rows"] == 2


def test_clear_range_live_rejects_unknown_what():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("clear_range_live")(range="A1:B2", what="not_a_real_thing")
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_PARAMETER"


def test_get_used_range_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("get_used_range_live")()
    assert result["success"] is True
    assert result["result"]["end_row"] == 5


def test_find_cells_live():
    context.reset()
    bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("find_cells_live")(query="Travel", sheet="Budget", look_in="all", match="regex")
    assert result["success"] is True
    assert result["result"]["count"] == 1
    assert result["result"]["matches"][0]["address"] == "B2"
    # Argument passthrough, not just a truthy result -- confirms the tool
    # wrapper forwards every parameter rather than silently dropping one.
    assert bridge.last_find_cells_call == {
        "query": "Travel", "sheet": "Budget", "range": None, "look_in": "all",
        "match": "regex", "case_sensitive": False, "max_results": 100,
    }


def test_find_cells_live_rejects_invalid_look_in_and_match():
    context.reset()
    _install(active_document=FakeDocument())
    for kwargs in ({"query": "x", "look_in": "bogus"}, {"query": "x", "match": "bogus"}):
        result = _handler("find_cells_live")(**kwargs)
        assert result["success"] is False
        assert result["error"]["code"] == "INVALID_PARAMETER"


# -- rows / columns --

def test_insert_and_delete_rows_columns_live():
    context.reset()
    _install(active_document=FakeDocument())
    for name, kwargs in (
        ("insert_rows_live", {"index": 0}), ("delete_rows_live", {"index": 0}),
        ("insert_columns_live", {"index": 0}), ("delete_columns_live", {"index": 0}),
    ):
        result = _handler(name)(**kwargs)
        assert result["success"] is True, name


def test_insert_cells_live_validates_shift():
    context.reset()
    _install(active_document=FakeDocument())
    ok = _handler("insert_cells_live")(range="A1:B2", shift="right")
    assert ok["success"] is True
    bad = _handler("insert_cells_live")(range="A1:B2", shift="sideways")
    assert bad["success"] is False and bad["error"]["code"] == "INVALID_PARAMETER"


def test_delete_cells_live_validates_shift():
    context.reset()
    _install(active_document=FakeDocument())
    ok = _handler("delete_cells_live")(range="A1:B2", shift="up")
    assert ok["success"] is True
    bad = _handler("delete_cells_live")(range="A1:B2", shift="sideways")
    assert bad["success"] is False and bad["error"]["code"] == "INVALID_PARAMETER"


def test_copy_range_live_and_move_range_live():
    context.reset()
    _install(active_document=FakeDocument())
    copied = _handler("copy_range_live")(source_range="A1:B2", dest_cell="D1")
    assert copied["success"] is True
    moved = _handler("move_range_live")(source_range="A1:B2", dest_cell="D5")
    assert moved["success"] is True


# -- fill / autofill --

def test_fill_series_live_validates_direction():
    context.reset()
    _install(active_document=FakeDocument())
    ok = _handler("fill_series_live")(range="A1:A5", direction="down", mode="linear")
    assert ok["success"] is True
    bad = _handler("fill_series_live")(range="A1:A5", direction="diagonal", mode="linear")
    assert bad["success"] is False and bad["error"]["code"] == "INVALID_PARAMETER"


def test_autofill_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("autofill_live")(source_range="A1:A2", destination_range="A3:A5")
    assert result["success"] is True


# -- formatting --

def test_set_range_format_live_skips_unknown_properties():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("set_range_format_live")(range="A1:B2", properties={"CellBackColor": 255, "InvalidProperty": 1})
    assert result["success"] is True
    assert result["result"]["applied"] == ["CellBackColor"]
    assert "InvalidProperty" in result["warnings"][0]


def test_get_range_format_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("get_range_format_live")(range="A1:B2")
    assert result["success"] is True
    assert "CellBackColor" in result["result"]


def test_merge_and_unmerge_cells_live():
    context.reset()
    _install(active_document=FakeDocument())
    merged = _handler("merge_cells_live")(range="A1:B2")
    assert merged["success"] is True
    unmerged = _handler("unmerge_cells_live")(range="A1:B2")
    assert unmerged["success"] is True


def test_set_row_height_and_column_width_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    row_result = _handler("set_row_height_live")(rows=[0, 1], height=500)
    assert row_result["success"] is True
    assert uno_bridge.row_heights[0] == 500
    col_result = _handler("set_column_width_live")(columns=[0], optimal=True)
    assert col_result["success"] is True
    assert uno_bridge.col_widths[0] == "optimal"


def test_hide_and_show_rows_columns_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    _handler("hide_rows_live")(rows=[2, 3])
    assert uno_bridge.hidden_rows == {2, 3}
    _handler("show_rows_live")(rows=[2])
    assert uno_bridge.hidden_rows == {3}
    _handler("hide_columns_live")(columns=[1])
    assert uno_bridge.hidden_cols == {1}
    _handler("show_columns_live")(columns=[1])
    assert uno_bridge.hidden_cols == set()


# -- freeze panes / recalculate --

def test_freeze_and_unfreeze_panes_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    frozen = _handler("freeze_panes_live")(cell="B2")
    assert frozen["success"] is True
    assert uno_bridge.frozen_at == "B2"
    unfrozen = _handler("unfreeze_panes_live")()
    assert unfrozen["success"] is True
    assert uno_bridge.frozen_at is None


def test_get_freeze_panes_live_reports_unfrozen_by_default():
    # New tool, 2026-08-22 (Brian's new-tools assignment, priority #12) --
    # freeze_panes_live/unfreeze_panes_live never had a getter.
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("get_freeze_panes_live")()
    assert result["success"] is True
    assert result["result"] == {"frozen": False, "columns": 0, "rows": 0}


def test_get_freeze_panes_live_reflects_a_real_freeze():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    _handler("freeze_panes_live")(cell="B2")
    result = _handler("get_freeze_panes_live")()
    assert result["success"] is True
    assert result["result"]["frozen"] is True
    assert result["result"]["cell"] == "B2"


def test_get_sheet_summary_live_defaults_to_active_sheet():
    # New tool, 2026-08-22 (Brian's new-tools assignment, priority #13) --
    # at-a-glance sheet summary in one call.
    context.reset()
    _install(active_document=FakeDocument(), sheet_names=["Sheet1", "Sheet2"])
    result = _handler("get_sheet_summary_live")()
    assert result["success"] is True
    r = result["result"]
    assert r["index"] == 0
    assert r["name"] == "Sheet1"
    assert r["visible"] is True
    assert r["protected"] is False
    assert r["row_count"] == 6 and r["column_count"] == 4
    assert r["frozen"] == {"frozen": False, "columns": 0, "rows": 0}


def test_get_sheet_summary_live_by_name_includes_frozen_state():
    context.reset()
    _install(active_document=FakeDocument(), sheet_names=["Sheet1", "Sheet2"])
    _handler("freeze_panes_live")(cell="B2")
    result = _handler("get_sheet_summary_live")(sheet="Sheet2")
    assert result["success"] is True
    assert result["result"]["index"] == 1
    assert result["result"]["name"] == "Sheet2"
    assert result["result"]["frozen"]["frozen"] is True
    assert result["result"]["frozen"]["cell"] == "B2"


def test_get_sheet_summary_live_unknown_sheet():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("get_sheet_summary_live")(sheet="Nonexistent")
    assert result["success"] is False


def test_recalculate_live_hard_and_soft():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    _handler("recalculate_live")()
    assert uno_bridge.recalculated == "soft"
    _handler("recalculate_live")(hard=True)
    assert uno_bridge.recalculated == "hard"


# -- formulas --

def test_evaluate_formula_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("evaluate_formula_live")(formula="=1+1")
    assert result["success"] is True
    assert result["result"]["value"] == 42.0


def test_get_formula_dependencies_live_both_directions():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("get_formula_dependencies_live")(range="B1")
    assert result["success"] is True
    assert "precedents" in result["result"] and "dependents" in result["result"]


def test_get_formula_dependencies_live_precedents_only():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("get_formula_dependencies_live")(range="B1", direction="precedents")
    assert "precedents" in result["result"]
    assert "dependents" not in result["result"]


def test_get_formula_errors_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("get_formula_errors_live")()
    assert result["success"] is True
    assert result["result"]["count"] == 1
    assert result["result"]["errors"][0]["cell"] == "B2"


if __name__ == "__main__":
    tests = [
        test_list_sheets_live,
        test_get_active_sheet_live,
        test_activate_sheet_live_by_name_and_index,
        test_activate_sheet_live_unknown_sheet_is_object_not_found,
        test_insert_and_delete_sheet_live,
        test_rename_sheet_live,
        test_move_sheet_live,
        test_copy_sheet_live,
        test_hide_and_show_sheet_live,
        test_get_and_set_cell_live,
        test_set_cell_live_with_formula,
        test_get_range_live,
        test_set_range_live_requires_range_or_start_cell,
        test_set_range_live_with_range,
        test_clear_range_live_rejects_unknown_what,
        test_get_used_range_live,
        test_insert_and_delete_rows_columns_live,
        test_insert_cells_live_validates_shift,
        test_delete_cells_live_validates_shift,
        test_copy_range_live_and_move_range_live,
        test_fill_series_live_validates_direction,
        test_autofill_live,
        test_set_range_format_live_skips_unknown_properties,
        test_get_range_format_live,
        test_merge_and_unmerge_cells_live,
        test_set_row_height_and_column_width_live,
        test_hide_and_show_rows_columns_live,
        test_freeze_and_unfreeze_panes_live,
        test_get_freeze_panes_live_reports_unfrozen_by_default,
        test_get_freeze_panes_live_reflects_a_real_freeze,
        test_get_sheet_summary_live_defaults_to_active_sheet,
        test_get_sheet_summary_live_by_name_includes_frozen_state,
        test_get_sheet_summary_live_unknown_sheet,
        test_recalculate_live_hard_and_soft,
        test_evaluate_formula_live,
        test_get_formula_dependencies_live_both_directions,
        test_get_formula_dependencies_live_precedents_only,
        test_get_formula_errors_live,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} calc_sheets tests passed.")
