import sys
import logging

import keyring
from PySide6.QtCore import QObject, QTimer, QThread, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu

try:
    from win11toast import notify
except Exception as e:
    notify = None
    print(f"[debug] win11toast import failed: {e!r}", flush=True)

from .resources import svg_icon
from .storage import (
    load_settings, save_settings,
    load_seen, save_seen,
    load_activity, save_activity,
    load_seen_updated_at, save_seen_updated_at,
)
from .poller import PollWorker
from .filters import item_key
from .ui.theme import apply_dark_theme
from .ui.window import MainWindow

KEYRING_SERVICE = "github-tray"
KEYRING_USER = "pat"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger(__name__)


def load_token():
    try:
        return keyring.get_password(KEYRING_SERVICE, KEYRING_USER) or ""
    except Exception as e:
        log.warning("keyring load failed: %s", e)
        return ""


def save_token(token: str):
    keyring.set_password(KEYRING_SERVICE, KEYRING_USER, token)


class App(QObject):
    poll_requested = Signal(str, dict, list, dict)
    toast_clicked = Signal()

    def __init__(self, qapp: QApplication):
        super().__init__()
        self.qapp = qapp

        self.settings = load_settings()
        self.seen = load_seen()
        self.activity = load_activity()
        self.seen_updated_at = load_seen_updated_at()
        self.token = load_token()
        self._last_issues = []
        self._last_prs = []

        self.window = MainWindow(self.settings, self.token)
        self.window.settings_changed.connect(self._on_settings_changed)
        self.window.pat_changed.connect(self._on_pat_changed)
        self.window.activity_cleared.connect(self._on_activity_cleared)
        self.window.poll_now_requested.connect(self._poll_now)
        self.window.mark_requested.connect(self._on_mark_requested)
        self.toast_clicked.connect(self._show_window)
        self.window.set_data([], [], self.activity)

        self._poll_thread = QThread()
        self._worker = PollWorker()
        self._worker.moveToThread(self._poll_thread)
        self._worker.finished.connect(self._on_poll_done)
        self._worker.error.connect(self._on_poll_error)
        self.poll_requested.connect(self._worker.do_poll)
        self._poll_thread.start()

        self._icon_default = svg_icon("tray-no-notif.svg")
        self._icon_unread = svg_icon("tray-notif-dark.svg")
        self._unread = False
        self.tray = QSystemTrayIcon(self._icon_default, self)
        self.tray.setToolTip("GitHub Tray")
        self._menu = QMenu()
        self._open_action = QAction("Open", self._menu)
        self._open_action.triggered.connect(self._show_window)
        self._poll_action = QAction("Poll now", self._menu)
        self._poll_action.triggered.connect(self._poll_now)
        self._quit_action = QAction("Quit", self._menu)
        self._quit_action.triggered.connect(self._quit)
        self._menu.addAction(self._open_action)
        self._menu.addAction(self._poll_action)
        self._menu.addSeparator()
        self._menu.addAction(self._quit_action)
        self.tray.setContextMenu(self._menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()
        self._set_unread(bool(self.activity))

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll_now)
        self._restart_timer()

        self.qapp.aboutToQuit.connect(self._shutdown)

        if not self.token:
            self.window.show()
            self.window.show_status("Set a PAT in Settings to begin.")
        else:
            # Start minimised to the tray; opened via tray click or a toast.
            self._poll_now()

    def _restart_timer(self):
        minutes = max(1, int(self.settings.get("poll_minutes", 5)))
        self.timer.start(minutes * 60 * 1000)

    def _show_window(self):
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self._show_window()

    def _app_is_foreground(self) -> bool:
        return self.window.isActiveWindow()

    def _set_unread(self, value: bool):
        print(f"[debug] _set_unread({value}) current={self._unread}", flush=True)
        if value != self._unread:
            self._unread = value
            self.tray.setIcon(self._icon_unread if value else self._icon_default)
            print(f"[debug] tray icon swapped -> "
                  f"{'UNREAD (tray-notif-dark)' if value else 'default (tray-no-notif)'}", flush=True)

    def _notify_summary(self, activity_by_subject, issues, prs):
        if notify is None or not activity_by_subject:
            print(f"[debug] _notify_summary skipped: notify={'None' if notify is None else 'ok'} "
                  f"items={len(activity_by_subject)}", flush=True)
            return
        act_keys = set(activity_by_subject)
        items = len(act_keys)
        n_issue = len(act_keys & {item_key(it) for it in issues})
        n_pr = len(act_keys & {item_key(it) for it in prs})
        if n_pr and not n_issue:
            noun = "PR" if items == 1 else "PRs"
        elif n_issue and not n_pr:
            noun = "issue" if items == 1 else "issues"
        else:
            noun = "update" if items == 1 else "updates"
        repos = {key.split("#")[0] for key in act_keys}
        title = f"{items} new {noun}"
        body = next(iter(repos)) if len(repos) == 1 else f"{len(repos)} repos"
        try:
            # notify() is non-blocking; the click callback fires on win11toast's
            # thread, so hop back to the GUI thread via a queued signal.
            print(f"[debug] notify({title!r}, {body!r})", flush=True)
            notify(title, body, on_click=lambda *a: self.toast_clicked.emit())
            print("[debug] notify() returned without error", flush=True)
        except Exception as e:
            print(f"[debug] notify() raised: {e!r}", flush=True)
            log.warning("toast failed: %s", e)

    def _on_settings_changed(self, new_settings):
        new_settings["last_poll_iso"] = self.settings.get("last_poll_iso")
        self.settings = new_settings
        save_settings(self.settings)
        self._restart_timer()
        self.window.show_status("Settings saved.")
        self._poll_now()

    def _on_pat_changed(self, token: str):
        self.token = token
        save_token(token)
        self.window.show_status("PAT saved.")
        self._poll_now()

    def _on_activity_cleared(self, key: str):
        if key in self.activity:
            del self.activity[key]
            save_activity(self.activity)
            self._set_unread(bool(self.activity))
            self.window.set_data(self._last_issues, self._last_prs, self.activity)

    def _on_mark_requested(self, keys, unread):
        changed = False
        for key in keys:
            if unread:
                entry = self.activity.get(key)
                if not entry or int(entry.get("count", 0)) < 1:
                    self.activity[key] = {
                        "count": 1,
                        "last_updated": entry.get("last_updated") if entry else None,
                    }
                    changed = True
            elif key in self.activity:
                del self.activity[key]
                changed = True
        if changed:
            save_activity(self.activity)
            self._set_unread(bool(self.activity))
            self.window.set_data(self._last_issues, self._last_prs, self.activity)

    def _poll_now(self):
        if not self.token:
            self.window.show_status("No PAT set.")
            return
        self.window.show_status("Polling...")
        self.poll_requested.emit(
            self.token,
            dict(self.settings),
            list(self.seen),
            dict(self.seen_updated_at),
        )

    def _on_poll_done(self, result: dict):
        for key, events in result.get("activity_by_subject", {}).items():
            existing = self.activity.get(key, {"count": 0, "last_updated": None})
            existing["count"] = int(existing.get("count", 0)) + len(events)
            latest = max(
                (e.get("updated_at") for e in events if e.get("updated_at")),
                default=None,
            )
            if latest:
                existing["last_updated"] = latest
            self.activity[key] = existing
        save_activity(self.activity)

        self.seen = set(result.get("seen_ids", []))
        save_seen(self.seen)

        new_seen_updated_at = result.get("seen_updated_at")
        if new_seen_updated_at is not None:
            self.seen_updated_at = dict(new_seen_updated_at)
            save_seen_updated_at(self.seen_updated_at)

        self.settings["last_poll_iso"] = result.get("now_iso")
        save_settings(self.settings)

        self._last_issues = result.get("issues", [])
        self._last_prs = result.get("prs", [])
        self.window.set_data(self._last_issues, self._last_prs, self.activity)

        api_floor_sec = int(result.get("poll_interval", 60))
        if api_floor_sec * 1000 > self.timer.interval():
            self.timer.setInterval(api_floor_sec * 1000)

        new_count = sum(len(v) for v in result.get("activity_by_subject", {}).values())
        abs_keys = list(result.get("activity_by_subject", {}).keys())
        print(f"[debug] poll done: new_count={new_count} new_keys={abs_keys} "
              f"accumulated_items={len(self.activity)} | "
              f"visible={self.window.isVisible()} minimized={self.window.isMinimized()} "
              f"active={self.window.isActiveWindow()}", flush=True)
        # Toast only on fresh activity while not foreground; tray reflects any outstanding counter.
        if new_count and not self._app_is_foreground():
            self._notify_summary(result.get("activity_by_subject", {}),
                                 result.get("issues", []), result.get("prs", []))
        else:
            print(f"[debug] toast not fired (new_count={new_count}, "
                  f"foreground={self._app_is_foreground()})", flush=True)
        self._set_unread(bool(self.activity))
        msg = f"{len(self._last_issues)} issues | {len(self._last_prs)} PRs"
        if new_count:
            msg += f" | {new_count} new"
        notif_err = result.get("notifications_error")
        scope = result.get("notify_scope")
        if scope == "watched" and notif_err:
            msg += "  |  notifications unavailable (classic PAT with 'notifications' scope required)"
        self.window.show_status(msg)

    def _on_poll_error(self, err: str):
        log.error("poll error: %s", err)
        self.window.show_status(f"Poll error: {err}")

    def _quit(self):
        self.qapp.quit()

    def _shutdown(self):
        self.tray.hide()
        self._poll_thread.quit()
        if not self._poll_thread.wait(2000):
            log.warning("poll thread did not exit cleanly")


def main():
    if sys.platform == "win32":
        # Windows groups taskbar icons by AppUserModelID; without our own id the taskbar
        # shows Python's icon rather than the window icon. Must run before QApplication.
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("com.revoconner.github-tray")
        except Exception:
            pass
    qapp = QApplication(sys.argv)
    qapp.setQuitOnLastWindowClosed(False)
    apply_dark_theme(qapp)
    qapp.setWindowIcon(svg_icon("app-icon.svg", 256))
    _app = App(qapp)
    sys.exit(qapp.exec())


if __name__ == "__main__":
    main()
