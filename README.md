# clodd-stomper

A small safety layer for [Claude Code](https://docs.claude.com) that stops you
losing work when your usage window runs out mid-task.

It does three things:

1. **Shows your usage** in the Claude Code status line (and/or a desktop bar).
2. **Warns you as you approach the limit** — graded nudges at 80% and 90%.
3. **Blocks the next tool call at 95%** and tells Claude to run your
   session-close procedure, so work is committed and a handoff is written
   *before* the window dies — not lost in a half-finished conversation.

A one-click **override** lets you deliberately spend a window down to the
limit when you know that's what you want, without permanently disabling the
safety net — it clears itself when the window resets.

> ⚠️ **Unofficial endpoint.** This reads an undocumented Anthropic usage
> endpoint with an unofficial beta header. It works today; it may break
> without notice if Anthropic changes it. Don't build anything load-bearing
> on it. The hook is written to **fail open** — on any error it does nothing
> and never blocks you — so a broken endpoint can't lock you out of your own
> tools.

---

## Why

Claude Code usage runs in windows. Hit the limit mid-task and the conversation
— including everything not yet written to a file or committed — is gone. The
fix isn't more credit; it's *discipline*: commit constantly, keep a handoff
file, and stop cleanly before the window dies. This tool makes that discipline
automatic by surfacing usage where you're already looking and forcing a clean
stop at the threshold.

The block message points Claude at **your** session-close procedure. A minimal
generic one is included in [`examples/CLAUDE.minimal.md`](examples/CLAUDE.minimal.md)
— bring your own if you have a framework already.

---

## Install

Requires Python 3 and Claude Code. (The optional combiner wrapper also needs
whatever second status-line tool you point it at.)

```bash
# 1. Copy the scripts somewhere on your machine
mkdir -p ~/bin
cp bin/claude-usage ~/bin/
cp bin/claude-usage-hook.py ~/bin/
chmod +x ~/bin/claude-usage ~/bin/claude-usage-hook.py

# 2. Confirm it can read your usage
~/bin/claude-usage
# → ☁ 5h 42% (3h20m) · 7d 18% (5d)
```

If you instead see `☁ ? keys=...`, the endpoint returned a shape this script
doesn't recognise — open an issue with the listed keys.

### Wire it into Claude Code

Merge the keys from [`examples/settings.fragment.jsonc`](examples/settings.fragment.jsonc)
into your `~/.claude/settings.json`. Don't overwrite the whole file — add the
`statusLine` and `hooks` keys to what's already there. Restart Claude Code.

### Add the session-close procedure

Copy the relevant parts of [`examples/CLAUDE.minimal.md`](examples/CLAUDE.minimal.md)
into your project's `CLAUDE.md`, or merge with your existing one. Without a
close procedure, the block message has nothing to trigger.

---

## The override button

When you want to push past the 95% block deliberately, write the current time
into the override file:

```bash
date +%s > ~/.claude/usage-override
```

From then until the window resets, the hook stops blocking and prints a
`⚡ Override on — commit now so nothing's lost` reminder on each tool call
instead. It clears itself automatically on window rollover — nothing to switch
back off.

Bind that one-liner to whatever's convenient:

- **A keyboard shortcut** (GNOME: Settings → Keyboard → Custom Shortcuts).
- **A desktop-bar button** (e.g. the GNOME [Executor](https://github.com/raujonas/executor)
  extension — add a command entry that runs the line and `echo`s a `⚡` label).

---

## Combining with another status-line tool

Claude Code's `statusLine` takes one command, and the session JSON it pipes in
can only be read once. To show usage *alongside* another tool (e.g. a
context-size meter), use [`bin/claude-status`](bin/claude-status), which reads
stdin once and feeds the same copy to both. Edit `OTHER_TOOL` at the top to
point at your second tool, then point `statusLine` at `claude-status` instead.

---

## How it works

- `claude-usage` fetches usage (cached 120s) and prints a compact line.
- `claude-usage-hook.py` runs as a `PreToolUse` hook before every tool call.
  Below 80% it's silent; at 80/90% it nudges; at 95% it blocks (exit 1) and
  tells Claude to close out. It force-refreshes the usage figure before any
  block so it never acts on stale data, and it fails open on any error.
- The override is a timestamp tied to the current window, so it can't get
  stuck "on."

## Tuning

Thresholds live at the top of `claude-usage-hook.py` (`BLOCK_AT`, `WARN_AT`,
`INFO_AT`). Adjust to taste.

## License

MIT — see [LICENSE](LICENSE). Provided as-is, low support. PRs welcome,
especially fixes if the upstream endpoint shape changes.
