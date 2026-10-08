# Architecture review procedure

Read before classifying or conducting an architecture review.
These are mandatory procedures routed by [AGENTS.md](../../AGENTS.md).
They do not authorize a new milestone or target mutation.

- `architecture-reviewer` (`.codex/agents/architecture-reviewer.toml`) is an
  independent read-only advisor to the owner, not an autonomous approval or
  convergence authority. For an architecture-sensitive plan, run one FULL
  PLAN review before presenting the plan to the owner. APPROVE goes to owner
  approval; APPROVE_WITH_CHANGES may receive obvious bounded nonblocking
  corrections and then goes to the owner without an automatic full re-review;
  BLOCK stops automatic work and returns the finding IDs, evidence, impact,
  smallest corrections and implementer recommendation to the owner. Never
  redesign and repeatedly review until APPROVE. A further full PLAN review
  requires an explicit owner request, except that one new review may follow a
  materially changed owner-approved architecture revision.
- Architecture DIFF review is risk-based. HIGH-RISK changes require one FULL
  DIFF review: canonical-state ownership, filesystem transactions/first save,
  migration, secret or credential persistence/security boundaries, Execution
  Node or process lifecycle/cancel/recovery, artifact/bundle trust or source
  authority, Vault/container-runtime architecture, a new persistence layer, or
  public/versioned contract architecture. MEDIUM-RISK changes normally rely on
  the PLAN review and need DIFF review only when the approved plan requires it,
  implementation changes architecture materially, or the owner requests it;
  examples include typed CRUD on the existing lifecycle, server model
  extensions, service editor integration and topology UI on existing
  contracts. LOW-RISK layout/labels/display fields, application-config value
  additions, CLI formatting, documentation, straightforward tests and bounded
  fixes within an approved contract normally require no architecture review.
- Per architecture review gate, the maximum automatic budget is one initial
  FULL review plus at most one TARGETED_RECHECK of owner-approved corrected
  blocker IDs. The recheck inspects only those findings and the immediately
  affected boundary. If it still BLOCKS, stop and return to the owner; there is
  no third automatic cycle. Nonblocking findings never trigger an automatic
  rerun. Any review beyond this budget requires explicit owner authorization.
- A material architecture change is narrowly limited to a change in canonical
  state ownership, persistence, public/versioned contract semantics,
  Core/Go/UI ownership, execution or resolver/source-selection authority,
  secret/security boundary, transaction/rollback model, daemon/lifecycle
  subsystem, or owner-approved architectural scope. Tests, names, error text,
  missing bounds/cleanup, negative tests, finding corrections that preserve the
  approved architecture, documentation synchronization and behavior-preserving
  local refactors do not automatically invalidate the whole review. If
  uncertain, report that uncertainty to the owner instead of starting another
  full review.
- Mandatory overengineering review remains. It is blocking only with evidence
  of a concrete unnecessary mechanism, a viable simpler existing/standard
  alternative satisfying the current requirement, and material maintenance,
  contract or safety cost. A merely aesthetic preference is nonblocking.
  Architecture review never replaces owner authorization or applicable
  Core-contract, safety and QA gates. Supply a facts-only envelope with mode,
  FULL/TARGETED_RECHECK context, exact revision identity, scope/non-goals,
  owner decisions, contracts and available evidence; never supply an expected
  verdict or self-review conclusion. If the custom role cannot be loaded, give
  the same full instructions to an independent read-only subagent and disclose
  the fallback. Self-review never counts. If no independent reviewer is
  available, report the review as unavailable/pending.
