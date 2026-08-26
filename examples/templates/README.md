# Book layout templates

Two complete book-layout templates, built as live artifacts through the
actual MCP tool surface against a real headless LibreOffice instance --
not written from a spec and not hand-edited afterward. Assigned by Brian
2026-08-25 as a test of the tools themselves, not just a content
deliverable: "test the MCP tools by actually building two complete, real
book-layout templates as live artifacts."

Both documents were driven entirely through `POST /tools/<name>` calls
against the embedded MCP HTTP server (localhost:8765), same mechanism
this repo's own root-level `*-probe-windows.py` live-verification
scripts use. The build scripts that produced them are checked in at
`.buildscripts/build_nonfiction.py` / `.buildscripts/build_fiction.py`
(gitignored from the shipped extension, kept here as the record of
which tool call produced which requirement -- see the table below).

## 8x10-nonfiction-for-dummies-style/

"For Dummies"-style nonfiction: title page, copyright page, TOC,
chapter openers with a distinct sans-serif heading style, section
headings, a callout/sidebar box, running headers/footers, mirrored
margins, sans-serif headings (Verdana) + serif body (Georgia), a bold
gold/amber accent color, back matter (Glossary/Index placeholders).

## 6x9-fiction-narrative/

Classic narrative fiction: title page, copyright page, TOC (chapter
list), chapter headings, a scene break, a blockquote-style epigraph,
mirrored margins for print binding, restrained black/white + one
burgundy accent, back matter (About the Author placeholder).

## Requirement -> tool mapping

| Requirement | Tool(s) driven |
|---|---|
| Trim size (8x10 / 6x9) | `set_page_layout_live` (nonfiction, explicit width/height) / `apply_page_preset_live("novel_6x9", ...)` (fiction) |
| Mirrored margins | `set_page_layout_live(mirrored=True, gutter=...)` -- real UNO `PageStyleLayout=MIRRORED`, not simulated |
| Title/copyright/front-matter page styles | `create_page_style_live`, `apply_page_style_live` |
| Roman-numeral front matter, Arabic body numbering | `create_page_style_live(properties={"NumberingType": ...})` |
| Heading/body/callout fonts + colors | `create_style_live` (ParagraphStyles), `CharFontName`/`CharColor`/`CharWeight` |
| Table of contents | `insert_toc_live`, refreshed at the end with `update_index_live` once real chapter headings existed |
| Running headers/footers | `set_header_live` / `set_footer_live` (variants: `default`, `left`) |
| Page numbers in the footer | `insert_page_number_field_live(target="footer")` |
| Callout/sidebar box (nonfiction) | `insert_shape_live` (rectangle), `set_shape_text_live`, `format_shape_text_live` |
| Blockquote epigraph, scene break (fiction) | Dedicated paragraph styles (`FIC-Epigraph`, `FIC-SceneBreak`) via `create_style_live` + `append_paragraph_live` |
| Back matter placeholders | Plain headed paragraphs, `create_style_live`/`append_paragraph_live` |
| Export | `save_as_document_live` (.odt), `convert_document_live` (.pdf) |

## Real gaps and bugs found (live-verified, not assumed)

### 1. Mirrored/alternating running headers do not actually work

**This is the requirement Brian specifically called out as a likely gap
("can't do true per-side mirrored margins") -- confirmed, but the
actual break is in headers/footers, not the margins themselves.**

