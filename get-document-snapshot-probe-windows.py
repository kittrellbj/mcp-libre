"""
Live-verification probe for get_document_snapshot_live (new tool,
Brian's new-tools assignment priority #14 -- compact cross-doc-type
"what's open right now" snapshot).

Exercises the tool against four real documents in turn (Writer, Calc,
Impress, Draw), each closed and reopened as the new type via
soffice's own private:factory URLs, checking the per-type fields
against what's actually in each real document.

Usage: python get-document-snapshot-probe-windows.py
Environment: LIBREOFFICE_PROGRAM_DIR, same convention as the other probes.
"""

import json
import os
import shutil
import subprocess
import sys
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


def launch(factory):
    kill_soffice()
    accept = f"socket,host=localhost,port={UNO_PORT};urp;"
    soffice_log = REPO_DIR / "get-document-snapshot-probe-soffice.log"
    with open(soffice_log, "w") as log_file:
        subprocess.Popen(
            [str(SOFFICE_EXE), "--headless", f"--accept={accept}", "--norestore"],
            stdout=log_file, stderr=subprocess.STDOUT,
        )
    bootstrap_path = REPO_DIR / "get-document-snapshot-probe-bootstrap.py"
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
    print("get_document_snapshot_live live-verification probe")
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

    print("\n[3/6] Writer snapshot")
    launch("swriter")
    r = http_post("/tools/set_paragraph_text_live", {"n": 1, "text": "First paragraph"})
    if not r.get("success"):
        fail(f"set_paragraph_text_live failed: {r}")
    r = http_post("/tools/insert_paragraph_live", {"text": "Second paragraph", "at_paragraph": 1, "position": "after"})
    if not r.get("success"):
        fail(f"insert_paragraph_live failed: {r}")
    r = http_post("/tools/get_document_snapshot_live", {})
    check("Writer snapshot request succeeds", r.get("success") is True)
    check("type: writer", r.get("success") and r["result"]["type"] == "writer")
    check("paragraph_count reflects the real 2 paragraphs",
          r.get("success") and r["result"]["paragraph_count"] == 2)
    check("page_count is a real positive integer, not None",
          r.get("success") and isinstance(r["result"]["page_count"], int) and r["result"]["page_count"] >= 1)
    check("no calc/impress/draw fields leak into a Writer snapshot",
          r.get("success") and "sheet_count" not in r["result"] and "slide_count" not in r["result"])

    print("\n[4/6] Calc snapshot")
    launch("scalc")
    r = http_post("/tools/insert_sheet_live", {"name": "Second Sheet"})
    if not r.get("success"):
        fail(f"insert_sheet_live failed: {r}")
    r = http_post("/tools/set_cell_live", {"cell": "B2", "value": "Hello"})
    if not r.get("success"):
        fail(f"set_cell_live failed: {r}")
    r = http_post("/tools/get_document_snapshot_live", {})
    check("Calc snapshot request succeeds", r.get("success") is True)
    check("type: calc", r.get("success") and r["result"]["type"] == "calc")
    check("sheet_count reflects the real 2 sheets", r.get("success") and r["result"]["sheet_count"] == 2)
    check("active_sheet reports the real active sheet's real used range",
          r.get("success") and r["result"]["active_sheet"]["name"] == "Sheet1" and
          r["result"]["active_sheet"]["used_range"] is not None)

    print("\n[5/6] Impress snapshot")
    launch("simpress")
    r = http_post("/tools/insert_shape_live", {
        "shape_type": "text", "container": 0,
        "position": {"x": 1000, "y": 1000}, "size": {"width": 8000, "height": 2000},
    })
    if not r.get("success"):
        fail(f"insert_shape_live failed: {r}")
    shape_id = r["result"]["shape_id"]
    r = http_post("/tools/set_shape_text_live", {"shape_id": shape_id, "text": "Title Slide"})
    if not r.get("success"):
        fail(f"set_shape_text_live failed: {r}")
    r = http_post("/tools/insert_slide_live", {})
    if not r.get("success"):
        fail(f"insert_slide_live failed: {r}")
    r = http_post("/tools/get_document_snapshot_live", {})
    check("Impress snapshot request succeeds", r.get("success") is True)
    check("type: impress", r.get("success") and r["result"]["type"] == "impress")
    check("slide_count reflects the real 2 slides", r.get("success") and r["result"]["slide_count"] == 2)
    check("active_slide reports the real active slide's real shape text",
          r.get("success") and any(t["text"] == "Title Slide" for t in r["result"]["active_slide"]["text"]))

    print("\n[6/6] Draw snapshot")
    launch("sdraw")
    r = http_post("/tools/insert_draw_page_live", {"name": "Second Page"})
    if not r.get("success"):
        fail(f"insert_draw_page_live failed: {r}")
    r = http_post("/tools/get_document_snapshot_live", {})
    check("Draw snapshot request succeeds", r.get("success") is True)
    check("type: draw", r.get("success") and r["result"]["type"] == "draw")
    check("page_count reflects the real 2 pages", r.get("success") and r["result"]["page_count"] == 2)
    check("active_page reports the real active page's real name",
          r.get("success") and r["result"]["active_page"]["name"])

    kill_soffice()
    run([str(UNOPKG_EXE), "remove", EXTENSION_ID])
    soffice_log = REPO_DIR / "get-document-snapshot-probe-soffice.log"
    if soffice_log.exists():
        soffice_log.unlink()
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)

    print("\nPASS: all get_document_snapshot_live checks passed against real headless LibreOffice.")
    sys.exit(0)


if __name__ == "__main__":
    main()
