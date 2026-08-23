"""
Live-verification probe for get_slide_content_live (new tool, Brian's
new-tools assignment priority #3, "give me all the content of slide 7"
instead of list_shapes_live + N get_shape_live calls).

Builds a real Impress deck with two shapes (one with text, one
deliberately empty) and speaker notes on slide 1, plus a second, hidden
slide, then exercises the tool against the real running extension,
checking each result against what's actually in the document (not just
success=true).

Usage: python slide-content-probe-windows.py
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

doc = desktop.loadComponentFromURL("private:factory/simpress", "_blank", 0, ())
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
    print("get_slide_content_live live-verification probe")
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

    print("\n[3/5] Launch headless LibreOffice (Impress), dispatch mcp:start_mcp_server")
    kill_soffice()
    accept = f"socket,host=localhost,port={UNO_PORT};urp;"
    soffice_log = REPO_DIR / "slide-content-probe-soffice.log"
    with open(soffice_log, "w") as log_file:
        subprocess.Popen(
            [str(SOFFICE_EXE), "--headless", f"--accept={accept}", "--norestore"],
            stdout=log_file, stderr=subprocess.STDOUT,
        )
    bootstrap_path = REPO_DIR / "slide-content-probe-bootstrap.py"
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

    print("\n[4/5] Set up real data: slide 1 gets a titled shape + an empty shape + notes, slide 2 is hidden and empty")
    r = http_post("/tools/insert_shape_live", {
        "shape_type": "text", "container": 0,
        "position": {"x": 1000, "y": 1000}, "size": {"width": 8000, "height": 2000},
    })
    if not r.get("success"):
        fail(f"insert_shape_live (titled) failed: {r}")
    title_shape_id = r["result"]["shape_id"]
    r = http_post("/tools/set_shape_text_live", {"shape_id": title_shape_id, "text": "Quarterly Results"})
    if not r.get("success"):
        fail(f"set_shape_text_live failed: {r}")

    r = http_post("/tools/insert_shape_live", {
        "shape_type": "rectangle", "container": 0,
        "position": {"x": 1000, "y": 4000}, "size": {"width": 3000, "height": 1500},
    })
    if not r.get("success"):
        fail(f"insert_shape_live (empty) failed: {r}")

    r = http_post("/tools/set_speaker_notes_live", {"slide": 0, "text": "Mention enterprise growth"})
    if not r.get("success"):
        fail(f"set_speaker_notes_live failed: {r}")

    r = http_post("/tools/insert_slide_live", {})
    if not r.get("success"):
        fail(f"insert_slide_live failed: {r}")
    r = http_post("/tools/hide_slide_live", {"slide": 1})
    if not r.get("success"):
        fail(f"hide_slide_live failed: {r}")

    print("\n[5/5] get_slide_content_live checks against real data")

    r = http_post("/tools/get_slide_content_live", {"slide": 0})
    check("slide 1 request succeeds", r.get("success") is True)
    check("index/name/hidden reported correctly for slide 1",
          r.get("success") and r["result"]["index"] == 0 and r["result"]["name"] and r["result"]["hidden"] is False)
    check("text includes the titled shape's real text",
          r.get("success") and any(t["text"] == "Quarterly Results" for t in r["result"]["text"]))
    check("the empty rectangle shape contributes nothing to text (skipped, not an empty-string entry)",
          r.get("success") and all(t["text"] for t in r["result"]["text"]) and
          len(r["result"]["text"]) == 1)
    check("notes returns the real speaker-notes text by default (include_notes defaults true)",
          r.get("success") and r["result"]["notes"] == "Mention enterprise growth")

    r = http_post("/tools/get_slide_content_live", {"slide": 0, "include_notes": False})
    check("include_notes=false omits the notes key entirely, not just null",
          r.get("success") and "notes" not in r["result"])

    r = http_post("/tools/get_slide_content_live", {"slide": 0, "include_shape_metadata": True})
    check("include_shape_metadata=true adds type/geometry to the text entry",
          r.get("success") and r["result"]["text"][0].get("type") == "text" and
          "width" in r["result"]["text"][0] and "height" in r["result"]["text"][0])

    r = http_post("/tools/get_slide_content_live", {"slide": 0, "include_shape_metadata": False})
    check("include_shape_metadata=false (default) omits type/geometry",
          r.get("success") and "type" not in r["result"]["text"][0])

    r = http_post("/tools/get_slide_content_live", {"slide": 1})
    check("hidden, empty slide 2 reports hidden=true and an empty text list",
          r.get("success") and r["result"]["hidden"] is True and r["result"]["text"] == [])

    r = http_post("/tools/get_slide_content_live", {"slide": "Nonexistent Slide Name"})
    check("unknown slide name reports a clean failure, not a raw traceback",
          r.get("success") is False)

    kill_soffice()
    run([str(UNOPKG_EXE), "remove", EXTENSION_ID])
    if soffice_log.exists():
        soffice_log.unlink()
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)

    print("\nPASS: all get_slide_content_live checks passed against real headless LibreOffice.")
    sys.exit(0)


if __name__ == "__main__":
    main()
