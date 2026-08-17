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
| Document and session lifecycle | 27 | 5 | 22 | **Scaffolded** (`tools/document_lifecycle.py`) |
| Undo, view, selection, events, orchestration | 14 | 0 | 14 | **Scaffolded** (`tools/undo_view_selection.py`) |
| Styles and formatting infrastructure | 12 | 0 | 12 | **Scaffolded** (`tools/styles.py`) |
| Writer - text, navigation, editing, search, review | 45 | 27 | 18 | **Scaffolded** (`tools/writer_text.py`) |
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
and "stub" tools separately; the remaining 354 scaffold tools are still
`status="stub"` and still gated by the env var exactly as before.

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

**Tool modules, 366 functions across 14 files (354 still stub, 12 real --
`core_runtime.py`, see "Real implementation pass" above):**

- Phase A: `core_runtime.py` (12, **implemented**), `document_lifecycle.py`
  (22 new, on top of 5 pre-existing), `undo_view_selection.py` (14), `styles.py` (12).
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

- **No UNO implementation in the remaining 354 tool stubs** (everything
  outside `core_runtime.py`). They all return `NOT_IMPLEMENTED`.
  Implementing them needs a working `uno`/`unohelper` environment inside
  LibreOffice -- confirmed working end-to-end for `core_runtime.py`'s 12
  (see "Real implementation pass" above); the same approach applies to
  the rest, tool by tool.
- **`DocumentRegistry`'s dispose-listener eviction** -- see above.
- **The 354 remaining stub tools are still not wired into the live server
  by default** -- see the `MCP_LIBRE_ENABLE_SCAFFOLD_STUBS` env var gate
  above. (The 12 `core_runtime.py` tools ARE always-on now, unconditionally.)
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
   done, live-verified, see "Real implementation pass" above.
2. Implement `begin_undo_context_live`/`end_undo_context_live` for real --
   `batch_execute_live` and `get_session_state_live` both have a
   documented gap waiting on this.
3. Wire `mcp_server.py`'s HTTP layer (`ai_interface.py`) to surface
   `NOT_IMPLEMENTED` responses distinctly (e.g. HTTP 501) so a client can
   tell "not implemented yet" apart from a real runtime error while these
   phases are partially built out.
4. Continue implementing real logic for `document_lifecycle.py` (open/
   save/convert/properties) -- natural next target since `core_runtime.py`
   now depends on some of the same document-resolution machinery, or
   continue scaffolding Phases E-F (Base and database access, forms and
   controls, Math formula documents, linguistic/accessibility/publishing
   QA, security/scripts/events/advanced UNO escape hatch -- 86 more rows),
   using the same `tools/registry.py` pattern established in Phases A-D.
