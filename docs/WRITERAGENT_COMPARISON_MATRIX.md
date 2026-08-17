# WriterAgent comparison matrix

Closes out Brian's original 8-item WriterAgent request, items 1/2/6:
produce the WriterAgent-better/ours-better/both/neither/unknown matrix
across the 11 named dimensions, and identify WriterAgent capabilities
absent from `LibreOffice_MCP_Complete_Tooling_Specification.md` itself
(a spec gap, not a backlog gap). Compares against `mcp-libre` HEAD
`5b8950d` on `scaffold/mcp-tooling-phase-a`.

**Licensing constraint, unchanged from every prior pass:** WriterAgent
(`E:\Tools\writeragent`) is GPLv3+; `mcp-libre` is MIT. Everything below
is read-only architectural/behavioral inspection -- file/directory
structure, tool names, parameter shapes, short code excerpts read
in-repo to confirm a claim -- described in prose, not reproduced. No
WriterAgent code is copied into this document or into `mcp-libre`.

## Evidence strength, stated per row

Not every row rests on equally strong evidence. Three tiers, used
explicitly below rather than left implicit:

- **Read** -- I read actual WriterAgent source this pass (or the prior
  transport/targeting research pass did) and can cite what it does.
- **Structural** -- inferred from directory/file layout and tool
  parameter names (e.g. `shapes.py` having a `shape_index` parameter)
  without reading the full implementation. Reasonable signal, not proof.
- **Absence** -- a grep found nothing; per this project's own
  `grep-for-token-misses-wrapper-callers` lesson, absence of a hit is
  weaker evidence than a positive read and is flagged as such rather
  than asserted as a confirmed gap.

## The matrix

| Dimension | Verdict | Evidence |
|---|---|---|
| Writer | **WriterAgent-better** | Structural + Read |
| Calc | **WriterAgent-better** | Structural |
| Impress | **Unknown, leans WriterAgent** | Structural (weak) |
| Draw | **WriterAgent-better** | Structural + Read |
| Runtime/lifecycle | **Both** | Read |
| Multi-doc targeting | **Both** | Read (prior pass) |
| MCP transport | **WriterAgent-better** | Read (prior pass) |
| Security | **Both weak (neither strong)** | Read (prior pass) |
| Undo/batching | **Ours-better** | Read |
| Object identity | **Both** | Read + Structural |
| Testing | **Both** | Read (prior pass) |

## Per-dimension detail

**Writer -- WriterAgent-better.** WriterAgent splits Writer support
across two directories: `plugin/doc/` (document-type-agnostic: outline,
diagnostics, undo, visual helpers, and a five-file "document research"
subsystem -- `document_research.py`/`_grep.py`/`_grep_tool.py`/
`_specialized.py`/`_tools.py`) and `plugin/writer/` (Writer-specific:
`content.py`, `format.py`, `structural.py`, `styles.py`, `outline.py`,
`navigation.py`, `selection.py`, `paragraph_search.py`, `proximity.py`,
a `math/` subdirectory for Math-formula insertion, and a genuinely
substantial tracked-changes/review subsystem -- `edit_review.py`,
`inline_review.py`, `review_authors.py`, `review_click_popup.py`,
`review_toolbar.py`, `word_diff_split.py` -- plus locale-aware grammar
proofreading as its own subsystem, `plugin/writer/locale/grammar_*.py`,
4 files). Read directly: `plugin/doc/undo.py`'s docstring confirms undo
"was re-enabled... with review mode off an agent's bad edit was
unrecoverable" -- evidence of a mature, iterated-on review/safety
workflow, not a first pass. `mcp-libre`'s Writer coverage is real for
45 tools (27 original-32 + 18 `writer_text.py`) but `writer_layout.py`
(43 tools: page layout, headers/footers, fields, indexes) and
`writer_tables.py` (38 tools: tables, sections, footnotes, content
controls, mail merge) are still 100% stub. Caveat worth stating
plainly: WriterAgent's Writer files include human-in-the-loop chat-
sidebar UI integration (context menus, toolbar buttons, click popups)
that isn't a fair comparison to `mcp-libre`'s pure external-MCP-tool
surface -- the verdict is about capability depth for an AI agent
operating on Writer documents, not an apples-to-apples architecture
comparison.

