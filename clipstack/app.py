import sys
import traceback
from pathlib import Path

from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox
from PySide6.QtGui import QIcon, QAction, QPalette, QColor
from PySide6.QtCore import Qt, QTimer

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

import sys
if sys.platform.startswith("win"):
    import ctypes
    def _set_windows_app_user_model_id(appid: str):
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)
        except Exception:
            # Güvenli şekilde geç
            pass
else:
    def _set_windows_app_user_model_id(appid: str):
        # Diğer platformlarda gerek yok
        pass

class TrayApp:
    def __init__(self):
        _set_windows_app_user_model_id("ClipStack.Taxperia")
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("ClipStack")
        self.app.setOrganizationName("ClipStack")
        self.app.setQuitOnLastWindowClosed(False)

        # Storage & settings
        data_dir = Path.home() / "AppData" / "Roaming" / "ClipStack"
        data_dir.mkdir(parents=True, exist_ok=True)
        self.storage = Storage(data_dir / "clipstack.db")
        self.settings = Settings(data_dir / "settings.json")
        self.settings.load()

        # Dil & Tema
        i18n.load_language(self.settings.get("language", "tr"))
        theme_manager.apply(self.settings.get("theme", "default"))
        # try:
        #     qss_global = resource_path("styles/style.qss")
        #     if qss_global.exists():
        #         self.app.setStyleSheet(self.app.styleSheet() + "\n" + qss_global.read_text("utf-8"))
        # except Exception:
        #     pass

        # App ve pencere ikonu
        app_icon = self._resolve_tray_icon()
        self.app.setWindowIcon(app_icon)

        # UI
        self.window = HistoryWindow(self.storage, self.settings)
        self.window.setWindowIcon(app_icon)
        # Düzeltme: pencere içindeki Ayarlar butonu bu metodu çağıracak
        self.window.set_open_settings_handler(self.open_settings)
        # Alternatif: sinyale bağlamak isterseniz
        self.window.open_settings_requested.connect(self.open_settings)

        # Tray
        self.tray = QSystemTrayIcon(app_icon, self.app)
        self.menu = QMenu()
        self.action_show = QAction("Geçmişi Göster")
        self.action_show.triggered.connect(self.toggle_window)
        self.menu.addAction(self.action_show)

        self.action_settings = QAction("Ayarlar")
        self.action_settings.triggered.connect(self.open_settings)
        self.menu.addAction(self.action_settings)

        self.action_pause = QAction("Kaydı Duraklat", checkable=True)
        self.action_pause.setChecked(self.settings.get("pause_recording", False))
        self.action_pause.triggered.connect(self.toggle_pause)
        self.menu.addAction(self.action_pause)

        self.action_startup = QAction("Windows ile Başlat", checkable=True)
        self.action_startup.setChecked(self.settings.get("launch_at_startup", True))
        self.action_startup.triggered.connect(self.toggle_startup)
        self.menu.addAction(self.action_startup)

        self.menu.addSeparator()
        self.action_exit = QAction("Çıkış")
        self.action_exit.triggered.connect(self.exit_app)
        self.menu.addAction(self.action_exit)

        self.tray.setContextMenu(self.menu)
        self.tray.setToolTip("ClipStack - Pano Geçmişi")
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()

        # Clipboard watcher vb. (aynı)
        self.clipboard_watcher = ClipboardWatcher(self.app.clipboard(), self.storage, self.settings)
        self.clipboard_watcher.item_added.connect(self.window.on_item_added)

        # Hotkey
        self.hotkey = HotkeyManager()
        desired_hotkey = self.settings.get("hotkey", "windows+v")
        if not self.hotkey.register(desired_hotkey, self.on_hotkey):
            fallback = "ctrl+shift+v"
            if self.hotkey.register(fallback, self.on_hotkey):
                self.settings.set("hotkey", fallback)
                self.settings.save()
                notify_tray(self.tray, "Kısayol değiştirildi", f"Win+V yakalanamadı, {fallback} kullanılacak.")
            else:
                notify_tray(self.tray, "Kısayol ayarlanamadı", "Lütfen Ayarlar'dan farklı bir kısayol deneyin.")

        # İlk çalışma
        if self.settings.get("first_run", True):
            try:
                set_launch_at_startup(True)
                self.action_startup.setChecked(True)
            except Exception:
                pass
            self.settings.set("first_run", False)
            self.settings.save()
            notify_tray(self.tray, "ClipStack çalışıyor", "Kısayol ile geçmişi açabilirsiniz.")

    def _resolve_tray_icon(self) -> QIcon:
        icon_path = self.settings.get("tray_icon", "assets/icons/tray/tray1.ico")
        p = Path(icon_path)
        if not p.is_absolute():
            p = resource_path(icon_path)
        if not p.exists():
            # fallback svg
            p = resource_path("assets/icons/clipboard.svg")
        return QIcon(str(p))

    def _apply_stay_on_top(self):
        self.window.setWindowFlag(Qt.WindowStaysOnTopHint, bool(self.settings.get("stay_on_top", False)))
        if self.window.isVisible():
            self.window.show()

    def _apply_toast_visibility(self):
        # HistoryWindow kendi içinde show_toast kontrol ediyor olabilir;
        # burada şimdilik ayar saklı kalsın (gerekirse Toast sınıfına parametre geç)
        pass

    def on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.toggle_window()

    def on_hotkey(self):
        QTimer.singleShot(0, self.toggle_window)

    def toggle_window(self):
        if self.window.isVisible():
            self.window.hide()
        else:
            # Önce göster, sonra yükle (beyaz ekranı engeller)
            self.window.showCentered()
            QTimer.singleShot(0, self.window.reload_items)
            self.window.activateWindow()
            self.window.raise_()

    def open_settings(self):
        dlg = SettingsDialog(self.settings)
        if dlg.exec():
            # Dil ve tema
            i18n.load_language(self.settings.get("language", "tr"))
            theme_manager.apply(self.settings.get("theme", "default"))

            # Tepsi ikonu
            self.tray.setIcon(self._resolve_tray_icon())

            # Pencere "üste tut" bayrağı
            self._apply_stay_on_top()

            # Windows ile başlat
            try:
                set_launch_at_startup(bool(self.settings.get("launch_at_startup", True)))
                self.action_startup.setChecked(bool(self.settings.get("launch_at_startup", True)))
            except Exception as e:
                QMessageBox.warning(None, "Hata", f"Başlangıç ayarı yapılamadı:\n{e}")

            # Bilgi bildirimi
            notify_tray(self.tray, "Ayarlar güncellendi", "Değişiklikler uygulandı.")

    def toggle_pause(self, checked: bool):
        self.settings.set("pause_recording", checked)
        self.settings.save()
        self.clipboard_watcher.set_paused(checked)
        state = "duraklatıldı" if checked else "devam ediyor"
        notify_tray(self.tray, "Kayıt durumu", f"Pano kaydı {state}.")

    def toggle_startup(self, checked: bool):
        try:
            set_launch_at_startup(checked)
            self.settings.set("launch_at_startup", checked)
            self.settings.save()
        except Exception as e:
            traceback.print_exc()
            QMessageBox.warning(None, "Hata", f"Başlangıç ayarı yapılamadı:\n{e}")
            self.action_startup.setChecked(is_launch_at_startup())

    def exit_app(self):
        try:
            self.hotkey.unregister()
        except Exception:
            pass
        self.tray.hide()
        self.window.close()
        self.app.quit()


def run_app():
    app = TrayApp()
    sys.exit(app.app.exec())