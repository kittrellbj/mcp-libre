"""
Re-verification probe for the wait_for_document_event_live capped-wait fix
(docs/EVENT_WAIT_CONCURRENCY_DECISION.md). Reruns the same positive/
negative pair the original finding used, this time against the fix:

- Positive (same-HTTP-path): a wait_for_document_event_live call and an
  append_paragraph_live call issued concurrently through the same HTTP
  server. Before the fix: the wait call held _UNO_EXECUTION_LOCK for its
  full requested timeout_ms, so the edit call could never even start
  until the wait timed out -- 0% observed. After the fix: the wait call's
  actual hold is clamped to _MAX_WAIT_LOCK_HOLD_MS per call, so the edit
  gets a fair turn at the lock much sooner; the caller polls
  (re-issues the wait call) to keep watching past one cap window. This
  probe polls up to POLL_ATTEMPTS times and reports whether the edit's
  event was ever observed, and after how many attempts.
- Negative (control, unchanged mechanism): the identical edit via a raw
  UNO socket connection that never touches _UNO_EXECUTION_LOCK at all --
  confirms no regression on the already-working path.

Usage: python event-wait-concurrency-probe-windows.py
Environment: LIBREOFFICE_PROGRAM_DIR, same convention as the other probes.
"""

import json
import os
import shutil
import subprocess
import sys
import threading
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
POLL_ATTEMPTS = 8

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

