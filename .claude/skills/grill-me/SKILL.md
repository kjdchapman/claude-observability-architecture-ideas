---
name: grill-me
description: >-
  Systematically interrogate the user's mental model of a proposed codebase
  change using a design tree. Use BEFORE planning sessions to extract the
  user's complete understanding — including assumptions they haven't
  articulated. Triggers on "/grill-me", "grill me", or when the user wants
  to be questioned about a change before planning it. Also use when the user
  says things like "I want to make sure we're aligned before planning",
  "let me walk you through what I'm thinking", or "question me about this
  change".
---

# Grill Me

Extract the user's complete mental model of a proposed change through structured, probing interrogation. The goal is to surface every assumption, constraint, and expectation *before* planning begins — so the plan doesn't miss what the user actually had in mind.

## Why this matters

When a user describes a change, they hold a rich internal model: trade-offs they've already weighed, edge cases they're worried about, constraints they consider obvious, interactions they've thought through. Most of this never makes it into the initial description. If planning starts from that thin description, the resulting plan will miss expectations — and the user won't notice until implementation is underway.

This skill exists to close that gap. By the time planning begins, the agent should hold a model of the change that's as complete as the user's own.

## The Design Tree

The interrogation is structured as a tree:

```
Root: The user's high-level description of the change
├── Branch A: [dimension discovered through questioning]
│   ├── A.1: [sub-concern]
│   └── A.2: [sub-concern]
├── Branch B: [another dimension]
│   └── B.1: [sub-concern]
│       └── B.1.1: [deeper detail]
└── Branch C: [another dimension]
```

Each node represents a discrete aspect of the change. Branches open when an answer reveals new dimensions worth exploring. The tree grows until it captures the user's full mental model.

### How it works

1. **Seed the root.** The user describes the change. Record this as the root node, then gather prior context before questioning begins (see *Investigate before asking* and *Prior recorded knowledge* below).
2. **Identify initial branches.** From the root description, identify 3-5 top-level dimensions that need exploration. These might include: scope, motivation, constraints, interactions with existing code, expected behaviour, error handling, migration concerns, performance expectations, user-facing impact — whatever is relevant to *this specific change*.
3. **Explore one branch at a time.** Pick the most foundational unexplored branch — the one that other branches are likely to depend on. Ask a focused, probing question about it.
4. **Record and branch.** When the user answers:
   - Record the understanding at that node
   - Identify any new branches their answer opened (new concerns, unstated assumptions, contradictions, areas they glossed over)
   - Add those as new nodes on the tree
5. **Repeat** until all branches are developed or the user moves to planning.

### Persisting the tree

The design tree is persisted as a JSON file inside `.grill-me/`, created at the start of the session and updated after every exchange. This serves three purposes: it survives context compression in long conversations, it gives the user a machine-readable artifact, and it forces the agent to be explicit about tree state rather than holding it loosely in conversation.

**File naming.** Each session gets a unique filename derived from the change title: slugify the title (lowercase, spaces to hyphens, strip non-alphanumeric characters, truncate to 60 chars) and append a short timestamp — e.g. `.grill-me/add-caching-layer-20260318T1400.json`. The corresponding summary uses the same slug: `.grill-me/add-caching-layer-20260318T1400-summary.md`. This prevents clashes between sessions while keeping filenames human-readable.

**Initialise** when the user describes the change. Create the `.grill-me/` directory in the project root if it doesn't already exist. Before writing any files, ask the user whether `.grill-me/` should be added to `.gitignore` — the tree may contain thinking the user doesn't want committed, or it may be a useful artifact they want to keep. Don't assume either way.

```json
{
  "title": "Short title for the change",
  "created": "2026-03-17T10:00:00Z",
  "root": {
    "description": "The user's initial description of the change"
  },
  "nodes": [
    {
      "id": "scope",
      "label": "Scope",
      "parent": null,
      "status": "unexplored",
      "understanding": null,
      "decisions": [],
      "constraints": [],
      "opened_by": "root"
    }
  ],
  "assumptions": [],
  "deferred": []
}
```

