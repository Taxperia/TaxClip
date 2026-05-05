import sys
import time
from pathlib import Path

from PySide6.QtCore import QByteArray, QMimeData, Qt, QSize
from PySide6.QtGui import QClipboard, QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from .storage import ClipItemType

def resource_path(rel: str) -> Path:
    # PyInstaller (onefile) sırasında dosyalar sys._MEIPASS altında olur.
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / rel
    return Path(__file__).resolve().parent.parent / rel


def _normalize_icon_size(size) -> QSize:
    if isinstance(size, QSize):
        return size
    if isinstance(size, (tuple, list)) and len(size) == 2:
        return QSize(int(size[0]), int(size[1]))
    return QSize(int(size), int(size))


def _normalize_color(color) -> QColor | None:
    if color is None:
        return None
    if isinstance(color, QColor):
        return color if color.isValid() else None
    qcolor = QColor(str(color).strip())
    return qcolor if qcolor.isValid() else None


def _tint_pixmap_preserving_highlights(pixmap: QPixmap, color: QColor) -> QPixmap:
    if pixmap.isNull() or not color or not color.isValid():
        return pixmap

    image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    hue = color.hslHue() if color.hslHue() >= 0 else 0
    saturation = color.hslSaturation()

    for y in range(image.height()):
        for x in range(image.width()):
            pixel = image.pixelColor(x, y)
            if pixel.alpha() == 0:
                continue
            if pixel.red() > 240 and pixel.green() > 240 and pixel.blue() > 240:
                continue

            lightness = max(18, pixel.lightness())
            if saturation <= 5:
                tinted = QColor.fromHsl(0, 0, lightness, pixel.alpha())
            else:
                tinted = QColor.fromHsl(hue, saturation, lightness, pixel.alpha())
            image.setPixelColor(x, y, tinted)

    return QPixmap.fromImage(image)


def icon_pixmap(path_or_rel, size: int = 64, color=None) -> QPixmap:
    """Dosyadan pixmap üretir, istenirse renklendirir."""
    p = Path(path_or_rel)
    if not p.is_absolute():
        p = resource_path(str(path_or_rel))
    if not p.exists():
        return QPixmap()

    target_size = _normalize_icon_size(size)

    if not str(p).lower().endswith((".svg", ".svgz")):
        pixmap = QPixmap(str(p))
    else:
        pixmap = QPixmap()
        try:
            from PySide6.QtSvg import QSvgRenderer

            renderer = QSvgRenderer(str(p))
            if renderer.isValid():
                pixmap = QPixmap(target_size)
                pixmap.fill(Qt.transparent)
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()
        except ImportError:
            pass
        except Exception:
            pass

    if pixmap.isNull():
        return QPixmap()

    if pixmap.size() != target_size:
        pixmap = pixmap.scaled(target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    tint_color = _normalize_color(color)
    if tint_color:
        pixmap = _tint_pixmap_preserving_highlights(pixmap, tint_color)

    return pixmap


def svg_icon(path_or_rel, size: int = 64, color=None) -> QIcon:
    """Dosyadan QIcon üretir, istenirse renklendirir."""
    pixmap = icon_pixmap(path_or_rel, size=size, color=color)
    if not pixmap.isNull():
        return QIcon(pixmap)

    p = Path(path_or_rel)
    if not p.is_absolute():
        p = resource_path(str(path_or_rel))
    if not p.exists():
        return QIcon()
    return QIcon(str(p))

def notify_tray(tray, title: str, message: str, ms: int = 3000):
    try:
        tray.showMessage(title, message, QSystemTrayIcon.Information, ms)
    except Exception:
        pass


def _set_windows_native_png_clipboard(payload: bytes, retries: int = 5, retry_delay: float = 0.02) -> bool:
    if sys.platform != "win32" or not payload:
        return False

    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return False

    GMEM_MOVEABLE = 0x0002
    format_names = ("PNG", "image/png")
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    user32.RegisterClipboardFormatW.restype = wintypes.UINT

    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.restype = wintypes.HGLOBAL

    opened = False
    for _ in range(max(1, retries)):
        if user32.OpenClipboard(None):
            opened = True
            break
        time.sleep(max(0.0, retry_delay))

    if not opened:
        return False

    success = False
    try:
        for format_name in format_names:
            format_id = user32.RegisterClipboardFormatW(format_name)
            if not format_id:
                continue

            handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(payload))
            if not handle:
                continue

            locked = kernel32.GlobalLock(handle)
            if not locked:
                kernel32.GlobalFree(handle)
                continue

            try:
                ctypes.memmove(locked, payload, len(payload))
            finally:
                kernel32.GlobalUnlock(handle)

            if user32.SetClipboardData(format_id, handle):
                success = True
            else:
                kernel32.GlobalFree(handle)
    finally:
        user32.CloseClipboard()

    return success

def copy_to_clipboard_safely(widget, data_kind: ClipItemType, payload) -> bool:
    """Veriyi panoya güvenli şekilde kopyala"""
    app = QApplication.instance()
    clipboard = app.clipboard()
    try:
        clipboard.blockSignals(True)
        
        if data_kind == ClipItemType.IMAGE:
            img = QImage.fromData(QByteArray(payload), "PNG")
            if not img.isNull():
                mime_data = QMimeData()
                mime_data.setImageData(img)
                mime_data.setData("image/png", QByteArray(payload))
                clipboard.setMimeData(mime_data, QClipboard.Clipboard)
                _set_windows_native_png_clipboard(bytes(payload))
            else:
                return False
                
        elif data_kind == ClipItemType.HTML:
            # HTML içerik - hem HTML hem düz metin olarak ayarla
            text = str(payload or "")
            mime_data = QMimeData()
            mime_data.setHtml(text)
            # Düz metin versiyonunu da ekle (bazı uygulamalar bunu bekler)
            from PySide6.QtGui import QTextDocument
            doc = QTextDocument()
            doc.setHtml(text)
            plain_text = doc.toPlainText()
            mime_data.setText(plain_text)
            clipboard.setMimeData(mime_data, QClipboard.Clipboard)
            
        else:
            # TEXT - düz metin
            text = str(payload or "")
            clipboard.setText(text, QClipboard.Clipboard)
            
        return True
    except Exception as e:
        print(f"[CLIPBOARD] Kopyalama hatası: {e}")
        return False
    finally:
        clipboard.blockSignals(False)
