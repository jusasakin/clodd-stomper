#!/usr/bin/env python3
"""
claude-override-indicator — usage display + override button for clodd-stomper.

Shows Claude Code usage in the system tray at all times. Icon colour reflects
usage level: green (normal), orange (approaching), red (at limit). When you
hit the block threshold the override option activates in the dropdown menu.

Requires: gir1.2-ayatanaappindicator3-0.1
  sudo apt install gir1.2-ayatanaappindicator3-0.1

Run install.sh to set everything up in one step.
"""
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import gi
gi.require_version('AyatanaAppIndicator3', '0.1')
gi.require_version('Gtk', '3.0')
from gi.repository import AyatanaAppIndicator3 as AppIndicator
from gi.repository import GLib, Gtk

HOME          = Path.home()
CACHE         = HOME / '.cache' / 'claude-usage.json'
OVERRIDE      = HOME / '.claude' / 'usage-override'
THRESHOLD_CFG = HOME / '.claude' / 'usage-guard-threshold'
ICON_DIR      = Path(__file__).resolve().parent
POLL_SECONDS  = 15

# Colour thresholds — match the hook's INFO_AT / WARN_AT
ORANGE_AT = 70   # approaching
RED_AT    = 90   # danger / block imminent


def read_threshold():
    try:
        return int(THRESHOLD_CFG.read_text().strip())
    except Exception:
        return 95


def icon_for(pct):
    if pct >= RED_AT:
        return 'claude-override-red'
    if pct >= ORANGE_AT:
        return 'claude-override-orange'
    return 'claude-override-green'


def time_left(ts):
    try:
        reset = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        s = int((reset - datetime.now(timezone.utc)).total_seconds())
        if s <= 0:
            return '↺'
        h, rem = divmod(s, 3600)
        m = rem // 60
        if h >= 24:
            return f'{h // 24}d'
        return f'{h}h{m:02d}m' if h else f'{m}m'
    except Exception:
        return '?'


def read_usage():
    """Returns (label_text, worst_pct)."""
    try:
        data = (json.loads(CACHE.read_text()).get('data') or {})
        parts = []
        worst = 0.0
        for keys, label in ((('five_hour', 'session'), '5h'),
                             (('seven_day', 'weekly'), '7d')):
            w = next((data[k] for k in keys if data.get(k)), {})
            if not w:
                continue
            pct = next((float(w[k]) for k in
                        ('utilization', 'utilization_pct', 'percent_used')
                        if w.get(k) is not None), 0.0)
            worst = max(worst, pct)
            reset = w.get('resets_at') or w.get('reset_at', '')
            parts.append(f'{label} {pct:.0f}% ({time_left(reset)})')
        if parts:
            return ' · '.join(parts), worst
    except Exception:
        pass
    return '?', 0.0


def override_is_active():
    if not OVERRIDE.exists():
        return False
    try:
        clicked = int(OVERRIDE.read_text().strip())
        now = time.time()
        return 0 < now - clicked < 5 * 3600
    except Exception:
        return False


def on_override(_, indicator, item):
    try:
        OVERRIDE.parent.mkdir(parents=True, exist_ok=True)
        OVERRIDE.write_text(str(int(time.time())))
        subprocess.Popen(['notify-send', 'Claude Override',
                          'Limit removed until window resets'])
    except Exception:
        pass


def poll(indicator, override_item):
    text, pct = read_usage()
    threshold = read_threshold()

    indicator.set_label(text, text)
    indicator.set_icon_full(icon_for(pct), 'Claude Code usage')

    if override_is_active():
        override_item.set_sensitive(False)
        override_item.set_label('✓  Override active')
    elif pct >= threshold:
        override_item.set_sensitive(True)
        override_item.set_label('⚡  Push on — remove limit')
    else:
        override_item.set_sensitive(False)
        override_item.set_label('⚡  Push on — remove limit')

    return GLib.SOURCE_CONTINUE


def main():
    indicator = AppIndicator.Indicator.new_with_path(
        'claude-override',
        'claude-override-green',
        AppIndicator.IndicatorCategory.APPLICATION_STATUS,
        str(ICON_DIR),
    )
    indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)

    menu = Gtk.Menu()

    override_item = Gtk.MenuItem(label='⚡  Push on — remove limit')
    override_item.connect('activate', on_override, indicator, override_item)
    override_item.set_sensitive(False)
    menu.append(override_item)

    menu.append(Gtk.SeparatorMenuItem())

    quit_item = Gtk.MenuItem(label='Quit indicator')
    quit_item.connect('activate', lambda _: Gtk.main_quit())
    menu.append(quit_item)

    menu.show_all()
    indicator.set_menu(menu)

    GLib.timeout_add_seconds(POLL_SECONDS, poll, indicator, override_item)
    poll(indicator, override_item)

    Gtk.main()


if __name__ == '__main__':
    main()
