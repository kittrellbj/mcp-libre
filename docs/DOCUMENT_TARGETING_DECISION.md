# Document targeting decision: `document_id` vs `document_url`

Mandated item #1 of Buddy's four-item order (blocking further Phase C/D
real implementation): "Standardize `document_id` targeting before Phases
B-D... compare against WriterAgent's `document_url` parameter +
`X-Document-URL` header approach; don't default-copy either, pick
deliberately and document why."

## Decision

**Keep `document_id`/`DocumentRegistry` as the one targeting mechanism for
every tool that needs to address a specific open document.** Do not add a
`document_url` parameter or an `X-Document-URL` header. This applies
going forward to every Phase C/D module (Calc, Impress, Draw, drawing
objects, charts) exactly as it already applies to Phase A: a tool takes
`document_id` if and only if the spec's own parameter list for that exact
tool includes it (the rule already established and applied consistently
in `document_lifecycle.py`, `styles.py`, and `writer_text.py` -- see
those modules' "Real implementation pass" sections above). This document
is about the underlying *mechanism* two different tools' `document_id`
parameters both resolve through, not about which tools get the parameter
-- that per-tool question stays governed by "match the spec's own
parameter list," unchanged.

## How WriterAgent does it (read-only architectural reference; GPLv3+,
no code copied -- see the licensing note at the bottom)

WriterAgent has no persistent registry at all. Every tool call re-resolves
its target live: it enumerates the LibreOffice desktop's currently-open
components and matches the caller-supplied string against either the
component's file URL or its UNO-native `RuntimeUID` (a session-scoped
identifier LibreOffice itself exposes per open component, present even
for untitled/unsaved documents that have no file path yet, and stable
across Save-As while a file URL is not). Clients get a `document_url`
parameter on every tool call, or an `X-Document-URL` HTTP header as a
per-connection alternative; if neither is given, the resolver falls back
to whichever document currently has focus. A `list_open_documents`-style
tool exposes both `url` and `uid` per open document so a client can pick
whichever is stable for its situation.

## Why `document_id`/`DocumentRegistry`, not `document_url`, for mcp-libre

`DocumentRegistry` already solves the two hard problems WriterAgent's
URL-or-UID split exists to solve, via a different mechanism:

- **Stability across Save-As.** `DocumentRegistry` keys its dict by the
  *UNO document object itself* (using object identity via `==`/`hash`,
  not `id()` -- see the proxy-identity bug fixed earlier this project),
  not by path. A document's `document_id` does not change when the file
  is saved to a new path, exactly like WriterAgent's `RuntimeUID` doesn't,
  without needing a tool to carry two different string shapes (URL vs.
  UID) or a resolver that tries one then the other.
- **Untitled/unsaved documents.** Because the registry key is the object,
  not a URL, a brand-new unsaved document registers and resolves exactly
  like a saved one -- there's no missing-URL edge case to special-case in
  every tool, unlike a URL-first scheme that needs a UID fallback
  specifically for this situation.

And `document_id` resolution is cheaper per call: a dict lookup, not an
enumeration over every open LibreOffice window. WriterAgent's live
resolve-by-enumeration cost is bounded by open-document count rather than
tool count, so it's not necessarily a problem at WriterAgent's scale --
but there's no reason to pay it when the registry already gives O(1)
lookup for free.

Switching to `document_url` now would also mean re-touching every
already-shipped, already-live-verified Phase A tool that takes
`document_id` (22 in `document_lifecycle.py` alone) to re-derive the same
guarantees `DocumentRegistry` already provides, for no behavioral gain.

## What's adopted from WriterAgent's design (reimplemented independently,
not copied) because it's a genuine gap

Three things WriterAgent's design gets right that are worth checking
against mcp-libre's own state, independent of which addressing mechanism
either project uses:

1. **A three-way distinct error taxonomy for resolution failures**
   (unknown tool name / no document open at all / supplied identifier
   doesn't resolve to anything open), checked in that order, before any
   tool-body work happens. **Already true in mcp-libre, confirmed this
   pass, not a gap:** unknown tool names return a distinct
   `"Unknown tool: <name>"` shape from the dispatcher before any handler
   runs (live-verified: see `list_documents_live` typo in this pass's own
   testing); `document_lifecycle.py`'s `_map_exception_to_code` already
   splits `NoActiveDocumentError` -> `NO_ACTIVE_DOCUMENT` from
   `DocumentNotFoundError`/`KeyError` -> `OBJECT_NOT_FOUND` as genuinely
   distinct codes.
2. **A per-result "which document did this actually run against" echo**,
   so a client that omitted `document_id` (falling back to "active
   document") can confirm after the fact which document a call landed on
   -- relevant because the active document can change due to user focus
   between when a client decides to omit the parameter and when the call
   executes. **Already true in mcp-libre, confirmed this pass, not a
   gap:** `envelope.build_success()`'s top-level `document_id` field is
   populated on every real tool response already (visible in every
   `curl` response captured across this project's live-verification
   passes), not something that needs adding.
3. **Per-document mutation serialization**, so two concurrent MCP clients
   mutating the *same* open document don't race, while two clients
   mutating *different* documents (or any read-only calls) proceed fully
   concurrently. **This is a real, currently-unaddressed gap in
   mcp-libre** -- there is no per-document lock anywhere in
   `mcp_server.py`/`ai_interface.py` today. This is a concurrency-control
   concern layered *on top of* addressing, not an addressing-mechanism
   question, so it doesn't change the `document_id` decision above --
   but it's a real design item for the `/mcp` transport work (mandated
   item #4), since the transport layer is where concurrent requests from
   multiple clients first become possible. Flagged there, not solved
   here.

## Not yet independently live-verified (follow-up, not blocking)

`DocumentRegistry`'s untitled/unsaved-document handling has not been
explicitly live-tested against a real never-saved document in this
project (WriterAgent's own test suite doesn't cover this against real
UNO either -- their tests mock the desktop/document objects throughout,
per the research pass that fed this decision). Worth a targeted live
check in a future pass, not blocking this decision since the underlying
mechanism (object-identity keying) has no structural reason to behave
differently for a saved vs. unsaved document.

## Licensing note

This decision was informed by a read-only research pass over WriterAgent
(`E:\Tools\writeragent`, GPLv3+) restricted to describing architecture and
behavior in prose, with no WriterAgent source code copied, quoted, or
reproduced anywhere in this document or in mcp-libre (MIT). Every
mechanism mcp-libre uses here (`DocumentRegistry`, the error-code split,
the `document_id` result echo) was already implemented independently in
earlier passes of this project, before this research pass ran; this
document's role is comparing and justifying against WriterAgent's
approach, not deriving from its code.
