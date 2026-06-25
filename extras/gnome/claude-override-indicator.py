#!/usr/bin/env python3
"""
claude-override-indicator — system tray override button for clodd-stomper.

Sits invisible in the system tray. When your Claude Code usage hits the
block threshold, the icon appears. Click it → limit removed for this window.

Requires Ubuntu/GNOME with:
  sudo apt install gir1.2-ayatanaappindicator3-0.1

Run install.sh to set everything up automatically.
"""
import json
import subprocess
import time
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


def read_threshold():
    try:
        return int(THRESHOLD_CFG.read_text().strip())
    except Exception:
        return 95


def read_pct():
    try:
        d = json.loads(CACHE.read_text())
        sess = (d.get('data') or {}).get('five_hour') or \
               (d.get('data') or {}).get('session') or {}
        for k in ('utilization', 'utilization_pct', 'percent_used'):
            if sess.get(k) is not None:
                return float(sess[k])
    except Exception:
        pass
    return 0.0


def on_override(_, indicator):
    try:
        OVERRIDE.parent.mkdir(parents=True, exist_ok=True)
        OVERRIDE.write_text(str(int(time.time())))
        subprocess.Popen(['notify-send', 'Claude Override',
                          'Limit removed until window resets'])
        indicator.set_status(AppIndicator.IndicatorStatus.PASSIVE)
    except Exception:
        pass


def poll(indicator):
    if read_pct() >= read_threshold():
        indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
    else:
        indicator.set_status(AppIndicator.IndicatorStatus.PASSIVE)
    return GLib.SOURCE_CONTINUE


def main():
    indicator = AppIndicator.Indicator.new_with_path(
        'claude-override',
        'claude-override',
        AppIndicator.IndicatorCategory.APPLICATION_STATUS,
        str(ICON_DIR),
    )
    indicator.set_status(AppIndicator.IndicatorStatus.PASSIVE)

    menu = Gtk.Menu()
    item = Gtk.MenuItem(label='⚡  Push on — remove limit')
    item.connect('activate', on_override, indicator)
    menu.append(item)
    menu.show_all()
    indicator.set_menu(menu)

    GLib.timeout_add_seconds(POLL_SECONDS, poll, indicator)
    poll(indicator)
    Gtk.main()


if __name__ == '__main__':
    main()
