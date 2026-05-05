"""
Hassas Veri Algılama ve Maskeleme
Kredi kartı, şifre, email vb. hassas bilgileri tespit eder
"""
import re
from typing import Tuple, List, Dict


class SensitiveDataDetector:
    """Hassas veri algılama ve maskeleme"""
    
    # Regex patterns
    CREDIT_CARD_PATTERN = re.compile(
        r'\b(?:\d{4}[-\s]?){3}\d{4}\b'  # 1234-5678-9012-3456 veya 1234567890123456
    )
    
    CVV_PATTERN = re.compile(
        r'\b\d{3,4}\b'  # 3-4 haneli sayılar (CVV olabilir)
    )
    
    # Yaygın şifre kalıpları
    PASSWORD_PATTERNS = [
        re.compile(r'password\s*[:=]\s*[^\s]+', re.IGNORECASE),
        re.compile(r'pass\s*[:=]\s*[^\s]+', re.IGNORECASE),
        re.compile(r'pwd\s*[:=]\s*[^\s]+', re.IGNORECASE),
        re.compile(r'şifre\s*[:=]\s*[^\s]+', re.IGNORECASE),
        re.compile(r'parola\s*[:=]\s*[^\s]+', re.IGNORECASE),
    ]
    
    # API Keys / Tokens
    API_KEY_PATTERN = re.compile(
        r'(?:api[_-]?key|api[_-]?token|access[_-]?token|secret[_-]?key)\s*[:=]\s*[\'"]?([a-zA-Z0-9_\-]{20,})[\'"]?',
        re.IGNORECASE
    )
    
    # Email adresleri
    EMAIL_PATTERN = re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    )
    
    # Telefon numaraları (Türkiye)
    PHONE_PATTERN = re.compile(
        r'(?:\+90|0)?[\s\-]?\(?5\d{2}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}'
    )
    
    # TC Kimlik No
    TC_ID_PATTERN = re.compile(
        r'\b[1-9]\d{10}\b'
    )
    
    # IBAN
    IBAN_PATTERN = re.compile(
        r'\bTR\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{2}\b',
        re.IGNORECASE
    )
    
    def __init__(self, settings=None):
        self.settings = settings
        self.enabled = settings.get("sensitive_data_detection", True) if settings else True
        self.mask_credit_cards = settings.get("mask_credit_cards", True) if settings else True
        self.mask_passwords = settings.get("mask_passwords", True) if settings else True
        self.mask_api_keys = settings.get("mask_api_keys", True) if settings else True
        self.mask_emails = settings.get("mask_emails", False) if settings else False
        self.mask_phones = settings.get("mask_phones", False) if settings else False
        self.mask_tc_ids = settings.get("mask_tc_ids", True) if settings else True
        self.mask_ibans = settings.get("mask_ibans", True) if settings else True
        self.block_sensitive = settings.get("block_sensitive_data", False) if settings else False
    
    def detect_sensitive_data(self, text: str) -> Dict[str, List[str]]:
        """
        Metindeki hassas verileri tespit et
        
        Returns:
            Dict of detected sensitive data types and their values
        """
        if not self.enabled or not text:
            return {}
        
        detected = {}
        
        # Kredi kartı
        if self.mask_credit_cards:
            cards = self.CREDIT_CARD_PATTERN.findall(text)
            if cards:
                # Luhn algoritması ile doğrula
                valid_cards = [card for card in cards if self._validate_luhn(card)]
                if valid_cards:
                    detected['credit_cards'] = valid_cards
        
        # Şifreler
        if self.mask_passwords:
            passwords = []
            for pattern in self.PASSWORD_PATTERNS:
                matches = pattern.findall(text)
                passwords.extend(matches)
            if passwords:
                detected['passwords'] = passwords
        
        # API Keys
        if self.mask_api_keys:
            api_keys = self.API_KEY_PATTERN.findall(text)
            if api_keys:
                detected['api_keys'] = api_keys
        
        # Email
        if self.mask_emails:
            emails = self.EMAIL_PATTERN.findall(text)
            if emails:
                detected['emails'] = emails
        
        # Telefon
        if self.mask_phones:
            phones = self.PHONE_PATTERN.findall(text)
            if phones:
                detected['phones'] = phones
        
        # TC Kimlik
        if self.mask_tc_ids:
            tc_ids = self.TC_ID_PATTERN.findall(text)
            # 11 haneli ve Luhn kontrolü
            valid_tc = [tc for tc in tc_ids if len(tc) == 11 and self._validate_tc_id(tc)]
            if valid_tc:
                detected['tc_ids'] = valid_tc
        
        # IBAN
        if self.mask_ibans:
            ibans = self.IBAN_PATTERN.findall(text)
            if ibans:
                detected['ibans'] = ibans
        
        return detected
    
    def should_block(self, text: str) -> Tuple[bool, str]:
        """
        Bu metin kaydedilmemeli mi?
        
        Returns:
            (block: bool, reason: str)
        """
        if not self.block_sensitive:
            return False, ""
        
        detected = self.detect_sensitive_data(text)
        
        if not detected:
            return False, ""
        
        # Hangi türler tespit edildi
        types = []
        if 'credit_cards' in detected:
            types.append("kredi kartı")
        if 'passwords' in detected:
            types.append("şifre")
        if 'api_keys' in detected:
            types.append("API key")
        if 'emails' in detected:
            types.append("email")
        if 'phones' in detected:
            types.append("telefon")
        if 'tc_ids' in detected:
            types.append("TC kimlik")
        if 'ibans' in detected:
            types.append("IBAN")
        
        if types:
            reason = f"Hassas veri tespit edildi: {', '.join(types)}"
            return True, reason
        
        return False, ""
    
    def mask_text(self, text: str) -> Tuple[str, bool]:
        """
        Metindeki hassas verileri maskele
        
        Returns:
            (masked_text, was_masked)
        """
        if not self.enabled or not text:
            return text, False
        
        detected = self.detect_sensitive_data(text)
        
        if not detected:
            return text, False
        
        masked_text = text
        
        # Kredi kartlarını maskele
        if 'credit_cards' in detected:
            for card in detected['credit_cards']:
                masked = self._mask_credit_card(card)
                masked_text = masked_text.replace(card, masked)
        
        # Şifreleri maskele
        if 'passwords' in detected:
            for pwd in detected['passwords']:
                masked = self._mask_password(pwd)
                masked_text = masked_text.replace(pwd, masked)
        
        # API Keys
        if 'api_keys' in detected:
            for key in detected['api_keys']:
                masked = f"{'*' * len(key)}"
                masked_text = masked_text.replace(key, masked)
        
        # Email
        if 'emails' in detected:
            for email in detected['emails']:
                masked = self._mask_email(email)
                masked_text = masked_text.replace(email, masked)
        
        # Telefon
        if 'phones' in detected:
            for phone in detected['phones']:
                masked = self._mask_phone(phone)
                masked_text = masked_text.replace(phone, masked)
        
        # TC Kimlik
        if 'tc_ids' in detected:
            for tc_id in detected['tc_ids']:
                masked = f"{tc_id[:2]}{'*' * 7}{tc_id[-2:]}"
                masked_text = masked_text.replace(tc_id, masked)
        
        # IBAN
        if 'ibans' in detected:
            for iban in detected['ibans']:
                masked = f"TR** **** **** **** **** **** {iban[-2:]}"
                masked_text = masked_text.replace(iban.replace(' ', ''), masked)
        
        return masked_text, True
    
    def _mask_credit_card(self, card: str) -> str:
        """Kredi kartı numarasını maskele"""
        # Sadece son 4 haneyi göster
        digits = re.sub(r'[\s\-]', '', card)
        return f"**** **** **** {digits[-4:]}"
    
    def _mask_password(self, pwd_text: str) -> str:
        """Şifre içeren metni maskele"""
        # "password: 12345" -> "password: *****"
        parts = pwd_text.split(':', 1)
        if len(parts) == 2:
            return f"{parts[0]}: {'*' * 8}"
        parts = pwd_text.split('=', 1)
        if len(parts) == 2:
            return f"{parts[0]}= {'*' * 8}"
        return '*' * 8
    
    def _mask_email(self, email: str) -> str:
        """Email adresini maskele"""
        parts = email.split('@')
        if len(parts) != 2:
            return email
        username = parts[0]
        domain = parts[1]
        
        if len(username) <= 2:
            masked_user = '*' * len(username)
        else:
            masked_user = username[0] + '*' * (len(username) - 2) + username[-1]
        
        return f"{masked_user}@{domain}"
    
    def _mask_phone(self, phone: str) -> str:
        """Telefon numarasını maskele"""
        digits = re.sub(r'[\s\-\(\)\+]', '', phone)
        if len(digits) >= 7:
            return f"*** *** {digits[-4:]}"
        return '*' * len(digits)
    
    def _validate_luhn(self, card_number: str) -> bool:
        """Luhn algoritması ile kredi kartı doğrulama"""
        try:
            digits = [int(d) for d in re.sub(r'[\s\-]', '', card_number)]
            checksum = 0
            reverse_digits = digits[::-1]
            
            for i, digit in enumerate(reverse_digits):
                if i % 2 == 1:
                    digit *= 2
                    if digit > 9:
                        digit -= 9
                checksum += digit
            
            return checksum % 10 == 0
        except:
            return False
    
    def _validate_tc_id(self, tc_id: str) -> bool:
        """TC Kimlik No doğrulama"""
        try:
            if len(tc_id) != 11:
                return False
            
            digits = [int(d) for d in tc_id]
            
            # İlk hane 0 olamaz
            if digits[0] == 0:
                return False
            
            # 10. hane kontrolü
            sum_odd = sum(digits[0:9:2])
            sum_even = sum(digits[1:8:2])
            if (sum_odd * 7 - sum_even) % 10 != digits[9]:
                return False
            
            # 11. hane kontrolü
            if sum(digits[0:10]) % 10 != digits[10]:
                return False
            
            return True
        except:
            return False


