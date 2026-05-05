"""
Google Drive Sync - OAuth 2.0 ile Google Drive senkronizasyonu
"""
import os
import json
import webbrowser
from pathlib import Path
from datetime import datetime

# Google OAuth kütüphaneleri
GOOGLE_AVAILABLE = False
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
    GOOGLE_AVAILABLE = True
except ImportError:
    pass


class GoogleDriveSync:
    """Google Drive senkronizasyon yöneticisi"""
    
    # OAuth 2.0 scopes
    SCOPES = ['https://www.googleapis.com/auth/drive.file']
    
    # OAuth bilgileri kaynak koda yazılmamalıdır.
    # Ortam değişkenleri: TAXCLIP_GOOGLE_CLIENT_ID / TAXCLIP_GOOGLE_CLIENT_SECRET
    # Alternatif: connect(credentials_json=...) ile Google credentials JSON verilebilir.
    CLIENT_ID = ""
    CLIENT_SECRET = ""
    CLIENT_ID_ENV = "TAXCLIP_GOOGLE_CLIENT_ID"
    CLIENT_SECRET_ENV = "TAXCLIP_GOOGLE_CLIENT_SECRET"
    
    def __init__(self, settings=None):
        self.settings = settings
        self.credentials = None
        self.service = None
        
        # Token ve credentials dosya yolları
        self.app_data_dir = Path.home() / ".taxclip"
        self.app_data_dir.mkdir(parents=True, exist_ok=True)
        
        self.token_path = self.app_data_dir / "google_token.json"
        self.credentials_path = self.app_data_dir / "google_credentials.json"
        
        # TaxClip folder ID (Google Drive'da)
        self.folder_id = None
    
    @staticmethod
    def is_available() -> bool:
        """Google API kütüphaneleri yüklü mü?"""
        return GOOGLE_AVAILABLE

    def _setting_value(self, key: str) -> str:
        if not self.settings:
            return ""
        try:
            return str(self.settings.get(key, "") or "").strip()
        except Exception:
            return ""

    def _load_client_config(self, credentials_json: str = None) -> dict:
        if credentials_json:
            try:
                client_config = json.loads(credentials_json) if isinstance(credentials_json, str) else credentials_json
            except json.JSONDecodeError as exc:
                raise ValueError("Google OAuth credentials JSON geçersiz.") from exc

            if not isinstance(client_config, dict) or not any(key in client_config for key in ("installed", "web")):
                raise ValueError("Google OAuth credentials JSON 'installed' veya 'web' bölümü içermeli.")
            return client_config

        client_id = (
            os.environ.get(self.CLIENT_ID_ENV, "").strip()
            or self._setting_value("google_client_id")
            or self.CLIENT_ID
        )
        client_secret = (
            os.environ.get(self.CLIENT_SECRET_ENV, "").strip()
            or self._setting_value("google_client_secret")
            or self.CLIENT_SECRET
        )

        if not client_id or not client_secret:
            raise ValueError(
                "Google OAuth bilgileri yapılandırılmamış. "
                "TAXCLIP_GOOGLE_CLIENT_ID ve TAXCLIP_GOOGLE_CLIENT_SECRET ortam değişkenlerini ayarlayın "
                "veya credentials_json parametresi verin."
            )

        return {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "redirect_uris": ["http://localhost"],
            }
        }
    
    def is_connected(self) -> bool:
        """Google Drive'a bağlı mı?"""
        if not GOOGLE_AVAILABLE:
            return False
        
        if self.credentials and self.credentials.valid:
            return True
        
        # Token dosyası var mı kontrol et
        if self.token_path.exists():
            try:
                self.credentials = Credentials.from_authorized_user_file(
                    str(self.token_path), self.SCOPES
                )
                return self.credentials.valid
            except:
                return False
        
        return False
    
    def connect(self, credentials_json: str = None) -> tuple[bool, str]:
        """
        Google Drive'a bağlan (OAuth 2.0)
        
        Args:
            credentials_json: Google Cloud Console'dan alınan credentials.json içeriği (opsiyonel)
        
        Returns:
            (success, message)
        """
        if not GOOGLE_AVAILABLE:
            return False, "Google API kütüphaneleri yüklü değil. Lütfen şu komutu çalıştırın:\npip install google-auth-oauthlib google-api-python-client"
        
        try:
            # Mevcut token'ı kontrol et
            if self.token_path.exists():
                try:
                    self.credentials = Credentials.from_authorized_user_file(
                        str(self.token_path), self.SCOPES
                    )
                except Exception:
                    self.credentials = None
            
            # Token geçersiz veya süresi dolmuş
            if not self.credentials or not self.credentials.valid:
                if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                    # Token'ı yenile
                    self.credentials.refresh(Request())
                else:
                    client_config = self._load_client_config(credentials_json)
                    
                    flow = InstalledAppFlow.from_client_config(client_config, self.SCOPES)
                    # Timeout ekleyerek donmayı önle
                    try:
                        self.credentials = flow.run_local_server(
                            port=0, 
                            open_browser=True,
                            timeout_seconds=120  # 2 dakika timeout
                        )
                    except Exception as auth_error:
                        error_msg = str(auth_error)
                        if "access_denied" in error_msg.lower():
                            return False, "Erişim reddedildi. Google Cloud Console'da OAuth Consent Screen'de kendinizi test kullanıcısı olarak ekleyin."
                        return False, f"Yetkilendirme hatası: {error_msg}"
                
                # Token'ı kaydet
                with open(self.token_path, 'w') as token:
                    token.write(self.credentials.to_json())
            
            # Drive API servisini oluştur
            self.service = build('drive', 'v3', credentials=self.credentials)
            
            # TaxClip klasörünü bul/oluştur
            self._ensure_folder()
            
            # Settings'e kaydet
            if self.settings:
                self.settings.set("gdrive_connected", True)
                self.settings.save()
            
            return True, "Google Drive'a başarıyla bağlandı!"
        
        except Exception as e:
            return False, f"Bağlantı hatası: {str(e)}"
    
    def disconnect(self) -> tuple[bool, str]:
        """Google Drive bağlantısını kes"""
        try:
            # Token dosyasını sil
            if self.token_path.exists():
                self.token_path.unlink()
            
            self.credentials = None
            self.service = None
            self.folder_id = None
            
            if self.settings:
                self.settings.set("gdrive_connected", False)
                self.settings.save()
            
            return True, "Bağlantı kesildi"
        except Exception as e:
            return False, f"Bağlantı kesme hatası: {str(e)}"
    
    def _ensure_folder(self):
        """TaxClip klasörünü Google Drive'da oluştur/bul"""
        if not self.service:
            return
        
        try:
            # TaxClip klasörünü ara
            results = self.service.files().list(
                q="name='TaxClip' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            files = results.get('files', [])
            
            if files:
                self.folder_id = files[0]['id']
            else:
                # Klasör oluştur
                file_metadata = {
                    'name': 'TaxClip',
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                folder = self.service.files().create(
                    body=file_metadata,
                    fields='id'
                ).execute()
                self.folder_id = folder.get('id')
            
            print(f"[GDRIVE] TaxClip folder ID: {self.folder_id}")
        except Exception as e:
            print(f"[GDRIVE] Klasör hatası: {e}")
    
    def upload_backup(self, json_data: str, filename: str = None) -> tuple[bool, str]:
        """
        JSON yedek dosyasını Google Drive'a yükle
        
        Args:
            json_data: JSON string
            filename: Dosya adı (opsiyonel)
        
        Returns:
            (success, message/file_id)
        """
        if not self.service:
            return False, "Google Drive'a bağlı değil"
        
        try:
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"taxclip_backup_{timestamp}.json"
            
            # Geçici dosya oluştur
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
                tmp.write(json_data)
                tmp_path = tmp.name
            
            file_metadata = {
                'name': filename,
                'parents': [self.folder_id] if self.folder_id else []
            }
            
            media = MediaFileUpload(tmp_path, mimetype='application/json')
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            # Geçici dosyayı sil
            os.unlink(tmp_path)
            
            return True, file.get('id')
        
        except Exception as e:
            return False, f"Yükleme hatası: {str(e)}"
    
    def list_backups(self) -> list:
        """Google Drive'daki yedekleri listele"""
        if not self.service:
            return []
        
        try:
            query = f"'{self.folder_id}' in parents and trashed=false" if self.folder_id else "trashed=false"
            
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name, createdTime, size)',
                orderBy='createdTime desc'
            ).execute()
            
            return results.get('files', [])
        except Exception as e:
            print(f"[GDRIVE] Liste hatası: {e}")
            return []
    
    def download_backup(self, file_id: str) -> tuple[bool, str]:
        """
        Yedek dosyasını indir
        
        Returns:
            (success, json_data or error_message)
        """
        if not self.service:
            return False, "Google Drive'a bağlı değil"
        
        try:
            import io
            
            request = self.service.files().get_media(fileId=file_id)
            file_stream = io.BytesIO()
            downloader = MediaIoBaseDownload(file_stream, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            file_stream.seek(0)
            json_data = file_stream.read().decode('utf-8')
            
            return True, json_data
        
        except Exception as e:
            return False, f"İndirme hatası: {str(e)}"
    
    def delete_backup(self, file_id: str) -> tuple[bool, str]:
        """Yedek dosyasını sil"""
        if not self.service:
            return False, "Google Drive'a bağlı değil"
        
        try:
            self.service.files().delete(fileId=file_id).execute()
            return True, "Dosya silindi"
        except Exception as e:
            return False, f"Silme hatası: {str(e)}"


# Test fonksiyonu
if __name__ == "__main__":
    sync = GoogleDriveSync()
    print(f"Google API available: {sync.is_available()}")
    print(f"Connected: {sync.is_connected()}")
