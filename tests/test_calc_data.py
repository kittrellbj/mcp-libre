#!/usr/bin/env python3
"""
Unit tests for all 42 real (status="implemented") calc_data.py tools,
including create_external_link_live/refresh_external_link_live/
delete_external_link_live, built on the FakeUnoBridge's own
`area_links` dict rather than real com.sun.star.sheet.XAreaLinks
mechanics (which are live-verified instead, see uno_bridge.py's
calc-data section header).

Uses a FakeUnoBridge modeling named ranges/filters/conditional formats/
validation/pivots/scenarios/database ranges as plain dicts/lists,
mirroring the real UNOBridge methods' public signatures -- tool-layer
plumbing only (argument passing, ObjectRegistry round-tripping for
rule_id/pivot_id, error-code mapping), not real XSheetCellRange/
XDataPilotTables/XSolver mechanics, which are live-verified instead --
see docs/MCP_TOOLING_SCAFFOLD_PLAN.md's calc_data.py pass.
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


class FakeConditionalFormatEntry:
    """A plain object, not a dict -- ObjectRegistry keys by identity/
    __eq__, and a dict isn't hashable; matches the real entry's own
    "distinct object per addNew() call, no dict-shaped identity" nature."""
    def __init__(self, operator, formula1, style):
        self.operator = operator
        self.formula1 = formula1
        self.style = style


class FakePivotTable:
    def __init__(self, name, sheet, rows, columns, data_fields):
        self.name = name
        self.sheet = sheet
        self.rows = list(rows)
        self.columns = list(columns)
        self.data_fields = list(data_fields)


class FakeUnoBridge:
    """Stand-in for uno_bridge.UNOBridge's calc_data.py-facing methods."""

    def __init__(self, active_document=None):
        self.ctx = object()
        self.active_document = active_document
        self.named_ranges = {}  # name -> {"refers_to": str, "scope": str|None}
        self.filter_state = {"active": False, "conditions": []}
        self.conditional_formats = []  # list of FakeConditionalFormatEntry
        self.validations = {}  # range -> rule dict
        self.subtotals = {}
        self.pivot_tables = []  # list of FakePivotTable
        self.scenarios = {}  # name -> comment
        self.database_ranges = {}  # name -> {"sheet", "range"}
        self.formula_links = ["file:///external.ods"]
        self.area_links = {}  # link_id -> {"url", "source_area", "destination", "filter", "refresh_delay_seconds"}
        self.exported_csv = []
        self.imported_csv = []
        self.grouped_rows = []
        self.grouped_columns = []

    def get_active_document(self):
        return self.active_document

    def get_document_info(self, doc):
        return {"type": doc.doc_type, "title": doc.title, "url": doc.url, "modified": doc.modified}

    # -- named ranges --

    def list_named_ranges(self, doc, scope=None):
        return [{"name": n, "refers_to": v["refers_to"], "scope": v["scope"]}
                for n, v in self.named_ranges.items() if v["scope"] == scope]

    def create_named_range(self, doc, name, refers_to, scope=None):
        self.named_ranges[name] = {"refers_to": refers_to, "scope": scope}
        return {"name": name, "scope": scope}

    def update_named_range(self, doc, name, refers_to):
        if name not in self.named_ranges:
            raise KeyError(f"No such named range '{name}'.")
        self.named_ranges[name]["refers_to"] = refers_to

    def delete_named_range(self, doc, name):
        if name not in self.named_ranges:
            raise KeyError(f"No such named range '{name}'.")
        del self.named_ranges[name]

    # -- sort / filter --

    def sort_range(self, doc, range, keys, sheet=None, has_header=None):
        self.last_sort = (range, keys, has_header)

    def apply_filter(self, doc, range, conditions, sheet=None, options=None):
        self.filter_state = {"active": True, "conditions": conditions}

    def clear_filter(self, doc, sheet=None, range=None):
        self.filter_state = {"active": False, "conditions": []}

    def get_filter_state(self, doc, sheet=None, range=None):
        return dict(self.filter_state)

    # -- conditional formats --

    def list_conditional_format_entries(self, doc, sheet=None, range=None):
        return list(self.conditional_formats)

    def get_conditional_format_summary(self, doc, entry_ref, rule_id):
        return {"rule_id": rule_id, "operator": entry_ref.operator, "formula1": entry_ref.formula1,
                "formula2": "", "style": entry_ref.style}

    def add_conditional_format(self, doc, range, rule, sheet=None, style=None):
        entry = FakeConditionalFormatEntry(rule.get("operator", "GREATER"), rule.get("formula1", ""), style or "Default")
        self.conditional_formats.append(entry)
        return entry

    def update_conditional_format(self, doc, entry_ref, properties):
        applied = []
        for k, v in properties.items():
            if k == "InvalidProperty":
                continue
            setattr(entry_ref, k, v)
            applied.append(k)
        return applied

    def delete_conditional_format(self, doc, entry_ref):
        self.conditional_formats.remove(entry_ref)

    # -- data validation --

    def get_data_validation(self, doc, range, sheet=None):
        return self.validations.get(range, {"type": "ANY", "operator": "EQUAL", "formula1": "", "formula2": "", "show_list": None, "ignore_blank": None})

    def set_data_validation(self, doc, range, rule, sheet=None):
        self.validations[range] = rule
        return [k for k in rule if k in ("type", "operator", "formula1", "formula2", "show_list", "ignore_blank")]

    def clear_data_validation(self, doc, range, sheet=None):
        self.validations.pop(range, None)

    # -- subtotals --

    def create_subtotals(self, doc, range, group_columns, subtotal_specs, sheet=None):
        self.subtotals[range] = {"group_columns": group_columns, "specs": subtotal_specs}

    def remove_subtotals(self, doc, range, sheet=None):
        self.subtotals.pop(range, None)

    # -- pivot tables --

    def list_pivot_tables(self, doc, sheet=None):
        return list(self.pivot_tables)

    def get_pivot_table_summary(self, doc, pivot, pivot_id):
        return {
            "pivot_id": pivot_id, "name": pivot.name, "sheet": pivot.sheet,
            "output_range": "Sheet1.A1:B5",
            "layout": {"rows": pivot.rows, "columns": pivot.columns, "data": pivot.data_fields, "filters": []},
        }

    def create_pivot_table(self, doc, source, destination, rows, columns, data_fields, filters=None):
        pivot = FakePivotTable(f"Pivot{len(self.pivot_tables) + 1}", "Sheet1", rows, columns, [d["field"] for d in data_fields])
        self.pivot_tables.append(pivot)
        return pivot

    def update_pivot_table(self, pivot, configuration):
        applied = []
        if "rows" in configuration:
            pivot.rows = configuration["rows"]
            applied.append("rows")
        if "data_fields" in configuration:
            pivot.data_fields = [d["field"] for d in configuration["data_fields"]]
            applied.append("data_fields")
        return applied

    def refresh_pivot_table(self, pivot):
        pivot.refreshed = True

    def delete_pivot_table(self, doc, pivot):
        self.pivot_tables.remove(pivot)

    # -- scenarios --

    def list_scenarios(self, doc, sheet=None):
        return [{"name": n, "comment": c} for n, c in self.scenarios.items()]

    def create_scenario(self, doc, name, ranges, comment=None, options=None):
        self.scenarios[name] = comment or ""
        return {"name": name}

    def apply_scenario(self, doc, name):
        if name not in self.scenarios:
            raise KeyError(f"No such scenario '{name}'.")
        self.applied_scenario = name

    def delete_scenario(self, doc, name):
        if name not in self.scenarios:
            raise KeyError(f"No such scenario '{name}'.")
        del self.scenarios[name]

    # -- goal seek / solver --

    def goal_seek(self, doc, formula_cell, target_value, variable_cell):
        return {"converged": True, "result": target_value / 2, "divergence": 0.0}

    def solver_solve(self, doc, objective_cell, optimize, variable_cells, constraints=None):
        return {"success": True, "result_value": 42.0, "solution": [1.0, 2.0], "status": "Solved"}

    # -- database ranges --

    def list_database_ranges(self, doc):
        return [{"name": n, "sheet": v["sheet"], "range": v["range"]} for n, v in self.database_ranges.items()]

    def create_database_range(self, doc, name, sheet, range):
        self.database_ranges[name] = {"sheet": sheet, "range": range}
        return {"name": name}

    def delete_database_range(self, doc, name):
        if name not in self.database_ranges:
            raise KeyError(f"No such database range '{name}'.")
        del self.database_ranges[name]

    # -- external links --

    def list_external_links(self, doc):
        formula_links = [{"link_id": u, "url": u} for u in self.formula_links]
        area_links = [dict(v, link_id=k) for k, v in self.area_links.items()]
        return {"formula_links": formula_links, "area_links": area_links}

    def create_external_link(self, doc, source_url, source_area, destination, filter=None):
        link_id = destination
        entry = {
            "url": source_url, "source_area": source_area, "destination": destination,
            "filter": filter or "calc8", "refresh_delay_seconds": 0,
        }
        self.area_links[link_id] = entry
        return dict(entry, link_id=link_id)

    def refresh_external_link(self, doc, link_id):
        if link_id not in self.area_links:
            raise KeyError(f"No such external link '{link_id}'.")
        return dict(self.area_links[link_id], link_id=link_id)

    def delete_external_link(self, doc, link_id, keep_values=True):
        if link_id not in self.area_links:
            raise KeyError(f"No such external link '{link_id}'.")
        del self.area_links[link_id]
        return {"deleted": link_id, "kept_values": keep_values}

    # -- CSV --

    def import_csv_to_range(self, doc, file_path, destination, delimiter=",", encoding="utf-8", options=None):
        if encoding.lower() not in ("utf-8", "utf8"):
            raise NotImplementedError(f"encoding='{encoding}' not implemented.")
        self.imported_csv.append((file_path, destination))
        return {"rows": 2, "columns": 2}

    def export_range_to_csv(self, doc, range, file_path, sheet=None, delimiter=",", encoding="utf-8"):
        if encoding.lower() not in ("utf-8", "utf8"):
            raise NotImplementedError(f"encoding='{encoding}' not implemented.")
        self.exported_csv.append((range, file_path))

    # -- row/column grouping --

    def group_rows(self, doc, rows, sheet=None):
        self.grouped_rows.append(tuple(rows))

    def ungroup_rows(self, doc, rows, sheet=None):
        self.grouped_rows.remove(tuple(rows))

    def group_columns(self, doc, columns, sheet=None):
        self.grouped_columns.append(tuple(columns))

    def ungroup_columns(self, doc, columns, sheet=None):
        self.grouped_columns.remove(tuple(columns))


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


