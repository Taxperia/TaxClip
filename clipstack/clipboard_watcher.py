from __future__ import annotations
import json
import re
import time
import zlib
import html as htmllib
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

from PySide6.QtCore import QObject, Signal, QMimeData, QBuffer, QByteArray, QIODevice, QTimer, QUrl
from PySide6.QtGui import QClipboard, QImage, QTextDocument
from .storage import Storage, ClipItemType
from .sensitive_detector import get_sensitive_detector, contains_sensitive_data
from .utils import copy_to_clipboard_safely
from .win_process import get_foreground_process_name

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
    """
    Kısa ömürlü pano dedupe anahtarı (kimlik doğrulama / parola saklama DEĞİL).
    Kriptografik hash kullanılmaz — CodeQL py/weak-sensitive-data-hashing
    false-positive'ini önlemek için length + Adler32 + CRC32 içerik kimliği.
    """
    data = b or b""
    a = zlib.adler32(data) & 0xFFFFFFFF
    c = zlib.crc32(data) & 0xFFFFFFFF
    return f"{len(data):x}-{a:08x}-{c:08x}"

def fingerprint_text(s: str) -> str:
    """Kısa ömürlü metin dedupe anahtarı (kimlik doğrulama / parola saklama DEĞİL)."""
    return fingerprint_bytes((s or "").encode("utf-8", errors="replace"))

