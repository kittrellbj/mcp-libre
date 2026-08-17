#!/usr/bin/env python3
"""
Unit tests for the 42 real (status="implemented") writer_layout.py
tools -- set_chapter_numbering_live stays a pure NOT_IMPLEMENTED stub
(see writer_layout.py's module docstring) and is covered by
tests/test_tool_scaffold_contract.py's generic stub-shape contract
test, not here.

Uses a FakeUnoBridge modeling page styles/headers/footers/bookmarks as
plain dicts and fields/hyperlinks/indexes as plain objects registered
through the real ObjectRegistry (matching the real UNOBridge's own
"no natural unique name" object categories) -- tool-layer plumbing
only, not real PageStyle/XTextField/XDocumentIndexesSupplier mechanics,
which are live-verified instead -- see
docs/MCP_TOOLING_SCAFFOLD_PLAN.md's writer_layout.py pass.
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


class FakeField:
    def __init__(self, field_type, text=""):
        self.field_type = field_type
        self.text = text
        self.disposed = False


class FakeHyperlinkRange:
    def __init__(self, url, text):
        self.url = url
        self.text = text


class FakeIndex:
    def __init__(self, title, index_type):
        self.title = title
        self.index_type = index_type
        self.updated = False
        self.disposed = False


class FakeUnoBridge:
    """Stand-in for uno_bridge.UNOBridge's writer_layout.py-facing methods."""

    def __init__(self, active_document=None):
        self.ctx = object()
        self.active_document = active_document
        self.page_styles = {"Standard": {"Width": 21000, "Height": 29700, "IsLandscape": False}}
        self.headers = {}  # (page_style, variant) -> text
        self.footers = {}
        self.header_on = {}
        self.footer_on = {}
        self.bookmarks = {}  # name -> text
        self.chapter_levels = [{"level": i + 1, "Prefix": "", "Suffix": ""} for i in range(10)]
        self.line_numbering = {"enabled": False, "interval": 1, "restart_each_page": False}
        self.deleted_fields_kept_text = []

    def get_active_document(self):
        return self.active_document

    def get_document_info(self, doc):
        return {"type": doc.doc_type, "title": doc.title, "url": doc.url, "modified": doc.modified}

    # -- page layout --

    def get_page_layout(self, doc, page_style=None):
        name = page_style or "Standard"
        return dict(self.page_styles.get(name, {}), page_style=name)

    def set_page_layout(self, doc, width, height, unit, orientation=None, margins=None,
                         mirrored=None, gutter=None, page_style=None):
        name = page_style or "Standard"
        style = self.page_styles.setdefault(name, {})
        style["Width"] = width
        style["Height"] = height
        applied = ["width", "height"]
        if orientation is not None:
            style["IsLandscape"] = orientation == "landscape"
            applied.append("orientation")
        return applied

    def apply_page_preset(self, doc, preset, overrides=None):
        presets = {"letter": (8.5, 11.0, "in"), "a4": (210.0, 297.0, "mm"), "novel_6x9": (6.0, 9.0, "in")}
        if preset not in presets:
            raise ValueError(f"Unknown preset '{preset}'.")
        w, h, u = presets[preset]
        applied = self.set_page_layout(doc, w, h, u)
        return {"preset": preset, "applied": applied}

    def list_page_styles(self, doc):
        return [{"name": n, "in_use": True} for n in self.page_styles]

    def create_page_style(self, doc, style_name, based_on=None, properties=None):
        if style_name in self.page_styles:
            raise ValueError(f"Page style '{style_name}' already exists.")
        self.page_styles[style_name] = {}
        applied = [k for k in (properties or {}) if k != "InvalidProperty"]
        return {"style_name": style_name, "applied": applied}

    def update_page_style(self, doc, style_name, properties):
        if style_name not in self.page_styles:
            raise KeyError(f"No such page style '{style_name}'.")
        applied = [k for k in properties if k != "InvalidProperty"]
        self.page_styles[style_name].update({k: properties[k] for k in applied})
        return applied

    def apply_page_style(self, doc, style_name, paragraph=None, insert_break=False):
        if style_name not in self.page_styles:
            raise KeyError(f"No such page style '{style_name}'.")
        return {"paragraph": paragraph or 1, "style_name": style_name}

    def set_page_columns(self, doc, count, spacing=None, widths=None, separator=None):
        self.last_columns = (count, spacing, widths, separator)

    def insert_page_break(self, doc, at_position=None, page_style=None, page_number=None):
        return {"paragraph": (at_position or 1) + 1, "page_style": page_style}

    def remove_page_break(self, doc, paragraph=None, position=None):
        return {"paragraph": paragraph or position or 1}

    # -- headers/footers --

    def get_headers_footers(self, doc, page_style=None):
        name = page_style or "Standard"
        return {
            "page_style": name, "header_on": self.header_on.get(name, False), "footer_on": self.footer_on.get(name, False),
            "header_default": self.headers.get((name, "default")), "footer_default": self.footers.get((name, "default")),
        }

    def set_header(self, doc, text, page_style=None, variant="default", properties=None):
        name = page_style or "Standard"
        self.headers[(name, variant)] = text
        self.header_on[name] = True
        applied = ["text"]
        if properties:
            applied.extend(k for k in properties if k != "InvalidProperty")
        return applied

    def set_footer(self, doc, text, page_style=None, variant="default", properties=None):
        name = page_style or "Standard"
        self.footers[(name, variant)] = text
        self.footer_on[name] = True
        applied = ["text"]
        if properties:
            applied.extend(k for k in properties if k != "InvalidProperty")
        return applied

    def clear_header(self, doc, page_style=None, variant=None):
        name = page_style or "Standard"
        self.headers.pop((name, variant or "default"), None)
        self.header_on[name] = False

    def clear_footer(self, doc, page_style=None, variant=None):
        name = page_style or "Standard"
        self.footers.pop((name, variant or "default"), None)
        self.footer_on[name] = False

    # -- fields --

    def insert_page_number_field(self, doc, target=None, format=None, offset=0):
        return {"target": target or "cursor"}

    def insert_page_count_field(self, doc, target=None, format=None):
        return {"target": target or "cursor"}

    def insert_date_time_field(self, doc, target=None, fixed=False, format=None):
        return {"target": target or "cursor", "fixed": fixed}

    def insert_document_property_field(self, doc, property_name, target=None, fixed=False):
        known = {"author", "title", "subject", "keywords", "description", "created", "modified"}
        if property_name.lower() not in known:
            raise NotImplementedError(f"property_name='{property_name}' not implemented.")
        return {"property_name": property_name, "target": target or "cursor"}

    def list_fields(self, doc, field_type=None):
        return list(getattr(self, "_fields", []))

    def get_field_summary(self, field, field_id):
        return {"field_id": field_id, "type": field.field_type, "text": field.text}

    def update_fields(self, doc, field_ids=None):
        targets = field_ids if field_ids is not None else list(getattr(self, "_fields", []))
        return len(targets)

    def delete_field(self, field, keep_text=True):
        field.disposed = True
        if keep_text:
            self.deleted_fields_kept_text.append(field.text)

    # -- bookmarks --

    def list_bookmarks(self, doc):
        return [{"name": n, "text": t} for n, t in self.bookmarks.items()]

    def add_bookmark(self, doc, name, start=None, end=None):
        self.bookmarks[name] = ""
        return {"name": name}

    def goto_bookmark(self, doc, name, select=False):
        if name not in self.bookmarks:
            raise KeyError(f"No such bookmark '{name}'.")
        return {"name": name}

    def rename_bookmark(self, doc, old_name, new_name):
        if old_name not in self.bookmarks:
            raise KeyError(f"No such bookmark '{old_name}'.")
        self.bookmarks[new_name] = self.bookmarks.pop(old_name)

    def delete_bookmark(self, doc, name):
        if name not in self.bookmarks:
            raise KeyError(f"No such bookmark '{name}'.")
        del self.bookmarks[name]

    # -- hyperlinks --

    def insert_hyperlink(self, doc, url, text=None, target=None, name=None):
        range_obj = FakeHyperlinkRange(url, text or url)
        getattr(self, "_hyperlinks", []).append(range_obj) if hasattr(self, "_hyperlinks") else setattr(self, "_hyperlinks", [range_obj])
        return range_obj

    def list_hyperlinks(self, doc):
        return list(getattr(self, "_hyperlinks", []))

    def get_hyperlink_summary(self, range_obj, hyperlink_id):
        return {"hyperlink_id": hyperlink_id, "url": range_obj.url, "text": range_obj.text}

    def update_hyperlink(self, range_obj, url=None, text=None):
        applied = []
        if text is not None:
            range_obj.text = text
            applied.append("text")
        if url is not None:
            range_obj.url = url
            applied.append("url")
        return applied

    def remove_hyperlink(self, range_obj):
        range_obj.url = ""

    # -- cross-references / captions --

    def insert_cross_reference(self, doc, reference_type, target, display):
        known = {"bookmark", "heading", "page", "caption", "caption_number", "caption_full"}
        if reference_type.lower() not in known:
            raise NotImplementedError(f"reference_type='{reference_type}' not implemented.")
        return {"reference_type": reference_type, "target": target}

    def insert_caption(self, doc, target, label="Figure", text=None, position="below"):
        return {"category": label, "position": position}

    # -- indexes --

    def list_document_indexes(self, doc):
        return list(getattr(self, "_indexes", []))

    def get_index_summary(self, index, index_id):
        return {"index_id": index_id, "title": index.title, "type": index.index_type}

    def insert_toc(self, doc, at_position=None, title=None, max_level=10, options=None):
        toc = FakeIndex(title or "Table of Contents", "ContentIndex")
        indexes = getattr(self, "_indexes", [])
        indexes.append(toc)
        self._indexes = indexes
        return toc

    def update_index(self, index):
        index.updated = True

    def delete_index(self, doc, index, keep_content=False):
        index.disposed = True
        if index in getattr(self, "_indexes", []):
            self._indexes.remove(index)

    def insert_alphabetical_index(self, doc, at_position=None, title=None, options=None):
        idx = FakeIndex(title or "Index", "DocumentIndex")
        indexes = getattr(self, "_indexes", [])
        indexes.append(idx)
        self._indexes = indexes
        return idx

    def add_index_mark(self, doc, index_type, primary_key=None, secondary_key=None):
        return {"index_type": index_type, "primary_key": primary_key}

    # -- chapter / line numbering --

    def get_chapter_numbering(self, doc):
        return list(self.chapter_levels)

    def get_line_numbering(self, doc):
        return dict(self.line_numbering)

    def set_line_numbering(self, doc, enabled, interval=None, restart_each_page=None):
        self.line_numbering["enabled"] = enabled
        applied = ["enabled"]
        if interval is not None:
            self.line_numbering["interval"] = interval
            applied.append("interval")
        if restart_each_page is not None:
            self.line_numbering["restart_each_page"] = restart_each_page
            applied.append("restart_each_page")
        return applied


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

