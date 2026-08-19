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

**Status: substantially done for the shared converter; broader struct
coverage stays open.**

Structural finding, good news first: there was already exactly ONE
shared converter, `_uno_value_to_plain()`, reused across all ~10 generic
property-enumeration call sites in `uno_bridge.py` -- no scattered,
duplicated ad hoc conversion logic. Centralization was closer to
already-solved than expected, same pattern as #31.

**Real bug found and fixed, live-verified:** `get_direct_formatting_
live`'s generic property-enumeration loop was silently DROPPING any
Locale-typed direct-formatting override (e.g. `CharLocale`, a real,
commonly-set Writer character property) with no warning. Root cause:
`_uno_value_to_plain()` only converted `uno.Enum` and `Width`/`Height`-
shaped structs (e.g. `com.sun.star.awt.Size`); anything else -- including
`com.sun.star.lang.Locale` -- passed through unconverted, then failed
`_is_json_safe()` (not a plain type), and `get_direct_formatting()`
silently excludes (never warns on) anything that fails that check.
Live-verified precisely: set `CharLocale` to a genuinely different value
than the document default (confirmed real `PropertyState.DIRECT_VALUE`
via an independent raw-UNO read), called `get_direct_formatting_live` on
that exact range -- `CharLocale` was completely absent from the result.
Fixed by adding a `Language`+`Country` branch (-> `"xx-YY"`, matching
`_parse_locale()`'s existing reverse-direction string convention) plus
`X`+`Y`-shaped (`awt.Point`) and full `X`+`Y`+`Width`+`Height`-shaped
(`awt.Rectangle`) branches for the same reason (not yet observed
silently dropping something live, but the same structural gap). Rebuilt,
redeployed, re-verified on a fresh headless instance -- `CharLocale`
correctly shows `"ja-JP"` now.

**Also found and merged, no bug but a real duplication:** a *second*,
entirely separate narrow converter already existed --
`uno_datetime.py`'s `uno_temporal_value_to_plain()` (Date/DateTime/
Duration structs -> ISO-8601 strings), used from exactly ONE call site
(`get_custom_properties()`) instead of being available to every other
`_uno_value_to_plain()` call site. Merged: `_uno_value_to_plain()` now
delegates to it first, so every one of its ~10 call sites gets Date/
DateTime/Duration handling for free, not just the one that happened to
import it directly. `get_custom_properties()` itself switched to call
`self._uno_value_to_plain()` instead of the standalone function
directly, for one real entry point. Re-verified live: a `DateTime`-typed
custom property still correctly converts to an ISO string after the
merge -- no regression.

