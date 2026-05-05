import base64
import binascii
import sqlite3
import re
import unicodedata
from enum import IntEnum
from pathlib import Path
from typing import List, Optional
from clipstack.utils_crypto import encrypt_aes256, decrypt_aes256
from clipstack.sensitive_detector import get_sensitive_detector
from datetime import datetime, timedelta
from rapidfuzz import fuzz


_whitespace_re = re.compile(r"\s+")
_html_tag_re = re.compile(r"<[^>]+>")
_search_token_re = re.compile(r"\w+", re.UNICODE)
_turkish_search_char_map = str.maketrans({
    "ı": "i",
    "İ": "i",
})


def _normalize_search_text(value: str) -> str:
    text = (value or "").translate(_turkish_search_char_map)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return _whitespace_re.sub(" ", text.strip().casefold())


def _strip_html_tags(value: str) -> str:
    return _normalize_search_text(_html_tag_re.sub(" ", value or ""))


def _html_to_plain_text(value: str) -> str:
    return _whitespace_re.sub(" ", _html_tag_re.sub(" ", value or "")).strip()


def _tokenize_search_text(value: str) -> List[str]:
    return [token for token in _search_token_re.findall(_normalize_search_text(value)) if token]


def _term_matches_word_prefix(term: str, word: str) -> bool:
    return bool(term and word.startswith(term))


def _term_matches_word_contains(term: str, word: str) -> bool:
    if not term or len(term) < 4:
        return False
    return term in word


def _score_search_match(normalized_query: str, searchable_text: str) -> int:
    if not normalized_query or not searchable_text:
        return 0

    query_terms = [term for term in normalized_query.split(" ") if term]
    searchable_terms = _tokenize_search_text(searchable_text)
    if not query_terms or not searchable_terms:
        return 0

    if len(query_terms) > 1 and normalized_query in searchable_text:
        return 100

    if len(query_terms) == 1:
        term = query_terms[0]
        if term in searchable_terms:
            return 100
        if any(_term_matches_word_prefix(term, word) for word in searchable_terms):
            return 98
        if len(term) >= 4 and term in searchable_text:
            return 96
        if len(term) < 5:
            return 0

        best_word_score = 0
        for word in searchable_terms:
            best_word_score = max(
                best_word_score,
                int(fuzz.ratio(term, word)),
                int(fuzz.partial_ratio(term, word)),
            )

        if best_word_score >= 90:
            return best_word_score

        phrase_score = int(fuzz.token_set_ratio(term, searchable_text))
        if phrase_score >= 94:
            return phrase_score
        return 0

    prefix_hits = sum(
        1 for term in query_terms
        if any(_term_matches_word_prefix(term, word) for word in searchable_terms)
    )
    contains_hits = sum(
        1 for term in query_terms
        if any(_term_matches_word_contains(term, word) for word in searchable_terms)
    )

    if prefix_hits == len(query_terms):
        return 98
    if contains_hits == len(query_terms):
        return 96

    if len(normalized_query) < 6:
        return 0

    token_score = int(fuzz.token_set_ratio(normalized_query, searchable_text))
    ratio_score = int(fuzz.ratio(normalized_query, searchable_text))
    combined_score = max(token_score, ratio_score)
    if combined_score >= 88:
        return combined_score
    return 0


def _looks_like_encrypted_value(value: str) -> bool:
    if not isinstance(value, str) or len(value) < 24:
        return False
    try:
        raw = base64.b64decode(value.encode("utf-8"), validate=True)
    except (ValueError, binascii.Error):
        return False
    return len(raw) >= 16


def _decrypt_field_if_needed(value: Optional[str], password: Optional[str]) -> Optional[str]:
    if not value or not password:
        return value
    if not _looks_like_encrypted_value(value):
        return value
    try:
        return decrypt_aes256(value, password)
    except Exception:
        return "[Şifreli veri çözülemedi]"


class ClipItemType(IntEnum):
    TEXT = 1
    IMAGE = 2
    HTML = 3