# -- named ranges --

def test_named_range_lifecycle_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    created = _handler("create_named_range_live")(name="SalesData", refers_to="$Sheet1.$A$1:$C$4")
    assert created["success"] is True
    listed = _handler("list_named_ranges_live")()
    assert listed["result"]["count"] == 1
    updated = _handler("update_named_range_live")(name="SalesData", refers_to="$Sheet1.$A$1:$D$10")
    assert updated["success"] is True
    assert uno_bridge.named_ranges["SalesData"]["refers_to"] == "$Sheet1.$A$1:$D$10"
    deleted = _handler("delete_named_range_live")(name="SalesData")
    assert deleted["success"] is True
    assert _handler("list_named_ranges_live")()["result"]["count"] == 0


def test_update_named_range_live_not_found():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("update_named_range_live")(name="NoSuch", refers_to="$A$1")
    assert result["success"] is False
    assert result["error"]["code"] == "OBJECT_NOT_FOUND"


# -- sort / filter --

def test_sort_range_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("sort_range_live")(range="A1:C4", keys=[{"column": 0, "ascending": True}])
    assert result["success"] is True


def test_apply_and_clear_filter_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    applied = _handler("apply_filter_live")(range="A1:C4", conditions=[{"column": 0, "operator": "equal", "value": "East"}])
    assert applied["success"] is True
    state = _handler("get_filter_state_live")()
    assert state["result"]["active"] is True
    cleared = _handler("clear_filter_live")()
    assert cleared["success"] is True
    assert _handler("get_filter_state_live")()["result"]["active"] is False


