import sys
import traceback
from pathlib import Path

from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Qt, QTimer, QObject, Signal, QElapsedTimer

from .clipboard_watcher import ClipboardWatcher
from .ui.main_window import HistoryWindow
from .ui.settings_dialog import SettingsDialog
from .storage import Storage
from .settings import Settings
from .startup import set_launch_at_startup, is_launch_at_startup
from .utils import resource_path, notify_tray
from .hotkey import HotkeyManager
from .i18n import i18n
from .theme_manager import theme_manager

def _set_windows_app_user_model_id(appid: str):
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)
        except Exception:
            pass


class HotkeyBridge(QObject):
    trigger = Signal()


class TrayApp:
    def __init__(self):

       if self.settings.get("encrypt_data", False):
        password, ok = QInputDialog.getText(None, "Şifre", "Veri şifrenizi girin:", QLineEdit.Password)
        if ok and password:
            self.settings.set("encryption_key", password)
        else:
            QMessageBox.warning(None, "Hata", "Şifre girilmedi, uygulama kapatılıyor.")
            sys.exit(1)
        _set_windows_app_user_model_id("TaxClip.Taxperia")

        self.app = QApplication(sys.argv)
        self.app.setApplicationName("TaxClip")
        self.app.setOrganizationName("Miyotu")
        self.app.setQuitOnLastWindowClosed(False)

        data_dir = Path.home() / "AppData" / "Roaming" / "TaxClip"
        data_dir.mkdir(parents=True, exist_ok=True)
        self.storage = Storage(data_dir / "taxclip.db")
        self.settings = Settings(data_dir / "settings.json")
        self.settings.load()

        try:
            i18n.load_language(self.settings.get("language", "tr"))
        except Exception:
            pass
        try:
            theme_manager.apply(self.settings.get("theme", "default"))
        except Exception:
            pass

        app_icon = self._resolve_tray_icon()
        self.app.setWindowIcon(app_icon)

        self.window = HistoryWindow(self.storage, self.settings)
        self.window.setWindowIcon(app_icon)
        self.window.set_open_settings_handler(self.open_settings)

        # Tray
        self.tray = QSystemTrayIcon(app_icon, self.app)
        self.menu = QMenu()

        self.action_show = QAction(self.menu)
        self.action_show.triggered.connect(self.toggle_window)
        self.menu.addAction(self.action_show)

        self.action_settings = QAction(self.menu)
        self.action_settings.triggered.connect(self.open_settings)
        self.menu.addAction(self.action_settings)

        self.action_pause = QAction(self.menu, checkable=True)
        self.action_pause.setChecked(self.settings.get("pause_recording", False))
        self.action_pause.triggered.connect(self.toggle_pause)
        self.menu.addAction(self.action_pause)

        self.action_startup = QAction(self.menu, checkable=True)
        self.action_startup.setChecked(self.settings.get("launch_at_startup", True))
        self.action_startup.triggered.connect(self.toggle_startup)
        self.menu.addAction(self.action_startup)

        self.menu.addSeparator()
        self.action_exit = QAction(self.menu)
        self.action_exit.triggered.connect(self.exit_app)
        self.menu.addAction(self.action_exit)

        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

        self._refresh_texts()
        i18n.languageChanged.connect(self._refresh_texts)

        # Clipboard watcher
        self.clipboard_watcher = ClipboardWatcher(self.app.clipboard(), self.storage, self.settings)
        try:
            self.clipboard_watcher.item_added.connect(self.window.on_item_added)
        except Exception:
            pass

        # Hotkey köprüsü + debounce
        self._hotkey_bridge = HotkeyBridge()
        self._hotkey_bridge.trigger.connect(self.toggle_window)
        self._toggle_lock = False
        self._toggle_timer = QElapsedTimer()
        self._toggle_timer.start()

        self.hotkey = HotkeyManager()
        self._rebind_hotkey(initial=True)

        if self.settings.get("first_run", True):
            try:
                set_launch_at_startup(True)
                self.action_startup.setChecked(True)
            except Exception:
                pass
            self.settings.set("first_run", False)
            self.settings.save()
            notify_tray(
                self.tray,
                self._tr("notify.running.title", "TaxClip is running"),
                self._tr("notify.running.body", "You can open the history with the hotkey.")
            )

        self._apply_stay_on_top()

    def _tr(self, key: str, fallback: str, **fmt) -> str:
        try:
            s = i18n.t(key)
        except Exception:
            s = ""
        s = s if s and s != key else fallback
        try:
            return s.format(**fmt) if fmt else s
        except Exception:
            return s

    def _resolve_tray_icon(self) -> QIcon:
        for rel in [self.settings.get("tray_icon", "assets/icons/tray/tray1.svg"),
                    "assets/icons/tray/tray1.svg",
                    "assets/icons/clipboard.svg"]:
            p = Path(rel)
            if not p.is_absolute():
                p = resource_path(rel)
            if p.exists():
                ico = QIcon(str(p))
                if not ico.isNull():
                    return ico
        return QIcon()

    def _apply_stay_on_top(self):
        try:
            self.window.setWindowFlag(Qt.WindowStaysOnTopHint, bool(self.settings.get("stay_on_top", False)))
            if self.window.isVisible():
                self.window.show()
        except Exception:
            pass

    def _refresh_texts(self):
        self.tray.setToolTip(self._tr("tray.tooltip", "TaxClip - Clipboard History"))
        self.action_show.setText(self._tr("tray.show_history", "Show History"))
        self.action_settings.setText(self._tr("tray.settings", "Settings"))
        self.action_pause.setText(self._tr("tray.pause_recording", "Pause Recording"))
        self.action_startup.setText(self._tr("tray.launch_at_startup", "Launch at Startup"))
        self.action_exit.setText(self._tr("tray.exit", "Exit"))

    def _rebind_hotkey(self, initial: bool = False):
        try:
            self.hotkey.unregister()
        except Exception:
            pass

        desired = (self.settings.get("hotkey", "windows+v") or "windows+v").strip()
        ok = False
        try:
            ok = self.hotkey.register(desired, self.on_hotkey)
        except Exception:
            ok = False

        if ok:
            if not initial:
                notify_tray(
                    self.tray,
                    self._tr("hotkey.updated.title", "Hotkey updated"),
                    self._tr("hotkey.updated.body", "{hotkey} is assigned.", hotkey=desired),
                )
            return

        fallback = "ctrl+shift+v"
        try:
            if self.hotkey.register(fallback, self.on_hotkey):
                self.settings.set("hotkey", fallback)
                self.settings.save()
                notify_tray(
                    self.tray,
                    self._tr("hotkey.changed.title", "Hotkey changed"),
                    self._tr("hotkey.changed.body", "Win+V couldn't be captured, {fallback} will be used.", fallback=fallback),
                )
                return
        except Exception:
            pass

        notify_tray(
            self.tray,
            self._tr("hotkey.failed.title", "Hotkey couldn't be set"),
            self._tr("hotkey.failed.body", "Please try a different hotkey in Settings."),
        )

    def _apply_runtime_settings(self):
        try:
            i18n.load_language(self.settings.get("language", "tr"))
        except Exception:
            pass
        try:
            theme_manager.apply(self.settings.get("theme", "default"))
        except Exception:
            pass
        self._apply_stay_on_top()
        try:
            self.tray.setIcon(self._resolve_tray_icon())
        except Exception:
            pass
        try:
            set_launch_at_startup(bool(self.settings.get("launch_at_startup", True)))
        except Exception:
            pass
        self._rebind_hotkey()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick, QSystemTrayIcon.MiddleClick):
            self.toggle_window()

    def on_hotkey(self):
        try:
            self._hotkey_bridge.trigger.emit()
        except Exception:
            pass

    def toggle_window(self):
        if self._toggle_lock:
            return
        if self._toggle_timer.elapsed() < 250:
            return
        self._toggle_lock = True
        self._toggle_timer.restart()
        try:
            if self.window.isVisible():
                self.window.hide()
            else:
                try:
                    self.window.showCentered()  # type: ignore[attr-defined]
                except Exception:
                    self.window.show()
                try:
                    QTimer.singleShot(0, self.window.reload_items)
                except Exception:
                    pass
                self.window.activateWindow()
                self.window.raise_()
        finally:
            QTimer.singleShot(200, lambda: setattr(self, "_toggle_lock", False))

    def open_settings(self):
        dlg = SettingsDialog(self.settings)
        if hasattr(dlg, "applied"):
            try:
                dlg.applied.connect(self._apply_runtime_settings)
            except Exception:
                pass
        if dlg.exec():
            self._apply_runtime_settings()
            try:
                self.action_startup.setChecked(bool(self.settings.get("launch_at_startup", True)))
            except Exception:
                pass
            notify_tray(
                self.tray,
                self._tr("notify.settings_updated.title", "Settings updated"),
                self._tr("notify.settings_updated.body", "Changes have been applied."),
            )

    def toggle_pause(self, checked: bool):
        self.settings.set("pause_recording", checked)
        self.settings.save()
        try:
            self.clipboard_watcher.set_paused(checked)
        except Exception:
            pass
        notify_tray(
            self.tray,
            self._tr("pause.status.title", "Recording status"),
            self._tr("pause.status.paused", "Clipboard recording paused.") if checked
            else self._tr("pause.status.resumed", "Clipboard recording resumed."),
        )

    def toggle_startup(self, checked: bool):
        try:
            set_launch_at_startup(checked)
            self.settings.set("launch_at_startup", checked)
            self.settings.save()
        except Exception as e:
            traceback.print_exc()
            QMessageBox.warning(
                None,
                self._tr("startup.error.title", "Error"),
                self._tr("startup.error.body", "Couldn't apply startup setting:\n{error}", error=e),
            )
            try:
                self.action_startup.setChecked(is_launch_at_startup())
            except Exception:
                pass

    def exit_app(self):
        try:
            self.hotkey.unregister()
        except Exception:
            pass
        try:
            self.tray.hide()
        except Exception:
            pass
        try:
            self.window.close()
        except Exception:
            pass
        self.app.quit()


def run_app():
    app = TrayApp()
    sys.exit(app.app.exec())