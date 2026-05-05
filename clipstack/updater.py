"""
GitHub Updater - Uygulama güncellemelerini kontrol eder ve yükler
"""
import os
import sys
import json
import tempfile
import zipfile
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple, Dict
from PySide6.QtCore import QObject, Signal, QThread
from PySide6.QtWidgets import QMessageBox, QProgressDialog
from PySide6.QtCore import Qt
from . import __version__

# HTTP istekleri için
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    import urllib.request
    import urllib.error


class UpdateChecker(QThread):
    """Arka planda güncelleme kontrolü yapan thread"""
    
    update_available = Signal(dict)  # {version, download_url, release_notes, published_at}
    check_failed = Signal(str)  # Hata mesajı
    no_update = Signal()  # Güncelleme yok
    
    def __init__(self, repo_owner: str, repo_name: str, current_version: str, parent=None):
        super().__init__(parent)
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.current_version = current_version
    
    def run(self):
        try:
            result = check_for_updates(
                self.repo_owner, 
                self.repo_name, 
                self.current_version
            )
            
            if result:
                self.update_available.emit(result)
            else:
                self.no_update.emit()
                
        except Exception as e:
            self.check_failed.emit(str(e))


class UpdateDownloader(QThread):
    """Güncelleme dosyasını indiren thread"""
    
    progress = Signal(int)  # 0-100
    finished = Signal(str)  # İndirilen dosya yolu
    failed = Signal(str)  # Hata mesajı
    
    def __init__(self, download_url: str, parent=None):
        super().__init__(parent)
        self.download_url = download_url
    
    def run(self):
        try:
            file_path = download_update(self.download_url, self._on_progress)
            self.finished.emit(file_path)
        except Exception as e:
            self.failed.emit(str(e))
    
    def _on_progress(self, percent: int):
        self.progress.emit(percent)


def get_current_version() -> str:
    """Mevcut uygulama versiyonunu al"""
    return __version__ or "1.0.0"


def parse_version(version: str) -> Tuple[int, ...]:
    """Version string'i tuple'a çevir (karşılaştırma için)"""
    # "v1.2.3" veya "1.2.3" formatını destekle
    version = version.lstrip('v').strip()
    parts = []
    for part in version.split('.'):
        try:
            parts.append(int(part))
        except ValueError:
            # "1.2.3-beta" gibi durumlar için
            num_part = ''.join(c for c in part if c.isdigit())
            parts.append(int(num_part) if num_part else 0)
    return tuple(parts)


def is_newer_version(remote: str, current: str) -> bool:
    """Remote version current'tan yeni mi?"""
    try:
        remote_tuple = parse_version(remote)
        current_tuple = parse_version(current)
        return remote_tuple > current_tuple
    except Exception:
        return False


