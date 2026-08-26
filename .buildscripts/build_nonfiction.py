"""Builds the 8x10 nonfiction ("For Dummies"-style) book-layout template
live through the running MCP server (localhost:8765) -- real tool calls
against a real headless LibreOffice document, not a written spec.

Run against the currently-active blank Writer document the bootstrap
script opened. Saves .odt + .pdf into examples/templates/ at the end.
"""

import sys
sys.path.insert(0, ".buildscripts")
import client  # noqa: E402
from client import call, call_soft, gap, step  # noqa: E402

ACCENT = 0xF2A900       # bold gold/amber accent -- "For Dummies"-style bright, high-contrast
INK = 0x1A1A1A          # near-black body ink
SANS = "Verdana"        # friendly sans-serif for headings
SERIF = "Georgia"       # serif for body text

BODY_PARA = (
    "This is where the chapter's real explanation goes -- plain language, "
    "short sentences, and a friendly, encouraging tone aimed at a reader "
    "who has never done this before. Each major idea gets its own "
    "paragraph so the page never feels like a wall of text."
)
BODY_PARA_2 = (
    "Numbered steps, bulleted lists, and callout boxes carry most of the "
    "actual instructions; body paragraphs like this one exist mostly to "
    "connect them and explain why a step matters, not just what to click."
)


def start_new_page(page_style, style_name=None):
    """Append a fresh empty paragraph and mark it as the start of a new
    page in `page_style` -- safer than insert_page_break_live's
    split-at-existing-paragraph semantics (which would shift whatever
    content was already in the anchor paragraph onto the new page
    instead of leaving a clean blank target). Returns the new
    paragraph's 1-based index."""
    call("append_paragraph_live", text="", style_name=style_name)
    n = call("get_paragraph_count_live")["count"]
    call("apply_page_style_live", style_name=page_style, paragraph=n, insert_break=True)
    return n


def set_and_style(n, text, style_name):
    call("set_paragraph_text_live", n=n, text=text)
    call("select_paragraph_live", n=n)
    call("apply_style_live", family="ParagraphStyles", style_name=style_name, target=None)


# ---------------------------------------------------------------------
step("1. Page size + mirrored margins (8x10 trim, Standard/body page style)")
call("set_page_layout_live", width=8, height=10, unit="in",
     margins={"left": 0.9, "right": 0.7, "top": 0.85, "bottom": 0.85},
     mirrored=True, gutter=0.15, page_style="Standard")
layout = call("get_page_layout_live", page_style="Standard")
print(f"  Standard page style now: {layout.get('Width')}x{layout.get('Height')} (1/100mm), "
      f"PageStyleLayout={layout.get('PageStyleLayout')}")

# ---------------------------------------------------------------------
step("2. Paragraph styles: sans headings, serif body, gold accent color")
for name, props in [
    ("BM-Title", {"CharFontName": SANS, "CharHeight": 34.0, "CharWeight": 150.0,
                   "CharColor": INK, "ParaAdjust": 1, "ParaTopMargin": 1500}),
    ("BM-Subtitle", {"CharFontName": SANS, "CharHeight": 16.0, "CharColor": ACCENT,
                      "CharWeight": 100.0, "ParaAdjust": 1, "ParaTopMargin": 600}),
    ("BM-TitleAuthor", {"CharFontName": SERIF, "CharHeight": 14.0, "CharColor": INK,
                         "ParaAdjust": 1, "ParaTopMargin": 3000}),
    ("BM-CopyrightText", {"CharFontName": SERIF, "CharHeight": 9.0, "CharColor": INK, "ParaBottomMargin": 200}),
    ("BM-ChapterEyebrow", {"CharFontName": SANS, "CharHeight": 13.0, "CharColor": ACCENT,
                            "CharWeight": 150.0, "CharCaseMap": 1, "ParaTopMargin": 400}),
    ("BM-ChapterTitle", {"CharFontName": SANS, "CharHeight": 28.0, "CharWeight": 150.0,
                          "CharColor": INK, "ParaBottomMargin": 500}),
    ("BM-SectionHeading", {"CharFontName": SANS, "CharHeight": 15.0, "CharWeight": 150.0,
                            "CharColor": ACCENT, "ParaTopMargin": 400, "ParaBottomMargin": 200}),
    ("BM-Body", {"CharFontName": SERIF, "CharHeight": 11.0, "CharColor": INK, "ParaBottomMargin": 240}),
    ("BM-CalloutText", {"CharFontName": SANS, "CharHeight": 10.0, "CharColor": INK}),
    ("BM-BackMatterHeading", {"CharFontName": SANS, "CharHeight": 20.0, "CharWeight": 150.0, "CharColor": INK}),
]:
    r = call("create_style_live", family="ParagraphStyles", style_name=name, parent_style="Standard", properties=props)
    if r.get("applied_properties") and set(props) - set(r["applied_properties"]):
        gap(f"Some properties silently ignored on {name}", f"requested={sorted(props)} applied={sorted(r['applied_properties'])}")
