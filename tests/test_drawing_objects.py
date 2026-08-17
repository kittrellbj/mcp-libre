#!/usr/bin/env python3
"""
Unit tests for the 25 real (status="implemented") drawing_objects.py tools.

Uses a FakeUnoBridge modeling shapes as plain FakeShape objects in a
single flat list (good enough to exercise the tool-layer logic --
parameter plumbing, shape_id<->ObjectRegistry round-tripping, error-code
mapping, warnings for skipped properties -- without needing to model
real UNO XDrawPage/XShape/XShapeGrouper/XGluePointsSupplier objects).
DocumentRegistry and its per-document ObjectRegistry (from
docs/OBJECT_HANDLE_DESIGN.md) are the REAL implementations, not faked --
the shape_id minting/resolution/eviction behavior under test is real.

What this file deliberately does NOT (and structurally cannot) verify --
same disclaimer as test_writer_text.py/test_styles.py: real UNO geometry
math (Position/Size struct construction), real ZOrder clamping, real
XShapeGrouper.group()/ungroup(), real GluePoint2 struct construction, and
real GraphicProvider-based image loading are all live-verified instead
(see docs/MCP_TOOLING_SCAFFOLD_PLAN.md's drawing_objects.py pass), not
something a fake can usefully assert.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugin", "pythonpath"))

from tools import context  # noqa: E402
from tools.documents import DocumentRegistry  # noqa: E402
from tools.object_registry import ObjectNotFoundError  # noqa: E402
from tools.registry import get_registry  # noqa: E402
from tools.runtime_state import RuntimeState  # noqa: E402


class FakeDocument:
    def __init__(self, doc_type="writer", title="Untitled", url=""):
        self.doc_type = doc_type
        self.title = title
        self.url = url
        self.modified = False


class FakeShape:
    def __init__(self, shape_type="rectangle", x=0, y=0, width=1000, height=1000):
        self.shape_type = shape_type
        self.x, self.y, self.width, self.height = x, y, width, height
        self.rotation = 0
        self.text = ""
        self.title = None
        self.description = None
        self.z_order = 0
        self.style = {}
        self.glue_points = []  # list of {"x", "y", "is_user_defined"}
        self.deleted = False


class FakeSelection:
    """Stand-in for the multi-shape selection UNOBridge.split_shape()/
    unbind_shape() return (real UNO returns the controller's current
    XSelectionSupplier-shaped selection, which exposes getCount()/
    getByIndex())."""

    def __init__(self, shapes):
        self._shapes = shapes

    def getCount(self):
        return len(self._shapes)

    def getByIndex(self, i):
        return self._shapes[i]


class FakeUnoBridge:
    """Stand-in for uno_bridge.UNOBridge's drawing_objects.py-facing methods."""

    def __init__(self, active_document=None, shapes=None):
        self.ctx = object()
        self.active_document = active_document
        self.shapes = list(shapes) if shapes is not None else []

    def get_active_document(self):
        return self.active_document

    def get_document_info(self, doc):
        return {"type": doc.doc_type, "title": doc.title, "url": doc.url, "modified": doc.modified}

    # -- shape CRUD --

    def list_shapes_in_container(self, doc, container=None, type_filter=None):
        return [s for s in self.shapes if type_filter is None or s.shape_type == type_filter]

    @staticmethod
    def get_shape_summary(shape, shape_id):
        return {"shape_id": shape_id, "type": shape.shape_type, "x": shape.x, "y": shape.y,
                "width": shape.width, "height": shape.height}

    @staticmethod
    def get_shape_details(shape, shape_id):
        return {"shape_id": shape_id, "type": shape.shape_type, "x": shape.x, "y": shape.y,
                "width": shape.width, "height": shape.height, "z_order": shape.z_order,
                "text": shape.text, "style": dict(shape.style)}

    def insert_shape(self, doc, shape_type, position, size, container=None, properties=None):
        shape = FakeShape(shape_type, position.get("x", 0), position.get("y", 0),
                           size.get("width", 1000), size.get("height", 1000))
        if properties:
            for k, v in properties.items():
                shape.style[k] = v
        self.shapes.append(shape)
        return shape

    def delete_shape(self, doc, shape):
        shape.deleted = True
        self.shapes.remove(shape)

    def duplicate_shape(self, doc, shape, offset=None):
        new_shape = FakeShape(shape.shape_type, shape.x, shape.y, shape.width, shape.height)
        new_shape.style = dict(shape.style)
        if offset:
            new_shape.x += offset.get("x", 0)
            new_shape.y += offset.get("y", 0)
        self.shapes.append(new_shape)
        return new_shape

    def set_shape_geometry(self, shape, geometry):
        applied = []
        for key in ("x", "y", "width", "height", "rotation"):
            if key in geometry:
                setattr(shape, key, geometry[key])
                applied.append(key)
        return applied

    def set_shape_style(self, shape, properties):
        applied = []
        for k, v in properties.items():
            if k == "InvalidProperty":
                continue
            shape.style[k] = v
            applied.append(k)
        return applied

    def set_shape_text(self, shape, text):
        shape.text = text

    def format_shape_text(self, shape, properties, range=None):
        applied = []
        for k, v in properties.items():
            if k == "InvalidProperty":
                continue
            applied.append(k)
        return applied

    def set_shape_alt_text(self, shape, title=None, description=None):
        applied = []
        if title is not None:
            shape.title = title
            applied.append("title")
        if description is not None:
            shape.description = description
            applied.append("description")
        return applied

    def set_shape_z_order(self, shape, action=None, z_order=None):
        max_order = len(self.shapes) - 1
        if z_order is not None:
            shape.z_order = max(0, min(z_order, max_order))
        elif action == "front":
            shape.z_order = max_order
        elif action == "back":
            shape.z_order = 0
        elif action == "forward":
            shape.z_order = min(shape.z_order + 1, max_order)
        elif action == "backward":
            shape.z_order = max(shape.z_order - 1, 0)
        else:
            raise ValueError("Either action or z_order must be given.")
        return shape.z_order

    @staticmethod
    def _shape_bounds(shape):
        return {"left": shape.x, "top": shape.y, "right": shape.x + shape.width, "bottom": shape.y + shape.height,
                "center_x": shape.x + shape.width // 2, "center_y": shape.y + shape.height // 2}

    def align_shapes(self, shapes, alignment, reference_bounds=None):
        if not shapes:
            return
        all_bounds = [self._shape_bounds(s) for s in shapes]
        bounds = reference_bounds or {
            "left": min(b["left"] for b in all_bounds), "top": min(b["top"] for b in all_bounds),
            "right": max(b["right"] for b in all_bounds), "bottom": max(b["bottom"] for b in all_bounds),
        }
        bounds.setdefault("center_x", (bounds["left"] + bounds["right"]) // 2)
        bounds.setdefault("center_y", (bounds["top"] + bounds["bottom"]) // 2)
        for shape in shapes:
            if alignment == "left":
                shape.x = bounds["left"]
            elif alignment == "right":
                shape.x = bounds["right"] - shape.width
            elif alignment == "center":
                shape.x = bounds["center_x"] - shape.width // 2
            elif alignment == "top":
                shape.y = bounds["top"]
            elif alignment == "bottom":
                shape.y = bounds["bottom"] - shape.height
            elif alignment == "middle":
                shape.y = bounds["center_y"] - shape.height // 2
            else:
                raise ValueError(f"Unknown alignment '{alignment}'.")

    def distribute_shapes(self, shapes, direction, mode=None):
        if len(shapes) < 3:
            return
        axis_attr = "x" if direction == "horizontal" else "y"
        ordered = sorted(shapes, key=lambda s: getattr(s, axis_attr))
        first, last = getattr(ordered[0], axis_attr), getattr(ordered[-1], axis_attr)
        step = (last - first) / (len(ordered) - 1)
        for i, shape in enumerate(ordered[1:-1], start=1):
            setattr(shape, axis_attr, first + step * i)

    def group_shapes(self, shapes):
        if len(shapes) < 2:
            raise ValueError("group_shapes needs at least 2 shapes.")
        group = FakeShape("group")
        for s in shapes:
            self.shapes.remove(s)
        self.shapes.append(group)
        return group

    def ungroup_shape(self, shape):
        self.shapes.remove(shape)

    def combine_shapes(self, doc, shapes):
        if len(shapes) < 2:
            raise ValueError("combine_shapes needs at least 2 shapes.")
        combined = FakeShape("combined")
        for s in shapes:
            self.shapes.remove(s)
        self.shapes.append(combined)
        return combined

    def split_shape(self, doc, shape):
        self.shapes.remove(shape)
        parts = [FakeShape("rectangle"), FakeShape("rectangle")]
        self.shapes.extend(parts)
        return FakeSelection(parts)

    def bind_shapes(self, doc, shapes):
        if len(shapes) < 2:
            raise ValueError("bind_shapes needs at least 2 shapes.")
        bound = FakeShape("bound")
        for s in shapes:
            self.shapes.remove(s)
        self.shapes.append(bound)
        return bound

    def unbind_shape(self, doc, shape):
        self.shapes.remove(shape)
        parts = [FakeShape("rectangle"), FakeShape("ellipse")]
        self.shapes.extend(parts)
        return FakeSelection(parts)

    def insert_connector(self, doc, from_shape, to_shape, from_glue=None, to_glue=None, connector_type=None):
        connector = FakeShape("connector")
        self.shapes.append(connector)
        return connector

    def list_glue_points(self, shape):
        return [{"glue_point_id": str(i), "x": gp["x"], "y": gp["y"], "is_user_defined": gp["is_user_defined"]}
                for i, gp in enumerate(shape.glue_points)]

    def add_glue_point(self, shape, position, direction=None):
        shape.glue_points.append({"x": position.get("x", 0), "y": position.get("y", 0), "is_user_defined": True})
        return str(len(shape.glue_points) - 1)

    def delete_glue_point(self, shape, glue_point_id):
        del shape.glue_points[int(glue_point_id)]

    def insert_image(self, doc, file_path, container=None, position=None, size=None, anchor=None, wrap=None):
        shape = FakeShape("image", (position or {}).get("x", 0), (position or {}).get("y", 0),
                           (size or {}).get("width", 100), (size or {}).get("height", 100))
        shape.style["file_path"] = file_path
        self.shapes.append(shape)
        return shape

    def replace_image(self, shape, file_path):
        if shape.shape_type != "image":
            raise NotImplementedError("This shape is not an image.")
        shape.style["file_path"] = file_path

    def set_image_properties(self, shape, properties):
        if shape.shape_type != "image":
            raise NotImplementedError("This shape is not an image.")
        applied = []
        for k, v in properties.items():
            if k == "InvalidProperty":
                continue
            shape.style[k] = v
            applied.append(k)
        return applied

    def export_shape(self, shape, file_path, format=None, dpi=None):
        pass

    def list_embedded_objects(self, doc, container=None):
        return [s for s in self.shapes if s.shape_type == "ole"]

    def delete_embedded_object(self, doc, shape):
        self.delete_shape(doc, shape)


def _install(active_document=None, shapes=None):
    uno_bridge = FakeUnoBridge(active_document=active_document, shapes=shapes)
    document_registry = DocumentRegistry(uno_bridge)
    runtime_state = RuntimeState()
    context.install(context.RuntimeContext(
        uno_bridge=uno_bridge, document_registry=document_registry,
        runtime_state=runtime_state, get_tools=lambda: {},
    ))
    return uno_bridge, document_registry, runtime_state


def _handler(name):
    return get_registry()[name]["handler"]


# -- list_shapes_live / get_shape_live --

def test_list_shapes_live_registers_and_returns_ids():
    context.reset()
    _install(active_document=FakeDocument(), shapes=[FakeShape("rectangle"), FakeShape("ellipse")])
    result = _handler("list_shapes_live")()
    assert result["success"] is True
    assert result["result"]["count"] == 2
    ids = [s["shape_id"] for s in result["result"]["shapes"]]
    assert len(set(ids)) == 2  # distinct ids minted


def test_list_shapes_live_type_filter():
    context.reset()
    _install(active_document=FakeDocument(), shapes=[FakeShape("rectangle"), FakeShape("ellipse")])
    result = _handler("list_shapes_live")(type_filter="ellipse")
    assert result["result"]["count"] == 1
    assert result["result"]["shapes"][0]["type"] == "ellipse"


def test_get_shape_live_round_trips_through_registry():
    context.reset()
    _install(active_document=FakeDocument(), shapes=[FakeShape("rectangle", x=10, y=20)])
    listed = _handler("list_shapes_live")()
    shape_id = listed["result"]["shapes"][0]["shape_id"]
    result = _handler("get_shape_live")(shape_id=shape_id)
    assert result["success"] is True
    assert result["result"]["x"] == 10 and result["result"]["y"] == 20


def test_get_shape_live_unknown_id_is_object_not_found():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("get_shape_live")(shape_id="not-a-real-id")
    assert result["success"] is False
    assert result["error"]["code"] == "OBJECT_NOT_FOUND"


# -- insert_shape_live / delete_shape_live / duplicate_shape_live --

def test_insert_shape_live_creates_and_registers():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("insert_shape_live")(shape_type="rectangle", position={"x": 5, "y": 5}, size={"width": 200, "height": 100})
    assert result["success"] is True
    assert len(uno_bridge.shapes) == 1
    assert result["result"]["shape_id"]


def test_delete_shape_live_removes_and_unregisters():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument(), shapes=[FakeShape("rectangle")])
    shape_id = _handler("list_shapes_live")()["result"]["shapes"][0]["shape_id"]
    result = _handler("delete_shape_live")(shape_id=shape_id)
    assert result["success"] is True
    assert len(uno_bridge.shapes) == 0
    # Deleted id no longer resolves.
    follow_up = _handler("get_shape_live")(shape_id=shape_id)
    assert follow_up["error"]["code"] == "OBJECT_NOT_FOUND"


def test_duplicate_shape_live_creates_a_second_shape():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument(), shapes=[FakeShape("rectangle", x=0, y=0)])
    shape_id = _handler("list_shapes_live")()["result"]["shapes"][0]["shape_id"]
    result = _handler("duplicate_shape_live")(shape_id=shape_id, offset={"x": 50, "y": 50})
    assert result["success"] is True
    assert len(uno_bridge.shapes) == 2
    assert result["result"]["x"] == 50 and result["result"]["y"] == 50
    assert result["result"]["shape_id"] != shape_id


# -- set_shape_geometry_live / set_shape_style_live --

def test_set_shape_geometry_live_applies_and_warns_on_unknown():
    context.reset()
    _install(active_document=FakeDocument(), shapes=[FakeShape("rectangle")])
    shape_id = _handler("list_shapes_live")()["result"]["shapes"][0]["shape_id"]
    result = _handler("set_shape_geometry_live")(shape_id=shape_id, geometry={"x": 99, "not_a_field": 1})
    assert result["success"] is True
    assert "x" in result["result"]["applied"]
    assert result["warnings"]


def test_set_shape_style_live_skips_unknown_properties():
    context.reset()
    _install(active_document=FakeDocument(), shapes=[FakeShape("rectangle")])
    shape_id = _handler("list_shapes_live")()["result"]["shapes"][0]["shape_id"]
    result = _handler("set_shape_style_live")(shape_id=shape_id, properties={"FillColor": 255, "InvalidProperty": 1})
    assert result["success"] is True
    assert result["result"]["applied"] == ["FillColor"]
    assert "InvalidProperty" in result["warnings"][0]


# -- set_shape_text_live / format_shape_text_live / set_shape_alt_text_live --

def test_set_shape_text_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument(), shapes=[FakeShape("text")])
    shape_id = _handler("list_shapes_live")()["result"]["shapes"][0]["shape_id"]
    result = _handler("set_shape_text_live")(shape_id=shape_id, text="Hello shape")
    assert result["success"] is True
    assert uno_bridge.shapes[0].text == "Hello shape"


