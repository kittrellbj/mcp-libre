"""
Live transport-conformance regression probe for plugin/pythonpath/
ai_interface.py + mcp_jsonrpc.py (hardening Phase 3: Mcp-Session-Id
enforcement + MCP-Protocol-Version validation, docs/HARDENING_PLAN.md).

ai_interface.py can't be imported without a live LibreOffice/uno instance
(same constraint concurrency-probe-windows.py's docstring notes), so the
HTTP-header-level behavior this pass adds -- 400/404 responses, a
DELETE'd session actually becoming invalid -- can't be pytest-unit-
tested either (mcp_jsonrpc.py's own check_session_header()/
check_protocol_version_header() ARE unit-tested directly, see
tests/test_mcp_jsonrpc.py; this script is the live check that they're
actually wired into the real HTTP path). Built on smoke-test-windows.py/
concurrency-probe-windows.py's install/launch/health-check harness
rather than retyping it.

What it does:
1. Build + install + launch, same as smoke-test-windows.py steps 1-6.
2. POST /mcp initialize -- confirm a session id is minted and returned.
3. POST /mcp tools/list with no Mcp-Session-Id header -- expect 400.
4. POST /mcp tools/list with a made-up Mcp-Session-Id -- expect 404.
5. POST /mcp tools/list with the real session id -- expect 200.
6. POST /mcp tools/list with the real session id but an unsupported
   MCP-Protocol-Version header -- expect 400.
7. POST /mcp tools/list with the real session id and no
   MCP-Protocol-Version header at all -- expect 200 (backwards-compat
   fallback, not a violation).
8. POST /mcp initialize with an unsupported protocolVersion in the body
   -- expect the server's own LATEST_PROTOCOL_VERSION back, not the
   client's request echoed.
9. DELETE /mcp with the real session id -- expect 200, then confirm a
   later POST /mcp tools/list with that SAME (now-terminated) session id
   gets 404, not 200 -- the actual behavior change this pass makes over
   the prior no-op DELETE.
10. Uninstall, same as smoke-test-windows.py step 8.

Usage:
    python transport-conformance-probe-windows.py

Environment variables:
    LIBREOFFICE_PROGRAM_DIR  Same convention as smoke-test-windows.py.

Exit code 0 if every check passes, 1 on any failure (build/install/
launch, or a conformance check got the wrong status code).
"""

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent
BUILD_DIR = REPO_DIR / "build"
OXT_PATH = BUILD_DIR / "libreoffice-mcp-extension-2.0.12.oxt"
EXTENSION_ID = "org.mcp.libreoffice.extension"
LO_PROGRAM_DIR = Path(os.environ.get("LIBREOFFICE_PROGRAM_DIR", r"E:\LibreOffice\program"))
SOFFICE_EXE = LO_PROGRAM_DIR / "soffice.exe"
UNOPKG_EXE = LO_PROGRAM_DIR / "unopkg.exe"
LO_PYTHON_EXE = LO_PROGRAM_DIR / "python.exe"
UNO_PORT = 2002
HTTP_PORT = 8765
STEPS_TOTAL = 10

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

_failures = []


def step(n, description):
    print(f"\n[{n}/{STEPS_TOTAL}] {description}")


def fail(message):
    print(f"FAIL: {message}")
    sys.exit(1)


def check(description, condition, detail=""):
    """Record a conformance check's result without aborting the whole
    probe on the first failure -- unlike fail(), so one wrong status
    code doesn't hide the others in the same run."""
    if condition:
        print(f"  OK: {description}")
    else:
        print(f"  MISMATCH: {description} {detail}")
        _failures.append(f"{description} {detail}")


def run(args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, **kwargs)


def kill_soffice():
    subprocess.run(["taskkill", "/F", "/IM", "soffice.bin", "/T"], capture_output=True)
    subprocess.run(["taskkill", "/F", "/IM", "soffice.exe", "/T"], capture_output=True)


def http_get(path, timeout=5):
    with urllib.request.urlopen(f"http://localhost:{HTTP_PORT}{path}", timeout=timeout) as resp:
        return json.loads(resp.read())


