#!/usr/bin/env python3
"""
Unit tests for the 37 real (status="implemented") writer_tables.py tools
-- mail_merge_live stays a pure NOT_IMPLEMENTED stub (see writer_tables.py's
module docstring) and is covered by tests/test_tool_scaffold_contract.py's
generic stub-shape contract test, not here.

Uses a FakeUnoBridge modeling tables/sections as plain dicts (matching
the real UNOBridge's own name-based, no-registry resolution for these
two categories) and footnotes/endnotes/content controls as plain objects
registered through the real ObjectRegistry -- tool-layer plumbing only,
not real XTextTable/XTextSection/XFootnote/XContentControl mechanics,
which are live-verified instead -- see
docs/MCP_TOOLING_SCAFFOLD_PLAN.md's writer_tables.py pass.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugin", "pythonpath"))

from tools import context  # noqa: E402
from tools.documents import DocumentRegistry  # noqa: E402
from tools.registry import get_registry  # noqa: E402
from tools.runtime_state import RuntimeState  # noqa: E402


class FakeDocument:
    def __init__(self, doc_type="writer", title="Untitled", url=""):
        self.doc_type = doc_type
        self.title = title
        self.url = url
        self.modified = False


class FakeNote:
    def __init__(self, text=""):
        self.text = text
        self.disposed = False


class FakeContentControl:
    def __init__(self, tag="", title="", text="", cc_type="plaintext"):
        self.tag = tag
        self.title = title
        self.text = text
        self.cc_type = cc_type
        self.disposed = False


class FakeUnoBridge:
    """Stand-in for uno_bridge.UNOBridge's writer_tables.py-facing methods."""

    def __init__(self, active_document=None):
        self.ctx = object()
        self.active_document = active_document
        self.tables = {}  # name -> {"rows": int, "columns": int, "cells": {(r,c): str}}
        self.sections = {}  # name -> {"is_protected": bool, "is_visible": bool, "properties": dict}
        self._footnotes = []
        self._endnotes = []
        self._content_controls = []
        self.note_settings = {
            "footnote": {"NumberingType": 4, "Prefix": "", "Suffix": ")"},
            "endnote": {"NumberingType": 2, "Prefix": "", "Suffix": ""},
        }
        self._table_seq = 0

    def get_active_document(self):
        return self.active_document

    def get_document_info(self, doc):
        return {"type": doc.doc_type, "title": doc.title, "url": doc.url, "modified": doc.modified}

    # -- tables --

    def list_tables(self, doc):
        return [{"table_id": name, "rows": t["rows"], "columns": t["columns"]} for name, t in self.tables.items()]

    def insert_table(self, doc, rows, columns, at_position=None, name=None, style=None):
        self._table_seq += 1
        table_id = name or f"Table{self._table_seq}"
        self.tables[table_id] = {"rows": rows, "columns": columns, "cells": {}}
        return {"table_id": table_id, "rows": rows, "columns": columns, "style_applied": bool(style)}

    def _require_table(self, table_id):
        if table_id not in self.tables:
            raise KeyError(f"No such table {table_id!r}.")
        return self.tables[table_id]

    def get_table(self, doc, table_id, include_cells=False):
        table = self._require_table(table_id)
        result = {"table_id": table_id, "rows": table["rows"], "columns": table["columns"]}
        if include_cells:
            result["cells"] = [
                [table["cells"].get((r, c), "") for c in range(table["columns"])]
                for r in range(table["rows"])
            ]
        return result

    def get_table_range(self, doc, table_id, start_cell, end_cell):
        table = self._require_table(table_id)
        return [[table["cells"].get((0, 0), "")]]

    def set_table_range(self, doc, table_id, start_cell, values):
        table = self._require_table(table_id)
        written = 0
        for r, row in enumerate(values):
            for c, value in enumerate(row):
                table["cells"][(r, c)] = str(value)
                written += 1
        return {"written": written}

    def insert_table_rows(self, doc, table_id, index, count=1):
        table = self._require_table(table_id)
        table["rows"] += count
        return {"rows": table["rows"]}

    def delete_table_rows(self, doc, table_id, index, count=1):
        table = self._require_table(table_id)
        table["rows"] -= count
        return {"rows": table["rows"]}

    def insert_table_columns(self, doc, table_id, index, count=1):
        table = self._require_table(table_id)
        table["columns"] += count
        return {"columns": table["columns"]}

    def delete_table_columns(self, doc, table_id, index, count=1):
        table = self._require_table(table_id)
        table["columns"] -= count
        return {"columns": table["columns"]}

    def merge_table_cells(self, doc, table_id, start_cell, end_cell):
        self._require_table(table_id)
        return {"merged": f"{start_cell}:{end_cell}"}

    def split_table_cell(self, doc, table_id, cell, count, direction):
        self._require_table(table_id)
        if direction not in ("horizontal", "vertical"):
            raise ValueError(f"Invalid direction {direction!r}.")
        return {"split": cell, "count": count, "direction": direction}

    def set_table_format(self, doc, table_id, properties):
        self._require_table(table_id)
        return list(properties.keys())

    def set_table_cell_format(self, doc, table_id, range, properties):
        self._require_table(table_id)
        return {"applied": sorted(properties.keys()), "cells": 1}

    def sort_table(self, doc, table_id, keys):
        self._require_table(table_id)
        return {"sorted_keys": len(keys)}

    def delete_table(self, doc, table_id):
        self._require_table(table_id)
        del self.tables[table_id]
        return {"deleted": table_id}

    def convert_text_to_table(self, doc, range=None, delimiter="\t", options=None):
        self._table_seq += 1
        table_id = f"Table{self._table_seq}"
        self.tables[table_id] = {"rows": 2, "columns": 2, "cells": {}}
        return {"table_id": table_id, "rows": 2, "columns": 2}

    def convert_table_to_text(self, doc, table_id, delimiter="\t"):
        table = self._require_table(table_id)
        del self.tables[table_id]
        return {"lines": table["rows"]}

    # -- sections --

    def list_sections(self, doc):
        return [
            {"section_id": name, "is_protected": s["is_protected"], "is_visible": s["is_visible"]}
            for name, s in self.sections.items()
        ]

    def insert_section(self, doc, name, range=None, columns=None, protected=False):
        self.sections[name] = {"is_protected": protected, "is_visible": True, "properties": {}}
        return {"section_id": name}

    def _require_section(self, section_id):
        if section_id not in self.sections:
            raise KeyError(f"No such section {section_id!r}.")
        return self.sections[section_id]

    def update_section(self, doc, section_id, properties):
        section = self._require_section(section_id)
        section["properties"].update(properties)
        return list(properties.keys())

    def delete_section(self, doc, section_id, keep_content=True):
        self._require_section(section_id)
        del self.sections[section_id]
        return {"deleted": section_id, "keep_content": keep_content}

    # -- footnotes / endnotes --

    def add_footnote(self, doc, text, position=None):
        note = FakeNote(text)
        self._footnotes.append(note)
        return note

    def list_footnotes(self, doc):
        return list(self._footnotes)

    @staticmethod
    def get_footnote_summary(footnote, footnote_id):
        return {"footnote_id": footnote_id, "text": footnote.text}

    def update_footnote(self, footnote, text):
        footnote.text = text
        return {"text": text}

    def delete_footnote(self, footnote):
        footnote.disposed = True
        self._footnotes.remove(footnote)

    def add_endnote(self, doc, text, position=None):
        note = FakeNote(text)
        self._endnotes.append(note)
        return note

    def list_endnotes(self, doc):
        return list(self._endnotes)

    @staticmethod
    def get_endnote_summary(endnote, endnote_id):
        return {"endnote_id": endnote_id, "text": endnote.text}

    def update_endnote(self, endnote, text):
        endnote.text = text
        return {"text": text}

    def delete_endnote(self, endnote):
        endnote.disposed = True
        self._endnotes.remove(endnote)

    def get_note_settings(self, doc, note_type):
        if note_type not in self.note_settings:
            raise ValueError(f"Unknown note_type {note_type!r}.")
        return dict(self.note_settings[note_type])

    def set_note_settings(self, doc, note_type, settings):
        if note_type not in self.note_settings:
            raise ValueError(f"Unknown note_type {note_type!r}.")
        self.note_settings[note_type].update(settings)
        return list(settings.keys())

    # -- content controls --

    def list_content_controls(self, doc):
        return list(self._content_controls)

    def insert_content_control(self, doc, range=None, tag=None, title=None, type=None):
        cc = FakeContentControl(tag=tag or "", title=title or "", cc_type=type or "plaintext")
        self._content_controls.append(cc)
        return cc

    @staticmethod
    def get_content_control_summary(cc, control_id):
        return {"control_id": control_id, "tag": cc.tag, "title": cc.title, "text": cc.text}

    def get_content_control(self, cc, control_id):
        return {"control_id": control_id, "tag": cc.tag, "title": cc.title, "text": cc.text, "type": cc.cc_type}

    def set_content_control(self, cc, text=None, properties=None):
        applied = []
        if text is not None:
            cc.text = text
            applied.append("text")
        if properties:
            for key, value in properties.items():
                setattr(cc, key, value)
                applied.append(key)
        return applied

    def delete_content_control(self, doc, cc, keep_content=True):
        # Real UNOBridge can never remove the wrapper in this LibreOffice
        # build (see uno_bridge.py's delete_content_control() docstring)
        # -- the fake mirrors that: content is cleared/kept, control stays
        # registered, wrapper_removed is always False.
        if not keep_content:
            cc.text = ""
        return False

    # -- mail merge --

    def preview_mail_merge(self, doc, data_source, command, rows=None, output="preview"):
        all_rows = [{"Name": "Alice", "Email": "alice@example.com"}, {"Name": "Bob", "Email": "bob@example.com"}]
        selected = [all_rows[i] for i in rows] if rows is not None else all_rows
        return {"columns": ["Name", "Email"], "row_count": len(all_rows),
                "previews": [{"row": r, "resolved_fields": {}} for r in selected]}


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


