# MCP Tooling Scaffold Plan

Tracks scaffolding progress against `LibreOffice_MCP_Complete_Tooling_Specification.md`
(the design doc, kept one level up in `E:\Tools\` on the machine this fork
lives on -- not copied into this repo). That spec targets **484 tool
definitions**: 32 existing/baseline (P0), 218 core (P1), 193 extended (P2),
41 advanced (P3), across 18 catalog sections plus a security/advanced-UNO
section. This document is maintained by the scaffolding pass so a later
session (or a senior engineer) can pick up exactly where it left off.

## Status

| Spec section | Tool rows | Existing (P0) | New this pass | Status |
|---|---|---|---|---|
| Core runtime, discovery, capability negotiation | 12 | 0 | 12 | **Scaffolded** (`tools/core_runtime.py`) |
| Document and session lifecycle | 27 | 5 | 22 | **Scaffolded** (`tools/document_lifecycle.py`) |
| Undo, view, selection, events, orchestration | 14 | 0 | 14 | **Scaffolded** (`tools/undo_view_selection.py`) |
| Styles and formatting infrastructure | 12 | 0 | 12 | **Scaffolded** (`tools/styles.py`) |
| Writer - text, navigation, editing, search, review | 45 | 27 | 0 | Not started |
| Writer - page layout, publishing, styles, headers, fields, indexes | 43 | 0 | 0 | Not started |
| Writer - tables, sections, notes, content controls, mail merge | 38 | 0 | 0 | Not started |
| Common drawing objects, images, shapes, embedded objects | 31 | 0 | 0 | Not started |
| Charts and data visualizations | 20 | 0 | 0 | Not started |
| Calc - sheets, cells, ranges, formulas, layout | 42 | 0 | 0 | Not started |
| Calc - data management, analysis, pivots, validation, external data | 42 | 0 | 0 | Not started |
| Calc - page setup, print ranges, annotations, protection | 15 | 0 | 0 | Not started |
| Impress - slides, masters, notes, transitions, animations, slideshow | 41 | 0 | 0 | Not started |
| Draw - pages, masters, layers, vector operations | 16 | 0 | 0 | Not started |
| Base and database access | 34 | 0 | 0 | Not started |
| Forms and controls | 16 | 0 | 0 | Not started |
| Math formula documents and embedded formulas | 7 | 0 | 0 | Not started |
| Linguistic services, accessibility, publishing QA | 15 | 0 | 0 | Not started |
| Security, scripts, events, advanced UNO escape hatch | 14 | 0 | 0 | Not started |
| **Total** | **484** | **32** | **60** | **60 / 452 net-new tools scaffolded** |

"Scaffolded" means: registered under the exact spec tool name with the
correct priority and a JSON Schema `parameters` block built from the
spec's Key Parameters column, with a docstring/purpose copied from the
spec's Purpose column, and a handler body that returns the standard
`NOT_IMPLEMENTED` error envelope. **No UNO logic has been written for any
of these 60 tools** -- that is deliberately left for a senior engineer, per
the phased plan below.

This first pass covers exactly Implementation Phase A from the spec's own
section 10 ("Runtime hardening and common document API: discovery, handles,
lifecycle, metadata, undo, batch execution, styles, export/print") --
picked because every later phase's tools describe operations *on* a
document, and Phase A is where the document-handle and response-envelope
plumbing those operations depend on gets defined.

## What was built

- `plugin/pythonpath/tools/registry.py` -- `@register_tool(name, priority,
  purpose, parameters)` decorator + `merge_into()`. Mirrors the
  `{description, parameters, handler}` dict shape
  `mcp_server.py`'s `_register_tools()` already uses for the original 32
  tools, so a senior engineer can move a finished stub's registration
  in-place if they'd rather not depend on this package at all.
- `plugin/pythonpath/tools/envelope.py` -- `build_success()` / `build_error()`
  implementing the spec's section 5 contract (`{success, result, warnings,
  error, document_id, elapsed_ms}`) and the spec's 13 stable error codes,
  plus a scaffold-only `NOT_IMPLEMENTED` code for stub responses.
- `plugin/pythonpath/tools/documents.py` -- `DocumentRegistry`, a stub for
  the stable `document_id` handle concept the spec requires (section 2) and
  that **does not exist anywhere in the codebase today** (`uno_bridge.py`
  only ever resolves "the active document"). Every method raises
  `NotImplementedError`; the docstrings describe the intended design
  (uuid4-keyed map, dispose-listener eviction) for whoever implements it.
  This is the single biggest real gap blocking Phase A from becoming real.
- Four Phase A tool modules (`core_runtime.py`, `document_lifecycle.py`,
  `undo_view_selection.py`, `styles.py`), 60 stub functions total.
- `tests/test_phase_a_stubs.py` -- contract tests that don't need a live
  LibreOffice or the `uno` module: registry completeness/no-collision,
  every stub's response shape, `merge_into()` non-destructiveness, and the
  error-code set. Run with `python tests/test_phase_a_stubs.py` or
  `uv run pytest tests/test_phase_a_stubs.py`. Verified passing locally
  (6/6) against this commit.
- One opt-in integration hook in `mcp_server.py`
  (`_register_phase_a_stub_tools`, gated by env var
  `MCP_LIBRE_ENABLE_PHASE_A_STUBS`): additive-only via `merge_into()`, so
  the original 32 tools' behavior is unchanged when the flag is unset
  (the default). This exists so a senior engineer can flip it on locally
  and see the new tools show up in `/tools` while implementing them, without
  the scaffold silently expanding the tool surface exposed to any current
  users of the extension.

## What is intentionally NOT done

- **No UNO implementation.** Every one of the 60 stubs returns
  `NOT_IMPLEMENTED`. Implementing them needs a working `uno`/`unohelper`
  environment inside LibreOffice, which this scaffolding pass didn't have
  reason to touch.
- **No `DocumentRegistry` implementation** -- see above. This blocks any
  stub whose signature takes `document_id` from being real; it should
  likely be implemented first, since Writer/Calc/Impress/Draw/Base tools in
  every later phase depend on the same handle concept for
  documents/sheets/slides/shapes/etc.
- **Not wired into the live server by default** -- see the env var gate
  above.
- **Phases B-F (writer, calc, drawing/charts, impress/draw, base/forms/math,
  quality/expert surface) are untouched.** ~392 more tools remain, per the
  table above.

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
   convention exactly, and drop the `tools/` package once Phase A stops
   being purely stubs.

Given the spec targets 484 tools and `uno_bridge.py` is already the
second-largest file in the repo, (1) seems safer for review size and merge
conflicts, but this is a real architectural call, not an obvious one --
flagging for @Morgan (Architect) rather than deciding it unilaterally here.

## Repo housekeeping noticed in passing (not touched by this scaffold)

- `windows-oxt` branch commit `d18c830` ("Add working Windows LibreOffice
  MCP extension v1.0.0") includes a file named `tatus` at the repo root --
  looks like `git diff` output accidentally redirected to a truncated
  filename (172 lines of diff text). Worth a follow-up cleanup commit;
  left alone here since it predates this scaffolding work and isn't part
  of the tooling catalog.

## Suggested next steps

1. Implement `DocumentRegistry` for real (see `documents.py` docstrings).
2. Implement the 12 core-runtime stubs against it -- `get_server_info_live`,
   `list_tools_live`, `get_session_state_live`, etc. are the tools every
   other tool's tests will use to introspect what's available.
3. Wire `mcp_server.py`'s HTTP layer (`ai_interface.py`) to surface
   `NOT_IMPLEMENTED` responses distinctly (e.g. HTTP 501) so a client can
   tell "not implemented yet" apart from a real runtime error while Phase A
   is partially built out.
4. Continue scaffolding Phase B (Writer-complete, 126 tool rows across the
   three Writer sections) using the same `tools/registry.py` pattern.