def test_set_shape_alt_text_live():
    context.reset()
    _install(active_document=FakeDocument(), shapes=[FakeShape("rectangle")])
    shape_id = _handler("list_shapes_live")()["result"]["shapes"][0]["shape_id"]
    result = _handler("set_shape_alt_text_live")(shape_id=shape_id, title="A title", description="A description")
    assert result["success"] is True
    assert set(result["result"]["applied"]) == {"title", "description"}


# -- set_shape_z_order_live --

def test_set_shape_z_order_live_explicit():
    context.reset()
    _install(active_document=FakeDocument(), shapes=[FakeShape("rectangle"), FakeShape("ellipse")])
    shapes = _handler("list_shapes_live")()["result"]["shapes"]
    result = _handler("set_shape_z_order_live")(shape_id=shapes[0]["shape_id"], z_order=1)
    assert result["success"] is True
    assert result["result"]["z_order"] == 1


def test_set_shape_z_order_live_requires_action_or_z_order():
    context.reset()
    _install(active_document=FakeDocument(), shapes=[FakeShape("rectangle")])
    shape_id = _handler("list_shapes_live")()["result"]["shapes"][0]["shape_id"]
    result = _handler("set_shape_z_order_live")(shape_id=shape_id)
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_PARAMETER"


# -- align_shapes_live / distribute_shapes_live --

