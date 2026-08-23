"""
Live-verification probe for the get_document_statistics_live rewrite
(Brian's original priority #1, "Part 4" -- the last item of the Phase 6
queue) and the get_document_snapshot_live follow-up that composes it
(folded into the tail of this same pass per Buddy's direction).

Exercises all four document types in turn (Writer, Calc, Impress, Draw)
against a real running extension, building real structural content for
every new counted concept (tables, images, shapes, bookmarks,
hyperlinks, sections, footnotes, endnotes, comments, tracked changes
for Writer; used cells/formulas/errors/charts/pivot tables for Calc;
shape-type breakdown/notes/hidden slides for Impress/Draw) and checking
the tool's counts against what's actually in the document -- not just
`success: true`.

Writer's word_count/character_count/character_count_no_spaces are
cross-checked against extract_document_text_live's independently
computed text (a different, already-verified extraction path) rather
than a hand-guessed expected count -- avoids baking in an assumption
about exactly where insert_hyperlink_live/footnotes/endnotes place
their text.

Usage: python document-statistics-rewrite-probe-windows.py
Environment: LIBREOFFICE_PROGRAM_DIR, same convention as the other probes.
"""

import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent
BUILD_DIR = REPO_DIR / "build"
EXTENSION_ID = "org.mcp.libreoffice.extension"
LO_PROGRAM_DIR = Path(os.environ.get("LIBREOFFICE_PROGRAM_DIR", r"E:\LibreOffice\program"))
SOFFICE_EXE = LO_PROGRAM_DIR / "soffice.exe"
UNOPKG_EXE = LO_PROGRAM_DIR / "unopkg.exe"
LO_PYTHON_EXE = LO_PROGRAM_DIR / "python.exe"
UNO_PORT = 2002
HTTP_PORT = 8765

# Minimal valid 1x1 transparent PNG, for insert_image_live -- real bytes,
# not a stub file, so a real GraphicObjectShape lands on the page.
TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+A8AAQUBAScY42YAAAAASUVORK5CYII="
)

BOOTSTRAP_SCRIPT = r'''
import sys
sys.path.insert(0, r"{program_dir}")
import uno

localContext = uno.getComponentContext()
resolver = localContext.ServiceManager.createInstanceWithContext(
    "com.sun.star.bridge.UnoUrlResolver", localContext)
ctx = resolver.resolve("uno:socket,host=localhost,port={uno_port};urp;StarOffice.ComponentContext")
smgr = ctx.ServiceManager
desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)

doc = desktop.loadComponentFromURL("private:factory/{factory}", "_blank", 0, ())
doc.getCurrentController().getFrame().activate()

parser = smgr.createInstanceWithContext("com.sun.star.util.URLTransformer", ctx)
url = uno.createUnoStruct("com.sun.star.util.URL")
url.Complete = "mcp:start_mcp_server"
ok, parsed = parser.parseStrict(url)
frame = doc.getCurrentController().getFrame()
dispatch = frame.queryDispatch(parsed, "", 0)
dispatch.dispatch(parsed, ())
print("DISPATCHED")
'''


def fail(message):
    print(f"FAIL: {message}")
    sys.exit(1)


def run(args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, **kwargs)


def kill_soffice():
    subprocess.run(["taskkill", "/F", "/IM", "soffice.bin", "/T"], capture_output=True)
    subprocess.run(["taskkill", "/F", "/IM", "soffice.exe", "/T"], capture_output=True)


def http_get(path, timeout=5):
    with urllib.request.urlopen(f"http://127.0.0.1:{HTTP_PORT}{path}", timeout=timeout) as resp:
        return json.loads(resp.read())


def http_post(path, payload, timeout=10):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:{HTTP_PORT}{path}", data=data,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def wait_for(predicate, timeout_seconds, poll_interval, description):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            if predicate():
                return True
        except Exception:
            pass
        time.sleep(poll_interval)
    fail(f"Timed out after {timeout_seconds}s waiting for: {description}")


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}")
    if not condition:
        fail(f"check failed: {label}")


def call(path, payload=None):
    r = http_post(path, payload or {})
    if not r.get("success"):
        fail(f"{path} failed: {r}")
    # add_comment_live/set_track_changes_live are old-style (mcp_server.py)
    # tools -- they return their payload at the top level, not nested
    # under "result" the way the new-style tools/ envelope does.
    return r["result"] if "result" in r else r


