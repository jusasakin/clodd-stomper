#!/usr/bin/env python3
"""
claude-usage-hook — Claude Code PreToolUse hook.

Reads your Claude Code usage and injects graded awareness messages before
each tool call:

  >= 80%   informational nudge (does not block)
  >= 90%   "finish current task, then wrap up" (does not block)
  >= 95%   BLOCKS the tool call and tells Claude to run your session-close
           procedure (whatever you define in CLAUDE.md)

Manual override:
  Writing the current unix time into ~/.claude/usage-override makes the hook
  stop blocking until the current 5h window resets. While the override is
  active above the block threshold, it prints a commit reminder instead of
  blocking, so you can spend a window down deliberately without silently
  accumulating uncommitted work. The override evaporates on its own when the
  window rolls over — there is nothing to switch back off.

Bind a button/shortcut to:
  date +%s > ~/.claude/usage-override

NOTE: reads an UNDOCUMENTED Anthropic endpoint; may break without notice.
The hook NEVER blocks on error — if anything goes wrong it exits 0 silently,
so a broken endpoint can never lock you out of your own tools.
"""
import json
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ── config ──────────────────────────────────────────────────────────────────
CREDS    = Path.home() / ".claude" / ".credentials.json"
URL      = "https://api.anthropic.com/api/oauth/usage"
CACHE    = Path.home() / ".cache" / "claude-usage.json"
OVERRIDE = Path.home() / ".claude" / "usage-override"
TTL      = 120          # seconds — normal cache
BLOCK_AT = 95           # block + trigger session close at/above this %
WARN_AT  = 90           # strong warning at/above this %
INFO_AT  = 80           # informational nudge at/above this %
WINDOW_SECONDS = 5 * 3600  # length of the rolling window the % refers to

# ── helpers ─────────────────────────────────────────────────────────────────

def get_token():
    d = json.loads(CREDS.read_text())
    return d["claudeAiOauth"]["accessToken"]


def fetch():
    token = get_token()
    req = urllib.request.Request(
        URL,
        headers={
            "Authorization":  f"Bearer {token}",
            "anthropic-beta": "oauth-2025-04-20",
            "User-Agent":     "claude-code/1.0.0",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def cached_fetch(force=False):
    if not force and CACHE.exists():
        try:
            c = json.loads(CACHE.read_text())
            if time.time() - c.get("_ts", 0) < TTL:
                return c["data"]
        except Exception:
            pass
    data = fetch()
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps({"_ts": time.time(), "data": data}))
    return data


def pct(window):
    for k in ("utilization", "utilization_pct", "percent_used"):
        v = window.get(k)
        if v is not None:
            return float(v)
    return 0.0


def reset_epoch(ts):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def time_left(ts):
    try:
        reset = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        s = int((reset - datetime.now(timezone.utc)).total_seconds())
        if s <= 0:
            return "resetting soon"
        h, rem = divmod(s, 3600)
        m = rem // 60
        if h >= 24:
            d, h = divmod(h, 24)
            return f"{d}d"
        return f"{h}h{m:02d}m" if h else f"{m}m"
    except Exception:
        return "?"


def override_active(window_reset):
    """
    True if the override was clicked within the CURRENT window. The override
    file holds the unix time it was written; it only counts if that time falls
    inside the window ending at window_reset, so it clears itself on rollover.
    """
    if not OVERRIDE.exists():
        return False
    try:
        clicked = int(OVERRIDE.read_text().strip())
    except Exception:
        return False
    now = time.time()
    # Safety: ignore a stamp from the future or absurdly old
    if clicked > now + 60 or (now - clicked) > (WINDOW_SECONDS + 3600):
        return False
    if window_reset:
        window_start = window_reset - WINDOW_SECONDS
        return clicked >= window_start
    # No reset info — honour a click made within one window length
    return (now - clicked) < WINDOW_SECONDS

# ── main ─────────────────────────────────────────────────────────────────────

def main():
    # Drain stdin — Claude Code pipes tool-call JSON in
    try:
        if not sys.stdin.isatty():
            sys.stdin.read()
    except Exception:
        pass

    try:
        data = cached_fetch(force=False)
        sess = data.get("five_hour") or data.get("session") or {}
        p = pct(sess)
        if p >= WARN_AT:
            data = cached_fetch(force=True)  # fresh data before any strong action
            sess = data.get("five_hour") or data.get("session") or {}
            p = pct(sess)
    except Exception:
        sys.exit(0)  # never block on error

    reset = sess.get("resets_at") or sess.get("reset_at", "")
    tl = time_left(reset)
    ov = override_active(reset_epoch(reset))

    if p >= BLOCK_AT and not ov:
        print(
            f"⛔ USAGE AT {p:.0f}% — window resets in {tl}. "
            f"Do not proceed with any tool calls. "
            f"Run the session-close procedure now as defined in CLAUDE.md: "
            f"commit all work, update your handoff file, and output the close summary."
        )
        sys.exit(1)  # blocks the tool call

    elif p >= BLOCK_AT and ov:
        print(f"⚡ Override on — {p:.0f}% — commit now so nothing's lost")

    elif p >= WARN_AT and not ov:
        print(
            f"🔴 Usage at {p:.0f}% ({tl} remaining). "
            f"Finish the current task only, then run session close per CLAUDE.md. "
            f"Do not start anything new."
        )

    elif p >= WARN_AT and ov:
        print(f"⚡ Override on — {p:.0f}% — commit now so nothing's lost")

    elif p >= INFO_AT and not ov:
        print(f"🟠 [Usage {p:.0f}% — session close approaching, {tl} remaining]")

    sys.exit(0)


if __name__ == "__main__":
    main()
