#!/usr/bin/env python3
"""
Unit tests for the 34 real (status="implemented") impress.py tools --
the remaining 7 (add/update/delete/reorder_animation_live,
next/previous_slideshow_effect_live, goto_slideshow_slide_live) stay pure
NOT_IMPLEMENTED stubs (see impress.py's module docstring for why) and are
covered by tests/test_tool_scaffold_contract.py's generic stub-shape
contract test, not here.

Uses a FakeUnoBridge modeling slides/masters/notes/transitions/
animations/custom shows as plain dicts/lists, mirroring the real
UNOBridge impress2 methods' public signatures -- enough for tool-layer
plumbing (argument passing, applied/skipped property reporting,
error-code mapping), not real XDrawPages/XPresentation/XAnimationNode
mechanics. Those are live-verified instead -- see
docs/MCP_TOOLING_SCAFFOLD_PLAN.md's impress.py pass, including the
documented move_slide_live/duplicate_slide_live destination
verification gap.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugin", "pythonpath"))

from tools import context  # noqa: E402
from tools.documents import DocumentRegistry  # noqa: E402
from tools.registry import get_registry  # noqa: E402
from tools.runtime_state import RuntimeState  # noqa: E402


class FakeDocument:
    def __init__(self, doc_type="impress", title="Untitled", url=""):
        self.doc_type = doc_type
        self.title = title
        self.url = url
        self.modified = False


class FakeShape:
    def __init__(self):
        self.on_click = None
        self.bookmark = None


def _new_slide(name, layout=0, master="Default", hidden=False):
    return {"name": name, "layout": layout, "master": master, "hidden": hidden}


class FakeUnoBridge:
    """Stand-in for uno_bridge.UNOBridge's impress.py-facing methods."""

    def __init__(self, active_document=None, slide_names=None):
        self.ctx = object()
        self.active_document = active_document
        self.slides = [_new_slide(n) for n in (slide_names or ["Slide 1"])]
        self.active_slide_name = self.slides[0]["name"]
        self.masters = [{"name": "Default"}]
        self.notes = {}
        self.transitions = {}
        self.presentation_settings = {"IsFullScreen": True, "IsMouseVisible": False, "IsEndless": False}
        self.custom_shows = {}
        self.slideshow_started = False
        self.exported = []

    def get_active_document(self):
        return self.active_document

    def get_document_info(self, doc):
        return {"type": doc.doc_type, "title": doc.title, "url": doc.url, "modified": doc.modified}

    def _find(self, slide):
        if isinstance(slide, int):
            return self.slides[slide]
        for s in self.slides:
            if s["name"] == slide:
                return s
        raise KeyError(f"No such slide '{slide}'.")

    # -- slide CRUD --

    def list_slides(self, doc):
        return [dict(s, index=i) for i, s in enumerate(self.slides)]

    def get_active_slide(self, doc):
        idx = next(i for i, s in enumerate(self.slides) if s["name"] == self.active_slide_name)
        return {"index": idx, "name": self.active_slide_name}

    def activate_slide(self, doc, slide):
        self.active_slide_name = self._find(slide)["name"]

    def insert_slide(self, doc, position=None, layout=None, master=None):
        idx = position if position is not None else len(self.slides)
        name = f"Slide {len(self.slides) + 1}"
        entry = _new_slide(name, layout=layout if layout is not None else 0, master=master or "Default")
        self.slides.insert(idx, entry)
        return {"index": idx, "name": name}

    def duplicate_slide(self, doc, slide, destination=None):
        source = self._find(slide)
        new_name = f"{source['name']} Copy"
        idx = destination if destination is not None else len(self.slides)
        self.slides.insert(idx, _new_slide(new_name, layout=source["layout"], master=source["master"]))
        return {"index": idx, "name": new_name}

    def delete_slide(self, doc, slide):
        entry = self._find(slide)
        self.slides.remove(entry)

    def move_slide(self, doc, slide, destination_index):
        if not (0 <= destination_index < len(self.slides)):
            raise IndexError(f"destination_index {destination_index} out of range.")
        entry = self._find(slide)
        self.slides.remove(entry)
        self.slides.insert(destination_index, entry)

    def rename_slide(self, doc, slide, name):
        self._find(slide)["name"] = name

    def hide_slide(self, doc, slide):
        self._find(slide)["hidden"] = True

    def show_slide(self, doc, slide):
        self._find(slide)["hidden"] = False

    def get_slide_layout(self, doc, slide):
        s = self._find(slide)
        return {"layout": s["layout"], "master": s["master"], "width": 28000, "height": 15750, "orientation": "landscape"}

    def set_slide_layout(self, doc, slide, layout):
        self._find(slide)["layout"] = layout

    def set_slide_size(self, doc, width, height, unit):
        self.slide_size = (width, height, unit)

    def set_slide_background(self, doc, slide, properties):
        applied = [k for k in properties if k != "InvalidProperty"]
        self._find(slide)["background"] = {k: properties[k] for k in applied}
        return applied

    # -- master pages --

    def list_master_pages(self, doc):
        return list(self.masters)

    def apply_master_page(self, doc, master, slides):
        if not any(m["name"] == master for m in self.masters):
            raise KeyError(f"No such master page '{master}'.")
        applied = []
        for s in slides:
            entry = self._find(s)
            entry["master"] = master
            applied.append(entry["name"])
        return applied

    def create_master_page(self, doc, name, based_on=None):
        self.masters.append({"name": name})
        return {"name": name}

    def delete_master_page(self, doc, master):
        self.masters = [m for m in self.masters if m["name"] != master]

    # -- notes --

    def get_speaker_notes(self, doc, slide):
        return self.notes.get(self._find(slide)["name"], "")

    def set_speaker_notes(self, doc, slide, text):
        self.notes[self._find(slide)["name"]] = text

    # -- transitions --

    def get_slide_transition(self, doc, slide):
        return self.transitions.get(self._find(slide)["name"], {
            "transition_type": 0, "transition_subtype": 0, "transition_direction": True,
            "duration": 1.0, "advance": "on_click", "auto_after": None, "sound": None, "loop_sound": False,
        })

    def set_slide_transition(self, doc, slide, effect=None, duration=None, advance=None, auto_after=None):
        name = self._find(slide)["name"]
        entry = self.transitions.setdefault(name, {})
        applied = []
        if effect is not None:
            entry["transition_type"] = effect
            applied.append("effect")
        if duration is not None:
            entry["duration"] = duration
            applied.append("duration")
        if advance is not None:
            entry["advance"] = advance
            applied.append("advance")
        if auto_after is not None:
            entry["auto_after"] = auto_after
            applied.append("auto_after")
        return applied

    # -- animations --

    def list_animations(self, doc, slide):
        self._find(slide)
        return []

    # -- click action --

    def set_shape_click_action(self, doc, shape, action, target=None):
        shape.on_click = action
        applied = ["action"]
        if target is not None:
            shape.bookmark = target
            applied.append("target")
        return applied

    # -- presentation settings --

    def get_presentation_settings(self, doc):
        return dict(self.presentation_settings)

    def set_presentation_settings(self, doc, settings):
        applied = [k for k in settings if k != "InvalidSetting"]
        self.presentation_settings.update({k: settings[k] for k in applied})
        return applied

    # -- custom shows --

    def list_custom_shows(self, doc):
        return [{"name": n, "slides": s} for n, s in self.custom_shows.items()]

    def create_custom_show(self, doc, name, slides):
        names = [self._find(s)["name"] for s in slides]
        self.custom_shows[name] = names
        return {"name": name, "count": len(names)}

    def update_custom_show(self, doc, name, slides):
        if name not in self.custom_shows:
            raise KeyError(f"No such custom show '{name}'.")
        names = [self._find(s)["name"] for s in slides]
        self.custom_shows[name] = names
        return {"name": name, "count": len(names)}

    def delete_custom_show(self, doc, name):
        if name not in self.custom_shows:
            raise KeyError(f"No such custom show '{name}'.")
        del self.custom_shows[name]

    # -- slideshow --

    def start_slideshow(self, doc, custom_show=None, first_slide=None):
        self.slideshow_started = True

    def stop_slideshow(self, doc):
        self.slideshow_started = False

    # -- export --

    def export_slide(self, doc, slide, file_path, format="png", width=None, height=None, dpi=None):
        if format not in ("png", "jpeg", "jpg", "svg"):
            raise NotImplementedError(f"format '{format}' not implemented.")
        self.exported.append((self._find(slide)["name"], file_path, format))

    def export_all_slides(self, doc, output_dir, format="png", slides=None, naming=None):
        targets = slides if slides else [s["name"] for s in self.slides]
        prefix = naming or "slide"
        files = []
        for i, slide in enumerate(targets):
            file_path = os.path.join(output_dir, f"{prefix}_{i + 1}.{format}")
            self.export_slide(doc, slide, file_path, format)
            files.append(file_path)
        return files


