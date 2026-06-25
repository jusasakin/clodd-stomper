#!/usr/bin/env python3
"""
claude-usage-hook — Claude Code PreToolUse hook.

Reads your Claude Code usage and injects graded awareness messages before
each tool call:

  >= 80%   informational nudge to the user's terminal (does not block)
  >= 90%   blocks ONCE per window so Claude actually sees the warning;
           subsequent calls at this level are silent (avoids blocking every
           tool call until the window resets)
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
WARNED   = Path.home() / ".cache" / "claude-usage-warned.json"
OVERRIDE = Path.home() / ".claude" / "usage-override"
TTL      = 30           # 30s here vs 120s in claude-usage: the gate should
                        # never act on data older than this
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
    if clicked > now + 60 or (now - clicked) > (WINDOW_SECONDS + 3600):
        return False
    if window_reset:
        window_start = window_reset - WINDOW_SECONDS
        return clicked >= window_start
    return (now - clicked) < WINDOW_SECONDS


def already_warned(threshold, window_reset):
    """
    True if we already fired an exit-1 warning at this threshold in the
    current window. Prevents every tool call at 90% from being blocked.
    """
    if not WARNED.exists():
        return False
    try:
        d = json.loads(WARNED.read_text())
        ts = d.get(str(threshold))
        if ts is None:
            return False
        if window_reset:
            window_start = window_reset - WINDOW_SECONDS
            return float(ts) >= window_start
        return (time.time() - float(ts)) < WINDOW_SECONDS
    except Exception:
        return False


def mark_warned(threshold):
    d = {}
    if WARNED.exists():
        try:
            d = json.loads(WARNED.read_text())
        except Exception:
            pass
    d[str(threshold)] = time.time()
    WARNED.parent.mkdir(parents=True, exist_ok=True)
    WARNED.write_text(json.dumps(d))

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
        if p >= INFO_AT:
            # Force-refresh at 80% so we never block or warn on stale data.
            # Previous threshold was WARN_AT (90%), which let cached values in
            # the 80-89% range through without a refresh — real usage could be
            # much higher and the block at 95% would never fire.
            data = cached_fetch(force=True)
            sess = data.get("five_hour") or data.get("session") or {}
            p = pct(sess)
    except Exception:
        sys.exit(0)  # never block on error

    reset = sess.get("resets_at") or sess.get("reset_at", "")
    tl    = time_left(reset)
    ov    = override_active(reset_epoch(reset))
    wr    = reset_epoch(reset)

    if p >= BLOCK_AT and not ov:
        print(
            f"⛔ USAGE AT {p:.0f}% — window resets in {tl}. "
            f"Do not proceed with any tool calls. "
            f"Run the session-close procedure now as defined in CLAUDE.md: "
            f"commit all work, update your handoff file, and output the close summary."
        )
        sys.exit(1)  # blocks the tool call

    elif p >= WARN_AT and ov:
        # Override covers both BLOCK_AT+ov and WARN_AT+ov
        print(f"⚡ Override on — {p:.0f}% — commit now so nothing's lost")

    elif p >= WARN_AT:
        # not ov implied — fire exit(1) once per window so Claude actually
        # sees this warning; after that, stay silent so tool calls aren't
        # blocked on every call until the window resets.
        if not already_warned(WARN_AT, wr):
            mark_warned(WARN_AT)
            print(
                f"🔴 Usage at {p:.0f}% ({tl} remaining). "
                f"Finish the current task only, then run session close per CLAUDE.md. "
                f"Do not start anything new. "
                f"Re-invoke the tool call you were about to make to continue your current task."
            )
            sys.exit(1)

    elif p >= INFO_AT and not ov:
        print(f"🟠 [Usage {p:.0f}% — session close approaching, {tl} remaining]")

    sys.exit(0)


if __name__ == "__main__":
    main()
