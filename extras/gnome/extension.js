import GObject from 'gi://GObject';
import St from 'gi://St';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Clutter from 'gi://Clutter';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';

const POLL_SECONDS   = 15;
const FLASH_MS       = 500;
const HOME           = GLib.get_home_dir();
const CACHE_PATH     = `${HOME}/.cache/claude-usage.json`;
const OVERRIDE_PATH  = `${HOME}/.claude/usage-override`;
const THRESHOLD_PATH = `${HOME}/.claude/usage-guard-threshold`;

function readFile(path) {
    try {
        const [, b] = Gio.File.new_for_path(path).load_contents(null);
        return new TextDecoder().decode(b);
    } catch (_) { return null; }
}

function readThreshold() {
    const v = parseInt(readFile(THRESHOLD_PATH));
    return isNaN(v) ? 95 : v;
}

function overrideIsActive() {
    const raw = readFile(OVERRIDE_PATH);
    if (!raw) return false;
    const clicked = parseInt(raw.trim());
    if (isNaN(clicked)) return false;
    const elapsed = Math.floor(Date.now() / 1000) - clicked;
    return elapsed >= 0 && elapsed < 5 * 3600;
}

function readUsage() {
    try {
        const raw = readFile(CACHE_PATH);
        if (!raw) return { pct: 0, label: '?' };
        const data = JSON.parse(raw).data ?? {};
        const sess = data.five_hour ?? data.session ?? {};
        let pct = 0;
        for (const k of ['utilization', 'utilization_pct', 'percent_used']) {
            if (sess[k] !== undefined) { pct = parseFloat(sess[k]); break; }
        }
        return { pct, label: `${Math.round(pct)}%` };
    } catch (_) {}
    return { pct: 0, label: '?' };
}

const ClaudeOverride = GObject.registerClass(
class ClaudeOverride extends PanelMenu.Button {
    _init(extensionPath) {
        super._init(0.0, 'Claude Override');
        this._extensionPath = extensionPath;
        this._flashId  = null;
        this._flashOn  = false;

        const box = new St.BoxLayout({ vertical: false });
        this.add_child(box);

        this._icon = new St.Icon({
            gicon: Gio.icon_new_for_string(`${extensionPath}/icon-green.svg`),
            icon_size: 16,
        });
        box.add_child(this._icon);

        this._label = new St.Label({
            text: '…',
            y_align: Clutter.ActorAlign.CENTER,
            style: 'padding-left: 4px;',
        });
        box.add_child(this._label);

        this.connect('button-press-event', () => this._activate());
        this._pollId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, POLL_SECONDS, () => {
            this._update();
            return GLib.SOURCE_CONTINUE;
        });
        this._update();
    }

    _setIcon(file) {
        this._icon.set_gicon(
            Gio.icon_new_for_string(`${this._extensionPath}/${file}`)
        );
    }

    _startFlash() {
        if (this._flashId) return;
        this._flashOn = true;
        this._setIcon('icon-red.svg');
        this._flashId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, FLASH_MS, () => {
            this._flashOn = !this._flashOn;
            this._setIcon(this._flashOn ? 'icon-red.svg' : 'icon-red-dim.svg');
            return GLib.SOURCE_CONTINUE;
        });
    }

    _stopFlash() {
        if (this._flashId) {
            GLib.source_remove(this._flashId);
            this._flashId = null;
        }
    }

    _update() {
        const { pct, label } = readUsage();
        const threshold = readThreshold();
        const active = overrideIsActive();

        // Label
        let text;
        if (active)                text = `⚡ ${label}`;
        else if (pct >= threshold) text = `⛔ ${label}`;
        else if (pct >= 90)        text = `🔴 ${label}`;
        else if (pct >= 80)        text = `🟠 ${label}`;
        else                       text = `☁ ${label}`;
        this._label.set_text(text);

        // Icon — flash red above 90%, calm down on override
        if (pct >= 90 && !active) {
            this._startFlash();
        } else {
            this._stopFlash();
            if (pct >= 80 || active) this._setIcon('icon-orange.svg');
            else                     this._setIcon('icon-green.svg');
        }
    }

    _activate() {
        const { pct } = readUsage();
        if (pct < readThreshold() || overrideIsActive()) return;
        try {
            Gio.Subprocess.new(
                ['bash', '-c', `date +%s > ${OVERRIDE_PATH} && notify-send "Claude Override" "Limit removed until window resets"`],
                Gio.SubprocessFlags.NONE
            );
            this._update();
        } catch (_) {}
    }

    destroy() {
        this._stopFlash();
        if (this._pollId) GLib.source_remove(this._pollId);
        this._pollId = null;
        super.destroy();
    }
});

let indicator = null;

export default class Extension {
    enable() {
        indicator = new ClaudeOverride(this.path);
        Main.panel.addToStatusArea('claude-override', indicator, 99, 'center');
    }
    disable() {
        indicator?.destroy();
        indicator = null;
    }
}
