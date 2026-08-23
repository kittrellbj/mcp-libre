#!/usr/bin/env python3
"""
Unit tests for the 16 real (status="implemented") draw.py tools.

Uses a FakeUnoBridge modeling pages as a list of plain dicts, layers as a
list of plain dicts, and shapes via the same FakeShape pattern
test_drawing_objects.py established (draw.py's assign_shape_layer_live
resolves shape_id through the same real ObjectRegistry that module's
tests already exercise) -- enough for tool-layer plumbing, not real UNO
page/layer mechanics. Real XDrawPages/XLayerManager behavior, and the
dispatch-based move_draw_page_live/duplicate_draw_page_live destination
handling, are live-verified instead -- see
docs/MCP_TOOLING_SCAFFOLD_PLAN.md's draw.py pass, not something a fake
can usefully assert.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugin", "pythonpath"))

from tools import context  # noqa: E402
from tools.documents import DocumentRegistry  # noqa: E402
from tools.registry import get_registry  # noqa: E402
from tools.runtime_state import RuntimeState  # noqa: E402


class FakeDocument:
    def __init__(self, doc_type="draw", title="Untitled", url=""):
        self.doc_type = doc_type
        self.title = title
        self.url = url
        self.modified = False


class FakeShape:
    def __init__(self):
        self.layer = None


class FakeUnoBridge:
    """Stand-in for uno_bridge.UNOBridge's draw.py-facing methods."""

    def __init__(self, active_document=None, page_names=None):
        self.ctx = object()
        self.active_document = active_document
        self.pages = [{"index": i, "name": n, "shapes": []} for i, n in enumerate(page_names or ["page1"])]
        self.active_page_name = self.pages[0]["name"]
        self.layers = [
            {"index": 0, "name": "layout", "visible": True, "locked": False, "printable": True},
        ]
        self.page_size = {}
        self.page_background = {}

    def get_active_document(self):
        return self.active_document

    def get_document_info(self, doc):
        return {"type": doc.doc_type, "title": doc.title, "url": doc.url, "modified": doc.modified}

    def _resolve_page_name(self, page):
        if page is None:
            return self.active_page_name
        for p in self.pages:
            if p["name"] == page:
                return page
        if isinstance(page, int) or (isinstance(page, str) and page.isdigit()):
            idx = int(page)
            if 0 <= idx < len(self.pages):
                return self.pages[idx]["name"]
        raise KeyError(f"No such page '{page}'.")

    # -- pages --

    def list_draw_pages(self, doc):
        return list(self.pages)

    def get_active_draw_page(self, doc):
        idx = next(i for i, p in enumerate(self.pages) if p["name"] == self.active_page_name)
        return {"index": idx, "name": self.active_page_name}

    def activate_draw_page(self, doc, page):
        name = self._resolve_page_name(page)
        self.active_page_name = name
        idx = next(i for i, p in enumerate(self.pages) if p["name"] == name)
        return {"index": idx, "name": name}

    def get_draw_page(self, doc, page=None, include_shape_metadata=False):
        name = self._resolve_page_name(page)
        idx, entry = next((i, p) for i, p in enumerate(self.pages) if p["name"] == name)
        text_entries = []
        for s in entry.get("shapes", []):
            if not s.get("text"):
                continue
            item = {"shape": s["name"], "text": s["text"]}
            if include_shape_metadata:
                item["type"] = s.get("type", "text")
                item["width"] = s.get("width", 1000)
                item["height"] = s.get("height", 500)
            text_entries.append(item)
        page_width, page_height, _unit = self.page_size.get(name, (28000, 21000, "mm"))
        background = self.page_background.get(name)
        return {
            "index": idx,
            "name": name,
            "width": page_width,
            "height": page_height,
            "shape_count": len(entry.get("shapes", [])),
            "background": {"set": background is not None, "properties": background or {}},
            "text": text_entries,
        }

    def insert_draw_page(self, doc, position=None, name=None):
        idx = position if position is not None else len(self.pages)
        page_name = name or f"page{len(self.pages) + 1}"
        self.pages.insert(idx, {"index": idx, "name": page_name})
        return {"index": idx, "name": page_name}

    def duplicate_draw_page(self, doc, page, destination=None):
        name = self._resolve_page_name(page)
        new_name = f"{name} Copy"
        idx = destination if destination is not None else len(self.pages)
        self.pages.insert(idx, {"index": idx, "name": new_name})
        return {"index": idx, "name": new_name}

    def delete_draw_page(self, doc, page):
        name = self._resolve_page_name(page)
        self.pages = [p for p in self.pages if p["name"] != name]

    def move_draw_page(self, doc, page, destination_index):
        name = self._resolve_page_name(page)
        if not (0 <= destination_index < len(self.pages)):
            raise IndexError(f"destination_index {destination_index} out of range.")
        entry = next(p for p in self.pages if p["name"] == name)
        self.pages.remove(entry)
        self.pages.insert(destination_index, entry)

    def rename_draw_page(self, doc, page, name):
        entry_name = self._resolve_page_name(page)
        for p in self.pages:
            if p["name"] == entry_name:
                p["name"] = name

    def set_draw_page_size(self, doc, width, height, unit, page=None):
        name = self._resolve_page_name(page)
        self.page_size[name] = (width, height, unit)

    def set_draw_page_background(self, doc, page, properties):
        name = self._resolve_page_name(page)
        applied = [k for k in properties if k != "InvalidProperty"]
        self.page_background[name] = {k: properties[k] for k in applied}
        return applied

    # -- layers --

    def list_layers(self, doc):
        return list(self.layers)

    def create_layer(self, doc, name, visible=True, locked=False, printable=True):
        self.layers.append({"index": len(self.layers), "name": name, "visible": visible, "locked": locked, "printable": printable})
        return {"name": name}

    def update_layer(self, doc, layer, properties):
        entry = next(l for l in self.layers if l["name"] == layer)
        applied = []
        for k, v in properties.items():
            if k == "InvalidProperty":
                continue
            if k == "name":
                entry["name"] = v
            else:
                entry[k] = v
            applied.append(k)
        return applied

    def delete_layer(self, doc, layer):
        self.layers = [l for l in self.layers if l["name"] != layer]

    def assign_shape_layer(self, doc, shape, layer):
        if not any(l["name"] == layer for l in self.layers):
            raise KeyError(f"No such layer '{layer}'.")
        shape.layer = layer

    # -- export --

    def export_draw_page(self, doc, page, file_path, format, options=None):
        if format not in ("png", "jpeg", "jpg", "svg"):
            raise NotImplementedError(f"format '{format}' not implemented.")

    def export_selection(self, doc, file_path, format="png", dpi=None):
        pass


