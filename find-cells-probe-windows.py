"""
Live-verification probe for find_cells_live (new tool, Brian's new-tools
assignment priority #2, "the biggest obvious Calc hole").

Sets up real data across two sheets (values, a formula, a comment), then
exercises every look_in/match combination against the real running
extension, checking each result against what's actually in the document
(not just success=true).

Usage: python find-cells-probe-windows.py
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
    print("find_cells_live live-verification probe")
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
    soffice_log = REPO_DIR / "find-cells-probe-soffice.log"
    with open(soffice_log, "w") as log_file:
        subprocess.Popen(
            [str(SOFFICE_EXE), "--headless", f"--accept={accept}", "--norestore"],
            stdout=log_file, stderr=subprocess.STDOUT,
        )
    bootstrap_path = REPO_DIR / "find-cells-probe-bootstrap.py"
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

    print("\n[4/5] Set up real data: Sheet1 values/formula, Sheet2 with a comment")
    r = http_post("/tools/set_range_live", {"start_cell": "A1", "values": [
        ["Category", "Amount"], ["Travel", 500], ["Food", 200], ["Total", "=B2+B3"],
    ]})
    if not r.get("success"):
        fail(f"set_range_live failed: {r}")
    r = http_post("/tools/insert_sheet_live", {"name": "Notes"})
    if not r.get("success"):
        fail(f"insert_sheet_live failed: {r}")
    r = http_post("/tools/set_cell_live", {"sheet": "Notes", "cell": "C3", "value": "See Travel budget"})
    if not r.get("success"):
        fail(f"set_cell_live failed: {r}")
    r = http_post("/tools/add_cell_comment_live", {"sheet": "Notes", "cell": "C3", "text": "Approved by Travel desk"})
    if not r.get("success"):
        fail(f"add_cell_comment_live failed: {r}")

    print("\n[5/5] find_cells_live checks against real data")

    r = http_post("/tools/find_cells_live", {"query": "Travel", "sheet": "Sheet1"})
    check("values/contains on Sheet1 finds A2", r.get("success") and
          any(m["address"] == "A2" and m["sheet"] == "Sheet1" for m in r["result"]["matches"]))

    r = http_post("/tools/find_cells_live", {"query": "Travel"})
    check("omitted sheet searches the whole workbook (finds both Sheet1 A2 and Notes C3)",
          r.get("success") and
          {(m["sheet"], m["address"]) for m in r["result"]["matches"]} >= {("Sheet1", "A2"), ("Notes", "C3")})

    r = http_post("/tools/find_cells_live", {"query": "B2+B3", "look_in": "formulas", "sheet": "Sheet1"})
    check("formulas/contains finds the Total formula cell",
          r.get("success") and any(m["address"] == "B4" for m in r["result"]["matches"]))
    r = http_post("/tools/find_cells_live", {"query": "B2+B3", "look_in": "values", "sheet": "Sheet1"})
    check("values mode does NOT match on formula text (would find the computed value 700, not the formula string)",
          r.get("success") and not any(m["address"] == "B4" for m in r["result"]["matches"]))

    r = http_post("/tools/find_cells_live", {"query": "Approved by Travel desk", "look_in": "comments", "sheet": "Notes"})
    check("comments/exact finds the commented cell",
          r.get("success") and any(m["address"] == "C3" for m in r["result"]["matches"]))
    r = http_post("/tools/find_cells_live", {"query": "Approved by Travel desk", "look_in": "values", "sheet": "Notes"})
    check("values mode does NOT match on comment text",
          r.get("success") and not any(m["address"] == "C3" for m in r["result"]["matches"]))

    r = http_post("/tools/find_cells_live", {"query": "travel", "match": "exact", "sheet": "Sheet1"})
    check("match=exact, case-insensitive: 'travel' matches 'Travel' cell exactly",
          r.get("success") and any(m["address"] == "A2" for m in r["result"]["matches"]))
    r = http_post("/tools/find_cells_live", {"query": "trav", "match": "exact", "sheet": "Sheet1"})
    check("match=exact rejects a partial substring that 'contains' would accept",
          r.get("success") and r["result"]["count"] == 0)

    r = http_post("/tools/find_cells_live", {"query": "^[A-Z][a-z]+$", "match": "regex", "sheet": "Sheet1"})
    check("match=regex finds capitalized-word cells (Category/Travel/Food/Total)",
          r.get("success") and {m["value"] for m in r["result"]["matches"]} >= {"Category", "Travel", "Food", "Total"})

    r = http_post("/tools/find_cells_live", {"query": "[", "match": "regex", "sheet": "Sheet1"})
    check("invalid regex reports INVALID_PARAMETER, not a raw traceback",
          r.get("success") is False and r["error"]["code"] == "INVALID_PARAMETER")

    r = http_post("/tools/find_cells_live", {"query": "e", "sheet": "Sheet1", "max_results": 1})
    check("max_results caps the match count and reports truncated=true",
          r.get("success") and r["result"]["count"] == 1 and r["result"]["truncated"] is True)

    r = http_post("/tools/find_cells_live", {"query": "nonexistent-xyz-query"})
    check("no matches: count=0, truncated=false, empty matches list", r.get("success") and
          r["result"]["count"] == 0 and r["result"]["truncated"] is False and r["result"]["matches"] == [])

    kill_soffice()
    run([str(UNOPKG_EXE), "remove", EXTENSION_ID])
    if soffice_log.exists():
        soffice_log.unlink()
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)

    print("\nPASS: all find_cells_live checks passed against real headless LibreOffice.")
    sys.exit(0)


if __name__ == "__main__":
    main()
