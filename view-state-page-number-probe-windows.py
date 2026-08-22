"""
Live-verification probe for the Writer current_page_number addition to
get_view_state_live (new tool behavior, Brian's new-tools assignment
priority #6, "get_view_state_live already established" the calc/
impress equivalents -- active_sheet, current_page_name -- but Writer
reported no page position at all).

Builds a real Writer document, forces a real page break so the
document genuinely has 2 pages, and checks that get_view_state_live's
current_page_number tracks the real view cursor position (1-based,
same number Writer's own status bar shows) -- both before and after
the break, not just a happy-path single check.

Usage: python view-state-page-number-probe-windows.py
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

doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
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
    print("get_view_state_live Writer current_page_number live-verification probe")
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

    print("\n[3/5] Launch headless LibreOffice (Writer), dispatch mcp:start_mcp_server")
    kill_soffice()
    accept = f"socket,host=localhost,port={UNO_PORT};urp;"
    soffice_log = REPO_DIR / "view-state-page-number-probe-soffice.log"
    with open(soffice_log, "w") as log_file:
        subprocess.Popen(
            [str(SOFFICE_EXE), "--headless", f"--accept={accept}", "--norestore"],
            stdout=log_file, stderr=subprocess.STDOUT,
        )
    bootstrap_path = REPO_DIR / "view-state-page-number-probe-bootstrap.py"
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

    print("\n[4/5] Baseline: fresh document, single page")
    r = http_post("/tools/get_view_state_live", {})
    check("baseline request succeeds", r.get("success") is True)
    check("type reports writer", r.get("success") and r["result"]["type"] == "writer")
    check("fresh single-page document reports current_page_number == 1",
          r.get("success") and r["result"]["current_page_number"] == 1)

    print("\n[5/5] Force a real page break, re-check current_page_number")
    r = http_post("/tools/set_paragraph_text_live", {"n": 1, "text": "First page text"})
    if not r.get("success"):
        fail(f"set_paragraph_text_live failed: {r}")
    r = http_post("/tools/insert_page_break_live", {"at_position": 1})
    if not r.get("success"):
        fail(f"insert_page_break_live failed: {r}")

    r = http_post("/tools/get_view_state_live", {})
    check("request succeeds after the break", r.get("success") is True)
    check("current_page_number now reports page 2 -- real page break, real cursor resync, not a stale/cached value",
          r.get("success") and r["result"]["current_page_number"] == 2)
    check("zoom/selection fields are still reported alongside the new field",
          r.get("success") and "zoom_value" in r["result"] and "has_selection" in r["result"])

    kill_soffice()
    run([str(UNOPKG_EXE), "remove", EXTENSION_ID])
    if soffice_log.exists():
        soffice_log.unlink()
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)

    print("\nPASS: all get_view_state_live Writer current_page_number checks passed against real headless LibreOffice.")
    sys.exit(0)


if __name__ == "__main__":
    main()
