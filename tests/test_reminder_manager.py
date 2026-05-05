import unittest
from datetime import datetime, timedelta

from PySide6.QtCore import QCoreApplication

from clipstack.reminder_manager import ReminderManager


class FakeSettings:
    def get(self, key, default=None):
        return default


class FakeStorage:
    def __init__(self, reminders):
        self.reminders = {reminder["id"]: dict(reminder) for reminder in reminders}

    def list_reminders(self, active_only=False):
        reminders = list(self.reminders.values())
        if active_only:
            reminders = [reminder for reminder in reminders if reminder.get("is_active", 1)]
        return [dict(reminder) for reminder in reminders]

    def get_reminder(self, reminder_id):
        reminder = self.reminders.get(reminder_id)
        return dict(reminder) if reminder else None

    def mark_reminder_triggered(self, reminder_id):
        self.reminders[reminder_id]["last_triggered"] = datetime.now().isoformat()

    def update_reminder_time(self, reminder_id, new_time):
        self.reminders[reminder_id]["reminder_time"] = new_time
        self.reminders[reminder_id]["last_triggered"] = None

    def set_reminder_active(self, reminder_id, is_active):
        self.reminders[reminder_id]["is_active"] = 1 if is_active else 0


class ReminderManagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def _create_manager(self, reminders):
        storage = FakeStorage(reminders)
        manager = ReminderManager(storage, FakeSettings())
        manager.stop()
        return manager, storage

    def test_single_reminder_snooze_keeps_reminder_active(self):
        due_time = datetime.now() - timedelta(seconds=5)
        snoozed_time = datetime.now() + timedelta(minutes=5)
        manager, storage = self._create_manager([
            {
                "id": 1,
                "title": "Tek seferlik",
                "description": "",
                "reminder_time": due_time.isoformat(),
                "is_active": 1,
                "repeat_type": "none",
                "last_triggered": None,
            }
        ])

        def on_triggered(reminder):
            storage.update_reminder_time(reminder["id"], snoozed_time.isoformat())
            storage.set_reminder_active(reminder["id"], True)

        manager.reminder_triggered.connect(on_triggered)
        manager._check_reminders()

        updated = storage.get_reminder(1)
        self.assertEqual(updated["is_active"], 1)
        self.assertEqual(updated["reminder_time"], snoozed_time.isoformat())
        self.assertIsNone(updated["last_triggered"])

    def test_repeating_reminder_snooze_is_not_overwritten_by_repeat_schedule(self):
        due_time = datetime.now() - timedelta(seconds=5)
        snoozed_time = datetime.now() + timedelta(minutes=10)
        manager, storage = self._create_manager([
            {
                "id": 2,
                "title": "Tekrarlayan",
                "description": "",
                "reminder_time": due_time.isoformat(),
                "is_active": 1,
                "repeat_type": "daily",
                "last_triggered": None,
            }
        ])

        def on_triggered(reminder):
            storage.update_reminder_time(reminder["id"], snoozed_time.isoformat())
            storage.set_reminder_active(reminder["id"], True)

        manager.reminder_triggered.connect(on_triggered)
        manager._check_reminders()

        updated = storage.get_reminder(2)
        self.assertEqual(updated["reminder_time"], snoozed_time.isoformat())
        self.assertEqual(updated["is_active"], 1)
        self.assertIsNone(updated["last_triggered"])


if __name__ == "__main__":
    unittest.main()