def mcp_post(payload, session_id=None, protocol_version=None, timeout=15):
    """POST to /mcp and return (status, headers, parsed_body) -- unlike a
    plain urlopen() call, this does NOT raise on a non-2xx status, since
    this probe specifically wants to inspect 400/404 responses rather
    than treat them as unexpected."""
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if session_id is not None:
        headers["Mcp-Session-Id"] = session_id
    if protocol_version is not None:
        headers["MCP-Protocol-Version"] = protocol_version
    req = urllib.request.Request(f"http://localhost:{HTTP_PORT}/mcp", data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return resp.status, dict(resp.headers), (json.loads(body) if body else None)
    except urllib.error.HTTPError as e:
        body = e.read()
        return e.code, dict(e.headers), (json.loads(body) if body else None)


def mcp_delete(session_id=None, timeout=15):
    headers = {}
    if session_id is not None:
        headers["Mcp-Session-Id"] = session_id
    req = urllib.request.Request(f"http://localhost:{HTTP_PORT}/mcp", headers=headers, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


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
    print("mcp-libre transport-conformance probe (Mcp-Session-Id + MCP-Protocol-Version)")
    print(f"LibreOffice program dir: {LO_PROGRAM_DIR}")
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

    step(5, "Launch headless LibreOffice, open a document, dispatch mcp:start_mcp_server")
    kill_soffice()
    accept = f"socket,host=localhost,port={UNO_PORT};urp;"
    soffice_log = REPO_DIR / "transport-conformance-probe-soffice.log"
    with open(soffice_log, "w") as log_file:
        subprocess.Popen(
            [str(SOFFICE_EXE), "--headless", f"--accept={accept}", "--norestore"],
            stdout=log_file, stderr=subprocess.STDOUT,
        )

    bootstrap_path = REPO_DIR / "transport-conformance-probe-bootstrap.py"
    bootstrap_path.write_text(BOOTSTRAP_SCRIPT.format(program_dir=str(LO_PROGRAM_DIR), uno_port=UNO_PORT))
    try:
        def bootstrap_succeeds():
            result = run([str(LO_PYTHON_EXE), str(bootstrap_path)])
            return "DISPATCHED" in result.stdout

        wait_for(bootstrap_succeeds, timeout_seconds=60, poll_interval=2,
                 description="soffice ready, document open, mcp:start_mcp_server dispatched")
        print("  document open, server dispatched")
    finally:
        bootstrap_path.unlink(missing_ok=True)

    step(6, "Health check: GET /health reports healthy")
    wait_for(lambda: http_get("/health").get("status") == "healthy",
             timeout_seconds=30, poll_interval=1, description="GET /health returning status: healthy")
    print("  /health OK")

    step(7, "initialize: session id minted, unsupported version falls back to server's own")
    status, headers, body = mcp_post({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}})
    check("initialize (supported version) returns 200", status == 200, f"(got {status})")
    session_id = headers.get("Mcp-Session-Id")
    check("initialize mints an Mcp-Session-Id header", bool(session_id), f"(got {session_id!r})")
    check("initialize echoes the requested (supported) protocolVersion",
          body and body.get("result", {}).get("protocolVersion") == "2025-06-18",
          f"(got {body})")

    status2, _, body2 = mcp_post({"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {"protocolVersion": "1900-01-01"}})
    check("initialize with an unsupported protocolVersion still returns 200 (not a JSON-RPC error)",
          status2 == 200, f"(got {status2})")
    check("initialize with an unsupported protocolVersion falls back to the server's own version",
          body2 and body2.get("result", {}).get("protocolVersion") not in (None, "1900-01-01"),
          f"(got {body2})")

    step(8, "Mcp-Session-Id enforcement: missing / unknown / known")
    status, _, body = mcp_post({"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
    check("tools/list with NO Mcp-Session-Id header returns 400", status == 400, f"(got {status}, body {body})")

    status, _, body = mcp_post({"jsonrpc": "2.0", "id": 4, "method": "tools/list"}, session_id="made-up-session-id")
    check("tools/list with an UNKNOWN Mcp-Session-Id returns 404", status == 404, f"(got {status}, body {body})")

    status, _, body = mcp_post({"jsonrpc": "2.0", "id": 5, "method": "tools/list"}, session_id=session_id)
    check("tools/list with the REAL session id returns 200", status == 200, f"(got {status}, body {body})")

    step(9, "MCP-Protocol-Version validation: unsupported header / absent header")
    status, _, body = mcp_post(
        {"jsonrpc": "2.0", "id": 6, "method": "tools/list"}, session_id=session_id, protocol_version="1900-01-01"
    )
    check("tools/list with an UNSUPPORTED MCP-Protocol-Version header returns 400", status == 400, f"(got {status}, body {body})")

    status, _, body = mcp_post({"jsonrpc": "2.0", "id": 7, "method": "tools/list"}, session_id=session_id)
    check("tools/list with NO MCP-Protocol-Version header still returns 200 (backwards-compat fallback)",
          status == 200, f"(got {status}, body {body})")

    step(10, "DELETE actually terminates the session; a later request with it is rejected")
    del_status, del_body = mcp_delete(session_id=session_id)
    check("DELETE /mcp with the real session id returns 200", del_status == 200, f"(got {del_status}, body {del_body})")

    status, _, body = mcp_post({"jsonrpc": "2.0", "id": 8, "method": "tools/list"}, session_id=session_id)
    check("tools/list reusing the now-DELETED session id returns 404, not 200",
          status == 404, f"(got {status}, body {body})")

    del_status, del_body = mcp_delete()
    check("DELETE /mcp with NO Mcp-Session-Id header returns 400", del_status == 400, f"(got {del_status}, body {del_body})")

    del_status, del_body = mcp_delete(session_id="made-up-session-id")
    check("DELETE /mcp with an UNKNOWN Mcp-Session-Id returns 404", del_status == 404, f"(got {del_status}, body {del_body})")

    print("\nUninstall: kill soffice, unopkg remove, confirm it's gone")
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

    if _failures:
        print(f"\nFAIL: {len(_failures)} conformance check(s) did not match expected behavior:")
        for f in _failures:
            print(f"  - {f}")
        sys.exit(1)

    print("\nPASS: all transport-conformance checks matched expected behavior.")
    sys.exit(0)


if __name__ == "__main__":
    main()