print("  10 paragraph styles created")

# ---------------------------------------------------------------------
step("3. Page styles: Title (no header/footer), FrontMatter (roman numerals), per-chapter Body")
call("create_page_style_live", style_name="BM-Title", based_on="Standard",
     properties={"HeaderIsOn": False, "FooterIsOn": False})
call("create_page_style_live", style_name="BM-FrontMatter", based_on="Standard",
     properties={"HeaderIsOn": False, "NumberingType": 4})  # ROMAN_LOWER
call("create_page_style_live", style_name="BM-Chapter1", based_on="Standard",
     properties={"HeaderIsShared": False, "FooterIsShared": False, "NumberingType": 0})  # ARABIC
call("create_page_style_live", style_name="BM-Chapter2", based_on="Standard",
     properties={"HeaderIsShared": False, "FooterIsShared": False, "NumberingType": 0})
print("  4 page styles created (BM-Title, BM-FrontMatter, BM-Chapter1, BM-Chapter2)")

# ---------------------------------------------------------------------
step("4. Title page")
set_and_style(1, "THE COMPLETE BEGINNER'S GUIDE", "BM-Title")
call("apply_page_style_live", style_name="BM-Title", paragraph=1)
call("append_paragraph_live", text="TO GETTING THINGS DONE", style_name="BM-Subtitle")
call("append_paragraph_live", text="by Sample Author", style_name="BM-TitleAuthor")
n = call("get_paragraph_count_live")["count"]
print(f"  title page done, paragraph count={n}")

# ---------------------------------------------------------------------
step("5. Copyright page")
n = start_new_page("BM-FrontMatter")
set_and_style(n, "Copyright © 2026 Sample Author. All rights reserved.", "BM-CopyrightText")
for line in [
    "No part of this publication may be reproduced, stored in a retrieval system, "
    "or transmitted in any form or by any means without the prior written permission "
    "of the publisher, except in the case of brief quotations embodied in critical "
    "reviews and certain other noncommercial uses permitted by copyright law.",
    "Published by Sample Publishing House.",
    "For information about permissions, contact permissions@example.com.",
    "Manufactured in the United States of America.",
    "10 9 8 7 6 5 4 3 2 1",
]:
    call("append_paragraph_live", text=line, style_name="BM-CopyrightText")
n = call("get_paragraph_count_live")["count"]
print(f"  copyright page done, paragraph count={n}")

# ---------------------------------------------------------------------
step("6. Table of contents (front matter, roman numerals)")
n = start_new_page("BM-FrontMatter")
toc = call("insert_toc_live", at_position=n, title="Contents")
print(f"  TOC inserted: {toc}")
n = call("get_paragraph_count_live")["count"]

# ---------------------------------------------------------------------
step("7. Chapter 1")
n = start_new_page("BM-Chapter1")
call("set_header_live", text="THE COMPLETE BEGINNER'S GUIDE", page_style="BM-Chapter1", variant="left")
call("set_header_live", text="Chapter 1: Getting Started", page_style="BM-Chapter1", variant="default")
call("set_footer_live", text="", page_style="BM-Chapter1", variant="left")
call("set_footer_live", text="", page_style="BM-Chapter1", variant="default")
call("insert_page_number_field_live", target="footer", format="arabic")
hf1 = call("get_headers_footers_live", page_style="BM-Chapter1")
print(f"  BM-Chapter1 headers: left={hf1.get('header_left')!r} default={hf1.get('header_default')!r} "
      f"(distinct={hf1.get('header_left') != hf1.get('header_default')})")