def test_get_and_set_page_layout_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    set_result = _handler("set_page_layout_live")(width=297, height=210, unit="mm", orientation="landscape")
    assert set_result["success"] is True
    get_result = _handler("get_page_layout_live")()
    assert get_result["success"] is True
    assert get_result["result"]["IsLandscape"] is True


def test_apply_page_preset_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("apply_page_preset_live")(preset="novel_6x9")
    assert result["success"] is True
    assert result["result"]["preset"] == "novel_6x9"


def test_page_style_lifecycle_live():
    context.reset()
    _install(active_document=FakeDocument())
    created = _handler("create_page_style_live")(style_name="Chapter", properties={"IsLandscape": True})
    assert created["success"] is True
    listed = _handler("list_page_styles_live")()
    assert listed["result"]["count"] == 2
    updated = _handler("update_page_style_live")(style_name="Chapter", properties={"Width": 15000, "InvalidProperty": 1})
    assert updated["success"] is True
    assert "InvalidProperty" in updated["warnings"][0]
    applied = _handler("apply_page_style_live")(style_name="Chapter", paragraph=3)
    assert applied["success"] is True


def test_set_page_columns_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("set_page_columns_live")(count=2, spacing=500)
    assert result["success"] is True


def test_insert_and_remove_page_break_live():
    context.reset()
    _install(active_document=FakeDocument())
    inserted = _handler("insert_page_break_live")(at_position=2, page_style="Chapter")
    assert inserted["success"] is True
    assert inserted["result"]["paragraph"] == 3
    removed = _handler("remove_page_break_live")(paragraph=3)
    assert removed["success"] is True


