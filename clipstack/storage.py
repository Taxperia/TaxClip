import sqlite3
from enum import IntEnum
from pathlib import Path
from typing import List, Optional
from clipstack.utils_crypto import encrypt_aes256, decrypt_aes256
from datetime import datetime, timedelta


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
                favorite INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_clip_items_created ON clip_items(created_at DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_clip_items_fav ON clip_items(favorite)")

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

        self.conn.commit()

    # ---------- Clip items (ESKİ işlevler korunmuştur) ----------

    def add_item(
        self,
        item_type: ClipItemType,
        text: Optional[str],
        image_bytes: Optional[bytes],
        html: Optional[str],
        created_at: str,
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

        # Şifreleme
        if self.settings and self.settings.get("encrypt_data", False):
            password = self.settings.get("encryption_key", None)
            if password:
                if text:
                    text = encrypt_aes256(text, password)
                if html:
                    html = encrypt_aes256(html, password)

        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO clip_items (created_at, item_type, text_content, image_blob, html_content)
            VALUES (?, ?, ?, ?, ?)
            """,
            (created_at, int(item_type), text, image_bytes, html),
        )
        self.conn.commit()
        inserted_id = cur.lastrowid
        return self.get_item(inserted_id)

    def get_last_item(self):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM clip_items ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        if not row:
            return None

        row_dict = dict(row)

        if self.settings and self.settings.get("encrypt_data", False):
            password = self.settings.get("encryption_key", None)
            if password:
                if row_dict.get("text_content"):
                    try:
                        row_dict["text_content"] = decrypt_aes256(row_dict["text_content"], password)
                    except Exception:
                        row_dict["text_content"] = "[Şifreli veri çözülemedi]"
                if row_dict.get("html_content"):
                    try:
                        row_dict["html_content"] = decrypt_aes256(row_dict["html_content"], password)
                    except Exception:
                        row_dict["html_content"] = "[Şifreli veri çözülemedi]"

        return row_dict

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

        if not self.settings or not self.settings.get("encrypt_data", False):
            return [dict(row) for row in rows]

        password = self.settings.get("encryption_key", None)
        if not password:
            return [dict(row) for row in rows]

        result = []
        for row in rows:
            row_dict = dict(row)
            if row_dict.get("text_content"):
                try:
                    row_dict["text_content"] = decrypt_aes256(row_dict["text_content"], password)
                except Exception:
                    row_dict["text_content"] = "[Şifreli veri çözülemedi]"
            if row_dict.get("html_content"):
                try:
                    row_dict["html_content"] = decrypt_aes256(row_dict["html_content"], password)
                except Exception:
                    row_dict["html_content"] = "[Şifreli veri çözülemedi]"
            result.append(row_dict)

        return result

    def get_item(self, item_id: int):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM clip_items WHERE id = ?", (item_id,))
        row = cur.fetchone()
        if not row:
            return None

        row_dict = dict(row)

        if self.settings and self.settings.get("encrypt_data", False):
            password = self.settings.get("encryption_key", None)
            if password:
                if row_dict.get("text_content"):
                    try:
                        row_dict["text_content"] = decrypt_aes256(row_dict["text_content"], password)
                    except Exception:
                        row_dict["text_content"] = "[Şifreli veri çözülemedi]"
                if row_dict.get("html_content"):
                    try:
                        row_dict["html_content"] = decrypt_aes256(row_dict["html_content"], password)
                    except Exception:
                        row_dict["html_content"] = "[Şifreli veri çözülemedi]"

        return row_dict

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

# Bu kodlar storage.py dosyasının sonuna eklenecek

    def _init_reminders_table(self):
        """Hatırlatmalar tablosunu oluştur (init_db içinde çağrılacak)"""
        cur = self.conn.cursor()
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
                notified INTEGER DEFAULT 0
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_reminders_time ON reminders(reminder_time)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_reminders_active ON reminders(is_active)")
        self.conn.commit()

    def add_reminder(self, title: str, description: str, reminder_time: str, 
                     repeat_type: str = "none", created_at: str = None):
        """Yeni hatırlatma ekle"""
        if not created_at:
            from datetime import datetime
            created_at = datetime.now().isoformat()
        
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
            INSERT INTO reminders (created_at, title, description, reminder_time, repeat_type, is_active, notified)
            VALUES (?, ?, ?, ?, ?, 1, 0)
            """,
            (created_at, title, description, reminder_time, repeat_type)
        )
        self.conn.commit()
        return self.get_reminder(cur.lastrowid)

    def list_reminders(self, limit: int = 200, offset: int = 0, active_only: bool = False):
        """Hatırlatmaları listele"""
        cur = self.conn.cursor()
        if active_only:
            cur.execute(
                "SELECT * FROM reminders WHERE is_active = 1 ORDER BY reminder_time ASC LIMIT ? OFFSET ?",
                (limit, offset)
            )
        else:
            cur.execute(
                "SELECT * FROM reminders ORDER BY reminder_time DESC LIMIT ? OFFSET ?",
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
        """Tek bir hatırlatmayı getir"""
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

    def update_reminder(self, reminder_id: int, title: str, description: str, 
                       reminder_time: str, repeat_type: str):
        """Hatırlatmayı güncelle"""
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
            UPDATE reminders 
            SET title = ?, description = ?, reminder_time = ?, repeat_type = ?
            WHERE id = ?
            """,
            (title, description, reminder_time, repeat_type, reminder_id)
        )
        self.conn.commit()

    def update_reminder_time(self, reminder_id: int, reminder_time: str):
        """Sadece hatırlatma zamanını güncelle (tekrarlama için)"""
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE reminders SET reminder_time = ?, notified = 0 WHERE id = ?",
            (reminder_time, reminder_id)
        )
        self.conn.commit()

    def set_reminder_active(self, reminder_id: int, is_active: bool):
        """Hatırlatmayı aktif/pasif yap"""
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE reminders SET is_active = ? WHERE id = ?",
            (1 if is_active else 0, reminder_id)
        )
        self.conn.commit()

    def delete_reminder(self, reminder_id: int):
        """Hatırlatmayı sil"""
        cur = self.conn.cursor()
        cur.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        self.conn.commit()

    def clear_reminders(self):
        """Tüm hatırlatmaları sil"""
        cur = self.conn.cursor()
        cur.execute("DELETE FROM reminders")
        self.conn.commit()