# -- tables --

def test_table_lifecycle_live():
    context.reset()
    _install(active_document=FakeDocument())
    inserted = _handler("insert_table_live")(rows=3, columns=3)
    assert inserted["success"] is True
    table_id = inserted["result"]["table_id"]

    listed = _handler("list_tables_live")()
    assert listed["result"]["count"] == 1

    got = _handler("get_table_live")(table_id=table_id, include_cells=True)
    assert got["result"]["rows"] == 3 and got["result"]["columns"] == 3

    set_result = _handler("set_table_range_live")(table_id=table_id, start_cell="A1", values=[["x", "y"]])
    assert set_result["result"]["written"] == 2

    range_result = _handler("get_table_range_live")(table_id=table_id, start_cell="A1", end_cell="A1")
    assert range_result["success"] is True

    rows_result = _handler("insert_table_rows_live")(table_id=table_id, index=1, count=1)
    assert rows_result["result"]["rows"] == 4
    del_rows = _handler("delete_table_rows_live")(table_id=table_id, index=1, count=1)
    assert del_rows["result"]["rows"] == 3

    cols_result = _handler("insert_table_columns_live")(table_id=table_id, index=1, count=1)
    assert cols_result["result"]["columns"] == 4
    del_cols = _handler("delete_table_columns_live")(table_id=table_id, index=1, count=1)
    assert del_cols["result"]["columns"] == 3

    deleted = _handler("delete_table_live")(table_id=table_id)
    assert deleted["result"]["deleted"] == table_id
    assert _handler("list_tables_live")()["result"]["count"] == 0