def test_align_shapes_live_left():
    context.reset()
    _install(active_document=FakeDocument(), shapes=[
        FakeShape("rectangle", x=10, width=100), FakeShape("rectangle", x=50, width=100),
    ])
    uno_bridge = context.get_context().uno_bridge
    ids = [s["shape_id"] for s in _handler("list_shapes_live")()["result"]["shapes"]]
    result = _handler("align_shapes_live")(shape_ids=ids, alignment="left")
    assert result["success"] is True
    assert uno_bridge.shapes[0].x == uno_bridge.shapes[1].x == 10


def test_align_shapes_live_with_reference():
    context.reset()
    _install(active_document=FakeDocument(), shapes=[
        FakeShape("rectangle", x=10, width=100), FakeShape("rectangle", x=999, width=100),
    ])
    uno_bridge = context.get_context().uno_bridge
    listed = _handler("list_shapes_live")()["result"]["shapes"]
    ref_id, other_id = listed[0]["shape_id"], listed[1]["shape_id"]
    result = _handler("align_shapes_live")(shape_ids=[other_id], alignment="left", reference=ref_id)
    assert result["success"] is True
    assert uno_bridge.shapes[1].x == 10  # aligned to reference shape's left, not the pair's own bounds


def test_distribute_shapes_live_needs_three_shapes_to_do_anything():
    context.reset()
    _install(active_document=FakeDocument(), shapes=[
        FakeShape("rectangle", x=0), FakeShape("rectangle", x=100), FakeShape("rectangle", x=300),
    ])
    uno_bridge = context.get_context().uno_bridge
    ids = [s["shape_id"] for s in _handler("list_shapes_live")()["result"]["shapes"]]
    result = _handler("distribute_shapes_live")(shape_ids=ids, direction="horizontal")
    assert result["success"] is True
    middle = sorted(uno_bridge.shapes, key=lambda s: s.x)[1]
    assert middle.x == 150  # evenly between 0 and 300


