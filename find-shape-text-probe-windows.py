"""
Live-verification probe for find_shape_text_live (new tool, Brian's
new-tools assignment priority #4, "shared search across Impress/Draw
shapes, optionally Writer/Calc drawing objects").

Scoped to Impress -- the doc type Brian's assignment names first and the
one where the container-scoping logic (one slide vs. every slide) is
actually exercised. The Writer/Calc branches in
UNOBridge._iter_shape_text_containers() route through the exact same
_resolve_shape_container()-family helpers list_shapes_live/get_shape_live/
insert_shape_live already live-verified across all four doc types in the
original drawing_objects.py pass (see that module's docstring) -- not
re-verified independently here, flagging that plainly rather than
implying broader coverage than this probe actually has.

Sets up real slides with real shapes across two containers, then
exercises match modes, container scoping, and the empty-shape/truncation
edge cases against the real running extension, checking each result
against what's actually on the slide (not just success=true).

Usage: python find-shape-text-probe-windows.py
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
    print("find_shape_text_live live-verification probe")
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
    soffice_log = REPO_DIR / "find-shape-text-probe-soffice.log"
    with open(soffice_log, "w") as log_file:
        subprocess.Popen(
            [str(SOFFICE_EXE), "--headless", f"--accept={accept}", "--norestore"],
            stdout=log_file, stderr=subprocess.STDOUT,
        )
    bootstrap_path = REPO_DIR / "find-shape-text-probe-bootstrap.py"
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

    print("\n[4/5] Set up real data: 2 slides, shapes with/without text, a duplicate-text pair")
    r = http_post("/tools/insert_slide_live", {"position": 1})
    if not r.get("success"):
        fail(f"insert_slide_live failed: {r}")
    r = http_post("/tools/list_slides_live", {})
    if not r.get("success") or r["result"]["count"] != 2:
        fail(f"list_slides_live did not report 2 slides: {r}")
    # Real slide names, not an assumed locale-specific default (e.g.
    # "Slide 1") -- LibreOffice's default page name is locale-dependent.
    slide1_name, slide2_name = (s["name"] for s in r["result"]["slides"])

    def add_shape(container, text=None):
        r = http_post("/tools/insert_shape_live", {
            "shape_type": "rectangle", "container": container,
            "position": {"x": 1000, "y": 1000}, "size": {"width": 3000, "height": 3000},
        })
        if not r.get("success"):
            fail(f"insert_shape_live failed: {r}")
        shape_id = r["result"]["shape_id"]
        if text is not None:
            r = http_post("/tools/set_shape_text_live", {"shape_id": shape_id, "text": text})
            if not r.get("success"):
                fail(f"set_shape_text_live failed: {r}")
        return shape_id

    add_shape(slide1_name, text="Quarterly Revenue Summary")
    add_shape(slide1_name)  # empty shape -- must contribute nothing
    add_shape(slide2_name, text="Quarterly Revenue Summary")  # same text, other slide

    print("\n[5/5] find_shape_text_live checks against real data")

    r = http_post("/tools/find_shape_text_live", {"query": "Revenue"})
    check("omitted container searches every slide (finds both slides' matching shape)",
          r.get("success") and {m["container"] for m in r["result"]["matches"]} >= {slide1_name, slide2_name})
    check("count matches the number of matching shapes (2), not the total shape count (3)",
          r["result"]["count"] == 2)

    r = http_post("/tools/find_shape_text_live", {"query": "Revenue", "container": slide2_name})
    check("container scopes the search to just that slide",
          r.get("success") and r["result"]["count"] == 1 and r["result"]["matches"][0]["container"] == slide2_name)

    r = http_post("/tools/find_shape_text_live", {"query": "nonexistent-xyz-query"})
    check("empty shape and non-matching text contribute nothing: no matches anywhere",
          r.get("success") and r["result"]["count"] == 0 and r["result"]["matches"] == [])

    r = http_post("/tools/find_shape_text_live", {"query": "revenue", "match": "exact", "container": slide1_name})
    check("match=exact, case-insensitive: 'revenue' does NOT exact-match the full title text",
          r.get("success") and r["result"]["count"] == 0)
    r = http_post("/tools/find_shape_text_live", {
        "query": "quarterly revenue summary", "match": "exact", "container": slide1_name,
    })
    check("match=exact, case-insensitive: full lowercase text exact-matches the real (Title Case) text",
          r.get("success") and r["result"]["count"] == 1)

    r = http_post("/tools/find_shape_text_live", {"query": "^Quarterly.*Summary$", "match": "regex"})
    check("match=regex finds both slides' shapes",
          r.get("success") and r["result"]["count"] == 2)
    r = http_post("/tools/find_shape_text_live", {"query": "[", "match": "regex"})
    check("invalid regex reports INVALID_PARAMETER, not a raw traceback",
          r.get("success") is False and r["error"]["code"] == "INVALID_PARAMETER")

    r = http_post("/tools/find_shape_text_live", {"query": "Revenue", "max_results": 1})
    check("max_results caps the match count and reports truncated=true",
          r.get("success") and r["result"]["count"] == 1 and r["result"]["truncated"] is True)

    r = http_post("/tools/find_shape_text_live", {"query": "Revenue", "container": slide1_name})
    check("shape_id round-trips through the ObjectRegistry (resolvable by get_shape_live)",
          r.get("success") and http_post(
              "/tools/get_shape_live", {"shape_id": r["result"]["matches"][0]["shape_id"]},
          ).get("success"))

    kill_soffice()
    run([str(UNOPKG_EXE), "remove", EXTENSION_ID])
    if soffice_log.exists():
        soffice_log.unlink()
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)

    print("\nPASS: all find_shape_text_live checks passed against real headless LibreOffice.")
    sys.exit(0)


if __name__ == "__main__":
    main()