# -- headers/footers --

def test_header_footer_lifecycle_live():
    context.reset()
    _install(active_document=FakeDocument())
    set_header = _handler("set_header_live")(text="My Header")
    assert set_header["success"] is True
    set_footer = _handler("set_footer_live")(text="My Footer")
    assert set_footer["success"] is True
    get_result = _handler("get_headers_footers_live")()
    assert get_result["result"]["header_on"] is True
    assert get_result["result"]["header_default"] == "My Header"
    cleared_h = _handler("clear_header_live")()
    assert cleared_h["success"] is True
    cleared_f = _handler("clear_footer_live")()
    assert cleared_f["success"] is True
    final = _handler("get_headers_footers_live")()
    assert final["result"]["header_on"] is False


# -- fields --

def test_insert_field_tools_live():
    context.reset()
    _install(active_document=FakeDocument())
    assert _handler("insert_page_number_field_live")()["success"] is True
    assert _handler("insert_page_count_field_live")()["success"] is True
    assert _handler("insert_date_time_field_live")(fixed=True)["success"] is True
    assert _handler("insert_document_property_field_live")(property_name="author")["success"] is True


def test_insert_document_property_field_live_unknown():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("insert_document_property_field_live")(property_name="bogus")
    assert result["success"] is False
    assert result["error"]["code"] == "UNSUPPORTED_CAPABILITY"


