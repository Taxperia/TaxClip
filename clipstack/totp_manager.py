"""
TOTP Manager - Google Authenticator uyumlu 2FA sistemi
"""
import os
import base64
import hashlib
from pathlib import Path
from typing import Optional, Tuple

# TOTP kütüphanesi
TOTP_AVAILABLE = False
try:
    import pyotp
    TOTP_AVAILABLE = True
except ImportError:
    pass

# QR kod kütüphanesi
QRCODE_AVAILABLE = False
try:
    import qrcode
    from io import BytesIO
    QRCODE_AVAILABLE = True
except ImportError:
    pass

TOTP_KDF_ITERATIONS = 210000


class TOTPManager:
    """Google Authenticator uyumlu TOTP yöneticisi"""
    
    APP_NAME = "TaxClip"
    
    def __init__(self, settings=None):
        self.settings = settings
        self._secret = None
        
        # Secret dosya yolu
        self.app_data_dir = Path.home() / ".taxclip"
        self.app_data_dir.mkdir(parents=True, exist_ok=True)
        self.secret_path = self.app_data_dir / ".totp_secret"
    
    @staticmethod
    def is_available() -> bool:
        """TOTP kütüphanesi yüklü mü?"""
        return TOTP_AVAILABLE
    
    @staticmethod
    def is_qrcode_available() -> bool:
        """QR kod kütüphanesi yüklü mü?"""
        return QRCODE_AVAILABLE
    
    def is_enabled(self) -> bool:
        """TOTP aktif mi?"""
        if self.settings:
            return self.settings.get("totp_enabled", False) and self.secret_path.exists()
        return self.secret_path.exists()
    
    def get_secret(self) -> Optional[str]:
        """Kayıtlı secret'ı al"""
        if self._secret:
            return self._secret
        
        if self.secret_path.exists():
            try:
                # Secret dosyasını oku ve decrypt et
                encrypted = self.secret_path.read_bytes()
                self._secret = self._decrypt_secret(encrypted)
                return self._secret
            except Exception:
                return None
        return None
    
    def generate_secret(self) -> str:
        """Yeni TOTP secret oluştur"""
        if not TOTP_AVAILABLE:
            raise RuntimeError("pyotp kütüphanesi yüklü değil")
        
        self._secret = pyotp.random_base32()
        return self._secret
    
    def save_secret(self, secret: str) -> bool:
        """Secret'ı kaydet"""
        try:
            # Secret'ı encrypt et ve kaydet
            encrypted = self._encrypt_secret(secret)
            self.secret_path.write_bytes(encrypted)
            self._secret = secret
            
            if self.settings:
                self.settings.set("totp_enabled", True)
                self.settings.save()
            
            return True
        except Exception as e:
            print(f"[TOTP] Secret kaydetme hatası: {e}")
            return False
    
    def disable(self) -> bool:
        """TOTP'yi devre dışı bırak"""
        try:
            if self.secret_path.exists():
                self.secret_path.unlink()
            
            self._secret = None
            
            if self.settings:
                self.settings.set("totp_enabled", False)
                self.settings.save()
            
            return True
        except Exception as e:
            print(f"[TOTP] Devre dışı bırakma hatası: {e}")
            return False
    
    def get_provisioning_uri(self, email: str = "user@taxclip.app") -> str:
        """Google Authenticator için QR kod URI'si oluştur"""
        if not TOTP_AVAILABLE:
            return ""
        
        secret = self.get_secret() or self.generate_secret()
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name=email, issuer_name=self.APP_NAME)
    
    def get_qrcode_image(self, email: str = "user@taxclip.app") -> Optional[bytes]:
        """QR kod görüntüsü oluştur (PNG bytes)"""
        if not TOTP_AVAILABLE or not QRCODE_AVAILABLE:
            return None
        
        try:
            uri = self.get_provisioning_uri(email)
            
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(uri)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            return buffer.getvalue()
        
        except Exception as e:
            print(f"[TOTP] QR kod oluşturma hatası: {e}")
            return None
    
    def verify(self, code: str) -> bool:
        """TOTP kodunu doğrula"""
        if not TOTP_AVAILABLE:
            return False
        
        secret = self.get_secret()
        if not secret:
            return False
        
        try:
            totp = pyotp.TOTP(secret)
            # 30 saniyelik pencere ile doğrula (1 önceki ve 1 sonraki kod da geçerli)
            return totp.verify(code, valid_window=1)
        except Exception as e:
            print(f"[TOTP] Doğrulama hatası: {e}")
            return False
    
    def get_current_code(self) -> Optional[str]:
        """Mevcut TOTP kodunu al (test için)"""
        if not TOTP_AVAILABLE:
            return None
        
        secret = self.get_secret()
        if not secret:
            return None
        
        try:
            totp = pyotp.TOTP(secret)
            return totp.now()
        except:
            return None
    
    def _encrypt_secret(self, secret: str) -> bytes:
        """Secret'ı AES-256 ile güvenli şekilde şifrele"""
        try:
            from Crypto.Cipher import AES
            from Crypto.Random import get_random_bytes
        except ImportError:
            raise RuntimeError("PyCryptodome is required for TOTP secret encryption")

        # Makine bazlı şifre oluştur
        machine_id = self._get_machine_id()
        salt = get_random_bytes(16)

        # PBKDF2 ile güvenli key türet
        key = self._derive_machine_key(
            machine_id,
            salt,
        )

        # AES-GCM ile şifrele
        nonce = get_random_bytes(12)
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(secret.encode('utf-8'))

        # Format: salt(16) + nonce(12) + tag(16) + ciphertext
        result = salt + nonce + tag + ciphertext
        return base64.b64encode(result)
    
    def _decrypt_secret(self, encrypted: bytes) -> str:
        """Şifrelenmiş secret'ı çöz"""
        raw = base64.b64decode(encrypted)

        try:
            from Crypto.Cipher import AES
        except ImportError as exc:
            raise RuntimeError("PyCryptodome is required for TOTP secret decryption") from exc

        if len(raw) < 44:
            raise ValueError("Unsupported TOTP secret format")

        # AES-GCM format: salt(16) + nonce(12) + tag(16) + ciphertext
        salt = raw[:16]
        nonce = raw[16:28]
        tag = raw[28:44]
        ciphertext = raw[44:]

        machine_id = self._get_machine_id()
        key = self._derive_machine_key(
            machine_id,
            salt,
        )

        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        return plaintext.decode('utf-8')
    
    def _get_machine_id(self) -> str:
        """Makine bazlı benzersiz ID al"""
        try:
            import platform
            import uuid
            
            # Kombinasyon: hostname + mac address
            hostname = platform.node()
            mac = uuid.getnode()
            
            return f"{hostname}-{mac}"
        except:
            return "taxclip-default-key"

    def _derive_machine_key(self, machine_id: str, salt: bytes) -> bytes:
        """PBKDF2-HMAC-SHA256 ile TOTP secret encryption anahtarı türet."""
        return hashlib.pbkdf2_hmac(
            "sha256",
            machine_id.encode("utf-8"),
            salt,
            TOTP_KDF_ITERATIONS,
            dklen=32,
        )