def _install(active_document=None, slide_names=None):
    uno_bridge = FakeUnoBridge(active_document=active_document, slide_names=slide_names)
    document_registry = DocumentRegistry(uno_bridge)
    runtime_state = RuntimeState()
    context.install(context.RuntimeContext(
        uno_bridge=uno_bridge, document_registry=document_registry,
        runtime_state=runtime_state, get_tools=lambda: {},
    ))
    return uno_bridge, document_registry, runtime_state


def _handler(name):
    return get_registry()[name]["handler"]


# -- slide CRUD --

def test_list_slides_live():
    context.reset()
    _install(active_document=FakeDocument(), slide_names=["Slide 1", "Slide 2"])
    result = _handler("list_slides_live")()
    assert result["success"] is True
    assert result["result"]["count"] == 2


def test_get_active_slide_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("get_active_slide_live")()
    assert result["success"] is True
    assert result["result"]["name"] == "Slide 1"


def test_activate_slide_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument(), slide_names=["Slide 1", "Slide 2"])
    result = _handler("activate_slide_live")(slide="Slide 2")
    assert result["success"] is True
    assert uno_bridge.active_slide_name == "Slide 2"


def test_insert_slide_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("insert_slide_live")(layout="title_slide")
    assert result["success"] is True
    assert len(uno_bridge.slides) == 2


