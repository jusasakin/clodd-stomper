# Minimal CLAUDE.md — session-close discipline

This is the smallest set of instructions that makes the usage hook useful.
The hook can *tell* Claude to "run the session-close procedure," but that only
works if a procedure exists. Copy the relevant parts into your project's
CLAUDE.md (or merge into your existing one).

The single principle behind all of it:

> Conversation history is ephemeral. Files and commits are permanent.
> When the usage window runs out, only what you committed survives.

---

## Commit constantly

After every change that completes something, commit it. Git is a local
operation — it costs no usage and has no downside. Do not accumulate
uncommitted work; if the window runs out mid-task, only committed work
carries into the next session.

Use a `wip:` prefix for in-progress commits if you like, so they're easy to
spot and squash later.

## Keep a handoff file

Maintain a `handoff.md` in the project root with three things, kept current:

- **Current state** — what's done, what's in progress
- **Next task** — the single next thing to do (be specific)
- **Open blockers** — anything broken or undecided, or "none"

This file is the baton. The next session reads it and resumes — it does not
need the conversation history.

## Session close (what the hook triggers at the block threshold)

When the hook blocks a tool call at the usage limit — or when you finish a
milestone, or you say you're done — run these steps:

1. Commit any uncommitted work on the current branch.
2. Update `handoff.md`: current state, next task, open blockers.
3. Output a short resume prompt the user can paste into the next session, e.g.:

   > Read handoff.md. Next task: [exact task]. [Any blocker in one line, or omit.]

That's it. Two minutes. It converts a messy mid-task cutoff into a clean,
one-line resume.

## If the window runs out before you could close cleanly

Credit running out does NOT mean the work is instantly gone — the conversation
is still on screen and git is still free to run locally. Before starting fresh:

1. Read back through the conversation for anything that exists ONLY there
   (a decision made, a bug spotted, the next intended step). Write those lines
   into `handoff.md` by hand.
2. Commit anything still uncommitted on disk (`wip:` is fine).
3. Then start a fresh session — it reads handoff.md and resumes clean.

Starting fresh with a clean handoff beats reopening a polluted, half-finished
conversation: the fresh session starts sharp and doesn't carry the weight of
an hour of stale context.