**Calc -- WriterAgent-better.** `plugin/calc/` has 35+ files including
several capability classes with no `mcp-libre` analog even planned:
`pivot.py` (pivot tables -- planned in our spec's Phase C `calc_data.py`,
but still stub), `forecast.py`/`forecast_auto_plot.py`, `optimize.py`
(solver/optimization), `symbolic_math.py`, `duckdb_tools.py` (DuckDB
integration for data analysis), `formula_dep_chain.py` (formula
dependency-chain analysis), `error_detector.py`, `vision_egress.py`
(vision-model-based chart/data reading), `viz.py`/`viz_auto_plot.py`,
`quant_egress.py`. This is Structural evidence (file/function names
read, not full implementations), but the breadth and specificity of the
names (`formula_dep_chain.py`, `duckdb_tools.py`) make "advanced
analysis engine, not just CRUD" a confident read. `mcp-libre`'s three
Calc modules (99 tools total: `calc_sheets.py`, `calc_data.py`,
`calc_page.py`) are 100% stub today, and per the spec's own Key
Parameters columns are CRUD/formatting/analysis-primitive oriented
(sheets, cells, ranges, formulas, named ranges, pivots, validation) --
not analysis-engine oriented. Several of WriterAgent's Calc files look
like genuine spec gaps, not just implementation gaps -- see below.

**Impress -- unknown, leans WriterAgent (weak evidence).** WriterAgent
has **no separate Impress directory at all** -- confirmed by directory
listing, not just a missed grep. Impress-flavored files
(`masters.py`, `notes.py`, `placeholders.py`, `transitions.py`,
`headers_footers.py`) live inside `plugin/draw/`, consistent with UNO's
own architecture (`com.sun.star.presentation.PresentationDocument`
shares the drawing-page layer with `com.sun.star.drawing.DrawingDocument`
-- there is no separate "Impress API" at the UNO level, only a separate
document service). This is a genuine, structurally-confirmed
architectural difference from `mcp-libre`'s spec, which keeps
`impress.py` (41 tools) and `draw.py` (16 tools) as fully separate
catalog sections. Marked "unknown, leans WriterAgent" rather than a
confident verdict because I did not read `masters.py`/`transitions.py`'s
actual implementations this pass to confirm real (not stub) Impress-
specific behavior -- the file names are strong signal, not proof.

**Draw -- WriterAgent-better.** Read directly this pass:
`plugin/draw/shapes.py` implements real shape CRUD (`upsert_shape`,
`shapes_connect`, `shapes_group`, `delete_shape`) addressed by a plain
integer `shape_index` (0-based position on the page) -- confirms
WriterAgent's shape-addressing philosophy is live/positional, not an
opaque handle (see "Object identity" below). Also present:
`transform.py`/`transform_engine.py`/`transform_schema.py` (geometry
transforms as their own subsystem), `tree.py`, `charts.py` (charts
embedded in a Draw/Impress page), `math_insert.py`. `mcp-libre`'s
`draw.py` (16 tools) and the shared `drawing_objects.py` (31 tools) are
both 100% stub.

**Runtime/lifecycle -- both.** WriterAgent: no persistent registry,
resolves the target document live via desktop enumeration
(`document_url`/`X-Document-URL`/`RuntimeUID`, see
`docs/DOCUMENT_TARGETING_DECISION.md`), a global semaphore for request
backpressure, per-document mutation lock for correctness (`mcp-libre`
still lacks this -- a real WriterAgent-better point, already flagged as
a gap in the targeting decision doc, not re-litigated here).
`mcp-libre`: `DocumentRegistry` (real, tested, O(1) resolution, Save-
As-stable), `core_runtime.py` (12/12 real) + `document_lifecycle.py`
(22/22 real) cover comparable open/save/properties/metadata/print
territory, live-verified. Verdict "both": each has something genuine
the other doesn't (WriterAgent's per-document lock vs. `mcp-libre`'s
O(1) handle + explicit undo-context transactions, see "Undo/batching"),
neither is a strict superset.

**Multi-doc targeting -- both.** Already the subject of
`docs/DOCUMENT_TARGETING_DECISION.md` -- not re-derived here.
WriterAgent's dual `document_url`/`RuntimeUID` addressing needs no
persistent state and handles unsaved documents naturally; `mcp-libre`'s
opaque `document_id` is cheaper per call and equally Save-As-stable via
a different mechanism (object-identity keying). Deliberately different,
both defensible tradeoffs -- see that document for the full reasoning
on why `mcp-libre` didn't default-copy WriterAgent's approach.