def test_table_lookup_not_found():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("get_table_live")(table_id="NoSuchTable")
    assert result["success"] is False
    assert result["error"]["code"] == "OBJECT_NOT_FOUND"


def test_merge_and_split_table_cells_live():
    context.reset()
    _install(active_document=FakeDocument())
    table_id = _handler("insert_table_live")(rows=3, columns=3)["result"]["table_id"]
    merged = _handler("merge_table_cells_live")(table_id=table_id, start_cell="A1", end_cell="B1")
    assert merged["success"] is True
    split = _handler("split_table_cell_live")(table_id=table_id, cell="A1", count=2, direction="horizontal")
    assert split["success"] is True
    bad_direction = _handler("split_table_cell_live")(table_id=table_id, cell="A1", count=2, direction="sideways")
    assert bad_direction["success"] is False
    assert bad_direction["error"]["code"] == "INVALID_PARAMETER"


def test_table_and_cell_format_live():
    context.reset()
    _install(active_document=FakeDocument())
    table_id = _handler("insert_table_live")(rows=2, columns=2)["result"]["table_id"]
    table_fmt = _handler("set_table_format_live")(table_id=table_id, properties={"RepeatHeadline": True})
    assert table_fmt["result"]["applied"] == ["RepeatHeadline"]
    cell_fmt = _handler("set_table_cell_format_live")(table_id=table_id, range="A1:B1", properties={"BackColor": 0xFF0000})
    assert cell_fmt["result"]["cells"] == 1