def _install(active_document=None, page_names=None):
    uno_bridge = FakeUnoBridge(active_document=active_document, page_names=page_names)
    document_registry = DocumentRegistry(uno_bridge)
    runtime_state = RuntimeState()
    context.install(context.RuntimeContext(
        uno_bridge=uno_bridge, document_registry=document_registry,
        runtime_state=runtime_state, get_tools=lambda: {},
    ))
    return uno_bridge, document_registry, runtime_state


def _handler(name):
    return get_registry()[name]["handler"]


# -- pages --

def test_list_draw_pages_live():
    context.reset()
    _install(active_document=FakeDocument(), page_names=["page1", "page2"])
    result = _handler("list_draw_pages_live")()
    assert result["success"] is True
    assert result["result"]["count"] == 2


def test_get_active_draw_page_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("get_active_draw_page_live")()
    assert result["success"] is True
    assert result["result"]["name"] == "page1"


def test_insert_draw_page_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("insert_draw_page_live")(name="NewPage")
    assert result["success"] is True
    assert any(p["name"] == "NewPage" for p in uno_bridge.pages)


def test_activate_draw_page_live_by_name():
    # New tool, 2026-08-22 (Brian's new-tools assignment, priority #9) --
    # the Draw counterpart to Impress's activate_slide_live.
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument(), page_names=["page1", "page2"])
    result = _handler("activate_draw_page_live")(page="page2")
    assert result["success"] is True
    assert result["result"] == {"index": 1, "name": "page2"}
    assert uno_bridge.active_page_name == "page2"