# -- group_shapes_live / ungroup_shape_live --

def test_group_shapes_live_creates_a_group_and_leaves_member_ids_resolvable():
    """Live-verified against real UNO (not just this fake): grouping does
    NOT dispose the member shapes -- page.group() reparents them into the
    new group, but the original PyUNO proxy stays fully valid and
    UNO-equal to the group's own child references, so a member's
    shape_id deliberately keeps resolving through ObjectRegistry after
    grouping (unlike ungroup_shape_live's group_id, which does go stale
    -- see test_ungroup_shape_live_unregisters_the_group)."""
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument(), shapes=[FakeShape("rectangle"), FakeShape("ellipse")])
    ids = [s["shape_id"] for s in _handler("list_shapes_live")()["result"]["shapes"]]
    result = _handler("group_shapes_live")(shape_ids=ids)
    assert result["success"] is True
    assert result["result"]["type"] == "group"
    # Listing the container now shows just the one group, matching real
    # UNO's page.getCount() dropping from 2 to 1 after grouping.
    assert len(uno_bridge.shapes) == 1
    assert uno_bridge.shapes[0].shape_type == "group"
    # The original member shape_ids still resolve.
    for member_id in ids:
        member_result = _handler("get_shape_live")(shape_id=member_id)
        assert member_result["success"] is True