**Flagged, deferred (found investigating, not this item's scope):**
`set_custom_property_live`'s bridge method (`set_custom_property()`)
accepts a `property_type` parameter that is never actually used in the
method body -- and a live call with `type="number"` on a plain integer
value raised a bare, empty-message `UNO_EXCEPTION`. Not touched this
pass; moved to the PyUNO robustness sweep (item 3) for a proper live
investigation rather than a guess fixed under a different task's banner.

**Still open, not yet audited:** whether every OTHER struct shape that
can realistically appear in a generic property enumeration is now
covered (e.g. `com.sun.star.awt.Color` -- believed to already be a plain
`long`/int in most read paths, not independently confirmed; sequences of
structs, e.g. a `TableSortField[]` read back through a generic property
scan rather than a dedicated getter). `_uno_value_to_plain()` remains,
by design, not a fully general UNO-struct converter -- anything
unhandled still passes through to `str()` at the JSON-encoding boundary,
same as before. `_uno_value_to_plain()` itself has no direct unit test
coverage -- it lives inside `uno_bridge.py`, which cannot be imported
outside a running LibreOffice process (confirmed in #31's own finding),
so it's only exercised via live verification, not the fakes-based suite;
`uno_datetime.py`'s own functions (which it now delegates to) already
have 17 direct unit tests in `tests/test_uno_datetime.py`.

## 3. PyUNO robustness sweep (#33)

**Status: in progress.** `DATABASE_ERROR`/SDBC exception mapping (see
item 1 above) still folds in here, not yet done.

**Real bug found (while investigating #32) and fixed, live-verified:**
`set_custom_property_live`'s bridge method, `set_custom_property()`, has
two write paths depending on whether the named property already exists
-- `container.setPropertyValue()` (UPDATE, existing name) or
`container.addProperty()` (CREATE, new name). A plain Python `int` value
live-verified raises `IllegalTypeException` on the CREATE path only --
confirmed directly: `addProperty(name, PropertyAttribute.REMOVABLE, 42)`
fails, `addProperty(name, PropertyAttribute.REMOVABLE, 42.0)` (a float)
succeeds, and `setPropertyValue(name, 99)` (an int, against an
already-`double`-typed existing property) succeeds and auto-coerces to
`99.0`. Root cause: pyuno can't infer which UNO numeric type a bare
Python `int` should become for a brand-new property with no existing
type to coerce toward; a `setPropertyValue()` call against an existing
property has that type already established and coerces fine. `uno.Any`-
typing the value (this session's usual fix for ambiguous-type UNO calls)
does NOT work here either -- `addProperty` specifically rejects it with
`"uno.Any instance not accepted during method call, use uno.invoke
instead"`, a different UNO API quirk than the sequence-typing pattern
`sort_range()`/`sort_table()` already established. Fixed by coercing a
plain `int` (explicitly excluding `bool`, an `int` subclass in Python --
`isinstance(True, int)` is `True`) to `float` on the CREATE path only.
Rebuilt, redeployed, re-verified live: `set_custom_property_live` with
`value=42` no longer raises, reads back as `42.0`; the UPDATE path and a
`bool` value both still work correctly (no regression). No fakes-based
regression test added -- `UNOBridge` can't be instantiated outside a
running LibreOffice process (its constructor calls `uno.
getComponentContext()`), so this class of bug is only exercisable live,
same constraint #31/#32 already hit.

**Status: done.** Completed the deliberate, systematic sweep across all
five named danger patterns, on the current (much larger -- 8400+ lines,
7 modules added since the original task #13 sweep) codebase.

**Bare `except:` blocks:** zero. The prior sweep's narrowing to `except
Exception:` held completely across every module added since.

**`except Exception:` silent-swallow audit:** wrote a small script to
extract every `except Exception[ as e]:` block's body and flag ones with
no clear action (no raise/return/append/warning/log) or an unused
captured exception variable -- 27 candidates out of 101 total blocks.
Read every one in context. 26 were legitimate, matching established,
already-reviewed patterns: a `None`/`False` fallback the caller can
detect (e.g. `get_headers_footers`'s `header_X: None`,
`get_document_statistics`'s `page_count: None`), the documented
"best-effort, report what applied" convention already used throughout
(`clone_style`/`update_style`'s per-property `applied` list,
`_insert_paragraph_block`'s per-paragraph style reapplication,
`set_shape_geometry`'s flip handling), optional-field shape enrichment
where absence doesn't misrepresent anything (`_shape_geometry`'s
rotation/shear, `get_shape`'s z_order/title/description), or a
try-primary-then-fallback structure (`_comment_id_for`,
`resolve_comment`). One genuine finding, fixed and live-verified:
`get_selection()`'s three per-doc-type blocks (Writer/Calc/Impress-Draw)
had NO signal at all on failure -- unlike every other case above, a
caller had no way to distinguish "nothing selected" from "reading the
selection details failed." Now records a warning string per doc type,
lifted to the envelope's top-level `warnings` field in
`get_selection_live` via the exact same pop-and-lift pattern
`get_view_state_live` already established. Live-verified the happy path
is unchanged (no regression).

**`isinstance()` on UNO interfaces:** re-audited given the file's growth
since task #13's original sweep (19 new `isinstance()` calls added).
Zero touch UNO interface types -- all check plain Python parameter
shapes (`dict`/`list`/`tuple`/`str`/`int`/`float`/`bool`) for dispatch/
validation purposes, a fundamentally different and safe use than the
PyUNO-proxy-identity fragility this pattern warns about. Every real tool
added since task #13 correctly routes document-type detection through
`_get_document_type()`'s `supportsService()`-based check (via
`_require_writer`/`_require_calc`/`_require_draw`/`_require_impress`),
never a bare `isinstance()` on a document/UNO object. The two already-
known, already-documented original-32 legacy cases (`format_text_live`,
`get_document_info_live`) remain the only fragile call sites, unchanged
from task #13's finding and still deliberately left alone to preserve
the original 32 exactly.

**`id()`-based identity:** zero live occurrences (the two grep hits are
both comments explaining why `id()` is deliberately NOT used, documenting
the task #13/85e9b6b fix). `DocumentRegistry` and `ObjectRegistry` both
correctly key by UNO object equality throughout, held consistently
across every module added since.

**Raw `str()` of UNO structs:** found and fixed one genuine case, `get_
comments`'s `"date": str(field.Date)` -- would have produced the raw
struct repr (`"(com.sun.star.util.DateTime){ NanoSeconds = ... }"`) for
any comment with a real date, not a readable value. `get_comments`
backs `get_comments_live` (one of the original 32) but was already
touched by the writer_text.py real-implementation pass (which added
`_comment_id_for()` for `update_comment_live`/`delete_comment_live`/
`resolve_comment_live` to address comments by), so it's not in the
"preserve exactly, never touch" bucket the isinstance() cases are --
fair game, and a purely additive display-quality fix, not a behavior/
detection-logic change. First fix attempt used `uno_datetime_to_iso()`
directly and silently returned `None` even for a genuinely-set date --
caught by testing with a plain duck-typed fake object carrying a real,
non-zero date rather than trusting the property name ("Date" turned out
to mean `com.sun.star.util.Date`, date-only, no `Hours`/`Minutes`/
`Seconds` -- `uno_datetime_to_iso()` requires those and raises
`AttributeError`, caught internally and returned as `None`). Fixed by
using the duck-typed dispatcher, `uno_temporal_value_to_plain()`,
instead of assuming a specific struct shape. Live-verified end to end:
set a real, non-zero date on a comment field via raw UNO, confirmed
`get_comments_live` now returns `"date": "2026-08-18"` instead of the
struct repr or a wrongly-`None`ed value. All other `str()` calls in the
file are normalizing caller-supplied JSON parameter values for a write
operation (e.g. `str(orientation).lower()`), not stringifying UNO
structs -- a safe, different use.

**`dict()` assumptions on UNO sequences:** zero remaining. Only 3 raw
`dict()` calls in the whole file; 2 are on plain Python parameter dicts
(safe), 1 is the exact danger pattern already caught and fixed in an
earlier pass (`get_document_info`'s filter-factory enumeration, with an
explanatory comment: `getByName()` returns a `PropertyValue` tuple, not
a mapping, and `dict()` on it directly raises `TypeError`). The
established `{p.Name: p.Value for p in <sequence>}` comprehension
pattern is used consistently everywhere a `PropertyValue` sequence needs
dict-ifying.

## 4. Writer/Calc/Draw production-hardening

**Status: done, folded into items 1-3 as scoped at the start of this
doc.** The note above the sequencing section already drew the
distinction: genuine capability gaps the spec never planned for
(WriterAgent's review/grammar/document-research subsystems, DuckDB/
forecast/symbolic-math/vision-based Calc analysis) are the parked
spec-gap decision, not touched here; production-hardening depth on
capability the spec already covers is the real scope of this item, and
that's exactly what items 1-3's fixes were -- WRONG_DOCUMENT_TYPE (every
real Writer/Calc/Draw/Impress tool's error path), the silently-dropped
CharLocale/date-struct conversion bugs (Writer formatting/comments),
set_custom_property_live's int-typing crash, and get_selection's silent
failure (spans all four document types). No separate checklist needed
beyond what 1-3 already delivered.

## 5. Packaging + install smoke tests (#36/#37)

**Status: done, with one finding flagged for a separate scope decision.**

**Manifest/packaging verification (#36):** already solid, confirmed by
reading `build-oxt-windows.py`. Every `pythonpath/*.py` module and the
whole `tools/` package are globbed in at build time, not hand-listed --
the comment in the script itself explains why: a hand-maintained file
list silently went stale twice before (`tools/` was missing entirely
until the Phase A+D real-implementation pass, then `uno_datetime.py` was
nearly missed the same way right after fixing that). The build also
hard-fails on any missing source file before writing the archive, and
independently re-opens and `testzip()`s the built `.oxt` to catch a
corrupt archive. This was already correct going in -- no fix needed.

**No automated CI exists in this repo at all** -- confirmed by directly
checking: no `.github/workflows/`, no other CI config file anywhere.
Every verification in this project's history, including this entire
hardening pass, has been run manually. Whether "CI checks every file
ships" (as originally scoped in Buddy's assignment) means "the build
script itself checks this when run" (already true, see above) or "an
automated pipeline runs the build on every push" (not true, and would
need its own infrastructure -- a GitHub-hosted runner has no LibreOffice
preinstalled, needs `apt-get install libreoffice` or equivalent on
first setup) is a real, separate scope decision, not something to build
speculatively under this item. Flagged here rather than either silently
building a CI pipeline or silently skipping the question.

**Scripted clean-profile install -> start -> health-check ->
representative-tool-execute -> uninstall test (#37): built and
live-verified.** `smoke-test-windows.py`, new -- every prior real-
implementation pass's live verification was ad hoc shell commands typed
fresh each time (kill soffice, build, unopkg remove/add, launch,
bootstrap, curl health, curl a tool, clean up); this captures that exact
cycle as a reusable, runnable artifact for the first time. Eight steps:
clean slate -> build -> uninstall any stale deployment -> install ->
launch headless LibreOffice and dispatch `mcp:start_mcp_server` (polling
the real state via a bootstrap-script retry loop, not a fixed sleep) ->
poll `/health` until healthy -> a genuine functional round trip
(`insert_text_live` a marker string, `get_text_content_live` confirms it
reads back) -> uninstall and confirm via `unopkg list` that the
extension is actually gone. Ran it for real: all 8 steps passed cleanly
on the first run, exit code 0, no leftover `soffice` process or `build/`
directory afterward. Also verified the failure path -- pointed
`LIBREOFFICE_PROGRAM_DIR` at a nonexistent directory, confirmed it fails
fast with a clear message and exit code 1 rather than hanging or
false-passing.

## 6. Release-readiness list (#43)

**Status: done.** A plain list of what's solid and what still blocks
calling `mcp-libre` production-ready, as of this hardening pass
(`scaffold/mcp-tooling-phase-a`, items 1-5 above complete, phase 2/
concurrency control not yet started).

### Solid, no known blockers

- **Tool catalog:** ~90 real, live-verified tools across 14 modules
  (`core_runtime.py`, `document_lifecycle.py`, `undo_view_selection.py`,
  `styles.py`, `writer_text.py`, `drawing_objects.py`, `charts.py`,
  `calc_sheets.py`, `calc_data.py`, `calc_page.py`, `impress.py`,
  `draw.py`, `writer_layout.py`, `writer_tables.py`), plus the original
  32 legacy tools, all against real headless LibreOffice 26.2 -- no
  scaffolded modules left. A short list of individual tools stay
  documented stubs, never silently claimed working, split into two
  distinct groups: 5 are genuinely blocked on a UNO API/environment
  limitation (`set_chapter_numbering_live` -- `ChapterNumberingRules.
  replaceByIndex()` raises `IllegalArgumentException` on an unmodified
  round-trip; `mail_merge_live` -- `MailMerge` needs a `DataSourceName`
  registered through `DatabaseContext`, which refuses to register an ad
  hoc `DataSource` without a persisted `.odb`; the 3 slideshow-effect
  tools in `impress.py` -- headless mode's `XSlideShowController` is
  always `None`), the other 12 are unattempted-but-plausible scope
  limits, not blocked (`add_chart_series_live`, 4 animation-mutation
  tools in `impress.py`, `insert/activate_embedded_object_live`,
  `create/refresh/delete_external_link_live`, plus document-events) --
  see each module's own section in `docs/MCP_TOOLING_SCAFFOLD_PLAN.md`
  for why.
- **Error-code consistency:** one shared, validated envelope
  (`envelope.build_error()`/`build_success()`) across every real tool;
  `WRONG_DOCUMENT_TYPE` now correctly wired (was dead code catalog-wide
  before this pass).
- **UNO->JSON conversion:** one shared, tested converter; the
  Locale-struct silent-drop bug (a real, confirmed data-loss case) is
  fixed.
- **PyUNO robustness:** systematic sweep across all five named danger
  patterns complete; zero bare `except:`, zero `id()`-based identity,
  zero unguarded `isinstance()` on UNO interfaces in real-tool code,
  zero `dict()`-on-UNO-sequence bugs; the two live bugs found
  (`get_selection`, `get_comments`) are fixed.
- **Packaging:** the build script can't silently ship an incomplete
  extension (globs source files, hard-fails on anything missing,
  validates archive integrity).
- **Testing discipline:** 434 fakes-based unit tests plus mandatory live
  verification against real headless LibreOffice for every real-
  implementation pass -- not just claimed, demonstrated repeatedly.

### Real, unaddressed gaps -- each needs its own decision, not a silent fix

1. **MCP transport concurrency control -- not started.** Per
   `docs/WRITERAGENT_COMPARISON_MATRIX.md`'s "MCP transport" row (the
   widest, most confident gap in that whole comparison): no global
   backpressure semaphore, no per-document mutation lock, `Mcp-Session-
   Id` minted/echoed but not enforced, no protocol-version validation
   against a supported-version list. This is explicitly Brian's next
   phase (see the top of this doc) -- named here for completeness, not
   because it was missed.
2. **No authentication on the MCP endpoint.** Read directly in an
   earlier research pass (`docs/WRITERAGENT_COMPARISON_MATRIX.md`'s
   "Security" row): loopback-only, no per-caller authorization for a
   tool surface that can read/write/delete real documents. `host_trust.
   py`'s Host/Origin header validation is a real, narrow DNS-rebinding
   mitigation, not authentication -- marked "both weak, neither strong"
   against WriterAgent (which has the identical gap, explicitly accepted
   by WriterAgent as a local-dev-tool risk). Not addressed by this
   hardening pass; a genuine pre-production question if this is ever
   exposed beyond a trusted local machine.
3. **No automated CI.** No `.github/workflows/`, no other CI config --
   every check in this project's history, including this entire
   hardening pass, has been run manually. The build script and the new
   smoke test (`smoke-test-windows.py`) both exist and both work, but
   nothing runs them automatically on push/PR. Needs its own
   infrastructure decision (a LibreOffice-capable runner).
4. **Original 32 legacy tools use a different, flatter error envelope**
   (`{"success": False, "error": "<string>"}`, not the modern structured
   `{"code", "message", "details"}` shape) -- flagged in item 1 above.
   Real inconsistency for any caller trying to handle errors uniformly
   across the full tool catalog; migrating 25+ long-stable legacy call
   sites is a bigger undertaking than this pass's scope.
5. **`DATABASE_ERROR` error code still unreachable.** Declared, never
   mapped -- `preview_mail_merge_live` (the only SDBC-touching code in
   the codebase) would currently surface a malformed-query/connection
   failure as the generic `UNO_EXCEPTION` catch-all instead. Narrow
   (one tool), not yet fixed.
6. **Windows-only tooling.** `build-oxt-windows.py` and
   `smoke-test-windows.py` are both Windows-specific (this project's own
   dev-environment convention throughout); there's an older, likely-
   stale `plugin/install.sh` assuming a Linux/PATH-based `libreoffice`/
   `unopkg` setup, not verified working in this pass. Whether Linux/
   macOS support matters depends on the actual deployment target, not
   evaluated here.
7. **Spec-gap capabilities, explicitly parked by Brian until after this
   hardening phase completes:** vision/screenshot document
   understanding, embeddings/RAG over content, a notebook-cell
   interface, and a Calc analysis engine (DuckDB/symbolic math/
   forecasting/solver) are real WriterAgent capabilities with zero
   presence in the 484-tool spec this project implements. Not a defect
   in what's built -- a scope call still sitting with Brian.

### Bottom line

Nothing above blocks the tool catalog itself from being correct and
live-verified -- it is. What blocks calling the *service* production-
ready, in likely order of consequence if ignored: concurrency control
(phase 2, already scheduled) and authentication (item 2, not scheduled)
if this is ever exposed beyond a single trusted local machine; the rest
(CI, legacy error-envelope migration, `DATABASE_ERROR`, platform
support) are real but narrower and can reasonably wait for their own
deliberate scope calls rather than blocking anything today.

## Phase 2 (after 1-6): MCP transport concurrency control

Done, `plugin/pythonpath/ai_interface.py`. Scope per
`docs/WRITERAGENT_COMPARISON_MATRIX.md`'s "MCP transport" row named four
gaps; this pass closes the two that are actually about concurrency
safety and leaves the other two as a deliberate scope note below.

**The actual bug, found before writing any fix.** The matrix's "no
per-document mutation lock" framing assumes the corruption risk is a
data race between two callers touching the *same* document. Tested that
assumption directly instead of taking it on faith: two threads each
running 300 iterations of `insert_text_live` + `get_text_content_live`
against *different* Writer documents, no lock at all -- corrupted up to
60%+ of one thread's calls with a bare `AttributeError: createTextCursor`
(the method vanishing off a live PyUNO proxy mid-call). The two
documents' content never cross-contaminated in any run, so this is not a
per-document race; it's PyUNO's own proxy/bridge layer corrupting under
any concurrent access, same document or not. Tried the finer-grained fix
the matrix's framing implies anyway (a lock scoped to the mutation calls
only, keyed per document) as a control: errors dropped but didn't reach
zero (95/600 still failed), because it left the object-resolution call
(`doc.getText()`) outside the lock. Only a single process-wide lock
around the *entire* tool-execution sequence -- resolution through
mutation -- reached 0/600 errors, repeatably. That's `_UNO_EXECUTION_LOCK`:
one `threading.Lock()`, not a per-document registry, because the real
constraint is coarser than the matrix's framing assumed.

**Backpressure**, the matrix's other named gap, is a genuinely separate
concern from the lock even though the lock already serializes work:
without a cap, a burst of concurrent requests still each spin up their
own OS thread (`ReusableThreadingTCPServer`'s inherited
`ThreadingTCPServer` behavior, unbounded) and all pile up waiting on the
lock -- fine for a handful of callers, a real resource-exhaustion risk
for hundreds. `_ADMISSION_SEMAPHORE` (`threading.BoundedSemaphore`,
`MAX_CONCURRENT_TOOL_CALLS = 4`) is acquired with a timeout
(`ADMISSION_TIMEOUT_SECONDS = 30`) before the lock; a caller that can't
be admitted in time gets a `ServerBusyError`, mapped to a real HTTP 503
+ `Retry-After` header on the REST path (`_send_busy_response`). On the
JSON-RPC path it's caught by `mcp_jsonrpc.py`'s existing broad
`except Exception` and surfaces as a generic `INTERNAL_ERROR` (-32603)
rather than a dedicated JSON-RPC busy code -- `mcp_jsonrpc.py` is
deliberately UNO/HTTP-free and unit-testable standalone, so it doesn't
know about transport-level exception types; teaching it one is a
reasonable, narrow follow-up, not done this pass.

**Live verification.** `ai_interface.py` imports `mcp_server` ->
`uno_bridge` -> `uno`, so it can't be imported outside a live LibreOffice
process (same constraint `tests/test_host_trust.py`'s docstring notes
for `host_trust.py`'s UNO-free sibling) -- this can't be a pytest unit
test. `concurrency-probe-windows.py` is the reusable version of the ad
hoc empirical test above, built on `smoke-test-windows.py`'s
install/launch/health-check harness: builds and installs the real .oxt,
opens two Writer documents, dispatches the real extension, then runs 2
threads x 300 iterations (600 concurrent round trips) against the live
HTTP tool-execution path. Run for real: **600/600 succeeded, 0 errors**,
clean uninstall after. 434/434 existing unit tests still pass (no
regression from the two files it touches).

**Scope note -- not addressed this pass.** The matrix's other two named
gaps, `Mcp-Session-Id` minted/echoed but not enforced and no
protocol-version validation against a supported-version list, are
protocol-conformance gaps, not concurrency-safety gaps -- grouped under
the same "MCP transport" row in the matrix but a different kind of
problem (a client sending a stale/wrong session ID or an unsupported
protocol version isn't a thread-safety risk). Left out of this phase
deliberately rather than folded in silently; flagging for Brian's call
on whether they're their own follow-up item or fold into the
release-readiness list (`docs/HARDENING_PLAN.md`'s bottom-line section
above).

## Phase 3 (after Phase 2): MCP transport protocol conformance

Brian's call (2026-08-18): the two protocol-conformance gaps Phase 2
scoped out -- `Mcp-Session-Id` enforcement and `MCP-Protocol-Version`
validation -- become their own item, due before 1.0, not reopening or
holding up the concurrency-control work above (which stays closed).

**Status: done.** `plugin/pythonpath/mcp_jsonrpc.py` +
`plugin/pythonpath/ai_interface.py`.

**Getting the actual rules right, not guessed at.** Both gaps have
precise MUST/SHOULD language in the MCP spec's Streamable HTTP transport
doc, read directly before writing anything (`https://modelcontextprotocol.io/specification/2025-06-18/basic/transports`
and `.../basic/lifecycle`) rather than inferred from the matrix's one-
line framing:

- *Session management.* "Servers that require a session ID SHOULD
  respond to requests without an `Mcp-Session-Id` header (other than
  initialization) with HTTP 400 Bad Request." / "The server MAY
  terminate the session at any time, after which it MUST respond to
  requests containing that session ID with HTTP 404 Not Found."
- *Protocol version header.* "If the server receives a request with an
  invalid or unsupported `MCP-Protocol-Version`, it MUST respond with
  400 Bad Request." / backwards-compat clause: if the header is absent
  and there's no other way to identify the version, the server SHOULD
  assume `2025-03-26`, not reject the request.
- *Version negotiation at `initialize`* (lifecycle doc, not the
  transport doc): "If the server supports the requested protocol
  version, it MUST respond with the same version. Otherwise, the server
  MUST respond with another protocol version it supports" -- a normal
  successful `initialize` result with the server's own version
  substituted, not a JSON-RPC error.

**A real scope boundary found doing this research, deliberately not
touched.** The spec has since split into two eras: "legacy"
(initialize-handshake, protocol versions `2025-11-25` and earlier -- what
this project implements) and "modern" (`2026-07-28` and later --
version declared per-request via `_meta`, no handshake, a mandatory
`server/discover` RPC). This project's `mcp_jsonrpc.py` only implements
legacy-era message shapes; adopting the modern per-request model would
be a much larger, separate architectural change (a new RPC, a different
negotiation model entirely), not a conformance tweak. Not attempted here
-- flagging for Morgan/Brian if supporting modern-era clients ever
becomes a real requirement. This pass stays entirely within the legacy
era the rest of the codebase already speaks.

**What changed, `mcp_jsonrpc.py` (pure, no UNO/HTTP dependency, same
split as every other function in this module -- see its own docstring):**

- `SUPPORTED_PROTOCOL_VERSIONS = ("2024-11-05", "2025-03-26",
  "2025-06-18")` -- the three legacy protocol versions this server's
  actual wire format (no per-request `_meta`, no `server/discover`)
  hasn't changed across. `LATEST_PROTOCOL_VERSION` and
  `DEFAULT_PROTOCOL_VERSION` (`"2025-03-26"`, the spec's own
  backwards-compat fallback) derive from it.
- `_handle_initialize()` now actually negotiates: echoes the client's
  requested version if it's in the supported set, otherwise substitutes
  `LATEST_PROTOCOL_VERSION` -- replacing the prior permissive "always
  echo back whatever the client asked for" behavior the module docstring
  used to flag as a known gap.
- `SessionRegistry`, a small thread-safe set of active session IDs
  (`create_session`/`has_session`/`end_session`) -- the mutable state the
  session-management rules above need. Pure bookkeeping, no document/UNO
  concept involved (this is a transport-level protocol session, not a
  `DocumentRegistry` handle).
- `check_protocol_version_header(header_value)` and
  `check_session_header(is_initialize, header_value, session_registry)`
  -- pure functions returning `None` (proceed) or `(http_status,
  json_rpc_error_body)` (reject), encoding the MUST/SHOULD rules above
  exactly. Both fully unit-tested in `tests/test_mcp_jsonrpc.py` (15 new
  tests: initialize negotiation, `SessionRegistry` lifecycle, both check
  functions' every branch) -- 449/449 passing (434 prior + 15 new), no
  regressions.

**What changed, `ai_interface.py` (HTTP-transport wiring):**

- Module-level `_SESSION_REGISTRY = mcp_jsonrpc.SessionRegistry()`,
  same lifetime as `_UNO_EXECUTION_LOCK`/`_ADMISSION_SEMAPHORE` (one per
  running server process; sessions don't survive a `soffice` restart,
  consistent with there being no other per-session state to restore
  either).
- `_handle_mcp_jsonrpc()` now runs both header checks before dispatch
  reaches the message-routing layer at all (skipped for `initialize`
  itself, which mints a session and hasn't negotiated a version yet).
  On `initialize`, the minted session id is registered via
  `_SESSION_REGISTRY.create_session()` -- previously minted but never
  stored anywhere, so nothing could actually validate against it later.
- `do_DELETE()` now calls `_SESSION_REGISTRY.end_session()` for real.
  The prior version always returned `200 {"status": "session
  terminated"}` regardless of what (if anything) was in the header --
  an acknowledgment with no effect. Now: missing header -> 400, unknown
  id -> 404, known id -> actually removed and 200 -- and a later request
  reusing that same id gets 404, not silently accepted.

**Live verification.** Same constraint as Phase 2:
`ai_interface.py` imports `mcp_server` -> `uno_bridge` -> `uno`, so it
can't be imported outside a live LibreOffice process, and the actual
HTTP-header wiring (as opposed to the pure logic functions, which are
unit-tested directly) can't be a pytest test either.
`transport-conformance-probe-windows.py`, new, built on the same
build/install/launch/health-check/uninstall harness
`concurrency-probe-windows.py` established -- one Writer document (no
concurrency angle to this probe, so no need for two), then 15 live HTTP
checks against the real running extension: `initialize` mints a session
and negotiates version correctly (including the fallback case); `tools/
list` returns 400 missing the session header, 404 on an unknown one,
200 on the real one; 400 on an unsupported `MCP-Protocol-Version`
header, 200 when it's absent entirely; `DELETE` terminates a real
session (200), a reused post-DELETE session id then correctly gets 404
instead of 200, and `DELETE` itself follows the same missing/unknown
header rules (400/404). Ran it for real: **15/15 checks passed**, clean
`unopkg list`-confirmed uninstall after, no leftover `soffice` process
or `build/` directory.

**Not touched, deliberately out of scope for this item:** the JSON-RPC
path's admission-semaphore busy response (Phase 2's noted follow-up --
`ServerBusyError` surfaces as a generic `INTERNAL_ERROR` rather than a
dedicated busy code on `/mcp`, unrelated to session/version conformance);
adopting the modern (`2026-07-28`+) per-request protocol era, per the
scope-boundary note above.