def test_activate_draw_page_live_by_index():
    context.reset()
    _install(active_document=FakeDocument(), page_names=["page1", "page2", "page3"])
    result = _handler("activate_draw_page_live")(page=2)
    assert result["success"] is True
    assert result["result"]["name"] == "page3"


def test_activate_draw_page_live_unknown_page():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("activate_draw_page_live")(page="Nonexistent")
    assert result["success"] is False


def test_get_draw_page_live_defaults_to_active_page():
    # New tool, 2026-08-22 (Brian's new-tools assignment, priority #10) --
    # the Draw counterpart to Impress's get_slide_content_live.
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument(), page_names=["page1", "page2"])
    uno_bridge.pages[0]["shapes"] = [
        {"name": "Title 1", "text": "Org Chart", "type": "text"},
        {"name": "Picture 1", "text": "", "type": "image"},  # empty text -- must be skipped
    ]
    result = _handler("get_draw_page_live")()
    assert result["success"] is True
    assert result["result"]["index"] == 0
    assert result["result"]["name"] == "page1"
    assert result["result"]["text"] == [{"shape": "Title 1", "text": "Org Chart"}]
    # shape_count reflects every shape on the page, including the one
    # skipped from "text" for having no text -- not len(text).
    assert result["result"]["shape_count"] == 2


def test_get_draw_page_live_includes_page_metadata():
    # Follow-up pass, real gap flagged after this tool first shipped:
    # Brian's original spec asked for "name, dimensions, background,
    # shape count, etc." -- the first version shipped only the shape-text
    # dump. This covers the metadata fields added alongside it.
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument(), page_names=["page1"])
    uno_bridge.set_draw_page_background(None, "page1", {"FillColor": 16711680})
    result = _handler("get_draw_page_live")()
    assert result["success"] is True
    assert result["result"]["width"] == 28000
    assert result["result"]["height"] == 21000
    assert result["result"]["shape_count"] == 0
    assert result["result"]["background"]["set"] is True
    assert result["result"]["background"]["properties"] == {"FillColor": 16711680}


def test_get_draw_page_live_by_name():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument(), page_names=["page1", "page2"])
    uno_bridge.pages[1]["shapes"] = [{"name": "Note 1", "text": "Second page text", "type": "text"}]
    result = _handler("get_draw_page_live")(page="page2")
    assert result["success"] is True
    assert result["result"]["index"] == 1
    assert result["result"]["text"] == [{"shape": "Note 1", "text": "Second page text"}]


def test_get_draw_page_live_with_shape_metadata():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    uno_bridge.pages[0]["shapes"] = [{"name": "Content 2", "text": "Revenue up", "type": "text",
                                      "width": 8000, "height": 3000}]
    result = _handler("get_draw_page_live")(include_shape_metadata=True)
    assert result["success"] is True
    entry = result["result"]["text"][0]
    assert entry["type"] == "text"
    assert entry["width"] == 8000 and entry["height"] == 3000


def test_get_draw_page_live_unknown_page():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("get_draw_page_live")(page="Nonexistent")
    assert result["success"] is False


def test_duplicate_draw_page_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("duplicate_draw_page_live")(page="page1")
    assert result["success"] is True
    assert any(p["name"] == "page1 Copy" for p in uno_bridge.pages)


def test_delete_draw_page_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument(), page_names=["page1", "page2"])
    result = _handler("delete_draw_page_live")(page="page2")
    assert result["success"] is True
    assert not any(p["name"] == "page2" for p in uno_bridge.pages)


def test_move_draw_page_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument(), page_names=["page1", "page2", "page3"])
    result = _handler("move_draw_page_live")(page="page3", destination_index=0)
    assert result["success"] is True
    assert uno_bridge.pages[0]["name"] == "page3"


def test_move_draw_page_live_out_of_range():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("move_draw_page_live")(page="page1", destination_index=99)
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_RANGE"