def launch(factory):
    kill_soffice()
    accept = f"socket,host=localhost,port={UNO_PORT};urp;"
    soffice_log = REPO_DIR / "document-statistics-rewrite-probe-soffice.log"
    with open(soffice_log, "w") as log_file:
        subprocess.Popen(
            [str(SOFFICE_EXE), "--headless", f"--accept={accept}", "--norestore"],
            stdout=log_file, stderr=subprocess.STDOUT,
        )
    bootstrap_path = REPO_DIR / "document-statistics-rewrite-probe-bootstrap.py"
    bootstrap_path.write_text(BOOTSTRAP_SCRIPT.format(program_dir=str(LO_PROGRAM_DIR), uno_port=UNO_PORT, factory=factory))
    try:
        def bootstrap_succeeds():
            result = run([str(LO_PYTHON_EXE), str(bootstrap_path)])
            return "DISPATCHED" in result.stdout

        wait_for(bootstrap_succeeds, timeout_seconds=60, poll_interval=2,
                 description=f"soffice UNO socket ready and mcp:start_mcp_server dispatched ({factory})")
    finally:
        bootstrap_path.unlink(missing_ok=True)
    wait_for(lambda: http_get("/health").get("status") == "healthy",
             timeout_seconds=30, poll_interval=1, description="GET /health healthy")


