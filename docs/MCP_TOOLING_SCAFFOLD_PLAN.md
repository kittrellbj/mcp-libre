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
| Core runtime, discovery, capability negotiation | 12 | 0 | 12 | **Scaffolded** (`tools/core_runtime.py`) |
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
| Impress - slides, masters, notes, transitions, animations, slideshow | 41 | 0 | 0 | Not started |
| Draw - pages, masters, layers, vector operations | 16 | 0 | 0 | Not started |
| Base and database access | 34 | 0 | 0 | Not started |
| Forms and controls | 16 | 0 | 0 | Not started |
| Math formula documents and embedded formulas | 7 | 0 | 0 | Not started |
| Linguistic services, accessibility, publishing QA | 15 | 0 | 0 | Not started |
| Security, scripts, events, advanced UNO escape hatch | 14 | 0 | 0 | Not started |
| **Total** | **484** | **32** | **309** | **309 / 452 net-new tools scaffolded** |

"Scaffolded" means: registered under the exact spec tool name with the
correct priority and a JSON Schema `parameters` block built from the
spec's Key Parameters column, with a docstring/purpose copied from the
spec's Purpose column, and a handler body that returns the standard
`NOT_IMPLEMENTED` error envelope. **No UNO logic has been written for any
of these 309 tools** -- that is deliberately left for a senior engineer.

This covers Implementation Phases A, B, and C from the spec's own section 10:

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
  **Not yet wired into any tool stub's body** -- every stub below still
  returns `NOT_IMPLEMENTED` regardless of arguments; wiring the registry
  into a handler is real tool-by-tool implementation work, not scaffolding.

**Tool modules, 309 stub functions across 12 files:**

- Phase A: `core_runtime.py` (12), `document_lifecycle.py` (22 new, on top
  of 5 pre-existing), `undo_view_selection.py` (14), `styles.py` (12).
- Phase B: `writer_text.py` (18 new, on top of 27 pre-existing),
  `writer_layout.py` (43), `writer_tables.py` (38).
- Phase C: `drawing_objects.py` (31), `charts.py` (20), `calc_sheets.py`
  (42), `calc_data.py` (42), `calc_page.py` (15).

**Tests:**

- `tests/test_tool_scaffold_contract.py` -- registry completeness checked
  **by exact name per module**, not just by count (a tool landing under
  the wrong name, or in the wrong module, fails loudly even if the total
  count still matches); no collisions with the 32 existing compat tools;
  every stub's response shape; `merge_into()` non-destructiveness; the
  error-code set. Run with `python tests/test_tool_scaffold_contract.py`
  or `uv run pytest tests/test_tool_scaffold_contract.py`. 7/7 passing
  locally, 309 tools registered across 12 modules.
- `tests/test_document_registry.py` -- 9 unit tests for `DocumentRegistry`
  against fakes, 9/9 passing.

**Integration:** one opt-in hook in `mcp_server.py`
(`_register_scaffold_stub_tools`, merges in all 309 tools via
`tools.merge_into()`, gated by env var
`MCP_LIBRE_ENABLE_SCAFFOLD_STUBS`): additive-only, so the original 32
tools' behavior is unchanged when the flag is unset (the default). This
exists so a senior engineer can flip it on locally and see the new tools
show up in `/tools` while implementing them, without the scaffold
silently expanding the tool surface exposed to any current users of the
extension.

## What is intentionally NOT done

- **No UNO implementation in any of the 309 tool stubs.** They all
  return `NOT_IMPLEMENTED`. Implementing them needs a working
  `uno`/`unohelper` environment inside LibreOffice, which this scaffolding
  pass didn't have reason to touch.
- **`DocumentRegistry`'s dispose-listener eviction** -- see above.
- **Not wired into the live server by default** -- see the env var gate
  above.
- **Phases D-F (Impress/Draw, Base/forms/Math, quality/expert surface) are
  untouched.** 143 more net-new tools remain, per the table above.

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

## Repo housekeeping noticed in passing (not touched by this scaffold)

- `windows-oxt` branch commit `d18c830` ("Add working Windows LibreOffice
  MCP extension v1.0.0") includes a file named `tatus` at the repo root --
  looks like `git diff` output accidentally redirected to a truncated
  filename (172 lines of diff text). Worth a follow-up cleanup commit;
  left alone here since it predates this scaffolding work and isn't part
  of the tooling catalog.

## Suggested next steps

1. Implement the 12 core-runtime stubs against `DocumentRegistry` --
   `get_server_info_live`, `list_tools_live`, `get_session_state_live`,
   etc. are the tools every other tool's tests will use to introspect
   what's available.
2. Wire `mcp_server.py`'s HTTP layer (`ai_interface.py`) to surface
   `NOT_IMPLEMENTED` responses distinctly (e.g. HTTP 501) so a client can
   tell "not implemented yet" apart from a real runtime error while these
   phases are partially built out.
3. Continue scaffolding Phase D (Impress: slides/masters/notes/
   transitions/animations/slideshow, 41 rows; Draw: pages/masters/layers/
   vector operations, 16 rows) and onward through Phases E-F (Base and
   database access, forms and controls, Math formula documents,
   linguistic/accessibility/publishing QA, security/scripts/events/
   advanced UNO escape hatch -- 86 more rows), using the same
   `tools/registry.py` pattern established in Phases A-C.
