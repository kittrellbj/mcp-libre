"""
Scripted clean-profile install -> start -> health-check ->
representative-tool-execute -> uninstall smoke test for the LibreOffice
MCP extension, Windows-only (mirrors build-oxt-windows.py's platform
scope; matches the repo's own unopkg.exe/soffice.exe path conventions).

Hardening-pass item #36/#37: this project's build has never had a single
scripted end-to-end verification -- every prior real-implementation
pass's live verification was ad hoc shell commands typed fresh each
time (kill soffice, build, unopkg remove/add, launch, bootstrap,
curl health, curl a tool, clean up), never captured as a reusable
artifact. This script is that artifact.

What this does NOT cover: there is no automated CI in this repo (no
.github/workflows, no other CI config) to run this on every commit --
that's a separate, larger infrastructure decision (a GitHub-hosted
runner has no LibreOffice preinstalled; would need `apt-get install
libreoffice` or similar, its own scope call), flagged in
docs/HARDENING_PLAN.md rather than built speculatively here. This
script is for a developer (or, if that infrastructure decision is made
later, a CI job) to run against a real local LibreOffice install.

Usage:
    python smoke-test-windows.py

Environment variables:
    LIBREOFFICE_PROGRAM_DIR  Path to LibreOffice's program/ directory
                             (contains soffice.exe, unopkg.exe,
                             python.exe). Defaults to
                             "E:\\LibreOffice\\program", this project's
                             own dev-environment convention throughout
                             its commit history -- override for any
                             other install location.

Exit code 0 on full success, 1 on any step failing. Prints which step
failed and why; does not attempt partial credit.
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
OXT_PATH = BUILD_DIR / "libreoffice-mcp-extension-2.0.8.oxt"
EXTENSION_ID = "org.mcp.libreoffice.extension"
LO_PROGRAM_DIR = Path(os.environ.get("LIBREOFFICE_PROGRAM_DIR", r"E:\LibreOffice\program"))
SOFFICE_EXE = LO_PROGRAM_DIR / "soffice.exe"
UNOPKG_EXE = LO_PROGRAM_DIR / "unopkg.exe"
LO_PYTHON_EXE = LO_PROGRAM_DIR / "python.exe"
UNO_PORT = 2002
HTTP_PORT = 8765
STEPS_TOTAL = 8

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


def http_post(path, payload, timeout=10):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"http://localhost:{HTTP_PORT}{path}", data=data,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def wait_for(predicate, timeout_seconds, poll_interval, description):
    """Poll `predicate` until it returns truthy or `timeout_seconds`
    elapses. Polls real state, not a fixed sleep -- a fixed sleep either
    wastes time on the fast path or isn't long enough on a slow one."""
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
    print("LibreOffice MCP extension smoke test")
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
    if not OXT_PATH.is_file():
        fail(f"Build reported success but {OXT_PATH} does not exist.")
    print(f"  built {OXT_PATH} ({OXT_PATH.stat().st_size:,} bytes)")

    step(3, "Uninstall any pre-existing deployment (tolerate 'not deployed')")
    result = run([str(UNOPKG_EXE), "remove", EXTENSION_ID])
    print(f"  unopkg remove exit code {result.returncode} (non-zero is fine if nothing was deployed)")

    step(4, "Install the freshly-built .oxt")
    result = run([str(UNOPKG_EXE), "add", str(OXT_PATH)])
    if result.returncode != 0:
        fail(f"unopkg add failed:\n{result.stdout}\n{result.stderr}")
    list_result = run([str(UNOPKG_EXE), "list"])
    if EXTENSION_ID not in list_result.stdout:
        fail(f"unopkg add reported success, but {EXTENSION_ID} is not in `unopkg list` output.")
    print(f"  {EXTENSION_ID} confirmed deployed via unopkg list")

    step(5, "Launch headless LibreOffice and dispatch mcp:start_mcp_server")
    kill_soffice()
    accept = f"socket,host=localhost,port={UNO_PORT};urp;"
    soffice_log = REPO_DIR / "smoke-test-soffice.log"
    with open(soffice_log, "w") as log_file:
        subprocess.Popen(
            [str(SOFFICE_EXE), "--headless", f"--accept={accept}", "--norestore"],
            stdout=log_file, stderr=subprocess.STDOUT,
        )

    bootstrap_path = REPO_DIR / "smoke-test-bootstrap.py"
    bootstrap_path.write_text(BOOTSTRAP_SCRIPT.format(program_dir=str(LO_PROGRAM_DIR), uno_port=UNO_PORT))
    try:
        def bootstrap_succeeds():
            result = run([str(LO_PYTHON_EXE), str(bootstrap_path)])
            return "DISPATCHED" in result.stdout

        wait_for(bootstrap_succeeds, timeout_seconds=60, poll_interval=2,
                 description="soffice UNO socket ready and mcp:start_mcp_server dispatched")
        print("  dispatched mcp:start_mcp_server")
    finally:
        bootstrap_path.unlink(missing_ok=True)

    step(6, "Health check: GET /health reports healthy")
    wait_for(lambda: http_get("/health").get("status") == "healthy",
             timeout_seconds=30, poll_interval=1, description="GET /health returning status: healthy")
    print("  /health OK")

    step(7, "Representative tool execution: insert_text_live + get_text_content_live round trip")
    marker = "smoke-test-marker-9f2c1"
    insert_result = http_post("/tools/insert_text_live", {"text": marker})
    if not insert_result.get("success"):
        fail(f"insert_text_live did not report success: {insert_result}")
    readback = http_post("/tools/get_text_content_live", {})
    if marker not in readback.get("content", ""):
        fail(f"get_text_content_live did not contain the inserted marker text. Got: {readback}")
    print(f"  round trip confirmed: inserted {marker!r}, read back correctly")

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

    print(f"\nPASS: all {STEPS_TOTAL} steps completed successfully.")
    sys.exit(0)


if __name__ == "__main__":
    main()