def check_for_updates(repo_owner: str, repo_name: str, current_version: str) -> Optional[Dict]:
    """
    GitHub API ile güncelleme kontrolü yap
    
    Returns:
        None - güncelleme yok veya hata
        dict - güncelleme bilgileri
    """
    api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
    
    try:
        if REQUESTS_AVAILABLE:
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            data = response.json()
        else:
            req = urllib.request.Request(api_url, headers={'User-Agent': 'TaxClip-Updater'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
        
        remote_version = data.get('tag_name', '').lstrip('v')
        
        if not remote_version:
            return None
        
        if not is_newer_version(remote_version, current_version):
            return None
        
        # Windows exe'yi bul
        download_url = None
        for asset in data.get('assets', []):
            name = asset.get('name', '').lower()
            if name.endswith('.exe') or name.endswith('.zip'):
                download_url = asset.get('browser_download_url')
                break
        
        # Asset yoksa zip olarak indir
        if not download_url:
            download_url = data.get('zipball_url')
        
        return {
            'version': remote_version,
            'download_url': download_url,
            'release_notes': data.get('body', ''),
            'published_at': data.get('published_at', ''),
            'html_url': data.get('html_url', ''),
        }
        
    except Exception as e:
        print(f"[UPDATER] Güncelleme kontrolü hatası: {e}")
        return None


def download_update(download_url: str, progress_callback=None) -> str:
    """
    Güncelleme dosyasını indir
    
    Returns:
        İndirilen dosyanın yolu
    """
    temp_dir = tempfile.mkdtemp()
    filename = download_url.split('/')[-1]
    if not filename or '.' not in filename:
        filename = "update.zip"
    
    file_path = os.path.join(temp_dir, filename)
    
    try:
        if REQUESTS_AVAILABLE:
            response = requests.get(download_url, stream=True, timeout=300)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size and progress_callback:
                            percent = int(downloaded * 100 / total_size)
                            progress_callback(percent)
        else:
            req = urllib.request.Request(download_url, headers={'User-Agent': 'TaxClip-Updater'})
            with urllib.request.urlopen(req, timeout=300) as response:
                total_size = int(response.headers.get('Content-Length', 0))
                downloaded = 0
                
                with open(file_path, 'wb') as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size and progress_callback:
                            percent = int(downloaded * 100 / total_size)
                            progress_callback(percent)
        
        return file_path
        
    except Exception as e:
        # Temizlik
        try:
            shutil.rmtree(temp_dir)
        except:
            pass
        raise e


def apply_update(file_path: str) -> bool:
    """
    Güncellemeyi uygula
    
    Windows'ta exe'yi çalıştırır veya zip'i çıkartır
    """
    try:
        if file_path.endswith('.exe'):
            # Installer'ı çalıştır
            subprocess.Popen([file_path], shell=True)
            return True
            
        elif file_path.endswith('.zip'):
            # Zip'i çıkart ve güncelleme script'i oluştur
            app_dir = Path(__file__).parent.parent
            temp_extract = tempfile.mkdtemp()
            
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(temp_extract)
            
            # Güncelleme batch dosyası oluştur
            update_script = os.path.join(tempfile.gettempdir(), 'taxclip_update.bat')
            
            # Çıkartılan klasörü bul
            extracted_folders = list(Path(temp_extract).iterdir())
            source_dir = str(extracted_folders[0]) if extracted_folders else temp_extract
            
            with open(update_script, 'w') as f:
                f.write('@echo off\n')
                f.write('echo Guncelleme yapiliyor...\n')
                f.write('timeout /t 2 /nobreak > nul\n')
                f.write(f'xcopy /E /Y /I "{source_dir}\\*" "{app_dir}"\n')
                f.write('echo Guncelleme tamamlandi!\n')
                f.write(f'start "" "{sys.executable}" "{app_dir}\\main.py"\n')
                f.write(f'rmdir /S /Q "{temp_extract}"\n')
                f.write(f'del "%~f0"\n')
            
            subprocess.Popen(['cmd', '/c', update_script], shell=True)
            return True
            
        return False
        
    except Exception as e:
        print(f"[UPDATER] Güncelleme uygulama hatası: {e}")
        return False


class Updater(QObject):
    """Ana güncelleme yöneticisi"""
    
    update_available = Signal(dict)
    update_progress = Signal(int)
    update_finished = Signal()
    update_failed = Signal(str)
    
    REPO_OWNER = "taxperia"  # GitHub kullanıcı adı
    REPO_NAME = "taxclip"    # GitHub repo adı
    
    def __init__(self, settings=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.current_version = get_current_version()
        self._checker_thread = None
        self._downloader_thread = None
        self._pending_update = None
    
    def check_for_updates(self, silent: bool = False):
        """Güncelleme kontrolü başlat"""
        if self._checker_thread and self._checker_thread.isRunning():
            return
        
        self._checker_thread = UpdateChecker(
            self.REPO_OWNER,
            self.REPO_NAME,
            self.current_version
        )
        self._checker_thread.update_available.connect(self._on_update_available)
        
        if not silent:
            self._checker_thread.check_failed.connect(self._on_check_failed)
            self._checker_thread.no_update.connect(self._on_no_update)
        
        self._checker_thread.start()
    
    def _on_update_available(self, update_info: dict):
        """Güncelleme bulundu"""
        self._pending_update = update_info
        self.update_available.emit(update_info)
    
    def _on_check_failed(self, error: str):
        """Kontrol başarısız"""
        self.update_failed.emit(f"Güncelleme kontrolü başarısız: {error}")
    
    def _on_no_update(self):
        """Güncelleme yok"""
        pass
    
    def download_and_install(self, update_info: dict = None):
        """Güncellemeyi indir ve kur"""
        if update_info is None:
            update_info = self._pending_update
        
        if not update_info or not update_info.get('download_url'):
            self.update_failed.emit("İndirme URL'si bulunamadı")
            return
        
        if self._downloader_thread and self._downloader_thread.isRunning():
            return
        
        self._downloader_thread = UpdateDownloader(update_info['download_url'])
        self._downloader_thread.progress.connect(self.update_progress.emit)
        self._downloader_thread.finished.connect(self._on_download_finished)
        self._downloader_thread.failed.connect(self.update_failed.emit)
        self._downloader_thread.start()
    
    def _on_download_finished(self, file_path: str):
        """İndirme tamamlandı"""
        if apply_update(file_path):
            self.update_finished.emit()
            # Uygulamayı kapat
            from PySide6.QtWidgets import QApplication
            QApplication.quit()
        else:
            self.update_failed.emit("Güncelleme uygulanamadı")


def show_update_dialog(parent, update_info: dict, updater: Updater) -> bool:
    """Güncelleme dialogu göster"""
    from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit
    
    dialog = QDialog(parent)
    dialog.setWindowTitle("🔄 Güncelleme Mevcut")
    dialog.setMinimumWidth(450)
    dialog.setModal(True)
    
    layout = QVBoxLayout(dialog)
    
    # Başlık
    title_label = QLabel(f"<h3>TaxClip v{update_info['version']} hazır!</h3>")
    layout.addWidget(title_label)
    
    # Mevcut versiyon
    current_label = QLabel(f"Mevcut versiyon: v{updater.current_version}")
    current_label.setStyleSheet("color: gray;")
    layout.addWidget(current_label)
    
    # Release notes
    if update_info.get('release_notes'):
        notes_label = QLabel("<b>Yenilikler:</b>")
        layout.addWidget(notes_label)
        
        notes_text = QTextEdit()
        notes_text.setReadOnly(True)
        notes_text.setPlainText(update_info['release_notes'])
        notes_text.setMaximumHeight(150)
        layout.addWidget(notes_text)
    
    # Butonlar
    btn_layout = QHBoxLayout()
    
    btn_later = QPushButton("Daha Sonra")
    btn_later.clicked.connect(dialog.reject)
    btn_layout.addWidget(btn_later)
    
    btn_layout.addStretch()
    
    btn_update = QPushButton("🔄 Şimdi Güncelle")
    btn_update.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
    btn_update.clicked.connect(dialog.accept)
    btn_layout.addWidget(btn_update)
    
    layout.addLayout(btn_layout)
    
    if dialog.exec() == QDialog.Accepted:
        # Progress dialog
        progress = QProgressDialog("Güncelleme indiriliyor...", "İptal", 0, 100, parent)
        progress.setWindowTitle("Güncelleme")
        progress.setWindowModality(Qt.WindowModal)
        progress.setAutoClose(True)
        progress.setMinimumDuration(0)
        
        updater.update_progress.connect(progress.setValue)
        updater.update_finished.connect(progress.accept)
        updater.update_failed.connect(lambda msg: QMessageBox.critical(parent, "Hata", msg))
        
        updater.download_and_install(update_info)
        progress.exec()
        
        return True
    
    return False