def test_duplicate_slide_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("duplicate_slide_live")(slide="Slide 1")
    assert result["success"] is True
    assert any(s["name"] == "Slide 1 Copy" for s in uno_bridge.slides)


def test_delete_slide_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument(), slide_names=["Slide 1", "Slide 2"])
    result = _handler("delete_slide_live")(slide="Slide 2")
    assert result["success"] is True
    assert not any(s["name"] == "Slide 2" for s in uno_bridge.slides)


def test_move_slide_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument(), slide_names=["Slide 1", "Slide 2", "Slide 3"])
    result = _handler("move_slide_live")(slide="Slide 3", destination_index=0)
    assert result["success"] is True
    assert uno_bridge.slides[0]["name"] == "Slide 3"


def test_move_slide_live_out_of_range():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("move_slide_live")(slide="Slide 1", destination_index=99)
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_RANGE"


def test_rename_slide_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("rename_slide_live")(slide="Slide 1", name="Intro")
    assert result["success"] is True
    assert uno_bridge.slides[0]["name"] == "Intro"


def test_hide_and_show_slide_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    hidden = _handler("hide_slide_live")(slide="Slide 1")
    assert hidden["success"] is True
    assert uno_bridge.slides[0]["hidden"] is True
    shown = _handler("show_slide_live")(slide="Slide 1")
    assert shown["success"] is True
    assert uno_bridge.slides[0]["hidden"] is False


# -- layout/size/background --

