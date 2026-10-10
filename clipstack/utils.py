import sys
import time
import struct
from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QMimeData, Qt, QSize, QUrl
from PySide6.QtGui import QClipboard, QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from .storage import ClipItemType

def resource_path(rel: str) -> Path:
    requested = Path(rel)
    if requested.is_absolute():
        return requested
    # PyInstaller (onefile) sırasında dosyalar sys._MEIPASS altında olur.
    base = Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else Path(__file__).resolve().parent.parent
    base = base.resolve()
    candidate = (base / requested).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        return base / "__invalid_resource__"
    return candidate


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


def _qimage_as_dib(image: QImage) -> bytes:
    """Return an opaque, bottom-up 24-bit CF_DIB payload.

    Some Windows paste targets treat the unused alpha byte in a 32-bit
    BITMAPINFOHEADER as transparency and display an otherwise valid image as
    blank.  A 24-bit DIB has no ambiguous alpha channel and is the most widely
    supported clipboard fallback.
    """
    if image.isNull() or image.width() <= 0 or image.height() <= 0:
        return b""

    converted = image.convertToFormat(QImage.Format.Format_BGR888)
    width = converted.width()
    height = converted.height()
    stride = converted.bytesPerLine()  # Qt and DIB both align rows to 4 bytes.
    raw = converted.constBits()
    pixel_data = b"".join(
        raw[y * stride:(y + 1) * stride]
        for y in range(height - 1, -1, -1)
    )
    header = struct.pack(
        "<IiiHHIIiiII",
        40, width, height, 1, 24, 0, len(pixel_data), 2835, 2835, 0, 0,
    )
    return header + pixel_data


