# Object handle design: sheets, slides, shapes, tables, charts

Mandated item #2 of Buddy's four-item order (blocking further Phase C/D
real implementation): "Design stable non-document object handles before
drawing/charts/Impress go real. Sheets, slides, shapes, tables and charts
need identity semantics before dozens of tools start passing names/
indexes around."

## The categorical split

Not every object category needs the same mechanism. The spec's own
already-scaffolded parameter shapes (see `plugin/pythonpath/tools/
calc_sheets.py`, `impress.py`, `drawing_objects.py`, `charts.py`,
`writer_tables.py`) already signal two different design intents, and
this design follows that signal rather than forcing one mechanism onto
every category:

- **`sheet`/`slide`** parameters are typed as plain strings (`sheet`) or
  explicitly documented as `"Slide index or name"` (`slide`, an
  untyped/polymorphic schema entry) -- never `sheet_id`/`slide_id`. The
  spec is already asking for live name-or-index addressing here, not an
  opaque handle.
- **`shape_id`, `chart_id`, `table_id`** are always plain opaque strings,
  matching `document_id`'s own naming convention. The spec is already
  asking for a handle here.

**Decision: honor that distinction.** Sheets and slides resolve directly
against UNO's own live named/indexed containers, every call, no registry.
Shapes/charts/tables resolve through a registry-backed opaque handle,
reusing (a generalized version of) the exact mechanism `DocumentRegistry`
already uses for `document_id` -- except for the sub-cases (Writer
tables, Calc sheets' own chart collection) where UNO already guarantees
a unique persistent name and minting a random handle on top of that would
just be redundant state to keep in sync. Each is explained below.

## Sheets: resolve by `sheet` (name), no registry

Calc sheets always have a UNO-assigned `Name` (never anonymous, unlike
shapes), and `XSpreadsheets` is itself a live `XNameAccess` container --
`getByName()` is a direct O(1) native UNO lookup, cheaper than a dict
lookup through a registry we'd have to maintain. There's no untitled-sheet
edge case analogous to an unsaved Writer document, either: a sheet is
never nameless.

**Resolution rule for every tool taking `sheet: string`:** try
`sheets.getByName(sheet)` first. If that raises/fails and `sheet` is
composed entirely of digits, fall back to `sheets.getByIndex(int(sheet))`
(0-based) -- this is what several of the scaffolded tools' own purpose
text already promises ("Activate sheet by name/index.") even though the
JSON Schema type is a plain string; a digit-only string is the only way
to express "by index" within that string-typed parameter, so this is the
literal, non-guessing interpretation of "name/index" given the type the
spec's Key Parameters column already committed to. A `destination_index`
parameter (seen on `move_sheet_live`/`copy_sheet_live`) is always an
int and always means *position*, not identity -- the same ordinal-vs-
identity split already established for `writer_text.py`'s 1-based
paragraph numbers vs. its 0-based character-range `target`.

## Slides: resolve by `slide` (index or name), no registry

Same reasoning, and here the spec is even more explicit: every `slide`
parameter in `impress.py` is schema'd as
`{"description": "Slide index or name."}` with no `type` constraint at
all -- an intentionally polymorphic parameter, not an oversight. This
already solves the "index shifts under reordering" identity trap Buddy's
mandate is worried about, the same way WriterAgent's `document_url`-or-
`RuntimeUID` duality solves the analogous problem for documents (see
`docs/DOCUMENT_TARGETING_DECISION.md`): a client that needs stability
across reorders addresses by name instead of index.

**Resolution rule:** Python `int` -> `pages.getByIndex(slide)` (0-based).
Python `str` -> `pages.getByName(slide)`, with the same digit-string
fallback to index as sheets, for consistency. No registry needed --
`XDrawPages` is a live `XIndexAccess`/`XNameAccess` container, resolved
fresh every call, same as sheets.

## Shapes, and charts/tables without a natural unique name: `ObjectRegistry`

Unlike sheets/slides, UNO gives shapes no persistent, guaranteed-unique
identifier at all. A shape's `Name` property exists but defaults to an
empty string and is not required to be unique -- most shapes on a page
are anonymous unless a client (or us) explicitly assigns names, which
would be an unwanted side effect just to support addressing. This is a
genuine identity gap, not a "just use the Name" case like sheets/slides,
so it needs an actual registry.

**`plugin/pythonpath/tools/object_registry.py`'s `ObjectRegistry`** is
that registry: the same mechanism `DocumentRegistry` already uses for
`document_id` (an id<->UNO-object map keyed by the object itself via
`__eq__`/`__hash__`, not `id()`, so PyUNO's re-minted-proxy-per-fetch
behavior can't spoof a duplicate registration -- the exact bug already
fixed once for `DocumentRegistry`, see its docstring), generalized so any
non-document object category can reuse it.

**Scoped per document, not global.** `DocumentRegistry.get_object_registry
(document_id)` lazily creates one `ObjectRegistry` instance per
`document_id` and drops it in `unregister_document()` -- so a
`shape_id`/`chart_id`/`table_id` handle's lifetime is naturally bounded
by its owning document's, without needing a UNO dispose listener on
every individual shape. This was already flagged as the intended shape
in `documents.py`'s own pre-existing docstring ("those likely want their
own per-document registries rather than reusing this class directly"),
and per-document scoping turns out to be the more tractable choice for
eviction too: `close_document_live` already exists as a clean,
already-called hook, so dropping a document's object handles piggybacks
on work that's already happening, rather than needing new dispose-
listener machinery `DocumentRegistry` itself still doesn't have for the
out-of-band-close case.

A future Phase C/D pass consumes this as:
`ctx.document_registry.get_object_registry(document_id).register_object(shape)`
during a discovery tool (`list_shapes_live`, etc.), and
`.resolve_object(shape_id)` on every subsequent `get_shape_live`/
`delete_shape_live`/etc. call. `ObjectNotFoundError` maps to
`OBJECT_NOT_FOUND`, the same code `DocumentNotFoundError` already maps
to -- no new error code needed.

**Applies to:** Draw/Impress/Writer shapes in general (no reliable unique
name). Writer and Impress embedded charts that aren't addressable through
Calc's dedicated named chart collection (see below) also fall back to
this -- an embedded chart there is really just a shape (an OLE/graphic
object) wrapping a chart document, with the same anonymity problem.

**Accepted tradeoff, deliberately not solved here:** one `ObjectRegistry`
per document mixes shape handles and chart handles (and table handles,
for the categories that use it) in a single flat id-space rather than
separate per-type namespaces. A client could theoretically pass a
`shape_id` where a `chart_id` is expected and get back the wrong-typed
object. This isn't guarded against at the registry level -- the
resolving tool is expected to check `supportsService()`/the object's
actual type before operating on it anyway, matching the
`_require_writer()`-style convention already used throughout the real-
implementation modules, so a type-confused handle surfaces as a clean,
mapped error (`UNSUPPORTED_CAPABILITY` or similar) at the tool level
rather than as a registry-level guarantee. Simpler than maintaining N
separate per-type registries per document for a case that already fails
safely one layer up.

## Tables and Calc charts: prefer the UNO-native unique name over minting a handle

Two sub-cases don't need `ObjectRegistry` at all, because UNO already
guarantees a unique persistent name for them:

- **Writer tables** (`table_id` in `writer_tables.py`): `XTextTablesSupplier
  .getTextTables()` is a named `XNameAccess` container -- Writer enforces
  a unique `Name` per text table in a document (auto-assigned "Table1",
  "Table2", ... unless renamed), the same guarantee sheets have.
- **Calc's own chart collection** (`chart_id` in `charts.py`, when the
  chart lives in a spreadsheet): `XChartsSupplier.getCharts()` is also a
  named `XNameAccess` container with the same uniqueness guarantee
  ("Chart 1", "Chart 2", ... auto-assigned).