**MCP transport -- WriterAgent-better.** `mcp-libre`'s `POST /mcp`
(shipped this session, `5b8950d`) is real and MCP-Inspector-verified,
but deliberately scoped down for a first pass: single-JSON-response
only (no SSE), permissive protocol-version handling (no validation
against a supported-version list), `Mcp-Session-Id` minted/echoed but
not enforced, and -- most materially -- no concurrency control of any
kind (no global backpressure semaphore, no per-document lock).
WriterAgent's transport (research from the prior pass) has real session
validation, protocol-version enforcement, a global semaphore, the per-
document lock, and a documented exemption path for long-running tools
that bypasses the semaphore without bypassing the lock. This is the
widest, most confident gap in the whole matrix -- WriterAgent's
transport is production-hardened; `mcp-libre`'s is a correct, live-
verified first pass, not yet hardened.

**Security -- both weak, neither strong.** Read directly (prior
research pass): WriterAgent's MCP endpoint has **no authentication at
all**, loopback-only, explicitly documented by WriterAgent as an
accepted risk for a local developer tool. `mcp-libre` also has no
authentication, but does have an active mitigation WriterAgent's
research didn't surface an equivalent for: `host_trust.py`'s Host/Origin
header validation, a real (if narrow) DNS-rebinding guard. Marked
"both weak" rather than "ours slightly better," because the DNS-
rebinding guard addresses a different, narrower threat than the shared
larger gap (no per-caller authorization for a destructive local tool) --
overclaiming a real security edge on one narrow point while the bigger
gap is identical on both sides would misstate the actual risk picture.

**Undo/batching -- ours-better.** Read directly this pass:
`plugin/doc/undo.py`'s `Undo`/`Redo` tools are simple, step-count-based,
operate on a stack **shared with the user's own manual edits** ("the
undo stack interleaves YOUR edits with the user's own edits"), and rely
on the calling model being prompted to "undo only its own last action" --
there is no transactional grouping concept. `mcp-libre`'s
`begin_undo_context_live`/`end_undo_context_live`/`cancel_undo_context_live`
(real, live-verified in an earlier pass) let a whole batch of edits be
grouped and rolled back as one atomic unit -- a genuine capability
WriterAgent's undo.py doesn't have. Weaker, Absence-tier evidence: no
`batch_execute`-equivalent tool was found by name anywhere in
WriterAgent's tool modules (grep hits were all incidental substring
matches inside unrelated pipeline code, not an agent-facing "run N tool
calls atomically" tool) -- consistent with, but not proof of, WriterAgent
not exposing an equivalent to `batch_execute_live` at the MCP layer.

**Object identity -- both.** `mcp-libre`'s `DocumentRegistry`/
`ObjectRegistry` (see `docs/OBJECT_HANDLE_DESIGN.md`) mint opaque,
stable handles below the document level for the object categories that
need them (shapes, non-Calc-native charts). WriterAgent, confirmed by
reading `plugin/draw/shapes.py` directly, addresses shapes by plain
0-based `shape_index` (page-local position) with no opaque-handle layer
at all -- the same "index shifts under mutation" identity risk this
project's own `docs/OBJECT_HANDLE_DESIGN.md` designed `ObjectRegistry`
specifically to avoid for shapes (as opposed to sheets/slides, which
that document deliberately resolves live by name/index precisely
because they're safe to). Verdict "both," not "ours-better," because
this wasn't independently checked against WriterAgent's actual usage
patterns -- it's possible position-based addressing is fine for
WriterAgent's actual call patterns (e.g. an agent typically creates and
immediately edits a shape within one tool-call sequence, never holding
a stale index across an intervening mutation) even though it's a risk
`mcp-libre`'s design doc identified and solved differently.

