"""Builds the 6x9 fiction (narrative-format) book-layout template live
through the running MCP server (localhost:8765) -- real tool calls
against a real headless LibreOffice document, not a written spec.

Run against a freshly created blank Writer document (create_document_live
called before this script, same as build_nonfiction.py's convention).
Saves .odt + .pdf into examples/templates/ at the end.
"""

import sys
sys.path.insert(0, ".buildscripts")
import client  # noqa: E402
from client import call, gap, step  # noqa: E402

ACCENT = 0x7A1F2B       # restrained deep burgundy -- the one accent color
INK = 0x1A1A1A
SERIF = "Georgia"       # classic narrative serif, used throughout (restrained typography)

CH1_PARA_1 = (
    "The letter arrived on a Tuesday, which Mara would later decide was "
    "exactly the kind of day a letter like that should arrive -- ordinary "
    "enough that she almost didn't notice the return address until she was "
    "halfway through slitting the envelope open with a butter knife."
)
CH1_PARA_2 = (
    "She read it twice standing at the kitchen counter, then a third time "
    "sitting down, because some sentences only make sense once you've "
    "stopped expecting the floor to hold still under you."
)
CH2_PARA_1 = (
    "By the time the train pulled out of the station, she had rehearsed "
    "the conversation four different ways and liked none of them."
)


def start_new_page(page_style, style_name=None):
    call("append_paragraph_live", text="", style_name=style_name)
    n = call("get_paragraph_count_live")["count"]
    call("apply_page_style_live", style_name=page_style, paragraph=n, insert_break=True)
    return n


def set_and_style(n, text, style_name):
    call("set_paragraph_text_live", n=n, text=text)
    call("select_paragraph_live", n=n)
    call("apply_style_live", family="ParagraphStyles", style_name=style_name, target=None)


# ---------------------------------------------------------------------
step("1. Page size (6x9 trim preset) + mirrored margins for print binding")
preset = call("apply_page_preset_live", preset="novel_6x9",
              overrides={"margins": {"left": 0.85, "right": 0.6, "top": 0.75, "bottom": 0.75},
                         "mirrored": True, "gutter": 0.1})
print(f"  preset applied: {preset}")

# ---------------------------------------------------------------------
step("2. Paragraph styles: restrained serif throughout, one accent color")
for name, props in [
    ("FIC-Title", {"CharFontName": SERIF, "CharHeight": 30.0, "CharWeight": 150.0,
                    "CharColor": INK, "ParaAdjust": 1, "ParaTopMargin": 2500}),
    ("FIC-TitleAuthor", {"CharFontName": SERIF, "CharHeight": 14.0, "CharPosture": 2,
                          "CharColor": ACCENT, "ParaAdjust": 1, "ParaTopMargin": 2000}),
    ("FIC-CopyrightText", {"CharFontName": SERIF, "CharHeight": 9.0, "CharColor": INK, "ParaBottomMargin": 200}),
    ("FIC-ChapterNumber", {"CharFontName": SERIF, "CharHeight": 13.0, "CharColor": ACCENT,
                            "CharCaseMap": 1, "ParaAdjust": 3, "ParaTopMargin": 1200}),
    ("FIC-ChapterTitle", {"CharFontName": SERIF, "CharHeight": 22.0, "CharWeight": 150.0,
                           "CharColor": INK, "ParaAdjust": 3, "ParaBottomMargin": 700}),
    ("FIC-Body", {"CharFontName": SERIF, "CharHeight": 11.5, "CharColor": INK,
                   "ParaFirstLineIndent": 300, "ParaLineSpacing": {"Mode": 0, "Height": 140}}),
    ("FIC-SceneBreak", {"CharFontName": SERIF, "CharHeight": 12.0, "CharColor": ACCENT,
                         "ParaAdjust": 3, "ParaTopMargin": 300, "ParaBottomMargin": 300}),
    ("FIC-Epigraph", {"CharFontName": SERIF, "CharHeight": 10.5, "CharPosture": 2, "CharColor": INK,
                       "ParaLeftMargin": 900, "ParaRightMargin": 900, "ParaAdjust": 1}),
    ("FIC-BackMatterHeading", {"CharFontName": SERIF, "CharHeight": 18.0, "CharWeight": 150.0, "CharColor": INK}),
]:
    r = call("create_style_live", family="ParagraphStyles", style_name=name, parent_style="Standard", properties=props)
    if r.get("applied_properties") and set(props) - set(r["applied_properties"]):
        gap(f"Some properties silently ignored on {name}", f"requested={sorted(props)} applied={sorted(r['applied_properties'])}")
print("  9 paragraph styles created")

# ---------------------------------------------------------------------
step("3. Page styles: Title, FrontMatter (roman numerals), per-chapter Body")
call("create_page_style_live", style_name="FIC-Title", based_on="Standard",
     properties={"HeaderIsOn": False, "FooterIsOn": False})
call("create_page_style_live", style_name="FIC-FrontMatter", based_on="Standard",
     properties={"HeaderIsOn": False, "NumberingType": 4})  # ROMAN_LOWER
call("create_page_style_live", style_name="FIC-Chapter1", based_on="Standard",
     properties={"HeaderIsShared": False, "FooterIsShared": False, "NumberingType": 0})  # ARABIC -- lesson from nonfiction build