def _set_clipboard_bitmap(user32, gdi32, image: QImage) -> bool:
    """Add a real CF_BITMAP handle for applications that ignore DIB/PNG."""
    import ctypes
    from ctypes import wintypes

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD),
            ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG),
            ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD),
            ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD),
            ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG),
            ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    class RGBQUAD(ctypes.Structure):
        _fields_ = [
            ("rgbBlue", ctypes.c_ubyte),
            ("rgbGreen", ctypes.c_ubyte),
            ("rgbRed", ctypes.c_ubyte),
            ("rgbReserved", ctypes.c_ubyte),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", RGBQUAD * 1)]

    converted = image.convertToFormat(QImage.Format.Format_RGB32)
    width = converted.width()
    height = converted.height()
    if width <= 0 or height <= 0:
        return False

    info = BITMAPINFO()
    info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    info.bmiHeader.biWidth = width
    info.bmiHeader.biHeight = height
    info.bmiHeader.biPlanes = 1
    info.bmiHeader.biBitCount = 32
    info.bmiHeader.biCompression = 0  # BI_RGB; the fourth byte is ignored.
    info.bmiHeader.biSizeImage = width * height * 4

    bits = ctypes.c_void_p()
    gdi32.CreateDIBSection.argtypes = [
        wintypes.HDC, ctypes.POINTER(BITMAPINFO), wintypes.UINT,
        ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD,
    ]
    gdi32.CreateDIBSection.restype = wintypes.HBITMAP
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteObject.restype = wintypes.BOOL

    bitmap = gdi32.CreateDIBSection(None, ctypes.byref(info), 0, ctypes.byref(bits), None, 0)
    if not bitmap or not bits.value:
        return False

    try:
        source = converted.constBits()
        stride = converted.bytesPerLine()
        row_size = width * 4
        for target_row, source_row in enumerate(range(height - 1, -1, -1)):
            ctypes.memmove(
                bits.value + (target_row * row_size),
                bytes(source[source_row * stride:source_row * stride + row_size]),
                row_size,
            )
        if user32.SetClipboardData(2, bitmap):  # CF_BITMAP
            bitmap = None  # Clipboard now owns the GDI handle.
            return True
        return False
    finally:
        if bitmap:
            gdi32.DeleteObject(bitmap)


def _clipboard_owner_handle(widget=None) -> int:
    """Return a real application HWND for reliable Windows clipboard ownership."""
    candidates = [widget, QApplication.activeWindow()]
    candidates.extend(QApplication.topLevelWidgets())
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            handle = int(candidate.window().winId())
            if handle:
                return handle
        except (AttributeError, RuntimeError, TypeError, ValueError):
            continue
    return 0


def _set_windows_image_clipboard(
    image: QImage,
    png_payload: bytes,
    owner_handle: int = 0,
) -> bool:
    """Write eager Windows formats so screenshots remain pasteable everywhere."""
    if sys.platform != "win32" or image.isNull() or not png_payload:
        return False

    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return False

    dib_payload = _qimage_as_dib(image)
    if not dib_payload:
        return False

    GMEM_MOVEABLE = 0x0002
    CF_DIB = 8
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    gdi32 = ctypes.windll.gdi32

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.restype = wintypes.BOOL
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
    for _ in range(20):
        if user32.OpenClipboard(wintypes.HWND(owner_handle) if owner_handle else None):
            opened = True
            break
        time.sleep(0.01)
    if not opened:
        return False

    compatible_format_written = False
    try:
        if not user32.EmptyClipboard():
            return False
        png_format = int(user32.RegisterClipboardFormatW("PNG") or 0)
        image_png_format = int(user32.RegisterClipboardFormatW("image/png") or 0)
        # Put modern lossless formats first. Consumers that enumerate formats
        # can select PNG, while older programs still receive CF_DIB/CF_BITMAP.
        formats = []
        if png_format:
            formats.append((png_format, bytes(png_payload)))
        if image_png_format and image_png_format != png_format:
            formats.append((image_png_format, bytes(png_payload)))
        formats.append((CF_DIB, dib_payload))

        for format_id, data in formats:
            handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
            if not handle:
                continue
            locked = kernel32.GlobalLock(handle)
            if not locked:
                kernel32.GlobalFree(handle)
                continue
            try:
                ctypes.memmove(locked, data, len(data))
            finally:
                kernel32.GlobalUnlock(handle)
            if user32.SetClipboardData(format_id, handle):
                if format_id == CF_DIB:
                    compatible_format_written = True
            else:
                kernel32.GlobalFree(handle)
        if _set_clipboard_bitmap(user32, gdi32, image):
            compatible_format_written = True
        return compatible_format_written
    finally:
        user32.CloseClipboard()


def copy_to_clipboard_safely(widget, data_kind: ClipItemType, payload) -> bool:
    """Veriyi panoya güvenli şekilde kopyala"""
    app = QApplication.instance()
    clipboard = app.clipboard()
    try:
        clipboard.blockSignals(True)
        
        if data_kind == ClipItemType.IMAGE:
            if not payload:
                return False
            try:
                png_payload = bytes(payload)
            except (TypeError, ValueError):
                return False
            img = QImage.fromData(QByteArray(png_payload), "PNG")
            if not img.isNull():
                owner_handle = _clipboard_owner_handle(widget)
                if not _set_windows_image_clipboard(img, png_payload, owner_handle):
                    mime_data = QMimeData()
                    mime_data.setImageData(img)
                    mime_data.setData("image/png", QByteArray(png_payload))
                    clipboard.setMimeData(mime_data, QClipboard.Clipboard)
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

        elif data_kind == ClipItemType.FILE:
            # Dosya yollarını CF_HDROP olarak panoya koy
            import json
            from pathlib import Path
            paths = []
            if isinstance(payload, str):
                try:
                    data = json.loads(payload)
                    paths = data.get("paths", []) if isinstance(data, dict) else []
                except Exception:
                    paths = [payload] if payload else []
            elif isinstance(payload, (list, tuple)):
                paths = list(payload)
            urls = []
            for p in paths:
                try:
                    urls.append(QUrl.fromLocalFile(str(Path(p))))
                except Exception:
                    continue
            if not urls:
                return False
            mime_data = QMimeData()
            mime_data.setUrls(urls)
            mime_data.setText("\n".join(str(p) for p in paths))
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