def test_ungroup_shape_live_unregisters_the_group():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument(), shapes=[FakeShape("rectangle"), FakeShape("ellipse")])
    ids = [s["shape_id"] for s in _handler("list_shapes_live")()["result"]["shapes"]]
    group_id = _handler("group_shapes_live")(shape_ids=ids)["result"]["shape_id"]
    result = _handler("ungroup_shape_live")(shape_id=group_id)
    assert result["success"] is True
    assert _handler("get_shape_live")(shape_id=group_id)["error"]["code"] == "OBJECT_NOT_FOUND"


# -- combine/split/bind/unbind: still status="stub" (see module docstring) --

def test_combine_shapes_live_unregisters_members_and_registers_result():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument(), shapes=[FakeShape("rectangle"), FakeShape("ellipse")])
    ids = [s["shape_id"] for s in _handler("list_shapes_live")()["result"]["shapes"]]
    result = _handler("combine_shapes_live")(shape_ids=ids)
    assert result["success"] is True
    assert result["result"]["type"] == "combined"
    assert len(uno_bridge.shapes) == 1
    for member_id in ids:
        assert _handler("get_shape_live")(shape_id=member_id)["error"]["code"] == "OBJECT_NOT_FOUND"


def test_combine_shapes_live_needs_at_least_two():
    context.reset()
    _install(active_document=FakeDocument(), shapes=[FakeShape("rectangle")])
    shape_id = _handler("list_shapes_live")()["result"]["shapes"][0]["shape_id"]
    result = _handler("combine_shapes_live")(shape_ids=[shape_id])
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_PARAMETER"


