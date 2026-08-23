"""
Live-verification probe for get_presentation_content_live (new tool,
Brian's new-tools assignment priority #5, bulk counterpart to
get_slide_content_live -- "give me all the content of the whole deck"
instead of N get_slide_content_live calls).

Builds a real 3-slide Impress deck (slide 1 titled + notes, slide 2
hidden and empty, slide 3 titled) then exercises the tool against the
real running extension, checking each result against what's actually in
the document (not just success=true).

Usage: python presentation-content-probe-windows.py
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
    print("get_presentation_content_live live-verification probe")
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
    soffice_log = REPO_DIR / "presentation-content-probe-soffice.log"
    with open(soffice_log, "w") as log_file:
        subprocess.Popen(
            [str(SOFFICE_EXE), "--headless", f"--accept={accept}", "--norestore"],
            stdout=log_file, stderr=subprocess.STDOUT,
        )
    bootstrap_path = REPO_DIR / "presentation-content-probe-bootstrap.py"
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

    print("\n[4/5] Set up real data: slide 1 titled + notes, slide 2 hidden + empty, slide 3 titled")
    r = http_post("/tools/insert_shape_live", {
        "shape_type": "text", "container": 0,
        "position": {"x": 1000, "y": 1000}, "size": {"width": 8000, "height": 2000},
    })
    if not r.get("success"):
        fail(f"insert_shape_live (slide 1) failed: {r}")
    shape1_id = r["result"]["shape_id"]
    r = http_post("/tools/set_shape_text_live", {"shape_id": shape1_id, "text": "Q1 Results"})
    if not r.get("success"):
        fail(f"set_shape_text_live (slide 1) failed: {r}")
    r = http_post("/tools/set_speaker_notes_live", {"slide": 0, "text": "Mention enterprise growth"})
    if not r.get("success"):
        fail(f"set_speaker_notes_live failed: {r}")

    r = http_post("/tools/insert_slide_live", {})
    if not r.get("success"):
        fail(f"insert_slide_live (slide 2) failed: {r}")
    r = http_post("/tools/hide_slide_live", {"slide": 1})
    if not r.get("success"):
        fail(f"hide_slide_live failed: {r}")

    r = http_post("/tools/insert_slide_live", {})
    if not r.get("success"):
        fail(f"insert_slide_live (slide 3) failed: {r}")
    r = http_post("/tools/insert_shape_live", {
        "shape_type": "text", "container": 2,
        "position": {"x": 1000, "y": 1000}, "size": {"width": 8000, "height": 2000},
    })
    if not r.get("success"):
        fail(f"insert_shape_live (slide 3) failed: {r}")
    shape3_id = r["result"]["shape_id"]
    r = http_post("/tools/set_shape_text_live", {"shape_id": shape3_id, "text": "Q3 Results"})
    if not r.get("success"):
        fail(f"set_shape_text_live (slide 3) failed: {r}")

    print("\n[5/5] get_presentation_content_live checks against real data")

    r = http_post("/tools/get_presentation_content_live", {})
    check("request succeeds with no arguments", r.get("success") is True)
    check("count reports all 3 slides", r.get("success") and r["result"]["count"] == 3)
    check("slides come back in deck order",
          r.get("success") and [s["index"] for s in r["result"]["slides"]] == [0, 1, 2])
    check("slide 1's real shape text is present",
          r.get("success") and any(t["text"] == "Q1 Results" for t in r["result"]["slides"][0]["text"]))
    check("slide 1's real notes are present by default",
          r.get("success") and r["result"]["slides"][0]["notes"] == "Mention enterprise growth")
    check("hidden slide 2 is still included by default, reports hidden=true, empty text",
          r.get("success") and r["result"]["slides"][1]["hidden"] is True and r["result"]["slides"][1]["text"] == [])
    check("slide 3's real shape text is present",
          r.get("success") and any(t["text"] == "Q3 Results" for t in r["result"]["slides"][2]["text"]))

    r = http_post("/tools/get_presentation_content_live", {"include_hidden": False})
    check("include_hidden=false drops the hidden slide, keeps count honest",
          r.get("success") and r["result"]["count"] == 2 and
          all(not s["hidden"] for s in r["result"]["slides"]))

    r = http_post("/tools/get_presentation_content_live", {"slides": [0, 2]})
    check("slides=[0, 2] scopes to just those two, in the order given",
          r.get("success") and r["result"]["count"] == 2 and
          [s["index"] for s in r["result"]["slides"]] == [0, 2])

    r = http_post("/tools/get_presentation_content_live", {"include_notes": False})
    check("include_notes=false omits the notes key on every slide, not just null",
          r.get("success") and all("notes" not in s for s in r["result"]["slides"]))

    r = http_post("/tools/get_presentation_content_live", {"include_shape_metadata": True})
    check("include_shape_metadata=true adds type/geometry to text entries",
          r.get("success") and r["result"]["slides"][0]["text"][0].get("type") == "text" and
          "width" in r["result"]["slides"][0]["text"][0])

    kill_soffice()
    run([str(UNOPKG_EXE), "remove", EXTENSION_ID])
    if soffice_log.exists():
        soffice_log.unlink()
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)

    print("\nPASS: all get_presentation_content_live checks passed against real headless LibreOffice.")
    sys.exit(0)


if __name__ == "__main__":
    main()
