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
  documented stubs, never silently claimed working: 5 remain, all
  genuinely blocked on a UNO API/environment limitation
  (`set_chapter_numbering_live` -- `ChapterNumberingRules.
  replaceByIndex()` raises `IllegalArgumentException` on an unmodified
  round-trip; `mail_merge_live` -- `MailMerge` needs a `DataSourceName`
  registered through `DatabaseContext`, which refuses to register an ad
  hoc `DataSource` without a persisted `.odb`; the 3 slideshow-effect
  tools in `impress.py` -- headless mode's `XSlideShowController` is
  always `None`) -- see each module's own section in
  `docs/MCP_TOOLING_SCAFFOLD_PLAN.md` for why. `create/refresh/delete_external_link_live` (Calc) moved out of
  this list in a follow-up pass -- real UNO mechanism turned out to be
  `com.sun.star.sheet.XAreaLinks` (`doc.AreaLinks`), a genuinely separate,
  CRUD-capable mechanism from the pre-existing `ExternalDocLinks`
  read-only enumeration, live-verified end to end including a real REST
  round trip against the rebuilt/reinstalled extension.
  `add/update/delete/reorder_animation_live` (Impress) also moved out of
  this list in a further follow-up pass -- real mechanism is the generic
  `com.sun.star.animations` module (not LibreOffice's internal preset
  library, which isn't reachable from the public UNO API at all),
  live-verified end to end including a real REST round trip; see
  `uno_bridge.py`'s `add_animation()`/`reorder_animations()` docstrings
  for two live findings from that verification (the `UserData`-based
  `node-type` mechanism, and animcore node proxies not comparing equal
  across independently-obtained references). `add_chart_series_live`
  (Calc) also moved out of this list in a further follow-up pass --
  real mechanism is `XDataProvider.createDataSequenceByRangeRepresentation`
  against a scratch sheet range (chart2 has no value-array constructor
  on the public interface), live-verified end to end including a real
  REST round trip; see `uno_bridge.py`'s `add_chart_series()` docstring
  for a live finding from that verification (an initial version wrote
  `categories` to cells but never wired them into any data sequence,
  caught by reading the raw chart2 series back independently).
  `get_document_events_live`/`wait_for_document_event_live` and
  `insert_embedded_object_live` (scoped to `object_type="formula"`) also
  moved out of this list in a further follow-up pass (v2.0.4) --
  real mechanism for the events pair is a single process-wide
  `com.sun.star.document.XDocumentEventListener` registered against
  `com.sun.star.frame.GlobalEventBroadcaster`, feeding a bounded,
  seq-numbered buffer with a `threading.Condition`-based blocking wait;
  for embedded-object insertion it's a `com.sun.star.drawing.OLE2Shape`
  with its `CLSID` set before `page.add()`, using the one CLSID
  (Math formula) trusted without live confirmation -- see
  `uno_bridge.py`'s "-- Document events --" section and
  `insert_embedded_object()`/`_EMBEDDED_OBJECT_CLSIDS` docstrings.
  Code-complete and unit-tested (469/469), but **not yet live-verified**:
  this pass's REST round trip against a real running instance is still
  pending, since the extension's one live instance was held for a
  separate overnight Writer-agent test and, checked directly afterward,
  was carrying an unsaved `modified: true` document with no backing file
  -- a rebuild/relaunch to live-verify would have destroyed it.
  `activate_embedded_object_live`, the last of the original 4, also
  moved out of this list (v2.0.5) -- drives `XEmbeddedObject.changeState()`
  via the shape's own `ExtendedControlOverEmbeddedObject` property.
  **Now live-verified (v2.0.6)**, once the held instance was free, and
  scoped down by what that verification found: `LOADED`/`RUNNING` work
  and are fast; `INPLACE_ACTIVE`/`UI_ACTIVE`/`ACTIVE` hang `changeState()`
  -- and the entire soffice process, not just the call -- indefinitely
  against a headless instance, confirmed reproducibly twice. Those three
  now raise `UNSUPPORTED_CAPABILITY` naming the finding rather than being
  attempted. The same live pass also fixed `insert_embedded_object_live`
  for Writer (`com.sun.star.drawing.OLE2Shape` isn't on Writer's own
  `createInstance()` factory -- confirmed `ServiceNotRegisteredException`
  live; fixed via `com.sun.star.text.TextEmbeddedObject` +
  `insertTextContent()` instead, plus two shared-code follow-on fixes in
  `_shape_geometry()`/`delete_shape()`) and found, but did not fix,
  a real limitation in `wait_for_document_event_live`: it blocks while
  holding the process-wide `_UNO_EXECUTION_LOCK`, so it can't observe an
  event triggered by another tool call through the same HTTP server --
  see `docs/MCP_TOOLING_SCAFFOLD_PLAN.md`'s "Live-verification pass"
  entry for the full evidence on all of the above. Architecture decision
  made 2026-08-21, not yet implemented -- see
  `docs/EVENT_WAIT_CONCURRENCY_DECISION.md`. This closes out Part
  2's 12 shared-service scope-limited stubs and `drawing_objects.py`'s
  remaining tool, live-verified.
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

## Phase 4 (after Phase 3): 2026-08-19 typeset-run remediation + durable guidance

Brian ran an extended agentic build (typesetting "Creativity and AI",
~19hr elapsed across two sessions) purely through the `:8765` MCP tool
surface and logged every problem hit along the way
(`mcp_problems_log.txt`, routed by Buddy). The book shipped, but only
after routing around 15 distinct product bugs. Standing decision: treat
this as the bar for "best practices to support agentic workflows," not a
one-off cleanup -- fix the 15, and write up durable guidance so the same
*classes* of bug don't recur.

**Status: done.** `fix/p0-remediation-08-20-2026`, `d208e64` (P0/P1) ->
`f4499a4` (P2/P3) -> `87bc458` (#8/#11 investigation) -> this pass.

### Corrected bug count: 13 real defects, not 15

Two of the original 15 logged findings were misdiagnoses, settled with
live evidence rather than assumed clean and moved past -- **name them
specifically here so neither gets re-litigated as still-open:**

- **#8** (`create_paragraph_style_live` catalog/dispatcher divergence):
  never existed -- `git log -S` across all commits, zero results. The
  real tool is `create_style_live` with `family="ParagraphStyles"`. The
  original tester's own captured `GET /tools` snapshot never contained
  `create_paragraph_style_live` either -- a name guessed by analogy with
  `create_page_style_live`, correctly rejected, misreported as a
  catalog/dispatcher mismatch. Structurally can't diverge: `/tools` and
  `/execute` share one `tools_dict` singleton (see bullet 5 below).
- **#11** (`set_shape_geometry_live` not resizing): already worked.
  `shape.Size` set directly on the resolved shape, unchanged since
  before the bug was logged. Confirmed two ways: the original session's
  own saved artifact (23 differently-sized source images all landing at
  one uniform requested width) and a fresh live repro this pass (insert
  3000x2000, resize to 9000x6000, independent `get_shape_live` readback:
  8999x6001).

The other 13 are real, all fixed except **#15**, deliberately left as a
documented architecture flag (see `batch_execute_live`'s own purpose
string) rather than a band-aid -- a real fix needs subprocess-level
isolation or a cooperative cancellation token, since a thread-based fake
timeout would abandon a zombie thread still holding the process-wide
`_UNO_EXECUTION_LOCK`, blocking every future call, not just that batch.

| # | Finding | Status |
|---|---------|--------|
| 1 | `set_page_layout(mirrored=...)` -- wrong UNO enum namespace | Fixed, `d208e64` |
| 2 | Session permanently stuck after last doc closed | Fixed, `d208e64` |
| 4 | `update_index_live` silent reversion, `success=true` | Fixed + fail-loud guard, `d208e64` |
| 5 | `batch_execute_live` scrambles position-sensitive inserts | Fixed for insert/heading/page-break, `d208e64`; extended this pass, see below |
| 6 | `save_as_document_live` serializes a phantom near-empty frame | Fixed, `d208e64` |
| 7 | `at_paragraph`/`at_position` semantics undocumented | Doc fix, `f4499a4` |
| 9 | `append_paragraph_live` partial-apply on unknown style | Fixed, `f4499a4` |
| 10 | `soffice.exe --version` hangs | Doc fix, `f4499a4` |
| 12 | `insert_toc_live` not idempotent | Fixed, `f4499a4` |
| 13 | `set_document_properties_live` case-sensitive keys | Fixed, `f4499a4` |
| 14 | `get_document_statistics_live` paragraph undercount | Fixed, `f4499a4` |
| 15 | `batch_execute_live` no per-op timeout | Documented architecture flag, not fixed |

### New finding this pass: BUG #5's fix didn't reach every tool with the same shape

Auditing bullet 3 below (batching safe-or-unsafe) against the actual
code, rather than taking BUG #5's fix as blanket coverage, turned up two
more tools with the identical defect shape: `apply_page_style()` and
`remove_page_break()` both resolve an omitted position through
`_current_paragraph_index(doc)` (the VIEW cursor) but, unlike
`insert_paragraph()`/`insert_heading()`/`insert_page_break()` after the
original fix, never resynced that cursor afterward -- so an explicit or
defaulted position set by one batched call couldn't be inherited by a
later omitted-position call in the same batch. Never triggered in
Brian's original repro (he didn't batch these two specifically), but the
same mechanism, live-confirmed.

Fixed with the identical resync pattern the original fix established
(reposition the view cursor to the paragraph just acted on, best-effort,
never fails an otherwise-successful call). Live-verified with a new
probe, `batch-page-style-probe-windows.py`: three paragraphs, then a
batch of `[apply_page_style(paragraph=1, insert_break=true),
remove_page_break(position omitted)]` -- the omitted call must resolve
paragraph 1, inherited from the prior call, not some unrelated stale
position. **Mutation-tested both directions:** reverting the fix and
rerunning the same probe against the same repro, `remove_page_break_live`
resolved paragraph 4 (the stale view-cursor position left over from
document creation/activation -- unrelated to paragraph 1) and the probe
correctly failed; with the fix restored, it resolves paragraph 1 and the
probe passes. No fakes-based regression test possible -- same
`UNOBridge`-can't-instantiate-outside-LibreOffice constraint every other
UNO-only fix in this doc has hit.

### Durable guidance -- the six standing-decision bullets

Written up as concrete, evidence-checked status, not restated as
aspirational rules -- some are already true project-wide, some are only
true where the originating bug was found and fixed, one is fully open.

1. **No `success=true` on partial-apply or state reversion.** Enforced
   at the two points where it was found broken: #4's `update_index_live`
   (paragraph-count-before/after fail-loud guard) and #9's
   `append_paragraph_live` (style validated before any edit, so an
   unknown style fails atomically instead of partially applying). Not
   yet a codebase-wide invariant with automated enforcement -- no
   lint/test catches a *new* tool introducing the same shape. That's a
   code-review-time discipline today, not a structural guarantee; a
   systematic audit across all ~90 real tools (same spirit as
   `test_map_exception_to_code_covers_every_branch` in item 1's #31
   work) would be the way to make it one, not attempted this pass.
2. **Every mutating call echoes the document/session id.** Already true
   for 339 of 348 `envelope.build_success()` call sites project-wide
   (audited this pass). Of the 9 without it, all are legitimately
   document-less: 8 are server-level tools in `core_runtime.py`
   (`get_server_info_live`, `list_tools_live`, etc. -- no document
   concept at all) and the 9th, `get_document_events_live`, is a
   process-wide multi-document event feed where each individual event
   already carries its own `document_id` (see `_public_document_event`).
   This was substantially already the existing convention
   (`envelope.py`'s `document_id` parameter) before this standing
   decision was written -- not new work, a confirmation.
3. **A batching path is automatically order-safe or explicitly
   documented as unsafe.** Partially true, a real gap found and fixed
   this pass. `batch_execute_live`'s own purpose string documents the
   one known-unsafe-by-design gap (#15, no per-op timeout). The
   position-drift class (#5) now covers `insert_paragraph`/
   `insert_heading`/`insert_page_break`/`apply_page_style`/
   `remove_page_break` (the last two fixed this pass, see above) --
   confirmed by grep, these five are the only callers of
   `_current_paragraph_index(doc)` for an omitted position, so no sixth
   instance is currently unaudited. Still no single enumerated
   safe/unsafe list in one place -- a caller has to read each function's
   own docstring to learn this. Flagging as a real, still-open
   documentation gap rather than closing the bullet.
4. **Named-resource creates are idempotent (get-or-create).** Fixed for
   the one instance found (#12, `insert_toc_live`, get-or-create by
   service name + title). Audited two other named-resource creates this
   pass: `create_style()` already fails loud on a duplicate name
   (`FileExistsError`) -- a different but compliant shape (reject, never
   silently duplicate or silently no-op); `create_named_range()` has no
   existence check at all -- calling it twice with the same name is
   unaudited, unverified behavior (UNO's `addNewByName()` could raise,
   silently overwrite, or duplicate, not confirmed either way). Flagged
   here rather than assumed safe.
5. **`/tools` catalog and `/execute` dispatch share one source of
   truth.** Already true, structurally guaranteed -- confirmed directly
   by #8's own investigation: both the catalog endpoint and dispatch
   read the same `tools_dict` singleton, so a genuine catalog/dispatcher
   split isn't representable in this architecture without a second
   registry existing somewhere, which there isn't. Nothing to fix; the
   bullet was written from a misdiagnosed symptom (#8), not an actual
   gap.
6. **Stats/verification tools match ground-truth enumeration.** Fixed
   for the one instance found (#14): `get_document_statistics_live`'s
   `paragraph_count` now shares the same filtered `_count_paragraphs()`
   helper `get_paragraph_count_live` already used. No other stats tool
   audited against its own ground-truth counterpart this pass -- scope
   was the one reported defect, not a sweep of every statistic in the
   catalog.

## Phase 5: `wait_for_document_event_live` capped-wait fix -- implemented per
Morgan's decision, but the primary use case is still not restored

`docs/EVENT_WAIT_CONCURRENCY_DECISION.md`'s decision implemented exactly
as specified: `uno_bridge.py`'s `wait_for_document_event()` now clamps
its actual wait to `min(timeout_ms, _MAX_WAIT_LOCK_HOLD_MS)`, no other
change to the wait loop, `ai_interface.py`/`_UNO_EXECUTION_LOCK` itself
untouched. **Status: implemented and live-verified for what it actually
does; live evidence shows it does not achieve what the decision doc
predicted it would. Escalating back to Morgan rather than declaring this
closed.**

**The cap value, measured not guessed, per the decision doc's explicit
ask.** `edit-latency-probe-windows.py` (new), 100 real HTTP round trips
of `append_paragraph_live`/`insert_heading_live` (the typeset-run's
dominant call shape) against a real headless LibreOffice instance: min
5.0ms, median 29.1ms, p95 44.8ms, max 62.7ms, each figure already
including its own full `_UNO_EXECUTION_LOCK` hold. First attempt at this
measurement returned a suspicious, uniform ~2000-2100ms per call
regardless of operation -- read as a red flag rather than trusted
(real UNO work for a single-paragraph insert has no reason to be that
uniform), traced to `urllib.request` resolving `"localhost"` on this
Windows dev box adding a large, constant per-connection delay unrelated
to any server-side work; switching the probe to `127.0.0.1` directly
dropped every sample by roughly 40x and produced the real, tightly-
clustered numbers above. `_MAX_WAIT_LOCK_HOLD_MS = 500` set from that:
roughly 8x headroom over the measured max, for heavier call shapes this
pass didn't probe (image/table inserts, saves), while keeping the worst
case one wait call can cost a queued *other* call an order of magnitude
below the original 2000ms placeholder.

**Re-verified with the same positive/negative pair Sabrina's original
finding used, per Morgan's explicit instruction -- and the result
diverges from the decision doc's prediction.** New probe,
`event-wait-concurrency-probe-windows.py`:

- **Cap mechanics: confirmed working exactly as specified.** Every
  `wait_for_document_event_live` call in both runs held the lock for
  512-528ms (the 500ms cap plus normal call overhead), never anywhere
  near the requested 5000ms `timeout_ms` -- the starvation-bounding half
  of the fix is real and verified.
- **Negative control (event from OUTSIDE this tool's own lock): still
  works, no regression.** A raw UNO connection (bypasses
  `_UNO_EXECUTION_LOCK` entirely, same mechanism as a human GUI edit)
  firing an edit genuinely concurrently with an active
  `wait_for_document_event_live` call was observed correctly, on the
  first poll attempt. (First attempt at this control ran the raw edit
  *then* started the wait -- sequential, not concurrent -- and failed
  for the wrong reason, the same snapshot-timing issue below; caught by
  rereading the original finding's own methodology before trusting a
  "regression," not assumed. Fixed the probe to fire the edit on a
  background thread genuinely overlapping an active wait call, matching
  what the original finding actually tested.)
- **Positive pair (the tool's own primary use case -- same agent's edit
  and wait through the same HTTP surface): still does not work, even
  with the cap, even across 8 poll attempts (4s of capped waiting).**
  Confirmed this is not a capture failure: a diagnostic read via
  `get_document_events_live` immediately after the failed poll loop
  shows the edit's `OnModifyChanged` event genuinely fired and is
  sitting in the buffer (`seq: 2`) -- it was simply never seen as "new"
  by any of the 8 wait calls. Reproduced identically on two independent
  runs.

**Why, mechanically -- read from the actual code, not guessed at.**
`wait_for_document_event()` takes its "what counts as new" snapshot
(`snapshot_seq = self._event_seq`) at the moment each call *starts*, and
that same call holds `_UNO_EXECUTION_LOCK` for its entire duration
(acquired once, in `ai_interface.py`, around the whole tool-execution
sequence -- confirmed by reading `_execute_tool_sync`'s `with
_UNO_EXECUTION_LOCK: result = self.mcp_server.execute_tool(...)`). Since
the edit call needs that identical lock, it structurally *cannot* run
while a wait call holds it -- it can only run in the gap between one
wait call releasing the lock and the next one acquiring it. Whichever of
{the queued edit, the caller's next wait call} wins that gap's lock
acquisition determines the outcome, and neither branch lets the caller
observe its own edit:

- If the edit wins the race: it runs to completion and fires its event
  *before* releasing the lock, so by the time the next wait call
  acquires the lock and takes its own fresh snapshot, that event is
  already in the past relative to that snapshot -- not "new."
- If the next wait call wins the race instead: the edit still can't run
  at all during that wait call's window (same starvation as before,
  just bounded to 500ms instead of unbounded) -- cycle repeats.

There is no interleaving where a wait call's snapshot is taken *before*
the edit's event lands *and* that same wait call is still actively
blocked (not yet returned) when it lands -- because the lock fully
serializes the two calls with no overlap window. **This is a property of
there being any positive-sized cap at all, not of 500ms specifically --
a 1ms or a 100000ms cap fails identically**, since the mechanism doesn't
depend on cap magnitude at all.

**Corrected the tool's own claims rather than ship an overclaim.** The
tool's `purpose` string and `wait_for_document_event_live`'s docstring
(written first pass, before this evidence existed) originally implied
re-polling would let a caller observe its own interleaved edit -- not
literally false (each poll *does* get a fair, bounded turn at the lock,
which is what was asked for), but reasonably read as promising more than
what's actually verified. Corrected both to state plainly, with the live
evidence, that this only reliably works for events from outside this
tool's own lock.

**Not fixed this pass, deliberately -- this needs Morgan's call, not a
same-pass silent redesign.** Making the primary use case actually work
would need a real design change to the wait/snapshot contract itself
(e.g., a caller-supplied `since_seq` so continuity is tracked across
polls instead of re-derived from "now" at each call's entry) -- Morgan's
decision doc explicitly scoped this pass to "no other change to the wait
loop itself" and preserving the existing `event_types`/`timeout_ms`
signature (rejecting the non-blocking-poll redesign, Alternative 2, for
exactly that signature-preservation reason). Changing the snapshot
semantics is exactly that kind of signature/contract change the decision
doc reserved for a future call, not something to fold in silently under
"implement the cap." Routed back to Morgan/Buddy: does the tool's
primary use case matter enough to warrant that further design change, or
does "reliably works for external events, bounded-but-non-functional for
self-triggered ones" become the documented, accepted shape going
forward?

**Testing.** 474/474 passing (no count change -- no fakes-based
regression test possible, same `UNOBridge`-can't-instantiate-outside-
LibreOffice constraint as every other UNO-only fix in this project).
Both new probes (`edit-latency-probe-windows.py`,
`event-wait-concurrency-probe-windows.py`) are new, reusable artifacts,
not one-off ad hoc commands, matching this project's `smoke-test-
windows.py`-established convention.

**Morgan's decision (2026-08-21): accept the current shape, do not chase
the fix this pass.** Confirmed the diagnosis is structural, not a tuning
problem -- any positive cap value fails the same way, since the wait's
contract ("events new since my snapshot-at-entry") and the producer/
consumer serialization on `_UNO_EXECUTION_LOCK` mean the two calls can
never overlap in time. Explicitly rejected redesigning the wait/snapshot
contract now: that's new API surface (a caller-supplied cursor, e.g.
`since_event_id`, params/docs/caller-learning-curve), a second design
decision layered on top of "clamp the timeout," for a P3 tool whose
primary use case has never worked for any caller in this project's
history -- no evidence anyone is currently blocked on it. Same
disproportionate-risk-for-the-payoff logic as rejecting the
`_UNO_EXECUTION_LOCK` exception-carve alternative in the original
decision. What shipped is kept as a real, standalone improvement:
correctness-critical lock untouched, the external-event path verified
and bounded, the docstring now tells the truth instead of overclaiming.

**Open backlog item, named explicitly so it isn't mistaken for closed:**
`wait_for_document_event_live` cannot observe self-triggered events
(its own caller's edit through the same HTTP surface) -- only events
from outside its own lock (a separate raw UNO connection, a human GUI
edit). Fixing this for real needs cursor-based continuity across polls
(a caller-supplied position replacing the current per-call
snapshot-at-entry), which changes the tool's parameter contract --
revisit only if a real caller actually needs the self-triggered path,
per Morgan's call above. Not tracked anywhere else; this paragraph is
the record.

## Phase 6: new tools (Brian's priority order) + `get_document_statistics_live`
rewrite -- in progress, posting per-tool per the standing "post progress
per tier" convention rather than batching

Brian's 2026-08-21 new-tools assignment, 15 items total, his priority
order (full rationale/schemas in his own message, quoted verbatim by
Buddy when assigning). Item 1 (statistics rewrite) is tracked as its own
item below the table since it replaces an existing tool's shape rather
than adding a new one; items 2-15 are new tools, "Part 3." Explicitly
NOT adding a standalone `get_selected_text_live` per Brian's own
redundancy note -- `get_selection_live` already covers it.

| # | Tool | Status |
|---|------|--------|
| 2 | `find_cells_live` | **Done, live-verified** -- see below |
| 3 | `get_slide_content_live` | **Done, live-verified** -- see below |
| 4 | `find_shape_text_live` | **Done, live-verified** -- see below |
| 5 | `get_presentation_content_live` | **Done, live-verified** -- see below |
| 6 | Writer page number on `get_view_state_live` | **Done, live-verified** -- see below |
| 7 | `goto_page_live` | Queued |
| 8 | `list_fonts_live` | Queued |
| 9 | `activate_draw_page_live` | Queued |
| 10 | `get_draw_page_live` | Queued |
| 11 | `update_cell_comment_live` | Queued |
| 12 | `get_freeze_panes_live` | Queued |
| 13 | `get_sheet_summary_live` | Queued |
| 14 | `get_document_snapshot_live` | Queued |
| 15 | `extract_document_text_live` | Queued |

**`find_cells_live` (#2, "the biggest obvious Calc hole").** Built to
Brian's exact schema (`query`, `sheet`, `range`, `look_in`, `match`,
`case_sensitive`, `max_results` -> `{matches: [{sheet, address, value,
formula}], count, truncated}`). New `UNOBridge.find_cells()`
(`uno_bridge.py`, right after `get_used_range()`) plus the
`find_cells_live` tool wrapper in `calc_sheets.py` (chosen over
`calc_data.py` -- directly related to and placed adjacent to
`get_used_range`, which the range-omitted search path reuses). Scope
deliberately bounded, not a full-grid scan: `range` given -> just that
range; `range` omitted -> each candidate sheet's own used range (same
cursor technique `get_used_range()` already established); `sheet`
omitted -> every sheet in the workbook, each match reporting which
sheet it came from. A `_FIND_CELLS_MAX_SCANNED_CELLS` backstop
(200,000) additionally bounds worst-case scan cost independent of
`max_results`, distinguished in `truncated`'s reasoning (though not
currently surfaced as two different values -- both report `truncated:
true`, a possible future refinement if a caller needs to tell them
apart). `look_in="comments"`/`"all"` pre-builds a `{(col,row): text}`
dict from the sheet's `Annotations` once per sheet rather than a fresh
linear scan per candidate cell. `match="regex"` invalid input raises
`ValueError` with the real `re.error` message, mapped to
`INVALID_PARAMETER` -- not a raw traceback, not silently matching
nothing.

Fakes-based plumbing tests (`tests/test_calc_sheets.py`,
`test_find_cells_live`/`test_find_cells_live_rejects_invalid_look_in_
and_match`) plus a real registry-catalog entry
(`tests/test_tool_scaffold_contract.py`). Live-verified against real
headless LibreOffice Calc with a new probe,
`find-cells-probe-windows.py` -- 12 checks, all passing, against real
data (values, a formula, a cross-sheet comment): finds by value within
one sheet and across the whole workbook when `sheet` is omitted; finds
formula text under `look_in="formulas"` while confirming `"values"`
mode does NOT match formula text (would find the computed result, not
the formula string) -- and the same values/comments cross-check in the
other direction; `match="exact"` case-insensitively matches a whole
cell but correctly rejects a partial substring `"contains"` would
accept; `match="regex"` finds a real pattern and a genuinely invalid
regex reports `INVALID_PARAMETER` cleanly; `max_results` caps the count
and sets `truncated: true`; a query with zero real matches reports
`count: 0`, `truncated: false`, an empty list -- not silently omitted
or defaulted to something misleading.

476/476 tests passing (474 + 2 new).

**`get_slide_content_live` (#3, "give me all the content of slide 7").**
No exact schema was specified for this one in Brian's message (only the
rationale -- avoid `list_shapes_live` + N `get_shape_live` calls), so it
was built to match the per-slide entry shape Brian *did* specify exactly
for `get_presentation_content_live` (#5, still queued): `{index, name,
hidden, text: [{shape, text}], notes}`. Deliberate choice, not a guess --
`get_presentation_content_live` will wrap N of these in bulk, so sharing
one shape now means it can reuse `UNOBridge.get_slide_content()` in a
loop later rather than duplicating the per-slide read logic.

New `UNOBridge.get_slide_content()` (`uno_bridge.py`, placed right after
`get_speaker_notes`/`set_speaker_notes`, whose `_find_notes_shape()` it
reuses for the notes read) plus the `get_slide_content_live` tool
wrapper in `impress.py`. `slide` is required (index or name, same
`_resolve_slide()` every other per-slide impress.py tool uses) --
unlike `get_presentation_content_live`, this tool's whole point is "one
specific slide," so there's no meaningful "all slides" default to fall
back to.

Only shapes with non-empty `getString()` text are included in `text`
(same "skip if falsy" convention `_shape_summary()` already established
for `list_shapes_live`) -- an empty placeholder or a pure image shape
contributes nothing to a text-content read. Each entry's `shape` key is
the shape's own UNO `Name` (e.g. "Title 1", matching Brian's own
example), not a registry `shape_id` -- this is a read-only content dump,
not an addressable-object mint; `list_shapes_live` already covers
minting `shape_id`s for callers that need to act on a specific shape
afterward. `include_shape_metadata=true` additionally reports each
entry's short type name and geometry, reusing `_get_shape_type`/
`_shape_geometry` (the same helpers `list_shapes_in_container`'s
summaries use) -- optional, since most callers just want text.
`include_notes=false` omits the `notes` key from the result entirely
rather than setting it to `null`, so a caller can tell "didn't ask"
apart from "asked, page genuinely has no `NotesShape`" (a real
`LookupError`, mapped to `notes: null`).

Fakes-based plumbing tests (`tests/test_impress.py`:
`test_get_slide_content_live`, `test_get_slide_content_live_omits_
notes_key_when_not_requested`, `test_get_slide_content_live_with_shape_
metadata`, `test_get_slide_content_live_unknown_slide`) plus the
registry-catalog entry (`tests/test_tool_scaffold_contract.py`).
Live-verified against real headless LibreOffice Impress with a new
probe, `slide-content-probe-windows.py` -- 10 checks, all passing,
against real data (a titled text shape, a deliberately empty rectangle
shape, real speaker notes, a second hidden empty slide): the titled
shape's real text is returned; the empty shape contributes nothing
(exactly 1 text entry, not 2 with an empty string); notes default to
included and match the real speaker-notes text; `include_notes=false`
omits the `notes` key entirely, confirmed by key absence not a `null`
check; `include_shape_metadata=true` adds `type`/`width`/`height` to the
text entry, `=false` (the default) omits them; a hidden, shapeless
second slide reports `hidden: true` and `text: []`; an unknown slide
name fails cleanly (`success: false`), not a raw traceback.

480/480 tests passing (476 + 4 new). One pre-existing issue flagged,
not touched this pass: `uv run pytest` (bare, no args) currently aborts
collection entirely on 3 files unrelated to this work --
`tests/test_client.py`, `plugin/test_plugin.py`,
`tests/test_insert_fix.py` -- with `ImportError`/`ModuleNotFoundError`
on `mcp.shared.memory.create_connected_server_and_client_session` /
`mcp.server.fastmcp`. Confirmed via `git stash` against the prior commit
(`7bb8233`) that this predates this pass's changes -- a `mcp` SDK/venv
version drift, not a regression introduced here. The 480/480 figure
above is `uv run pytest --ignore=plugin/test_plugin.py
--ignore=tests/test_client.py --ignore=tests/test_insert_fix.py`, i.e.
the fakes-based suite this whole remediation effort has been tracking;
a bare `uv run pytest` needs that drift fixed first before it can even
start collecting. Worth its own pass -- not silently worked around
here, and not blocking this tool's own verification.

**`find_shape_text_live` (#4, "shared search across Impress/Draw
shapes, optionally Writer/Calc drawing objects").** No exact schema was
given for this one either; `query`/`match`/`case_sensitive`/
`max_results` reuse `find_cells_live`'s established search-tool shape
rather than inventing a new one, since both are "find text somewhere in
the document" primitives -- the shape-level counterpart to that tool's
cell-level search.

New `UNOBridge.find_shape_text()` (`uno_bridge.py`, placed right after
`get_shape_details`) plus the `find_shape_text_live` tool wrapper in
`drawing_objects.py`, placed right after `list_shapes_live` (both are
container-scoped shape enumeration primitives). A new
`_iter_shape_text_containers()` helper does the per-doc-type container
list: Writer's single document-wide draw page (`container` ignored,
same as `_resolve_shape_container()`); a named/indexed Calc sheet's own
draw page, or every sheet's if `container` is omitted; a named/indexed
Impress/Draw page, or every page's if omitted -- mirroring
`find_cells()`'s "container given -> just that one; omitted -> every
candidate, each match reporting which one it came from" scope
discipline. The bridge method returns raw UNO shape objects paired with
their container label, not JSON; minting `shape_id`s via
`ObjectRegistry` stays the tool layer's job, the same split
`list_shapes_in_container()` already established. Stops as soon as
`max_results` matches are found or a 5000-shape scan backstop is hit --
the same runaway-scan pattern `find_cells()` uses, scaled down since a
document's shape count is normally orders of magnitude below its cell
count.

Fakes-based plumbing tests (`tests/test_drawing_objects.py`:
`test_find_shape_text_live_registers_and_returns_ids`,
`test_find_shape_text_live_container_scopes_the_search`,
`test_find_shape_text_live_rejects_invalid_match`) plus the
registry-catalog entry (`tests/test_tool_scaffold_contract.py`).
Live-verified against real headless LibreOffice Impress with a new
probe, `find-shape-text-probe-windows.py` -- 10 checks, all passing,
against real data (two slides, a matching shape on each, a deliberately
empty shape): omitted `container` searches every slide and reports each
match's real slide name; `container` scopes the search to just that
slide; the empty shape and a non-matching shape contribute nothing;
`match="exact"` case-insensitively matches the full text but correctly
rejects a partial substring; `match="regex"` finds both slides' shapes
and a genuinely invalid regex reports `INVALID_PARAMETER` cleanly;
`max_results` caps the count and sets `truncated: true`; the minted
`shape_id` round-trips through the `ObjectRegistry` (resolvable by a
follow-up `get_shape_live` call). Scoped to Impress -- the doc type
Brian's assignment names first, and the one where container-scoping
(one slide vs. every slide) is actually exercised. Writer/Calc container
resolution shares the exact same `_resolve_shape_container()`-family
helpers already live-verified across all four doc types by
`list_shapes_live`/`get_shape_live`/`insert_shape_live` in the original
`drawing_objects.py` pass -- not independently re-verified by this
probe, flagged plainly rather than implying broader coverage than this
pass actually has.

483/483 tests passing (480 + 3 new). Same bare-`uv run pytest` collection
gap noted above -- unchanged by this tool, still queued as the first
item after step 5 wraps.

**`get_presentation_content_live` (#5, bulk counterpart to
`get_slide_content_live`).** Schema was already fixed by #3's own
design note (see above) -- the per-slide entry shape `{index, name,
hidden, text: [{shape, text}], notes}` was built to be reused here
rather than guessed fresh, so this tool is a loop, not a new read path:
`{slides: [...], count}`.

New `UNOBridge.get_presentation_content()` (`uno_bridge.py`, placed
right after `get_slide_content()`) plus the
`get_presentation_content_live` tool wrapper in `impress.py`, right
after `get_slide_content_live`. `slides` omitted -> every slide in the
deck, in order (`doc.getDrawPages()`, index 0..N); `slides` given ->
just those, in the order given, same index-or-name `_resolve_slide()`
convention every per-slide call already uses, resolved by
`get_slide_content()` itself so there's no second resolution path to
keep in sync. `include_notes`/`include_shape_metadata` pass straight
through to `get_slide_content()` unchanged, same meaning as there.
`include_hidden=false` is the one genuinely new behavior this tool adds
over a hand-rolled loop of `get_slide_content_live` calls: it drops any
slide whose own `hidden` comes back `true`, so a caller wanting "what
the audience actually sees" doesn't need a second round-trip per slide
to check first.

Fakes-based plumbing tests (`tests/test_impress.py`:
`test_get_presentation_content_live_returns_every_slide_in_order`,
`test_get_presentation_content_live_scopes_to_given_slides`,
`test_get_presentation_content_live_can_exclude_hidden_slides`,
`test_get_presentation_content_live_omits_notes_key_when_not_
requested`) plus the registry-catalog entry
(`tests/test_tool_scaffold_contract.py`). Live-verified against real
headless LibreOffice Impress with a new probe,
`presentation-content-probe-windows.py` -- 11 checks, all passing,
against a real 3-slide deck (slide 1 titled + notes, slide 2 hidden and
empty, slide 3 titled): omitted `slides` returns all 3 in deck order
with each slide's real text/notes; `include_hidden=false` drops the
hidden slide and keeps `count` honest for what's left; `slides=[0, 2]`
scopes to just those two, in the order given; `include_notes=false`
omits the `notes` key on every slide, not just null; `include_shape_
metadata=true` adds type/geometry to every slide's text entries.

487/487 tests passing (483 + 4 new). Same bare-`uv run pytest`
collection gap noted above -- unchanged by this tool, still queued as
the first item after step 5 wraps.

**Writer page number on `get_view_state_live` (#6).** Not a new tool --
an enrichment to an existing one. `get_view_state_live` already
reported a document-type-specific position for calc (`active_sheet`)
and impress/draw (`current_page_name`), but Writer fell through both
`if`/`elif` branches and reported no page position at all. Added a
`writer` branch to `UNOBridge.get_view_state()` (`uno_bridge.py`)
alongside the existing two: `controller.getViewCursor()` implements
`com.sun.star.text.XPageCursor`, whose `getPage()` returns the 1-based
page the cursor is currently on -- the same number Writer's own status
bar shows, not a 0-based index. Same best-effort try/except-with-
warning pattern the calc/impress branches already use, so a read
failure reports `current_page_number: None` plus a `warnings` entry
rather than raising.

Fakes-based plumbing tests (`tests/test_undo_view_selection.py`:
`test_get_view_state_live_reports_writer_current_page_number`,
`test_get_view_state_live_omits_page_number_for_non_writer_docs`; the
existing `test_get_view_state_live_reports_zoom_and_selection` updated
for the new field). No registry-catalog change needed -- this is an
existing implemented tool, not a new name. Live-verified against real
headless LibreOffice Writer with a new probe,
`view-state-page-number-probe-windows.py` -- 6 checks, all passing: a
fresh single-page document reports `current_page_number: 1`; after
`set_paragraph_text_live` + a real `insert_page_break_live` (which
resyncs the view cursor to the new paragraph per the BUG #5 fix --
see `insert_page_break`'s docstring), the same call reports
`current_page_number: 2` -- a real page break moving a real cursor,
not a stale or cached value -- while `zoom_value`/`has_selection` are
still reported alongside it.

489/489 tests passing (487 + 2 new). Same bare-`uv run pytest`
collection gap noted above -- unchanged by this tool, still queued as
the first item after step 5 wraps.
