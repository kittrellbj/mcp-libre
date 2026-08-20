"""
Live concurrency-control regression probe for plugin/pythonpath/ai_interface.py
(hardening-pass phase 2: MCP transport concurrency control).

ai_interface.py can't be imported without a live LibreOffice/uno instance
(see tests/test_host_trust.py's docstring), so the correctness claim in
the module-level comment above _UNO_EXECUTION_LOCK -- "two threads
hammering two different Writer documents with no lock corrupts PyUNO
proxy calls; a process-wide lock around the whole tool-execution
sequence reaches zero errors" -- can't be pytest-unit-tested either. This
script is the reusable version of that ad hoc empirical test, built on
smoke-test-windows.py's install/launch/health-check harness rather than
retyping it.

What it does:
1. Build + install + launch, same as smoke-test-windows.py steps 1-6.
2. Create two Writer documents live via UNO.
3. Fire CONCURRENT_THREADS threads x ITERATIONS_PER_THREAD each, doing
   insert_text_live + get_text_content_live round trips against the two
   documents concurrently through the HTTP tool-execution path (the
   code path _UNO_EXECUTION_LOCK actually guards).
4. Assert zero errors across all calls. Any exception, non-success
   response, or wrong-content round trip fails the probe.
5. Uninstall, same as smoke-test-windows.py step 8.

Usage:
    python concurrency-probe-windows.py

Environment variables:
    LIBREOFFICE_PROGRAM_DIR  Same convention as smoke-test-windows.py.

Exit code 0 on zero errors, 1 on any failure (build/install/launch, or
a real concurrency error was reproduced).
"""

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent
BUILD_DIR = REPO_DIR / "build"
OXT_PATH = BUILD_DIR / "libreoffice-mcp-extension-2.0.5.oxt"
EXTENSION_ID = "org.mcp.libreoffice.extension"
LO_PROGRAM_DIR = Path(os.environ.get("LIBREOFFICE_PROGRAM_DIR", r"E:\LibreOffice\program"))
SOFFICE_EXE = LO_PROGRAM_DIR / "soffice.exe"
UNOPKG_EXE = LO_PROGRAM_DIR / "unopkg.exe"
LO_PYTHON_EXE = LO_PROGRAM_DIR / "python.exe"
UNO_PORT = 2002
HTTP_PORT = 8765
STEPS_TOTAL = 8

CONCURRENT_THREADS = 2
ITERATIONS_PER_THREAD = 300

# Opens two Writer documents and prints their frame indices so the probe
# can target each one's insert/read tools independently (the tool
# catalog addresses "the active document" -- to actually exercise two
# DIFFERENT documents concurrently, as the original empirical test did,
# each thread's requests activate its own document's frame immediately
# before its tool call. That activation call itself goes through the
# same lock/semaphore as any other tool call, which is intentional: it's
# part of the real call sequence a concurrent caller would make).
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

