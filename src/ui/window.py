import webbrowser

from PySide6.QtCore import Qt, Signal, QSize, QEvent
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QWidget, QMainWindow, QTabWidget, QScrollArea, QFrame,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QToolButton, QLineEdit,
    QComboBox, QCheckBox, QGroupBox, QFormLayout, QStatusBar, QMenu,
)

from ..resources import svg_icon


ISSUE_STATE_OPTIONS = [("open", "Open"), ("closed", "Closed"), ("all", "All")]
PR_STATE_OPTIONS = [
    ("open", "Open"),
    ("draft", "Draft"),
    ("open_draft", "Open/Draft"),
    ("closed", "Closed"),
    ("all", "All"),
]
SCOPE_OPTIONS = [
    ("owned", "All repos I own"),
    ("watched", "Watched repos only (uses /notifications)"),
]


def _state_tag(it) -> str:
    # /search/issues gives state + draft but NOT merged_at, so a merged PR can only
    # be reported as "closed" here without an extra per-PR call.
    if it.get("pull_request") is not None:
        if it.get("state") == "open":
            return "draft" if it.get("draft") else "open"
        return "closed"
    return it.get("state", "open")


def _apply_selected(widget, selected: bool):
    # Toggle a dynamic property the stylesheet keys off, then re-polish to repaint.
    widget.setProperty("selected", "true" if selected else "false")
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class ItemRow(QWidget):
    clicked = Signal(str, str, bool)
    right_clicked = Signal(str)

    def __init__(self, title: str, count: int, number: int, tag: str, html_url: str, key: str):
        super().__init__()
        self.html_url = html_url
        self.key = key
        self.setObjectName("itemRow")
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_Hover, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(34, 10, 14, 10)
        layout.setSpacing(8)

        self.count_label = QLabel(str(count) if count else "")
        self.count_label.setObjectName("rowcount")
        self.count_label.setFixedWidth(18)
        self.count_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("title")
        self.title_label.setWordWrap(True)
        self.title_label.setTextInteractionFlags(Qt.NoTextInteraction)
        self.title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        # Word-wrap keeps a content-driven minimum width; without this the row would
        # scroll horizontally instead of reflowing. See QScrollArea word-wrap notes.
        self.title_label.setMinimumWidth(1)

        self.tag_label = QLabel(tag)
        self.tag_label.setObjectName("muted")
        self.tag_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self.number_label = QLabel(f"#{number}")
        self.number_label.setObjectName("muted")
        self.number_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        layout.addWidget(self.count_label, 0, Qt.AlignTop)
        layout.addWidget(self.title_label, 1)
        layout.addWidget(self.tag_label, 0, Qt.AlignTop)
        layout.addWidget(self.number_label, 0, Qt.AlignTop)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            ctrl = bool(event.modifiers() & Qt.ControlModifier)
            self.clicked.emit(self.html_url, self.key, ctrl)
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        self.right_clicked.emit(self.key)
        event.accept()


class RepoHeader(QWidget):
    clicked = Signal(bool)
    right_clicked = Signal()

    def __init__(self, repo_full: str, count: int):
        super().__init__()
        self.setObjectName("repoHeader")
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_Hover, True)
        self._has_unread = False
        self._expanded = True
        h = QHBoxLayout(self)
        h.setContentsMargins(12, 9, 14, 9)
        h.setSpacing(8)

        self.arrow = QLabel()
        self.arrow.setObjectName("repoArrow")
        self.arrow.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.dot = QLabel("●")
        self.dot.setObjectName("repoDot")
        self.dot.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.dot.setVisible(False)
        self.name = QLabel(repo_full)
        self.name.setObjectName("repoName")
        self.name.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.count_label = QLabel(str(count))
        self.count_label.setObjectName("repoCount")
        self.count_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        h.addWidget(self.arrow)
        h.addWidget(self.dot)
        h.addWidget(self.name)
        h.addStretch(1)
        h.addWidget(self.count_label)

    def set_unread(self, has_unread: bool):
        self._has_unread = has_unread
        self._refresh_dot()

    def set_expanded(self, expanded: bool):
        self._expanded = expanded
        self.arrow.setText("▾" if expanded else "▸")
        self._refresh_dot()

    def _refresh_dot(self):
        # Dot only shows when the repo is collapsed and has unread children.
        self.dot.setVisible(self._has_unread and not self._expanded)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            ctrl = bool(event.modifiers() & Qt.ControlModifier)
            self.clicked.emit(ctrl)
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        self.right_clicked.emit()
        event.accept()


