# Hardening plan

Post-catalog-completion phase. The full tool-catalog real-implementation
pass closed out with `writer_tables.py` (`f85e47f` on
`scaffold/mcp-tooling-phase-a`) -- seven modules (`draw.py`, `charts.py`,
`impress.py`, `calc_data.py`, `calc_page.py`, `writer_layout.py`,
`writer_tables.py`), all live-verified against real headless LibreOffice,
no scaffolded modules left in the plan.

Brian's explicit sequencing (2026-08-17): hardening first, then MCP
transport concurrency control as its own distinct phase, then the parked
spec-gap decision (vision/RAG/notebook/Calc-analysis-engine, see
`docs/WRITERAGENT_COMPARISON_MATRIX.md`) after both.

Scope for this doc, pulled from Buddy's assignment message plus the
standing audit-item numbers Brian/Buddy have been using in channel:

1. Error-code consistency (#31)
2. Centralized UNO->JSON conversion (#32)
3. PyUNO robustness sweep (#33)
4. Writer/Calc/Draw production-hardening (WriterAgent-matrix-informed)
5. Packaging + install smoke tests (#36/#37)
6. Release-readiness list (#43)
7. *(separate phase, after 1-6)* MCP transport concurrency control

**Note on item 4:** `docs/WRITERAGENT_COMPARISON_MATRIX.md` was written
*before* the catalog closed out and is now stale on tool-coverage claims
(it says `writer_layout.py`/`writer_tables.py`/all three Calc modules are
"100% stub" -- no longer true). Its Writer/Calc/Draw "WriterAgent-better"
verdicts split into two different kinds of gap: (a) genuine capability
gaps this project's own spec never planned for at all (WriterAgent's
review/grammar/document-research subsystems, DuckDB/forecast/symbolic-
math/vision-based Calc analysis) -- these are the parked spec-gap
decision, explicitly deferred by Brian until after hardening, not folded
in here; (b) production-hardening depth (error handling, edge cases,
concurrency-safety) on capability this project's spec *does* already
cover and has now implemented -- that's the real scope of item 4, and it
overlaps heavily with items 1-3 rather than being a separate checklist.

Sequencing chosen: 1 -> 2 -> 3 (structural/hygiene work, cheapest and
most bounded, establishes a clean baseline) -> 4 (informed by what 1-3
turn up) -> 5 (verification gate over all of the above) -> 6 (synthesis)
-> then phase 2, concurrency control, per Brian's explicit ordering.

## 1. Error-code consistency (#31)

**Status: in progress.**

Structural finding, good news first: nearly every real tool module
already reuses ONE shared `_error_response()`/`_map_exception_to_code()`
pair (defined in `document_lifecycle.py`, imported by every other
`tools/*.py` module except `core_runtime.py`, which builds `envelope.
build_error()` directly at each specific validation failure point instead
-- a different but equally consistent pattern, not drift, since those 12
tools mostly validate input rather than call into UNO). `envelope.
build_error()` itself hard-validates the code against a fixed
`ERROR_CODES` frozenset, so a genuinely wrong/typo'd code raises
immediately rather than silently shipping. Error-code consistency was
much closer to already-solved than expected going in.

**Real bug found and fixed:** `WRONG_DOCUMENT_TYPE` is declared in
`ERROR_CODES` but was **never reachable** from any of the ~90 real
tools -- confirmed by grep. `_require_writer()`/`_require_calc()`/
`_require_draw()`/`_require_impress()` (the document-type gate every
real tool calls through) all raised plain `NotImplementedError`, which
`_map_exception_to_code()` maps to `UNSUPPORTED_CAPABILITY` -- the same
code a genuinely-not-implemented stub option returns (e.g.
`insert_cross_reference`'s unknown `reference_type`). That conflated two
semantically different situations ("this tool isn't built" vs "you
called this on the wrong kind of document") under one code, for what is
the single most common error path in the entire catalog. Even
self-documented as a known, deliberate shortcut in this project's own
`docs/MCP_TOOLING_SCAFFOLD_PLAN.md` (the styles.py pass called it out
explicitly as `"WRONG_DOCUMENT_TYPE"-shaped UNSUPPORTED_CAPABILITY`) --
not an oversight, a compromise that's now worth undoing with the full
catalog stable.

Fixed: added `tools.documents.WrongDocumentTypeError` (a plain
`Exception` subclass -- deliberately placed in `tools/documents.py`, not
`uno_bridge.py` itself, so `document_lifecycle.py` can `isinstance()`-
check it without importing `uno_bridge.py`, which pulls in the real
`uno`/`unohelper` PyUNO modules only available inside a running
LibreOffice process; a first attempt at a module-level `import uno_bridge`
from `document_lifecycle.py` broke the entire fakes-based test suite
outside LibreOffice, confirmed live: `ModuleNotFoundError: No module
named 'uno'`). Nine raise sites updated to use it: the four `_require_*`
gates, `apply_style`/`get_direct_formatting`/`clear_direct_formatting`/
`copy_formatting` (Writer-only, checked directly rather than through
`_require_writer`), and `_require_chart_capable` (Calc-native-chart
check in `charts.py`'s backing bridge code). `_map_exception_to_code()`
gained one new branch. Live-verified against a real headless LibreOffice
26.2 instance across all nine call sites (a Calc-only tool called against
an open Writer document, and vice versa) -- every one now returns
`WRONG_DOCUMENT_TYPE` with the correct message, not
`UNSUPPORTED_CAPABILITY`. New regression test,
`test_map_exception_to_code_covers_every_branch` in
`tests/test_document_lifecycle.py`, unit-tests every branch of
`_map_exception_to_code()` directly. 434/434 passing.

**Confirmed, not a bug -- `AMBIGUOUS_SELECTOR` is structurally
inapplicable to this architecture:** `ERROR_CODES` declares it (per the
spec's own language, quoted in `DocumentRegistry.resolve_document()`'s
docstring: "Document selectors default to the active document only when
unambiguous"), but `get_active_document()` resolves through UNO's own
`desktop.getCurrentComponent()`, which is single-valued by construction
-- there is no UNO-level scenario where two documents are simultaneously
"the current component." `document_id` is either explicitly given
(unambiguous by definition) or omitted (falls back to that one value).
Representing "ambiguous" at all would require inventing a different
multi-document-detection heuristic than what this project's addressing
model uses -- a design decision, not a bug fix. Not implemented; flagged
here rather than silently left dead code with no explanation.

**Flagged, deferred, needs a scope decision (bigger than this audit
item):** the **original 32 "legacy" tools** (still live today via
`mcp_server.py`'s own dispatch, entirely separate from the `tools/`-
registry pattern every real-implementation pass since Phase A has used)
return a flat `{"success": False, "error": "<string>"}` shape -- not the
modern structured `{"success": False, "error": {"code", "message",
"details"}}` envelope. Confirmed live in the source (~25+ `doc_type !=
"writer"` checks in `uno_bridge.py`'s legacy methods, e.g. `get_track_
changes_status()`, still returning bare error strings). This is a
genuine, real inconsistency, but migrating 25+ long-stable legacy call
sites to the modern envelope is a much larger undertaking than a
same-pass audit fix and risks touching code that predates this project's
whole real-implementation methodology. Not touched this pass -- needs a
deliberate scope decision (migrate now vs. accept as documented, pre-
existing legacy-vs-modern split) before further work here, not a silent
rewrite.

**Not yet checked:** `DATABASE_ERROR` (declared, never used) is a live
candidate given `writer_tables.py`'s new `preview_mail_merge_live` is the
first (only) SDBC-touching code in the whole codebase -- a malformed
table name or connection failure there currently falls through to the
generic `UNO_EXCEPTION` catch-all. Deferred to the PyUNO robustness sweep
(item 3 below), where it can be live-verified against a real SDBC
failure rather than guessed at from a static read.

## 2. Centralized UNO->JSON conversion (#32)

Not started.

## 3. PyUNO robustness sweep (#33)

Not started. `DATABASE_ERROR`/SDBC exception mapping (see item 1 above)
folds in here.

## 4. Writer/Calc/Draw production-hardening

Not started. See the note above on what's actually in scope here vs. the
parked spec-gap decision.

## 5. Packaging + install smoke tests (#36/#37)

Not started.

## 6. Release-readiness list (#43)

Not started -- depends on 1-5.

## Phase 2 (after 1-6): MCP transport concurrency control

Not started. Scope per `docs/WRITERAGENT_COMPARISON_MATRIX.md`'s "MCP
transport" row: no global backpressure semaphore, no per-document
mutation lock, `Mcp-Session-Id` minted/echoed but not enforced, no
protocol-version validation against a supported-version list.
