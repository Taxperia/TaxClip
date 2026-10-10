import tempfile
import unittest
from pathlib import Path

from clipstack.storage import (
    ClipItemType,
    Storage,
    _normalize_search_text,
    _score_search_match,
)


def _score(query: str, text: str) -> int:
    return _score_search_match(
        _normalize_search_text(query),
        _normalize_search_text(text),
    )


class SearchRelevanceTests(unittest.TestCase):
    def test_exact_prefix_and_typo_matches_remain_relevant(self):
        self.assertEqual(_score("uygulama", "uygulama ayarlari"), 100)
        self.assertEqual(_score("uygul", "uygulama ayarlari"), 98)
        self.assertGreaterEqual(_score("uygulma", "uygulama ayarlari"), 88)

    def test_short_candidate_cannot_match_a_long_query(self):
        self.assertLess(_score("application", "app settings"), 88)
        self.assertLess(_score("javascript", "java examples"), 88)
        self.assertLess(_score("screenshot", "screen capture"), 88)

    def test_every_word_in_query_must_match(self):
        self.assertLess(_score("merhaba dunya", "merhaba"), 88)
        self.assertGreaterEqual(_score("merhaba dunya", "dunya merhaba"), 98)

    def test_turkish_characters_are_normalized(self):
        self.assertEqual(_score("şifre ışık", "SIFRE ISIK ayarları"), 100)

    def test_source_application_is_not_treated_as_clip_content(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = Storage(Path(temp_dir) / "search.db")
            try:
                source_only = storage.add_item(
                    ClipItemType.TEXT,
                    "toplantı notları",
                    None,
                    None,
                    "2026-10-10 10:00:00",
                    source_app="discord.exe",
                )
                content_match = storage.add_item(
                    ClipItemType.TEXT,
                    "Discord kanalına bak",
                    None,
                    None,
                    "2026-10-10 10:01:00",
                    source_app="code.exe",
                )

                results = storage.search_items("discord", fuzzy_threshold=88)

                self.assertEqual(
                    [row["id"] for row in results],
                    [content_match["id"]],
                )
                self.assertNotEqual(source_only["id"], content_match["id"])
            finally:
                storage.conn.close()

    def test_internal_image_path_is_not_treated_as_image_content(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = Storage(Path(temp_dir) / "search.db")
            try:
                image_path = Path(temp_dir) / "Applications Series" / "screenshots" / "capture.png"
                image_path.parent.mkdir(parents=True)
                image_path.write_bytes(b"image-placeholder")
                storage.add_item(
                    ClipItemType.IMAGE,
                    str(image_path),
                    None,
                    None,
                    "2026-10-10 10:00:00",
                )

                self.assertEqual(
                    storage.search_items("application", fuzzy_threshold=88),
                    [],
                )
            finally:
                storage.conn.close()

    def test_search_returns_requested_page_and_total_match_count(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = Storage(Path(temp_dir) / "search.db")
            try:
                for index in range(20):
                    storage.add_item(
                        ClipItemType.TEXT,
                        f"needle item {index}",
                        None,
                        None,
                        f"2026-10-10 10:{index:02d}:00",
                    )

                first_page, first_total = storage.search_items(
                    "needle", fuzzy_threshold=88, limit=9, offset=0, include_total=True
                )
                second_page, second_total = storage.search_items(
                    "needle", fuzzy_threshold=88, limit=9, offset=9, include_total=True
                )

                self.assertEqual(first_total, 20)
                self.assertEqual(second_total, 20)
                self.assertEqual(len(first_page), 9)
                self.assertEqual(len(second_page), 9)
                self.assertTrue(
                    {row["id"] for row in first_page}.isdisjoint(
                        {row["id"] for row in second_page}
                    )
                )
            finally:
                storage.conn.close()


if __name__ == "__main__":
    unittest.main()