def test_rename_draw_page_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("rename_draw_page_live")(page="page1", name="Renamed")
    assert result["success"] is True
    assert uno_bridge.pages[0]["name"] == "Renamed"


def test_set_draw_page_size_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("set_draw_page_size_live")(width=297, height=210, unit="mm")
    assert result["success"] is True
    assert uno_bridge.page_size["page1"] == (297, 210, "mm")


def test_set_draw_page_background_live_skips_unknown_properties():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("set_draw_page_background_live")(page="page1", properties={"FillColor": 255, "InvalidProperty": 1})
    assert result["success"] is True
    assert result["result"]["applied"] == ["FillColor"]
    assert "InvalidProperty" in result["warnings"][0]


# -- layers --

def test_list_layers_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("list_layers_live")()
    assert result["success"] is True
    assert result["result"]["count"] == 1


def test_create_update_delete_layer_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    created = _handler("create_layer_live")(name="MyLayer")
    assert created["success"] is True
    updated = _handler("update_layer_live")(layer="MyLayer", properties={"visible": False})
    assert updated["success"] is True
    assert next(l for l in uno_bridge.layers if l["name"] == "MyLayer")["visible"] is False
    deleted = _handler("delete_layer_live")(layer="MyLayer")
    assert deleted["success"] is True
    assert not any(l["name"] == "MyLayer" for l in uno_bridge.layers)


def test_assign_shape_layer_live():
    context.reset()
    uno_bridge, document_registry, _ = _install(active_document=FakeDocument())
    doc = uno_bridge.active_document
    document_id = document_registry.register_document(doc)
    shape = FakeShape()
    object_registry = document_registry.get_object_registry(document_id)
    shape_id = object_registry.register_object(shape)
    result = _handler("assign_shape_layer_live")(shape_id=shape_id, layer="layout")
    assert result["success"] is True
    assert shape.layer == "layout"


def test_assign_shape_layer_live_unknown_layer():
    context.reset()
    uno_bridge, document_registry, _ = _install(active_document=FakeDocument())
    doc = uno_bridge.active_document
    document_id = document_registry.register_document(doc)
    shape = FakeShape()
    shape_id = document_registry.get_object_registry(document_id).register_object(shape)
    result = _handler("assign_shape_layer_live")(shape_id=shape_id, layer="NoSuchLayer")
    assert result["success"] is False
    assert result["error"]["code"] == "OBJECT_NOT_FOUND"


# -- export --

def test_export_draw_page_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("export_draw_page_live")(page="page1", file_path="/tmp/out.png", format="png")
    assert result["success"] is True


def test_export_draw_page_live_unsupported_format():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("export_draw_page_live")(page="page1", file_path="/tmp/out.pdf", format="pdf")
    assert result["success"] is False
    assert result["error"]["code"] == "UNSUPPORTED_CAPABILITY"


def test_export_selection_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("export_selection_live")(file_path="/tmp/sel.png")
    assert result["success"] is True


if __name__ == "__main__":
    tests = [
        test_list_draw_pages_live,
        test_get_active_draw_page_live,
        test_insert_draw_page_live,
        test_activate_draw_page_live_by_name,
        test_activate_draw_page_live_by_index,
        test_activate_draw_page_live_unknown_page,
        test_get_draw_page_live_defaults_to_active_page,
        test_get_draw_page_live_includes_page_metadata,
        test_get_draw_page_live_by_name,
        test_get_draw_page_live_with_shape_metadata,
        test_get_draw_page_live_unknown_page,
        test_duplicate_draw_page_live,
        test_delete_draw_page_live,
        test_move_draw_page_live,
        test_move_draw_page_live_out_of_range,
        test_rename_draw_page_live,
        test_set_draw_page_size_live,
        test_set_draw_page_background_live_skips_unknown_properties,
        test_list_layers_live,
        test_create_update_delete_layer_live,
        test_assign_shape_layer_live,
        test_assign_shape_layer_live_unknown_layer,
        test_export_draw_page_live,
        test_export_draw_page_live_unsupported_format,
        test_export_selection_live,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} draw tests passed.")