**Node statuses:** `"unexplored"` | `"exploring"` | `"explored"`

**After each exchange:**
1. Update the current node: set `status` to `"explored"`, fill in `understanding`, `decisions`, `constraints`
2. Add any new nodes the answer opened (with `opened_by` pointing to the parent node id)
3. Add any surfaced assumptions to the `assumptions` array
4. Write the updated JSON to disk
5. Display the tree in the conversation using this format:

```
## Design Tree

✅ Root: Add caching layer to API responses
├── ✅ Scope: Only GET endpoints on /api/v2/*
│   ├── ✅ Exclusions: /api/v2/user/session is excluded (real-time)
│   └── ✅ Future: v3 endpoints will opt-in later
├── 🔍 Invalidation strategy  ← currently exploring
│   └── ⬚ TTL vs event-driven (opened from parent)
├── ⬚ Performance targets
└── ⬚ Failure modes

Legend: ✅ explored | 🔍 current | ⬚ unexplored
```

The visual tree in conversation is the user's live map — they can see gaps and redirect. The JSON file is the durable record.

## Questioning approach

The point is to *grill* — not to interview politely. The user chose this skill because they want their thinking stress-tested.

### What good questions do

- **Expose implicit assumptions.** "You said 'we'd just update the schema' — what happens to rows written under the old schema?"
- **Find missing dimensions.** "You've described the happy path. What should happen when the upstream service is unavailable?"
- **Challenge stated constraints.** "You said this has to be backwards-compatible. Is that a hard requirement from another team, or a preference?"
- **Force specificity.** "You said 'handle errors gracefully.' What does the user actually see? What gets logged?"
- **Probe interactions.** "This touches the payment flow. How does it interact with the retry logic that's already there?"

### What bad questions look like

- Restating what the user just said as a question
- Asking about things that are obvious from the description
- Generic checklist questions that aren't tailored to the specific change ("Have you considered testing?")
- Multiple questions packed into one (pick the most important one)

### Investigate before asking

Before asking a question, consider whether the codebase itself can answer it. If a question is about existing behaviour, current structure, call paths, schema shapes, or what code already does — read the code first. Use that understanding to ask a *better* question: one that targets the delta between what exists and what the user intends, rather than asking the user to describe things the code already shows.

Examples:
- **Instead of** "How does the current auth middleware work?" → read the middleware, **then ask** "The current middleware stores session tokens in a cookie with no expiry. Is your change replacing that mechanism, or wrapping it?"
- **Instead of** "What endpoints exist under /api/v2?" → check the routes, **then ask** "I see 14 GET endpoints under /api/v2, including /user/session which hits the DB on every call. Should all of them be cached, or are there exclusions?"

This makes questions sharper and avoids wasting the user's time describing things that are already in the code. However, the goal is still to extract the *user's* mental model — not to substitute your reading of the code for their intent. Use codebase investigation to *inform* questions, not to skip them. If you discover something that contradicts what the user said, surface it: "You mentioned X, but the code shows Y — which is the intended state?"

### Prior recorded knowledge

The codebase shows what the system *does*; it rarely shows *why*. If the project keeps a knowledge vault — an Open Knowledge Format (OKF) vault or equivalent — consult it before the first question. Recorded decisions, rejected alternatives, and externally-imposed constraints are exactly the material that sharpens a question:

> "The vault records that you chose TTL invalidation in March, and rejected event-driven because the event bus gave no ordering guarantee. Is this change building on that decision, or revisiting it?"

**Finding the vault.** If the `open-knowledge-format` skill is available, defer to it for anything format-specific. Failing that, the usual signals are a vault path in project configuration (the OKF plugin currently records one in `.claude/okf-memory.json`) or a directory whose `index.md` reads as a knowledge index. Treat both as hints, not contracts — if neither resolves and there's reason to think a vault exists, ask rather than guess. If OKF memory hooks are installed the root index is already injected at session start, so don't re-read it; follow its links to the notes relevant to *this* change rather than loading the whole vault.

