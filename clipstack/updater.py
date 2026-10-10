"""
GitHub Updater - Uygulama güncellemelerini kontrol eder ve yükler
"""
import os
import sys
import json
import tempfile
import shutil
import subprocess
import re
from pathlib import Path
from typing import Optional, Tuple, Dict
from urllib.parse import urlparse, unquote
from PySide6.QtCore import QObject, Signal, QThread
from PySide6.QtWidgets import QMessageBox, QProgressDialog
from PySide6.QtCore import Qt
from . import __version__

MAX_UPDATE_BYTES = 512 * 1024 * 1024
MAX_CHECKSUM_BYTES = 1024 * 1024
# Yeni sertifikaya geçişte, eski sürüm yayımlanmadan önce yeni sertifikanın
# SHA-256 parmak izi bu kümeye eklenebilir.
TRUSTED_UPDATE_SIGNER_SHA256 = frozenset()

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
    
    def __init__(self, download_url: str, sha256_url: str = None, sha256_expected: str = None, parent=None):
        super().__init__(parent)
        self.download_url = download_url
        self.sha256_url = sha256_url
        self.sha256_expected = sha256_expected
    
    def run(self):
        try:
            file_path = download_update(
                self.download_url,
                self._on_progress,
                sha256_url=self.sha256_url,
                sha256_expected=self.sha256_expected,
            )
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
            _validate_download_url(response.url)
            data = response.json()
        else:
            req = urllib.request.Request(api_url, headers={'User-Agent': 'TaxClip-Updater'})
            with urllib.request.urlopen(req, timeout=10) as response:
                _validate_download_url(response.geturl())
                data = json.loads(response.read().decode('utf-8'))
        
        remote_version = data.get('tag_name', '').lstrip('v')
        
        if not remote_version:
            return None
        
        if not is_newer_version(remote_version, current_version):
            return None
        
        # Yalnızca Authenticode ile doğrulanabilen Windows EXE paketini ve
        # isteğe bağlı sha256 asset'ini bul.
        download_url = None
        sha256_url = None
        sha256_expected = None
        assets = data.get('assets', [])

        for asset in assets:
            name = asset.get('name', '').lower()
            url = asset.get('browser_download_url')
            if name.endswith('.sha256') or name.endswith('.sha256.txt'):
                sha256_url = url
            elif name.endswith('.exe'):
                if download_url is None:
                    download_url = url

        if not download_url:
            return None

        # Release body içinde SHA256 satırı varsa yakala
        body = data.get('body', '') or ''
        for line in body.splitlines():
            line = line.strip()
            # örn: SHA256: abc... veya abc...  TaxClip.exe
            if line.lower().startswith('sha256:'):
                sha256_expected = line.split(':', 1)[1].strip().split()[0]
                break
            parts = line.split()
            if len(parts) >= 1 and len(parts[0]) == 64 and all(c in '0123456789abcdef' for c in parts[0].lower()):
                sha256_expected = parts[0].lower()
                break
        
        return {
            'version': remote_version,
            'download_url': download_url,
            'sha256_url': sha256_url,
            'sha256_expected': sha256_expected,
            'release_notes': body,
            'published_at': data.get('published_at', ''),
            'html_url': data.get('html_url', ''),
        }
        
    except Exception as e:
        print(f"[UPDATER] Güncelleme kontrolü hatası: {e}")
        return None


def _fetch_text(url: str) -> str:
    _validate_download_url(url)
    if REQUESTS_AVAILABLE:
        response = requests.get(url, timeout=30, stream=True)
        response.raise_for_status()
        _validate_download_url(response.url)
        declared_size = int(response.headers.get('content-length', 0) or 0)
        if declared_size < 0 or declared_size > MAX_CHECKSUM_BYTES:
            raise ValueError("SHA256 dosyası izin verilen boyutu aşıyor.")
        content = bytearray()
        for chunk in response.iter_content(chunk_size=8192):
            if not chunk:
                continue
            content.extend(chunk)
            if len(content) > MAX_CHECKSUM_BYTES:
                raise ValueError("SHA256 dosyası izin verilen boyutu aşıyor.")
        return bytes(content).decode('utf-8', errors='replace')
    req = urllib.request.Request(url, headers={'User-Agent': 'TaxClip-Updater'})
    with urllib.request.urlopen(req, timeout=30) as response:
        _validate_download_url(response.geturl())
        content = response.read(MAX_CHECKSUM_BYTES + 1)
        if len(content) > MAX_CHECKSUM_BYTES:
            raise ValueError("SHA256 dosyası izin verilen boyutu aşıyor.")
        return content.decode('utf-8', errors='replace')


