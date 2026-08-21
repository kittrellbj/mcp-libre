"""
One-off live-verification probe for the BUG #5-class fix to
apply_page_style()/remove_page_break() (found auditing HARDENING_PLAN.md's
durable-guidance writeup on 2026-08-21 -- same "omitted position resolves
through a stale view cursor" mechanism as the original BUG #5, applied to
two functions the original fix pass didn't reach).

Reuses smoke-test-windows.py's build/install/launch/health-check/uninstall
harness pattern rather than duplicating it by import (that script is a
`__main__`-only script, not an importable module) -- same steps, scoped to
this one repro instead of the general representative-tool round trip.

Repro: three paragraphs, batch_execute_live containing
[apply_page_style(paragraph=1, "Landscape"), remove_page_break(omitted)].
Before the fix: remove_page_break's omitted position resolves through
whatever the view cursor was BEFORE this batch started (unrelated to
paragraph 1) because apply_page_style never moved it. After the fix:
apply_page_style resyncs the view cursor to paragraph 1, so
remove_page_break's omitted position correctly resolves to paragraph 1 too.

Usage: python batch-page-style-probe-windows.py
Environment: LIBREOFFICE_PROGRAM_DIR, same convention as smoke-test-windows.py.
Exit code 0 on pass, 1 on any step failing.
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
    with urllib.request.urlopen(f"http://localhost:{HTTP_PORT}{path}", timeout=timeout) as resp:
        return json.loads(resp.read())


def http_post(path, payload, timeout=10):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"http://localhost:{HTTP_PORT}{path}", data=data,
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


def main():
    print("apply_page_style/remove_page_break batch-safety probe")
    for exe, name in ((SOFFICE_EXE, "soffice.exe"), (UNOPKG_EXE, "unopkg.exe"), (LO_PYTHON_EXE, "python.exe")):
        if not exe.is_file():
            fail(f"{name} not found at {exe} -- set LIBREOFFICE_PROGRAM_DIR.")

    print("\n[1/6] Clean slate")
    kill_soffice()
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)

    print("\n[2/6] Build the .oxt")
    result = run([sys.executable, str(REPO_DIR / "build-oxt-windows.py")], cwd=REPO_DIR)
    if result.returncode != 0:
        fail(f"build failed:\n{result.stdout}\n{result.stderr}")
    oxt_files = list(BUILD_DIR.glob("*.oxt"))
    if not oxt_files:
        fail("Build reported success but no .oxt found in build/.")
    oxt_path = oxt_files[0]
    print(f"  built {oxt_path.name}")

    print("\n[3/6] Install (remove any stale deployment first)")
    run([str(UNOPKG_EXE), "remove", EXTENSION_ID])
    result = run([str(UNOPKG_EXE), "add", str(oxt_path)])
    if result.returncode != 0:
        fail(f"unopkg add failed:\n{result.stdout}\n{result.stderr}")

    print("\n[4/6] Launch headless LibreOffice, dispatch mcp:start_mcp_server")
    kill_soffice()
    accept = f"socket,host=localhost,port={UNO_PORT};urp;"
    soffice_log = REPO_DIR / "batch-page-style-probe-soffice.log"
    with open(soffice_log, "w") as log_file:
        subprocess.Popen(
            [str(SOFFICE_EXE), "--headless", f"--accept={accept}", "--norestore"],
            stdout=log_file, stderr=subprocess.STDOUT,
        )
    bootstrap_path = REPO_DIR / "batch-page-style-probe-bootstrap.py"
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

    print("\n[5/6] Repro: 3 paragraphs, then batch [apply_page_style(paragraph=1), remove_page_break(omitted)]")
    for text in ("First paragraph.", "Second paragraph.", "Third paragraph."):
        r = http_post("/tools/append_paragraph_live", {"text": text})
        if not r.get("success"):
            fail(f"append_paragraph_live failed: {r}")

    # append_paragraph_live edits via its own text cursor (gotoEnd), never
    # touching the VIEW cursor -- so it stays wherever the fresh document
    # left it (paragraph 0), distinct from the batch's target (paragraph 1).
    # That makes a stale-cursor read decisively wrong if the resync fix
    # doesn't work, rather than accidentally matching by coincidence.

    batch_payload = {
        "operations": [
            {"tool_name": "apply_page_style_live", "parameters": {"style_name": "Landscape", "paragraph": 1, "insert_break": True}},
            {"tool_name": "remove_page_break_live", "parameters": {}},
        ],
        "stop_on_error": True,
    }
    batch_result = http_post("/tools/batch_execute_live", batch_payload)
    if not batch_result.get("success"):
        fail(f"batch_execute_live did not report success: {batch_result}")
    op_results = batch_result["result"]["results"]
    removed_at = op_results[1]["result"]["paragraph"]
    print(f"  apply_page_style_live acted on paragraph 1; remove_page_break_live (omitted) resolved paragraph {removed_at}")
    if removed_at != 1:
        fail(f"BATCH-UNSAFE: remove_page_break_live resolved paragraph {removed_at}, expected 1 "
             f"(should have inherited apply_page_style_live's position via the resynced view cursor).")
    print("  PASS: remove_page_break_live correctly inherited paragraph 1 from the prior batched call")

    print("\n[6/6] Uninstall")
    kill_soffice()
    run([str(UNOPKG_EXE), "remove", EXTENSION_ID])
    if soffice_log.exists():
        soffice_log.unlink()
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)

    print("\nPASS: batch page-style/remove-break resync fix live-verified.")
    sys.exit(0)


if __name__ == "__main__":
    main()