# -- conditional formats --

def test_conditional_format_lifecycle_live():
    context.reset()
    _install(active_document=FakeDocument())
    added = _handler("add_conditional_format_live")(range="C2:C4", rule={"operator": "GREATER", "formula1": "100"}, style="Good")
    assert added["success"] is True
    rule_id = added["result"]["rule_id"]
    listed = _handler("list_conditional_formats_live")()
    assert listed["result"]["count"] == 1
    updated = _handler("update_conditional_format_live")(rule_id=rule_id, properties={"style": "Bad", "InvalidProperty": 1})
    assert updated["success"] is True
    assert updated["result"]["applied"] == ["style"]
    deleted = _handler("delete_conditional_format_live")(rule_id=rule_id)
    assert deleted["success"] is True
    assert _handler("list_conditional_formats_live")()["result"]["count"] == 0


def test_update_conditional_format_live_not_found():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("update_conditional_format_live")(rule_id="bogus", properties={})
    assert result["success"] is False
    assert result["error"]["code"] == "OBJECT_NOT_FOUND"


# -- data validation --

def test_data_validation_lifecycle_live():
    context.reset()
    _install(active_document=FakeDocument())
    set_result = _handler("set_data_validation_live")(range="E1", rule={"type": "list", "formula1": '"A;B;C"'})
    assert set_result["success"] is True
    get_result = _handler("get_data_validation_live")(range="E1")
    assert get_result["success"] is True
    cleared = _handler("clear_data_validation_live")(range="E1")
    assert cleared["success"] is True


