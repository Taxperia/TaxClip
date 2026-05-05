from __future__ import annotations

import sys
import traceback
from pathlib import Path

from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox, QInputDialog, QLineEdit
from PySide6.QtGui import QIcon, QAction, QScreen, QPixmap, QGuiApplication
from PySide6.QtCore import Qt, QTimer, QObject, Signal, QElapsedTimer, QDateTime, QByteArray, QBuffer, QIODevice

from .clipboard_watcher import ClipboardWatcher
from .ui.main_window import HistoryWindow
from .ui.settings_dialog import SettingsDialog
from .storage import Storage
from .settings import Settings
from .startup import set_launch_at_startup, is_launch_at_startup
from .utils import resource_path, notify_tray, svg_icon, copy_to_clipboard_safely
from .hotkey import HotkeyManager
from .i18n import i18n
from .sensitive_detector import ensure_sensitive_access
from .theme_manager import theme_manager

from .reminder_manager import ReminderManager
from .sound_player import SoundPlayer, is_sound_backend_available, get_sound_backend_error
from .ui.reminder_notification import ReminderNotificationDialog

def _set_windows_app_user_model_id(appid: str):
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)
        except Exception:
            pass


def _is_fullscreen_foreground_app(*, ignored_pid: int | None = None) -> bool:
    if not sys.platform.startswith("win"):
        return False

    try:
        import ctypes
        from ctypes import wintypes

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG),
            ]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", RECT),
                ("rcWork", RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False

        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return False

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if ignored_pid and pid.value == ignored_pid:
            return False

        rect = RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return False

        monitor = user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
        if not monitor:
            return False

        monitor_info = MONITORINFO()
        monitor_info.cbSize = ctypes.sizeof(MONITORINFO)
        if not user32.GetMonitorInfoW(monitor, ctypes.byref(monitor_info)):
            return False

        tolerance = 8
        return (
            abs(rect.left - monitor_info.rcMonitor.left) <= tolerance
            and abs(rect.top - monitor_info.rcMonitor.top) <= tolerance
            and abs(rect.right - monitor_info.rcMonitor.right) <= tolerance
            and abs(rect.bottom - monitor_info.rcMonitor.bottom) <= tolerance
        )
    except Exception:
        return False


class HotkeyBridge(QObject):
    trigger = Signal()
    paste_last = Signal()
    quick_note = Signal()
    screenshot = Signal()
    ocr = Signal()
    snip = Signal()


class TrayApp:
    def __init__(self):

        _set_windows_app_user_model_id("TaxClip.Taxperia")

        self.app = QApplication(sys.argv)
        self.app.setApplicationName("TaxClip")
        self.app.setApplicationDisplayName("TaxClip")
        self.app.setOrganizationName("Miyotu")
        self.app.setQuitOnLastWindowClosed(False)

        data_dir = Path.home() / "AppData" / "Roaming" / "TaxClip"
        data_dir.mkdir(parents=True, exist_ok=True)

        self.settings = Settings(data_dir / "settings.json")
        self.settings.load()

        self.storage = Storage(data_dir / "taxclip.db", self.settings)

        try:
            i18n.load_language(self.settings.get("language", "tr"))
        except Exception:
            pass
        try:
            theme_manager.apply(self.settings.get("theme", "default"))
        except Exception:
            pass

        self.app_icon = self._resolve_app_icon()
        tray_icon = self._resolve_tray_icon()
        self.app.setWindowIcon(self.app_icon)

        self.window = HistoryWindow(self.storage, self.settings)
        self.window.setWindowIcon(self.app_icon)
        self.window.set_open_settings_handler(self.open_settings)
        
        self.is_locked = False
        
        # TOTP (Google Authenticator) kontrolü
        if self.settings.get("totp_on_startup", False):
            from .totp_manager import TOTPManager
            totp = TOTPManager(self.settings)
            if totp.is_enabled():
                from .ui.totp_dialog import TOTPVerifyDialog
                totp_dlg = TOTPVerifyDialog(self.settings, None, "Uygulama Girişi")
                if not (totp_dlg.exec() and totp_dlg.is_verified()):
                    QMessageBox.warning(None, "Erişim Reddedildi", "2FA doğrulaması başarısız.")
                    sys.exit(1)

        if self.settings.get("encrypt_data", False):
            password, ok = QInputDialog.getText(None, "Şifre", "Veri şifrenizi girin:", QLineEdit.Password)
            if ok and password:
                self.settings.set("encryption_key", password)
            else:
                QMessageBox.warning(None, "Hata", "Şifre girilmedi, uygulama kapatılıyor.")
                sys.exit(1)

        self.tray = QSystemTrayIcon(tray_icon, self.app)
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
        
        self.action_screenshot = QAction(self.menu)
        self.action_screenshot.triggered.connect(self.open_snip_tool)
        self.menu.addAction(self.action_screenshot)

        self.menu.addSeparator()
        self.action_exit = QAction(self.menu)
        self.action_exit.triggered.connect(self.exit_app)
        self.menu.addAction(self.action_exit)

        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

        self._refresh_texts()
        i18n.languageChanged.connect(self._refresh_texts)

        self.clipboard_watcher = ClipboardWatcher(self.app.clipboard(), self.storage, self.settings)
        try:
            self.clipboard_watcher.item_added.connect(self.window.on_item_added)
        except Exception:
            pass

        self._hotkey_bridge = HotkeyBridge()
        self._hotkey_bridge.trigger.connect(self.toggle_window)
        self._hotkey_bridge.paste_last.connect(self.paste_last_item)
        self._hotkey_bridge.quick_note.connect(self.quick_note_dialog)
        self._hotkey_bridge.screenshot.connect(self.capture_screenshot)
        self._hotkey_bridge.ocr.connect(self.on_ocr_hotkey)
        self._hotkey_bridge.snip.connect(self.open_snip_tool)

        self._toggle_lock = False
        self._toggle_timer = QElapsedTimer()
        self._toggle_timer.start()

        self.hotkey = HotkeyManager()
        self.hotkey_paste = HotkeyManager()
        self.hotkey_quick_note = HotkeyManager()
        self.hotkey_screenshot = HotkeyManager()
        self.hotkey_ocr = HotkeyManager()
        self.hotkey_snip = HotkeyManager()

        self._sound_player: SoundPlayer | None = None
        if is_sound_backend_available():
            try:
                self._sound_player = SoundPlayer(self.app)
                self._sound_player.playbackFailed.connect(self._on_sound_playback_failed)
            except Exception as exc:
                print(f"[SOUND] Multimedia backend init failed: {exc}")
        else:
            print(f"[SOUND] QtMultimedia backend unavailable: {get_sound_backend_error()}; WAV-only fallback will be used.")

        self._rebind_all_hotkeys(initial=True)
        try:
            self._sync_launch_at_startup()
        except Exception:
            pass

        if self.settings.get("first_run", True):
            self.settings.set("first_run", False)
            self.settings.save()
            notify_tray(
                self.tray,
                self._tr("notify.running.title", "TaxClip is running"),
                self._tr("notify.running.body", "You can open the history with the hotkey.")
            )
        
        # ReminderManager'ı if bloğunun DIŞINA taşıyın
        self.reminder_manager = ReminderManager(self.storage, self.settings)
        self.reminder_manager.reminder_triggered.connect(self._on_reminder_triggered)
        self.reminder_manager.reminder_triggered.connect(self.window.on_reminder_time_updated)

        self._apply_stay_on_top()
        
        # Saatlik TOTP kilitleme sistemi
        self._totp_last_verified = QDateTime.currentDateTime()
        self._totp_lock_timer = QTimer()
        self._totp_lock_timer.timeout.connect(self._check_totp_hourly_lock)
        if self.settings.get("totp_hourly_lock", False):
            self._totp_lock_timer.start(60000)  # Her dakika kontrol et
        
        # Başlangıçta güncelleme kontrolü (sessiz)
        self._check_updates_on_startup()

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

    def _resolve_app_icon(self) -> QIcon:
        for rel in (
            "assets/icons/logo.ico",
            "assets/icons/logo.png",
            "assets/icons/clipboard.ico",
            "assets/icons/clipboard.svg",
        ):
            path = resource_path(rel)
            if not path.exists():
                continue
            icon = QIcon(str(path))
            if not icon.isNull():
                return icon
            icon = svg_icon(rel, 256)
            if not icon.isNull():
                return icon
        return self._resolve_tray_icon()

    def _resolve_tray_icon(self) -> QIcon:
        from PySide6.QtGui import QPixmap, QPainter, QColor
        from PySide6.QtCore import Qt as QtCore_Qt

        for rel in [self.settings.get("tray_icon", "assets/icons/tray/tray1.svg"),
                    "assets/icons/tray/tray1.svg",
                    "assets/icons/clipboard.svg"]:
            ico = svg_icon(rel, 64)
            if not ico.isNull():
                return ico
        
        # Fallback: Basit clipboard ikonu
        base_color = QColor("#2c3e50")
        accent_color = QColor("#1a252f")

        pixmap = QPixmap(64, 64)
        pixmap.fill(QtCore_Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(base_color)
        painter.setPen(accent_color)
        painter.drawRoundedRect(8, 4, 48, 56, 6, 6)
        painter.setBrush(accent_color)
        painter.drawRoundedRect(18, 4, 28, 10, 4, 4)
        painter.setBrush(QColor("#ffffff"))
        painter.drawRect(16, 12, 32, 4)
        painter.drawRect(16, 22, 32, 4)
        painter.drawRect(16, 32, 32, 4)
        painter.drawRect(16, 42, 24, 4)
        painter.end()
        return QIcon(pixmap)

    def _sync_launch_at_startup(self, desired_state: bool | None = None, save: bool = True) -> bool:
        desired = bool(self.settings.get("launch_at_startup", True)) if desired_state is None else bool(desired_state)
        set_launch_at_startup(desired)
        actual_state = is_launch_at_startup()
        if actual_state != bool(self.settings.get("launch_at_startup", True)):
            self.settings.set("launch_at_startup", actual_state)
            if save:
                self.settings.save()
        try:
            self.action_startup.setChecked(actual_state)
        except Exception:
            pass
        return actual_state

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
        self.action_screenshot.setText(self._tr("tray.screenshot", "Ekran Alıntısı"))
        self.action_exit.setText(self._tr("tray.exit", "Exit"))

    def _rebind_all_hotkeys(self, initial: bool = False):
        self._rebind_hotkey(initial)
        self._rebind_paste_hotkey(initial)
        self._rebind_quick_note_hotkey(initial)
        self._rebind_screenshot_hotkey(initial)
        self._rebind_ocr_hotkey(initial)
        self._rebind_snip_hotkey(initial)

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

    def _rebind_paste_hotkey(self, initial: bool = False):
        try:
            self.hotkey_paste.unregister()
        except Exception:
            pass

        desired = (self.settings.get("hotkey_paste_last", "") or "").strip()
        if not desired:
            return

        ok = False
        try:
            ok = self.hotkey_paste.register(desired, self.on_paste_last_hotkey)
        except Exception:
            ok = False

        if ok and not initial:
            notify_tray(
                self.tray,
                self._tr("hotkey.paste.updated.title", "Paste hotkey updated"),
                self._tr("hotkey.paste.updated.body", "{hotkey} is assigned.", hotkey=desired),
            )

    def _rebind_quick_note_hotkey(self, initial: bool = False):
        try:
            self.hotkey_quick_note.unregister()
        except Exception:
            pass

        desired = (self.settings.get("hotkey_quick_note", "") or "").strip()
        if not desired:
            return

        ok = False
        try:
            ok = self.hotkey_quick_note.register(desired, self.on_quick_note_hotkey)
        except Exception:
            ok = False

        if ok and not initial:
            notify_tray(
                self.tray,
                self._tr("hotkey.quicknote.updated.title", "Quick note hotkey updated"),
                self._tr("hotkey.quicknote.updated.body", "{hotkey} is assigned.", hotkey=desired),
            )

    def _rebind_screenshot_hotkey(self, initial: bool = False):
        try:
            self.hotkey_screenshot.unregister()
        except Exception:
            pass

        desired = (self.settings.get("hotkey_screenshot", "") or "").strip()
        if not desired:
            return

        ok = False
        try:
            ok = self.hotkey_screenshot.register(desired, self.on_screenshot_hotkey)
        except Exception:
            ok = False

        if ok and not initial:
            notify_tray(
                self.tray,
                self._tr("hotkey.screenshot.updated.title", "Ekran görüntüsü kısayolu güncellendi"),
                self._tr("hotkey.screenshot.updated.body", "{hotkey} atandı.", hotkey=desired),
            )
    
    def _rebind_ocr_hotkey(self, initial: bool = False):
        try:
            self.hotkey_ocr.unregister()
        except Exception:
            pass

        desired = (self.settings.get("hotkey_ocr", "") or "").strip()
        if not desired:
            return

        ok = False
        try:
            ok = self.hotkey_ocr.register(desired, self.on_ocr_hotkey)
        except Exception:
            ok = False

        if ok and not initial:
            notify_tray(
                self.tray,
                self._tr("hotkey.ocr.updated.title", "OCR kısayolu güncellendi"),
                self._tr("hotkey.ocr.updated.body", "{hotkey} atandı.", hotkey=desired),
            )

    def _rebind_snip_hotkey(self, initial: bool = False):
        try:
            self.hotkey_snip.unregister()
        except Exception:
            pass

        desired = (self.settings.get("hotkey_snip", "") or "").strip()
        if not desired:
            return

        ok = False
        try:
            ok = self.hotkey_snip.register(desired, self.on_snip_hotkey)
        except Exception:
            ok = False

        if ok and not initial:
            notify_tray(
                self.tray,
                self._tr("hotkey.snip.updated.title", "Ekran alıntısı kısayolu güncellendi"),
                self._tr("hotkey.snip.updated.body", "{hotkey} atandı.", hotkey=desired),
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
            tray_icon = self._resolve_tray_icon()
            self.tray.setIcon(tray_icon)
            self.app.setWindowIcon(self.app_icon)
            self.window.setWindowIcon(self.app_icon)
        except Exception:
            pass
        try:
            self._sync_launch_at_startup()
        except Exception:
            pass
        self._rebind_all_hotkeys()
        
        # Video recorder ayarlarını yeniden yükle
        try:
            if hasattr(self.window, 'video_control_widget') and self.window.video_control_widget:
                self.window.video_control_widget.reload_settings()
        except Exception:
            pass

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick, QSystemTrayIcon.MiddleClick):
            self.toggle_window()

    def on_hotkey(self):
        try:
            self._hotkey_bridge.trigger.emit()
        except Exception:
            pass

    def on_paste_last_hotkey(self):
        try:
            self._hotkey_bridge.paste_last.emit()
        except Exception:
            pass

    def on_quick_note_hotkey(self):
        try:
            self._hotkey_bridge.quick_note.emit()
        except Exception:
            pass

    def on_screenshot_hotkey(self):
        try:
            self._hotkey_bridge.screenshot.emit()
        except Exception:
            pass

    def on_snip_hotkey(self):
        try:
            self._hotkey_bridge.snip.emit()
        except Exception:
            pass

    def capture_screenshot(self):
        """Tam ekran görüntüsü al (klasik)"""        
        try:
            from .storage import ClipItemType
            screen = QGuiApplication.primaryScreen()
            if screen:
                pixmap = screen.grabWindow(0)
                ba = QByteArray()
                buf = QBuffer(ba)
                buf.open(QBuffer.WriteOnly)
                pixmap.save(buf, "PNG")
                buf.close()
                png_bytes = bytes(ba)
                
                copy_to_clipboard_safely(None, ClipItemType.IMAGE, png_bytes)
                
                # Storage'a kaydet
                self._on_screenshot_taken(png_bytes)
        except Exception as e:
            print(f"Full screenshot error: {e}")

    def open_snip_tool(self):
        """Lightshot benzeri ekran alıntısı aracını aç"""
        try:
            from .ui.screenshot_tool import ScreenshotOverlay
            
            # Önceki overlay varsa kapat
            if hasattr(self, '_screenshot_overlay') and self._screenshot_overlay:
                try:
                    self._screenshot_overlay.close()
                except Exception:
                    pass
            
            self._screenshot_overlay = ScreenshotOverlay(settings=self.settings)
            self._screenshot_overlay.screenshot_taken.connect(self._on_screenshot_taken)
            self._screenshot_overlay.screenshot_saved.connect(self._on_screenshot_saved)
            self._screenshot_overlay.start()
            
        except Exception as e:
            print(f"Screenshot tool error: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_screenshot_taken(self, png_bytes: bytes):
        """Ekran alıntısı alındığında - storage'a kaydet"""
        try:
            from .storage import ClipItemType
            created_at = QDateTime.currentDateTime().toString(Qt.ISODate)
            row = self.storage.add_item(
                item_type=ClipItemType.IMAGE,
                text=None,
                image_bytes=png_bytes,
                html=None,
                created_at=created_at
            )
            
            if row:
                self.window.on_item_added(row)
            else:
                print("[SCREENSHOT] Görsel hassas veri politikası nedeniyle kaydedilmedi")
            
            if self.settings.get("show_toast", True):
                notify_tray(
                    self.tray,
                    self._tr("screenshot.captured.title", "Ekran görüntüsü alındı"),
                    self._tr("screenshot.captured.body", "Ekran görüntüsü panoya kopyalandı."),
                )
        except Exception as e:
            print(f"Screenshot save error: {e}")
    
    def _on_screenshot_saved(self, file_path: str):
        """Ekran alıntısı dosyaya kaydedildiğinde"""
        try:
            if self.settings.get("show_toast", True):
                notify_tray(
                    self.tray,
                    self._tr("screenshot.saved.title", "Ekran görüntüsü kaydedildi"),
                    f"📁 {file_path}",
                )
        except Exception as e:
            print(f"Screenshot save notify error: {e}")
    
    def on_ocr_hotkey(self):
        """OCR kısayolu - ekrandan seçilen bölgedeki yazıyı tanı"""
        try:
            if not self.settings.get("ocr_enabled", False):
                notify_tray(
                    self.tray,
                    "OCR Kapalı",
                    "Ayarlar > Güvenlik bölümünden OCR'yi aktifleştirin."
                )
                return
            
            from .ocr_manager import OCRManager
            ocr = OCRManager(self.settings)
            
            if not ocr.is_available():
                notify_tray(
                    self.tray,
                    "OCR Kullanılamıyor",
                    ocr.get_install_message()
                )
                return
            
            # Ekran alıntısı aracını OCR modu ile aç
            from .ui.screenshot_tool import ScreenshotOverlay
            
            if hasattr(self, '_ocr_overlay') and self._ocr_overlay:
                try:
                    self._ocr_overlay.close()
                except Exception:
                    pass
            
            self._ocr_overlay = ScreenshotOverlay(settings=self.settings)
            self._ocr_overlay.screenshot_taken.connect(self._on_ocr_screenshot)
            self._ocr_overlay.start()
            
        except Exception as e:
            print(f"OCR hotkey error: {e}")
            import traceback
            traceback.print_exc()
            notify_tray(
                self.tray,
                "OCR Hatası",
                f"OCR işlemi başarısız: {str(e)}"
            )
    
    def _on_ocr_screenshot(self, png_bytes: bytes):
        """OCR için alınan ekran görüntüsünü işle"""
        try:
            from .ocr_manager import OCRManager
            ocr = OCRManager(self.settings)
            
            ocr_lang = self.settings.get("ocr_language", "tur+eng")
            text = ocr.extract_text(png_bytes, lang=ocr_lang)
            
            if text:
                QApplication.clipboard().setText(text)
                
                from .storage import ClipItemType
                created_at = QDateTime.currentDateTime().toString(Qt.ISODate)
                row = self.storage.add_item(
                    item_type=ClipItemType.TEXT,
                    text=text,
                    image_bytes=None,
                    html=None,
                    created_at=created_at
                )
                
                if row:
                    self.window.on_item_added(row)
                else:
                    print("[OCR] Çıkarılan metin hassas veri politikası nedeniyle geçmişe eklenmedi")
                
                if self.settings.get("show_toast", True):
                    preview = text[:100] + "..." if len(text) > 100 else text
                    notify_tray(
                        self.tray,
                        f"OCR Başarılı ({ocr.get_engine_name()})",
                        f"Metin panoya kopyalandı:\n{preview}"
                    )
            else:
                notify_tray(
                    self.tray,
                    "OCR Başarısız",
                    "Seçilen alanda metin bulunamadı."
                )
        except Exception as e:
            print(f"OCR processing error: {e}")
            notify_tray(
                self.tray,
                "OCR Hatası",
                f"OCR işlemi başarısız: {str(e)}"
            )

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
                    self.window.showCentered()
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

    def paste_last_item(self):
        try:
            last = self.storage.get_last_item()
            if not last:
                return

            from .storage import ClipItemType
            from .utils import copy_to_clipboard_safely

            item_type = ClipItemType(last["item_type"])

            if item_type == ClipItemType.TEXT:
                payload = last["text_content"]
                probe_text = payload or ""
            elif item_type == ClipItemType.HTML:
                payload = last["html_content"]
                probe_text = payload or ""
            elif item_type == ClipItemType.IMAGE:
                payload = last["image_blob"]
                probe_text = last.get("ocr_text") or ""
            else:
                return

            if probe_text and not ensure_sensitive_access(self.settings, probe_text, self.window):
                if self.settings.get("show_toast", True):
                    notify_tray(
                        self.tray,
                        "Erişim Engellendi",
                        "Son öğe hassas veri içeriyor. Yapıştırma için doğrulama gerekli."
                    )
                return

            copy_to_clipboard_safely(None, item_type, payload)

            # Simulate Ctrl+V to actually paste into the active window
            try:
                import ctypes
                from ctypes import wintypes
                
                INPUT_KEYBOARD = 1
                KEYEVENTF_KEYUP = 0x0002
                VK_CONTROL = 0x11
                VK_V = 0x56
                
                class KEYBDINPUT(ctypes.Structure):
                    _fields_ = [
                        ("wVk", wintypes.WORD),
                        ("wScan", wintypes.WORD),
                        ("dwFlags", wintypes.DWORD),
                        ("time", wintypes.DWORD),
                        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
                    ]
                
                class INPUT(ctypes.Structure):
                    class _INPUT(ctypes.Union):
                        _fields_ = [("ki", KEYBDINPUT)]
                    _fields_ = [("type", wintypes.DWORD), ("_input", _INPUT)]
                
                def _send_key(vk, flags=0):
                    x = INPUT(type=INPUT_KEYBOARD)
                    x._input.ki = KEYBDINPUT(
                        wVk=vk, wScan=0, dwFlags=flags, time=0,
                        dwExtraInfo=ctypes.pointer(ctypes.c_ulong(0))
                    )
                    ctypes.windll.user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))
                
                import time as _time
                _time.sleep(0.05)
                _send_key(VK_CONTROL)
                _send_key(VK_V)
                _send_key(VK_V, KEYEVENTF_KEYUP)
                _send_key(VK_CONTROL, KEYEVENTF_KEYUP)
            except Exception as paste_err:
                print(f"[PASTE] Ctrl+V simulation failed: {paste_err}")

            if self.settings.get("show_toast", True):
                notify_tray(
                    self.tray,
                    self._tr("paste.last.title", "Pasted"),
                    self._tr("paste.last.body", "Last item pasted to clipboard."),
                )
        except Exception:
            pass

    def quick_note_dialog(self):
        try:
            text, ok = QInputDialog.getMultiLineText(
                None,
                self._tr("notes.quick.title", "Quick Note"),
                self._tr("notes.quick.prompt", "Enter note:"),
                "",
            )
            if not ok:
                return

            content = (text or "").strip()
            if not content:
                return

            created_at = QDateTime.currentDateTime().toString(Qt.ISODate)
            self.storage.add_note(content, created_at)

            if self.settings.get("show_toast", True):
                notify_tray(
                    self.tray,
                    self._tr("notes.quick.saved.title", "Note Saved"),
                    self._tr("notes.quick.saved.body", "Quick note has been saved."),
                )
        except Exception:
            pass

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
            self._sync_launch_at_startup(checked)
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

    def _check_totp_hourly_lock(self):
        """Saatlik TOTP kilitleme kontrolü"""
        if not self.settings.get("totp_hourly_lock", False):
            return
        
        from .totp_manager import TOTPManager
        totp = TOTPManager(self.settings)
        
        if not totp.is_enabled():
            return
        
        # Son doğrulamadan bu yana 1 saat geçti mi?
        now = QDateTime.currentDateTime()
        elapsed_secs = self._totp_last_verified.secsTo(now)
        
        if elapsed_secs >= 3600:  # 1 saat = 3600 saniye
            # TOTP doğrulaması iste
            from .ui.totp_dialog import TOTPVerifyDialog
            dlg = TOTPVerifyDialog(self.settings, None, "Saatlik Güvenlik Doğrulaması")
            
            if dlg.exec() and dlg.is_verified():
                self._totp_last_verified = QDateTime.currentDateTime()
                print("[TOTP] Saatlik doğrulama başarılı")
            else:
                # Doğrulama başarısız - pencereyi kapat
                self.window.hide()
                notify_tray(
                    self.tray,
                    "🔒 Uygulama Kilitlendi",
                    "Saatlik güvenlik doğrulaması gerekiyor."
                )
    
    def _check_updates_on_startup(self):
        """Başlangıçta sessiz güncelleme kontrolü"""
        try:
            from .updater import Updater, show_update_dialog
            
            self._startup_updater = Updater(self.settings, None)
            
            def on_update_available(update_info):
                # Kullanıcıya bildir
                notify_tray(
                    self.tray,
                    f"🔄 Güncelleme Mevcut: v{update_info['version']}",
                    "Ayarlar > Hakkında bölümünden güncelleyebilirsiniz."
                )
            
            self._startup_updater.update_available.connect(on_update_available)
            self._startup_updater.check_for_updates(silent=True)
        except Exception as e:
            print(f"[UPDATE] Başlangıç güncelleme kontrolü hatası: {e}")

    def exit_app(self):
        try:
            self.hotkey.unregister()
        except Exception:
            pass
        try:
            self.hotkey_paste.unregister()
        except Exception:
            pass
        try:
            self.hotkey_quick_note.unregister()
        except Exception:
            pass
        try:
            self.hotkey_screenshot.unregister()
        except Exception:
            pass
        try:
            self.hotkey_ocr.unregister()
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

    def _on_reminder_triggered(self, reminder: dict):
        """Hatırlatma zamanı geldiğinde çağrılır"""
        try:
            notification_type = self.settings.get("reminder_notification_type", "system")
            title = reminder.get("title", "")
            description = reminder.get("description", "")
            sound_enabled = self.settings.get("reminder_sound_enabled", True)
            suppress_popup_for_fullscreen = _is_fullscreen_foreground_app(ignored_pid=self.app.applicationPid())

            if notification_type == "system":
                if sound_enabled:
                    self._play_reminder_sound()
                notify_tray(
                    self.tray,
                    f"⏰ {title}",
                    description if description else self._tr("reminder.time", "Hatırlatma zamanı!")
                )
                return

            if notification_type == "app":
                if sound_enabled:
                    self._play_reminder_sound()
                if suppress_popup_for_fullscreen:
                    print(f"[REMINDER] Full-screen uygulama algılandı, popup gösterilmedi: ID={reminder.get('id')}")
                    return
                if self.settings.get("reminder_show_popup", True):
                    dlg = ReminderNotificationDialog(reminder, self.settings)
                    dlg.snooze_requested.connect(self._on_reminder_snooze)
                    dlg.exec()
                return

            # Bilinmeyen tipler için her ikisini de dene
            if sound_enabled:
                self._play_reminder_sound()
            notify_tray(
                self.tray,
                f"⏰ {title}",
                description if description else self._tr("reminder.time", "Hatırlatma zamanı!")
            )
        except Exception:
            pass
    
    def _on_reminder_snooze(self, reminder_id: int, minutes: int):
        """Hatırlatmayı ertele"""
        try:
            from datetime import datetime, timedelta
            now = datetime.now()
            new_time = now + timedelta(minutes=minutes)
            
            # Zamanı güncelle ve last_triggered'ı sıfırla
            self.storage.update_reminder_time(reminder_id, new_time.isoformat())
            # Aktif yap ki tekrar tetiklenebilsin
            self.storage.set_reminder_active(reminder_id, True)
            
            print(f"[SNOOZE] Hatırlatma #{reminder_id} ertelendi: {new_time.isoformat()}")
            
            notify_tray(
                self.tray,
                self._tr("reminder.snoozed.title", "Hatırlatma ertelendi"),
                self._tr("reminder.snoozed.body", "{minutes} dakika sonra tekrar hatırlatılacak.", minutes=minutes)
            )
        except Exception as e:
            print(f"[SNOOZE] Erteleme hatası: {e}")
            import traceback
            traceback.print_exc()
    
    def _play_reminder_sound(self):
        """Hatırlatma sesi çal"""
        try:
            sound_file = self.settings.get("reminder_sound_file", "default")
            
            print(f"[SOUND] Ses ayarı okundu: {sound_file}")
            
            if sound_file == "default" or not sound_file or sound_file == "":
                # Windows sistem sesi çal
                import winsound
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
                print("[SOUND] Windows default ses çalındı")
            else:
                # Özel ses dosyası çal
                from pathlib import Path
                sound_path = Path(sound_file)
                
                print(f"[SOUND] Ses dosyası kontrol ediliyor:")
                print(f"  - Path: {sound_path}")
                print(f"  - Absolute: {sound_path.absolute()}")
                print(f"  - Exists: {sound_path.exists()}")
                
                if not sound_path.exists():
                    print(f"[SOUND] HATA: Ses dosyası bulunamadı!")
                    return
                
                # QtMultimedia ile çalmayı dene
                if self._sound_player is not None:
                    try:
                        print("[SOUND] QtMultimedia ile ses çalınıyor...")
                        self._sound_player.stop()
                        self._sound_player.play(sound_path)
                        return
                    except Exception as exc:
                        print(f"[SOUND] QtMultimedia hata verdi: {exc}")

                # QtMultimedia yoksa yalnızca WAV dosyalarını winsound ile çal
                if sound_path.suffix.lower() == ".wav":
                    try:
                        import winsound
                        print("[SOUND] winsound fallback devreye girdi...")
                        winsound.PlaySound(str(sound_path), winsound.SND_FILENAME | winsound.SND_ASYNC)
                        return
                    except Exception as exc:
                        print(f"[SOUND] winsound fallback başarısız: {exc}")
                else:
                    print("[SOUND] QtMultimedia kullanılamıyor ve dosya WAV değil, ses çalınamadı.")
        except Exception as e:
            print(f"[SOUND] Genel ses hatası: {e}")
            import traceback
            traceback.print_exc()

    def _on_sound_playback_failed(self, message: str) -> None:
        print(f"[SOUND] Playback error signalled: {message}")


def run_app():
    app = TrayApp()
    sys.exit(app.app.exec())