class ListTab(QWidget):
    activity_cleared = Signal(str)
    mark_requested = Signal(list, bool)

    def __init__(self):
        super().__init__()
        # repo_full -> expanded bool, preserved across polls within a session.
        self._expanded = {}
        self._selected = set()   # selected child item keys (not persisted)
        self._rows = {}          # key -> ItemRow, rebuilt each poll
        self._sections = {}      # repo_full -> {"header", "body", "keys"}
        self._activity = {}      # latest activity dict, for read/unread checks
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("repoScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.container = QWidget()
        self.container.setObjectName("repoContainer")
        self.container.setAttribute(Qt.WA_StyledBackground, True)
        self.vbox = QVBoxLayout(self.container)
        self.vbox.setContentsMargins(0, 0, 0, 0)
        self.vbox.setSpacing(0)
        self.vbox.addStretch(1)
        self.scroll.setWidget(self.container)

        self.empty_label = QLabel("Nothing here.")
        self.empty_label.setObjectName("muted")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.hide()

        layout.addWidget(self.scroll)
        layout.addWidget(self.empty_label)

    def _clear_sections(self):
        # Drop every section but keep the trailing stretch (last item).
        while self.vbox.count() > 1:
            item = self.vbox.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def set_items(self, items, activity_dict):
        self._clear_sections()
        self._rows = {}
        self._sections = {}
        self._activity = activity_dict

        groups = []
        index = {}
        for it in items:
            repo_full = it["repository_url"].replace("https://api.github.com/repos/", "")
            if repo_full not in index:
                index[repo_full] = len(groups)
                groups.append((repo_full, []))
            groups[index[repo_full]][1].append(it)

        if groups:
            self.empty_label.hide()
            self.scroll.show()
            for repo_full, repo_items in groups:
                section = self._build_section(repo_full, repo_items, activity_dict)
                self.vbox.insertWidget(self.vbox.count() - 1, section)
        else:
            self.scroll.hide()
            self.empty_label.show()

        # Selection survives a rebuild; drop keys that vanished and restore visuals.
        self._selected &= set(self._rows)
        self._refresh_selection_visuals()

    def _build_section(self, repo_full, repo_items, activity_dict):
        section = QWidget()
        section.setObjectName("repoSection")
        sv = QVBoxLayout(section)
        sv.setContentsMargins(0, 0, 0, 0)
        sv.setSpacing(0)

        header = RepoHeader(repo_full, len(repo_items))
        body = QWidget()
        body.setObjectName("repoBody")
        body.setAttribute(Qt.WA_StyledBackground, True)
        bv = QVBoxLayout(body)
        bv.setContentsMargins(0, 0, 0, 0)
        bv.setSpacing(0)
        keys = []
        for it in repo_items:
            row = self._build_row(it, activity_dict)
            bv.addWidget(row)
            self._rows[row.key] = row
            keys.append(row.key)
        self._sections[repo_full] = {"header": header, "body": body, "keys": keys}

        # Parent header/body into the section before touching visibility. Calling
        # setVisible(True) on a still-parentless body briefly pops it as its own
        # top-level window -- that was the flash on every rebuild (poll / activity clear).
        sv.addWidget(header)
        sv.addWidget(body)

        repo_has_unread = any(
            (activity_dict.get(f"{repo_full}#{it['number']}") or {}).get("count", 0) > 0
            for it in repo_items
        )
        header.set_unread(repo_has_unread)

        expanded = self._expanded.get(repo_full, True)
        header.set_expanded(expanded)
        body.setVisible(expanded)

        header.clicked.connect(lambda ctrl, rf=repo_full: self._on_header_clicked(rf, ctrl))
        header.right_clicked.connect(lambda rf=repo_full: self._on_header_right_clicked(rf))

        return section

    def _build_row(self, it, activity_dict):
        html_url = it.get("html_url", "")
        repo_full = it["repository_url"].replace("https://api.github.com/repos/", "")
        number = it["number"]
        title = it.get("title", "")
        key = f"{repo_full}#{number}"
        count = (activity_dict.get(key) or {}).get("count", 0)
        row = ItemRow(title, count, number, _state_tag(it), html_url, key)
        row.clicked.connect(self._on_row_clicked)
        row.right_clicked.connect(self._on_item_right_clicked)
        return row

    def _on_row_clicked(self, url, key, ctrl):
        if ctrl:
            self._toggle_item(key)
            return
        if self._selected:
            self.clear_selection()
            return
        if url:
            webbrowser.open(url)
        if key:
            self.activity_cleared.emit(key)

    def _on_header_clicked(self, repo_full, ctrl):
        sec = self._sections.get(repo_full)
        if not sec:
            return
        if ctrl:
            keys = set(sec["keys"])
            if keys and keys <= self._selected:
                self._selected -= keys
            else:
                self._selected |= keys
            self._refresh_selection_visuals()
            return
        if self._selected:
            self.clear_selection()
            return
        self._toggle_section(repo_full)

    def _toggle_section(self, repo_full):
        sec = self._sections.get(repo_full)
        if not sec:
            return
        new_state = not sec["body"].isVisible()
        sec["body"].setVisible(new_state)
        sec["header"].set_expanded(new_state)
        self._expanded[repo_full] = new_state

    def _toggle_item(self, key):
        if key in self._selected:
            self._selected.discard(key)
        else:
            self._selected.add(key)
        self._refresh_selection_visuals()

    def clear_selection(self):
        if not self._selected:
            return
        self._selected.clear()
        self._refresh_selection_visuals()

    def _refresh_selection_visuals(self):
        for key, row in self._rows.items():
            _apply_selected(row, key in self._selected)
        for sec in self._sections.values():
            keys = set(sec["keys"])
            _apply_selected(sec["header"], bool(keys) and keys <= self._selected)

    def _is_unread(self, key) -> bool:
        return (self._activity.get(key) or {}).get("count", 0) > 0

    def _on_item_right_clicked(self, key):
        self._show_context_menu({key})

    def _on_header_right_clicked(self, repo_full):
        sec = self._sections.get(repo_full)
        self._show_context_menu(set(sec["keys"]) if sec else set())

    def _menu_options(self, keys):
        # Applicable (label, icon, unread) options for the target: Mark Read when any
        # item is unread, Mark Unread when any is read; both when the target is mixed.
        opts = []
        if any(self._is_unread(k) for k in keys):
            opts.append(("Mark Read", "mark-read.svg", False))
        if any(not self._is_unread(k) for k in keys):
            opts.append(("Mark Unread", "mark-unread.svg", True))
        return opts

    def _show_context_menu(self, default_keys):
        # Right-click acts on the active selection if there is one, else the clicked target.
        keys = set(self._selected) if self._selected else set(default_keys)
        opts = self._menu_options(keys) if keys else []
        if not opts:
            return
        menu = QMenu(self)
        for label, icon, unread in opts:
            act = menu.addAction(svg_icon(icon, 32), label)
            act.triggered.connect(
                lambda checked=False, u=unread: self.mark_requested.emit(sorted(keys), u)
            )
        menu.exec(QCursor.pos())


class SettingsTab(QWidget):
    settings_changed = Signal(dict)
    pat_saved = Signal(str)

    def __init__(self, settings: dict, current_token: str):
        super().__init__()
        self.settings = dict(settings)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)

        filter_group = QGroupBox("Filters")
        form = QFormLayout(filter_group)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)

        self.issue_combo = QComboBox()
        for k, label in ISSUE_STATE_OPTIONS:
            self.issue_combo.addItem(label, k)
        self._select_combo(self.issue_combo, self.settings.get("issue_state", "open"))
        form.addRow("Issues:", self.issue_combo)

        self.pr_combo = QComboBox()
        for k, label in PR_STATE_OPTIONS:
            self.pr_combo.addItem(label, k)
        self._select_combo(self.pr_combo, self.settings.get("pr_state", "open"))
        form.addRow("PRs:", self.pr_combo)

        bots_widget = QWidget()
        bots_layout = QVBoxLayout(bots_widget)
        bots_layout.setContentsMargins(0, 0, 0, 0)
        bots_layout.setSpacing(4)
        self.show_bots_cb = QCheckBox("Show issues and PRs opened by bots")
        self.show_bots_cb.setChecked(bool(self.settings.get("show_bots", False)))
        bots_hint = QLabel("Logins listed below are always shown regardless of the toggle above.")
        bots_hint.setObjectName("muted")
        bots_hint.setWordWrap(True)
        self.bot_allowlist_input = QLineEdit(
            ", ".join(self.settings.get("bot_allowlist", ["claude[bot]"]))
        )
        self.bot_allowlist_input.setPlaceholderText("claude[bot], renovate[bot], dependabot[bot]")
        bots_layout.addWidget(self.show_bots_cb)
        bots_layout.addWidget(bots_hint)
        bots_layout.addWidget(self.bot_allowlist_input)
        form.addRow("Bots:", bots_widget)

        self.scope_combo = QComboBox()
        for k, label in SCOPE_OPTIONS:
            self.scope_combo.addItem(label, k)
        self._select_combo(self.scope_combo, self.settings.get("notify_scope", "owned"))
        form.addRow("Notifications:", self.scope_combo)

        self.flag_first_sight_cb = QCheckBox("Flag items on first sight (testing)")
        self.flag_first_sight_cb.setChecked(bool(self.settings.get("flag_first_sight", False)))
        form.addRow("", self.flag_first_sight_cb)

        layout.addWidget(filter_group)

        poll_group = QGroupBox("Poll interval")
        poll_layout = QHBoxLayout(poll_group)
        self.poll_input = QLineEdit(str(self.settings.get("poll_minutes", 5)))
        self.poll_input.setFixedWidth(60)
        poll_layout.addWidget(QLabel("Minutes:"))
        poll_layout.addWidget(self.poll_input)
        poll_layout.addStretch(1)
        layout.addWidget(poll_group)

        pat_group = QGroupBox("GitHub PAT")
        pat_layout = QFormLayout(pat_group)
        self.pat_input = QLineEdit(current_token or "")
        self.pat_input.setEchoMode(QLineEdit.Password)
        self.pat_input.setPlaceholderText("ghp_... (classic) or github_pat_... (fine-grained)")
        pat_layout.addRow("Token:", self.pat_input)
        self.pat_status = QLabel("PAT loaded from keyring." if current_token else "No PAT stored.")
        self.pat_status.setObjectName("muted")
        pat_layout.addRow("", self.pat_status)
        layout.addWidget(pat_group)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save)
        btn_row.addStretch(1)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)
        layout.addStretch(1)

    def _select_combo(self, combo: QComboBox, key: str):
        idx = combo.findData(key)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _save(self):
        try:
            poll_min = max(1, int(self.poll_input.text()))
        except ValueError:
            poll_min = 5
        new_settings = dict(self.settings)
        new_settings["issue_state"] = self.issue_combo.currentData()
        new_settings["pr_state"] = self.pr_combo.currentData()
        new_settings["show_bots"] = self.show_bots_cb.isChecked()
        new_settings["bot_allowlist"] = [
            s.strip() for s in self.bot_allowlist_input.text().split(",") if s.strip()
        ]
        new_settings["notify_scope"] = self.scope_combo.currentData()
        new_settings["flag_first_sight"] = self.flag_first_sight_cb.isChecked()
        new_settings["poll_minutes"] = poll_min
        self.settings = new_settings
        self.settings_changed.emit(new_settings)
        token = self.pat_input.text().strip()
        if token:
            self.pat_saved.emit(token)
            self.pat_status.setText("PAT saved to keyring.")


