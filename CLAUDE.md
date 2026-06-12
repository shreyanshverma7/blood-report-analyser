# Project Rules

## Every session

Read `PLAN.md` at the start. If it exists, pick up from the first unchecked task. Don't re-plan work that's already planned.

## Before writing any code

A task covering that work must exist in `PLAN.md`. For anything touching more than one file or with real architectural consequence, write the plan first — use `/plan` to think it through read-only, then write the result to `PLAN.md` before building.

## PLAN.md structure

```
## Plan: [feature name]
_[YYYY-MM-DD] — from BRAINSTORM.md idea N_

### Scope
[What's in. What's explicitly out.]

### First step
[The one unambiguous action to start.]

### Phase 1 — [milestone]  ·  Delivers: [verifiable outcome]
- [ ] T1.1 — [specific action]
- [ ] T1.2 — [specific action, depends on T1.1]
  - ❓ [any open question that blocks this task — resolve before starting]

### Phase 2 — [milestone]  ·  Delivers: [...]
- [ ] T2.1 — [...]
```

## Completing tasks

Mark done with `[x]` and today's date: `- [x] T1.1 _(done: YYYY-MM-DD)_`

## File ownership

- `BRAINSTORM.md` — ideas, options, accept/reject
- `PLAN.md` — plan, tasks, open questions, progress

## When to skip brainstorming

Small, well-understood tasks go straight to `PLAN.md`. Brainstorming is for decisions with real architectural consequence — multiple viable approaches, non-trivial tradeoffs. Don't add ceremony to a two-task feature.
