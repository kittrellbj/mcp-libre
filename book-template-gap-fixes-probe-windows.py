"""
Live-verification probe for the 4 book-template tool gaps Buddy assigned
Sabrina 2026-08-26 (channel mcp-libre-2.0):

1. Mirrored/alternating header text (set_header_live/set_footer_live
   left/first variants silently collapsing to "default").
2. get_page_layout_live missing mirroring/header-share fields.
3. Struct-typed style properties (ParaLineSpacing) silently dropped on
   create_style_live/update_style_live/set_paragraph_format_live.
4. No dynamic "current chapter" header field (insert_chapter_field_live).

Mirrors the repo's own *-probe-windows.py idiom (bootstrap, http_post/get,
wait_for, check) -- see find-cells-probe-windows.py.

Usage: python book-template-gap-fixes-probe-windows.py
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


def call(tool_name, **kwargs):
    """POST /tools/<tool_name>, return the FULL envelope (success, result,
    warnings, ...) -- unlike .buildscripts/client.py's call(), which
    unwraps to just `result`, several checks below need `warnings` too."""
    envelope = http_post(f"/tools/{tool_name}", kwargs)
    if not envelope.get("success", False):
        fail(f"{tool_name}({kwargs}) failed: {json.dumps(envelope, indent=2)}")
    return envelope


def main():
    print("book-template gap fixes live-verification probe")
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

    print("\n[3/6] Launch headless LibreOffice (Writer), dispatch mcp:start_mcp_server")
    kill_soffice()
    accept = f"socket,host=localhost,port={UNO_PORT};urp;"
    soffice_log = REPO_DIR / "book-template-gap-fixes-probe-soffice.log"
    with open(soffice_log, "w") as log_file:
        subprocess.Popen(
            [str(SOFFICE_EXE), "--headless", f"--accept={accept}", "--norestore"],
            stdout=log_file, stderr=subprocess.STDOUT,
        )
    bootstrap_path = REPO_DIR / "book-template-gap-fixes-probe-bootstrap.py"
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

    # ------------------------------------------------------------------
    print("\n[4/6] Gap #1/#2: mirrored headers + get_page_layout_live fields")
    call("create_page_style_live", style_name="GapTest")
    call("apply_page_style_live", style_name="GapTest", paragraph=1)

    layout = call("get_page_layout_live", page_style="GapTest")["result"]
    for field in ("PageStyleLayout", "HeaderIsShared", "FooterIsShared", "FirstIsShared"):
        check(f"get_page_layout_live returns {field}", field in layout)
    print(f"  (info) new page style HeaderIsShared/FooterIsShared/FirstIsShared before any set_header_live call: "
          f"{layout['HeaderIsShared']!r}/{layout['FooterIsShared']!r}/{layout['FirstIsShared']!r}")

    call("set_header_live", text="RIGHT PAGE TEXT", page_style="GapTest", variant="default")
    call("set_header_live", text="LEFT PAGE TEXT", page_style="GapTest", variant="left")
    call("set_header_live", text="FIRST PAGE TEXT", page_style="GapTest", variant="first")
    hf = call("get_headers_footers_live", page_style="GapTest")["result"]
    check("header_default == 'RIGHT PAGE TEXT'", hf["header_default"] == "RIGHT PAGE TEXT")
    check("header_left == 'LEFT PAGE TEXT' (not collapsed to default)", hf["header_left"] == "LEFT PAGE TEXT")
    check("header_first == 'FIRST PAGE TEXT' (not collapsed to default)", hf["header_first"] == "FIRST PAGE TEXT")
    check("header_left != header_default", hf["header_left"] != hf["header_default"])
    check("header_first != header_default", hf["header_first"] != hf["header_default"])
    check("get_headers_footers_live reports header_left_shared == False", hf.get("header_left_shared") is False)
    check("get_headers_footers_live reports header_first_shared == False", hf.get("header_first_shared") is False)

    layout_after = call("get_page_layout_live", page_style="GapTest")["result"]
    check("get_page_layout_live now reports HeaderIsShared == False", layout_after["HeaderIsShared"] is False)
    check("get_page_layout_live now reports FirstIsShared == False", layout_after["FirstIsShared"] is False)

    call("set_footer_live", text="RIGHT FOOTER", page_style="GapTest", variant="default")
    call("set_footer_live", text="LEFT FOOTER", page_style="GapTest", variant="left")
    hf2 = call("get_headers_footers_live", page_style="GapTest")["result"]
    check("footer_left != footer_default", hf2["footer_left"] != hf2["footer_default"])
    check("footer_left_shared == False", hf2.get("footer_left_shared") is False)

    call("set_page_layout_live", width=6.0, height=9.0, unit="in", mirrored=True, page_style="GapTest")
    layout_mirrored = call("get_page_layout_live", page_style="GapTest")["result"]
    check("PageStyleLayout reads back as MIRRORED after set_page_layout_live(mirrored=True)",
          layout_mirrored["PageStyleLayout"] == "MIRRORED")

    # ------------------------------------------------------------------
    print("\n[5/6] Gap #3: struct-typed style property (ParaLineSpacing)")
    create_resp = call("create_style_live", family="ParagraphStyles", style_name="GapTestPara",
                        properties={"ParaLineSpacing": {"Mode": 0, "Height": 150}})
    check("create_style_live applied_properties includes ParaLineSpacing (not silently dropped)",
          "ParaLineSpacing" in create_resp["result"]["applied_properties"])
    check("create_style_live raised no warning about ParaLineSpacing", not create_resp["warnings"])

    update_resp = call("update_style_live", family="ParagraphStyles", style_name="GapTestPara",
                        properties={"ParaLineSpacing": {"Mode": 0, "Height": 250}})
    check("update_style_live applied includes ParaLineSpacing (not silently dropped)",
          "ParaLineSpacing" in update_resp["result"]["applied"])
    check("update_style_live raised no warning about ParaLineSpacing", not update_resp["warnings"])

    n = call("get_paragraph_count_live")["count"]
    call("insert_paragraph_live", text="Struct property probe paragraph", at_paragraph=n, position="after")
    fmt_resp = call("set_paragraph_format_live", properties={"ParaLineSpacing": {"Mode": 0, "Height": 175}})
    check("set_paragraph_format_live applied ParaLineSpacing on a real text range",
          "ParaLineSpacing" in fmt_resp["result"]["applied"])
    check("set_paragraph_format_live raised no warning about ParaLineSpacing", not fmt_resp["warnings"])

    # ------------------------------------------------------------------
    print("\n[6/6] Gap #4: dynamic current-chapter header field")
    # A fresh, unmutated page style -- deliberately NOT "GapTest", whose
    # FirstIsShared=False (set in gap #1/#2 above) would make this single-page
    # document render HeaderTextFirst instead of HeaderText on its only page,
    # so a field placed in the "default" header would never get laid out
    # (confirmed live: that's a real LibreOffice sharing rule, not a bug in
    # insert_chapter_field_live -- isolating the page style avoids conflating
    # the two tests).
    call("create_page_style_live", style_name="ChapterFieldTest")
    call("apply_page_style_live", style_name="ChapterFieldTest", paragraph=1)
    n2 = call("get_paragraph_count_live")["count"]
    call("insert_heading_live", text="Chapter One", level=1, at_paragraph=n2, position="after")
    call("set_header_live", text="placeholder ", page_style="ChapterFieldTest", variant="default")
    field_resp = call("insert_chapter_field_live", target="header", level=1, format="name")
    check("insert_chapter_field_live reports level=1", field_resp["result"]["level"] == 1)
    check("insert_chapter_field_live reports format='name'", field_resp["result"]["format"] == "name")
    call("update_fields_live")
    hf3 = call("get_headers_footers_live", page_style="ChapterFieldTest")["result"]
    check("header_default now shows the chapter field's live text ('Chapter One')",
          "Chapter One" in (hf3["header_default"] or ""))

    fields = call("list_fields_live")["result"]
    chapter_fields = [f for f in fields["fields"] if "Chapter" in json.dumps(f)]
    check("list_fields_live sees the inserted Chapter field", len(chapter_fields) >= 1)

    # Every real ChapterFormat constant-group member should resolve without
    # raising (regression check for the NUMBER_NAME/NO_CHAPTER guessed-wrong-
    # name bug found live-verifying this tool -- see _CHAPTER_FORMAT_MAP).
    # DANGER (live-verified, see insert_chapter_field's own docstring): two
    # Chapter fields landing adjacent to each other (e.g. repeat calls at an
    # unmoved cursor) can send LibreOffice's field expansion into a runaway
    # loop that hangs the whole process. Each format value below gets its
    # own fresh page style + header, never adjacent to another Chapter field.
    for i, fmt in enumerate(("name", "number", "name_number", "no_prefix_suffix", "digit")):
        style_name = f"ChapterFormatTest{i}"
        pn = call("get_paragraph_count_live")["count"]
        call("insert_paragraph_live", text=f"format test {i}", at_paragraph=pn, position="after")
        call("create_page_style_live", style_name=style_name)
        call("apply_page_style_live", style_name=style_name, paragraph=pn + 1)
        call("set_header_live", text="x", page_style=style_name, variant="default")
        call("insert_chapter_field_live", target="header", level=1, format=fmt)
    print("  all 5 ChapterFormat values (name/number/name_number/no_prefix_suffix/digit) resolved without error")

    print("\nPASS: all book-template gap fixes verified live.")

    print("\n[cleanup] Uninstall extension, kill soffice")
    kill_soffice()
    run([str(UNOPKG_EXE), "remove", EXTENSION_ID])


if __name__ == "__main__":
    main()