# -- subtotals --

def test_create_and_remove_subtotals_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    created = _handler("create_subtotals_live")(range="A1:C4", group_columns=[0], subtotal_specs=[{"column": 2, "function": "sum"}])
    assert created["success"] is True
    assert "A1:C4" in uno_bridge.subtotals
    removed = _handler("remove_subtotals_live")(range="A1:C4")
    assert removed["success"] is True
    assert "A1:C4" not in uno_bridge.subtotals


# -- pivot tables --

def test_pivot_table_lifecycle_live():
    context.reset()
    _install(active_document=FakeDocument())
    created = _handler("create_pivot_table_live")(
        source="A1:C4", destination="A6", rows=["Region"], columns=[], data_fields=[{"field": "Sales", "function": "sum"}],
    )
    assert created["success"] is True
    pivot_id = created["result"]["pivot_id"]
    listed = _handler("list_pivot_tables_live")()
    assert listed["result"]["count"] == 1
    fetched = _handler("get_pivot_table_live")(pivot_id=pivot_id)
    assert fetched["success"] is True
    assert fetched["result"]["layout"]["rows"] == ["Region"]
    updated = _handler("update_pivot_table_live")(pivot_id=pivot_id, configuration={"rows": ["Product"]})
    assert updated["success"] is True
    assert updated["result"]["applied"] == ["rows"]
    refreshed = _handler("refresh_pivot_table_live")(pivot_id=pivot_id)
    assert refreshed["success"] is True
    deleted = _handler("delete_pivot_table_live")(pivot_id=pivot_id)
    assert deleted["success"] is True
    assert _handler("list_pivot_tables_live")()["result"]["count"] == 0


# -- scenarios --

def test_scenario_lifecycle_live():
    context.reset()
    _install(active_document=FakeDocument())
    created = _handler("create_scenario_live")(name="Best Case", ranges=["A1:A3"], comment="optimistic")
    assert created["success"] is True
    listed = _handler("list_scenarios_live")()
    assert listed["result"]["count"] == 1
    applied = _handler("apply_scenario_live")(name="Best Case")
    assert applied["success"] is True
    deleted = _handler("delete_scenario_live")(name="Best Case")
    assert deleted["success"] is True
    assert _handler("list_scenarios_live")()["result"]["count"] == 0


def test_apply_scenario_live_not_found():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("apply_scenario_live")(name="NoSuch")
    assert result["success"] is False
    assert result["error"]["code"] == "OBJECT_NOT_FOUND"


# -- goal seek / solver --

def test_goal_seek_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("goal_seek_live")(formula_cell="B1", target_value=20.0, variable_cell="A1")
    assert result["success"] is True
    assert result["result"]["converged"] is True
    assert result["warnings"] == []


def test_solver_solve_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("solver_solve_live")(objective_cell="D1", optimize="max", variable_cells=["A1", "A2"])
    assert result["success"] is True
    assert result["result"]["success"] is True


# -- database ranges --

def test_database_range_lifecycle_live():
    context.reset()
    _install(active_document=FakeDocument())
    created = _handler("create_database_range_live")(name="Sales", sheet="Sheet1", range="A1:C4")
    assert created["success"] is True
    listed = _handler("list_database_ranges_live")()
    assert listed["result"]["count"] == 1
    deleted = _handler("delete_database_range_live")(name="Sales")
    assert deleted["success"] is True
    assert _handler("list_database_ranges_live")()["result"]["count"] == 0


def test_delete_database_range_live_not_found():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("delete_database_range_live")(name="NoSuch")
    assert result["success"] is False
    assert result["error"]["code"] == "OBJECT_NOT_FOUND"


