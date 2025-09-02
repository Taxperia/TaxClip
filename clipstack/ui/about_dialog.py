from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt
from ..settings import Settings
from ..i18n import i18n

class AboutDialog(QDialog):
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self._tr("about.title", "About"))
        v = QVBoxLayout(self)

        app_name = str(settings.get("app_name", "ClipStack"))
        dev = str(settings.get("developer_name", "Taxperia567"))
        des = str(settings.get("designer_name", "")).strip()

        v.addWidget(QLabel(f"{app_name}", alignment=Qt.AlignLeft))
        v.addWidget(QLabel(self._tr("about.developer", f"Developer: {dev}")))
        if des:
            v.addWidget(QLabel(self._tr("about.designer", f"Designer: {des}")))

        h = QHBoxLayout()
        h.addStretch(1)
        btn = QPushButton(self._tr("about.close", "Close"))
        btn.clicked.connect(self.accept)
        h.addWidget(btn)
        v.addLayout(h)

    def _tr(self, key: str, fallback: str) -> str:
        try:
            s = i18n.t(key)
        except Exception:
            s = ""
        return s if s and s != key else fallback