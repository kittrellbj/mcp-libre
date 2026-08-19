# MCP Tooling Scaffold Plan

Tracks scaffolding progress against `LibreOffice_MCP_Complete_Tooling_Specification.md`
(the design doc, kept one level up in `E:\Tools\` on the machine this fork
lives on -- not copied into this repo). That spec targets **484 tool
definitions**: 32 existing/baseline (P0), 218 core (P1), 193 extended (P2),
41 advanced (P3), across 19 catalog sections. This document is maintained
by the scaffolding pass so a later session (or a senior engineer) can pick
up exactly where it left off.

## Status

| Spec section | Tool rows | Existing (P0) | New this pass | Status |
|---|---|---|---|---|
| Core runtime, discovery, capability negotiation | 12 | 0 | 12 | **Implemented** (`tools/core_runtime.py`) -- real logic, live-verified |
| Document and session lifecycle | 27 | 5 | 22 | **Implemented** (`tools/document_lifecycle.py`) -- real logic, live-verified |
| Undo, view, selection, events, orchestration | 14 | 0 | 14 | **12/14 Implemented** (`tools/undo_view_selection.py`) -- real logic, live-verified; document-events (2 tools) still stub, separate pass |
| Styles and formatting infrastructure | 12 | 0 | 12 | **Implemented** (`tools/styles.py`) -- real logic, live-verified |
| Writer - text, navigation, editing, search, review | 45 | 27 | 18 | **18/18 new tools Implemented** (`tools/writer_text.py`) -- real logic, live-verified; the 27 "(existing)" tools stay in `mcp_server.py`/`uno_bridge.py` under the original 32, not duplicated here |
| Writer - page layout, publishing, styles, headers, fields, indexes | 43 | 0 | 43 | **42/43 Implemented** (`tools/writer_layout.py`) -- real logic, live-verified; `set_chapter_numbering_live` (P2) still stub -- `ChapterNumberingRules.replaceByIndex()` resists writes this build |
| Writer - tables, sections, notes, content controls, mail merge | 38 | 0 | 38 | **37/38 Implemented** (`tools/writer_tables.py`) -- real logic, live-verified; `mail_merge_live` (P3) still stub -- `preview_mail_merge_live` (the real data-connection half) IS real |
| Common drawing objects, images, shapes, embedded objects | 31 | 0 | 31 | **29/31 Implemented** (`tools/drawing_objects.py`) -- real logic, live-verified; only insert/activate_embedded_object (P3) still stub (uncertain OLE scope, not dispatch risk -- combine/split/bind/unbind re-enabled once the dispatch-safety finding was corrected) |
| Charts and data visualizations | 20 | 0 | 20 | **20/20 Implemented** (`tools/charts.py`) -- real logic, live-verified, Calc-native charts only |
| Calc - sheets, cells, ranges, formulas, layout | 42 | 0 | 42 | **42/42 Implemented** (`tools/calc_sheets.py`) -- real logic, live-verified |
| Calc - data management, analysis, pivots, validation, external data | 42 | 0 | 42 | **39/42 Implemented** (`tools/calc_data.py`) -- real logic, live-verified; create/refresh/delete_external_link (P2/P3) still stub -- no write-side ExternalDocLinks mechanism this pass |
| Calc - page setup, print ranges, annotations, protection | 15 | 0 | 15 | **15/15 Implemented** (`tools/calc_page.py`) -- real logic, live-verified |
| Impress - slides, masters, notes, transitions, animations, slideshow | 41 | 0 | 41 | **34/41 Implemented** (`tools/impress.py`) -- real logic, live-verified; 7 tools (animation mutation x4, live slideshow-effect control x3) still stub -- no XAnimationNode construction / no headless XSlideShowController this pass |
| Draw - pages, masters, layers, vector operations | 16 | 0 | 16 | **16/16 Implemented** (`tools/draw.py`) -- real logic, live-verified |
| Base and database access | 34 | 0 | 0 | Not started |
| Forms and controls | 16 | 0 | 0 | Not started |
| Math formula documents and embedded formulas | 7 | 0 | 0 | Not started |
| Linguistic services, accessibility, publishing QA | 15 | 0 | 0 | Not started |
| Security, scripts, events, advanced UNO escape hatch | 14 | 0 | 0 | Not started |
| **Total** | **484** | **32** | **366** | **366 / 452 net-new tools scaffolded** |

"Scaffolded" means: registered under the exact spec tool name with the
correct priority and a JSON Schema `parameters` block built from the
spec's Key Parameters column, with a docstring/purpose copied from the
spec's Purpose column, and a handler body that returns the standard
`NOT_IMPLEMENTED` error envelope. **No UNO logic has been written for any
of these 366 tools** -- that is deliberately left for a senior engineer.

This covers Implementation Phases A, B, C, and D from the spec's own section 10:

- **Phase A** ("Runtime hardening and common document API": discovery,
  handles, lifecycle, metadata, undo, batch execution, styles,
  export/print) -- picked first because every later phase's tools describe
  operations *on* a document, and Phase A is where the document-handle and
  response-envelope plumbing those operations depend on gets defined.
- **Phase B** ("Writer complete": page layout/publishing, tables,
  sections, fields, indexes, footnotes/endnotes, content controls,
  graphics -- graphics itself is the separate "Common drawing objects"
  section and is *not* included here, since it's shared with
  Calc/Impress/Draw rather than Writer-specific).
- **Phase C** (shared "Common drawing objects" and "Charts and data
  visualizations" sections Writer's own Phase B intentionally left out,
  plus Calc-complete: sheets/cells/ranges/formulas/layout, data
  management/pivots/validation/external data, and page setup/print/
  annotations/protection) -- see "## Phase C" below for detail.
- **Phase D** (Impress-complete: slides/masters/notes/transitions/
  animations/slideshow; Draw-complete: pages/masters/layers/vector
  operations) -- see "## Phase D" below for detail.

## Phase C

Phase C scaffolds the two sections shared across document types that
Writer's own Phase B deliberately excluded (`tools/drawing_objects.py`,
`tools/charts.py`), plus all three "Calc-complete" sections from the
spec (`tools/calc_sheets.py`, `tools/calc_data.py`, `tools/calc_page.py`)
-- 150 tool rows total, all P1-P3, all net-new (Calc/drawing/chart tools
have zero P0 overlap with the 32 existing Writer/lifecycle compat tools).
Same pattern as Phase A/B throughout: `@register_tool` from
`tools/registry.py`, JSON Schema `parameters` built from each row's Key
Parameters column, purpose copied verbatim from the spec's Purpose
column, and every handler body returning `envelope.build_not_implemented`
with no UNO calls. The five new modules are wired into
`plugin/pythonpath/tools/__init__.py` the same additive, side-effect-only
way as the Phase A/B modules, so they show up under the existing
`MCP_LIBRE_ENABLE_SCAFFOLD_STUBS` opt-in with no new wiring in
`mcp_server.py` itself. `tests/test_tool_scaffold_contract.py` gained one
more `EXPECTED_BY_MODULE` entry per new file (exact tool-name sets, same
style as the Phase A/B entries); the full contract suite now checks 309
registered tools by exact name across 12 modules.

## Phase D

Phase D scaffolds the two document-type-complete sections for Impress
(`tools/impress.py`, 41 rows: slide CRUD/layout/background, master pages,
speaker notes, transitions, animations, click actions, presentation/
slideshow settings, custom shows, slideshow playback control, slide/deck
image export) and Draw (`tools/draw.py`, 16 rows: page CRUD/size/
background, layers, shape-to-layer assignment, page/selection export) --
57 tool rows total, all P1-P3, all net-new (zero P0 overlap, same as
Phase C). Same `@register_tool`/`envelope.build_not_implemented` pattern
throughout; wired into `plugin/pythonpath/tools/__init__.py` the same
additive way as every prior phase, so no changes were needed in
`mcp_server.py` itself. `tests/test_tool_scaffold_contract.py` gained two
more `EXPECTED_BY_MODULE` entries (`impress`, `draw`); the full contract
suite now checks 366 registered tools by exact name across 14 modules.

## Real implementation pass: core runtime tools

Per direction to stop scaffolding and implement for real, all 12
`tools/core_runtime.py` tools now have real logic instead of stub bodies,
and are registered `status="implemented"` (see `registry.register_tool`'s
new `status` parameter) -- they're merged into `LibreOfficeMCPServer.tools`
unconditionally, like the original 32, not gated behind
`MCP_LIBRE_ENABLE_SCAFFOLD_STUBS` anymore. `get_registry(status=...)` and
`merge_into(..., registry=...)` let `mcp_server.py` merge "implemented"
and "stub" tools separately; the remaining scaffold tools are still
`status="stub"` and still gated by the env var exactly as before (see the
document-lifecycle pass below for the current stub/implemented split).

**New shared infrastructure this required:**

- `tools/runtime_state.py` -- `RuntimeState`: session id, tool-exposure
  profile, and a bounded (200-entry) error history. Pure Python, no UNO.
- `tools/context.py` -- `RuntimeContext`/`install()`/`get_context()`: a
  process-wide holder for the live `UNOBridge`, `DocumentRegistry`,
  `RuntimeState`, and a `get_tools()` callable, since `@register_tool`
  handlers are plain functions with no `self`. `mcp_server.py` installs
  this once in `LibreOfficeMCPServer.__init__`, right after constructing
  those three dependencies and before registering any tool.
- `mcp_server.py`: `DocumentRegistry` and `RuntimeState` are now actually
  constructed (previously `DocumentRegistry` was real code nothing ever
  instantiated in production). `execute_tool()` now calls
  `runtime_state.record_call()`/`record_error()` around every dispatch --
  not just core_runtime's own tools -- so `get_recent_errors_live`/
  `get_diagnostics_live` reflect real traffic across all 44 tools, not
  just the 12 that call runtime_state directly. (`batch_execute_live`
  calls handlers directly rather than through `execute_tool()`, so
  operations run inside a batch are not separately recorded in the error
  history -- a documented scope boundary, not a bug.)
- `uno_bridge.py` gained two new real methods: `get_application_version()`
  (queries `/org.openoffice.Setup/Product` via the UNO configuration
  provider -- live-verified to return the real running LibreOffice version,
  e.g. "26.2", not a guess) and `get_capabilities()` (reports which of the
  module's guarded optional-interface imports actually resolved on this
  build/platform).

**Known, documented scope limits** (not hidden, called out in
`core_runtime.py`'s module docstring and in code comments at each site):

- `list_tools_live`'s profile filtering is derived from which module a
  tool's handler was defined in (`handler.__module__`), not per-tool
  metadata -- accurate at module granularity; a module shared across
  document types (e.g. `drawing_objects.py`) is tagged with the union of
  types, not filtered tool-by-tool within itself.
- `validate_tool_call_live` implements a minimal JSON Schema subset
  (required-field presence, declared `type`, `enum` membership) -- not a
  general-purpose validator, but sufficient for every schema this package
  actually produces via `registry.schema()`.
- `batch_execute_live` accepts `undo_label` but returns a warning that
  named-undo-context grouping isn't implemented yet
  (`begin_undo_context_live`/`end_undo_context_live` are still stubs).
- `get_session_state_live`'s `registered_document_handles` reflects
  `DocumentRegistry`, which nothing populates yet (`open_document_live`,
  `create_document_live`, etc. are still stubs) -- `open_documents` is
  sourced from the live desktop frame list instead, live-verified to work
  correctly even when `registered_document_handles` is empty.

**Testing:** `tests/test_runtime_state.py` (11 tests, pure logic),
`tests/test_context.py` (4 tests), `tests/test_core_runtime.py` (29 tests,
using fakes for `UNOBridge` but the real `DocumentRegistry`/`RuntimeState`/
`context` -- exercises the actual integration path, not just isolated
logic). `tests/test_tool_scaffold_contract.py` gained
`test_every_tool_has_a_valid_status` and
`test_core_runtime_tools_are_marked_implemented`, and
`test_stub_shape_contract` now only iterates `status="stub"` tools.

**Live-verified, not just unit-tested with fakes:** built the `.oxt`
(catching and fixing a real bug in the process -- `build-oxt-windows.py`'s
file list never included `plugin/pythonpath/tools/` at all, so every
build since Phase A would have shipped a broken extension the moment
`mcp_server.py`'s `import tools` ran; now globs `tools/*.py` in rather
than hand-listing modules), installed it via `unopkg`, launched a real
headless `soffice.exe` with a UNO accept socket, dispatched
`mcp:start_mcp_server` through the actual `registration.py` dispatch path
(not a shortcut), and hit the live HTTP API with `curl`. Confirmed for
real: `GET /` reports `tools_count: 44` (32 original + 12 implemented);
`ping_live`, `get_server_info_live` (real LibreOffice version "26.2", real
Python version, real OS -- not placeholders), `get_capabilities_live`
(real per-build interface availability -- `XPresentationDocument` came
back `false` on this LibreOffice build, a genuine capability gap the
guarded-import pattern is designed to surface), `get_session_state_live`,
`list_tools_live`, `get_diagnostics_live`, `validate_tool_call_live`,
`batch_execute_live`, `get_recent_errors_live`, `clear_diagnostics_live`,
and `set_tool_profile_live` all behaved correctly against the live
extension. Also incidentally re-confirmed the earlier baseline-cleanup
security fix still works live: a request with `Host: evil.example.com`
got a real 403 from the running server. Cleaned up afterward (stopped the
MCP server via dispatch, terminated `soffice`, verified port 8765 was
released, removed scratch scripts and the local `build/` artifact).

## Real implementation pass: document lifecycle tools

All 22 new `tools/document_lifecycle.py` tools now have real logic too,
following the exact same pattern as core_runtime.py (`status="implemented"`,
always-on, `tools.context.get_context()`). This pass added ~20 new
`UNOBridge` methods (open/close/activate/save-as/save-copy/convert/
statistics/properties/custom-properties/modified-state/refresh/reload/
print/print-settings/list-filters) plus a small shared error-mapping
helper (`_map_exception_to_code`) so a raised `FileNotFoundError`/
`FileExistsError`/`ValueError`/`KeyError`/`NotImplementedError`/
`PermissionError` from a `UNOBridge` method (or `DocumentRegistry`) maps
onto the right spec error code without every tool body re-deriving it.

**Auto-registration closes a gap from the core-runtime pass:** every tool
that resolves "the active document" (`document_id` omitted) now registers
it into `DocumentRegistry` if it wasn't already there (`_resolve_and_register`),
so `get_session_state_live`'s `registered_document_handles` -- empty in
the core-runtime pass because nothing ever called `register_document()` --
now populates for real as documents get touched.

**`DocumentRegistry` gained `replace_document(document_id, new_document)`**
for `reload_document_live`: reloading closes the old UNO component and
loads a new one with a different object identity, but the caller should
keep using the same `document_id` afterward.

**Three real bugs found and fixed by live-verifying against actual
LibreOffice** (not just the fakes-based unit tests, which by construction
couldn't have caught any of these -- they don't model real PyUNO object
behavior):

1. **`build-oxt-windows.py` nearly shipped `uno_datetime.py` missing**,
   immediately after fixing the *first* instance of this bug class (the
   whole `tools/` package missing, found during the core-runtime pass).
   Root-caused it properly this time: replaced the hand-maintained file
   list with a glob over all of `pythonpath/*.py` (plus `tools/*.py`), so
   a new top-level module can never be silently left out of a build again.
2. **`get_document_properties_live` returned raw UNO struct reprs for
   dates** -- `str()` on a `com.sun.star.util.DateTime` produces
   `"(com.sun.star.util.DateTime){ NanoSeconds = ... }"`, not a readable
   date. Fixed by building an ISO-8601 string from the struct's own
   fields. Extracted to `uno_datetime.py` (mirroring the `host_trust.py`
   precedent) specifically so the conversion is unit-testable without a
   live UNO context -- `tests/test_uno_datetime.py`, 6 tests.
3. **`list_export_filters_live` returned an empty list.** Root cause:
   `FilterFactory.getByName(name)` returns a tuple of `PropertyValue`
   structs, not something `dict()` can convert directly -- `dict(entry)`
   was silently raising inside a bare `except: continue` for every single
   filter. Fixed to build the dict from `.Name`/`.Value` pairs properly
   (the same pattern `get_print_settings` already used correctly).
4. **A structural bug, not just a value bug:** `DocumentRegistry`'s
   same-object dedup was keyed by Python `id(uno_document)`. Live-verified
   that PyUNO mints a *fresh* Python-side proxy object (different `id()`)
   every time the same remote document is fetched (e.g. two separate
   `desktop.getCurrentComponent()` calls) -- but those proxies compare
   `==` and hash consistently for the same underlying UNO object. Result:
   opening a document, then resolving "the active document" a moment
   later, silently minted a *second* `document_id` for the same real
   document instead of returning the first one. Fixed by keying
   `_ids_by_identity` off the object itself (using its `__eq__`/`__hash__`)
   instead of `id()`. Added a regression test using a hand-built fake with
   overridden `__eq__`/`__hash__` (simulating the PyUNO behavior) since
   the plain-object fakes used everywhere else default to identity
   semantics and wouldn't have caught this.
5. **Minor, fixed alongside #2:** `get_print_settings_live` returned raw
   `uno.Enum` reprs (`"<Enum instance ... ('PORTRAIT')>"`) and a raw
   `Size` struct repr for `PaperOrientation`/`PaperFormat`/`PaperSize`.
   Added `UNOBridge._uno_value_to_plain()` (Enum -> its `.value` string,
   Size-shaped struct -> `{width, height}` dict) and live-verified clean
   output afterward.

**Live-verified end to end**, including real file I/O this time (not just
HTTP calls returning success): opened a real `.odt` from disk via
`open_document_live`; wrote a real file via `save_as_document_live` and
`save_copy_live` (confirmed on disk with `ls`); converted a real `.odt` to
a real `.pdf` via `convert_document_live` (confirmed the PDF existed and
had plausible size); round-tripped a custom property through
`set_custom_property_live` -> `get_custom_properties_live` ->
`remove_custom_property_live`; `reload_document_live` correctly kept the
same `document_id` pointing at the new component; `close_document_live`
correctly unregistered its `document_id` (subsequent resolution correctly
returned `OBJECT_NOT_FOUND`); `open_from_template_live` correctly created
an untitled document from template content; `print_document_live` printed
for real to a "Microsoft Print to PDF" virtual printer (~12s, no timeout);
`GET /` showed `tools_count: 66` (32 + 12 + 22) throughout.

**One environment-specific, documented (not a bug) observation:**
`desktop.getCurrentComponent()` doesn't recognize a document as "active"
purely from being loaded via `loadComponentFromURL` in this scripted/
headless test harness -- `get_active_document_live` and similar
active-document-only tools (`set_custom_property_live` before
`activate_document_live` was called, etc.) correctly returned
`NO_ACTIVE_DOCUMENT` until `activate_document_live` was called explicitly.
In a normal interactive LibreOffice session this resolves naturally via
real window/frame focus; scripted/headless callers (including future test
harnesses) should call `activate_document_live` after opening/reloading a
document if they need active-document resolution to work.

**Testing:** `tests/test_document_lifecycle.py` (19 tests, fakes for
`UNOBridge` plus the real `DocumentRegistry`/`RuntimeState`/`context`),
`tests/test_uno_datetime.py` (6 tests), plus 2 new
`tests/test_document_registry.py` tests (`replace_document`, and the
proxy-identity regression test above). 95/95 passing under `pytest` across
the full relevant suite.

## Real implementation pass: undo, view, selection, and locking tools

Split into two sub-passes per explicit direction, since undo semantics
were the highest-leverage next step (two architectural holes -- see
below -- depended on it) and view/selection/locking could follow
separately without blocking on it.

**Sub-pass 1: the 6 undo tools** (`get_undo_state_live`, `undo_live`,
`redo_live`, `begin_undo_context_live`, `end_undo_context_live`,
`cancel_undo_context_live`) via `XUndoManagerSupplier.getUndoManager()`.
Closed two real architectural holes rather than just adding tool count:

- `batch_execute_live`'s `undo_label` now opens a real named undo context
  before running its operations and closes it after, instead of emitting
  a "not implemented yet" warning and running ungrouped.
- `get_session_state_live`'s `pending_undo_context` now reports the real
  open context's title/document_id while one is open, `null` after
  end/cancel, instead of being hardcoded to `None`.

New plumbing: `RuntimeState` tracks the single open undo context
(`set_undo_context`/`get_undo_context`/`clear_undo_context` --
`{title, document_id, baseline_count}`, no UNO references); a new
`INVALID_STATE` error code (`envelope.py`, a documented scaffold-only
addition beyond the spec's own list) for nesting rejection and
end/cancel-with-nothing-open. Deliberate design choice: nested
`begin_undo_context_live` is rejected outright (`INVALID_STATE`) rather
than silently supported -- the tracker can only hold one context at a
time, and end/cancel take no title/document_id to disambiguate which of
two open contexts they'd target.

Live-verified against real headless LibreOffice with 8 explicit
acceptance tests (begin/3-edits/end coalescing into one Undo step,
`batch_execute_live`'s undo_label producing the same behavior, session
state reporting, nesting rejection, no-context-open errors, cancel
genuinely restoring pre-context content, count bounds/exhaustion,
real UNO action titles). All 8 passed; no live-only bugs turned up this
sub-pass. One discovered-not-hidden behavior: `XUndoManager` has no true
"cancel" primitive, so `cancel_undo_context_live` works by undoing, which
pushes the "cancelled" edits onto the *redo* stack like any other undo --
a `redo_live` right after a cancel resurrects them. Correct UNO semantics,
just worth knowing.

**Sub-pass 2: the 6 view/selection/locking tools** (`get_view_state_live`,
`set_zoom_live`, `get_selection_live`, `clear_selection_live`,
`lock_document_updates_live`, `unlock_document_updates_live`).
`get_document_events_live`/`wait_for_document_event_live` deliberately
NOT included -- event capture needs a persistent listener with its own
lifecycle/concurrency behavior, different enough from these otherwise-
synchronous UNO calls to deserve its own pass.

**One real bug found and fixed by live-verifying** (again, something a
fakes-based unit test structurally can't catch -- the fakes model the
UNOBridge method boundary, not the shape of the real UNO controller
object underneath it): `set_zoom_live`/`get_view_state_live` assumed
`ZoomValue`/`ZoomType` were direct properties of `doc.getCurrentController()`.
Reading `controller.ZoomValue` silently returned `None` and writing
`controller.ZoomType` raised a real UNO exception. Live-verified the
actual location: `controller.ViewSettings` (an `XPropertySet`, service
`com.sun.star.text.ViewSettings` for Writer) -- fixed to read/write zoom
via `getPropertyValue`/`setPropertyValue` on that object instead, with a
fallback to the controller itself if `ViewSettings` isn't present.
**Scope note:** only Writer was available to live-verify this pass: the
UNO API docs describe the same `ViewSettings` pattern for Calc/Impress/
Draw controllers, but that's not independently confirmed here.

`get_selection_live`/`clear_selection_live` and `lock_document_updates_live`/
`unlock_document_updates_live` all worked as designed on the first live
attempt (`doc.lockControllers()`/`unlockControllers()` and
`controller.getSelection()` are well-established, less surprising UNO
APIs than the zoom property location was). One discovered nuance, not a
bug: after `clear_selection_live` collapses a Writer selection to a
point, `has_selection` still reports `true` (a collapsed cursor is still
a zero-length selection object, per the same `_has_selection()` helper
the original 32 tools already use) while `selected_text` correctly comes
back empty -- consistent with existing codebase semantics, not a new
inconsistency.

**Testing:** `tests/test_undo_view_selection.py` grew from 17 to 27 tests
(fakes for `UNOBridge`, real `DocumentRegistry`/`RuntimeState`/`context`,
same pattern as the other real-implementation test files).
`tests/test_tool_scaffold_contract.py`'s `IMPLEMENTED_TOOL_NAMES` now
lists all 12 implemented tools in this mixed module (the remaining 2
document-event tools are asserted to still be `status="stub"`). 129/129
passing under `pytest` across the full relevant suite after both
sub-passes.

## Real implementation pass: styles and formatting tools

All 12 `tools/styles.py` tools implemented for real in one pass (unlike
the split undo/view-selection pass, styles didn't need to be broken up --
no cross-module architectural holes depended on it). Family/style CRUD
(`list_style_families_live`, `list_styles_live`, `get_style_live`,
`create_style_live`, `clone_style_live`, `update_style_live`,
`rename_style_live`, `delete_style_live`) works across any document type
implementing `XStyleFamiliesSupplier` (Writer/Calc/Impress/Draw all do);
`create_style_live`/`clone_style_live` are limited to 6 families with a
known UNO service name (`ParagraphStyles`, `CharacterStyles`,
`PageStyles`, `FrameStyles`, `NumberingStyles`, `CellStyles`) --
live-verified LibreOffice 26.2 also exposes a 7th, `TableStyles`, which
correctly raises `UNSUPPORTED_CAPABILITY` for create/clone rather than
guessing at its service name.

**Resolved the `target` selector question** left open for Morgan since
the original Phase A scaffolding pass: for `apply_style_live`/
`get_direct_formatting_live`/`clear_direct_formatting_live`/
`copy_formatting_live`, omitted `target` means the current selection;
an explicit `{"start": int, "end": int}` means a 0-based Writer character
range, reusing the exact cursor-building code the existing
`select_text_range_live` legacy tool already uses. These four tools are
Writer-only this pass (`WRONG_DOCUMENT_TYPE`-shaped `UNSUPPORTED_CAPABILITY`
for other types via the same `NotImplementedError` mapping pattern as
`refresh_document`/`apply_style`).

**Caught before committing (not a live bug, a self-review catch):** an
early draft added an undocumented `document_id` parameter to 11 of the 12
tools. Only `list_style_families_live` has `document_id` in the spec's
own parameter list -- every other styles tool is scoped to the active
document only, matching the precedent already set by
`document_lifecycle.py`'s `save_as_document_live`/`print_document_live`.
Caught by re-checking the original Phase A stub signatures before writing
tests, not by live testing -- a reminder that live verification and
careful spec re-reading catch different classes of mistake.

**Two real bugs found and fixed by live-verifying:**

1. `clone_style_live` needed the `com.sun.star.beans.PropertyState`
   `DIRECT_VALUE` enum for comparison (`uno.Enum("com.sun.star.beans.PropertyState",
   "DIRECT_VALUE")`) -- live-verified this construction pattern works and
   that clone_style_live genuinely copies direct property values (checked
   independently via a raw UNO script reading `CharHeight`/`CharWeight` off
   both the source and cloned style after cloning, not just trusting the
   tool's own success response).
2. `get_direct_formatting_live` initially dumped a raw UNO object repr for
   any property whose value is itself an object reference (e.g. a Writer
   paragraph's `TextParagraph` self-reference property came back as
   `"pyuno object (com.sun.star.text.XTextContent)0x...{implementationName=SwXParagraph, ...}"`)
   -- `_uno_value_to_plain()` doesn't know how to convert an arbitrary
   object reference, and nothing filtered out what it couldn't convert.
   Added `UNOBridge._is_json_safe()` to exclude any property whose
   (converted) value isn't a plain JSON-serializable type, applied to both
   `get_direct_formatting_live` and `copy_formatting_live` (the latter
   also skips copying such properties rather than attempting -- and
   presumably failing -- to set them on the target).
   **Scope note surfaced by this:** Writer text ranges implement both
   `CharacterProperties` and `ParagraphProperties`, so `get_direct_formatting_live`'s
   `DIRECT_VALUE` filter still includes structural paragraph-level
   properties (`ParaStyleName`, `PageStyleName`, etc.) alongside genuine
   character-formatting overrides -- not curated down to a
   "formatting-only" subset, documented in the method's own docstring
   rather than silently narrowed (which risked hiding real overrides
   behind a wrong guess at which properties "count").

**Also confirmed pre-existing, not caused by this pass:** the original
32 tools' `format_text_live` returned `"No Writer document available"`
against a document this session had just opened, activated, and
successfully read/selected text on with other legacy tools. Root cause:
`uno_bridge.py`'s `format_text()` checks `_is_instance(doc, XTextDocument)`
(a literal Python `isinstance()` against the imported UNO type), not the
more robust `supportsService()` duck-typing pattern `_get_document_type()`
uses elsewhere -- exactly the fragility spec section 6 itself warns
against ("Prefer supportsService... over Python isinstance() where UNO
bridge types are unreliable"). Not fixed here (preserving the original 32
exactly, per spec section 6's own compatibility requirement); worked
around for this pass's live testing by setting direct character
formatting via a raw UNO script instead of the broken legacy tool.

**Live-verified end to end, including independent verification (not just
trusting the tool's own success response):** created a custom paragraph
style with real properties, cloned it and confirmed via raw UNO script
that `CharHeight`/`CharWeight` genuinely matched between original and
clone; applied a style to an explicit character range and confirmed via
raw UNO script that the paragraph's real `ParaStyleName` changed; set
real direct character formatting (bold/color) via UNO script, read it
back through `get_direct_formatting_live`, cleared it and confirmed it
was genuinely gone, then copied it to a different range and confirmed the
values landed there too. `tools_count: 90` (78 + 12) throughout.

**Testing:** `tests/test_styles.py`, 17 new tests (fakes modeling style
families as plain dicts and text ranges as `{start, end}` keys -- real
UNO service names, property names, and `PropertyState` enum comparisons
are live-verified instead, not something a fake can usefully assert).
146/146 passing under `pytest` across the full relevant suite.

## Real implementation pass: writer_text.py (18 new tools)

All 18 new tools in the "Writer - text, navigation, editing, search,
review" spec section implemented for real in one pass:
`insert_paragraph_live`, `append_paragraph_live`, `insert_heading_live`,
`set_paragraph_text_live`, `split_paragraph_live`, `merge_paragraphs_live`,
`move_paragraphs_live`, `copy_paragraphs_live`, `set_paragraph_format_live`,
`set_character_format_live`, `get_text_range_format_live`,
`find_regex_live`, `replace_regex_live`, `find_by_style_live`,
`replace_style_live`, `update_comment_live`, `delete_comment_live`,
`resolve_comment_live`. The section's other 27 rows are the pre-existing
"(existing)" tools already live in `mcp_server.py`/`uno_bridge.py` under
the original 32 -- intentionally not duplicated here.

**Paragraph indexing is 1-based**, matching the convention the pre-existing
`get_paragraph_live`/`goto_paragraph_live`/`select_paragraph_live` legacy
tools already established (`UNOBridge._get_paragraph_object`,
`_count_paragraphs`) -- `split_paragraph_live`'s `n`, `merge_paragraphs_live`'s
`first_n`, and `move_paragraphs_live`/`copy_paragraphs_live`'s `start`/`end`/
`destination` all mean "the Nth paragraph, counting from 1", and
`find_by_style_live`'s `matches[].paragraph` reports in the same 1-based
scheme. This is deliberately a *different* convention from
`set_paragraph_format_live`/`set_character_format_live`'s `target`
(0-based Writer character offsets, reusing styles.py's `apply_style_live`
precedent) -- the two schemes address different things (a paragraph
ordinal vs. a character range) and live-testing this pass confirmed the
mixed convention is what the pre-existing paragraph tools already expect,
not something worth "fixing" into false consistency.

**`get_text_range_format_live`** returns every JSON-safe effective
character/paragraph property on a range (~80 real UNO properties observed
live), using the same `_is_json_safe()` filter styles.py's pass added.

**Comments got a `comment_id` scheme that didn't exist before this pass.**
`get_comments_live`/`add_comment_live` (original 32) never needed to
address a specific comment; `update_comment_live`/`delete_comment_live`/
`resolve_comment_live` do, so a minimal, additive `comment_id` was invented
and threaded through the same `com.sun.star.text.TextField.Annotation`
enumeration those two legacy tools already use. Full lifecycle live-verified
end to end: selected a text range, added a comment, listed it (real
`comment_id`), updated its text (confirmed via re-listing that content
changed), resolved it, deleted it, confirmed the list came back empty --
each step re-confirmed independently, not just trusting the previous
call's own success response.

**Two real bugs found and fixed by live-verifying:**

1. `set_paragraph_format_live`/`set_character_format_live`'s `target`
   parameter was declared as a plain required argument
   (`target: Any`) instead of `target: Optional[Any] = None` like
   `styles.py`'s identical `apply_style_live`/`get_direct_formatting_live`
   precedent. Both tools' own docstrings and JSON Schema describe "omitted
   `target` means current selection" -- but because the dispatcher calls
   handlers as `handler(**parameters)` and the JSON body legitimately omits
   `target` for that case, the missing default meant Python raised
   `TypeError: set_paragraph_format_live() missing 1 required positional
   argument: 'target'` *before* the function body's own `try/except` could
   ever run, so the omitted-target contract was uncatchably broken for both
   tools. Live-caught: `curl` with a `target`-less body returned a raw
   Python traceback instead of an envelope, not the current-selection
   success static analysis and the fakes-based unit tests (which always
   passed `target` explicitly) never exercised. Fixed by adding the missing
   `Optional[Any] = None` default to both signatures, matching styles.py's
   pattern; re-verified live that omitting `target` now correctly formats
   the current selection.
2. Not a bug, but worth recording since it looked like one during this
   pass's live testing: `set_paragraph_format_live`/`set_character_format_live`'s
   `properties` dict takes real UNO property names (`CharWeight`,
   `CharColor`, `ParaAdjust`, ...), not friendly aliases (`bold`, `color`).
   This matches `create_style_live`/`update_style_live`'s existing
   best-effort "apply what UNO accepts, report what applied, silently skip
   the rest" contract from the styles.py pass -- not a new pattern, just
   easy to mistake for a bug when testing with alias-shaped keys first.

**Also newly discovered this pass, not fixed (preserving the original 32
exactly, same rule as `format_text_live`'s known `isinstance()` bug):**
the original 32 tools' `get_comments_live` returns a raw
`com.sun.star.util.Date` struct repr for its `date` field (e.g.
`"(com.sun.star.util.Date){ Day = (unsigned short)0x0, Month = ...
}"`) instead of an ISO-8601 string -- the same class of bug
`get_document_properties_live` had before this repo's `uno_datetime.py`
module was added, just never applied to this legacy tool. Left untouched
per the preserve-the-original-32 rule; flagged here as technical debt
(see Buddy's audit item #42).

**Live-verified end to end on a fresh headless LibreOffice 26.2 instance
after the two bug fixes landed, independently checking the real document
state after every call (not trusting each tool's own success response):**
`split_paragraph_live` on "Body paragraph." at offset 4, independently
read back as two paragraphs ("Body" / " paragraph."); `merge_paragraphs_live`
merged them back to the original text; `copy_paragraphs_live` duplicated a
paragraph to the end, independently confirmed via paragraph enumeration;
`move_paragraphs_live` moved that duplicate to the front, independently
confirmed; `set_character_format_live` set real `CharWeight`/`CharColor`
on an explicit character range, independently read back off the live text
cursor; `set_paragraph_format_live` with `target` omitted set `ParaAdjust`
on the current selection's paragraphs, independently read back off both
touched paragraphs; `find_by_style_live` correctly found both `Heading 1`
paragraphs by 1-based paragraph number; `replace_style_live` swapped both
to `Heading 2`, independently confirmed via paragraph enumeration.
`tools_count: 108` (90 + 18) throughout.

**Testing:** `tests/test_writer_text.py`, 32 new tests (fakes modeling
paragraphs/text ranges the same way `test_styles.py` does -- real UNO
paragraph indexing, `PropertyState`, and `TextField.Annotation` behavior
are live-verified instead, not something a fake can usefully assert).
178/178 passing under `pytest` across the full relevant suite (146 prior +
32 new).

## PyUNO robustness sweep

Mandated by Brian/Buddy before further Phase C/D real implementation
("cheap to audit at 90 tools and expensive at 400+"): a sweep of
`uno_bridge.py` for two known dangerous patterns.

**11 bare `except:` blocks, all fixed** (narrowed to `except Exception:`).
All 11 live inside original-32 legacy helper methods -- best-effort
property/range probes, not tool entry points:
`get_track_changes_status` (3, reading `RecordChanges`/`ShowChanges`/
`getRedlines()` -- any one may not exist on a given document type),
`_is_text_range_in_tracked_deletion`/its paragraph-filtering counterpart
(4, comparing/collecting redline ranges), `find_text`/`find_and_replace_all`
(2, the same `RecordChanges`/`ShowChanges` probe duplicated), and
`_has_selection` (1). This is a mechanical narrowing, not a behavior
change for any realistic UNO-raised exception -- a bare `except:` and
`except Exception:` catch exactly the same things a UNO call can raise;
the only difference is a bare `except:` also silently swallows
`KeyboardInterrupt`/`SystemExit`/`GeneratorExit`, which matters in a
long-running embedded server process. Live-verified behaviorally
unchanged on the normal path: rebuilt the extension, live-called
`get_track_changes_status_live`, `find_text_live`, and
`find_and_replace_all_live` against a real document with real matches,
independently confirmed `find_and_replace_all_live`'s replacement
genuinely landed via `get_text_content_live`. Full suite still 178/178
after the change.

**`isinstance()`-on-UNO-interface fragility audit.** Grepped every
`_is_instance(doc, ...)` call site (9 total, the helper itself excluded).
Two are genuinely unguarded (isinstance is the *only* check, no
`supportsService()` fallback if it spuriously returns the wrong answer
for a given UNO document proxy):

1. `format_text_live` (original 32) -- **already known and documented**
   (styles.py pass), confirmed still present, still deliberately left
   unfixed to preserve the original 32 exactly.
2. `get_document_info_live` (original 32) -- **newly discovered this
   pass**. `get_document_info()`'s Writer/Calc enrichment branch
   (`word_count`/`character_count` for Writer, `sheet_count`/
   `sheet_names` for Calc) is gated by `_is_instance(doc, XTextDocument)`/
   `_is_instance(doc, XSpreadsheetDocument)` alone, with no
   `supportsService()` fallback. Unlike `format_text_live`'s failure mode
   (an outright error), this one fails *silently*: if isinstance
   spuriously returns `False` for a genuinely-Writer or genuinely-Calc
   document, `get_document_info_live` still returns `success: true` with
   the base fields, just missing the type-specific enrichment -- easy to
   miss since nothing signals the omission. Not fixed here (preserving
   the original 32 exactly, same rule as `format_text_live`); flagged as
   technical debt.

The remaining 5 `_is_instance()` call sites (`insert_text`,
`get_text_content`, `_get_document_type` x3) all either `or` the
isinstance check together with a `supportsService()` check and/or a
`hasattr(doc, 'getText')` fallback, or -- in `_get_document_type()`'s
case, which every real-implementation module's `_require_writer()`/
style-family/etc. helpers route through -- try isinstance first and fall
through to `supportsService()` when it doesn't match. None of the new
Phase A real-implementation code is exposed to the isinstance fragility
as a result; only these two original-32 legacy methods are.

## Document targeting decision: `document_id` vs `document_url`

Mandated item #1, blocking further Phase C/D real implementation until
decided: see `docs/DOCUMENT_TARGETING_DECISION.md` for the full
comparison against WriterAgent's `document_url`/`X-Document-URL`
approach. Short version: **`document_id`/`DocumentRegistry` stays the one
targeting mechanism** -- it already gives O(1), Save-As-stable,
untitled-document-safe resolution via UNO object-identity keying, the
same guarantees WriterAgent's URL-or-`RuntimeUID` dual scheme exists to
provide, without a second parameter shape or a per-call desktop
enumeration. Which tools take `document_id` at all stays governed by the
existing "match the spec's own parameter list for that tool exactly"
rule (`document_lifecycle.py`/`styles.py`/`writer_text.py` precedent),
unchanged by this decision. One real gap this comparison surfaced,
independent of the addressing mechanism: mcp-libre has no per-document
mutation lock, so two concurrent MCP clients could race on the same open
document -- flagged for the `/mcp` transport work (mandated item #4), not
solved here since it's a concurrency-control concern layered on top of
addressing, not an addressing question itself.

## Object handle design: sheets, slides, shapes, tables, charts

Mandated item #2, blocking further Phase C/D real implementation until
decided: see `docs/OBJECT_HANDLE_DESIGN.md` for the full design. Short
version: **not every category gets the same mechanism**, following the
spec's own already-scaffolded parameter shapes. Sheets (`sheet: string`)
and slides (`slide`, documented as "index or name") resolve live against
UNO's own named/indexed containers every call, no registry -- UNO already
guarantees both are uniquely named, and the spec's own polymorphic
`slide` parameter already solves the "index shifts under reordering"
identity trap. Writer tables and Calc's own chart collection
(`table_id`/`chart_id`) also resolve directly against a UNO-guaranteed
unique `Name`, no registry -- confirmed live this pass (a newly-inserted
Writer table auto-gets `Name: "Table1"`; a Calc sheet's `getCharts()` is
a name-accessible container). Shapes, and charts embedded outside Calc's
dedicated chart collection, get a real registry -- UNO gives them no
persistent unique identity at all (confirmed live: two distinct new Draw
shapes both default to `Name: ''`, and a draw page's shape container has
no `getByName()`). Built this pass: `plugin/pythonpath/tools/
object_registry.py`'s `ObjectRegistry` (the same object-identity-keyed
mechanism `DocumentRegistry` already uses for `document_id`, generalized)
plus `DocumentRegistry.get_object_registry(document_id)`, which lazily
creates one `ObjectRegistry` per document and drops it in
`unregister_document()` so a shape/chart handle's lifetime is bounded by
its owning document's. Unit-tested (`tests/test_object_registry.py`, 8
tests; 4 new cases in `tests/test_document_registry.py`), not yet wired
into any Phase C/D tool -- that's for whichever pass makes Calc-sheets/
Impress/Draw/drawing-objects/charts real.

## Real MCP JSON-RPC 2.0 transport

Mandated item #4, run in parallel rather than gated on the tool catalog
(per Buddy: "there is no architectural reason to postpone it until the
tool catalog is complete"). Before this pass, confirmed by grep: zero
occurrences of `initialize`/`tools/list`/`tools/call`/`jsonrpc` anywhere
in the codebase -- `ai_interface.py`'s `MCPRequestHandler` served only a
bespoke REST shim (`GET /`, `GET /tools`, `GET /health`, `POST /execute`,
`POST /tools/{tool_name}`), no MCP protocol layer at all.

**`plugin/pythonpath/mcp_jsonrpc.py`** is the actual JSON-RPC 2.0
message-level dispatch (`initialize`, `notifications/initialized`,
`ping`, `tools/list`, `tools/call`, `resources/list`/`prompts/list`
-- both always empty, this server exposes no MCP resources/prompts),
kept UNO/HTTP-independent (takes a plain tools dict and an
`execute_tool` callable) so it's unit-testable with fakes --
`tests/test_mcp_jsonrpc.py`, 22 tests. JSON-RPC batch arrays are
supported; notifications get no response entry, matching spec. Reuses
the two-layer error model this project's own WriterAgent research
surfaced: a tool-level failure (this project's envelope has
`success: false`) is `isError: true` on a normal 200-shaped
`tools/call` result, not a JSON-RPC error object -- only protocol-level
faults (bad method, malformed params, an exception escaping the
handler) are real JSON-RPC errors (`-32601`/`-32602`/`-32603`, the
standard reserved codes).

**`ai_interface.py`** wires this in as `POST /mcp` (plus `/sse` and
`/messages` as aliases for clients hardcoded to the older split-SSE
transport's path names, dispatched through the identical handler),
`GET /mcp` (405 -- no server-initiated SSE stream, this server has
nothing to push), and `DELETE /mcp` (acknowledges session termination;
no real per-session state to tear down yet, see below). Mints an
`Mcp-Session-Id` on `initialize` and echoes the negotiated
`Mcp-Protocol-Version`; CORS headers extended with
`Access-Control-Expose-Headers` so a browser-hosted MCP client's JS can
read both. The pre-existing REST bridge (`/tools`, `/execute`, etc.) is
untouched and still works -- confirmed side-by-side this pass, same
server, same session, both code paths live at once.

**Scoped down, deliberately, for this first real-transport pass:**
`Mcp-Protocol-Version` negotiation is permissive (always echoes back
whatever version the client's `initialize` requested, rather than
validating against a fixed supported-version list) -- reasonable with
one server version to support today; a future pass adding real
multi-version negotiation should tighten this. `Mcp-Session-Id` is
minted and echoed but not yet validated/enforced on subsequent
requests -- there is no per-session state to isolate yet (no
per-document mutation lock either, see
`docs/DOCUMENT_TARGETING_DECISION.md`'s flagged gap), so a session id
today is a courtesy for clients that expect the header, not a real
guarantee. Responses are always a single JSON object/array
(`Content-Type: application/json`), never an SSE stream -- valid per
the Streamable HTTP spec (SSE is for a server that needs to push
multiple messages per request; this server never does), but means no
server-initiated progress notifications mid-call.

**Live-verified against a real MCP client, not just curl** (the
mandate's explicit bar): `npx @modelcontextprotocol/inspector --cli`
(the official reference MCP Inspector, doing real protocol negotiation
and JSON-RPC framing, not hand-crafted curl JSON) connected to a live
headless LibreOffice 26.2 instance running this build, ran `tools/list`
and got back the real, full 108-tool catalog, then `tools/call
insert_paragraph_live` with a real text argument -- independently
confirmed the paragraph genuinely landed in the live document via a
completely separate code path (`get_text_content_live` through the
pre-existing REST bridge), not just trusting the JSON-RPC response.
Also curl-verified directly: `initialize` (protocol version echo,
session id minted), `notifications/initialized` (202, empty body),
batch requests (notification correctly dropped, only the two `id`-
bearing responses returned, in order), unknown tool (`isError: true`,
not a JSON-RPC error -- confirms the two-layer model), unknown method
(`-32601`), invalid JSON (`-32700`), `GET /mcp` (405), `DELETE /mcp`
(200 ack), `/sse`/`/messages` aliases, and CORS preflight
(`OPTIONS /mcp` with an `Origin` header returns the right
`Access-Control-*` headers).

**Testing:** `tests/test_mcp_jsonrpc.py`, 22 new tests. 212/212 passing
under `pytest` across the full relevant suite (190 prior + 22 new).

## WriterAgent comparison matrix

Closes Brian's original 8-item WriterAgent request, items 1/2/6: see
`docs/WRITERAGENT_COMPARISON_MATRIX.md` for the full WriterAgent-better/
ours-better/both/neither/unknown table across Writer, Calc, Impress,
Draw, runtime/lifecycle, multi-doc targeting, MCP transport, security,
undo/batching, object identity, and testing -- plus a standalone,
confidence-graded list of WriterAgent capabilities absent from the spec
document itself (vision/screenshot understanding, embeddings/RAG over
document content, a notebook-cell interface, and a Calc analysis engine
-- DuckDB, symbolic math, forecasting, solver/optimization -- are the
high-confidence findings). Widest deltas: WriterAgent's MCP transport is
production-hardened where `mcp-libre`'s is a correct first pass (no
concurrency control yet); `mcp-libre`'s undo-context transactions are a
real capability WriterAgent's simple shared-stack undo doesn't have.

## Real implementation pass: drawing_objects.py (25 of 31 tools)

Built first among the remaining Phase C/D modules per audit #41
(dependency order, not catalog order): charts/impress/draw all sit on
top of this shared shape primitive. Consumes `ObjectRegistry`
(mandated item #2) for the first time -- `shape_id`/`object_id` resolve
through `DocumentRegistry.get_object_registry(document_id)`, exactly the
mechanism `docs/OBJECT_HANDLE_DESIGN.md` designed for this pass.

**Category split confirmed, not just designed this time:** `container`
(sheet/page addressing) resolves live against UNO's own named/indexed
containers -- `UNOBridge._resolve_shape_container()` handles Writer's
single document-wide draw page, a Calc sheet's own draw page (sheet
name or digit-string index), and a specific Impress/Draw page (int
index or name, `getDrawPages().hasByName()`/`getByName()` confirmed to
exist live this pass, closing the one previously-unverified claim in
the design doc).

**Two real bugs found and fixed by live-verifying:**

1. `delete_glue_point_live` called `glue_points.remove(index)` --
   `remove()` doesn't exist on the glue-points container at all
   (`AttributeError`); the real method is `removeByIndex()`. Live-
   caught (the fakes-based unit test couldn't have caught this --
   it doesn't model the real UNO method name), fixed, rebuilt, and
   re-verified live that a custom glue point genuinely round-trips
   (add -> list count 5 -> delete -> list count 4 -> independently
   confirmed via a raw UNO script).
2. `_map_exception_to_code()` (shared by every real-implementation
   module via `document_lifecycle.py`) didn't know about
   `object_registry.ObjectNotFoundError` -- an unresolvable `shape_id`
   fell through to the generic `UNO_EXCEPTION` code instead of
   `OBJECT_NOT_FOUND`, the same code `DocumentNotFoundError` already
   maps to. Caught by the new unit tests (4 of 26 failed on this before
   the fix), not live-testing -- a reminder this project has made
   before that the two verification methods catch different mistakes.
   Fixed by adding one `isinstance` check; this also silently benefits
   every future module that reuses `ObjectRegistry`.

**Not a bug, but live-testing corrected a wrong assumption baked into
the initial unit tests:** grouping shapes does NOT dispose the member
shapes in real UNO -- `page.group()` reparents them into the new group,
but the original PyUNO proxy stays fully valid and UNO-equal to the
group's own child references (confirmed live: `child0 == s1` is `True`
even though `child0 is s1` is `False`, the same proxy-re-minting
behavior `DocumentRegistry` was built around). So a member shape's
`shape_id` deliberately keeps resolving after `group_shapes_live` --
only `ungroup_shape_live`'s *group* id goes stale (confirmed live: the
group object becomes an empty, zero-child shell after ungrouping, and
its `shape_id` is explicitly unregistered). The initial test asserted
the opposite for the group case; fixed to match live-verified reality
before this pass was called done, not left un-reconciled.

**Scope limit, deliberate (see this section's opening paragraph and
both `uno_bridge.py`'s and `drawing_objects.py`'s own docstrings for the
full reasoning):** `combine_shapes_live`, `split_shape_live`,
`bind_shapes_live`, `unbind_shape_live`, `insert_embedded_object_live`,
`activate_embedded_object_live` (all P3) stay `status="stub"`.
Live-testing `.uno:Combine` this pass -- the only UNO-level way to
implement combine/split/bind/unbind, since there is no direct API --
executed successfully but then **crashed the headless soffice process
outright on the very next UNO call** (`DisposedException: "Binary URP
bridge disposed during call"`), which would take down the extension's
whole host process for every connected MCP client, not just the caller
issuing the risky call. Not safe to ship without a dedicated isolation/
testing pass. The two embedded-object tools are the same OLE-activation/
dispatch risk class and weren't exploration-tested given the crash.

**Live-verified end to end on a fresh headless LibreOffice 26.2
instance, independently checking real document state after every call**
(not trusting each tool's own success response): inserted a rectangle
and ellipse, confirmed real position/size/z-order via a raw UNO script;
moved/rotated a shape and confirmed the resulting UNO `Position` shift
after rotation matches expected bounding-box-after-rotation geometry
(not a bug -- standard UNO rotation semantics); set fill color, z-order
swap (`action: "back"`), duplicated a shape (confirmed the clone's
`RotateAngle` was genuinely copied, 214-ish of ~229 properties copied
per the method's own docstring); inserted a connector and confirmed
`StartShape`/`EndShape` were genuinely wired via a raw UNO script;
aligned two shapes left and confirmed their real `x` values matched;
added/listed/deleted a glue point (post-fix) and independently confirmed
the count via a raw UNO script; grouped two shapes (confirmed
`page.getCount()` dropped as expected) and ungrouped them (confirmed the
group's `shape_id` genuinely stops resolving); inserted a real PNG image
via `GraphicProvider`, set 50% transparency (confirmed via raw UNO
`Transparency` read), exported it to PNG at a specific DPI and
independently confirmed the exported file's real pixel dimensions
(177x177, matching the hand-computed expected value from the shape's
1500/100mm size at 300dpi exactly) via a `GraphicProvider` readback of
the exported file, not just trusting the export call's own success;
replaced the image source; set/formatted/alt-texted a text shape and
confirmed all three landed via `get_shape_live`; distributed three
shapes horizontally and confirmed the middle one's position via a raw
UNO script; deleted a shape and confirmed `page.getCount()` dropped.
`tools_count: 133` (108 + 25) throughout.

**Testing:** `tests/test_drawing_objects.py`, 26 new tests (a
`FakeShape`/`FakeUnoBridge` pair modeling shapes as plain Python objects
in a flat list -- `DocumentRegistry`/`ObjectRegistry` are the real
implementations under test, not faked; real UNO geometry math, ZOrder
clamping, `XShapeGrouper`, `GluePoint2` construction, and
`GraphicProvider`-based image loading are live-verified instead, not
something a fake can usefully assert). 239/239 passing under `pytest`
across the full relevant suite (212 prior + 1 new contract test + 26
new).

## Real implementation pass: calc_sheets.py (all 42 tools)

Second Phase C module, per Buddy's "Calc sheets can proceed in parallel
since sheet/slide addressing needed no registry per your design doc."
All 42 tools real -- unlike `drawing_objects.py`, no scope limits were
needed: every UNO API this module depends on (cell/range addressing,
`setFormulaArray`, `XCellSeries.fillSeries`/`fillAuto`,
`XCellRangeMovement`, `NumberFormats`, `queryPrecedents`/
`queryDependents`) turned out to be a clean, direct, non-dispatch call --
no repeat of `drawing_objects.py`'s `.uno:Combine` crash risk.

**Sheet addressing confirmed live, not just designed:** `sheet` resolves
via `UNOBridge._resolve_sheet_by_name_or_index()` (already shared with
`drawing_objects.py`'s container resolution) plus a new
`_resolve_sheet()` wrapper for the "omitted -> active sheet" fallback.
Cell/range addressing uses plain A1-notation strings directly via
`getCellRangeByName()` -- confirmed live to accept both single cells and
ranges, an object implementing both `XCell` and `XCellRange`
simultaneously for a single-cell reference.

**Three real bugs found and fixed by live-verifying:**

1. `range` is shadowed by its own parameter name in `get_range_live`/
   `get_formula_errors_live` -- a systematic AST-based sweep of the new
   code (not live-testing) found both call sites where the loop code
   called `range(start, stop)` intending the *builtin*, but Python
   resolved the local parameter (a string or `None`) instead, which
   would have raised `TypeError: 'str'/'NoneType' object is not
   callable` the first time either code path actually ran. Fixed with
   an explicit `import builtins` and `builtins.range(...)` at both call
   sites, commented as deliberate. Caught by writing a small AST script
   to search every new function for a parameter that shadows a Python
   builtin *and* a call to that same name inside the function body --
   cheaper and more complete than waiting to hit it during live testing
   or unit tests (the fakes-based tests never exercised these specific
   code paths with real multi-cell ranges either).
2. `delete_cells_live` called `sheet.removeCells(...)` -- doesn't exist
   (confirmed via `hasattr`); the real `XCellRangeMovement` method is
   `removeRange()`. Same class of "guessed method name is wrong"
   mistake as `drawing_objects.py`'s `delete_glue_point_live` fix, this
   time caught by exploration (checking `hasattr` against a live UNO
   object) before writing the implementation, not after.
3. `get_formula_errors_live` (when `range` is omitted, "scan the whole
   sheet") only scanned a single cell -- the sheet's last used cell --
   instead of the whole used area. Root cause: `cursor.
   gotoEndOfUsedArea(False)` on a fresh cursor (starting at A1)
   collapses the cursor down to just the end cell rather than expanding
   it from A1; `get_used_range_live` avoided this by using two separate
   cursors (one for start, one for end) and reading each `RangeAddress`
   independently, but `get_formula_errors_live` used a single cursor
   with only the end call. Fixed to `gotoStartOfUsedArea(False)` then
   `gotoEndOfUsedArea(True)` (`True` = extend the existing selection)
   on the same cursor -- live-verified a `#DIV/0!` cell at column G was
   invisible to the buggy version and correctly found after the fix.

**Not a bug, but live-testing surfaced two UNO behaviors worth
documenting rather than "fixing" into false simplicity:**

- Copying a range whose source contains a formula (`copy_range_live`)
  adjusts the formula's relative references by the same offset a normal
  copy-paste in the Calc UI would -- copying `C1`'s formula `=A2+1`
  eight columns over does not re-copy the *value* 43, it copies a
  *retargeted formula* `=I2+1`, which evaluates against whatever (if
  anything) is actually in `I2`. An initial live test that looked like
  a "missing column" bug in `copy_range_live` turned out to be exactly
  this, confirmed by isolating a clean plain-value-only copy (which
  round-tripped perfectly) from the original mixed formula+merge test
  case (where an unrelated `merge_cells_live` call on the destination
  range had also cleared part of what was just copied there, a second,
  separate expected side effect of merging over already-populated
  cells).
- `queryPrecedents()`'s reported bounding range can span (and include)
  columns beyond the actual individual precedent cells -- for `C1`
  `=A1+B1`, live-verified via direct UNO reflection (not just this
  tool) that `queryPrecedents(False)` genuinely returns a single
  `A1:C1` range (including `C1` itself, the formula cell), not two
  separate `A1`/`B1` ranges. `get_formula_dependencies_live` reports
  whatever UNO itself returns rather than trying to second-guess or
  narrow it.

**Live-verified end to end on a fresh headless LibreOffice 26.2
instance, independently checking real document state after every call**
(not trusting each tool's own success response, and re-verifying the
three fixes above post-fix): sheet CRUD (insert/rename/move/copy/hide/
show), cell get/set with both plain values and formulas (confirmed a
formula genuinely computed, not just stored as text), `set_range_live`
writing a mixed values-and-formula matrix and confirming via
`get_range_live`'s three modes that the formula was genuinely evaluated
(43.0) while a formula-looking string in a different cell mode stayed
literal text where intended; `fill_series_live` (seeded start + step,
confirmed the real linear sequence) and `autofill_live` (confirmed the
real extended pattern) via raw UNO reads; `insert_cells_live` shift-down
(confirmed the shifted value's new position); `copy_range_live`/
`move_range_live` (confirmed via a clean isolated case after
untangling the formula-reference-adjustment behavior above);
`merge_cells_live` and `set_range_format_live`'s `NumberFormat` string
handling (confirmed the real formatted display, `"1,234.50"`-style, via
`queryKey`/`addNew`); `hide_rows_live`/`set_row_height_live` (confirmed
real `IsVisible`/`Height` properties); `freeze_panes_live` (confirmed
`hasFrozenPanes()` -- same visible-window caveat `drawing_objects.py`'s
Zoom-property precedent already documented); `evaluate_formula_live`
(confirmed the scratch-cell technique restores the target sheet's
actual last cell to its original state afterward, and that
`get_used_range_live` doesn't see it as used); `get_formula_errors_live`
post-fix (confirmed a real `#DIV/0!` cell is found);
`get_formula_dependencies_live` (confirmed against direct UNO
reflection, not just the tool's own output). `tools_count: 175`
(133 + 42) throughout.

**Testing:** `tests/test_calc_sheets.py`, 33 new tests (a `FakeUnoBridge`
modeling sheets as a list of plain dicts and cells as a per-sheet dict
keyed by A1-notation string -- enough for tool-layer plumbing, not real
Calc arithmetic; the three live-caught bugs above are exactly the class
of defect this kind of fake structurally cannot catch). 272/272 passing
under `pytest` across the full relevant suite (239 prior + 33 new).

## Real implementation pass: draw.py (all 16 tools) -- and a dispatch-safety correction

First of `charts.py`/`impress.py`/`draw.py`, per Buddy's go-ahead
("they're the modules that sit on top of the drawing_objects.py/
ObjectRegistry primitive you just built"). All 16 tools real. Page
addressing (`page`: index or name) reuses `_resolve_page_by_name_or_index()`
(already shared with `drawing_objects.py`'s container resolution);
`shape_id` (`assign_shape_layer_live`) resolves through the same
`ObjectRegistry`.

**Important correction to the `drawing_objects.py` pass's conclusion,**
found while investigating `move_draw_page_live` (no non-dispatch UNO API
exists for arbitrary page reordering, so this tool genuinely needed to
resolve the dispatch-safety question, not route around it): that pass
concluded `.uno:` dispatch commands were broadly unsafe after
`.uno:Combine` crashed headless soffice with a `DisposedException` on
the very next UNO call. Re-investigating before assuming that also
blocked `move_draw_page_live`, this pass found the crash was an artifact
of the *external test script's own pattern* -- connecting over a URP
socket, dispatching, then calling `doc.close()` on the same document --
not a defect in dispatch commands themselves. Live-verified precisely:

- A harmless `.uno:SelectAll` dispatch, from the same kind of external
  script, crashed headless soffice on the very next `doc.close()` call
  too -- proving the trigger isn't specific to `.uno:Combine`'s
  shape-structural nature.
- Intermediate read-only UNO calls (page count, `getURL()`) after a
  dispatch, and even a 1-second sleep, did NOT crash -- only `close()`
  specifically did, and only on the *same* document a dispatch had just
  run against.
- Most importantly: a real diagnostic tool was wired into the actual
  running extension this pass (`tools/_diagnostic_dispatch_test.py`,
  deleted after the investigation, never committed) and called via
  `curl` through the live REST bridge -- i.e. the dispatch ran from the
  extension's own in-process code, the real production code path, not
  an external URP connection. `.uno:MovePageFirst` executed
  successfully, the server stayed healthy for a follow-up `curl
  /health` call, `soffice.bin` was still running, and an independent
  raw-UNO read (itself never calling `close()`) confirmed the page had
  genuinely moved and stayed moved.

**Conclusion: dispatch commands ARE safe to use for real from within the
extension's own tool implementations** -- the actual usage pattern never
calls `document.close()` immediately after a dispatch on the same
document within one tool call, so the specific trigger this pass
isolated never fires in production. `move_draw_page_live` and
`duplicate_draw_page_live`'s `destination` parameter are therefore
implemented for real via `.uno:MovePageUp`/`.uno:MovePageDown` dispatch
(no native "move to arbitrary index" UNO API exists; iterating the
up/down dispatch the right number of times is the working substitute).
This also means `drawing_objects.py`'s `combine_shapes_live`/
`split_shape_live`/`bind_shapes_live`/`unbind_shape_live` scope limits
from the prior pass were more conservative than necessary -- see the
follow-up fix immediately after this section.

**One real bug found and fixed by live-verifying:**
`set_draw_page_background_live` initially tried
`page.setPropertyValue(key, value)` directly on the page object for
properties like `FillColor`/`FillStyle`/`IsBackgroundVisible` -- all
three raised `AttributeError`, silently swallowed by the tool's own
best-effort skip-unsettable-properties contract, so the tool reported
success with an empty `applied` list and a warning, not an outright
error. A Draw page's fill properties are not direct page properties at
all: the real mechanism is `doc.createInstance("com.sun.star.drawing.
Background")` (document-scoped -- the same call via the global
`ServiceManager` returns `None`), apply properties to *that* object
(a genuine `FillProperties` implementor), then assign it to
`page.Background`. `page`'s own `PropertySetInfo` only exposes
`Background` (an opaque object reference, `None` until assigned) and
the read-only `IsBackgroundDark` -- not `FillColor`/`FillStyle`/
`IsBackgroundVisible` as the tool's own scaffolded parameter naming
might suggest. Fixed, rebuilt, and re-verified live: `FillColor`/
`FillStyle` genuinely landed on `page.Background`, confirmed via an
independent raw UNO read.

**Live-verified end to end on a fresh headless LibreOffice 26.2
instance, independently checking real document state after every call**
(not trusting each tool's own success response, and re-verifying the
background fix post-fix): page CRUD (list/insert/rename/delete),
`move_draw_page_live`'s dispatch-based reorder (confirmed via an
independent raw UNO read the page order genuinely changed, and that the
server stayed healthy and `soffice.bin` stayed alive throughout);
`duplicate_draw_page_live` with an explicit `destination` (confirmed the
duplicate landed at the requested index, not just after the source);
`set_draw_page_size_live`; `set_draw_page_background_live` post-fix;
layer CRUD (`list_layers_live` showing the 5 real built-in layers --
layout/background/backgroundobjects/controls/measurelines --
`create_layer_live`/`update_layer_live`/`delete_layer_live`);
`assign_shape_layer_live` (confirmed via `LayerManager.getLayerForShape()`
that the shape's real layer assignment changed, not just its `LayerID`
property); `export_draw_page_live` (confirmed a real PNG file, correctly
rejects `format="pdf"` with a documented `UNSUPPORTED_CAPABILITY`
explaining the real fix -- whole-document `storeToURL` export, not
`GraphicExportFilter`); `export_selection_live` (confirmed
`GraphicExportFilter.setSourceDocument()` accepts a multi-shape
`ShapeCollection` directly -- no need to group the selection first,
which would have mutated the document as an unwanted side effect of a
supposedly read-only export -- confirmed a real exported file with a
real selection). `tools_count: 191` (175 + 16) throughout.

**Testing:** `tests/test_draw.py`, 17 new tests (a `FakeUnoBridge`
modeling pages/layers as plain dicts, reusing `test_drawing_objects.py`'s
`FakeShape`/`ObjectRegistry` pattern for `assign_shape_layer_live` --
real `XDrawPages`/`XLayerManager` mechanics and the dispatch-based move
are live-verified instead, not something a fake can usefully assert).
289/289 passing under `pytest` across the full relevant suite (272 prior
+ 17 new).

## Follow-up fix: drawing_objects.py's combine/split/bind/unbind, re-enabled

Direct consequence of the dispatch-safety correction above. Re-tested
`combine_shapes_live`/`split_shape_live`/`bind_shapes_live`/
`unbind_shape_live` (all P3) through the same real-running-server
methodology draw.py's investigation established (not an external script
that also calls `close()`), and confirmed `.uno:Combine`/`.uno:Split`/
`.uno:Bind`/`.uno:Unbind` are all safe to dispatch from the extension's
own in-process code -- the server stayed healthy and `soffice.bin`
stayed alive through every call below, including the one that failed.
`insert_embedded_object_live`/`activate_embedded_object_live` remain
`status="stub"` -- that scope limit was never about dispatch safety
(embedded-object creation is broad/uncertain in scope; OLE activation
wasn't exploration-tested this pass either), so it's unaffected by this
correction.

**`combine_shapes_live`** implemented and live-verified end to end:
combined a rectangle and an ellipse, confirmed via an independent raw
UNO read that the page's shape count dropped from 2 to 1 and the result
is a real bezier-path shape; confirmed the two original `shape_id`s no
longer resolve (`OBJECT_NOT_FOUND`) -- combine is destructive, unlike
`group_shapes_live`, whose member handles deliberately stay valid (see
the `drawing_objects.py` pass's own group/ungroup finding). Made
defensive against a combine that doesn't reduce to exactly one shape
(raises a clear `UNSUPPORTED_CAPABILITY`-mapped error instead of
crashing downstream trying to read `.Position` off a multi-item
selection), mirroring the fix `bind_shapes_live` needed below --
though combine itself worked correctly in every case tested this pass.

**`split_shape_live`** live-verified to execute without error against a
combined shape and register the resulting shape(s), but the shape count
returned was 1, not the 2 a full "undo of combine" might imply. Not
treated as a bug: `split_shape_live`'s own spec purpose text
("Split a combined shape") doesn't guarantee restoring the original
shape count, and the tool correctly reports whatever `.uno:Split`
itself returns (same "report whatever UNO returns, don't second-guess
it" principle `calc_sheets.py`'s `queryPrecedents` finding already
established) -- flagged here as an observed characteristic, not
verified against every possible combined-shape structure.

**`bind_shapes_live`, a real bug found and fixed by live-verifying:**
the initial implementation assumed `.uno:Bind` always produces one
bound shape (same pattern as combine), and calling
`get_shape_summary()` on whatever came back crashed with a raw
`AttributeError` on `.Position` (surfaced as `UNO_EXCEPTION` to the
caller) when it didn't. Live-testing found `.uno:Bind` genuinely
**no-ops** -- leaves the input shapes completely unchanged, selection
count stays at the input count -- for both primitive shapes
(rectangle/ellipse) and actual polygon/freeform shapes in this
LibreOffice 26.2 build; not a dispatch-safety problem (confirmed the
server stayed healthy and `soffice.bin` stayed alive through the
no-op), genuinely no bound shape gets created either way. Fixed to
detect this explicitly (selection count didn't reduce to 1) and raise
a clear, documented `UNSUPPORTED_CAPABILITY` error instead of crashing
-- this also matches the tool's own spec purpose text ("Bind shapes
into one path/object **where supported**") exactly: in this build, for
the shape types tested, it isn't. Re-verified live post-fix: the error
is now clean and documented, the server stays healthy, and -- because
the tool layer only unregisters the input `shape_id`s *after* a
successful bridge call -- a failed bind leaves the original `shape_id`s
correctly still resolvable (confirmed independently).

**`unbind_shape_live`**: implemented symmetrically with `split_shape_live`
on the reasonable assumption `.uno:Unbind`'s UNO behavior mirrors
`.uno:Split`'s, but **not independently live-verified against a
genuinely-bound shape this pass** -- `bind_shapes_live` could not
produce one to unbind (see above), so there was nothing real to test
`unbind_shape_live` against. Flagged explicitly rather than silently
presented as verified; a future pass with a LibreOffice build/shape
combination where Bind actually produces something should close this
gap.

**Testing:** 4 new/replaced tests in `tests/test_drawing_objects.py`
(the fake models Bind as always succeeding, since exercising the
tool-layer plumbing for the success path is a legitimate and useful
thing to test even though real UNO sometimes no-ops -- the no-op
behavior itself is exactly the class of defect only live-testing could
catch, and is documented above, not asserted in the fake). 293/293
passing under `pytest` across the full relevant suite (289 prior + 4
new).

## Real implementation pass: charts.py (19 of 20 tools)

Second of `charts.py`/`impress.py`/`draw.py`, per Buddy's go-ahead --
draw.py done, this pass, impress.py next. 19 of 20 tools real;
`add_chart_series_live` stays `status="stub"` (see scope below).

**Scope, deliberate: Calc-native embedded charts only this pass.**
`chart_id` resolves via `sheet.getCharts()` (`XTablesSupplier`'s native
named chart collection) -- the UNO-guaranteed-unique-`Name` container
`docs/OBJECT_HANDLE_DESIGN.md` already designed this exact resolution
for, no `ObjectRegistry` needed, same category as sheets/Writer tables.
Every tool raises a documented `NotImplementedError` (mapped to
`UNSUPPORTED_CAPABILITY`) against a non-Calc document; Writer/Impress/
Draw embedded charts (a generic `OLE2Shape` wrapping a chart document,
no dedicated named container) are left for a follow-up.
`series_id` is a plain string index into `XChartType.getDataSeries()`
(0-based) -- chart2 data series have no persistent name/identity of
their own, only positional order, mirroring `writer_text.py`'s
1-based-paragraph-ordinal precedent for "no natural identity, use
position." A chart's real geometry/export both go through its backing
`OLE2Shape` on the sheet's draw page, found by matching
`PersistName == chart_id` -- live-verified this is the actual UNO
linkage; the shape's own `.Name` is empty and `TableChart` itself
exposes no `Position`/`Size`. `create_chart_live`/`set_chart_data_live`
both keep `status="implemented"` since their `source`/`source_range`
path is real; only their `data`-array branch raises `NotImplementedError`
(building a chart2 data sequence from raw in-memory values needs
`XDataProvider` construction not exploration-tested this pass).
`add_chart_series_live` has no real code path at all -- same precedent
as `drawing_objects.py`'s `insert_embedded_object_live`/
`activate_embedded_object_live` -- so it stays a pure `status="stub"`
`NOT_IMPLEMENTED` response rather than a function that always raises
through the bridge.

**Two chart2 creation-context gotchas, opposite of each other, mapped
during exploration:** chart2 sub-objects (`Title`, `FormattedString`,
a new `XChartType`, `ErrorBar`, a regression-curve service) must be
created via the global `smgr.createInstanceWithContext(...)` --
`chart_doc.createInstance(...)` silently returns `None` for all of
them. This is the *opposite* of `draw.py`'s `Background` finding
(`doc.createInstance(...)` required there, global `smgr` returns
`None`) -- both now documented in `uno_bridge.py` next to the code they
apply to so a future pass doesn't have to rediscover either by trial
and error. Also mapped: `XDiagram` has no `getAxisByDimension` (an
earlier exploration script's crashed partial output was misread as
confirming it did; re-verified carefully via `CoreReflection`
introspection of `XDiagram`'s actual method list) -- the real location
is `coordinateSystem.getAxisByDimension(dimension, index)`; and
`com.sun.star.chart.ChartDocument`'s legacy `Title = "string"` shortcut
doesn't exist on chart2 -- its `Title` property is `XTitle`-typed, set
via a real `Title`/`FormattedString` object, not a plain string.

**Two real bugs found live-verifying, both fixed and re-verified
post-fix:**

1. `set_chart_legend_live`'s `position` mapping used `"top"`/`"bottom"`
   → `"TOP"`/`"BOTTOM"`, which don't exist:
   `com.sun.star.chart2.LegendPosition` (confirmed via `CoreReflection`
   and by exhaustively trying every plausible enum literal against a
   real legend) only has `LINE_START`/`LINE_END`/`PAGE_START`/
   `PAGE_END`/`CUSTOM` -- calling with `position="bottom"` raised a raw
   `UNO_EXCEPTION` ("value BOTTOMis unknown in enum ..."), not a clean
   tool response. Fixed to alias `"top"`→`PAGE_START`, `"bottom"`→
   `PAGE_END` (spatially above/below the diagram, matching the enum's
   actual semantics), `"left"`/`"right"`→`LINE_START`/`LINE_END`.
   Re-verified live: both `"top"` and `"bottom"` now land the
   documented enum value, confirmed by an independent raw UNO read of
   `legend.AnchorPosition`.
2. `set_chart_data_labels_live` silently dropped every property it was
   given (`ShowNumber`, `ShowCategoryName`, etc.) -- reported `applied:
   []` with a warning listing them all as "unknown/unsettable." These
   aren't direct settable properties on `XDataSeries` at all; they're
   fields of its `Label` property, a `com.sun.star.chart2.
   DataPointLabel` struct (confirmed via `getPropertySetInfo()`/reading
   the live struct). Fixed with a read-modify-write on the whole struct
   for the 6 known `DataPointLabel` field names, falling through to the
   existing direct-property path for everything else (e.g.
   `LabelPlacement`, which *is* a real direct property). Re-verified
   live: `ShowNumber`/`ShowCategoryName` genuinely land on the series'
   `Label` struct, confirmed by an independent raw UNO read.

**Headless-mode gotcha hit and fixed during this pass's own live
verification (not a code bug, an environment/procedure one) --
recorded here since it will hit `impress.py` too:** a freshly-launched
headless `soffice.exe`'s `desktop.getCurrentComponent()` returns `None`
even immediately after loading a document, with no window manager to
give any frame focus. Every tool call that resolves the active document
(the common no-`document_id` path) failed with `NO_ACTIVE_DOCUMENT`
until the loaded document's frame was explicitly activated:
`doc.getCurrentController().getFrame().activate()`. Confirmed via a
before/after raw UNO check (`getCurrentComponent()` genuinely `None`
before, genuinely resolves to the right document after). Also hit and
fixed separately: `unopkg add`/`unopkg remove` must target the *same*
LibreOffice user profile the test `soffice.exe` instance launches
against -- an isolated `-env:UserInstallation=...` override on the
`soffice.exe` launch (this pass's own first attempt, to keep the
default profile clean) silently loaded zero extensions, since
`unopkg`'s install went to the default profile instead; the protocol
handler wasn't even instantiable (`createInstanceWithContext` on its
own service name returned `None`) until both commands targeted the
same profile.

**Live-verified end to end on a fresh headless LibreOffice 26.2
instance, independently checking real document state after every
call** (not trusting each tool's own success response, and re-verifying
both bug fixes post-fix on a fresh rebuild): seeded a real range,
`create_chart_live` (confirmed via independent raw UNO read: real
`BarChartType`, correct series count from the source range);
`list_charts_live`/`get_chart_live`; `set_chart_type_live` (confirmed
type genuinely changed to `LineChartType`); `set_chart_data_live`;
`set_chart_title_live` with `subtitle` (confirmed both lines landed on
the real `Title`/`FormattedString` object); `set_chart_legend_live`
post-fix; `get_chart_series_live`/`set_chart_series_live` (confirmed
`Color` genuinely changed on the real series); `set_chart_axis_live`
(confirmed `Minimum`/`Maximum` landed on the real Y-axis `ScaleData`);
`set_chart_data_labels_live` post-fix; `set_chart_gridlines_live`;
`add_chart_trendline_live`/`remove_chart_trendline_live` (confirmed a
real regression curve was added then removed via
`series.getRegressionCurves()`); `set_chart_error_bars_live`;
`set_chart_geometry_live` (confirmed real `Position`/`Size` on the
backing shape); `export_chart_live` (confirmed a real 454x340 PNG file
on disk); `remove_chart_series_live`/`delete_chart_live` (confirmed via
`list_charts_live` returning to empty). `add_chart_series_live`
confirmed absent from the REST bridge's execution surface, consistent
with `drawing_objects.py`'s two established stubs. `tools_count: 214`
throughout (both before and after the rebuild that carried the two
fixes -- `create_chart_live` etc. were already counted in the pre-fix
`214`, since `status="implemented"` was set from the start; the fixes
were within already-implemented tool bodies).

**Testing:** `tests/test_charts.py`, 22 new tests (a `FakeUnoBridge`
modeling charts as a dict keyed by `chart_id`, mirroring the real
`UNOBridge` chart2 methods' public signatures -- tool-layer plumbing
only, not real chart2 mechanics, which are live-verified instead).
`tests/test_tool_scaffold_contract.py` gained
`IMPLEMENTED_CHART_TOOL_NAMES` and
`test_implemented_chart_tools_are_marked_implemented`, following the
`drawing_objects.py` mixed-module precedent; also added the
pre-existing `test_implemented_drawing_object_tools_are_marked_implemented`
to this file's own `__main__` list, which had never been added when
that test was written (a `pytest`-only gap -- `pytest` auto-discovers
it regardless, so it was never actually skipped by the suite, just
absent from direct `python tests/test_tool_scaffold_contract.py`
runs). 318/318 passing under `pytest` across the full relevant suite
(293 prior + 22 charts.py + 1 contract + 2 carried over from
`tests/test_document_registry.py`'s identity-dedup coverage, committed
alongside this pass -- see the preceding commit's message for that
unrelated leftover fix from the earlier PyUNO robustness sweep).

**Follow-up (v2.0.3): `add_chart_series_live` went real.** Real
mechanism turned out to be `XDataProvider.createDataSequenceByRangeRepresentation`
against a scratch sheet range past the chart's used area (chart2's
public `XDataProvider` has no value-array constructor, confirmed
against the interface reference), wired into a new chart2 `DataSeries`
via `XDataSink.setData()`. `charts.py` is now 20/20 real, moved into
`test_tool_scaffold_contract.py`'s `IMPLEMENTED_MODULES` (the
mixed-module `IMPLEMENTED_CHART_TOOL_NAMES`/
`test_implemented_chart_tools_are_marked_implemented` pair mentioned
above no longer exists). One real bug caught live-verifying: an
initial version wrote `categories` to real sheet cells but never
attached them to any chart2 data sequence, silently orphaning the
values -- caught by independently reading the raw
`XDataSeries.getDataSequences()` back after a REST round trip, not by
trusting the tool's own response. See `uno_bridge.py`'s
`add_chart_series()` docstring and the README's `## v2.0.3` changelog
entry for the full mechanism and verification detail.

## Real implementation pass: impress.py (34 of 41 tools)

Third and last of charts.py/impress.py/draw.py per Buddy's go-ahead --
draw.py and charts.py done, this one closes out the assigned set. 34 of
41 tools real; the other 7 stay `status="stub"` in two clusters, both a
genuine "not exploration-tested/not verifiable this pass" scope limit,
same precedent as `insert_embedded_object_live` before them
(`add_chart_series_live` has since gone real -- see the charts.py
section's v2.0.3 follow-up above):

- `add_animation_live`/`update_animation_live`/`delete_animation_live`/
  `reorder_animations_live`: constructing or mutating a real
  `com.sun.star.animations.XAnimationNode` preset tree (the Parallel/
  Sequence container structure LibreOffice's own entrance/emphasis/exit
  effects use) is genuinely complex and wasn't attempted this pass.
  `list_animations_live` (a read-only recursive tree walk) **is** real.
- `next_slideshow_effect_live`/`previous_slideshow_effect_live`/
  `goto_slideshow_slide_live`: all three need a live
  `com.sun.star.presentation.XSlideShowController`
  (`Presentation.Controller`) -- live-verified this pass to always be
  `None` in headless mode, confirmed via an independent readback right
  after `pres.start()` (which itself returns without error). No window
  manager to render a slideshow view to, a real environment limit, not a
  code defect. `start_slideshow_live`/`stop_slideshow_live` (which only
  need `XPresentation.start()`/`end()`, not the Controller) **are** real.

**`move_slide_live`/`duplicate_slide_live`'s `destination` carry a
flagged verification gap, not a stub** -- the code is real and correct
(the exact same dispatch-based reorder mechanism draw.py proved safe and
effective for Draw: `_move_draw_page_to_index()`, already
document-type-agnostic, is reused directly, not duplicated), but this
pass could not observe it taking effect for an *Impress* document in
headless mode, confirmed through extensive live testing: the dispatch's
own `IsEnabled` status genuinely reports `True` (checked via a real
`XStatusListener`); the dispatch pipeline itself is confirmed working in
this exact setup (`.uno:DuplicatePage` on the same frame visibly added a
page, as a control test); but repeated attempts to reorder --
`setCurrentPage()`, `select()`, both together, dispatching via
`frame.queryDispatch().dispatch()`, via `DispatchHelper`, via
`desktop.getCurrentFrame()`, with up to 1.5s settle time, and even after
dispatching `.uno:DiaMode` to try switching to Slide Sorter view first --
never produced an observed reorder in `doc.getDrawPages()`, live-verified
again through the actual tool layer (not just raw exploration scripts):
`move_slide_live` reports `success: true` but `list_slides_live`
afterward shows the original order unchanged. Flagged explicitly, not
silently presented as verified -- left for a follow-up with a real
GUI/virtual-display session, the same category as `unbind_shape_live`'s
"could not produce a real bound shape this pass" gap in the
`drawing_objects.py` pass.

**AutoLayout has no queryable name table via `CoreReflection`** (unlike
`chart2`'s `LegendPosition`, it isn't a discoverable IDL enum/constants
group) -- only 4 values were empirically verified by inspecting the real
placeholder shapes a fresh slide gets at each one: `0` = title+subtitle,
`1` = title+content, `19` = title only, `20` = blank.
`set_slide_transition_live`'s `effect` similarly accepts a raw
`TransitionType` integer or the literal `"none"` (both empirically
verified: `TransitionType`/`TransitionSubtype` default to `0`/`0` on a
fresh slide, arbitrary ints accepted unvalidated) -- the full
ODF/OOXML named-transition table wasn't mapped this pass. Both are
honest, bounded scope limits rather than guessing at the rest of either
table and risking a repeat of this pass's own two live-found bugs below.

**Four real bugs found live-verifying, all fixed and re-verified
post-fix on a rebuild:**

1. `create_master_page_live` raised a raw `UNO_EXCEPTION: "invalid
   STRING value!"` -- `XDrawPages.insertNamedNewByIndex(index, name)`
   takes the index *first*, name *second*; the initial implementation
   had them backwards (an easy mistake -- `dir()` introspection lists
   the method name but not its parameter order, and this specific method
   was never actually live-tested during exploration, only assumed from
   the interface listing). Fixed and re-verified: a real named master
   page is created and `apply_master_page_live` (which depends on
   resolving it by name afterward) now works too.
2. `get_speaker_notes_live`/`set_speaker_notes_live` raised
   `"Notes page has no NotesShape."` even on a notes page that
   demonstrably has one -- the real `NotesShape`'s own
   `supportsService("com.sun.star.presentation.NotesShape")` returns
   `False` despite `getShapeType()` returning exactly that string.
   Presentation placeholder shapes expose their role through their shape
   *type*, not through `XServiceInfo`, unlike most other shapes in this
   codebase. Fixed to key off `getShapeType()` instead; re-verified live
   (set then read back real notes text).
3. `get_presentation_settings_live` raised
   `"'str' object has no attribute 'Name'"` -- `XPresentation.FirstPage`
   is already a plain slide-name string (empty string when unset), not a
   page object reference, contrary to this pass's initial assumption.
   Fixed to stop calling `.Name` on it; `set_presentation_settings_live`
   still resolves its own `FirstPage` input through `_resolve_slide()`
   (which accepts an index or a name, matching the tool's own flexible
   parameter) and extracts `.Name` from *that* result before the actual
   UNO write, which is correct -- only the *get* side had the bug.
4. `set_slide_transition_live`'s `duration` and `auto_after` reported
   `duration` as silently clobbered when both were given in the same
   call -- live-verified `page.Duration` (`auto_after`) and
   `page.HighResDuration` (`duration`) are two-way coupled in this
   LibreOffice build (setting either syncs the other to a rounded copy:
   `Duration=4.0` makes `HighResDuration` read back `4.0`;
   `HighResDuration=2.5` afterward makes `Duration` read back `3`,
   `round(2.5)`), not kept independent as their names/spec purposes
   would suggest. Fixed by applying `auto_after` before `duration` so an
   explicit `duration` is always honored exactly; `auto_after` is only
   *approximately* honored when both are given together, and the tool
   now returns a warning saying so rather than silently claiming both
   landed exactly as requested.

**Live-verified end to end on a fresh headless LibreOffice 26.2
instance, independently checking real document state after every
call** (not trusting each tool's own success response, and re-verifying
all four bug fixes post-fix on a rebuild): slide CRUD --
`insert_slide_live` with `layout="title_content"`/`"blank"` (confirmed
via an independent raw UNO read the real placeholder shape counts
matched: 2 shapes for title+content, 0 for blank);
`rename_slide_live`/`hide_slide_live`/`get_slide_layout_live`;
`set_slide_background_live`; master pages (`list`/`create`/`apply`,
post-fix); speaker notes (post-fix); slide transitions (post-fix,
including the `duration`/`auto_after` coupling warning);
`list_animations_live` (confirmed it walks the real
`ParallelTimeContainer` root node returned by a fresh slide's
`AnimationNode`); `set_shape_click_action_live` (confirmed a real
shape's `OnClick` property genuinely changed to `NEXTPAGE`); presentation
settings (post-fix); the full custom-show lifecycle (create/list/update/
delete, confirmed slide membership survives an update); `start_slideshow_
live`/`stop_slideshow_live` (execute without error; `Presentation.
Controller` confirmed `None` throughout, the documented headless limit);
`export_slide_image_live`/`export_all_slides_images_live` (confirmed
real PNG files on disk, correct magic bytes); `duplicate_slide_live`;
`delete_slide_live` (confirmed via `list_slides_live` returning to the
prior count); `move_slide_live` (confirmed the flagged non-effect above,
through the actual tool layer, not just exploration scripts).
`tools_count: 248` throughout (214 + 34).

**Testing:** `tests/test_impress.py`, 31 new tests (a `FakeUnoBridge`
modeling slides/masters/notes/transitions/custom shows as plain dicts/
lists, mirroring the real `UNOBridge` methods' public signatures --
tool-layer plumbing only, not real `XDrawPages`/`XPresentation`/
`XAnimationNode` mechanics, which are live-verified instead).
`tests/test_tool_scaffold_contract.py` gained
`IMPLEMENTED_IMPRESS_TOOL_NAMES` and
`test_implemented_impress_tools_are_marked_implemented`, following the
`drawing_objects.py`/`charts.py` mixed-module precedent. 361/361 passing
under `pytest` across the full relevant suite (319 prior + 11 more
`tests/test_uno_datetime.py` coverage found sitting uncommitted in the
shared worktree mid-pass and committed separately -- see that commit's
own message -- + 31 impress.py + 1 contract).

**Note on this pass's own working conditions:** twice during this pass,
`git status` showed unrelated, complete, well-formed changes already
sitting in the working tree that this session hadn't made in its current
context window -- once the tail end of the earlier PyUNO robustness
sweep (task tracked as done, but never actually committed before a
context compaction), and once a second, later addition of
`tests/test_uno_datetime.py` coverage for functions that first commit
had already added and pushed. Both were committed separately from this
pass's own charts.py/impress.py work rather than folded in or discarded,
consistent with this project's practice of never silently dropping
found-but-unexplained work. The second occurrence in particular suggests
something else is also writing to this exact worktree
(`E:\Tools\mcp-libre-scaffold`) during this session -- flagged for Buddy/
Brian, not something this pass's own commits attempt to resolve.

## Real implementation pass: calc_data.py (39 of 42 tools)

First of the four remaining Phase B/C scaffolds Buddy assigned after the
draw/charts/impress trio closed out (calc_data.py -> calc_page.py ->
writer_layout.py -> writer_tables.py, 138 tools total). 39 of 42 tools
real; create_external_link_live/refresh_external_link_live/delete_
external_link_live stay `status="stub"` -- doc.ExternalDocLinks' write
side (adding a new link, vs. list_external_links_live's read-only
enumeration, which IS real) wasn't exploration-tested this pass, same
honest-scope-limit precedent as insert_embedded_object_live (these three
external-link tools, add_chart_series_live, and add_animation_live have
all since gone real -- see each module's own follow-up note).

**Conditional formats use the legacy per-range `range.ConditionalFormat`
(`XSheetConditionalEntries`), not the newer `sheet.ConditionalFormats`/
`XConditionalFormat` API** -- explored both; the newer API's
`createEntry(long, long)` has a genuinely different, much less tractable
signature than its own IDL parameter *types* implied (neither parameter
is a condition-type enum or a cell address, both are just `long`, and
the values that seemed obvious raised `CannotConvertException`) and
wasn't successfully mapped in the time available. The legacy API
(`addNew()` takes a plain sequence of `PropertyValue`:
Operator/Formula1/Formula2/StyleName) is simpler, well-documented, and
fully live-verified working.

**A real, load-bearing design bug found and fixed mid-pass, before it
ever reached live-verification against the real server:** the first
draft registered conditional-format entries and pivot tables as raw
`(range, entry)`/`XDataPilotTable` object pairs in `ObjectRegistry`,
following the exact pattern `drawing_objects.py`'s shapes established.
Live-verifying `add_conditional_format_live` immediately after
`list_conditional_formats_live` showed two *different* `rule_id`s for
what should have been the same single rule, and `update_conditional_
format_live`/`delete_conditional_format_live` both failed with
"this rule no longer exists" against a rule that plainly still existed.
Root cause, confirmed via a raw UNO script: a legacy `ConditionalFormat`
entry does **not** compare equal to itself across two separate fetches
(`cf.getByIndex(i) == cf.getByIndex(i)` from two different
`range.ConditionalFormat` reads is `False`) -- unlike shapes/documents
elsewhere in this codebase, where `ObjectRegistry`'s own docstring
("PyUNO proxies implement `__eq__`/`__hash__` consistently for the same
underlying UNO object") holds. Fixed by switching conditional-format
`rule_id` to a `(sheet_name, range_string, index)` address instead of an
object reference, re-resolved fresh on every call -- the honest cost,
documented in `uno_bridge.py`, is the same "filled slot is not the right
slot" risk any raw index carries if an unrelated `add`/`delete` on the
same range shifts the index first, but at least a reproducible,
*working* mechanism instead of one that never worked at all. Pivot
tables hit the identical `list_pivot_tables_live`-mints-a-different-id
symptom for the same underlying reason (`XDataPilotTable` doesn't
compare equal across fetches either) -- **not** fixed the same way,
since `get_pivot_table_live`/`refresh_pivot_table_live`/
`delete_pivot_table_live` all operate on the *held* reference directly
(reading `.Name`/`.OutputRange` or calling `.refresh()`), never
re-locating it by comparison, so every pivot_id still works correctly
for its own subsequent calls -- only repeated `list_pivot_tables_live`
calls mint a fresh, non-matching id for the same underlying pivot each
time, a real but narrower and lower-priority gap, documented rather than
fixed this pass.

**Three more real bugs found live-verifying, all fixed and re-verified
post-fix on a rebuild:**

1. `sort_range_live` reported success but never actually reordered
   anything -- reconstructing `range.createSortDescriptor()`'s result as
   a plain dict and rebuilding fresh `PropertyValue`s from it silently
   dropped `SortFields`' typing: a plain Python tuple of
   `TableSortField` structs is accepted without error by `range.sort()`
   but has no effect, while every *other* sequence-valued property in
   this codebase (`FilterFields`, `DataPilotFields` entries, etc.)
   works fine as a plain tuple. Root-caused via a bisecting live script;
   fixed by wrapping the reconstructed value in
   `uno.Any("[]com.sun.star.table.TableSortField", ...)` explicitly.
2. `list_scenarios_live` raised a raw `UNO_EXCEPTION: "Comment"` --
   guessed property name; the real one (confirmed via `dir()` on a live
   scenario sheet) is `ScenarioComment`.
3. (Documented as a design choice, not a bug, but worth noting alongside
   the others): `goal_seek_live` explicitly writes the converged result
   back to the variable cell -- live-verified `doc.seekGoal()` itself
   computes and returns the answer but leaves the cell's value
   unchanged, unlike Calc's own Goal Seek dialog (which commits on
   accept). Matched the dialog's behavior since a caller asking this
   tool to "perform goal seek" almost certainly wants the sheet updated.

**Live-verified end to end on a fresh headless LibreOffice 26.2
instance, independently checking real document state after every
call** (not trusting each tool's own success response, and re-verifying
all fixes post-fix on a rebuild): named range CRUD; `sort_range_live`
post-fix (confirmed real descending reorder); `apply_filter_live`/
`clear_filter_live` (confirmed real row visibility changes and their
reversal); the full conditional-format lifecycle post-fix (confirmed a
real rule's `ConditionalFormat.Count` genuinely reaches 0 after delete);
data validation get/set/clear (confirmed `Formula1` round-trips through
a real `LIST` validation); `create_subtotals_live`/`remove_subtotals_
live` (confirmed real grouped Sum/Grand-Sum rows appear and the sheet
structure reverts cleanly); the full pivot-table lifecycle (confirmed
real, correctly-aggregated output data -- East=250, West=200,
Total=450 -- and confirmed deletion via `DataPilotTables.getCount()`
independently); the full scenario lifecycle post-fix; `goal_seek_live`
(confirmed the variable cell genuinely changed to the converged value);
`solver_solve_live` (confirmed a real constrained-minimization result:
minimizing x²-4x over [0,10] converged to x≈2, value≈-4, the correct
analytic minimum); database range CRUD; `list_external_links_live`;
CSV import/export (confirmed real file content on both sides, including
non-ASCII-safe quoting); row/column grouping (calls succeed; no direct
per-row/column outline-level readback property exists on `TableRows`/
`TableColumns`, live-verified via a full property-name dump, so this is
call-succeeds verification only, documented rather than silently
presented as fully confirmed). `tools_count: 287` throughout (248 +
39).

**Testing:** `tests/test_calc_data.py`, 21 new tests (a `FakeUnoBridge`
mirroring the real `UNOBridge` methods' public signatures, including
the `(sheet, range, index)`-address `ObjectRegistry` round-trip for
conditional formats -- tool-layer plumbing only, real
`XSheetCellRange`/`XDataPilotTables`/`XSolver` mechanics are
live-verified instead). `tests/test_tool_scaffold_contract.py` gained
`IMPLEMENTED_CALC_DATA_TOOL_NAMES` and `test_implemented_calc_data_
tools_are_marked_implemented`, following the established mixed-module
precedent. 383/383 passing under `pytest` across the full relevant
suite (361 prior + 21 calc_data.py + 1 contract).

## Real implementation pass: calc_page.py (all 15 tools)

Second of the four remaining Phase B/C scaffolds (calc_data.py done ->
calc_page.py -> writer_layout.py -> writer_tables.py). All 15 tools
real. Page layout resolves through the sheet's own `PageStyle` (a
`com.sun.star.style.PageStyle` in the workbook's `"PageStyles"`
`StyleFamilies` family -- the same family `styles.py` already resolves
via `_get_style_family()`), not a direct sheet property.
`list_number_formats_live` has a documented scope limit, surfaced in
both its own `purpose=` string and `uno_bridge.py`'s docstring per the
now-established practice from the calc_data.py pass's pivot-table
caveat: `XNumberFormats` has no "list every format" API (keyed/query
access only, live-verified via its actual method list), so it lists the
standard format for each well-known `NumberFormat` category instead of
every custom format ever created in the document.

**Two real bugs found live-verifying, both fixed and re-verified
post-fix on a rebuild:**

1. `add_cell_comment_live` with an `author` raised a raw `UNO_EXCEPTION`
   ("property at index 6 is readonly") -- `Author` is read-only in this
   LibreOffice build (auto-derived from the user identity, not
   settable), confirmed via the exact property-index error. Worse than
   just failing cleanly: on the *update* path the comment's `text` had
   already been written via `setString()` before the `Author` write
   raised, so the whole call aborted with an exception even though the
   text change should have counted as a success. Fixed to catch the
   `Author` write specifically, report `author_applied: false` in the
   result, and have the tool layer turn that into a warning rather than
   a failure -- the text always lands; the caller finds out honestly
   whether the author did too.
2. (Caught during exploration, before it became a live-tool bug, but
   worth noting alongside the real ones): `list_number_formats_live`'s
   `NumberFormat` category constants needed
   `from com.sun.star.util import NumberFormat` at module level, not a
   locally-scoped import -- since `_NUMBER_FORMAT_CATEGORIES` is a
   class-body dict literal evaluated at class-definition time (i.e. at
   `uno_bridge.py`'s own import time), a wrong import location would
   have failed the *entire extension's* load, not just this one tool.
   Verified the correct import shape via a standalone script before
   adding it, rather than guessing and finding out at deploy time.

**Live-verified end to end on a fresh headless LibreOffice 26.2
instance, independently checking real document state after every
call** (not trusting each tool's own success response, and re-verifying
the comment-author fix post-fix on a rebuild): `get_sheet_page_layout_
live`/`set_sheet_page_layout_live` (confirmed real `Width`/`Height`/
`IsLandscape`/margins/`PageScale` changes on the underlying `PageStyle`,
modulo ~1-unit mm-to-1/100mm float rounding); `set_print_area_live`/
`clear_print_area_live` (confirmed real `PrintAreas`); `set_repeating_
print_rows_live`/`set_repeating_print_columns_live` (confirmed real
`TitleRows`/`TitleColumns`); the cell-comment lifecycle including the
author fix (confirmed real annotation text via an independent read, and
confirmed `Author` genuinely stays `"Unknown Author"` -- the honest
outcome the warning describes); `protect_sheet_live`/`unprotect_sheet_
live`/`set_cell_protection_live` (confirmed real `CellProtection.
IsLocked`/`IsHidden` changes -- and along the way, confirmed live that
Calc silently ignores `CellProtection` writes while the sheet itself is
still protected, which the first verification attempt hit by testing
in the wrong order; re-verified in the correct order afterward, not a
code defect); the full number-format lifecycle (confirmed a real,
correctly-formatted cell display: `1,234.50 USD` after applying a
custom-created format). `tools_count: 302` throughout (287 + 15).

**Testing:** `tests/test_calc_page.py`, 12 new tests (a `FakeUnoBridge`
mirroring the real `UNOBridge` methods' public signatures, including a
dedicated test for the comment-author warning path -- tool-layer
plumbing only, real `PageStyle`/`XSheetAnnotations`/`XNumberFormats`
mechanics are live-verified instead). Unlike `charts.py`/`impress.py`/
`calc_data.py`, this module is *not* mixed -- all 15 tools are real, so
`calc_page` was added to `IMPLEMENTED_MODULES` in
`tests/test_tool_scaffold_contract.py` directly rather than getting its
own `IMPLEMENTED_CALC_PAGE_TOOL_NAMES` set. 395/395 passing under
`pytest` across the full relevant suite (383 prior + 11 calc_page.py +
1 for the comment-author warning test added during live-verification).

## Real implementation pass: writer_layout.py (42 of 43 tools)

Third of the four remaining Phase B/C scaffolds (calc_data.py, calc_page.py
done -> writer_layout.py -> writer_tables.py). Page style resolution reuses
`_get_style_family(doc, "PageStyles")`, the same family `styles.py`/
`calc_page.py` already resolve through. Bookmarks are addressed by name
directly (`doc.getBookmarks()` is a real UNO-guaranteed-unique-Name
`XNameAccess`, confirmed live) -- no `ObjectRegistry`, same category as
sheets/Writer tables/Calc's own named charts per
`docs/OBJECT_HANDLE_DESIGN.md`. Fields, hyperlink text ranges, and document
indexes have no natural unique name and resolve `field_id`/`hyperlink_id`/
`index_id` through the same `ObjectRegistry` `drawing_objects.py`
established. `set_chapter_numbering_live` stays `status="stub"` --
live-verified `ChapterNumberingRules.replaceByIndex()` raises a bare
`IllegalArgumentException` even passing back the exact unmodified sequence
`getByIndex()` itself returned; `get_chapter_numbering_live` (read-only) is
real.

**Five real bugs found live-verifying, all fixed and re-verified post-fix
on a rebuild:**

1. `remove_page_break_live` raised a raw `UNO_EXCEPTION` ("Type 0 is not
   supported!") -- the fix set `PageDescName = None` to clear it, but
   `None` isn't a legal value for this string-typed property. Fixed to
   clear with `""` instead, confirmed by reading back the same
   `BreakType`/`PageDescName` state an untouched paragraph starts in.
2. `insert_page_number_field_live`/`insert_page_count_field_live` never
   set `NumberingType` explicitly, and the UNO default for a freshly
   created field isn't Arabic -- live-verified page 2 rendered as `"B"`
   (alphabetic numbering), not `"2"`. Fixed to default to `ARABIC` and
   added a `format` parameter (`arabic`/`roman_upper`/`roman_lower`/
   `alpha_upper`/`alpha_lower`) for callers who want something else;
   re-verified `"2"` by default and `"II"` for `roman_upper`.
3. `insert_hyperlink_live` silently produced a hyperlink whose `HyperLinkURL`
   never applied, discoverable only by reading the property back off a
   text-portion scan -- the tool's own success response gave no sign of
   it. Two approaches failed before landing on a fix: setting the property
   on a cursor positioned *before* inserting the display text (the
   property never applies to text that doesn't exist yet), and inserting
   with `bAbsorb=False` then re-selecting the range with a second cursor
   snapshotted before the insert (that second cursor tracks the live edit
   and moves forward right along with it, so the "selection" it ends up
   with is zero-width and the property set silently no-ops on it). Fixed
   by inserting with `bAbsorb=True`, which leaves the cursor itself
   selecting exactly the text it just inserted.
4. `insert_cross_reference_live` raised `"enum com.sun.star.text.
   ReferenceFieldSource is unknown"` -- `ReferenceFieldSource`/
   `ReferenceFieldPart` are plain `SHORT`-typed properties, not real UNO
   enums (confirmed via `getPropertySetInfo()` reporting `TypeClass
   SHORT`), so `uno.Enum(...)` can't resolve them. Fixed to use
   `uno.getConstantByName()` against the `com.sun.star.text.
   ReferenceFieldSource`/`ReferenceFieldPart` constant groups instead --
   the same mechanism `insert_caption` already used correctly for
   `NumberingType`/`SetVariableType`. Re-verified bookmark-sourced text
   and page references render correctly (`"Target"` and `"1"`).
5. `set_line_numbering_live` raised `"property ... is readonly"` on
   `doc.LineNumberingProperties = lnp` -- worse than a clean failure, the
   preceding in-place field mutations (`lnp.IsOn = ...` etc.) had *already
   taken effect* on the live document before that final write-back threw,
   so the tool reported failure on a call that had, in fact, succeeded.
   `LineNumberingProperties` turned out to be a live-linked reference, not
   a value-type struct snapshot -- mutating its fields applies immediately;
   the write-back was both unnecessary and read-only. Fixed by dropping
   it; re-verified a clean `success: true` with the correct state on
   readback.

**Id-churn caveat, confirmed for two more object kinds this pass:**
hyperlink text ranges do NOT compare equal to themselves across two
separate UNO fetches, same gap as calc_data.py's pivot tables --
`insert_hyperlink_live`'s own returned `hyperlink_id` differs from what a
later `list_hyperlinks_live` returns for that same hyperlink, though each
id keeps working for its own later `update`/`remove` call. Documented in
both the module docstring and the two tools' `purpose=` strings per
Buddy's standing note that this belongs in the caller-visible surface.
`list_document_indexes_live`'s proactively-flagged version of the same
risk was tested this pass too: `insert_toc_live`'s own id likewise differs
from a subsequent `list_document_indexes_live` fetch for that same index,
but repeated `list` calls for the same document state returned a *stable*
id across three separate fetches (unlike hyperlinks/pivot tables, where
even list-to-list churns) -- a narrower version of the gap than initially
assumed.

**Live-verified end to end on a fresh headless LibreOffice 26.2 instance,
independently checking real document state after every call** (not
trusting each tool's own success response, and rebuilding/redeploying
after each of the five fixes above): the full page layout/style/preset/
columns/page-break lifecycle; headers/footers including the shared-by-
default `HeaderIsShared`/`FooterIsShared` behavior; all four field-insert
tools plus `update_fields_live`/`delete_field_live`; the full bookmark
lifecycle including `rename_bookmark_live`'s real parameter name
(`old_name`/`new_name`) and a not-found error path; the full hyperlink
lifecycle; both cross-reference variants; `insert_caption_live` against a
real shape (`"Figure 1: A test figure"` confirmed via raw text scan); the
full TOC/alphabetical-index lifecycle including `add_index_mark_live`
(confirmed via a `DocumentIndexMark` text-portion scan, since index marks
carry no visible text of their own); `get_chapter_numbering_live`; the
full line-numbering lifecycle.

**Testing:** `tests/test_writer_layout.py`, 21 new tests (a `FakeUnoBridge`
modeling page styles/headers/footers/bookmarks as plain dicts and fields/
hyperlinks/indexes as plain objects registered through the real
`ObjectRegistry` -- tool-layer plumbing only, real UNO mechanics are
live-verified instead). Mixed module like `charts.py`/`impress.py`/
`calc_data.py`: `IMPLEMENTED_WRITER_LAYOUT_TOOL_NAMES` (42 names) added to
`tests/test_tool_scaffold_contract.py`. 417/417 passing under `pytest`
across the full relevant suite.

## Real implementation pass: writer_tables.py (37 of 38 tools)

Last of the four remaining Phase B/C scaffolds Buddy assigned (calc_data.py,
calc_page.py, writer_layout.py done -> writer_tables.py). Tables/sections
resolve through their own UNO-native unique Name (`getTextTables()`/
`getTextSections()` are both real `XNameAccess` containers, confirmed
live) -- no `ObjectRegistry`, same category as bookmarks/page styles.
Footnotes/endnotes/content controls have no natural unique name and
resolve through `ObjectRegistry` -- a narrower version of calc_data.py's
pivot-table id-churn gap applies (insert's own returned id differs from a
later list fetch for that same object, but list-to-list stays stable),
same shape writer_layout.py's document indexes turned out to have.

Two invented conventions, both documented inline: `convert_text_to_table_
live`'s and `insert_content_control_live`'s `range` parameter -- the only
two `range` params in the whole catalog scaffolded as a bare string
rather than the `{"start": int, "end": int}` object convention -- accept
`"<start>-<end>"` 0-based character offsets.

**Three real bugs found live-verifying, all fixed and re-verified
post-fix on a rebuild:**

1. `sort_table_live` reported success but never actually sorted rows
   correctly -- a fresh test with three distinct values (`banana`,
   `apple`, `cherry`) sorted ascending came back unchanged. Root cause:
   unlike Calc's `sort_range()` (where `TableSortField.Field` is 0-based,
   confirmed and documented that pass), Writer `TextTable`'s own
   `TableSortField.Field` is 1-based -- confirmed by passing back
   `table.createSortDescriptor()`'s own untouched default (which
   pre-fills `Field=1` for a single-column table and sorts correctly)
   versus a rebuilt descriptor with `Field=0` (silently no-ops) versus
   `Field=1` (sorts correctly). Fixed by adding 1 internally when
   building the struct, while keeping the tool-facing `column` parameter
   0-based like every other column reference in the catalog.
2. `convert_table_to_text_live` raised `UNO_EXCEPTION: 'NoneType' object
   has no attribute 'createTextCursorByRange'` -- `table.getAnchor().
   getText()` returns `None` for a table occupying the whole document
   body (`getAnchor()` itself is a valid range, its own `getText()` just
   doesn't resolve). A first fix attempt (`doc.getText().
   createTextCursorByRange(anchor.getStart())`) raised a different error,
   `"Invalid text range"` -- the anchor's start position isn't
   interchangeable with `doc.getText()` for cursor creation in this
   edge case. Fixed by walking `doc.getText()`'s own top-level content
   enumeration to find the table and the element immediately before it
   (or `text_obj.getStart()` if the table is first), both guaranteed to
   belong to the same `XText`.
3. `delete_content_control_live` left a duplicate, empty "ghost" content
   control behind on its first fix attempt (capture text, dispose,
   reinsert) -- live-verified three different removal mechanisms
   (`ContentControl.dispose()`, `doc.getText().removeTextContent()`, and
   both together): none of them actually remove a content control from
   `doc.getContentControls()` in this LibreOffice build. `getCount()`
   stays the same and the surviving entry compares `==` equal to the
   original object -- only the wrapped content gets cleared, never the
   wrapper. Fixed to stop trying to remove the wrapper at all: clears
   content only when `keep_content=False`, and always returns
   `wrapper_removed: false` plus a warning so the caller isn't misled
   into thinking the control is actually gone.

**Also confirmed, not a bug:** `insert_section_live` wrapping a partial
paragraph forces a real paragraph break at the selection boundary
(sections can't occupy less than a full paragraph in ODF) -- the document
grows by one paragraph mark that `delete_section_live`'s
`keep_content=True` path cannot undo, since it's baked into the document
the moment the section is inserted, not something the wrapper itself
owns. Documented in `insert_section()`'s docstring rather than treated as
a defect.

**Live-verified end to end on a fresh headless LibreOffice 26.2 instance,
independently checking real document state after every call** (not
trusting each tool's own success response, rebuilding/redeploying after
each of the three fixes above): the full table lifecycle including
rows/columns/merge/split (confirmed `direction="horizontal"` genuinely
produces more rows, `"vertical"` more columns, via a real cell-name-set
diff) and format/cell-format; the sort fix with three distinct values;
`convert_text_to_table_live`/`convert_table_to_text_live` as an exact
round trip (`Name\tAge\n...` -> table -> `Name,Age\n...`); the full
section lifecycle including both `keep_content` branches; the full
footnote and endnote lifecycles; note settings get/set; the full content
control lifecycle including the honest delete fix; `preview_mail_merge_
live` against a real CSV folder (2 rows read back correctly via SDBC,
plus a real `TextField.Database` field resolving to the correct row
value); confirmed `mail_merge_live` correctly stays absent from the
live tool-dispatch list (same as writer_layout.py's `set_chapter_
numbering_live` stub).

**Testing:** `tests/test_writer_tables.py`, 15 new tests (a `FakeUnoBridge`
modeling tables/sections as plain dicts and footnotes/endnotes/content
controls as plain objects registered through the real `ObjectRegistry` --
tool-layer plumbing only, real UNO mechanics are live-verified instead).
Mixed module like `charts.py`/`impress.py`/`calc_data.py`/`writer_layout.
py`: `IMPLEMENTED_WRITER_TABLES_TOOL_NAMES` (37 names) added to `tests/
test_tool_scaffold_contract.py`. 433/433 passing under `pytest` across
the full relevant suite. This closes out the four-scaffold assignment
(calc_data.py, calc_page.py, writer_layout.py, writer_tables.py).

## What was built

**Shared plumbing (`plugin/pythonpath/tools/`):**

- `registry.py` -- `@register_tool(name, priority, purpose, parameters)`
  decorator + `merge_into()`. Mirrors the `{description, parameters,
  handler}` dict shape `mcp_server.py`'s `_register_tools()` already uses
  for the original 32 tools, so a senior engineer can move a finished
  stub's registration in-place if they'd rather not depend on this package
  at all.
- `envelope.py` -- `build_success()` / `build_error()` implementing the
  spec's section 5 contract (`{success, result, warnings, error,
  document_id, elapsed_ms}`) and the spec's 13 stable error codes, plus a
  scaffold-only `NOT_IMPLEMENTED` code for stub responses.
- `documents.py` -- `DocumentRegistry`, a **real, working implementation**
  (not a stub) of the stable `document_id` handle concept the spec
  requires (section 2) and that did not exist anywhere in the codebase
  before this pass (`uno_bridge.py` only ever resolves "the active
  document"). Thread-safe in-memory register/resolve/unregister/list,
  uuid4 ids, idempotent re-registration of an already-known object.
  Unit-tested with fake document/uno_bridge objects (no live LibreOffice
  needed, since the registry never calls into UNO itself) in
  `tests/test_document_registry.py`, 9/9 passing.
  **Still open, left for a senior engineer** because it needs a live
  LibreOffice/UNO context to build and validate safely: dispose-listener
  eviction, so a document closed by the user outside of any MCP call gets
  cleanly evicted instead of surfacing as a wrapped UNO exception on next
  resolve. `register_document()` takes an unused `on_dispose` hook
  reserved for this -- see the module docstring for the full list,
  including the note that this only covers the top-level `document_id`,
  not the finer-grained handles (`shape_id`, `table_id`, etc.) later
  phases will also need.
  **Now wired into real tool bodies:** `core_runtime.py`'s
  `get_capabilities_live`, `list_tools_live` ("auto" profile), and
  `get_session_state_live` all call `resolve_document()`/`list_documents()`
  for real (see "Real implementation pass" above). Every other tool
  module's stubs still ignore it -- wiring it into each of those is real
  tool-by-tool implementation work, not scaffolding.

**Tool modules, 366 functions across 14 files (308 still stub, 58 real --
all of Phase A -- `core_runtime.py`, `document_lifecycle.py`, `styles.py`,
and 12/14 of `undo_view_selection.py` -- see the "Real implementation
pass" sections above):**

- Phase A: `core_runtime.py` (12, **implemented**), `document_lifecycle.py`
  (22 new, **implemented**, on top of 5 pre-existing), `undo_view_selection.py`
  (14, **12 implemented** -- document-events pair still stub), `styles.py`
  (12, **implemented**).
- Phase B: `writer_text.py` (18 new, on top of 27 pre-existing),
  `writer_layout.py` (43), `writer_tables.py` (38).
- Phase C: `drawing_objects.py` (31), `charts.py` (20), `calc_sheets.py`
  (42), `calc_data.py` (42), `calc_page.py` (15).
- Phase D: `impress.py` (41), `draw.py` (16).

**Tests:**

- `tests/test_tool_scaffold_contract.py` -- registry completeness checked
  **by exact name per module**, not just by count (a tool landing under
  the wrong name, or in the wrong module, fails loudly even if the total
  count still matches); no collisions with the 32 existing compat tools;
  every stub's response shape; `merge_into()` non-destructiveness; the
  error-code set. Run with `python tests/test_tool_scaffold_contract.py`
  or `uv run pytest tests/test_tool_scaffold_contract.py`. 7/7 passing
  locally, 366 tools registered across 14 modules.
- `tests/test_document_registry.py` -- 9 unit tests for `DocumentRegistry`
  against fakes, 9/9 passing.
- `tests/test_host_trust.py` -- 5 unit tests for the HTTP bridge's
  trusted-host/DNS-rebinding guard (from the separate windows-oxt baseline
  cleanup pass, unrelated to the tool scaffold but living in the same
  `tests/` directory), 5/5 passing.

**Integration:** one opt-in hook in `mcp_server.py`
(`_register_scaffold_stub_tools`, merges in all 366 tools via
`tools.merge_into()`, gated by env var
`MCP_LIBRE_ENABLE_SCAFFOLD_STUBS`): additive-only, so the original 32
tools' behavior is unchanged when the flag is unset (the default). This
exists so a senior engineer can flip it on locally and see the new tools
show up in `/tools` while implementing them, without the scaffold
silently expanding the tool surface exposed to any current users of the
extension.

## What is intentionally NOT done

- **No UNO implementation in the remaining 308 tool stubs** (everything
  outside all of Phase A except the document-events pair). They all
  return `NOT_IMPLEMENTED`. Implementing them needs a working
  `uno`/`unohelper` environment inside LibreOffice -- confirmed working
  end-to-end for 58 tools across four modules now (see the "Real
  implementation pass" sections above); the same approach applies to the
  rest, tool by tool.
- **`DocumentRegistry`'s dispose-listener eviction** -- see above.
- **`get_document_events_live`/`wait_for_document_event_live`** -- still
  stub; deliberately deferred to their own pass (persistent listener
  lifecycle/concurrency, a different concern from the rest of
  `undo_view_selection.py`).
- **The 308 remaining stub tools are still not wired into the live server
  by default** -- see the `MCP_LIBRE_ENABLE_SCAFFOLD_STUBS` env var gate
  above. (The 58 implemented tools ARE always-on now, unconditionally.)
- **Undo-context tracking** (`begin_undo_context_live`/`end_undo_context_live`)
  -- still stubs, which is why `batch_execute_live`'s `undo_label` and
  `get_session_state_live`'s `pending_undo_context` can't be backed for real yet.
- **Phases E-F (Base/forms/Math, quality/expert surface) are untouched.**
  86 more net-new tools remain, per the table above.

## Open architecture question for Morgan

The existing plugin code is two flat files (`uno_bridge.py`, 1951 lines;
`mcp_server.py`, 739 lines) with no module-per-domain split. This pass
introduced `plugin/pythonpath/tools/` as a **parallel, additive** package
specifically so it wouldn't force a decision about restructuring the
existing 32-tool implementation. Two ways to continue from here:

1. **Keep growing `tools/`** as the home for all net-new tools (one module
   per spec section, as done here), and eventually have `uno_bridge.py`
   grow a matching per-domain split only when someone touches it anyway.
2. **Fold everything into the existing two files**, matching current
   convention exactly, and drop the `tools/` package once a phase stops
   being purely stubs.

Given the spec targets 484 tools and `uno_bridge.py` is already the
second-largest file in the repo, (1) seems safer for review size and merge
conflicts, but this is a real architectural call, not an obvious one --
flagging for @Morgan (Architect) rather than deciding it unilaterally here.
Not a blocker: `tools/` stays additive and reversible either way.

## Repo housekeeping noticed in passing

- `windows-oxt` had a file named `tatus` at the repo root (a `git diff`
  accidentally redirected to a truncated filename) -- this was already
  cleaned up upstream (`windows-oxt` commit `1bd4e5c`, "Remove accidental
  diff output file") before Phase C's rebase, so no action needed here.
- A full baseline review (hardcoded paths, overclaimed MCP compatibility,
  wildcard CORS/no Origin validation, false auto-start claims, wrong HTTP
  methods, version mismatches, and more -- 18 items) was done and fixed
  separately from this tool-scaffold plan; see the merged
  `fix/windows-oxt-baseline-cleanup` branch (PR #1) for that pass. Not
  duplicated here since it's a different concern (baseline correctness
  vs. new tool coverage).

## Suggested next steps

1. ~~Implement the 12 core-runtime tools against `DocumentRegistry`~~ --
   done, live-verified, see "Real implementation pass: core runtime tools" above.
2. ~~Implement `document_lifecycle.py`'s 22 tools for real~~ -- done,
   live-verified (including real file I/O), see "Real implementation
   pass: document lifecycle tools" above.
3. ~~Implement `undo_view_selection.py`'s undo + view/selection/locking
   tools (12 of 14) for real~~ -- done, live-verified, see "Real
   implementation pass: undo, view, selection, and locking tools" above.
4. ~~Implement `styles.py`'s 12 tools for real~~ -- done, live-verified,
   see "Real implementation pass: styles and formatting tools" above.
   All of Phase A is now real except the document-events pair.
5. Implement `get_document_events_live`/`wait_for_document_event_live` --
   the deliberately-deferred pair from step 3, needs a persistent
   listener with its own lifecycle/concurrency design, not just another
   synchronous UNO call. The only real-implementation gap left in Phase A.
6. Wire `mcp_server.py`'s HTTP layer (`ai_interface.py`) to surface
   `NOT_IMPLEMENTED` responses distinctly (e.g. HTTP 501) so a client can
   tell "not implemented yet" apart from a real runtime error while these
   phases are partially built out.
7. Phase A is otherwise complete -- natural next step is either the
   document-events pair (step 5) or starting Phase B's real
   implementation (`writer_text.py`/`writer_layout.py`/`writer_tables.py`,
   126 tool rows), or continuing to scaffold Phases E-F (Base and database
   access, forms and controls, Math formula documents, linguistic/
   accessibility/publishing QA, security/scripts/events/advanced UNO
   escape hatch -- 86 more rows), using the same `tools/registry.py`
   pattern established throughout.
