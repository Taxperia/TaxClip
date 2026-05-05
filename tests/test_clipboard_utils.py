import ctypes
import sys
import unittest
from ctypes import wintypes

from PySide6.QtCore import QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

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
        cls.user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
        cls.user32.RegisterClipboardFormatW.restype = wintypes.UINT

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
        self.assertTrue(self.user32.OpenClipboard(None))
        try:
            self.assertTrue(self.user32.IsClipboardFormatAvailable(png_format))
            self.assertTrue(self.user32.IsClipboardFormatAvailable(image_png_format))
            self.assertTrue(self.user32.IsClipboardFormatAvailable(8))  # CF_DIB
        finally:
            self.user32.CloseClipboard()


if __name__ == "__main__":
    unittest.main()
