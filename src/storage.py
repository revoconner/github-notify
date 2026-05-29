import json
import os
from pathlib import Path

APP_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "github-tray"
SETTINGS_FILE = APP_DIR / "settings.json"
SEEN_FILE = APP_DIR / "seen.json"
ACTIVITY_FILE = APP_DIR / "activity.json"
SEEN_UPDATED_FILE = APP_DIR / "seen_updated_at.json"

DEFAULT_SETTINGS = {
    "issue_state": "open",
    "pr_state": "open",
    "show_bots": False,
    "bot_allowlist": ["claude[bot]"],
    "notify_scope": "owned",
    "poll_minutes": 5,
    "flag_first_sight": False,
    "last_poll_iso": None,
}


def ensure_dir():
    APP_DIR.mkdir(parents=True, exist_ok=True)


def _migrate(settings):
    # Carry forward state_filter -> issue_state/pr_state if upgrading from older builds.
    if "state_filter" in settings and "issue_state" not in settings:
        old = settings.pop("state_filter")
        if old in ("open", "both"):
            settings["issue_state"] = "open"
            settings["pr_state"] = "open"
        elif old == "draft":
            settings["issue_state"] = "open"
            settings["pr_state"] = "draft"
    settings.pop("reasons", None)
    # The PR "merged" filter was replaced by "closed" (merged is a subset of closed).
    if settings.get("pr_state") == "merged":
        settings["pr_state"] = "closed"
    return settings


def load_settings():
    ensure_dir()
    if not SETTINGS_FILE.exists():
        return dict(DEFAULT_SETTINGS)
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_SETTINGS)
    merged = dict(DEFAULT_SETTINGS)
    merged.update(data)
    return _migrate(merged)


def save_settings(settings):
    ensure_dir()
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def load_seen():
    ensure_dir()
    if not SEEN_FILE.exists():
        return set()
    try:
        return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))
    except Exception:
        return set()


def save_seen(seen):
    ensure_dir()
    seen_list = list(seen)[-10000:]
    SEEN_FILE.write_text(json.dumps(seen_list), encoding="utf-8")


def load_activity():
    ensure_dir()
    if not ACTIVITY_FILE.exists():
        return {}
    try:
        return json.loads(ACTIVITY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_activity(activity):
    ensure_dir()
    ACTIVITY_FILE.write_text(json.dumps(activity, indent=2), encoding="utf-8")


def load_seen_updated_at():
    ensure_dir()
    if not SEEN_UPDATED_FILE.exists():
        return {}
    try:
        return json.loads(SEEN_UPDATED_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_seen_updated_at(seen_updated_at):
    ensure_dir()
    SEEN_UPDATED_FILE.write_text(json.dumps(seen_updated_at), encoding="utf-8")