# -- external links --

def test_list_external_links_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("list_external_links_live")()
    assert result["success"] is True
    assert result["result"]["count"] == 1
    assert result["result"]["formula_links"] == [{"link_id": "file:///external.ods", "url": "file:///external.ods"}]
    assert result["result"]["area_links"] == []


def test_create_refresh_delete_external_link_live_round_trip():
    context.reset()
    _install(active_document=FakeDocument())
    created = _handler("create_external_link_live")(source_url="file:///x.ods", source_area="Sheet1.A1:B2", destination="Sheet1.A1")
    assert created["success"] is True
    link_id = created["result"]["link_id"]
    assert created["result"]["url"] == "file:///x.ods"

    listed = _handler("list_external_links_live")()
    assert listed["result"]["count"] == 2  # the pre-existing formula link + the new area link
    assert any(l["link_id"] == link_id for l in listed["result"]["area_links"])

    refreshed = _handler("refresh_external_link_live")(link_id=link_id)
    assert refreshed["success"] is True
    assert refreshed["result"]["link_id"] == link_id

    deleted = _handler("delete_external_link_live")(link_id=link_id)
    assert deleted["success"] is True
    assert deleted["result"] == {"deleted": link_id, "kept_values": True}
    assert _handler("list_external_links_live")()["result"]["count"] == 1


def test_refresh_external_link_live_not_found():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("refresh_external_link_live")(link_id="NoSuchLink")
    assert result["success"] is False
    assert result["error"]["code"] == "OBJECT_NOT_FOUND"


def test_delete_external_link_live_not_found():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("delete_external_link_live")(link_id="NoSuchLink")
    assert result["success"] is False
    assert result["error"]["code"] == "OBJECT_NOT_FOUND"


# -- CSV --

def test_import_and_export_csv_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    imported = _handler("import_csv_to_range_live")(file_path="/tmp/in.csv", destination="A1")
    assert imported["success"] is True
    exported = _handler("export_range_to_csv_live")(range="A1:B2", file_path="/tmp/out.csv")
    assert exported["success"] is True
    assert uno_bridge.imported_csv == [("/tmp/in.csv", "A1")]
    assert uno_bridge.exported_csv == [("A1:B2", "/tmp/out.csv")]


def test_import_csv_to_range_live_unsupported_encoding():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("import_csv_to_range_live")(file_path="/tmp/in.csv", destination="A1", encoding="latin-1")
    assert result["success"] is False
    assert result["error"]["code"] == "UNSUPPORTED_CAPABILITY"


# -- row/column grouping --

def test_group_and_ungroup_rows_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    grouped = _handler("group_rows_live")(rows=[1, 2, 3])
    assert grouped["success"] is True
    assert (1, 2, 3) in uno_bridge.grouped_rows
    ungrouped = _handler("ungroup_rows_live")(rows=[1, 2, 3])
    assert ungrouped["success"] is True
    assert (1, 2, 3) not in uno_bridge.grouped_rows


def test_group_and_ungroup_columns_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    grouped = _handler("group_columns_live")(columns=[0, 1])
    assert grouped["success"] is True
    assert (0, 1) in uno_bridge.grouped_columns
    ungrouped = _handler("ungroup_columns_live")(columns=[0, 1])
    assert ungrouped["success"] is True
    assert (0, 1) not in uno_bridge.grouped_columns


if __name__ == "__main__":
    tests = [
        test_named_range_lifecycle_live,
        test_update_named_range_live_not_found,
        test_sort_range_live,
        test_apply_and_clear_filter_live,
        test_conditional_format_lifecycle_live,
        test_update_conditional_format_live_not_found,
        test_data_validation_lifecycle_live,
        test_create_and_remove_subtotals_live,
        test_pivot_table_lifecycle_live,
        test_scenario_lifecycle_live,
        test_apply_scenario_live_not_found,
        test_goal_seek_live,
        test_solver_solve_live,
        test_database_range_lifecycle_live,
        test_delete_database_range_live_not_found,
        test_list_external_links_live,
        test_create_refresh_delete_external_link_live_round_trip,
        test_refresh_external_link_live_not_found,
        test_delete_external_link_live_not_found,
        test_import_and_export_csv_live,
        test_import_csv_to_range_live_unsupported_encoding,
        test_group_and_ungroup_rows_live,
        test_group_and_ungroup_columns_live,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} calc_data tests passed.")
