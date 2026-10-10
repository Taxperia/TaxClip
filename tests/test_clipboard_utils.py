import ctypes
import struct
import sys
import time
import unittest
from ctypes import wintypes

from PySide6.QtCore import QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QWidget

from clipstack.storage import ClipItemType
from clipstack.utils import copy_to_clipboard_safely


@unittest.skipUnless(sys.platform == "win32", "Windows clipboard format test")
class ClipboardUtilsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.user32 = ctypes.windll.user32
        cls.user32.OpenClipboard.argtypes = [wintypes.HWND]
        cls.user32.OpenClipboard.restype = wintypes.BOOL
        cls.user32.CloseClipboard.restype = wintypes.BOOL
        cls.user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
        cls.user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
        cls.user32.GetClipboardData.argtypes = [wintypes.UINT]
        cls.user32.GetClipboardData.restype = wintypes.HANDLE
        cls.user32.GetClipboardOwner.restype = wintypes.HWND
        cls.user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
        cls.user32.RegisterClipboardFormatW.restype = wintypes.UINT
        cls.kernel32 = ctypes.windll.kernel32
        cls.kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        cls.kernel32.GlobalLock.restype = ctypes.c_void_p
        cls.kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        cls.kernel32.GlobalUnlock.restype = wintypes.BOOL
        cls.kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]
        cls.kernel32.GlobalSize.restype = ctypes.c_size_t

    def _open_clipboard(self, attempts=50, delay=0.01):
        for _ in range(attempts):
            self.app.processEvents()
            if self.user32.OpenClipboard(None):
                return True
            time.sleep(delay)
        return False

    def test_copy_image_adds_native_png_clipboard_formats(self):
        image = QImage(32, 24, QImage.Format.Format_ARGB32)
        image.fill(0xFF1E90FF)

        buffer_data = QByteArray()
        buffer = QBuffer(buffer_data)
        self.assertTrue(buffer.open(QIODevice.WriteOnly))
        self.assertTrue(image.save(buffer, "PNG"))
        buffer.close()

        copied = copy_to_clipboard_safely(None, ClipItemType.IMAGE, bytes(buffer_data))
        self.assertTrue(copied)

        clipboard = QApplication.clipboard()
        self.assertFalse(clipboard.image().isNull())
        self.assertIn("image/png", clipboard.mimeData().formats())

        png_format = self.user32.RegisterClipboardFormatW("PNG")
        image_png_format = self.user32.RegisterClipboardFormatW("image/png")
        self.assertTrue(self._open_clipboard())
        try:
            self.assertTrue(self.user32.IsClipboardFormatAvailable(png_format))
            self.assertTrue(self.user32.IsClipboardFormatAvailable(image_png_format))
            self.assertTrue(self.user32.IsClipboardFormatAvailable(2))  # CF_BITMAP
            self.assertTrue(self.user32.IsClipboardFormatAvailable(8))  # CF_DIB

            dib_handle = self.user32.GetClipboardData(8)
            self.assertTrue(dib_handle)
            dib_size = self.kernel32.GlobalSize(dib_handle)
            dib_ptr = self.kernel32.GlobalLock(dib_handle)
            self.assertTrue(dib_ptr)
            try:
                dib = ctypes.string_at(dib_ptr, dib_size)
            finally:
                self.kernel32.GlobalUnlock(dib_handle)
            header = struct.unpack_from("<IiiHHIIiiII", dib)
            self.assertEqual(header[0], 40)
            self.assertEqual(header[1:3], (32, 24))
            self.assertEqual(header[3:6], (1, 24, 0))
        finally:
            self.user32.CloseClipboard()

    def test_repeated_image_copy_stays_immediately_readable(self):
        clipboard = QApplication.clipboard()
        for index in range(20):
            image = QImage(80 + index, 48, QImage.Format.Format_ARGB32)
            image.fill(0xFF000000 | ((index * 11) << 16) | 0x003366)
            buffer_data = QByteArray()
            buffer = QBuffer(buffer_data)
            self.assertTrue(buffer.open(QIODevice.WriteOnly))
            self.assertTrue(image.save(buffer, "PNG"))
            buffer.close()

            self.assertTrue(copy_to_clipboard_safely(None, ClipItemType.IMAGE, bytes(buffer_data)))
            pasted = clipboard.image()
            self.assertFalse(pasted.isNull(), f"copy {index} returned a blank image")
            self.assertEqual(pasted.size(), image.size())

    def test_image_copy_uses_a_real_window_as_clipboard_owner(self):
        owner_widget = QWidget()
        owner_handle = int(owner_widget.winId())
        image = QImage(18, 12, QImage.Format.Format_ARGB32)
        image.fill(0xFFFF5500)
        buffer_data = QByteArray()
        buffer = QBuffer(buffer_data)
        self.assertTrue(buffer.open(QIODevice.WriteOnly))
        self.assertTrue(image.save(buffer, "PNG"))
        buffer.close()

        self.assertTrue(copy_to_clipboard_safely(
            owner_widget, ClipItemType.IMAGE, bytes(buffer_data)
        ))
        self.assertEqual(int(self.user32.GetClipboardOwner()), owner_handle)
        self.assertFalse(QApplication.clipboard().image().isNull())


if __name__ == "__main__":
    unittest.main()
