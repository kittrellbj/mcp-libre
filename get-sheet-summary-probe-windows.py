"""
Live-verification probe for get_sheet_summary_live (new tool, Brian's
new-tools assignment priority #13, at-a-glance sheet summary instead
of get_active_sheet_live + get_used_range_live + get_freeze_panes_live
+ reading protection separately).

Checks the tool against the real running extension: a genuinely blank
sheet (must NOT report a misleading "1x1 used" -- gotoStartOfUsedArea/
gotoEndOfUsedArea both collapse to A1 on an empty sheet), a sheet with
real content and a real freeze, and a protected sheet.

Follow-up pass, real gap flagged after this tool first shipped: Brian's
original spec also asked for "formula+error counts", missing entirely
from the first version. This probe also sets a real formula cell and a
real DIV/0-erroring formula cell, then checks formula_count/error_count
against those real, independently-created cells -- reusing the same
cell.getFormula()-truthiness gotcha get_document_statistics_live's
probe caught (a plain value cell is NOT a formula cell).

Usage: python get-sheet-summary-probe-windows.py
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

doc = desktop.loadComponentFromURL("private:factory/scalc", "_blank", 0, ())
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


def main():
    print("get_sheet_summary_live live-verification probe")
    for exe, name in ((SOFFICE_EXE, "soffice.exe"), (UNOPKG_EXE, "unopkg.exe"), (LO_PYTHON_EXE, "python.exe")):
        if not exe.is_file():
            fail(f"{name} not found at {exe} -- set LIBREOFFICE_PROGRAM_DIR.")

    print("\n[1/5] Clean slate")
    kill_soffice()
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)

    print("\n[2/5] Build and install the .oxt")
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

    print("\n[3/5] Launch headless LibreOffice (Calc), dispatch mcp:start_mcp_server")
    kill_soffice()
    accept = f"socket,host=localhost,port={UNO_PORT};urp;"
    soffice_log = REPO_DIR / "get-sheet-summary-probe-soffice.log"
    with open(soffice_log, "w") as log_file:
        subprocess.Popen(
            [str(SOFFICE_EXE), "--headless", f"--accept={accept}", "--norestore"],
            stdout=log_file, stderr=subprocess.STDOUT,
        )
    bootstrap_path = REPO_DIR / "get-sheet-summary-probe-bootstrap.py"
    bootstrap_path.write_text(BOOTSTRAP_SCRIPT.format(program_dir=str(LO_PROGRAM_DIR), uno_port=UNO_PORT))
    try:
        def bootstrap_succeeds():
            result = run([str(LO_PYTHON_EXE), str(bootstrap_path)])
            return "DISPATCHED" in result.stdout

        wait_for(bootstrap_succeeds, timeout_seconds=60, poll_interval=2,
                 description="soffice UNO socket ready and mcp:start_mcp_server dispatched")
    finally:
        bootstrap_path.unlink(missing_ok=True)

    wait_for(lambda: http_get("/health").get("status") == "healthy",
             timeout_seconds=30, poll_interval=1, description="GET /health healthy")
    print("  extension up")

    print("\n[4/5] get_sheet_summary_live on a genuinely blank sheet")
    r = http_post("/tools/get_sheet_summary_live", {})
    check("request succeeds on a fresh document", r.get("success") is True)
    check("name/visible/protected reported correctly",
          r.get("success") and r["result"]["visible"] is True and r["result"]["protected"] is False)
    check("blank sheet reports used_range: null, not a misleading 1x1",
          r.get("success") and r["result"]["used_range"] is None)
    check("blank sheet reports row_count: 0, column_count: 0",
          r.get("success") and r["result"]["row_count"] == 0 and r["result"]["column_count"] == 0)
    check("blank sheet reports frozen: false",
          r.get("success") and r["result"]["frozen"]["frozen"] is False)
    check("blank sheet reports formula_count/error_count: 0, counts_truncated: false",
          r.get("success") and r["result"]["formula_count"] == 0 and r["result"]["error_count"] == 0 and
          r["result"]["counts_truncated"] is False)

    print("\n[5/5] get_sheet_summary_live with real content, a real freeze, protection, a real formula, and a real error")
    r = http_post("/tools/set_cell_live", {"cell": "B2", "value": "Revenue"})
    if not r.get("success"):
        fail(f"set_cell_live failed: {r}")
    r = http_post("/tools/set_cell_live", {"cell": "D5", "value": 100})
    if not r.get("success"):
        fail(f"set_cell_live (D5) failed: {r}")
    r = http_post("/tools/set_cell_live", {"cell": "E5", "formula": "=D5*2"})
    if not r.get("success"):
        fail(f"set_cell_live (E5 real formula) failed: {r}")
    r = http_post("/tools/set_cell_live", {"cell": "E6", "formula": "=D5/0"})
    if not r.get("success"):
        fail(f"set_cell_live (E6 real DIV/0 error) failed: {r}")
    r = http_post("/tools/freeze_panes_live", {"cell": "B2"})
    if not r.get("success"):
        fail(f"freeze_panes_live failed: {r}")
    r = http_post("/tools/protect_sheet_live", {"password": "secret"})
    if not r.get("success"):
        fail(f"protect_sheet_live failed: {r}")

    r = http_post("/tools/get_sheet_summary_live", {})
    check("request succeeds with real content/freeze/protection", r.get("success") is True)
    check("used_range reflects the real content span (B2:E6)",
          r.get("success") and r["result"]["used_range"] == {"start_column": 1, "start_row": 1, "end_column": 4, "end_row": 5})
    check("row_count/column_count match the real span (5 rows, 4 columns)",
          r.get("success") and r["result"]["row_count"] == 5 and r["result"]["column_count"] == 4)
    check("protected: true after a real protect_sheet_live call",
          r.get("success") and r["result"]["protected"] is True)
    check("frozen state matches the real freeze at B2",
          r.get("success") and r["result"]["frozen"]["frozen"] is True and r["result"]["frozen"]["cell"] == "B2")
    check("formula_count is 2 (E5's real formula + E6's erroring formula), not counting D5's plain value",
          r.get("success") and r["result"]["formula_count"] == 2)
    check("error_count is 1 (only E6's real DIV/0), not E5's valid formula",
          r.get("success") and r["result"]["error_count"] == 1)
    check("counts_truncated is false for a small real sheet",
          r.get("success") and r["result"]["counts_truncated"] is False)

    kill_soffice()
    run([str(UNOPKG_EXE), "remove", EXTENSION_ID])
    if soffice_log.exists():
        soffice_log.unlink()
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)

    print("\nPASS: all get_sheet_summary_live checks passed against real headless LibreOffice.")
    sys.exit(0)


if __name__ == "__main__":
    main()