def test_split_shape_live_unregisters_source_and_registers_parts():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument(), shapes=[FakeShape("combined")])
    shape_id = _handler("list_shapes_live")()["result"]["shapes"][0]["shape_id"]
    result = _handler("split_shape_live")(shape_id=shape_id)
    assert result["success"] is True
    assert result["result"]["count"] == 2
    assert len(uno_bridge.shapes) == 2
    assert _handler("get_shape_live")(shape_id=shape_id)["error"]["code"] == "OBJECT_NOT_FOUND"
    for new_id in result["result"]["shape_ids"]:
        assert _handler("get_shape_live")(shape_id=new_id)["success"] is True


def test_bind_shapes_live_unregisters_members_and_registers_result():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument(), shapes=[FakeShape("rectangle"), FakeShape("ellipse")])
    ids = [s["shape_id"] for s in _handler("list_shapes_live")()["result"]["shapes"]]
    result = _handler("bind_shapes_live")(shape_ids=ids)
    assert result["success"] is True
    assert result["result"]["type"] == "bound"
    for member_id in ids:
        assert _handler("get_shape_live")(shape_id=member_id)["error"]["code"] == "OBJECT_NOT_FOUND"


def test_unbind_shape_live_unregisters_source_and_registers_parts():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument(), shapes=[FakeShape("bound")])
    shape_id = _handler("list_shapes_live")()["result"]["shapes"][0]["shape_id"]
    result = _handler("unbind_shape_live")(shape_id=shape_id)
    assert result["success"] is True
    assert result["result"]["count"] == 2
    assert _handler("get_shape_live")(shape_id=shape_id)["error"]["code"] == "OBJECT_NOT_FOUND"


# -- insert_connector_live / glue points --

def test_insert_connector_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument(), shapes=[FakeShape("rectangle"), FakeShape("ellipse")])
    ids = [s["shape_id"] for s in _handler("list_shapes_live")()["result"]["shapes"]]
    result = _handler("insert_connector_live")(from_shape=ids[0], to_shape=ids[1])
    assert result["success"] is True
    assert len(uno_bridge.shapes) == 3  # 2 originals + connector


def test_glue_point_lifecycle():
    context.reset()
    _install(active_document=FakeDocument(), shapes=[FakeShape("rectangle")])
    shape_id = _handler("list_shapes_live")()["result"]["shapes"][0]["shape_id"]
    added = _handler("add_glue_point_live")(shape_id=shape_id, position={"x": 5, "y": 5})
    assert added["success"] is True
    glue_point_id = added["result"]["glue_point_id"]
    listed = _handler("list_glue_points_live")(shape_id=shape_id)
    assert listed["result"]["count"] == 1
    deleted = _handler("delete_glue_point_live")(shape_id=shape_id, glue_point_id=glue_point_id)
    assert deleted["success"] is True
    listed_again = _handler("list_glue_points_live")(shape_id=shape_id)
    assert listed_again["result"]["count"] == 0