# Global instance
_detector: SensitiveDataDetector = None


def get_sensitive_detector(settings=None) -> SensitiveDataDetector:
    """Global detector instance'ını döndür"""
    global _detector
    if _detector is None or settings is not None:
        _detector = SensitiveDataDetector(settings)
    return _detector


def contains_sensitive_data(text: str, settings=None) -> bool:
    """Metin mevcut ayarlara göre hassas veri içeriyor mu?"""
    if not text:
        return False
    detector = SensitiveDataDetector(settings)
    return bool(detector.detect_sensitive_data(text))


def requires_sensitive_access(settings, text: str) -> bool:
    """Hassas veri gösterimi için erişim doğrulaması gerekli mi?"""
    if not settings or not settings.get("totp_for_sensitive", False):
        return False
    return contains_sensitive_data(text, settings)


def ensure_sensitive_access(settings, text: str, parent_widget=None) -> bool:
    """Gerekliyse TOTP doğrulaması isteyerek erişimi kontrol et."""
    if not requires_sensitive_access(settings, text):
        return True
    return verify_totp_for_sensitive(settings, parent_widget)


def verify_totp_for_sensitive(settings, parent_widget=None) -> bool:
    """
    Hassas veri göstermek için TOTP doğrulaması yap
    
    Returns:
        True: Doğrulama başarılı veya TOTP kapalı
        False: Doğrulama başarısız
    """
    if not settings:
        return True
    
    # TOTP hassas veri için aktif mi?
    if not settings.get("totp_for_sensitive", False):
        return True
    
    # TOTP kurulu mu?
    try:
        from .totp_manager import TOTPManager
        totp = TOTPManager(settings)
        
        if not totp.is_enabled():
            return True
        
        # Doğrulama dialogu göster
        from .ui.totp_dialog import TOTPVerifyDialog
        dialog = TOTPVerifyDialog(settings, parent_widget, "Hassas Veri Erişimi")
        
        if dialog.exec() and dialog.is_verified():
            return True
        
        return False
    
    except Exception as e:
        print(f"[SENSITIVE] TOTP doğrulama hatası: {e}")
        return True  # Hata durumunda erişime izin ver