**Resolution rule for these:** the `table_id`/`chart_id` string *is* the
object's own UNO `Name` -- resolve directly via `getTextTables().getByName
(table_id)` / `getCharts().getByName(chart_id)`, no registry, no minted
handle. This is cheaper, human-debuggable in server logs, and avoids
inventing state to track something UNO already tracks natively. It still
satisfies the spec's `"_id"`-suffixed, opaque-string parameter contract
from the client's point of view -- clients aren't meant to parse or rely
on a handle's internal structure regardless of whether it's a UUID or a
native UNO name.

Charts embedded in Writer or Impress (not going through
`XChartsSupplier`) don't get this guarantee and fall back to
`ObjectRegistry` as described above -- so `chart_id` resolution is
genuinely mixed by host document type; the tool implementing `get_chart_live`
et al. needs to check which case it's in (Calc doc with a matching
`XChartsSupplier` entry, vs. everything else) before choosing which
resolution path to use.

## Summary table

| Category | Parameter | Mechanism | Registry? |
|---|---|---|---|
| Sheet | `sheet: string` | live `getByName()`, digit-string falls back to `getByIndex()` | No |
| Slide | `slide: index or name` | live `getByIndex()`/`getByName()` per Python type | No |
| Writer table | `table_id: string` | live `getTextTables().getByName()` -- the id *is* the UNO Name | No |
| Calc chart | `chart_id: string` | live `getCharts().getByName()` -- the id *is* the UNO Name | No |
| Shape | `shape_id: string` | `DocumentRegistry.get_object_registry(document_id).resolve_object()` | Yes, per-document |
| Writer/Impress embedded chart | `chart_id: string` | same `ObjectRegistry` as shapes | Yes, per-document |

## What's built now vs. left for the real-implementation pass

Built and tested this pass (design + reusable primitive, not yet wired
into any tool -- no Phase C/D module goes real from this alone):
`plugin/pythonpath/tools/object_registry.py`'s `ObjectRegistry`, and
`DocumentRegistry.get_object_registry()`/its eviction-on-
`unregister_document()` wiring in `documents.py`. Both are unit-tested
(`tests/test_object_registry.py`, plus four new cases in
`tests/test_document_registry.py`) the same way `DocumentRegistry` itself
was before anything consumed it.

Left for whichever pass makes Calc-sheets/Impress/Draw/drawing-objects/
charts real: the actual `_resolve_sheet()`/`_resolve_slide()` helpers
(mirroring `document_lifecycle.py`'s `_resolve_and_register()` pattern),
wiring `list_shapes_live`/`list_charts_live`-style discovery tools to
populate `ObjectRegistry` via `register_object()`, and live-verifying the
full resolve-a-real-handle-through-a-real-tool path -- none of that is
consumed by a real tool yet, so it hasn't been exercised end to end.

The three UNO API claims this design's category split depends on *were*
independently live-verified against a real headless LibreOffice 26.2
instance this pass (not just asserted from memory of the UNO API
surface), since getting one of them wrong would misfile an entire object
category into the wrong mechanism: (1) a Calc sheet's `getCharts()`
returns a name-accessible (`getByName`-capable) container; (2) a newly
inserted Writer table auto-gets a unique `Name` (`"Table1"`) via
`getTextTables()`, confirmed via `getElementNames()`; (3) two distinct,
newly-created Draw shapes both default to an empty-string `Name` (`''`
== `''`), and a draw page's shape container has no `getByName()` at all
-- only index access -- confirming shapes have no UNO-native identity to
resolve by, unlike sheets/tables/Calc-charts.

## Licensing note

No WriterAgent code informed the mechanism decisions in this document
directly -- `ObjectRegistry` is a straightforward generalization of
`DocumentRegistry`, a mechanism already implemented in this project
before the WriterAgent research pass ran. The reordering/index-identity
concern this document addresses for slides was raised by Brian/Buddy
directly, not sourced from WriterAgent.
