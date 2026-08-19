#!/usr/bin/env python3
"""
Unit tests for the 20 real (status="implemented") charts.py tools.

Uses a FakeUnoBridge modeling charts as a dict keyed by chart_id (mirroring
the real UNOBridge's chart2 methods' public signatures) -- enough for
tool-layer plumbing (argument passing, applied/skipped property reporting,
error-code mapping), not real chart2 mechanics (XChartType/XDataSeries/
XCoordinateSystem/XAxis hierarchy, the smgr-vs-doc.createInstance creation-
context split, the chart2 Title/FormattedString object requirement). Those
are live-verified instead -- see docs/MCP_TOOLING_SCAFFOLD_PLAN.md's
charts.py pass.
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


def _new_chart(sheet="Sheet1", ranges=None, chart_type="bar"):
    return {
        "sheet": sheet,
        "ranges": ranges or ["A1:B3"],
        "chart_type": chart_type,
        "title": None,
        "has_legend": False,
        "legend_position": None,
        "series": [{"series_id": "0", "color": 0}, {"series_id": "1", "color": 1}],
        "axes": {},
        "gridlines": {},
        "trendlines": {},
        "error_bars": {},
        "position": {"x": 0, "y": 0},
        "size": {"width": 10000, "height": 8000},
    }


class FakeUnoBridge:
    """Stand-in for uno_bridge.UNOBridge's charts.py-facing methods."""

    def __init__(self, active_document=None):
        self.ctx = object()
        self.active_document = active_document
        self.charts = {"Chart 1": _new_chart()}
        self.exported = []

    def get_active_document(self):
        return self.active_document

    def get_document_info(self, doc):
        return {"type": doc.doc_type, "title": doc.title, "url": doc.url, "modified": doc.modified}

    def _get(self, chart_id):
        if chart_id not in self.charts:
            raise KeyError(f"No such chart '{chart_id}'.")
        return self.charts[chart_id]

    # -- chart lifecycle --

    def list_charts(self, doc, container=None):
        return [{"chart_id": cid, "sheet": c["sheet"], "ranges": c["ranges"]} for cid, c in self.charts.items()
                if container is None or c["sheet"] == container]

    def create_chart(self, doc, chart_type, source=None, data=None, container=None, position=None, size=None):
        if source is None and data is not None:
            raise NotImplementedError("create_chart_live with explicit 'data' is not implemented this pass.")
        if source is None:
            raise ValueError("Either source or data must be given.")
        index = len(self.charts) + 1
        name = f"Chart {index}"
        self.charts[name] = _new_chart(sheet=container or "Sheet1", ranges=[source], chart_type=chart_type)
        return {"chart_id": name, "sheet": container or "Sheet1"}

    def get_chart(self, doc, chart_id):
        c = self._get(chart_id)
        return {
            "chart_id": chart_id, "sheet": c["sheet"], "chart_type": c["chart_type"],
            "title": c["title"], "has_legend": c["has_legend"], "series_count": len(c["series"]),
            "ranges": c["ranges"],
        }

    def delete_chart(self, doc, chart_id):
        del self.charts[chart_id]

    def set_chart_type(self, doc, chart_id, chart_type, subtype=None):
        self._get(chart_id)["chart_type"] = chart_type

    def set_chart_data(self, doc, chart_id, source_range=None, data=None, categories=None):
        c = self._get(chart_id)
        if source_range is not None:
            c["ranges"] = [source_range]
        elif data is not None:
            raise NotImplementedError("set_chart_data_live with explicit 'data' is not implemented this pass.")
        else:
            raise ValueError("Either source_range or data must be given.")

    def set_chart_title(self, doc, chart_id, title=None, subtitle=None, properties=None):
        c = self._get(chart_id)
        applied = []
        if title is not None:
            c["title"] = title
            applied.append("title")
            if subtitle is not None:
                applied.append("subtitle")
        if properties:
            applied.extend(k for k in properties if k != "InvalidProperty")
        return applied

    def set_chart_legend(self, doc, chart_id, visible=None, position=None, properties=None):
        c = self._get(chart_id)
        applied = []
        if visible is not None:
            c["has_legend"] = visible
            applied.append("visible")
        if position is not None:
            c["legend_position"] = position
            applied.append("position")
        if properties:
            applied.extend(k for k in properties if k != "InvalidProperty")
        return applied

    def get_chart_series(self, doc, chart_id):
        return list(self._get(chart_id)["series"])

    def set_chart_series(self, doc, chart_id, series_id, properties):
        c = self._get(chart_id)
        index = int(series_id)
        if not (0 <= index < len(c["series"])):
            raise IndexError(f"series_id {series_id} out of range.")
        applied = [k for k in properties if k != "InvalidProperty"]
        c["series"][index].update({k: properties[k] for k in applied})
        return applied

    def add_chart_series(self, doc, chart_id, values, label=None, categories=None):
        c = self._get(chart_id)
        if not values:
            raise ValueError("values must be a non-empty list.")
        index = len(c["series"])
        entry = {"series_id": str(index), "values": list(values)}
        if label is not None:
            entry["label"] = label
        if categories:
            entry["categories"] = list(categories)
        c["series"].append(entry)
        return {"series_id": str(index), "range": f"Sheet1.Z{index + 1}"}

    def remove_chart_series(self, doc, chart_id, series_id):
        c = self._get(chart_id)
        index = int(series_id)
        if not (0 <= index < len(c["series"])):
            raise IndexError(f"series_id {series_id} out of range.")
        del c["series"][index]

    # -- axes / gridlines / labels --

    def set_chart_axis(self, doc, chart_id, axis, properties):
        c = self._get(chart_id)
        applied = [k for k in properties if k != "InvalidProperty"]
        c["axes"].setdefault(axis, {}).update({k: properties[k] for k in applied})
        return applied

    def set_chart_data_labels(self, doc, chart_id, properties, series_id=None):
        self._get(chart_id)
        return [k for k in properties if k != "InvalidProperty"]

    def set_chart_gridlines(self, doc, chart_id, axis, major=None, minor=None, properties=None):
        c = self._get(chart_id)
        applied = []
        if major is not None:
            c["gridlines"].setdefault(axis, {})["major"] = major
            applied.append("major")
        if minor is not None:
            c["gridlines"].setdefault(axis, {})["minor"] = minor
            applied.append("minor")
        if properties:
            applied.extend(k for k in properties if k != "InvalidProperty")
        return applied

    # -- trendlines / error bars --

    def add_chart_trendline(self, doc, chart_id, series_id, type, properties=None):
        c = self._get(chart_id)
        curves = c["trendlines"].setdefault(series_id, [])
        curves.append(type)
        return {"series_id": series_id, "type": type, "trendline_id": str(len(curves) - 1)}

    def remove_chart_trendline(self, doc, chart_id, series_id, trendline_id=None):
        c = self._get(chart_id)
        curves = c["trendlines"].get(series_id, [])
        idx = int(trendline_id) if trendline_id is not None else 0
        if not (0 <= idx < len(curves)):
            raise IndexError(f"trendline_id {trendline_id} out of range.")
        del curves[idx]

    def set_chart_error_bars(self, doc, chart_id, series_id, properties):
        c = self._get(chart_id)
        applied = [k for k in properties if k != "InvalidProperty"]
        c["error_bars"][series_id] = {k: properties[k] for k in applied}
        return applied

    # -- geometry / export --

    def set_chart_geometry(self, doc, chart_id, position=None, size=None):
        c = self._get(chart_id)
        applied = []
        if position:
            c["position"].update(position)
            applied.extend(position.keys())
        if size:
            c["size"].update(size)
            applied.extend(size.keys())
        return applied

    def export_chart(self, doc, chart_id, file_path, format="png", dpi=None):
        self._get(chart_id)
        if format not in ("png", "jpeg", "jpg", "svg"):
            raise NotImplementedError(f"format '{format}' not implemented.")
        self.exported.append((chart_id, file_path, format, dpi))


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