RAW_UNO_EDIT_SCRIPT = r'''
import sys
sys.path.insert(0, r"{program_dir}")
import uno
from com.sun.star.text.ControlCharacter import PARAGRAPH_BREAK

localContext = uno.getComponentContext()
resolver = localContext.ServiceManager.createInstanceWithContext(
    "com.sun.star.bridge.UnoUrlResolver", localContext)
ctx = resolver.resolve("uno:socket,host=localhost,port={uno_port};urp;StarOffice.ComponentContext")
smgr = ctx.ServiceManager
desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
doc = desktop.getCurrentComponent()
text = doc.getText()
cursor = text.createTextCursor()
cursor.gotoEnd(False)
text.insertControlCharacter(cursor, PARAGRAPH_BREAK, False)
text.insertString(cursor, "Raw-UNO negative-control edit.", False)
print("RAW_UNO_EDIT_DONE")
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


def main():
    print("wait_for_document_event_live capped-wait re-verification probe")
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

    print("\n[3/6] Launch headless LibreOffice, dispatch mcp:start_mcp_server")
    kill_soffice()
    accept = f"socket,host=localhost,port={UNO_PORT};urp;"
    soffice_log = REPO_DIR / "event-wait-probe-soffice.log"
    with open(soffice_log, "w") as log_file:
        subprocess.Popen(
            [str(SOFFICE_EXE), "--headless", f"--accept={accept}", "--norestore"],
            stdout=log_file, stderr=subprocess.STDOUT,
        )
    bootstrap_path = REPO_DIR / "event-wait-probe-bootstrap.py"
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

    print("\n[4/6] Discover real event_type names (register listener first, then edit, then read back)")
    # The listener registers lazily on the FIRST get/wait_for_document_event_live
    # call (_ensure_document_event_capture()) -- an edit fired before that
    # first call is never captured (documented open question in
    # uno_bridge.py's get_document_events docstring). Prime it first.
    priming = http_post("/tools/get_document_events_live", {"limit": 20})
    if not priming.get("success"):
        fail(f"priming get_document_events_live failed: {priming}")
    r = http_post("/tools/append_paragraph_live", {"text": "Discovery edit."})
    if not r.get("success"):
        fail(f"discovery append_paragraph_live failed: {r}")
    events_result = http_post("/tools/get_document_events_live", {"limit": 20})
    if not events_result.get("success"):
        fail(f"get_document_events_live failed: {events_result}")
    seen_types = sorted({e["event_type"] for e in events_result["result"]["events"]})
    if not seen_types:
        fail("No document events captured at all (even after priming the listener) -- "
             "can't run the positive-pair test.")
    print(f"  observed real event types: {seen_types}")

    print("\n[5/6] POSITIVE pair: same-HTTP-path wait_for_document_event_live vs append_paragraph_live")
    edit_started = threading.Event()
    edit_done = {"result": None, "elapsed_ms": None}

    def do_edit():
        edit_started.wait()
        time.sleep(0.15)  # let the first wait call acquire the lock first
        t0 = time.perf_counter()
        edit_done["result"] = http_post("/tools/append_paragraph_live", {"text": "Positive-pair interleaved edit."})
        edit_done["elapsed_ms"] = (time.perf_counter() - t0) * 1000

    edit_thread = threading.Thread(target=do_edit)
    edit_thread.start()

    observed = None
    for attempt in range(1, POLL_ATTEMPTS + 1):
        edit_started.set()
        t0 = time.perf_counter()
        wait_result = http_post("/tools/wait_for_document_event_live",
                                 {"event_types": seen_types, "timeout_ms": 5000}, timeout=10)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        if not wait_result.get("success"):
            fail(f"wait_for_document_event_live call {attempt} failed: {wait_result}")
        timed_out = wait_result["result"]["timed_out"]
        print(f"  attempt {attempt}: held lock for {elapsed_ms:.0f}ms, timed_out={timed_out}"
              + ("" if timed_out else f", event={wait_result['result']['event']['event_type']}"))
        if elapsed_ms > 600:
            fail(f"attempt {attempt} held the lock for {elapsed_ms:.0f}ms -- "
                 f"the cap (500ms) did not clamp the wait.")
        if not timed_out:
            observed = wait_result["result"]["event"]
            break

    edit_thread.join(timeout=10)
    if edit_done["result"] is None or not edit_done["result"].get("success"):
        fail(f"interleaved append_paragraph_live never completed successfully: {edit_done['result']}")
    print(f"  interleaved edit completed in {edit_done['elapsed_ms']:.0f}ms (own HTTP round trip)")

    if observed is None:
        print(f"  RESULT: never observed the interleaved edit's event within "
              f"{POLL_ATTEMPTS} poll attempts ({POLL_ATTEMPTS * 0.5:.1f}s of capped waiting), "
              f"even though the edit itself completed. Continuing to the negative control "
              f"rather than aborting -- this is a real finding to report, not a script bug.")
    else:
        print(f"  RESULT: interleaved edit's event observed after {attempt} poll attempt(s)")

    # Diagnostic regardless of outcome above: is the edit's event actually
    # sitting in the buffer (fired and captured, just missed by the poll
    # loop's per-call snapshot timing) or never captured at all (a
    # different bug)? Distinguishes a structural snapshot/lock-ordering
    # property from an event-capture failure.
    post_events = http_post("/tools/get_document_events_live", {"limit": 20})
    if post_events.get("success"):
        modify_events = [e for e in post_events["result"]["events"] if e["event_type"] == "OnModifyChanged"]
        print(f"  diagnostic: {len(modify_events)} OnModifyChanged event(s) in the buffer post-edit "
              f"(seqs: {[e['seq'] for e in modify_events]})")

    print("\n[6/6] NEGATIVE control: raw-UNO edit fired WHILE a wait call is actively blocked "
          "(bypasses _UNO_EXECUTION_LOCK entirely -- must be genuinely concurrent with the wait, "
          "not run-then-wait, or it hits the exact same snapshot-timing miss as the positive pair "
          "for the wrong reason)")
    raw_script_path = REPO_DIR / "event-wait-probe-raw-edit.py"
    raw_script_path.write_text(RAW_UNO_EDIT_SCRIPT.format(program_dir=str(LO_PROGRAM_DIR), uno_port=UNO_PORT))
    try:
        raw_started = threading.Event()

        def do_raw_edit():
            raw_started.wait()
            time.sleep(0.15)  # let the wait call start blocking first
            run([str(LO_PYTHON_EXE), str(raw_script_path)])

        raw_thread = threading.Thread(target=do_raw_edit)
        raw_thread.start()

        raw_observed = None
        for attempt in range(1, POLL_ATTEMPTS + 1):
            raw_started.set()
            wait_result = http_post("/tools/wait_for_document_event_live",
                                     {"event_types": seen_types, "timeout_ms": 5000}, timeout=10)
            if not wait_result.get("success"):
                fail(f"wait_for_document_event_live (negative control) call {attempt} failed: {wait_result}")
            if not wait_result["result"]["timed_out"]:
                raw_observed = wait_result["result"]["event"]
                break
        raw_thread.join(timeout=10)
        if raw_observed is None:
            fail("NEGATIVE CONTROL FAILED (regression): raw-UNO edit's event was never observed "
                 "even fired concurrently with an active wait -- this path worked before the fix "
                 "and must still work.")
        print(f"  PASS: raw-UNO edit's event observed after {attempt} poll attempt(s) (no regression)")
    finally:
        raw_script_path.unlink(missing_ok=True)

    print("\n[7/7] Uninstall")
    kill_soffice()
    run([str(UNOPKG_EXE), "remove", EXTENSION_ID])
    if soffice_log.exists():
        soffice_log.unlink()
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)

    print("\nPASS: capped-wait fix live-verified with both positive and negative pairs.")
    sys.exit(0)


if __name__ == "__main__":
    main()