def main():
    print("get_document_statistics_live rewrite (Part 4) live-verification probe")
    for exe, name in ((SOFFICE_EXE, "soffice.exe"), (UNOPKG_EXE, "unopkg.exe"), (LO_PYTHON_EXE, "python.exe")):
        if not exe.is_file():
            fail(f"{name} not found at {exe} -- set LIBREOFFICE_PROGRAM_DIR.")

    print("\n[1/6] Clean slate")
    kill_soffice()
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)

    print("\n[2/6] Build and install the .oxt")
    result = run([sys.executable, str(REPO_DIR / "build-oxt-windows.py")], cwd=REPO_DIR)
    if result.returncode != 0:
        fail(f"build failed:\n{result.stdout}\n{result.stderr}")
    oxt_files = list(BUILD_DIR.glob("*.oxt"))
    if not oxt_files:
        fail("Build reported success but no .oxt found in build/.")
    run([str(UNOPKG_EXE), "remove", EXTENSION_ID])
    result = run([str(UNOPKG_EXE), "add", str(oxt_files[0])])
    if result.returncode != 0:
        fail(f"unopkg add failed:\n{result.stdout}\n{result.stderr}")

    png_path = Path(tempfile.gettempdir()) / "mcp-libre-statistics-probe.png"
    png_path.write_bytes(base64.b64decode(TINY_PNG_B64))

    # ------------------------------------------------------------------
    print("\n[3/6] Writer -- full structural inventory")
    launch("swriter")
    call("/tools/set_paragraph_text_live", {"n": 1, "text": "First paragraph"})
    call("/tools/insert_paragraph_live", {"text": "Second paragraph", "at_paragraph": 1, "position": "after"})
    call("/tools/insert_table_live", {"rows": 2, "columns": 2})
    call("/tools/insert_shape_live", {"shape_type": "rectangle", "position": {"x": 1000, "y": 1000}, "size": {"width": 2000, "height": 2000}})
    call("/tools/insert_image_live", {"file_path": str(png_path)})
    call("/tools/add_bookmark_live", {"name": "Bookmark1", "start": 0, "end": 5})
    call("/tools/insert_hyperlink_live", {"url": "https://example.com", "text": "link text"})
    call("/tools/insert_section_live", {"name": "Section1", "range": {"start": 0, "end": 5}})
    call("/tools/add_footnote_live", {"text": "footnote text"})
    call("/tools/add_endnote_live", {"text": "endnote text"})
    call("/tools/add_comment_live", {"text": "comment text"})
    call("/tools/set_track_changes_live", {"enabled": True})
    call("/tools/insert_paragraph_live", {"text": "Third paragraph (tracked)", "at_paragraph": 2, "position": "after"})

    stats = call("/tools/get_document_statistics_live", {})
    extracted = call("/tools/extract_document_text_live", {})
    real_text = extracted["text"]
    check("type: writer", stats["type"] == "writer")
    check("word_count matches independent extract_document_text_live extraction",
          stats["word_count"] == len(real_text.split()))
    check("character_count matches independent extraction", stats["character_count"] == len(real_text))
    check("character_count_no_spaces matches independent extraction",
          stats["character_count_no_spaces"] == len("".join(real_text.split())))
    real_paragraph_count = call("/tools/get_paragraph_count_live", {})
    print(f"  DEBUG paragraph_count={stats['paragraph_count']!r} get_paragraph_count_live={real_paragraph_count!r}")
    check("paragraph_count agrees with the independently-tested get_paragraph_count_live",
          stats["paragraph_count"] == (real_paragraph_count.get("count") if isinstance(real_paragraph_count, dict) else real_paragraph_count))
    check("page_count is a real positive integer", isinstance(stats["page_count"], int) and stats["page_count"] >= 1)
    check("table_count reflects the real 1 table", stats["table_count"] == 1)
    check("shape_count includes the rectangle and the image (>= 2)", stats["shape_count"] >= 2)
    check("image_count reflects the real 1 inserted image", stats["image_count"] == 1)
    check("field_count excludes the comment annotation field (0, not 1)", stats["field_count"] == 0)
    check("bookmark_count reflects the real 1 bookmark", stats["bookmark_count"] == 1)
    check("hyperlink_count reflects the real 1 hyperlink", stats["hyperlink_count"] == 1)
    check("section_count reflects the real 1 section", stats["section_count"] == 1)
    check("footnote_count reflects the real 1 footnote", stats["footnote_count"] == 1)
    check("endnote_count reflects the real 1 endnote", stats["endnote_count"] == 1)
    check("comment_count reflects the real 1 comment (not double-counted into field_count)", stats["comment_count"] == 1)
    check("tracked_change_count is real and non-zero after a tracked edit", stats["tracked_change_count"] >= 1)

    snapshot = call("/tools/get_document_snapshot_live", {})
    check("snapshot.statistics matches get_document_statistics_live's own result", snapshot["statistics"] == stats)
    check("snapshot.view_state reports type writer", snapshot["view_state"]["type"] == "writer")
    check("snapshot.selection reports type writer", snapshot["selection"]["type"] == "writer")
    check("no calc/impress/draw active-object key leaks into a Writer snapshot",
          "active_sheet" not in snapshot and "active_slide" not in snapshot and "active_page" not in snapshot)

    # ------------------------------------------------------------------
    print("\n[4/6] Calc -- used cells, formulas, errors, charts, pivot tables")
    launch("scalc")
    call("/tools/insert_sheet_live", {"name": "Second Sheet"})
    call("/tools/set_cell_live", {"cell": "B1", "value": "Revenue"})
    call("/tools/set_cell_live", {"cell": "B2", "formula": "=1+1"})
    call("/tools/set_cell_live", {"cell": "B3", "formula": "=1/0"})
    call("/tools/set_cell_live", {"cell": "D1", "value": "Category"})
    call("/tools/set_cell_live", {"cell": "E1", "value": "Amount"})
    call("/tools/set_cell_live", {"cell": "D2", "value": "Fruit"})
    call("/tools/set_cell_live", {"cell": "E2", "value": 10})
    call("/tools/set_cell_live", {"cell": "D3", "value": "Veg"})
    call("/tools/set_cell_live", {"cell": "E3", "value": 20})
    call("/tools/create_chart_live", {"chart_type": "bar", "source": "D1:E3"})
    call("/tools/create_pivot_table_live", {
        "source": "D1:E3", "destination": "G1",
        "rows": ["Category"], "columns": [], "data_fields": [{"field": "Amount", "function": "sum"}],
    })

    stats = call("/tools/get_document_statistics_live", {})
    check("type: calc", stats["type"] == "calc")
    check("sheet_count reflects the real 2 sheets", stats["sheet_count"] == 2)
    print(f"  DEBUG used_cell_count={stats['used_cell_count']!r} formula_count={stats['formula_count']!r} error_count={stats['error_count']!r}")
    check("used_cell_count reflects real content (at least the 9 cells set directly)", stats["used_cell_count"] >= 9)
    check("formula_count reflects the real 2 formula cells (B2, B3)", stats["formula_count"] == 2)
    check("error_count reflects the real 1 error cell (B3, DIV/0)", stats["error_count"] == 1)
    check("chart_count reflects the real 1 chart", stats["chart_count"] == 1)
    check("pivot_count reflects the real 1 pivot table", stats["pivot_count"] == 1)
    check("truncated is false for a small sheet", stats["truncated"] is False)

    snapshot = call("/tools/get_document_snapshot_live", {})
    check("Calc snapshot.statistics.sheet_count matches", snapshot["statistics"]["sheet_count"] == 2)
    check("Calc snapshot still reports active_sheet", snapshot["active_sheet"]["name"] == "Sheet1")

    # ------------------------------------------------------------------
    print("\n[5/6] Impress -- shape-type breakdown, notes, hidden slides")
    launch("simpress")
    text_shape = call("/tools/insert_shape_live", {
        "shape_type": "text", "position": {"x": 1000, "y": 1000}, "size": {"width": 8000, "height": 2000},
    })
    call("/tools/set_shape_text_live", {"shape_id": text_shape["shape_id"], "text": "Title Slide"})
    call("/tools/insert_shape_live", {
        "shape_type": "rectangle", "position": {"x": 1000, "y": 4000}, "size": {"width": 2000, "height": 2000},
    })
    call("/tools/set_speaker_notes_live", {"slide": 0, "text": "Speaker notes here"})
    call("/tools/insert_slide_live", {})
    call("/tools/hide_slide_live", {"slide": 1})

    stats = call("/tools/get_document_statistics_live", {})
    check("type: impress", stats["type"] == "impress")
    check("page_count reflects the real 2 slides", stats["page_count"] == 2)
    check("shape_count includes the real text shape and rectangle (>= 2)", stats["shape_count"] >= 2)
    check("text_object_count reflects the real text shape (>= 1)", stats["text_object_count"] >= 1)
    check("notes_count reflects the real 1 slide with non-empty notes", stats["notes_count"] == 1)
    check("hidden_slide_count reflects the real 1 hidden slide", stats["hidden_slide_count"] == 1)

    snapshot = call("/tools/get_document_snapshot_live", {})
    check("Impress snapshot.statistics.page_count matches", snapshot["statistics"]["page_count"] == 2)
    check("Impress snapshot active_slide reports the real shape text",
          any(t["text"] == "Title Slide" for t in snapshot["active_slide"]["text"]))

    # ------------------------------------------------------------------
    print("\n[6/6] Draw -- shape-type breakdown, no notes/hidden-slide fields")
    launch("sdraw")
    text_shape = call("/tools/insert_shape_live", {
        "shape_type": "text", "position": {"x": 1000, "y": 1000}, "size": {"width": 8000, "height": 2000},
    })
    call("/tools/set_shape_text_live", {"shape_id": text_shape["shape_id"], "text": "Draw text"})
    call("/tools/insert_shape_live", {
        "shape_type": "ellipse", "position": {"x": 1000, "y": 4000}, "size": {"width": 2000, "height": 2000},
    })
    call("/tools/insert_draw_page_live", {"name": "Second Page"})

    stats = call("/tools/get_document_statistics_live", {})
    check("type: draw", stats["type"] == "draw")
    check("page_count reflects the real 2 pages", stats["page_count"] == 2)
    check("shape_count includes the real text shape and ellipse (>= 2)", stats["shape_count"] >= 2)
    check("text_object_count reflects the real text shape (>= 1)", stats["text_object_count"] >= 1)
    check("image_count is 0 (no image inserted on this page)", stats["image_count"] == 0)
    check("Draw statistics has no Impress-only notes_count/hidden_slide_count keys",
          "notes_count" not in stats and "hidden_slide_count" not in stats)

    snapshot = call("/tools/get_document_snapshot_live", {})
    check("Draw snapshot.statistics.page_count matches", snapshot["statistics"]["page_count"] == 2)
    check("Draw snapshot still reports active_page", bool(snapshot["active_page"]["name"]))

    kill_soffice()
    run([str(UNOPKG_EXE), "remove", EXTENSION_ID])
    soffice_log = REPO_DIR / "document-statistics-rewrite-probe-soffice.log"
    if soffice_log.exists():
        soffice_log.unlink()
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    png_path.unlink(missing_ok=True)

    print("\nPASS: all get_document_statistics_live/get_document_snapshot_live checks passed against real headless LibreOffice.")
    sys.exit(0)


if __name__ == "__main__":
    main()