def test_sort_table_live():
    context.reset()
    _install(active_document=FakeDocument())
    table_id = _handler("insert_table_live")(rows=3, columns=2)["result"]["table_id"]
    result = _handler("sort_table_live")(table_id=table_id, keys=[{"column": "A", "ascending": True}])
    assert result["result"]["sorted_keys"] == 1


def test_convert_text_table_roundtrip_live():
    context.reset()
    _install(active_document=FakeDocument())
    to_table = _handler("convert_text_to_table_live")(range="0-20", delimiter="\t")
    assert to_table["success"] is True
    table_id = to_table["result"]["table_id"]
    to_text = _handler("convert_table_to_text_live")(table_id=table_id, delimiter="\t")
    assert to_text["success"] is True


# -- sections --

def test_section_lifecycle_live():
    context.reset()
    _install(active_document=FakeDocument())
    inserted = _handler("insert_section_live")(name="Intro", range={"start": 0, "end": 10}, protected=False)
    assert inserted["result"]["section_id"] == "Intro"

    listed = _handler("list_sections_live")()
    assert listed["result"]["count"] == 1

    updated = _handler("update_section_live")(section_id="Intro", properties={"IsProtected": True})
    assert updated["result"]["applied"] == ["IsProtected"]

    deleted = _handler("delete_section_live")(section_id="Intro", keep_content=True)
    assert deleted["result"]["keep_content"] is True
    assert _handler("list_sections_live")()["result"]["count"] == 0


def test_section_lookup_not_found():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("update_section_live")(section_id="NoSuch", properties={})
    assert result["success"] is False
    assert result["error"]["code"] == "OBJECT_NOT_FOUND"


# -- footnotes / endnotes --

def test_footnote_lifecycle_live():
    context.reset()
    _install(active_document=FakeDocument())
    added = _handler("add_footnote_live")(text="First footnote")
    footnote_id = added["result"]["footnote_id"]

    listed = _handler("list_footnotes_live")()
    assert listed["result"]["count"] == 1

    updated = _handler("update_footnote_live")(footnote_id=footnote_id, text="Updated footnote")
    assert updated["result"]["text"] == "Updated footnote"

    deleted = _handler("delete_footnote_live")(footnote_id=footnote_id)
    assert deleted["result"]["deleted"] == footnote_id
    assert _handler("list_footnotes_live")()["result"]["count"] == 0


