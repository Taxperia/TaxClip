from __future__ import annotations
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from .utils import resource_path

class ThemeManager:
    # keys: default, dark, light, purple, cyberpunk, sunset, matrix, ocean, retro
    def __init__(self):
        self.current = "default"

    def apply(self, theme_key: str):
        self.current = theme_key
        app = QApplication.instance()
        if not app:
            return
        # Load QSS
        qss_file = {
            "default": "styles/theme_default.qss",
            "dark": "styles/theme_dark.qss",
            "light": "styles/theme_light.qss",
            "purple": "styles/theme_purple.qss",
            "cyberpunk": "styles/theme_cyberpunk.qss",
            "sunset": "styles/theme_sunset.qss",
            "matrix": "styles/theme_matrix.qss",
            "ocean": "styles/theme_ocean.qss",
            "retro": "styles/theme_retro.qss",
        }.get(theme_key, "styles/theme_default.qss")
        try:
            qss = resource_path(qss_file).read_text("utf-8")
            app.setStyleSheet(qss)
        except Exception:
            pass
        # Palette minimal tweak
        pal = app.palette()
        if theme_key == "light":
            pal.setColor(QPalette.Window, QColor("#f4f7fb"))
            pal.setColor(QPalette.Base, QColor("#ffffff"))
            pal.setColor(QPalette.Text, QColor("#111111"))
            pal.setColor(QPalette.WindowText, QColor("#111111"))
        elif theme_key == "retro":
            pal.setColor(QPalette.Window, QColor("#0078d7"))
            pal.setColor(QPalette.Base, QColor("#ffffff"))
            pal.setColor(QPalette.Text, QColor("#000000"))
            pal.setColor(QPalette.WindowText, QColor("#ffffff"))
        elif theme_key == "matrix":
            pal.setColor(QPalette.Window, QColor("#0d0d0d"))
            pal.setColor(QPalette.Base, QColor("#001a00"))
            pal.setColor(QPalette.Text, QColor("#00ff41"))
            pal.setColor(QPalette.WindowText, QColor("#00ff41"))
        elif theme_key == "cyberpunk":
            pal.setColor(QPalette.Window, QColor("#0d0221"))
            pal.setColor(QPalette.Base, QColor("#1a0933"))
            pal.setColor(QPalette.Text, QColor("#f0e7ff"))
            pal.setColor(QPalette.WindowText, QColor("#f0e7ff"))
        elif theme_key in ("sunset", "ocean"):
            pal.setColor(QPalette.Window, QColor("#1a0a2e"))
            pal.setColor(QPalette.Base, QColor("#1a0a2e"))
            pal.setColor(QPalette.Text, QColor("#ffe5ec"))
            pal.setColor(QPalette.WindowText, QColor("#ffe5ec"))
        else:
            pal.setColor(QPalette.Window, QColor("#0f172a"))
            pal.setColor(QPalette.Base, QColor("#0f172a"))
            pal.setColor(QPalette.Text, QColor("#e2e8f0"))
            pal.setColor(QPalette.WindowText, QColor("#e2e8f0"))
        app.setPalette(pal)

theme_manager = ThemeManager()