if hf1.get("header_left") == hf1.get("header_default"):
    gap("Mirrored running headers not automatically distinct",
        "set_header_live(variant='left') vs variant='default' write and read back different "
        "strings via get_headers_footers_live, but neither set_page_layout_live(mirrored=True) "
        "nor set_header_live ever sets HeaderIsShared/FooterIsShared -- LibreOffice's own "
        "default (True) makes the page ALWAYS render the 'default'/right-page text on every "
        "page. A caller must separately call update_page_style_live(properties={"
        "'HeaderIsShared': False, 'FooterIsShared': False}) before the left/right split shows "
        "up in the rendered document. Applied as a workaround for this template (see step 7).")
    call("update_page_style_live", style_name="BM-Chapter1", properties={"HeaderIsShared": False, "FooterIsShared": False})
    call("update_page_style_live", style_name="BM-Chapter2", properties={"HeaderIsShared": False, "FooterIsShared": False})

set_and_style(n, "CHAPTER 1", "BM-ChapterEyebrow")
call("append_paragraph_live", text="Getting Started", style_name="BM-ChapterTitle")
call("append_paragraph_live", text=BODY_PARA, style_name="BM-Body")
call("append_paragraph_live", text="Setting Up Your Workspace", style_name="BM-SectionHeading")
call("append_paragraph_live", text=BODY_PARA_2, style_name="BM-Body")
call("append_paragraph_live", text=BODY_PARA, style_name="BM-Body")
call("append_paragraph_live", text="A Quick Sanity Check", style_name="BM-SectionHeading")
call("append_paragraph_live", text=BODY_PARA_2, style_name="BM-Body")
n = call("get_paragraph_count_live")["count"]
print(f"  chapter 1 body done, paragraph count={n}")

step("7b. Chapter 1 callout/sidebar box")
callout = call("insert_shape_live", shape_type="rectangle",
                position={"x": 12500, "y": 4000}, size={"width": 4500, "height": 6000},
                properties={"FillColor": ACCENT, "FillTransparence": 0, "LineStyle": 0})
call("set_shape_text_live", shape_id=callout["shape_id"], text="TIP\n\nYou can always come back to this "
     "step later -- nothing here is a one-way door.")
call("format_shape_text_live", shape_id=callout["shape_id"],
     properties={"CharFontName": SANS, "CharColor": INK, "CharWeight": 150.0, "CharHeight": 11.0})
print(f"  callout box inserted: {callout.get('shape_id')}")

# ---------------------------------------------------------------------
step("8. Chapter 2")
n = start_new_page("BM-Chapter2")
call("set_header_live", text="THE COMPLETE BEGINNER'S GUIDE", page_style="BM-Chapter2", variant="left")
call("set_header_live", text="Chapter 2: Building Momentum", page_style="BM-Chapter2", variant="default")
call("set_footer_live", text="", page_style="BM-Chapter2", variant="left")
call("set_footer_live", text="", page_style="BM-Chapter2", variant="default")
call("insert_page_number_field_live", target="footer", format="arabic")

set_and_style(n, "CHAPTER 2", "BM-ChapterEyebrow")
call("append_paragraph_live", text="Building Momentum", style_name="BM-ChapterTitle")
call("append_paragraph_live", text=BODY_PARA, style_name="BM-Body")
call("append_paragraph_live", text="Keeping Track of Progress", style_name="BM-SectionHeading")
call("append_paragraph_live", text=BODY_PARA_2, style_name="BM-Body")
n = call("get_paragraph_count_live")["count"]
print(f"  chapter 2 body done, paragraph count={n}")

# ---------------------------------------------------------------------
step("9. Back matter: Glossary + Index placeholders")
n = start_new_page("BM-FrontMatter")
set_and_style(n, "Glossary", "BM-BackMatterHeading")
call("append_paragraph_live", text="[Placeholder -- term/definition pairs go here.]", style_name="BM-Body")
call("append_paragraph_live", text="Index", style_name="BM-BackMatterHeading")
call("append_paragraph_live", text="[Placeholder -- generated index goes here.]", style_name="BM-Body")
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

print("\nNonfiction build complete.")