def test_endnote_lifecycle_live():
    context.reset()
    _install(active_document=FakeDocument())
    added = _handler("add_endnote_live")(text="First endnote")
    endnote_id = added["result"]["endnote_id"]

    listed = _handler("list_endnotes_live")()
    assert listed["result"]["count"] == 1

    updated = _handler("update_endnote_live")(endnote_id=endnote_id, text="Updated endnote")
    assert updated["result"]["text"] == "Updated endnote"

    deleted = _handler("delete_endnote_live")(endnote_id=endnote_id)
    assert deleted["result"]["deleted"] == endnote_id
    assert _handler("list_endnotes_live")()["result"]["count"] == 0


def test_note_settings_live():
    context.reset()
    _install(active_document=FakeDocument())
    got = _handler("get_note_settings_live")(note_type="footnote")
    assert got["result"]["Suffix"] == ")"

    updated = _handler("set_note_settings_live")(note_type="footnote", settings={"Suffix": "]"})
    assert updated["result"]["applied"] == ["Suffix"]

    bad_type = _handler("get_note_settings_live")(note_type="bogus")
    assert bad_type["success"] is False
    assert bad_type["error"]["code"] == "INVALID_PARAMETER"


# -- content controls --

def test_content_control_lifecycle_live():
    context.reset()
    _install(active_document=FakeDocument())
    inserted = _handler("insert_content_control_live")(range="0-10", tag="mytag", title="My Title", type="plaintext")
    assert inserted["success"] is True
    control_id = inserted["result"]["control_id"]

    listed = _handler("list_content_controls_live")()
    assert listed["result"]["count"] == 1

    got = _handler("get_content_control_live")(control_id=control_id)
    assert got["result"]["tag"] == "mytag"

    updated = _handler("set_content_control_live")(control_id=control_id, text="new text")
    assert updated["result"]["applied"] == ["text"]

    deleted = _handler("delete_content_control_live")(control_id=control_id, keep_content=True)
    assert deleted["result"]["deleted"] == control_id
    assert deleted["result"]["wrapper_removed"] is False
    assert deleted["warnings"], "expected a warning that the wrapper could not be removed"
    # The wrapper itself can never be removed in this LibreOffice build
    # (see uno_bridge.py's delete_content_control() docstring) -- it stays
    # enumerable, just no longer tracked under the deleted control_id.
    assert _handler("list_content_controls_live")()["result"]["count"] == 1


def test_content_control_lookup_not_found():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("get_content_control_live")(control_id="NoSuchControl")
    assert result["success"] is False
    assert result["error"]["code"] == "OBJECT_NOT_FOUND"


# -- mail merge --

def test_preview_mail_merge_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("preview_mail_merge_live")(data_source="/tmp/contacts", command="contacts", rows=[0])
    assert result["success"] is True
    assert result["result"]["row_count"] == 2
    assert len(result["result"]["previews"]) == 1


def test_mail_merge_live_not_implemented():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("mail_merge_live")(data_source="/tmp/contacts", command="contacts", output_mode="files")
    assert result["success"] is False
    assert result["error"]["code"] == "NOT_IMPLEMENTED"


if __name__ == "__main__":
    tests = [
        test_table_lifecycle_live,
        test_table_lookup_not_found,
        test_merge_and_split_table_cells_live,
        test_table_and_cell_format_live,
        test_sort_table_live,
        test_convert_text_table_roundtrip_live,
        test_section_lifecycle_live,
        test_section_lookup_not_found,
        test_footnote_lifecycle_live,
        test_endnote_lifecycle_live,
        test_note_settings_live,
        test_content_control_lifecycle_live,
        test_content_control_lookup_not_found,
        test_preview_mail_merge_live,
        test_mail_merge_live_not_implemented,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} writer_tables tests passed.")