def test_list_charts_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("list_charts_live")()
    assert result["success"] is True
    assert result["result"]["count"] == 1


def test_create_chart_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("create_chart_live")(chart_type="line", source="A1:B3")
    assert result["success"] is True
    assert result["result"]["chart_id"] == "Chart 2"
    assert "Chart 2" in uno_bridge.charts


def test_create_chart_live_data_not_implemented():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("create_chart_live")(chart_type="line", data=[[1, 2], [3, 4]])
    assert result["success"] is False
    assert result["error"]["code"] == "UNSUPPORTED_CAPABILITY"


def test_get_chart_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("get_chart_live")(chart_id="Chart 1")
    assert result["success"] is True
    assert result["result"]["series_count"] == 2


def test_get_chart_live_not_found():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("get_chart_live")(chart_id="NoSuchChart")
    assert result["success"] is False
    assert result["error"]["code"] == "OBJECT_NOT_FOUND"


def test_delete_chart_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("delete_chart_live")(chart_id="Chart 1")
    assert result["success"] is True
    assert "Chart 1" not in uno_bridge.charts


def test_set_chart_type_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("set_chart_type_live")(chart_id="Chart 1", chart_type="pie")
    assert result["success"] is True
    assert uno_bridge.charts["Chart 1"]["chart_type"] == "pie"


def test_set_chart_data_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("set_chart_data_live")(chart_id="Chart 1", source_range="C1:D5")
    assert result["success"] is True
    assert uno_bridge.charts["Chart 1"]["ranges"] == ["C1:D5"]


def test_set_chart_title_live_skips_unknown_properties():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("set_chart_title_live")(chart_id="Chart 1", title="Sales", properties={"InvalidProperty": 1})
    assert result["success"] is True
    assert result["result"]["applied"] == ["title"]
    assert "InvalidProperty" in result["warnings"][0]
    assert uno_bridge.charts["Chart 1"]["title"] == "Sales"