def test_get_slide_layout_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("get_slide_layout_live")(slide="Slide 1")
    assert result["success"] is True
    assert result["result"]["layout"] == 0


def test_set_slide_layout_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("set_slide_layout_live")(slide="Slide 1", layout="blank")
    assert result["success"] is True
    assert uno_bridge.slides[0]["layout"] == "blank"


def test_set_slide_size_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("set_slide_size_live")(width=254, height=190.5, unit="mm")
    assert result["success"] is True
    assert uno_bridge.slide_size == (254, 190.5, "mm")


def test_set_slide_background_live_skips_unknown_properties():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("set_slide_background_live")(slide="Slide 1", properties={"FillColor": 255, "InvalidProperty": 1})
    assert result["success"] is True
    assert result["result"]["applied"] == ["FillColor"]
    assert "InvalidProperty" in result["warnings"][0]


# -- master pages --

def test_list_master_pages_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("list_master_pages_live")()
    assert result["success"] is True
    assert result["result"]["count"] == 1


def test_apply_master_page_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    uno_bridge.masters.append({"name": "MyMaster"})
    result = _handler("apply_master_page_live")(master="MyMaster", slides=["Slide 1"])
    assert result["success"] is True
    assert uno_bridge.slides[0]["master"] == "MyMaster"


def test_create_and_delete_master_page_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    created = _handler("create_master_page_live")(name="NewMaster")
    assert created["success"] is True
    assert any(m["name"] == "NewMaster" for m in uno_bridge.masters)
    deleted = _handler("delete_master_page_live")(master="NewMaster")
    assert deleted["success"] is True
    assert not any(m["name"] == "NewMaster" for m in uno_bridge.masters)


def test_create_master_page_live_based_on_warns():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("create_master_page_live")(name="NewMaster", based_on="Default")
    assert result["success"] is True
    assert "based_on" in result["warnings"][0]


# -- notes --

def test_get_and_set_speaker_notes_live():
    context.reset()
    _install(active_document=FakeDocument())
    set_result = _handler("set_speaker_notes_live")(slide="Slide 1", text="Remember to smile")
    assert set_result["success"] is True
    get_result = _handler("get_speaker_notes_live")(slide="Slide 1")
    assert get_result["success"] is True
    assert get_result["result"]["text"] == "Remember to smile"


# -- transitions --

def test_get_and_set_slide_transition_live():
    context.reset()
    _install(active_document=FakeDocument())
    set_result = _handler("set_slide_transition_live")(slide="Slide 1", effect=5, duration=1.5, advance="auto", auto_after=3.0)
    assert set_result["success"] is True
    assert set(set_result["result"]["applied"]) == {"effect", "duration", "advance", "auto_after"}
    get_result = _handler("get_slide_transition_live")(slide="Slide 1")
    assert get_result["success"] is True
    assert get_result["result"]["transition_type"] == 5


# -- animations --

def test_list_animations_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("list_animations_live")(slide="Slide 1")
    assert result["success"] is True
    assert result["result"]["count"] == 0


def test_add_animation_live_not_implemented():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("add_animation_live")(shape_id="whatever", effect="fade")
    assert result["success"] is False
    assert result["error"]["code"] == "NOT_IMPLEMENTED"


# -- click action --

def test_set_shape_click_action_live():
    context.reset()
    uno_bridge, document_registry, _ = _install(active_document=FakeDocument())
    doc = uno_bridge.active_document
    document_id = document_registry.register_document(doc)
    shape = FakeShape()
    shape_id = document_registry.get_object_registry(document_id).register_object(shape)
    result = _handler("set_shape_click_action_live")(shape_id=shape_id, action="next_page")
    assert result["success"] is True
    assert shape.on_click == "next_page"


# -- presentation settings --

