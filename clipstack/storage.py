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
    def __init__(self, path: Path):
        self.path = Path(path)
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
        if self.settings.get("encrypt_data", False):
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

    def get_last_item(self) -> Optional[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM clip_items ORDER BY id DESC LIMIT 1")
        return cur.fetchone()

    def list_items(self, limit: int = 200, favorites_only: bool = False, offset: int = 0) -> List[sqlite3.Row]:
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
        return cur.fetchall()

def get_item(self, item_id: int) -> sqlite3.Row:
    cur = self.conn.cursor()
    cur.execute("SELECT * FROM clip_items WHERE id = ?", (item_id,))
    row = cur.fetchone()
    if row and self.settings.get("encrypt_data", False):
        password = self.settings.get("encryption_key", None)
        if password:
            if row["text_content"]:
                try:
                    row["text_content"] = decrypt_aes256(row["text_content"], password)
                except Exception:
                    row["text_content"] = "[Şifreli veri çözülemedi]"
            if row["html_content"]:
                try:
                    row["html_content"] = decrypt_aes256(row["html_content"], password)
                except Exception:
                    row["html_content"] = "[Şifreli veri çözülemedi]"
    return row

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

    def add_note(self, content: str, created_at: str) -> Optional[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute("INSERT INTO notes (created_at, content) VALUES (?, ?)", (created_at, content))
        self.conn.commit()
        inserted_id = cur.lastrowid
        return self.get_note(inserted_id)

    def list_notes(self, limit: int = 200, offset: int = 0) -> List[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM notes ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))
        return cur.fetchall()

    def get_note(self, note_id: int) -> Optional[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
        return cur.fetchone()

    def update_note(self, note_id: int, content: str):
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
        if not self.settings.get("auto_delete_enabled", False):
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