def test_set_chart_legend_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("set_chart_legend_live")(chart_id="Chart 1", visible=True, position="bottom")
    assert result["success"] is True
    assert uno_bridge.charts["Chart 1"]["has_legend"] is True
    assert uno_bridge.charts["Chart 1"]["legend_position"] == "bottom"


def test_get_chart_series_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("get_chart_series_live")(chart_id="Chart 1")
    assert result["success"] is True
    assert result["result"]["count"] == 2


def test_set_chart_series_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("set_chart_series_live")(chart_id="Chart 1", series_id="0", properties={"color": 99})
    assert result["success"] is True
    assert uno_bridge.charts["Chart 1"]["series"][0]["color"] == 99


def test_add_chart_series_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("add_chart_series_live")(chart_id="Chart 1", values=[1, 2, 3], label="Q3")
    assert result["success"] is True
    assert result["result"]["series_id"] == "2"
    assert len(uno_bridge.charts["Chart 1"]["series"]) == 3
    assert uno_bridge.charts["Chart 1"]["series"][2]["values"] == [1, 2, 3]
    assert uno_bridge.charts["Chart 1"]["series"][2]["label"] == "Q3"


def test_add_chart_series_live_requires_values():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("add_chart_series_live")(chart_id="Chart 1", values=[])
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_PARAMETER"


def test_remove_chart_series_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("remove_chart_series_live")(chart_id="Chart 1", series_id="1")
    assert result["success"] is True
    assert len(uno_bridge.charts["Chart 1"]["series"]) == 1


def test_set_chart_axis_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("set_chart_axis_live")(chart_id="Chart 1", axis="y", properties={"min": 0, "max": 100})
    assert result["success"] is True
    assert uno_bridge.charts["Chart 1"]["axes"]["y"] == {"min": 0, "max": 100}


def test_set_chart_data_labels_live():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("set_chart_data_labels_live")(chart_id="Chart 1", properties={"ShowNumber": True})
    assert result["success"] is True
    assert result["result"]["applied"] == ["ShowNumber"]


def test_set_chart_gridlines_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("set_chart_gridlines_live")(chart_id="Chart 1", axis="y", major=True, minor=False)
    assert result["success"] is True
    assert uno_bridge.charts["Chart 1"]["gridlines"]["y"] == {"major": True, "minor": False}


def test_add_and_remove_chart_trendline_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    added = _handler("add_chart_trendline_live")(chart_id="Chart 1", series_id="0", type="linear")
    assert added["success"] is True
    assert added["result"]["trendline_id"] == "0"
    removed = _handler("remove_chart_trendline_live")(chart_id="Chart 1", series_id="0", trendline_id="0")
    assert removed["success"] is True
    assert uno_bridge.charts["Chart 1"]["trendlines"]["0"] == []


def test_set_chart_error_bars_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("set_chart_error_bars_live")(chart_id="Chart 1", series_id="0", properties={"PositiveError": 5})
    assert result["success"] is True
    assert uno_bridge.charts["Chart 1"]["error_bars"]["0"] == {"PositiveError": 5}


def test_set_chart_geometry_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("set_chart_geometry_live")(chart_id="Chart 1", position={"x": 500}, size={"width": 20000})
    assert result["success"] is True
    assert uno_bridge.charts["Chart 1"]["position"]["x"] == 500
    assert uno_bridge.charts["Chart 1"]["size"]["width"] == 20000


def test_export_chart_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    result = _handler("export_chart_live")(chart_id="Chart 1", file_path="/tmp/chart.png", format="png")
    assert result["success"] is True
    assert uno_bridge.exported == [("Chart 1", "/tmp/chart.png", "png", None)]


def test_export_chart_live_unsupported_format():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("export_chart_live")(chart_id="Chart 1", file_path="/tmp/chart.pdf", format="pdf")
    assert result["success"] is False
    assert result["error"]["code"] == "UNSUPPORTED_CAPABILITY"


if __name__ == "__main__":
    tests = [
        test_list_charts_live,
        test_create_chart_live,
        test_create_chart_live_data_not_implemented,
        test_get_chart_live,
        test_get_chart_live_not_found,
        test_delete_chart_live,
        test_set_chart_type_live,
        test_set_chart_data_live,
        test_set_chart_title_live_skips_unknown_properties,
        test_set_chart_legend_live,
        test_get_chart_series_live,
        test_set_chart_series_live,
        test_add_chart_series_live,
        test_add_chart_series_live_requires_values,
        test_remove_chart_series_live,
        test_set_chart_axis_live,
        test_set_chart_data_labels_live,
        test_set_chart_gridlines_live,
        test_add_and_remove_chart_trendline_live,
        test_set_chart_error_bars_live,
        test_set_chart_geometry_live,
        test_export_chart_live,
        test_export_chart_live_unsupported_format,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} charts tests passed.")