call("create_page_style_live", style_name="FIC-Chapter2", based_on="Standard",
     properties={"HeaderIsShared": False, "FooterIsShared": False, "NumberingType": 0})
print("  4 page styles created")

# ---------------------------------------------------------------------
step("4. Title page")
set_and_style(1, "The Long Way Around", "FIC-Title")
call("apply_page_style_live", style_name="FIC-Title", paragraph=1)
call("append_paragraph_live", text="a novel", style_name="FIC-TitleAuthor")
call("append_paragraph_live", text="Sample Author", style_name="FIC-TitleAuthor")
n = call("get_paragraph_count_live")["count"]
print(f"  title page done, paragraph count={n}")

# ---------------------------------------------------------------------
step("5. Copyright page")
n = start_new_page("FIC-FrontMatter")
set_and_style(n, "This is a work of fiction. Names, characters, places, and incidents "
                 "either are the product of the author's imagination or are used "
                 "fictitiously.", "FIC-CopyrightText")
for line in [
    "Copyright © 2026 Sample Author. All rights reserved.",
    "No part of this book may be reproduced in any form without written "
    "permission from the publisher, except for brief quotations in a review.",
    "Published by Sample Fiction Press.",
    "First edition.",
]:
    call("append_paragraph_live", text=line, style_name="FIC-CopyrightText")
n = call("get_paragraph_count_live")["count"]
print(f"  copyright page done, paragraph count={n}")

# ---------------------------------------------------------------------
step("6. Table of contents (chapter list)")
n = start_new_page("FIC-FrontMatter")
toc = call("insert_toc_live", at_position=n, title="Contents")
print(f"  TOC inserted: {toc}")
n = call("get_paragraph_count_live")["count"]

# ---------------------------------------------------------------------
step("7. Chapter 1 -- with epigraph, scene break, mirrored running headers")
n = start_new_page("FIC-Chapter1")
call("set_header_live", text="The Long Way Around", page_style="FIC-Chapter1", variant="left")
call("set_header_live", text="Chapter One", page_style="FIC-Chapter1", variant="default")
call("set_footer_live", text="", page_style="FIC-Chapter1", variant="left")
call("set_footer_live", text="", page_style="FIC-Chapter1", variant="default")
call("insert_page_number_field_live", target="footer", format="arabic")
hf1 = call("get_headers_footers_live", page_style="FIC-Chapter1")
print(f"  FIC-Chapter1 headers distinct={hf1.get('header_left') != hf1.get('header_default')} "
      f"(left={hf1.get('header_left')!r}, default={hf1.get('header_default')!r})")

set_and_style(n, "ONE", "FIC-ChapterNumber")
call("append_paragraph_live", text="The Letter", style_name="FIC-ChapterTitle")
call("append_paragraph_live",
     text="“Not all those who wander are lost.” — an epigraph, for example",
     style_name="FIC-Epigraph")
call("append_paragraph_live", text=CH1_PARA_1, style_name="FIC-Body")
call("append_paragraph_live", text=CH1_PARA_2, style_name="FIC-Body")
call("append_paragraph_live", text="•  •  •", style_name="FIC-SceneBreak")
call("append_paragraph_live", text=CH1_PARA_1, style_name="FIC-Body")
n = call("get_paragraph_count_live")["count"]
print(f"  chapter 1 done, paragraph count={n}")

# ---------------------------------------------------------------------
step("8. Chapter 2")
n = start_new_page("FIC-Chapter2")
call("set_header_live", text="The Long Way Around", page_style="FIC-Chapter2", variant="left")
call("set_header_live", text="Chapter Two", page_style="FIC-Chapter2", variant="default")
call("set_footer_live", text="", page_style="FIC-Chapter2", variant="left")
call("set_footer_live", text="", page_style="FIC-Chapter2", variant="default")
call("insert_page_number_field_live", target="footer", format="arabic")

set_and_style(n, "TWO", "FIC-ChapterNumber")
call("append_paragraph_live", text="The Platform", style_name="FIC-ChapterTitle")
call("append_paragraph_live", text=CH2_PARA_1, style_name="FIC-Body")
call("append_paragraph_live", text=CH1_PARA_2, style_name="FIC-Body")
n = call("get_paragraph_count_live")["count"]
print(f"  chapter 2 done, paragraph count={n}")

# ---------------------------------------------------------------------
step("9. Back matter: About the Author placeholder")
n = start_new_page("FIC-FrontMatter")
set_and_style(n, "About the Author", "FIC-BackMatterHeading")
call("append_paragraph_live", text="[Placeholder -- author bio goes here.]", style_name="FIC-Body")
n = call("get_paragraph_count_live")["count"]
print(f"  back matter done, paragraph count={n}")

# ---------------------------------------------------------------------
step("10. Refresh TOC now that real chapter headings exist")
indexes = call("list_document_indexes_live")
print(f"  document indexes: {indexes}")
if indexes.get("indexes"):
    toc_id = indexes["indexes"][0]["index_id"]
    updated = call("update_index_live", index_id=toc_id)
    print(f"  TOC refreshed: {updated}")

print(f"\nGAPS FOUND: {len(client.GAPS)}")
for title, detail in client.GAPS:
    print(f"  - {title}")

print("\nFiction build complete.")