`set_header_live(text=X, variant="left")` followed by
`set_header_live(text=Y, variant="default")` (or the reverse order)
reports `"applied": ["text"]` -- success -- for both calls, and
LibreOffice's own `HeaderIsShared` page-style property defaults to
`True`, which collapses the "left" (verso) variant's displayed content
into the "default" (recto) variant's regardless of what was written to
each. Setting `HeaderIsShared: False` via `update_page_style_live` (an
undocumented-for-this-purpose property -- see gap #2) before writing
either variant does **not** fix it either: isolated repro (a scratch
page style, `HeaderIsShared: False` set at creation, then
`set_header_live(variant="left")` immediately followed by
`set_header_live(variant="default")`) still collapsed to the same text
for both. Confirmed at three independent layers, not just the tool's
own success response:

1. `get_headers_footers_live` reads back `header_left == header_default`.
2. The raw saved `.odt`'s `styles.xml` shows `<style:header-left>` and
   `<style:header>` containing the identical string for the same page
   style (`Chapter 1: Getting Started` on both, in
   `8x10-nonfiction-for-dummies-style/template.odt`).
3. Reproduced in complete isolation on a scratch page style outside
   either template's own styles, ruling out any cross-call ordering
   issue specific to the build scripts.

**Practical effect on the shipped templates:** the running headers in
both `template.odt`/`template.pdf` files show the recto (chapter
title) text on every page, not alternating with the book title on
verso pages, despite the build scripts explicitly attempting both. Not
silently worked around -- flagged here per Brian's instruction.

### 2. `get_page_layout_live` doesn't return what its own purpose string promises

The tool's registered purpose is "Return active page style, paper
size, orientation, margins, **mirrored layout**, columns,
**header/footer settings**." In practice `_WRITER_PAGE_LAYOUT_PROPS`
(`plugin/pythonpath/uno_bridge.py`) only includes `Width`, `Height`,
`IsLandscape`, the four margins, `GutterMargin`, `HeaderIsOn`,
`FooterIsOn`, `HeaderHeight`, `FooterHeight` -- it never reads back
`PageStyleLayout` (the actual mirrored-margins flag `set_page_layout_
live(mirrored=...)` writes) or `HeaderIsShared`/`FooterIsShared` (the
property gap #1 depends on). `get_style_live(family="PageStyles", ...)`
doesn't fill the gap either -- for `PageStyles` it only returns
`name`/`parent_style`/`is_user_defined`/`is_in_use`, no property dump.
**There is currently no tool that can read back whether a page style
is actually mirrored, or whether its headers/footers are actually
independent per page side** -- a caller can write these settings
blind and only discover whether they took by exporting and inspecting
the file directly, the way this report had to.

### 3. Struct-typed paragraph-style properties are silently dropped

`create_style_live`/`update_style_live` pass their `properties` dict
straight to UNO's `setPropertyValue` per key
(`_apply_direct_properties`, best-effort, catches and silently skips
anything UNO rejects). This works fine for scalar properties
(`CharColor`, `CharHeight`, `CharFontName`, `ParaFirstLineIndent`,
...) but **any UNO property whose type is a struct rather than a
scalar -- confirmed for `ParaLineSpacing` (`com.sun.star.style.
LineSpacing`) -- is silently rejected** every time, because a plain
JSON object (`{"Mode": 0, "Height": 130}`) is not a real
`uno.createUnoStruct(...)` instance and `setPropertyValue` refuses it
without raising. The tool reports success and lists every other
requested property as applied; the struct-typed one just quietly
isn't in the `applied_properties` list, discoverable only by diffing
against what was requested (which is how this was caught -- neither
template's body-text line-spacing (`BM-Body`/`FIC-Body`) actually
applied the requested `ParaLineSpacing`). Likely affects any other
struct-typed style property (e.g. `TabStops`, `DropCapFormat`) the
same way, not verified individually here.

### 4. No dynamic "current chapter" field for running headers

There's no UNO `TextField.Chapter`-equivalent exposed anywhere in the
tool surface (checked `insert_document_property_field_live` and the
whole field-insertion surface in `writer_layout.py`) -- a running
header that's supposed to show "whatever chapter this page is in"
without the caller manually re-setting it per chapter isn't possible.
Both templates work around this the only way available: one page
style per chapter (`BM-Chapter1`/`BM-Chapter2`,
`FIC-Chapter1`/`FIC-Chapter2`), each with its own static header text,
switched via `apply_page_style_live` at each chapter boundary. Fine
for a two-chapter template; a caller building a full-length book would
need one page style per chapter, which is a real scaling cost worth
knowing about up front rather than discovering at chapter 30.

## Verification performed

- Both build scripts ran end to end against real headless LibreOffice
  with zero tool-call failures (`.buildscripts/build_nonfiction.py`:
  28 paragraphs, 10 paragraph styles, 4 page styles, 1 TOC, 1 shape;
  `.buildscripts/build_fiction.py`: 23 paragraphs, 9 paragraph styles,
  4 page styles, 1 TOC).
- Document structure spot-checked via `extract_document_text_live`
  against the live document (front matter, chapter headings, section
  headings, callout, epigraph, scene break, back matter all present
  and in the right order).
- The four gaps above were each independently confirmed live (isolated
  repro calls against the running server), not inferred from reading
  the source.
- **Not done:** pixel-level visual rendering of the exported PDFs --
  this environment has no `pdftoppm`/ImageMagick/Ghostscript
  available, so page-by-page visual confirmation of margins/colors as
  actually rendered wasn't possible here. The `.odt`/`.pdf` files are
  checked in for a human (or an environment with a PDF renderer) to
  eyeball directly.
