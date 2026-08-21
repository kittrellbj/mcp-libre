# `wait_for_document_event_live` concurrency decision

Routed to Morgan (Architect) by Buddy, 2026-08-21, off the live finding in
`docs/MCP_TOOLING_SCAFFOLD_PLAN.md`'s "Live-verification pass: mcp-libre
Part 2's newest 4 tools" section: `wait_for_document_event_live` blocks
while holding `ai_interface.py`'s process-wide `_UNO_EXECUTION_LOCK` for
its full `timeout_ms`, so it can never observe an event triggered by
*another tool call through the same HTTP server* -- confirmed live with a
positive/negative pair (same-HTTP-path edit: times out every time, event
lands only after; raw-UNO-connection edit bypassing the lock: picked up
in ~3s). That defeats the tool's primary intended use (one agent driving
both the edit and the wait through this tool surface).

## Decision

**Cap how long a single call may hold `_UNO_EXECUTION_LOCK`. Do not carve
a module-boundary exception into the lock itself.** Keep the tool's name
and parameter shape (`event_types`, `timeout_ms`) unchanged for spec
conformance. Change what happens internally:

- `wait_for_document_event_live` clamps its actual wait to
  `min(timeout_ms, _MAX_WAIT_LOCK_HOLD_MS)` (proposed 2000ms) regardless
  of the caller-requested `timeout_ms`, and returns `timed_out: true` at
  the cap if nothing matched, exactly like a real timeout -- the caller
  cannot tell a capped return apart from a genuine timeout, which is
  correct: from the caller's perspective both mean "nothing matched
  within what this call was willing to wait."
- A caller that wants to wait longer than the cap re-issues the call
  (a client-side polling loop, each call getting its own fair turn at
  `_UNO_EXECUTION_LOCK` alongside any interleaved edit call). Document
  this explicitly in the tool's `purpose` string and docstring: "waits
  are capped at `_MAX_WAIT_LOCK_HOLD_MS` per call regardless of
  `timeout_ms`; poll by re-calling for longer waits."

This fixes the live-verified bug (a single call monopolizing the lock for
its entire requested duration, starving the concurrent call that would
produce the awaited event) while keeping every change inside
`uno_bridge.py`/`tools/undo_view_selection.py`, the files Sabrina already
owns and has full context on.

## Alternatives considered

**1. Carve a scoped exception into `_UNO_EXECUTION_LOCK` for this one
tool** (release the lock around the actual `_event_condition.wait()`,
re-acquire only for the fast, idempotent `_ensure_document_event_capture()`
registration call). Mechanically sound -- read `uno_bridge.py`'s
`wait_for_document_event()`: the blocking phase makes zero further UNO
calls, it's pure Python state (`threading.Condition` over a deque
populated by `_DocumentEventCapture.documentEventOccured`, which runs on
LibreOffice's own event-dispatch thread, already decoupled from
`_UNO_EXECUTION_LOCK`). But achieving it cleanly requires giving
`uno_bridge.py` access to the same `_UNO_EXECUTION_LOCK` object
`ai_interface.py` owns, which today is deliberately singular (see the
comment above that lock's definition: "exactly one place... needs to
acquire the concurrency-control primitives"). `uno_bridge.py` can't import
it from `ai_interface.py` directly -- `ai_interface.py` already depends on
`uno_bridge.py` transitively (`ai_interface -> mcp_server ->
tools.context -> uno_bridge`), so that import would cycle. Fixing it right
means relocating the lock's canonical definition to a new shared
low-level module both files import, then re-running the exact concurrency
stress test that produced the lock's 0/600-vs-95/600 evidence to confirm
the relocation didn't reopen that hole. That's a real refactor of a
correctness-critical, already-hardened primitive, for the benefit of one
P3 tool that has never yet worked for its primary use case. Rejected: the
risk is disproportionate to the payoff, and a cheaper fix (below) reaches
the same practical outcome.

**2. Redesign as pure non-blocking poll** (drop `timeout_ms` entirely,
one immediate check per call, caller supplies `since_seq` and loops
client-side with its own delay -- essentially folding this tool into
`get_document_events_live` with a `since_seq` filter). Same safety
profile as the decision above and an even smaller diff, but changes the
tool's parameter contract (`timeout_ms` becomes meaningless / a validation
error). Rejected in favor of the capped-wait design above only because it
preserves the existing `event_types`/`timeout_ms` signature the spec
names -- worth revisiting if `_MAX_WAIT_LOCK_HOLD_MS` turns out too short
to be useful in practice (see Open question below).

**3. Leave as a documented known limitation.** Rejected: the tool is
implemented, merged, and currently non-functional for its stated primary
use case (0-for-N against the real use case, confirmed live) with a cheap
fix available -- "known limitation" is the right call when no cheap fix
exists, not here.

## Why the cap value matters, and why 2000ms is a starting point, not a
derived number

The cap trades off two things pulling in opposite directions: too long,
and a single `wait_for_document_event_live` call still meaningfully
delays a concurrent edit call queued behind `_UNO_EXECUTION_LOCK` (same
failure shape as today, just bounded instead of unbounded); too short,
and the tool degenerates into `get_document_events_live` with extra
ceremony, forcing the caller into a tight re-poll loop that spends more
of its own round-trip overhead than the wait saves. 2000ms is a
placeholder, not measured -- Sabrina should live-verify the actual
edit-call latency this blocks behind (a `_UNO_EXECUTION_LOCK`-held Writer
paragraph-insert, the typeset-run's dominant call shape) and set the cap
from that, not from this document's guess.

## Implementation notes for Sabrina

- `uno_bridge.py`'s `wait_for_document_event()`: add the
  `_MAX_WAIT_LOCK_HOLD_MS` clamp to the `deadline` computation; no other
  change to the wait loop itself.
- `tools/undo_view_selection.py`'s `wait_for_document_event_live`
  docstring/`purpose`: document the cap and the re-call-to-continue-
  waiting contract.
- `docs/HARDENING_PLAN.md`/`docs/MCP_TOOLING_SCAFFOLD_PLAN.md`: update the
  "Found, not fixed -- flagged for a decision" bullet once shipped, same
  as this project's convention for every other resolved item in those
  docs (strike-through + pointer to the fixing commit).
- Live-verify with the same positive/negative pair Sabrina already ran
  (same-HTTP-path edit interleaved with the wait) -- this time the edit
  should complete and the wait should observe it, within one or two
  poll cycles, instead of timing out every time.
- No change needed to `ai_interface.py` or `_UNO_EXECUTION_LOCK`'s
  definition at all.