def test_field_lifecycle_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    uno_bridge._fields = [FakeField("PageNumber", "1")]
    listed = _handler("list_fields_live")()
    assert listed["success"] is True
    assert listed["result"]["count"] == 1
    field_id = listed["result"]["fields"][0]["field_id"]
    updated = _handler("update_fields_live")(field_ids=[field_id])
    assert updated["success"] is True
    assert updated["result"]["updated"] == 1
    deleted = _handler("delete_field_live")(field_id=field_id, keep_text=True)
    assert deleted["success"] is True
    assert uno_bridge.deleted_fields_kept_text == ["1"]


# -- bookmarks --

def test_bookmark_lifecycle_live():
    context.reset()
    _install(active_document=FakeDocument())
    added = _handler("add_bookmark_live")(name="Chapter1")
    assert added["success"] is True
    listed = _handler("list_bookmarks_live")()
    assert listed["result"]["count"] == 1
    goto = _handler("goto_bookmark_live")(name="Chapter1")
    assert goto["success"] is True
    renamed = _handler("rename_bookmark_live")(old_name="Chapter1", new_name="Intro")
    assert renamed["success"] is True
    deleted = _handler("delete_bookmark_live")(name="Intro")
    assert deleted["success"] is True
    assert _handler("list_bookmarks_live")()["result"]["count"] == 0


def test_goto_bookmark_live_not_found():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("goto_bookmark_live")(name="NoSuch")
    assert result["success"] is False
    assert result["error"]["code"] == "OBJECT_NOT_FOUND"


# -- hyperlinks --

