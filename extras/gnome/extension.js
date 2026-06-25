import GObject from 'gi://GObject';
import St from 'gi://St';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';

const POLL_SECONDS = 15;
const HOME = GLib.get_home_dir();
const CACHE_PATH    = `${HOME}/.cache/claude-usage.json`;
const OVERRIDE_PATH = `${HOME}/.claude/usage-override`;
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

function readUsagePct() {
    try {
        const raw = readFile(CACHE_PATH);
        if (!raw) return 0;
        const json = JSON.parse(raw);
        const sess = (json.data ?? {}).five_hour ?? (json.data ?? {}).session ?? {};
        for (const k of ['utilization', 'utilization_pct', 'percent_used']) {
            if (sess[k] !== undefined) return parseFloat(sess[k]);
        }
    } catch (_) {}
    return 0;
}

const ClaudeOverride = GObject.registerClass(
class ClaudeOverride extends PanelMenu.Button {
    _init(extensionPath) {
        super._init(0.0, 'Claude Override');

        this._icon = new St.Icon({
            gicon: Gio.icon_new_for_string(`${extensionPath}/icon2.svg`),
            icon_size: 16,
        });
        this.add_child(this._icon);
        this.hide();

        this.connect('button-press-event', () => this._activate());
        this._pollId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, POLL_SECONDS, () => {
            this._update();
            return GLib.SOURCE_CONTINUE;
        });
        this._update();
    }

    _update() {
        const pct = readUsagePct();
        const threshold = readThreshold();
        if (pct >= threshold) this.show();
        else this.hide();
    }

    _activate() {
        try {
            Gio.Subprocess.new(
                ['bash', '-c', `date +%s > ${OVERRIDE_PATH} && notify-send "Claude Override" "Limit removed until window resets"`],
                Gio.SubprocessFlags.NONE
            );
            this.hide();
        } catch (_) {}
    }

    destroy() {
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