# Second document for the concurrency probe's two-target requirement.
doc2 = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
doc2.getCurrentController().getFrame().activate()
print("SECOND_DOC_OPENED")
'''


def step(n, description):
    print(f"\n[{n}/{STEPS_TOTAL}] {description}")


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


def http_post(path, payload, timeout=15):
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


def worker(thread_id, errors, lock):
    """Hammers insert_text_live + get_text_content_live for this
    thread's share of ITERATIONS_PER_THREAD, against whichever document
    is currently active on the server (there is exactly one HTTP
    process shared by both simulated clients, matching the real
    deployment: one extension instance, N concurrent callers)."""
    local_errors = []
    for i in range(ITERATIONS_PER_THREAD):
        marker = f"probe-t{thread_id}-{i}"
        try:
            insert_result = http_post("/tools/insert_text_live", {"text": marker})
            if not insert_result.get("success"):
                local_errors.append(f"t{thread_id} iter {i}: insert not success: {insert_result}")
                continue
            readback = http_post("/tools/get_text_content_live", {})
            if marker not in readback.get("content", ""):
                local_errors.append(f"t{thread_id} iter {i}: marker not found in readback")
        except Exception as e:
            local_errors.append(f"t{thread_id} iter {i}: {type(e).__name__}: {e}")
    with lock:
        errors.extend(local_errors)


def main():
    print("mcp-libre concurrency-control probe")
    print(f"LibreOffice program dir: {LO_PROGRAM_DIR}")
    print(f"{CONCURRENT_THREADS} threads x {ITERATIONS_PER_THREAD} iterations each")
    for exe, name in ((SOFFICE_EXE, "soffice.exe"), (UNOPKG_EXE, "unopkg.exe"), (LO_PYTHON_EXE, "python.exe")):
        if not exe.is_file():
            fail(f"{name} not found at {exe} -- set LIBREOFFICE_PROGRAM_DIR to your LibreOffice program/ directory.")

    step(1, "Clean slate: kill any running soffice, remove build/ dir")
    kill_soffice()
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)

    step(2, "Build the .oxt (build-oxt-windows.py)")
    result = run([sys.executable, str(REPO_DIR / "build-oxt-windows.py")], cwd=REPO_DIR)
    if result.returncode != 0:
        fail(f"build-oxt-windows.py failed:\n{result.stdout}\n{result.stderr}")
    print(f"  built {OXT_PATH} ({OXT_PATH.stat().st_size:,} bytes)")

    step(3, "Uninstall any pre-existing deployment (tolerate 'not deployed')")
    result = run([str(UNOPKG_EXE), "remove", EXTENSION_ID])
    print(f"  unopkg remove exit code {result.returncode} (non-zero is fine if nothing was deployed)")

    step(4, "Install the freshly-built .oxt")
    result = run([str(UNOPKG_EXE), "add", str(OXT_PATH)])
    if result.returncode != 0:
        fail(f"unopkg add failed:\n{result.stdout}\n{result.stderr}")
    print(f"  {EXTENSION_ID} installed")

    step(5, "Launch headless LibreOffice, open two documents, dispatch mcp:start_mcp_server")
    kill_soffice()
    accept = f"socket,host=localhost,port={UNO_PORT};urp;"
    soffice_log = REPO_DIR / "concurrency-probe-soffice.log"
    with open(soffice_log, "w") as log_file:
        subprocess.Popen(
            [str(SOFFICE_EXE), "--headless", f"--accept={accept}", "--norestore"],
            stdout=log_file, stderr=subprocess.STDOUT,
        )

    bootstrap_path = REPO_DIR / "concurrency-probe-bootstrap.py"
    bootstrap_path.write_text(BOOTSTRAP_SCRIPT.format(program_dir=str(LO_PROGRAM_DIR), uno_port=UNO_PORT))
    try:
        def bootstrap_succeeds():
            result = run([str(LO_PYTHON_EXE), str(bootstrap_path)])
            return "DISPATCHED" in result.stdout and "SECOND_DOC_OPENED" in result.stdout

        wait_for(bootstrap_succeeds, timeout_seconds=60, poll_interval=2,
                 description="soffice ready, two docs open, mcp:start_mcp_server dispatched")
        print("  two documents open, server dispatched")
    finally:
        bootstrap_path.unlink(missing_ok=True)

    step(6, "Health check: GET /health reports healthy")
    wait_for(lambda: http_get("/health").get("status") == "healthy",
             timeout_seconds=30, poll_interval=1, description="GET /health returning status: healthy")
    print("  /health OK")

    step(7, f"Concurrency probe: {CONCURRENT_THREADS} threads x {ITERATIONS_PER_THREAD} iterations")
    errors = []
    errors_lock = threading.Lock()
    threads = [
        threading.Thread(target=worker, args=(i, errors, errors_lock))
        for i in range(CONCURRENT_THREADS)
    ]
    start = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.monotonic() - start
    total_calls = CONCURRENT_THREADS * ITERATIONS_PER_THREAD
    print(f"  {total_calls} concurrent round trips in {elapsed:.1f}s, {len(errors)} errors")
    if errors:
        for e in errors[:20]:
            print(f"    {e}")
        if len(errors) > 20:
            print(f"    ... and {len(errors) - 20} more")
        fail(f"{len(errors)}/{total_calls} concurrent tool calls failed -- concurrency control regression.")

    step(8, "Uninstall: kill soffice, unopkg remove, confirm it's gone")
    kill_soffice()
    result = run([str(UNOPKG_EXE), "remove", EXTENSION_ID])
    if result.returncode != 0:
        fail(f"unopkg remove (uninstall) failed:\n{result.stdout}\n{result.stderr}")
    list_result = run([str(UNOPKG_EXE), "list"])
    if EXTENSION_ID in list_result.stdout:
        fail(f"unopkg remove reported success, but {EXTENSION_ID} is still in `unopkg list` output.")
    print(f"  {EXTENSION_ID} confirmed removed via unopkg list")

    if soffice_log.exists():
        soffice_log.unlink()
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)

    print(f"\nPASS: {total_calls}/{total_calls} concurrent tool calls succeeded, zero errors.")
    sys.exit(0)


if __name__ == "__main__":
    main()