def test_hyperlink_lifecycle_live():
    context.reset()
    _install(active_document=FakeDocument())
    inserted = _handler("insert_hyperlink_live")(url="https://example.com", text="Click here")
    assert inserted["success"] is True
    hyperlink_id = inserted["result"]["hyperlink_id"]
    listed = _handler("list_hyperlinks_live")()
    assert listed["result"]["count"] == 1
    updated = _handler("update_hyperlink_live")(hyperlink_id=hyperlink_id, url="https://updated.com")
    assert updated["success"] is True
    removed = _handler("remove_hyperlink_live")(hyperlink_id=hyperlink_id)
    assert removed["success"] is True


# -- cross-references / captions --

def test_insert_cross_reference_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("insert_cross_reference_live")(reference_type="bookmark", target="Chapter1", display="text")
    assert result["success"] is True


def test_insert_cross_reference_live_unknown_type():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("insert_cross_reference_live")(reference_type="bogus", target="X", display="text")
    assert result["success"] is False
    assert result["error"]["code"] == "UNSUPPORTED_CAPABILITY"


def test_insert_caption_live():
    context.reset()
    uno_bridge, document_registry, _ = _install(active_document=FakeDocument())
    doc = uno_bridge.active_document
    document_id = document_registry.register_document(doc)
    shape = object()
    shape_id = document_registry.get_object_registry(document_id).register_object(shape)
    result = _handler("insert_caption_live")(target_id=shape_id, label="Figure", text="My caption")
    assert result["success"] is True
    assert result["result"]["category"] == "Figure"


# -- indexes --

def test_toc_lifecycle_live():
    context.reset()
    _install(active_document=FakeDocument())
    inserted = _handler("insert_toc_live")(title="Contents")
    assert inserted["success"] is True
    index_id = inserted["result"]["index_id"]
    listed = _handler("list_document_indexes_live")()
    assert listed["result"]["count"] == 1
    updated = _handler("update_index_live")(index_id=index_id)
    assert updated["success"] is True
    deleted = _handler("delete_index_live")(index_id=index_id)
    assert deleted["success"] is True
    assert _handler("list_document_indexes_live")()["result"]["count"] == 0


def test_insert_alphabetical_index_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("insert_alphabetical_index_live")(title="Index")
    assert result["success"] is True
    assert result["result"]["type"] == "DocumentIndex"


def test_add_index_mark_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("add_index_mark_live")(index_type="alphabetical", primary_key="Example")
    assert result["success"] is True


# -- chapter / line numbering --

def test_get_chapter_numbering_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("get_chapter_numbering_live")()
    assert result["success"] is True
    assert len(result["result"]["levels"]) == 10


def test_set_chapter_numbering_live_not_implemented():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("set_chapter_numbering_live")(levels=[{"level": 1, "prefix": "Chapter "}])
    assert result["success"] is False
    assert result["error"]["code"] == "NOT_IMPLEMENTED"


def test_get_and_set_line_numbering_live():
    context.reset()
    _install(active_document=FakeDocument())
    set_result = _handler("set_line_numbering_live")(enabled=True, interval=5)
    assert set_result["success"] is True
    get_result = _handler("get_line_numbering_live")()
    assert get_result["result"]["enabled"] is True
    assert get_result["result"]["interval"] == 5


if __name__ == "__main__":
    tests = [
        test_get_and_set_page_layout_live,
        test_apply_page_preset_live,
        test_page_style_lifecycle_live,
        test_set_page_columns_live,
        test_insert_and_remove_page_break_live,
        test_header_footer_lifecycle_live,
        test_insert_field_tools_live,
        test_insert_document_property_field_live_unknown,
        test_field_lifecycle_live,
        test_bookmark_lifecycle_live,
        test_goto_bookmark_live_not_found,
        test_hyperlink_lifecycle_live,
        test_insert_cross_reference_live,
        test_insert_cross_reference_live_unknown_type,
        test_insert_caption_live,
        test_toc_lifecycle_live,
        test_insert_alphabetical_index_live,
        test_add_index_mark_live,
        test_get_chapter_numbering_live,
        test_set_chapter_numbering_live_not_implemented,
        test_get_and_set_line_numbering_live,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} writer_layout tests passed.")
