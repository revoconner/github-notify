from PySide6.QtGui import QPalette, QColor

BG = "#16181c"
BG_ALT = "#1c1f24"
BG_HOVER = "#22262c"
BORDER = "#2a2d33"
TEXT = "#c8c9cc"
TEXT_MUTED = "#7c7f86"
ACCENT = "#1a4870"
ACTIVITY = "#308637"
SELECT = "#243140"


def apply_dark_theme(app):
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(BG))
    palette.setColor(QPalette.WindowText, QColor(TEXT))
    palette.setColor(QPalette.Base, QColor(BG_ALT))
    palette.setColor(QPalette.AlternateBase, QColor(BG))
    palette.setColor(QPalette.ToolTipBase, QColor(BG_ALT))
    palette.setColor(QPalette.ToolTipText, QColor(TEXT))
    palette.setColor(QPalette.Text, QColor(TEXT))
    palette.setColor(QPalette.Button, QColor(BG_ALT))
    palette.setColor(QPalette.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.BrightText, QColor(TEXT))
    palette.setColor(QPalette.Link, QColor(ACCENT))
    palette.setColor(QPalette.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.HighlightedText, QColor(BG))
    palette.setColor(QPalette.PlaceholderText, QColor(TEXT_MUTED))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(TEXT_MUTED))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(TEXT_MUTED))
    app.setPalette(palette)

    qss = f"""
    QWidget {{ font-size: 12px; color: {TEXT}; }}
    QMainWindow, QDialog {{ background: {BG}; }}
    QTabWidget::pane {{ border: 1px solid {BORDER}; background: {BG}; }}
    QTabBar::tab {{
        background: {BG_ALT};
        color: {TEXT_MUTED};
        padding: 6px 14px;
        border: 1px solid {BORDER};
        border-bottom: none;
        margin-right: 1px;
    }}
    QTabBar::tab:selected {{ background: {BG}; color: {TEXT}; }}
    QTabBar::tab:hover {{ color: {TEXT}; }}
    QToolButton#pollButton {{ border: none; background: transparent; padding: 2px 10px; }}
    QToolButton#pollButton:hover {{ background: {BG_ALT}; }}
    QScrollArea#repoScroll {{ background: {BG}; border: 1px solid {BORDER}; }}
    QWidget#repoContainer {{ background: {BG}; }}
    QWidget#repoBody {{ background: {BG}; }}
    QWidget#repoHeader {{ background: {BG_ALT}; border-bottom: 1px solid {BORDER}; }}
    QWidget#repoHeader:hover {{ background: {BG_HOVER}; }}
    QLabel#repoArrow {{ color: {TEXT_MUTED}; font-size: 10px; }}
    QLabel#repoDot {{ color: {ACTIVITY}; font-size: 12px; }}
    QLabel#repoName {{ color: {TEXT}; font-size: 12px; font-weight: 600; }}
    QLabel#repoCount {{ color: {TEXT_MUTED}; font-size: 11px; }}
    QWidget#itemRow {{ background: {BG}; border-bottom: 1px solid {BG_ALT}; }}
    QWidget#itemRow:hover {{ background: {BG_ALT}; }}
    QWidget#itemRow[selected="true"], QWidget#itemRow[selected="true"]:hover {{ background: {SELECT}; }}
    QWidget#repoHeader[selected="true"], QWidget#repoHeader[selected="true"]:hover {{ background: {SELECT}; }}
    QPushButton {{
        background: {BG_ALT};
        color: {TEXT};
        border: 1px solid {BORDER};
        padding: 6px 14px;
    }}
    QPushButton:hover {{ background: {BG_HOVER}; }}
    QPushButton:pressed {{ background: {BORDER}; }}
    QLineEdit, QComboBox {{
        background: {BG_ALT};
        color: {TEXT};
        border: 1px solid {BORDER};
        padding: 5px 7px;
        selection-background-color: {ACCENT};
    }}
    QComboBox::drop-down {{ border: none; width: 18px; }}
    QComboBox QAbstractItemView {{
        background: {BG_ALT};
        color: {TEXT};
        border: 1px solid {BORDER};
        selection-background-color: {ACCENT};
    }}
    QCheckBox {{ color: {TEXT}; spacing: 6px; }}
    QCheckBox::indicator {{
        width: 13px; height: 13px;
        border: 1px solid {BORDER};
        background: {BG_ALT};
    }}
    QCheckBox::indicator:checked {{ background: {ACCENT}; }}
    QGroupBox {{
        border: 1px solid {BORDER};
        margin-top: 12px;
        padding-top: 10px;
        color: {TEXT_MUTED};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 4px;
    }}
    QStatusBar {{ color: {TEXT_MUTED}; background: {BG}; border-top: 1px solid {BORDER}; }}
    QMenu {{
        background: {BG_ALT};
        color: {TEXT};
        border: 1px solid {BORDER};
    }}
    QMenu::item:selected {{ background: {BG_HOVER}; }}
    QLabel#muted {{ color: {TEXT_MUTED}; font-size: 11px; }}
    QLabel#activity {{ color: {ACTIVITY}; font-size: 11px; }}
    QLabel#rowcount {{ color: {ACTIVITY}; font-size: 13px; font-weight: 700; }}
    QLabel#title {{ color: {TEXT}; font-size: 14px; font-weight: 500; }}
    QScrollBar:vertical {{ background: {BG}; width: 10px; border: none; }}
    QScrollBar::handle:vertical {{ background: {BORDER}; min-height: 24px; }}
    QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ background: none; border: none; height: 0; }}
    """
    app.setStyleSheet(qss)