class Storage:
    def __init__(self, path: Path, settings=None):
        self.path = Path(path)
        self.settings = settings
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _get_encryption_password(self) -> Optional[str]:
        if not self.settings or not self.settings.get("encrypt_data", False):
            return None
        return self.settings.get("encryption_key", None)

    def _decrypt_clip_row(self, row_dict: dict) -> dict:
        password = self._get_encryption_password()
        if not password:
            return row_dict

        for field in ("text_content", "html_content", "ocr_text"):
            if row_dict.get(field):
                row_dict[field] = _decrypt_field_if_needed(row_dict[field], password)
        return row_dict

    def _protect_clip_item(
        self,
        item_type: ClipItemType,
        text: Optional[str],
        html: Optional[str],
        ocr_text: Optional[str],
    ) -> tuple[ClipItemType, Optional[str], Optional[str], Optional[str], bool]:
        if not self.settings:
            return item_type, text, html, ocr_text, False

        detector = get_sensitive_detector(self.settings)

        if item_type == ClipItemType.TEXT and text:
            should_block, reason = detector.should_block(text)
            if should_block:
                print(f"[STORAGE SENSITIVE] Metin engellendi: {reason}")
                return item_type, text, html, ocr_text, True
            text, _ = detector.mask_text(text)

        elif item_type == ClipItemType.HTML and html:
            plain_text = _html_to_plain_text(html)
            if plain_text:
                should_block, reason = detector.should_block(plain_text)
                if should_block:
                    print(f"[STORAGE SENSITIVE] HTML engellendi: {reason}")
                    return item_type, text, html, ocr_text, True

                masked_plain_text, was_masked = detector.mask_text(plain_text)
                if was_masked:
                    item_type = ClipItemType.TEXT
                    text = masked_plain_text
                    html = None
                    print("[STORAGE SENSITIVE] Zengin HTML maskeli düz metne dönüştürüldü")

        if item_type == ClipItemType.IMAGE and ocr_text:
            should_block, reason = detector.should_block(ocr_text)
            if should_block:
                print(f"[STORAGE SENSITIVE] OCR ile hassas içerik taşıyan görsel engellendi: {reason}")
                return item_type, text, html, ocr_text, True

        return item_type, text, html, ocr_text, False

    def _init_db(self):
        cur = self.conn.cursor()

        # Mevcut: kopya öğeleri tablosu
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS clip_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                item_type INTEGER NOT NULL,
                text_content TEXT,
                image_blob BLOB,
                html_content TEXT,
                favorite INTEGER NOT NULL DEFAULT 0,
                ocr_text TEXT
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_clip_items_created ON clip_items(created_at DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_clip_items_fav ON clip_items(favorite)")
        
        # OCR text sütunu yoksa ekle (mevcut DB'ler için)
        try:
            cur.execute("SELECT ocr_text FROM clip_items LIMIT 1")
        except:
            try:
                cur.execute("ALTER TABLE clip_items ADD COLUMN ocr_text TEXT")
                print("[STORAGE] OCR text sütunu eklendi")
            except Exception as e:
                print(f"[STORAGE] OCR text sütunu eklenemedi: {e}")

        # Yeni: notlar tablosu (varsa dokunmaz)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                content TEXT NOT NULL
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_notes_created ON notes(created_at DESC)")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                reminder_time TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                repeat_type TEXT DEFAULT 'none',
                last_triggered TEXT DEFAULT NULL
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_reminders_time ON reminders(reminder_time)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_reminders_active ON reminders(is_active)")
        
        # Snippets tablosu (kod parçacıkları)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS snippets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                title TEXT NOT NULL,
                code TEXT NOT NULL,
                language TEXT NOT NULL,
                tags TEXT,
                favorite INTEGER NOT NULL DEFAULT 0,
                is_multi_file INTEGER DEFAULT 0
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_snippets_created ON snippets(created_at DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_snippets_fav ON snippets(favorite)")
        
        # Multi-file snippet'ler için snippet_files tablosu
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS snippet_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snippet_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                content TEXT NOT NULL,
                language TEXT NOT NULL,
                order_index INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (snippet_id) REFERENCES snippets(id) ON DELETE CASCADE
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_snippet_files_snippet ON snippet_files(snippet_id)")
        
        # is_multi_file sütunu yoksa ekle
        try:
            cur.execute("SELECT is_multi_file FROM snippets LIMIT 1")
        except:
            try:
                cur.execute("ALTER TABLE snippets ADD COLUMN is_multi_file INTEGER DEFAULT 0")
                print("[STORAGE] is_multi_file sütunu eklendi")
            except Exception as e:
                print(f"[STORAGE] is_multi_file sütunu eklenemedi: {e}")
        
        # Todos tablosu
        # Todo Lists tablosu
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS todo_lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_todo_lists_created ON todo_lists(created_at DESC)")
        
        # Todos tablosu (list_id ile) - index'leri sonra ekleyeceğiz
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                list_id INTEGER,
                created_at TEXT NOT NULL,
                content TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT
            )
            """
        )
        
        # Drawings tablosu
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS drawings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                image_data BLOB NOT NULL,
                title TEXT,
                favorite INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_drawings_created ON drawings(created_at DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_drawings_fav ON drawings(favorite)")
        
        # Eski 'notified' sütununu kaldır, 'last_triggered' ekle
        try:
            cur.execute("SELECT last_triggered FROM reminders LIMIT 1")
        except:
            # Eğer sütun yoksa, ekle
            try:
                cur.execute("ALTER TABLE reminders ADD COLUMN last_triggered TEXT DEFAULT NULL")
            except:
                pass
            # Eski notified sütununu temizle
            try:
                cur.execute("UPDATE reminders SET notified = 0")
            except:
                pass
        
        # Migration: Eski todos tablosunu yeni yapıya çevir
        try:
            cur.execute("SELECT list_id FROM todos LIMIT 1")
        except:
            # list_id sütunu yok, migration gerekli
            print("[MIGRATION] Todos tablosu güncelleniyor...")
            try:
                # Eski todos verilerini yedekle
                cur.execute("ALTER TABLE todos RENAME TO todos_old")
                
                # Yeni todos tablosunu oluştur
                cur.execute("""
                    CREATE TABLE todos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        list_id INTEGER NOT NULL DEFAULT 1,
                        created_at TEXT NOT NULL,
                        content TEXT NOT NULL,
                        completed INTEGER NOT NULL DEFAULT 0,
                        completed_at TEXT,
                        FOREIGN KEY (list_id) REFERENCES todo_lists(id) ON DELETE CASCADE
                    )
                """)
                
                # Default liste oluştur (eğer yoksa)
                cur.execute("INSERT OR IGNORE INTO todo_lists (id, name, created_at) VALUES (1, 'Genel', datetime('now'))")
                
                # Eski verileri taşı
                cur.execute("""
                    INSERT INTO todos (id, list_id, created_at, content, completed, completed_at)
                    SELECT id, 1, created_at, content, completed, completed_at FROM todos_old
                """)
                
                # Eski tabloyu sil
                cur.execute("DROP TABLE todos_old")
                
                # İndeksleri yeniden oluştur
                cur.execute("CREATE INDEX IF NOT EXISTS idx_todos_list ON todos(list_id)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_todos_created ON todos(created_at DESC)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_todos_completed ON todos(completed)")
                
                print("[MIGRATION] Todos tablosu güncellendi!")
            except Exception as e:
                print(f"[MIGRATION ERROR] {e}")
                pass

        self.conn.commit()

    # ---------- Clip items (ESKİ işlevler korunmuştur) ----------

    def add_item(
        self,
        item_type: ClipItemType,
        text: Optional[str],
        image_bytes: Optional[bytes],
        html: Optional[str],
        created_at: str,
        ocr_text: Optional[str] = None,
    ) -> Optional[sqlite3.Row]:
        # Yinelenenleri engelle
        last = self.get_last_item()
        if last and last["item_type"] == int(item_type):
            if item_type == ClipItemType.TEXT and (last["text_content"] or "") == (text or ""):
                return None
            if item_type == ClipItemType.HTML and (last["html_content"] or "") == (html or ""):
                return None
            if item_type == ClipItemType.IMAGE and last["image_blob"] == image_bytes:
                return None
        
        # OCR işlemi (resim için ve OCR aktifse)
        if item_type == ClipItemType.IMAGE and image_bytes and not ocr_text:
            if self.settings and self.settings.get("ocr_enabled", False):
                try:
                    from .ocr_manager import OCRManager
                    ocr = OCRManager(self.settings)
                    if ocr.is_available():
                        ocr_lang = self.settings.get("ocr_language", "tur+eng")
                        ocr_text = ocr.extract_text(image_bytes, lang=ocr_lang)
                        if ocr_text:
                            print(f"[STORAGE OCR] Metin çıkarıldı: {ocr_text[:50]}...")
                except Exception as e:
                    print(f"[STORAGE OCR] Hata: {e}")

        item_type, text, html, ocr_text, should_drop = self._protect_clip_item(
            item_type,
            text,
            html,
            ocr_text,
        )
        if should_drop:
            return None

        # Resimler için harici kaydetme kontrolü
        image_path = None
        if item_type == ClipItemType.IMAGE and image_bytes and self.settings:
            if self.settings.get("save_images_externally", False):
                external_path = self.settings.get("external_images_path", "")
                if external_path:
                    from pathlib import Path
                    import datetime
                    
                    folder = Path(external_path)
                    folder.mkdir(parents=True, exist_ok=True)
                    
                    # Dosya adı: tarih_saat.png
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    filename = f"img_{timestamp}.png"
                    file_path = folder / filename
                    
                    try:
                        file_path.write_bytes(image_bytes)
                        image_path = str(file_path)
                        # Harici kayıtta DB'ye blob kaydetme
                        image_bytes = None
                        print(f"[STORAGE] Resim harici olarak kaydedildi: {image_path}")
                    except Exception as e:
                        print(f"[STORAGE] Harici kayıt hatası: {e}")

        # Şifreleme (harici kayıtta resimler şifrelenmez)
        password = self._get_encryption_password()
        if password:
            if text:
                text = encrypt_aes256(text, password)
            if html:
                html = encrypt_aes256(html, password)
            if ocr_text:
                ocr_text = encrypt_aes256(ocr_text, password)

        # Eğer image_path varsa text_content alanına kaydedelim
        if image_path:
            text = image_path

        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO clip_items (created_at, item_type, text_content, image_blob, html_content, ocr_text)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (created_at, int(item_type), text, image_bytes, html, ocr_text),
        )
        self.conn.commit()
        inserted_id = cur.lastrowid
        
        # Maksimum öğe sayısı kontrolü
        self._enforce_max_items()
        
        return self.get_item(inserted_id)
    
    def _enforce_max_items(self):
        """Maksimum öğe sayısını aşan eski öğeleri sil (favoriler hariç)"""
        if not self.settings:
            return
        
        max_items = self.settings.get("max_items", 1000)
        
        cur = self.conn.cursor()
        # Favori olmayan öğe sayısını bul
        cur.execute("SELECT COUNT(*) FROM clip_items WHERE favorite = 0")
        count = cur.fetchone()[0]
        
        if count > max_items:
            # Silinecek öğe sayısı
            to_delete = count - max_items
            # En eski favori olmayan öğeleri sil
            cur.execute("""
                DELETE FROM clip_items WHERE id IN (
                    SELECT id FROM clip_items WHERE favorite = 0 
                    ORDER BY id ASC LIMIT ?
                )
            """, (to_delete,))
            self.conn.commit()
            print(f"[STORAGE] Max items aşıldı, {to_delete} eski öğe silindi")

    def get_last_item(self):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM clip_items ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        if not row:
            return None

        row_dict = dict(row)

        # Harici resim yükleme
        if row_dict.get("item_type") == int(ClipItemType.IMAGE):
            if not row_dict.get("image_blob") and row_dict.get("text_content"):
                from pathlib import Path
                try:
                    image_path = Path(row_dict["text_content"])
                    if image_path.exists():
                        row_dict["image_blob"] = image_path.read_bytes()
                        row_dict["text_content"] = None
                except Exception as e:
                    print(f"[STORAGE get_last_item] Harici resim yükleme hatası: {e}")

        return self._decrypt_clip_row(row_dict)

    def list_items(self, limit: int = 200, favorites_only: bool = False, offset: int = 0) -> List[dict]:
        cur = self.conn.cursor()
        if favorites_only:
            cur.execute(
                "SELECT * FROM clip_items WHERE favorite = 1 ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        else:
            cur.execute(
                "SELECT * FROM clip_items ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        rows = cur.fetchall()

        result = []
        for row in rows:
            row_dict = dict(row)
            
            # Harici resim yükleme
            if row_dict.get("item_type") == int(ClipItemType.IMAGE):
                if not row_dict.get("image_blob") and row_dict.get("text_content"):
                    # text_content alanında dosya yolu var
                    from pathlib import Path
                    try:
                        image_path = Path(row_dict["text_content"])
                        if image_path.exists():
                            row_dict["image_blob"] = image_path.read_bytes()
                            row_dict["text_content"] = None  # Yol görünmesin
                        else:
                            print(f"[STORAGE list_items] Resim dosyası bulunamadı: {image_path}")
                    except Exception as e:
                        print(f"[STORAGE list_items] Harici resim yükleme hatası: {e}")
            
            result.append(self._decrypt_clip_row(row_dict))

        return result

    def get_item(self, item_id: int):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM clip_items WHERE id = ?", (item_id,))
        row = cur.fetchone()
        if not row:
            return None

        row_dict = dict(row)

        # Harici resim yükleme
        if row_dict.get("item_type") == int(ClipItemType.IMAGE):
            if not row_dict.get("image_blob") and row_dict.get("text_content"):
                # text_content alanında dosya yolu var
                from pathlib import Path
                try:
                    image_path = Path(row_dict["text_content"])
                    if image_path.exists():
                        row_dict["image_blob"] = image_path.read_bytes()
                        row_dict["text_content"] = None
                        print(f"[STORAGE] Harici resim yüklendi: {image_path}")
                    else:
                        print(f"[STORAGE] Harici resim dosyası bulunamadı: {image_path}")
                except Exception as e:
                    print(f"[STORAGE] Harici resim yükleme hatası: {e}")

        return self._decrypt_clip_row(row_dict)

    def search_items(
        self, 
        query: str = "", 
        item_types: Optional[List[ClipItemType]] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        fuzzy_threshold: int = 60,
        limit: int = 100
    ) -> List[dict]:
        """
        Gelişmiş arama fonksiyonu
        - query: Aranacak metin (fuzzy search destekli)
        - item_types: [ClipItemType.TEXT, ClipItemType.IMAGE] gibi filtre
        - date_from: "2025-01-01" formatında başlangıç tarihi
        - date_to: "2025-12-31" formatında bitiş tarihi
        - fuzzy_threshold: 0-100 arası benzerlik skoru (60 = %60 benzer)
        - limit: Maksimum sonuç sayısı
        """
        cur = self.conn.cursor()
        
        # SQL query oluştur
        sql = "SELECT * FROM clip_items WHERE 1=1"
        params = []
        
        # Tip filtresi
        if item_types:
            placeholders = ",".join("?" * len(item_types))
            sql += f" AND item_type IN ({placeholders})"
            params.extend([int(t) for t in item_types])
        
        # Tarih filtresi
        if date_from:
            sql += " AND created_at >= ?"
            params.append(date_from)
        if date_to:
            sql += " AND created_at <= ?"
            params.append(date_to)
        
        sql += " ORDER BY id DESC"
        
        cur.execute(sql, params)
        rows = cur.fetchall()
        normalized_query = _normalize_search_text(query)
        
        result = []
        for row in rows:
            row_dict = dict(row)
            
            # Harici resim yükleme
            if row_dict.get("item_type") == int(ClipItemType.IMAGE):
                if not row_dict.get("image_blob") and row_dict.get("text_content"):
                    try:
                        image_path = Path(row_dict["text_content"])
                        if image_path.exists():
                            row_dict["image_blob"] = image_path.read_bytes()
                            row_dict["text_content"] = None
                    except Exception:
                        pass
            
            row_dict = self._decrypt_clip_row(row_dict)
            
            # Query ile fuzzy match kontrolü
            if normalized_query:
                text_parts = []
                if row_dict.get("text_content"):
                    text_parts.append(_normalize_search_text(row_dict["text_content"]))
                if row_dict.get("html_content"):
                    text_parts.append(_strip_html_tags(row_dict["html_content"]))
                if row_dict.get("ocr_text"):
                    text_parts.append(_normalize_search_text(row_dict["ocr_text"]))
                
                searchable_text = " ".join(part for part in text_parts if part).strip()
                if searchable_text:
                    score = _score_search_match(normalized_query, searchable_text)
                    if score >= fuzzy_threshold:
                        row_dict["_search_score"] = score
                        result.append(row_dict)
            else:
                # Query boşsa hepsini ekle
                row_dict["_search_score"] = 100
                result.append(row_dict)
        
        # Skora göre sırala
        result.sort(key=lambda x: (x.get("_search_score", 0), x.get("id", 0)), reverse=True)
        
        return result[:limit]

    def delete_item(self, item_id: int):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM clip_items WHERE id = ?", (item_id,))
        self.conn.commit()

    def clear_all(self):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM clip_items")
        self.conn.commit()

    def set_favorite(self, item_id: int, fav: bool):
        cur = self.conn.cursor()
        cur.execute("UPDATE clip_items SET favorite = ? WHERE id = ?", (1 if fav else 0, item_id))
        self.conn.commit()

    def toggle_favorite(self, item_id: int) -> bool:
        row = self.get_item(item_id)
        new_val = not bool(row["favorite"])
        self.set_favorite(item_id, new_val)
        return new_val

    # ---------- Notes (YENİ) ----------

    def add_note(self, content: str, created_at: str):
        if self.settings and self.settings.get("encrypt_data", False):
            password = self.settings.get("encryption_key", None)
            if password and content:
                content = encrypt_aes256(content, password)

        cur = self.conn.cursor()
        cur.execute("INSERT INTO notes (created_at, content) VALUES (?, ?)", (created_at, content))
        self.conn.commit()
        inserted_id = cur.lastrowid
        return self.get_note(inserted_id)

    def list_notes(self, limit: int = 200, offset: int = 0) -> List[dict]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM notes ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))
        rows = cur.fetchall()

        if not self.settings or not self.settings.get("encrypt_data", False):
            return [dict(row) for row in rows]

        password = self.settings.get("encryption_key", None)
        if not password:
            return [dict(row) for row in rows]

        result = []
        for row in rows:
            row_dict = dict(row)
            if row_dict.get("content"):
                try:
                    row_dict["content"] = decrypt_aes256(row_dict["content"], password)
                except Exception:
                    row_dict["content"] = "[Şifreli veri çözülemedi]"
            result.append(row_dict)

        return result

    def get_note(self, note_id: int):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
        row = cur.fetchone()
        if not row:
            return None

        row_dict = dict(row)

        if self.settings and self.settings.get("encrypt_data", False):
            password = self.settings.get("encryption_key", None)
            if password and row_dict.get("content"):
                try:
                    row_dict["content"] = decrypt_aes256(row_dict["content"], password)
                except Exception:
                    row_dict["content"] = "[Şifreli veri çözülemedi]"

        return row_dict

    def update_note(self, note_id: int, content: str):
        if self.settings and self.settings.get("encrypt_data", False):
            password = self.settings.get("encryption_key", None)
            if password and content:
                content = encrypt_aes256(content, password)

        cur = self.conn.cursor()
        cur.execute("UPDATE notes SET content = ? WHERE id = ?", (content, note_id))
        self.conn.commit()

    def delete_note(self, note_id: int):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        self.conn.commit()

    def clear_notes(self):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM notes")
        self.conn.commit()

    # ---------- Reminders (YENİ - EKSİK OLAN METODLAR) ----------

    def add_reminder(self, title: str, description: str, reminder_time: str, repeat_type: str = 'none', created_at: str = None):
        """Yeni hatırlatıcı ekle"""
        if created_at is None:
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Şifreleme
        if self.settings and self.settings.get("encrypt_data", False):
            password = self.settings.get("encryption_key", None)
            if password:
                if title:
                    title = encrypt_aes256(title, password)
                if description:
                    description = encrypt_aes256(description, password)

        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO reminders (created_at, title, description, reminder_time, repeat_type)
            VALUES (?, ?, ?, ?, ?)
            """,
            (created_at, title, description, reminder_time, repeat_type)
        )
        self.conn.commit()
        inserted_id = cur.lastrowid
        return self.get_reminder(inserted_id)

    def list_reminders(self, limit: int = 200, offset: int = 0, active_only: bool = False) -> List[dict]:
        """Hatırlatıcıları listele"""
        cur = self.conn.cursor()
        
        if active_only:
            cur.execute(
                "SELECT * FROM reminders WHERE is_active = 1 ORDER BY reminder_time ASC LIMIT ? OFFSET ?",
                (limit, offset)
            )
        else:
            cur.execute(
                "SELECT * FROM reminders ORDER BY reminder_time ASC LIMIT ? OFFSET ?",
                (limit, offset)
            )
        
        rows = cur.fetchall()

        if not self.settings or not self.settings.get("encrypt_data", False):
            return [dict(row) for row in rows]

        password = self.settings.get("encryption_key", None)
        if not password:
            return [dict(row) for row in rows]

        result = []
        for row in rows:
            row_dict = dict(row)
            if row_dict.get("title"):
                try:
                    row_dict["title"] = decrypt_aes256(row_dict["title"], password)
                except Exception:
                    row_dict["title"] = "[Şifreli veri çözülemedi]"
            if row_dict.get("description"):
                try:
                    row_dict["description"] = decrypt_aes256(row_dict["description"], password)
                except Exception:
                    row_dict["description"] = "[Şifreli veri çözülemedi]"
            result.append(row_dict)

        return result

    def get_reminder(self, reminder_id: int):
        """Tek bir hatırlatıcıyı getir"""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,))
        row = cur.fetchone()
        if not row:
            return None

        row_dict = dict(row)

        if self.settings and self.settings.get("encrypt_data", False):
            password = self.settings.get("encryption_key", None)
            if password:
                if row_dict.get("title"):
                    try:
                        row_dict["title"] = decrypt_aes256(row_dict["title"], password)
                    except Exception:
                        row_dict["title"] = "[Şifreli veri çözülemedi]"
                if row_dict.get("description"):
                    try:
                        row_dict["description"] = decrypt_aes256(row_dict["description"], password)
                    except Exception:
                        row_dict["description"] = "[Şifreli veri çözülemedi]"

        return row_dict

    def update_reminder(self, reminder_id: int, title: str = None, description: str = None, 
                       reminder_time: str = None, repeat_type: str = None, is_active: bool = None):
        """Hatırlatıcıyı güncelle"""
        cur = self.conn.cursor()
        
        # Önce mevcut veriyi al
        current = self.get_reminder(reminder_id)
        if not current:
            return
        
        # Şifreleme
        if self.settings and self.settings.get("encrypt_data", False):
            password = self.settings.get("encryption_key", None)
            if password:
                if title:
                    title = encrypt_aes256(title, password)
                if description:
                    description = encrypt_aes256(description, password)
        
        # Güncellenecek alanları belirle
        updates = []
        params = []
        
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if reminder_time is not None:
            updates.append("reminder_time = ?")
            params.append(reminder_time)
        if repeat_type is not None:
            updates.append("repeat_type = ?")
            params.append(repeat_type)
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if is_active else 0)
        
        if updates:
            params.append(reminder_id)
            query = f"UPDATE reminders SET {', '.join(updates)} WHERE id = ?"
            cur.execute(query, params)
            self.conn.commit()

    def delete_reminder(self, reminder_id: int):
        """Hatırlatıcıyı sil"""
        cur = self.conn.cursor()
        cur.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        self.conn.commit()

    def clear_reminders(self):
        """Tüm hatırlatıcıları sil"""
        cur = self.conn.cursor()
        cur.execute("DELETE FROM reminders")
        self.conn.commit()

    def mark_reminder_triggered(self, reminder_id: int):
        """Hatırlatıcının tetiklendiği zamanı kaydet"""
        now = datetime.now().isoformat()
        cur = self.conn.cursor()
        cur.execute("UPDATE reminders SET last_triggered = ? WHERE id = ?", (now, reminder_id))
        self.conn.commit()

    def auto_delete_items(self):
        if not self.settings or not self.settings.get("auto_delete_enabled", False):
            return
        days = int(self.settings.get("auto_delete_days", 7))
        cutoff = datetime.now() - timedelta(days=days)
        keep_fav = self.settings.get("auto_delete_keep_fav", True)
        cur = self.conn.cursor()
        if keep_fav:
            cur.execute("""
                DELETE FROM clip_items
                WHERE favorite=0 AND created_at < ?
            """, (cutoff.strftime("%Y-%m-%d %H:%M:%S"),))
        else:
            cur.execute("""
                DELETE FROM clip_items
                WHERE created_at < ?
            """, (cutoff.strftime("%Y-%m-%d %H:%M:%S"),))
        self.conn.commit()

    def set_reminder_active(self, reminder_id: int, is_active: bool):
        """Hatırlatıcının aktiflik durumunu değiştir"""
        cur = self.conn.cursor()
        cur.execute("UPDATE reminders SET is_active = ? WHERE id = ?", (1 if is_active else 0, reminder_id))
        self.conn.commit()
    
    def update_reminder_time(self, reminder_id: int, new_time: str):
        """Hatırlatıcının zamanını güncelle ve last_triggered'ı sıfırla"""
        cur = self.conn.cursor()
        cur.execute("UPDATE reminders SET reminder_time = ?, last_triggered = NULL WHERE id = ?", (new_time, reminder_id))
        self.conn.commit()
    
    # ---------- Snippets (Kod Parçacıkları) ----------
    
    def add_snippet(self, title: str, code: str, language: str, tags: str = "", created_at: str = None) -> int:
        """Yeni snippet ekle"""
        if created_at is None:
            created_at = datetime.now().isoformat()
        
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO snippets (created_at, title, code, language, tags, favorite)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (created_at, title, code, language, tags)
        )
        self.conn.commit()
        return cur.lastrowid
    
    def list_snippets(self, limit: int = 100, offset: int = 0, favorites_only: bool = False, language: str = None) -> List[dict]:
        """Snippet listesi"""
        cur = self.conn.cursor()
        
        query = "SELECT * FROM snippets WHERE 1=1"
        params = []
        
        if favorites_only:
            query += " AND favorite = 1"
        
        if language:
            query += " AND language = ?"
            params.append(language)
        
        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cur.execute(query, params)
        rows = cur.fetchall()
        
        return [dict(row) for row in rows]
    
    def get_snippet(self, snippet_id: int) -> Optional[dict]:
        """Snippet detayı"""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM snippets WHERE id = ?", (snippet_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    
    def update_snippet(self, snippet_id: int, title: str = None, code: str = None, language: str = None, tags: str = None):
        """Snippet güncelle"""
        cur = self.conn.cursor()
        updates = []
        params = []
        
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if code is not None:
            updates.append("code = ?")
            params.append(code)
        if language is not None:
            updates.append("language = ?")
            params.append(language)
        if tags is not None:
            updates.append("tags = ?")
            params.append(tags)
        
        if updates:
            params.append(snippet_id)
            query = f"UPDATE snippets SET {', '.join(updates)} WHERE id = ?"
            cur.execute(query, params)
            self.conn.commit()
    
    def delete_snippet(self, snippet_id: int):
        """Snippet sil"""
        cur = self.conn.cursor()
        cur.execute("DELETE FROM snippets WHERE id = ?", (snippet_id,))
        self.conn.commit()
    
    def toggle_snippet_favorite(self, snippet_id: int):
        """Snippet favori durumunu değiştir"""
        cur = self.conn.cursor()
        cur.execute("SELECT favorite FROM snippets WHERE id = ?", (snippet_id,))
        row = cur.fetchone()
        if row:
            new_fav = 0 if row["favorite"] else 1
            cur.execute("UPDATE snippets SET favorite = ? WHERE id = ?", (new_fav, snippet_id))
            self.conn.commit()
            return new_fav
        return 0
    
    def search_snippets(self, query: str, language: str = None, limit: int = 100) -> List[dict]:
        """Snippet arama"""
        cur = self.conn.cursor()
        
        sql = "SELECT * FROM snippets WHERE (title LIKE ? OR code LIKE ? OR tags LIKE ?)"
        params = [f"%{query}%", f"%{query}%", f"%{query}%"]
        
        if language:
            sql += " AND language = ?"
            params.append(language)
        
        sql += " ORDER BY favorite DESC, id DESC LIMIT ?"
        params.append(limit)
    
    # ==================== MULTI-FILE SNIPPET İŞLEMLERİ ====================
    
    def add_multi_file_snippet(self, title: str, files: List[dict], tags: str = "", created_at: str = None) -> int:
        """Multi-file snippet ekle
        files: [{"filename": "index.html", "content": "...", "language": "html"}, ...]
        """
        if created_at is None:
            created_at = datetime.now().isoformat()
        
        cur = self.conn.cursor()
        # Ana snippet kaydı
        cur.execute(
            """
            INSERT INTO snippets (created_at, title, code, language, tags, favorite, is_multi_file)
            VALUES (?, ?, ?, ?, ?, 0, 1)
            """,
            (created_at, title, "", "multi", tags)
        )
        snippet_id = cur.lastrowid
        
        # Dosyaları ekle
        for i, file_data in enumerate(files):
            cur.execute(
                """
                INSERT INTO snippet_files (snippet_id, filename, content, language, order_index)
                VALUES (?, ?, ?, ?, ?)
                """,
                (snippet_id, file_data["filename"], file_data["content"], file_data["language"], i)
            )
        
        self.conn.commit()
        return snippet_id
    
    def get_snippet_files(self, snippet_id: int) -> List[dict]:
        """Snippet'e ait dosyaları getir"""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM snippet_files WHERE snippet_id = ? ORDER BY order_index ASC",
            (snippet_id,)
        )
        rows = cur.fetchall()
        return [dict(row) for row in rows]
    
    def update_multi_file_snippet(self, snippet_id: int, title: str = None, files: List[dict] = None, tags: str = None):
        """Multi-file snippet güncelle"""
        cur = self.conn.cursor()
        
        # Ana snippet güncelle
        updates = []
        params = []
        
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if tags is not None:
            updates.append("tags = ?")
            params.append(tags)
        
        if updates:
            params.append(snippet_id)
            query = f"UPDATE snippets SET {', '.join(updates)} WHERE id = ?"
            cur.execute(query, params)
        
        # Dosyaları güncelle
        if files is not None:
            # Eski dosyaları sil
            cur.execute("DELETE FROM snippet_files WHERE snippet_id = ?", (snippet_id,))
            
            # Yeni dosyaları ekle
            for i, file_data in enumerate(files):
                cur.execute(
                    """
                    INSERT INTO snippet_files (snippet_id, filename, content, language, order_index)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (snippet_id, file_data["filename"], file_data["content"], file_data["language"], i)
                )
        
        self.conn.commit()
        
        cur.execute(sql, params)
        rows = cur.fetchall()
        
        return [dict(row) for row in rows]
    
    # ==================== TODO İŞLEMLERİ ====================
    # ESKİ TODO APİ KALDIRILDI - list_id parametresi gerekli (satır 1219)
    
    def list_todos(self, completed: bool = None) -> List[dict]:
        """Todo'ları listele"""
        cur = self.conn.cursor()
        
        if completed is None:
            cur.execute("SELECT * FROM todos ORDER BY completed ASC, order_index ASC, id DESC")
        else:
            cur.execute(
                "SELECT * FROM todos WHERE completed = ? ORDER BY order_index ASC, id DESC",
                (1 if completed else 0,)
            )
        
        rows = cur.fetchall()
        return [dict(row) for row in rows]
    
    def get_todo(self, todo_id: int) -> dict | None:
        """Tek bir todo getir"""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM todos WHERE id = ?", (todo_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    
    def update_todo(self, todo_id: int, content: str = None, completed: bool = None, order_index: int = None) -> None:
        """Todo güncelle"""
        from datetime import datetime
        cur = self.conn.cursor()
        
        updates = []
        params = []
        
        if content is not None:
            updates.append("content = ?")
            params.append(content)
        
        if completed is not None:
            updates.append("completed = ?")
            params.append(1 if completed else 0)
            
            if completed:
                updates.append("completed_at = ?")
                params.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            else:
                updates.append("completed_at = NULL")
        
        if order_index is not None:
            updates.append("order_index = ?")
            params.append(order_index)
        
        if updates:
            params.append(todo_id)
            sql = f"UPDATE todos SET {', '.join(updates)} WHERE id = ?"
            cur.execute(sql, params)
            self.conn.commit()
    
    def delete_todo(self, todo_id: int) -> None:
        """Todo sil"""
        cur = self.conn.cursor()
        cur.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        self.conn.commit()
    
    def clear_completed_todos(self) -> None:
        """Tamamlanan todo'ları sil"""
        cur = self.conn.cursor()
        cur.execute("DELETE FROM todos WHERE completed = 1")
        self.conn.commit()
    
    # ==================== ÇİZİM İŞLEMLERİ ====================
    
    def add_drawing(self, image_data: str, title: str = None) -> int:
        """Yeni çizim ekle (image_data base64 string)"""
        from datetime import datetime
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO drawings (created_at, image_data, title, favorite) VALUES (?, ?, ?, 0)",
            (created_at, image_data, title or "Çizim")
        )
        self.conn.commit()
        return cur.lastrowid
    
    def list_drawings(self, limit: int = 100) -> List[dict]:
        """Çizimleri listele (image_data dahil)"""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT id, created_at, title, favorite, image_data FROM drawings ORDER BY favorite DESC, id DESC LIMIT ?",
            (limit,)
        )
        rows = cur.fetchall()
        return [dict(row) for row in rows]
    
    def get_drawing(self, drawing_id: int) -> dict | None:
        """Tek bir çizim getir (image_data ile)"""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM drawings WHERE id = ?", (drawing_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    
    def update_drawing(self, drawing_id: int, image_data: str = None, title: str = None, favorite: bool = None) -> None:
        """Çizim güncelle (image_data base64 string)"""
        cur = self.conn.cursor()
        
        updates = []
        params = []
        
        if image_data is not None:
            updates.append("image_data = ?")
            params.append(image_data)
        
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        
        if favorite is not None:
            updates.append("favorite = ?")
            params.append(1 if favorite else 0)
        
        if updates:
            params.append(drawing_id)
            sql = f"UPDATE drawings SET {', '.join(updates)} WHERE id = ?"
            cur.execute(sql, params)
            self.conn.commit()
    
    def delete_drawing(self, drawing_id: int) -> None:
        """Çizim sil"""
        cur = self.conn.cursor()
        cur.execute("DELETE FROM drawings WHERE id = ?", (drawing_id,))
        self.conn.commit()
    
    def toggle_drawing_favorite(self, drawing_id: int) -> None:
        """Çizim favori durumunu değiştir"""
        cur = self.conn.cursor()
        cur.execute("UPDATE drawings SET favorite = NOT favorite WHERE id = ?", (drawing_id,))
        self.conn.commit()
    
    def get_drawing_by_id(self, drawing_id: int) -> dict | None:
        """Çizim getir (ID ile)"""
        cur = self.conn.cursor()
        cur.execute("SELECT id, image_data as image, title, created_at, favorite FROM drawings WHERE id = ?", (drawing_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    
    # Todo metodları
    def get_todo_list_by_id(self, list_id: int) -> dict | None:
        """Todo listesi getir"""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM todo_lists WHERE id = ?", (list_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    
    def get_todos_by_list(self, list_id: int) -> list:
        """Listeye ait todoları getir"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, list_id, content, completed, created_at
            FROM todos
            WHERE list_id = ?
            ORDER BY created_at ASC
        """, (list_id,))
        return [dict(row) for row in cur.fetchall()]
    
    def add_todo(self, list_id: int, content: str) -> int:
        """Yeni todo ekle"""
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO todos (list_id, content, completed, created_at)
            VALUES (?, ?, 0, datetime('now'))
        """, (list_id, content))
        self.conn.commit()
        return cur.lastrowid
    
    def update_todo_status(self, todo_id: int, completed: bool) -> None:
        """Todo durumunu güncelle"""
        cur = self.conn.cursor()
        cur.execute("UPDATE todos SET completed = ? WHERE id = ?", (1 if completed else 0, todo_id))
        self.conn.commit()
    
    def toggle_todo(self, todo_id: int) -> None:
        """Todo durumunu tersine çevir"""
        cur = self.conn.cursor()
        cur.execute("SELECT completed FROM todos WHERE id = ?", (todo_id,))
        row = cur.fetchone()
        if row:
            new_status = 0 if row[0] else 1
            cur.execute("UPDATE todos SET completed = ? WHERE id = ?", (new_status, todo_id))
            self.conn.commit()
    
    def update_todo_content(self, todo_id: int, content: str) -> None:
        """Todo içeriğini güncelle"""
        cur = self.conn.cursor()
        cur.execute("UPDATE todos SET content = ? WHERE id = ?", (content, todo_id))
        self.conn.commit()
    
    def delete_todo(self, todo_id: int) -> None:
        """Todo sil"""
        cur = self.conn.cursor()
        cur.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        self.conn.commit()
    
    def update_todo_list_name(self, list_id: int, name: str) -> None:
        """Todo liste adını güncelle"""
        cur = self.conn.cursor()
        cur.execute("UPDATE todo_lists SET name = ? WHERE id = ?", (name, list_id))
        self.conn.commit()
    
    def delete_todo_list(self, list_id: int) -> None:
        """Todo listesi sil (cascade)"""
        cur = self.conn.cursor()
        cur.execute("DELETE FROM todos WHERE list_id = ?", (list_id,))
        cur.execute("DELETE FROM todo_lists WHERE id = ?", (list_id,))
        self.conn.commit()
    
    def list_todo_lists(self, limit: int = 100) -> list:
        """Tüm todo listelerini getir"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, name, created_at
            FROM todo_lists
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cur.fetchall()]
    
    def create_todo_list(self, name: str) -> int:
        """Yeni todo listesi oluştur"""
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO todo_lists (name, created_at)
            VALUES (?, datetime('now'))
        """, (name,))
        self.conn.commit()
        return cur.lastrowid