def test_get_and_set_presentation_settings_live():
    context.reset()
    _install(active_document=FakeDocument())
    get_result = _handler("get_presentation_settings_live")()
    assert get_result["success"] is True
    assert get_result["result"]["IsFullScreen"] is True
    set_result = _handler("set_presentation_settings_live")(settings={"IsFullScreen": False, "InvalidSetting": 1})
    assert set_result["success"] is True
    assert set_result["result"]["applied"] == ["IsFullScreen"]
    assert "InvalidSetting" in set_result["warnings"][0]


# -- custom shows --

def test_custom_show_lifecycle_live():
    context.reset()
    _install(active_document=FakeDocument(), slide_names=["Slide 1", "Slide 2"])
    created = _handler("create_custom_show_live")(name="MyShow", slides=["Slide 1"])
    assert created["success"] is True
    listed = _handler("list_custom_shows_live")()
    assert listed["result"]["count"] == 1
    updated = _handler("update_custom_show_live")(name="MyShow", slides=["Slide 1", "Slide 2"])
    assert updated["success"] is True
    assert updated["result"]["count"] == 2
    deleted = _handler("delete_custom_show_live")(name="MyShow")
    assert deleted["success"] is True
    assert _handler("list_custom_shows_live")()["result"]["count"] == 0


def test_delete_custom_show_live_not_found():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("delete_custom_show_live")(name="NoSuchShow")
    assert result["success"] is False
    assert result["error"]["code"] == "OBJECT_NOT_FOUND"


# -- slideshow --

def test_start_and_stop_slideshow_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    started = _handler("start_slideshow_live")()
    assert started["success"] is True
    assert uno_bridge.slideshow_started is True
    stopped = _handler("stop_slideshow_live")()
    assert stopped["success"] is True
    assert uno_bridge.slideshow_started is False


def test_next_slideshow_effect_live_not_implemented():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("next_slideshow_effect_live")()
    assert result["success"] is False
    assert result["error"]["code"] == "NOT_IMPLEMENTED"


# -- export --

def test_export_slide_image_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("export_slide_image_live")(slide="Slide 1", file_path="/tmp/slide1.png", format="png")
    assert result["success"] is True
    assert uno_bridge.exported == [("Slide 1", "/tmp/slide1.png", "png")]


def test_export_slide_image_live_unsupported_format():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("export_slide_image_live")(slide="Slide 1", file_path="/tmp/slide1.pdf", format="pdf")
    assert result["success"] is False
    assert result["error"]["code"] == "UNSUPPORTED_CAPABILITY"


def test_export_all_slides_images_live():
    context.reset()
    _install(active_document=FakeDocument(), slide_names=["Slide 1", "Slide 2"])
    result = _handler("export_all_slides_images_live")(output_dir="/tmp/out")
    assert result["success"] is True
    assert result["result"]["count"] == 2


if __name__ == "__main__":
    tests = [
        test_list_slides_live,
        test_get_active_slide_live,
        test_activate_slide_live,
        test_insert_slide_live,
        test_duplicate_slide_live,
        test_delete_slide_live,
        test_move_slide_live,
        test_move_slide_live_out_of_range,
        test_rename_slide_live,
        test_hide_and_show_slide_live,
        test_get_slide_layout_live,
        test_set_slide_layout_live,
        test_set_slide_size_live,
        test_set_slide_background_live_skips_unknown_properties,
        test_list_master_pages_live,
        test_apply_master_page_live,
        test_create_and_delete_master_page_live,
        test_create_master_page_live_based_on_warns,
        test_get_and_set_speaker_notes_live,
        test_get_and_set_slide_transition_live,
        test_list_animations_live,
        test_add_animation_live_not_implemented,
        test_set_shape_click_action_live,
        test_get_and_set_presentation_settings_live,
        test_custom_show_lifecycle_live,
        test_delete_custom_show_live_not_found,
        test_start_and_stop_slideshow_live,
        test_next_slideshow_effect_live_not_implemented,
        test_export_slide_image_live,
        test_export_slide_image_live_unsupported_format,
        test_export_all_slides_images_live,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} impress tests passed.")