def _parse_sha256_file(content: str, expected_filename: str = "") -> Optional[str]:
    """sha256 dosya içeriğinden hash çıkar."""
    fallback = None
    for line in (content or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.lower().startswith('sha256:'):
            value = line.split(':', 1)[1].strip().split()[0].lower()
            if len(value) == 64 and all(c in "0123456789abcdef" for c in value):
                fallback = fallback or value
            continue
        parts = line.split()
        if parts and len(parts[0]) == 64 and all(c in '0123456789abcdef' for c in parts[0].lower()):
            value = parts[0].lower()
            listed_name = parts[-1].lstrip("*") if len(parts) > 1 else ""
            if expected_filename and Path(listed_name).name.lower() == expected_filename.lower():
                return value
            fallback = fallback or value
    return fallback if not expected_filename else None


def _validate_download_url(url: str) -> None:
    parsed = urlparse(url or "")
    allowed_hosts = {"github.com", "api.github.com", "objects.githubusercontent.com"}
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Güncelleme adresindeki port geçersiz.") from exc
    if (
        parsed.scheme.lower() != "https"
        or (parsed.hostname or "").lower() not in allowed_hosts
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
    ):
        raise ValueError("Güncelleme yalnızca güvenilir GitHub HTTPS adreslerinden indirilebilir.")


def _safe_download_filename(download_url: str) -> str:
    name = Path(unquote(urlparse(download_url).path)).name
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.exe", name, re.IGNORECASE):
        raise ValueError("Güncelleme dosya adı veya uzantısı güvenli değil.")
    return name


def verify_file_sha256(file_path: str, expected_hash: str) -> bool:
    """Dosyanın SHA256 hash'ini doğrula."""
    import hashlib
    expected = (expected_hash or "").strip().lower()
    if not expected or len(expected) != 64:
        return False
    h = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    actual = h.hexdigest()
    return actual == expected


def _authenticode_info(file_path: str) -> tuple[str, str]:
    """Authenticode durumunu ve imzalayan sertifikanın SHA-256 izini döndür."""
    if sys.platform != "win32":
        return "", ""
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    env = os.environ.copy()
    env["TAXCLIP_UPDATE_PATH"] = str(Path(file_path).resolve())
    script = (
        "$s = Get-AuthenticodeSignature -LiteralPath $env:TAXCLIP_UPDATE_PATH; "
        "$fp = if ($s.SignerCertificate) {$s.SignerCertificate.GetCertHashString('SHA256')} else {''}; "
        "[PSCustomObject]@{Status=[string]$s.Status; Sha256=[string]$fp} "
        "| ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            [str(powershell), "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            env=env,
        )
        info = json.loads(result.stdout.strip())
        status = str(info.get("Status", ""))
        fingerprint = re.sub(r"[^0-9A-Fa-f]", "", str(info.get("Sha256", ""))).upper()
        if len(fingerprint) != 64:
            fingerprint = ""
        return status, fingerprint
    except Exception:
        return "", ""


def _trusted_update_signers() -> set[str]:
    trusted = {value.upper() for value in TRUSTED_UPDATE_SIGNER_SHA256 if value}
    configured = os.environ.get("TAXCLIP_UPDATE_SIGNER_SHA256", "")
    for value in re.split(r"[,;\s]+", configured):
        normalized = re.sub(r"[^0-9A-Fa-f]", "", value).upper()
        if len(normalized) == 64:
            trusted.add(normalized)

    # Kurulu uygulama imzalıysa güncellemenin aynı sertifikayla imzalanmasını
    # zorunlu tut. Böylece herhangi bir geçerli kod imzalama sertifikası yeterli
    # sayılmaz.
    if getattr(sys, "frozen", False):
        status, fingerprint = _authenticode_info(sys.executable)
        if status == "Valid" and fingerprint:
            trusted.add(fingerprint)
    return trusted


def verify_windows_authenticode(file_path: str) -> bool:
    """EXE imzasını ve güvenilen yayıncı sertifikasını doğrula."""
    status, fingerprint = _authenticode_info(file_path)
    return status == "Valid" and bool(fingerprint) and fingerprint in _trusted_update_signers()


def download_update(download_url: str, progress_callback=None, sha256_url: str = None, sha256_expected: str = None) -> str:
    """
    Güncelleme dosyasını indir ve mümkünse SHA256 doğrula.
    
    Returns:
        İndirilen dosyanın yolu
    """
    _validate_download_url(download_url)
    if sha256_url:
        _validate_download_url(sha256_url)
    if not sha256_expected and not sha256_url:
        raise ValueError("Güncelleme için zorunlu SHA256 doğrulama bilgisi bulunamadı.")

    temp_dir = tempfile.mkdtemp(prefix="taxclip-update-")
    filename = _safe_download_filename(download_url)
    
    file_path = os.path.join(temp_dir, filename)
    
    try:
        if REQUESTS_AVAILABLE:
            response = requests.get(download_url, stream=True, timeout=300)
            response.raise_for_status()
            _validate_download_url(response.url)
            
            total_size = int(response.headers.get('content-length', 0) or 0)
            if total_size < 0 or total_size > MAX_UPDATE_BYTES:
                raise ValueError("Güncelleme dosyası izin verilen boyutu aşıyor.")
            downloaded = 0
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if downloaded > MAX_UPDATE_BYTES:
                            raise ValueError("Güncelleme dosyası izin verilen boyutu aşıyor.")
                        if total_size and progress_callback:
                            percent = int(downloaded * 100 / total_size)
                            progress_callback(percent)
        else:
            req = urllib.request.Request(download_url, headers={'User-Agent': 'TaxClip-Updater'})
            with urllib.request.urlopen(req, timeout=300) as response:
                _validate_download_url(response.geturl())
                total_size = int(response.headers.get('Content-Length', 0) or 0)
                if total_size < 0 or total_size > MAX_UPDATE_BYTES:
                    raise ValueError("Güncelleme dosyası izin verilen boyutu aşıyor.")
                downloaded = 0
                
                with open(file_path, 'wb') as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if downloaded > MAX_UPDATE_BYTES:
                            raise ValueError("Güncelleme dosyası izin verilen boyutu aşıyor.")
                        if total_size and progress_callback:
                            percent = int(downloaded * 100 / total_size)
                            progress_callback(percent)

        # SHA256 doğrulama
        expected = sha256_expected
        if not expected and sha256_url:
            try:
                expected = _parse_sha256_file(_fetch_text(sha256_url), filename)
            except Exception as e:
                print(f"[UPDATER] SHA256 dosyası alınamadı: {e}")

        if not expected:
            raise ValueError("Güncelleme dosyasına ait SHA256 değeri doğrulanamadı.")
        if expected:
            if not verify_file_sha256(file_path, expected):
                try:
                    shutil.rmtree(temp_dir)
                except Exception:
                    pass
                raise ValueError(
                    "Güncelleme dosyası bütünlük kontrolünden geçemedi (SHA256 uyuşmazlığı). "
                    "Kurulum iptal edildi."
                )
            print("[UPDATER] SHA256 doğrulaması başarılı")

        return file_path
        
    except Exception as e:
        # Temizlik
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass
        raise e


def apply_update(file_path: str) -> bool:
    """
    Güncellemeyi uygula
    
    Windows'ta doğrulanmış EXE kurulum paketini çalıştırır.
    """
    try:
        update_path = Path(file_path).resolve(strict=True)
        if update_path.suffix.lower() == '.exe':
            if not verify_windows_authenticode(str(update_path)):
                raise ValueError("Güncelleme EXE dosyasının dijital imzası geçerli değil.")
            # Installer'ı shell olmadan çalıştır
            subprocess.Popen([str(update_path)], shell=False)
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
        
        self._downloader_thread = UpdateDownloader(
            update_info['download_url'],
            sha256_url=update_info.get('sha256_url'),
            sha256_expected=update_info.get('sha256_expected'),
        )
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