**Treat a recorded note as a claim, not a fact.** It may be stale, or may record a position the user has since abandoned. It gives you a question, not an answer: "The vault has X down as a hard constraint — does that still hold?" Never let a note stand in for the user's intent, and surface any contradiction between the vault and what they tell you, exactly as you would for the code.

If there's no vault, skip this — nothing else changes.

### Pacing

Ask **one question at a time.** Wait for the answer. Each answer informs the next question — don't pre-plan a fixed sequence.

If the user gives a short or vague answer, push deeper on the same point before moving on. "Can you say more about that?" is fine. Moving on from a vague answer signals that vague is acceptable.

## Completion

### When to stop

Stop exploring when **all branches are marked ✅** — every dimension has been explored to the point where the user's position is clear and specific.

Before declaring completion, always ask:

> "I believe we've explored all the branches I can see. Are there areas we haven't covered, or dimensions you expected me to ask about?"

If the user raises anything, continue. If they confirm completion, produce the summary.

### Early exit

If the user says "let's move to planning" or similar before all branches are explored, flag the unexplored branches:

> "We have unexplored branches: [list]. These gaps may surface as misaligned expectations during planning. Want to cover them quickly, or proceed knowing they're open?"

Respect their decision either way, but make the trade-off visible.

### Output

When complete, produce two artifacts — plus a third if the project has a knowledge vault:

**1. Update the JSON file.** Set all remaining node statuses to their final state. Add a `"completed"` timestamp and a `"summary"` field at the top level. The JSON is the machine-readable handoff — a planning agent or skill can read it directly.

**2. Write a markdown summary** to the session's summary file (same slug as the JSON, with `-summary.md` suffix):

```markdown
# Design Tree Summary: [Change Title]

## Root
[One-paragraph summary of the change and its motivation]

## Explored Branches

### [Branch name]
**Understanding:** [What was established]
**Key decisions:** [Choices the user has already made]
**Constraints:** [Hard requirements surfaced]
**Open questions:** [Anything that was flagged but deferred]

### [Next branch...]
...

## Assumptions Register
[List of assumptions that were surfaced and confirmed during questioning.
These are things the user considers settled but that weren't in the original description.]

## Deferred / Out of Scope
[Anything explicitly marked as not part of this change]
```

The markdown summary is the human-readable handoff. A planning agent should be able to read either artifact and understand the user's full mental model of the change without needing to re-ask any of these questions.

**3. Optionally, emit the durable conclusions to the project's knowledge vault.**

The settled output of a grill — decisions with their rationale, hard constraints — is exactly what a knowledge vault exists to hold, and next session's grill will read it back (see *Prior recorded knowledge*).

**This mode requires the `open-knowledge-format` skill.** It is a precondition, not an enhancement. Without it, produce artifacts 1 and 2 only and stop there — don't improvise a vault format from memory, and don't write unstructured files into someone's vault. Artifact 2 is already plain, portable markdown and stands on its own as the handoff.

When the mode is active, grill-me decides *what* goes in; the skill decides *how* it is written.

**What to emit — grill-me's call:**

- Only what is **settled**: confirmed decisions with their rationale, hard constraints, confirmed assumptions.
- Never the tree structure, node statuses, open questions, or anything in `deferred`. That is session scaffolding and stays in `.grill-me/`.
- **The durable unit is the decision** — not the grill session, and not the tree node. A session that settled four decisions yields four notes. How each note is then named, placed, and structured is the skill's business, not this one's.
- **Ask before writing.** The user may not want a design session recorded in the vault.

**How to write it — the skill's call.** Invoke `open-knowledge-format` and follow it for everything format-specific: which frontmatter fields exist and which are required, what makes a good description, file paths and placement, linking and navigation, how changes are logged, and validation. Don't restate those rules here or work from a remembered version of them — the skill tracks the spec, and the spec churns.

The `.grill-me/` files remain the record of *this session*; the vault notes are the long-lived record of what was decided. Where both cover the same ground, the vault notes are the source of truth.

Finally, tell the user where every file is — the JSON, the summary, and any vault notes written — and suggest they feed the summary into their planning session.