def _paths_from_mime(md: QMimeData) -> list[str]:
    """CF_HDROP / hasUrls dosya listesini çıkar."""
    paths: list[str] = []
    if not md or not md.hasUrls():
        return paths
    for url in md.urls():
        try:
            if isinstance(url, QUrl):
                local = url.toLocalFile()
            else:
                local = str(url)
            if not local and str(url).startswith("file:"):
                parsed = urlparse(str(url))
                local = unquote(parsed.path)
                if local.startswith("/") and len(local) > 2 and local[2] == ":":
                    local = local[1:]
            if local:
                paths.append(str(Path(local)))
        except Exception:
            continue
    # Yalnızca gerçek dosya/klasör yolları (web URL'leri değil)
    return [p for p in paths if p and (":\\" in p or p.startswith("\\\\") or p.startswith("/"))]


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
        # Dedupe süresini ayarlardan al (ms -> saniye)
        self._dedupe_window_sec = settings.get("dedupe_window_ms", 1200) / 1000.0
        self._image_stabilize_retry_delays_ms = (80, 200, 500)
        self._clear_timer: QTimer | None = None
        self.clipboard.dataChanged.connect(self._on_clip_changed)
        self.sensitive_detector = get_sensitive_detector(settings)

    def set_paused(self, paused: bool):
        self._paused = paused

    def _excluded_apps(self) -> set[str]:
        raw = self.settings.get("excluded_apps", "") if self.settings else ""
        if isinstance(raw, list):
            items = raw
        else:
            items = [x.strip() for x in str(raw or "").replace(";", ",").split(",") if x.strip()]
        # Varsayılan güvenlik listesi
        defaults = {
            "keepass.exe", "keepassxc.exe", "1password.exe", "bitwarden.exe",
            "lastpass.exe", "enpass.exe", "dashlane.exe",
        }
        return {x.lower() for x in items} | defaults

    def _should_skip_source_app(self) -> bool:
        if not self.settings or not self.settings.get("exclude_apps_enabled", True):
            return False
        proc = get_foreground_process_name()
        if not proc:
            return False
        excluded = self._excluded_apps()
        return proc in excluded or any(proc.endswith(x) for x in excluded)

    def _schedule_clipboard_clear(self, text: str):
        """Hassas veri panodan otomatik temizlensin."""
        if not self.settings:
            return
        secs = int(self.settings.get("auto_clear_clipboard_seconds", 0) or 0)
        if secs <= 0:
            return
        if not contains_sensitive_data(text, self.settings):
            return
        if self._clear_timer is not None:
            self._clear_timer.stop()
            self._clear_timer.deleteLater()
        self._clear_timer = QTimer(self)
        self._clear_timer.setSingleShot(True)
        captured = text

        def _clear():
            try:
                current = self.clipboard.text()
                if current == captured:
                    self.clipboard.clear()
                    print(f"[CLIPBOARD] Hassas içerik {secs}s sonra temizlendi")
            except Exception:
                pass

        self._clear_timer.timeout.connect(_clear)
        self._clear_timer.start(secs * 1000)

    def _should_skip_by_fingerprint(self, fp: str) -> bool:
        now = time.time()
        if self._last_fp == fp and (now - self._last_ts) < self._dedupe_window_sec:
            return True
        self._last_fp = fp
        self._last_ts = now
        return False

    def _image_mime_needs_stabilization(self, md: QMimeData) -> bool:
        formats = [fmt.lower() for fmt in (md.formats() or [])]
        return "image/png" not in formats

    def _queue_image_stabilization(self, expected_fp: str, png_bytes: bytes, md: QMimeData):
        if md is None or md.hasHtml() or not self._image_mime_needs_stabilization(md):
            return

        self._stabilize_clipboard_image(expected_fp, png_bytes)

        for delay_ms in self._image_stabilize_retry_delays_ms:
            QTimer.singleShot(
                delay_ms,
                lambda fp=expected_fp, img_bytes=png_bytes: self._stabilize_clipboard_image(fp, img_bytes),
            )

    def _stabilize_clipboard_image(self, expected_fp: str, png_bytes: bytes):
        md = self.clipboard.mimeData()
        if md is None or md.hasHtml() or not self._image_mime_needs_stabilization(md):
            return

        img = self.clipboard.image()
        if img.isNull():
            return

        ba = QByteArray()
        buf = QBuffer(ba)
        if not buf.open(QIODevice.WriteOnly):
            return
        img.save(buf, "PNG")
        current_bytes = bytes(ba)

        if "I:" + fingerprint_bytes(current_bytes) != expected_fp:
            return

        # Print Screen / Snipping Tool gibi kaynaklardan gelen ham bitmap'i
        # PNG + imageData formatlarıyla yeniden yazarak Ctrl+V kararlılığını artır.
        copy_to_clipboard_safely(None, ClipItemType.IMAGE, png_bytes)

    def _on_clip_changed(self):
        if self._paused:
            return

        if self._should_skip_source_app():
            print(f"[CLIPBOARD] Hariç tutulan uygulama: {get_foreground_process_name()}")
            return

        md: QMimeData = self.clipboard.mimeData()
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        source_app = get_foreground_process_name()

        # 0) Dosya/klasör listesi (CF_HDROP)
        file_paths = _paths_from_mime(md)
        if file_paths:
            payload = json.dumps({"paths": file_paths}, ensure_ascii=False)
            fp = "F:" + fingerprint_text(payload)
            if self._should_skip_by_fingerprint(fp):
                return
            row = self.storage.add_item(
                ClipItemType.FILE, payload, None, None, created_at, source_app=source_app
            )
            if row is not None:
                self.item_added.emit(row)
            return

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
                self._queue_image_stabilization(fp, img_bytes, md)
                if self._should_skip_by_fingerprint(fp):
                    return
                row = self.storage.add_item(
                    ClipItemType.IMAGE, None, img_bytes, None, created_at, source_app=source_app
                )
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
            row = self.storage.add_item(
                ClipItemType.TEXT, candidate_url, None, None, created_at, source_app=source_app
            )
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
                
                # Hassas veri kontrolü
                should_block, block_reason = self.sensitive_detector.should_block(norm_text)
                if should_block:
                    print(f"[SENSITIVE] HTML metni engellendi: {block_reason}")
                    return
                
                # Hassas veriyi maskele
                masked_text, was_masked = self.sensitive_detector.mask_text(norm_text)
                if was_masked:
                    print(f"[SENSITIVE] HTML'den çıkan metin maskelendi")
                    norm_text = masked_text
                
                fp = "T:" + fingerprint_text(norm_text)
                if self._should_skip_by_fingerprint(fp):
                    return
                is_sens = contains_sensitive_data(norm_text, self.settings) if not was_masked else True
                row = self.storage.add_item(
                    ClipItemType.TEXT, norm_text, None, None, created_at,
                    source_app=source_app, is_sensitive=is_sens,
                )
                if row is not None:
                    self.item_added.emit(row)
                    self._schedule_clipboard_clear(norm_text)
                return

            # Gerçek zengin HTML ise ham HTML'i kaydet (önizleme düz metin olacak)
            fp = "H:" + fingerprint_text(html)
            if self._should_skip_by_fingerprint(fp):
                return
            row = self.storage.add_item(
                ClipItemType.HTML, None, None, html, created_at, source_app=source_app
            )
            if row is not None:
                self.item_added.emit(row)
            return

        # 4) Sade metin
        if md.hasText():
            norm_text = strip_invisible(text)
            if not norm_text:
                return
            
            # Hassas veri kontrolü
            should_block, block_reason = self.sensitive_detector.should_block(norm_text)
            if should_block:
                print(f"[SENSITIVE] Metin engellendi: {block_reason}")
                return
            
            # Hassas veriyi maskele
            masked_text, was_masked = self.sensitive_detector.mask_text(norm_text)
            if was_masked:
                print(f"[SENSITIVE] Hassas veri maskelendi")
                norm_text = masked_text
            
            fp = "T:" + fingerprint_text(norm_text)
            if self._should_skip_by_fingerprint(fp):
                return
            is_sens = contains_sensitive_data(norm_text, self.settings) if not was_masked else True
            row = self.storage.add_item(
                ClipItemType.TEXT, norm_text, None, None, created_at,
                source_app=source_app, is_sensitive=is_sens,
            )
            if row is not None:
                self.item_added.emit(row)
                self._schedule_clipboard_clear(norm_text)
