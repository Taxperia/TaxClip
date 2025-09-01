from pathlib import Path
from PySide6.QtWidgets import QApplication, QSystemTrayIcon
from PySide6.QtGui import QImage, QClipboard
from PySide6.QtCore import QByteArray
from .storage import ClipItemType
import sys

def resource_path(rel: str) -> Path:
    # PyInstaller (onefile) sırasında dosyalar sys._MEIPASS altında olur.
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / rel
    return Path(__file__).resolve().parent.parent / rel

def notify_tray(tray, title: str, message: str, ms: int = 3000):
    try:
        tray.showMessage(title, message, QSystemTrayIcon.Information, ms)
    except Exception:
        pass

def copy_to_clipboard_safely(widget, data_kind: ClipItemType, payload) -> bool:
    app = QApplication.instance()
    clipboard = app.clipboard()
    try:
        clipboard.blockSignals(True)
        if data_kind == ClipItemType.IMAGE:
            img = QImage.fromData(QByteArray(payload), "PNG")
            clipboard.setImage(img, QClipboard.Clipboard)
        else:
            text = str(payload or "")
            clipboard.setText(text, QClipboard.Clipboard)
        return True
    except Exception:
        return False
    finally:
        clipboard.blockSignals(False)