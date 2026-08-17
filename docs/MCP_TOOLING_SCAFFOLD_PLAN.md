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
| Writer - page layout, publishing, styles, headers, fields, indexes | 43 | 0 | 43 | **Scaffolded** (`tools/writer_layout.py`) |
| Writer - tables, sections, notes, content controls, mail merge | 38 | 0 | 38 | **Scaffolded** (`tools/writer_tables.py`) |
| Common drawing objects, images, shapes, embedded objects | 31 | 0 | 31 | **Scaffolded** (`tools/drawing_objects.py`) |
| Charts and data visualizations | 20 | 0 | 20 | **Scaffolded** (`tools/charts.py`) |
| Calc - sheets, cells, ranges, formulas, layout | 42 | 0 | 42 | **Scaffolded** (`tools/calc_sheets.py`) |
| Calc - data management, analysis, pivots, validation, external data | 42 | 0 | 42 | **Scaffolded** (`tools/calc_data.py`) |
| Calc - page setup, print ranges, annotations, protection | 15 | 0 | 15 | **Scaffolded** (`tools/calc_page.py`) |
| Impress - slides, masters, notes, transitions, animations, slideshow | 41 | 0 | 41 | **Scaffolded** (`tools/impress.py`) |
| Draw - pages, masters, layers, vector operations | 16 | 0 | 16 | **Scaffolded** (`tools/draw.py`) |
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
