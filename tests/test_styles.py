#!/usr/bin/env python3
"""
Unit tests for the 12 real (status="implemented") styles.py tools.

Uses a FakeUnoBridge modeling style families as plain dicts of
{name: {parent, properties, is_user_defined}} and a text-range concept as
{start, end} pairs -- enough to exercise the tool-layer logic (parameter
plumbing, error-code mapping, warnings for skipped properties) without
needing to model real UNO XStyleFamiliesSupplier/XPropertyState objects.
Real UNO service names, property names (ParaStyleName/CharStyleName), and
PropertyState enum comparisons are live-verified instead -- see the
commit message for this pass.
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


class FakeUnoBridge:
    """Stand-in for uno_bridge.UNOBridge's style methods.

    Families are a fixed set for the test doc: "ParagraphStyles" and
    "CharacterStyles", each seeded with one built-in style ("Default
    Paragraph Style" / "Default Style") that can't be deleted, matching
    real UNO's built-in-style protection.
    """

    def __init__(self, active_document=None):
        self.ctx = object()
        self.active_document = active_document
        self.families = {
            "ParagraphStyles": {"Default Paragraph Style": {"parent": None, "properties": {}, "is_user_defined": False}},
            "CharacterStyles": {"Default Style": {"parent": None, "properties": {}, "is_user_defined": False}},
        }
        self.direct_formatting = {}  # {(start, end): {prop: value}}
        self.applied_styles = []  # [(family, style_name, target)]

    def get_active_document(self):
        return self.active_document

    def get_document_info(self, doc):
        return {"type": doc.doc_type, "title": doc.title, "url": doc.url, "modified": doc.modified}

    def _family(self, family):
        if family not in self.families:
            raise KeyError(f"No such style family '{family}'. Available: {sorted(self.families)}")
        return self.families[family]

    def list_style_families(self, doc):
        return {"families": sorted(self.families.keys())}

    def list_styles(self, doc, family):
        fam = self._family(family)
        return {"family": family, "styles": [
            {"name": name, "is_user_defined": info["is_user_defined"], "is_in_use": False}
            for name, info in fam.items()
        ]}

    def get_style(self, doc, family, style_name):
        fam = self._family(family)
        if style_name not in fam:
            raise KeyError(f"No such style '{style_name}' in family '{family}'.")
        info = fam[style_name]
        return {"name": style_name, "parent_style": info["parent"], "is_user_defined": info["is_user_defined"], "is_in_use": False}

    def create_style(self, doc, family, style_name, parent_style=None, properties=None):
        fam = self._family(family)
        if style_name in fam:
            raise FileExistsError(f"Style '{style_name}' already exists in family '{family}'.")
        if family not in ("ParagraphStyles", "CharacterStyles"):
            raise NotImplementedError(f"create_style is not implemented for family '{family}'.")
        applied = []
        settable = {"Color", "Height"}  # arbitrary fake-settable property names for testing
        applied_props = {}
        for key, value in (properties or {}).items():
            if key in settable:
                applied_props[key] = value
                applied.append(key)
        fam[style_name] = {"parent": parent_style, "properties": applied_props, "is_user_defined": True}
        return applied

    def clone_style(self, doc, family, source_style, new_style_name):
        fam = self._family(family)
        if source_style not in fam:
            raise KeyError(f"No such style '{source_style}' in family '{family}'.")
        if new_style_name in fam:
            raise FileExistsError(f"Style '{new_style_name}' already exists in family '{family}'.")
        source = fam[source_style]
        fam[new_style_name] = {"parent": source["parent"], "properties": dict(source["properties"]), "is_user_defined": True}

    def update_style(self, doc, family, style_name, properties):
        fam = self._family(family)
        if style_name not in fam:
            raise KeyError(f"No such style '{style_name}' in family '{family}'.")
        settable = {"Color", "Height"}
        applied = []
        for key, value in properties.items():
            if key in settable:
                fam[style_name]["properties"][key] = value
                applied.append(key)
        return applied

    def rename_style(self, doc, family, old_name, new_name):
        fam = self._family(family)
        if old_name not in fam:
            raise KeyError(f"No such style '{old_name}' in family '{family}'.")
        if new_name in fam:
            raise FileExistsError(f"A style named '{new_name}' already exists in family '{family}'.")
        fam[new_name] = fam.pop(old_name)

    def delete_style(self, doc, family, style_name):
        fam = self._family(family)
        if style_name not in fam:
            raise KeyError(f"No such style '{style_name}' in family '{family}'.")
        if not fam[style_name]["is_user_defined"]:
            raise ValueError(f"'{style_name}' is a built-in style and cannot be deleted.")
        del fam[style_name]

    def apply_style(self, doc, family, style_name, target=None):
        fam = self._family(family)
        if style_name not in fam:
            raise KeyError(f"No such style '{style_name}' in family '{family}'.")
        if family not in ("ParagraphStyles", "CharacterStyles"):
            raise NotImplementedError(f"apply_style is not implemented for family '{family}'.")
        self.applied_styles.append((family, style_name, target))

    def get_direct_formatting(self, doc, target=None):
        key = self._target_key(target)
        return {"direct_formatting": dict(self.direct_formatting.get(key, {}))}

    def clear_direct_formatting(self, doc, target=None):
        key = self._target_key(target)
        self.direct_formatting[key] = {}

    def copy_formatting(self, doc, source, target, include=None):
        source_key = self._target_key(source)
        target_key = self._target_key(target)
        source_props = self.direct_formatting.get(source_key, {})
        applied = []
        for name, value in source_props.items():
            if include and name not in include:
                continue
            self.direct_formatting.setdefault(target_key, {})[name] = value
            applied.append(name)
        return applied

    def _target_key(self, target):
        if target is None:
            return "selection"
        if isinstance(target, dict) and "start" in target and "end" in target:
            if target["start"] < 0 or target["end"] < target["start"]:
                raise ValueError(f"Invalid target range: start={target['start']}, end={target['end']}")
            return (target["start"], target["end"])
        raise ValueError("target must be omitted (use current selection) or {'start': int, 'end': int}.")


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


# -- list_style_families_live / list_styles_live / get_style_live --

def test_list_style_families_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("list_style_families_live")()
    assert result["success"] is True
    assert result["result"]["families"] == ["CharacterStyles", "ParagraphStyles"]


def test_list_styles_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("list_styles_live")(family="ParagraphStyles")
    assert result["success"] is True
    names = {s["name"] for s in result["result"]["styles"]}
    assert names == {"Default Paragraph Style"}


def test_list_styles_live_unknown_family():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("list_styles_live")(family="NotARealFamily")
    assert result["success"] is False
    assert result["error"]["code"] == "OBJECT_NOT_FOUND"


def test_get_style_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("get_style_live")(family="ParagraphStyles", style_name="Default Paragraph Style")
    assert result["success"] is True
    assert result["result"]["is_user_defined"] is False


# -- create_style_live / clone_style_live / update_style_live --

def test_create_style_live_and_warns_on_unknown_property():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("create_style_live")(
        family="ParagraphStyles", style_name="Heading Extra",
        properties={"Color": "red", "NotARealProperty": 1},
    )
    assert result["success"] is True
    assert result["result"]["applied_properties"] == ["Color"]
    assert any("NotARealProperty" in w for w in result["warnings"])


def test_create_style_live_already_exists():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("create_style_live")(family="ParagraphStyles", style_name="Default Paragraph Style")
    assert result["success"] is False
    assert result["error"]["code"] == "FILE_EXISTS"


def test_clone_style_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("clone_style_live")(family="ParagraphStyles", source_style="Default Paragraph Style", new_style="Cloned Style")
    assert result["success"] is True
    assert "Cloned Style" in uno_bridge.families["ParagraphStyles"]


def test_update_style_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("update_style_live")(family="ParagraphStyles", style_name="Default Paragraph Style", properties={"Color": "blue"})
    assert result["success"] is True
    assert result["result"]["applied"] == ["Color"]


# -- rename_style_live / delete_style_live --

def test_rename_style_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    _handler("clone_style_live")(family="ParagraphStyles", source_style="Default Paragraph Style", new_style="Custom")
    result = _handler("rename_style_live")(family="ParagraphStyles", old_name="Custom", new_name="Renamed")
    assert result["success"] is True
    assert "Renamed" in uno_bridge.families["ParagraphStyles"]
    assert "Custom" not in uno_bridge.families["ParagraphStyles"]


def test_delete_style_live_rejects_built_in():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("delete_style_live")(family="ParagraphStyles", style_name="Default Paragraph Style")
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_PARAMETER"


def test_delete_style_live_removes_user_defined():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    _handler("clone_style_live")(family="ParagraphStyles", source_style="Default Paragraph Style", new_style="Custom")
    result = _handler("delete_style_live")(family="ParagraphStyles", style_name="Custom")
    assert result["success"] is True
    assert "Custom" not in uno_bridge.families["ParagraphStyles"]


# -- apply_style_live --

def test_apply_style_live_with_explicit_target():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("apply_style_live")(family="ParagraphStyles", style_name="Default Paragraph Style", target={"start": 0, "end": 5})
    assert result["success"] is True
    assert uno_bridge.applied_styles == [("ParagraphStyles", "Default Paragraph Style", {"start": 0, "end": 5})]


def test_apply_style_live_unsupported_family():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    uno_bridge.families["PageStyles"] = {"Default Page Style": {"parent": None, "properties": {}, "is_user_defined": False}}
    result = _handler("apply_style_live")(family="PageStyles", style_name="Default Page Style")
    assert result["success"] is False
    assert result["error"]["code"] == "UNSUPPORTED_CAPABILITY"


# -- get_direct_formatting_live / clear_direct_formatting_live / copy_formatting_live --

def test_get_and_clear_direct_formatting_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    uno_bridge.direct_formatting[(0, 5)] = {"CharWeight": "bold"}

    result = _handler("get_direct_formatting_live")(target={"start": 0, "end": 5})
    assert result["success"] is True
    assert result["result"]["direct_formatting"] == {"CharWeight": "bold"}

    cleared = _handler("clear_direct_formatting_live")(target={"start": 0, "end": 5})
    assert cleared["success"] is True
    after = _handler("get_direct_formatting_live")(target={"start": 0, "end": 5})
    assert after["result"]["direct_formatting"] == {}


def test_copy_formatting_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    uno_bridge.direct_formatting[(0, 5)] = {"CharWeight": "bold", "CharColor": "red"}

    result = _handler("copy_formatting_live")(source={"start": 0, "end": 5}, target={"start": 10, "end": 15})
    assert result["success"] is True
    assert set(result["result"]["applied"]) == {"CharWeight", "CharColor"}
    assert uno_bridge.direct_formatting[(10, 15)] == {"CharWeight": "bold", "CharColor": "red"}


def test_copy_formatting_live_respects_include():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    uno_bridge.direct_formatting[(0, 5)] = {"CharWeight": "bold", "CharColor": "red"}

    result = _handler("copy_formatting_live")(source={"start": 0, "end": 5}, target={"start": 10, "end": 15}, include=["CharColor"])
    assert result["result"]["applied"] == ["CharColor"]
    assert uno_bridge.direct_formatting[(10, 15)] == {"CharColor": "red"}


def test_get_direct_formatting_live_invalid_target():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("get_direct_formatting_live")(target={"start": 5, "end": 2})
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_PARAMETER"


if __name__ == "__main__":
    tests = [
        test_list_style_families_live,
        test_list_styles_live,
        test_list_styles_live_unknown_family,
        test_get_style_live,
        test_create_style_live_and_warns_on_unknown_property,
        test_create_style_live_already_exists,
        test_clone_style_live,
        test_update_style_live,
        test_rename_style_live,
        test_delete_style_live_rejects_built_in,
        test_delete_style_live_removes_user_defined,
        test_apply_style_live_with_explicit_target,
        test_apply_style_live_unsupported_family,
        test_get_and_clear_direct_formatting_live,
        test_copy_formatting_live,
        test_copy_formatting_live_respects_include,
        test_get_direct_formatting_live_invalid_target,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    context.reset()
    print(f"\nAll {len(tests)} styles tests passed.")