# -- images --

def test_insert_image_live_and_replace_and_set_properties():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    inserted = _handler("insert_image_live")(file_path="/tmp/a.png")
    assert inserted["success"] is True
    shape_id = inserted["result"]["shape_id"]
    replaced = _handler("replace_image_live")(shape_id=shape_id, file_path="/tmp/b.png")
    assert replaced["success"] is True
    assert uno_bridge.shapes[0].style["file_path"] == "/tmp/b.png"
    props = _handler("set_image_properties_live")(shape_id=shape_id, properties={"Transparency": 50})
    assert props["success"] is True
    assert props["result"]["applied"] == ["Transparency"]


def test_replace_image_live_on_non_image_shape_is_unsupported():
    context.reset()
    _install(active_document=FakeDocument(), shapes=[FakeShape("rectangle")])
    shape_id = _handler("list_shapes_live")()["result"]["shapes"][0]["shape_id"]
    result = _handler("replace_image_live")(shape_id=shape_id, file_path="/tmp/a.png")
    assert result["success"] is False
    assert result["error"]["code"] == "UNSUPPORTED_CAPABILITY"


def test_export_shape_live():
    context.reset()
    _install(active_document=FakeDocument(), shapes=[FakeShape("rectangle")])
    shape_id = _handler("list_shapes_live")()["result"]["shapes"][0]["shape_id"]
    result = _handler("export_shape_live")(shape_id=shape_id, file_path="/tmp/out.png", format="png", dpi=300)
    assert result["success"] is True


# -- embedded objects --

def test_list_and_delete_embedded_objects_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument(), shapes=[FakeShape("ole"), FakeShape("rectangle")])
    listed = _handler("list_embedded_objects_live")()
    assert listed["result"]["count"] == 1
    object_id = listed["result"]["objects"][0]["shape_id"]
    deleted = _handler("delete_embedded_object_live")(object_id=object_id)
    assert deleted["success"] is True
    assert len(uno_bridge.shapes) == 1


def test_insert_and_activate_embedded_object_are_still_not_implemented():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("insert_embedded_object_live")(object_type="chart")
    assert result["success"] is False and result["error"]["code"] == "NOT_IMPLEMENTED"
    result2 = _handler("activate_embedded_object_live")(object_id="a")
    assert result2["success"] is False and result2["error"]["code"] == "NOT_IMPLEMENTED"


if __name__ == "__main__":
    tests = [
        test_list_shapes_live_registers_and_returns_ids,
        test_list_shapes_live_type_filter,
        test_get_shape_live_round_trips_through_registry,
        test_get_shape_live_unknown_id_is_object_not_found,
        test_insert_shape_live_creates_and_registers,
        test_delete_shape_live_removes_and_unregisters,
        test_duplicate_shape_live_creates_a_second_shape,
        test_set_shape_geometry_live_applies_and_warns_on_unknown,
        test_set_shape_style_live_skips_unknown_properties,
        test_set_shape_text_live,
        test_set_shape_alt_text_live,
        test_set_shape_z_order_live_explicit,
        test_set_shape_z_order_live_requires_action_or_z_order,
        test_align_shapes_live_left,
        test_align_shapes_live_with_reference,
        test_distribute_shapes_live_needs_three_shapes_to_do_anything,
        test_group_shapes_live_creates_a_group_and_leaves_member_ids_resolvable,
        test_ungroup_shape_live_unregisters_the_group,
        test_combine_shapes_live_unregisters_members_and_registers_result,
        test_combine_shapes_live_needs_at_least_two,
        test_split_shape_live_unregisters_source_and_registers_parts,
        test_bind_shapes_live_unregisters_members_and_registers_result,
        test_unbind_shape_live_unregisters_source_and_registers_parts,
        test_insert_connector_live,
        test_glue_point_lifecycle,
        test_insert_image_live_and_replace_and_set_properties,
        test_replace_image_live_on_non_image_shape_is_unsupported,
        test_export_shape_live,
        test_list_and_delete_embedded_objects_live,
        test_insert_and_activate_embedded_object_are_still_not_implemented,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} drawing_objects tests passed.")