**Testing -- both.** From the prior transport research pass:
WriterAgent's `tests/` tree is large and organized per-domain
(`tests/calc/`, `tests/draw/`, `tests/mcp/`, `tests/framework/`) --
broader in raw test count than `mcp-libre`'s 212. But it's entirely
`unittest.mock.MagicMock`-based, not live-UNO, even for the tests that
spin up a real HTTP server (the fixture still mocks the document/tools
service). The only thing in WriterAgent that touches genuinely running
LibreOffice is `scripts/mcp_live_smoke.py`, a manual, non-automated
script. `mcp-libre`'s own unit suite (212 tests) is the same fakes-based
pattern for anything UNO-independent, but every real-implementation
pass this project has done is *additionally* gated on mandatory live
verification against actual headless LibreOffice (and, this session,
against the real MCP Inspector client) before being called done --
demonstrated repeatedly and consistently across ten-plus passes.
Verdict "both": WriterAgent wins on test breadth/count, `mcp-libre` wins
on live-verification being a systematic, mandatory discipline rather
than a manual script.

## WriterAgent capabilities absent from the spec document itself

Per Brian's item 2/Buddy's framing: this is about
`LibreOffice_MCP_Complete_Tooling_Specification.md` not mentioning these
capabilities *at all*, in any of its 19 catalog sections or 484 planned
tools -- a spec gap, not merely something `mcp-libre` hasn't implemented
yet. Ordered by confidence:

**High confidence** (multiple files, `module.yaml` present, i.e. a
first-class WriterAgent plugin module, not incidental):

1. **Vision/screenshot-based document understanding**
   (`plugin/vision/`, 6+ files: `vision_availability.py`,
   `vision_common.py`, `vision_egress.py`, `vision_runner.py`,
   `vision_templates.py`, `vision_tools.py`). Nothing in the spec's 19
   sections covers an agent visually inspecting rendered document/chart
   output.
2. **Embeddings/full-text-search/RAG over document content**
   (`plugin/embeddings/`, 10+ files: indexing, caching, periodic
   refresh, FTS and semantic search tools, locale-aware). No spec
   section covers semantic search across a document's own content or a
   folder of documents.
3. **Notebook-style cell interface** (`plugin/notebook/`:
   `cell_registry.py`, `notebook_controls.py`, `notebook_runner.py`,
   `writer_importer.py`). A distinct UX/data model (Jupyter-like cells
   embedded in a document) with no equivalent concept anywhere in the
   spec.
4. **Calc analysis-engine capabilities**: DuckDB integration
   (`duckdb_tools.py`), symbolic math (`symbolic_math.py`), forecasting
   with auto-plotting (`forecast.py`/`forecast_auto_plot.py`), solver/
   optimization (`optimize.py`), formula dependency-chain analysis
   (`formula_dep_chain.py`), automated error detection
   (`error_detector.py`), vision-based chart/data reading
   (`vision_egress.py`). The spec's Calc sections are CRUD/formatting/
   analysis-primitive oriented (cells, ranges, formulas, pivots,
   validation) -- there is no "analysis engine" or "data science
   tooling" concept in the spec at all.

**Moderate confidence** (fewer files, or read the docstring/parameters
but not the full implementation):

5. **Document diffing** (`word_diff_split.py`) -- no "diff two document
   versions" tool category anywhere in the spec.
6. **Locale-aware grammar/proofreading as a distinct subsystem**
   (`plugin/writer/locale/grammar_*.py`, 4 files) -- the spec's
   Linguistic services section (15 tools, not started) may cover some
   of this at a coarser grain, worth a closer read before calling this
   a confirmed gap rather than a partial overlap.
7. **Document research/grep across content as first-class MCP tools**
   (`document_research_grep_tool.py`,
   `document_research_search_tool.py`) -- closer to "search within an
   open document" than embeddings-based RAG (item 2), but still not a
   concept the spec names.

Not included here: WriterAgent's chat-sidebar UI integration (context
menus, toolbar buttons, review click-popups) -- that's a different
product surface (an in-app copilot UX) rather than an MCP-tool-catalog
gap, so it's out of scope for a spec-gap comparison against a tool
specification document.

## What this changes about current priorities

Nothing here overrides the dependency-order plan already agreed
(`drawing_objects.py` first, informed by the WriterAgent-better Draw
verdict and the confirmed shape-index-vs-opaque-handle difference
above). The clearest actionable signal for Morgan/Brian: the Calc
analysis-engine gap (item 4 above) and the MCP-transport concurrency gap
are the two widest deltas in this matrix -- worth a deliberate
scope decision (adopt, defer, or explicitly decline) rather than
surfacing only when Calc or transport-hardening work starts.
