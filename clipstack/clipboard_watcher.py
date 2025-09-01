from __future__ import annotations
import re
import time
import hashlib
import html as htmllib
from datetime import datetime
from PySide6.QtCore import QObject, Signal, QMimeData, QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QClipboard, QImage, QTextDocument
from .storage import Storage, ClipItemType

ZERO_WIDTH = "\u200b\u200c\u200d\uFEFF"

_url_like_re = re.compile(
    r"^(?:https?:\/\/)?(?:www\.)?[\w\-\.]+\.[a-zA-Z]{2,}(?:[\/\?#][^\s]*)?$",
    re.IGNORECASE,
)
_href_re = re.compile(r'href\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)

def strip_invisible(s: str) -> str:
    return (s or "").strip().translate({ord(ch): None for ch in ZERO_WIDTH})

def looks_like_url(s: str) -> bool:
    s = strip_invisible(s)
    if not s or " " in s or "\n" in s or "\t" in s:
        return False
    return bool(_url_like_re.match(s))

def canonicalize_url(s: str) -> str:
    s = strip_invisible(s)
    s = htmllib.unescape(s)
    s = s.strip(" \t\r\n.,;)")
    if s.lower().startswith("http://"):
        s = "https://" + s[7:]
    elif not s.lower().startswith("https://"):
        s = "https://" + s.lstrip("/")
    return s

def extract_href_from_html(html: str) -> str | None:
    m = _href_re.search(html or "")
    if not m:
        return None
    href = m.group(1).strip()
    if href.lower().startswith(("javascript:", "data:", "mailto:")):
        return None
    return href

def html_to_plain_text(html: str) -> str:
    doc = QTextDocument()
    doc.setHtml(html or "")
    return doc.toPlainText()

def fingerprint_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def fingerprint_text(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()

class ClipboardWatcher(QObject):
    item_added = Signal(object)   # sqlite3.Row

    def __init__(self, clipboard: QClipboard, storage: Storage, settings):
        super().__init__()
        self.clipboard = clipboard
        self.storage = storage
        self.settings = settings
        self._paused = bool(settings.get("pause_recording", False))
        self._last_fp: str | None = None
        self._last_ts: float = 0.0
        self._dedupe_window_sec = 1.2
        self.clipboard.dataChanged.connect(self._on_clip_changed)

    def set_paused(self, paused: bool):
        self._paused = paused

    def _should_skip_by_fingerprint(self, fp: str) -> bool:
        now = time.time()
        if self._last_fp == fp and (now - self._last_ts) < self._dedupe_window_sec:
            return True
        self._last_fp = fp
        self._last_ts = now
        return False

    def _on_clip_changed(self):
        if self._paused:
            return

        md: QMimeData = self.clipboard.mimeData()
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1) Görsel (HTML yoksa)
        if self.clipboard.image() and not md.hasHtml():
            img: QImage = self.clipboard.image()
            if not img.isNull():
                ba = QByteArray()
                buf = QBuffer(ba)
                buf.open(QIODevice.WriteOnly)
                img.save(buf, "PNG")
                img_bytes = bytes(ba)
                fp = "I:" + fingerprint_bytes(img_bytes)
                if self._should_skip_by_fingerprint(fp):
                    return
                row = self.storage.add_item(ClipItemType.IMAGE, None, img_bytes, None, created_at)
                if row is not None:
                    self.item_added.emit(row)
            return

        html = md.html() if md.hasHtml() else ""
        text = md.text().strip() if md.hasText() else ""

        # 2) URL'leri tekilleştirip HTTPS TEXT olarak kaydet
        url_from_html = extract_href_from_html(html) if html else None
        candidate_url = None
        if url_from_html and looks_like_url(url_from_html):
            candidate_url = canonicalize_url(url_from_html)
        elif text and looks_like_url(text):
            candidate_url = canonicalize_url(text)

        if candidate_url:
            fp = "T:" + fingerprint_text(candidate_url)
            if self._should_skip_by_fingerprint(fp):
                return
            row = self.storage.add_item(ClipItemType.TEXT, candidate_url, None, None, created_at)
            if row is not None:
                self.item_added.emit(row)
            return

        # 3) HTML varsa: önce plain'e çevir, metinle eşleşiyorsa TEXT olarak kaydet
        if md.hasHtml():
            plain_from_html = html_to_plain_text(html).strip()
            if plain_from_html and (not text or strip_invisible(plain_from_html) == strip_invisible(text)):
                norm_text = strip_invisible(plain_from_html)
                if not norm_text:
                    return
                fp = "T:" + fingerprint_text(norm_text)
                if self._should_skip_by_fingerprint(fp):
                    return
                row = self.storage.add_item(ClipItemType.TEXT, norm_text, None, None, created_at)
                if row is not None:
                    self.item_added.emit(row)
                return

            # Gerçek zengin HTML ise ham HTML'i kaydet (önizleme düz metin olacak)
            fp = "H:" + fingerprint_text(html)
            if self._should_skip_by_fingerprint(fp):
                return
            row = self.storage.add_item(ClipItemType.HTML, None, None, html, created_at)
            if row is not None:
                self.item_added.emit(row)
            return

        # 4) Sade metin
        if md.hasText():
            norm_text = strip_invisible(text)
            if not norm_text:
                return
            fp = "T:" + fingerprint_text(norm_text)
            if self._should_skip_by_fingerprint(fp):
                return
            row = self.storage.add_item(ClipItemType.TEXT, norm_text, None, None, created_at)
            if row is not None:
                self.item_added.emit(row)