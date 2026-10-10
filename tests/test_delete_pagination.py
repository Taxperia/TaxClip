import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from clipstack.ui.main_window import HistoryWindow


class DeletePaginationTests(unittest.TestCase):
    def test_successful_delete_reloads_current_page(self):
        host = SimpleNamespace(
            settings={"confirm_delete": False},
            storage=SimpleNamespace(delete_item=Mock()),
            search=SimpleNamespace(text=lambda: ""),
            filter_panel=SimpleNamespace(isVisible=lambda: False),
            _schedule_page_reload=Mock(),
            _perform_search=Mock(),
            _refresh_chip_meta=Mock(),
        )

        HistoryWindow.on_delete_requested(host, 42)

        host.storage.delete_item.assert_called_once_with(42)
        host._schedule_page_reload.assert_called_once_with()
        host._perform_search.assert_not_called()

    def test_page_index_moves_back_when_last_page_disappears(self):
        host = SimpleNamespace(_page_index=2)

        offset = HistoryWindow._page_offset_for_total(host, 18)

        self.assertEqual(host._page_index, 1)
        self.assertEqual(offset, 9)

    def test_next_page_repeats_active_search_instead_of_loading_history(self):
        host = SimpleNamespace(
            _page_index=0,
            _page_size_dynamic=9,
            _total_for_page=20,
            search=SimpleNamespace(text=lambda: "needle"),
            filter_panel=SimpleNamespace(isVisible=lambda: False),
            _perform_search=Mock(),
            _schedule_page_reload=Mock(),
        )

        HistoryWindow._goto_page(host, 1)

        self.assertEqual(host._page_index, 1)
        host._perform_search.assert_called_once_with()
        host._schedule_page_reload.assert_not_called()


if __name__ == "__main__":
    unittest.main()
