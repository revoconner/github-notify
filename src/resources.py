import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer


def asset_path(name: str) -> str:
    # Resolve a bundled asset to an absolute path. PyInstaller onefile unpacks to
    # sys._MEIPASS at runtime; dev and onedir resolve relative to the project root.
    base = getattr(sys, "_MEIPASS", None)
    root = Path(base) if base else Path(__file__).resolve().parent.parent
    return str((root / "assets" / name).resolve())


def svg_icon(name: str, size: int = 64) -> QIcon:
    renderer = QSvgRenderer(asset_path(name))
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    renderer.render(painter)
    painter.end()
    return QIcon(pix)