class MainWindow(QMainWindow):
    settings_changed = Signal(dict)
    pat_changed = Signal(str)
    activity_cleared = Signal(str)
    poll_now_requested = Signal()
    mark_requested = Signal(list, bool)

    def __init__(self, settings: dict, current_token: str):
        super().__init__()
        self.setWindowTitle("GitHub Tray")
        self.resize(640, 740)

        self.tabs = QTabWidget()
        self.issues_tab = ListTab()
        self.prs_tab = ListTab()
        self.settings_tab = SettingsTab(settings, current_token)
        self.tabs.addTab(self.issues_tab, "Issues")
        self.tabs.addTab(self.prs_tab, "PRs")
        self.tabs.addTab(self.settings_tab, "Settings")
        self.setCentralWidget(self.tabs)

        self.poll_button = QToolButton()
        self.poll_button.setObjectName("pollButton")
        self.poll_button.setIcon(svg_icon("poll.svg", 32))
        self.poll_button.setIconSize(QSize(18, 18))
        self.poll_button.setAutoRaise(True)
        self.poll_button.setCursor(Qt.PointingHandCursor)
        self.poll_button.setToolTip("Poll now")
        self.poll_button.clicked.connect(self.poll_now_requested)
        self.tabs.setCornerWidget(self.poll_button, Qt.TopRightCorner)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self.settings_tab.settings_changed.connect(self.settings_changed)
        self.settings_tab.pat_saved.connect(self.pat_changed)
        self.issues_tab.activity_cleared.connect(self.activity_cleared)
        self.prs_tab.activity_cleared.connect(self.activity_cleared)
        self.issues_tab.mark_requested.connect(self.mark_requested)
        self.prs_tab.mark_requested.connect(self.mark_requested)

    def set_data(self, issues, prs, activity_dict):
        self.issues_tab.set_items(issues, activity_dict)
        self.prs_tab.set_items(prs, activity_dict)

    def show_status(self, msg: str):
        self.status.showMessage(msg)

    def _clear_selections(self):
        self.issues_tab.clear_selection()
        self.prs_tab.clear_selection()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange and self.isMinimized():
            self._clear_selections()
        super().changeEvent(event)

    def closeEvent(self, event):
        event.ignore()
        self._clear_selections()
        self.hide()
