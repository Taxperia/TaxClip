"""
Windows Hello Biometric Authentication
Parmak izi ve yüz tanıma desteği
"""
import sys
import ctypes
from ctypes import wintypes
from typing import Optional, Tuple

# Windows Hello API sabitleri
WINBIO_TYPE_FINGERPRINT = 0x00000008
WINBIO_TYPE_FACIAL_FEATURES = 0x00000020
WINBIO_TYPE_IRIS = 0x00000010
WINBIO_TYPE_VOICE = 0x00000040

WINBIO_POOL_SYSTEM = 0x00000001
WINBIO_FLAG_DEFAULT = 0x00000000

# Error codes
S_OK = 0
WINBIO_E_NOT_ACTIVE_CONSOLE = -2146861999
WINBIO_E_ENROLLMENT_IN_PROGRESS = -2146861983
WINBIO_E_UNKNOWN_ID = -2146861991


class BiometricAuth:
    """Windows Hello biometric authentication wrapper"""
    
    def __init__(self):
        self.available = False
        self.error_message = ""
        self._check_availability()
    
    def _check_availability(self):
        """Gerçek bir Windows Hello doğrulayıcısı hazır mı?"""
        # winbio.dll'nin bulunması doğrulama yapabildiğimiz anlamına gelmez.
        # Önceki sürüm yalnızca genel CredUI penceresini gösteriyor ve pencere
        # başarılı kapandığında girilen bilgiyi doğrulamadan True dönüyordu.
        # Güvenli bir UserConsentVerifier/WinBio akışı eklenene kadar özellik
        # fail-closed kalmalıdır.
        self.available = False
        self.error_message = (
            "Windows Hello bu sürümde güvenli doğrulama sağlayamadığı için devre dışı. "
            "TOTP veya veri şifreleme parolasını kullanın."
        )
    
    def is_available(self) -> bool:
        """Windows Hello kullanılabilir mi?"""
        return self.available
    
    def get_error_message(self) -> str:
        """Son hata mesajı"""
        return self.error_message
    
    def authenticate(self, reason: str = "ClipStack Doğrulama") -> Tuple[bool, str]:
        """
        Windows Hello ile kullanıcı doğrulama
        
        Args:
            reason: Doğrulama nedeni (kullanıcıya gösterilir)
            
        Returns:
            (başarılı_mı, hata_mesajı)
        """
        return False, self.error_message
    
    def check_biometric_enrolled(self) -> bool:
        """
        Kullanıcının biyometrik bilgileri kayıtlı mı?
        
        Returns:
            True: En az bir biyometrik veri kayıtlı
            False: Kayıtlı biyometrik veri yok
        """
        if not self.available:
            return False
        
        try:
            # winbio.dll fonksiyonlarını tanımla
            WinBioEnumBiometricUnits = self.winbio.WinBioEnumBiometricUnits
            WinBioEnumBiometricUnits.argtypes = [
                wintypes.ULONG,  # Factor
                ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)),  # UnitSchemaArray
                ctypes.POINTER(ctypes.c_size_t)  # UnitCount
            ]
            WinBioEnumBiometricUnits.restype = wintypes.HRESULT
            
            unit_array = ctypes.POINTER(ctypes.c_void_p)()
            unit_count = ctypes.c_size_t()
            
            # Parmak izi sensörlerini kontrol et
            result = WinBioEnumBiometricUnits(
                WINBIO_TYPE_FINGERPRINT,
                ctypes.byref(unit_array),
                ctypes.byref(unit_count)
            )
            
            if result == S_OK and unit_count.value > 0:
                # Belleği serbest bırak
                try:
                    WinBioFree = self.winbio.WinBioFree
                    WinBioFree.argtypes = [ctypes.c_void_p]
                    WinBioFree(unit_array)
                except:
                    pass
                return True
            
            # Yüz tanıma sensörlerini kontrol et
            result = WinBioEnumBiometricUnits(
                WINBIO_TYPE_FACIAL_FEATURES,
                ctypes.byref(unit_array),
                ctypes.byref(unit_count)
            )
            
            if result == S_OK and unit_count.value > 0:
                try:
                    WinBioFree = self.winbio.WinBioFree
                    WinBioFree.argtypes = [ctypes.c_void_p]
                    WinBioFree(unit_array)
                except:
                    pass
                return True
            
            return False
            
        except Exception as e:
            print(f"[BIOMETRIC] Enrollment check error: {e}")
            return False
    
    def get_available_types(self) -> list:
        """
        Kullanılabilir biyometrik türleri döndür
        
        Returns:
            ["fingerprint", "face", "iris"] gibi bir liste
        """
        if not self.available:
            return []
        
        available_types = []
        
        try:
            WinBioEnumBiometricUnits = self.winbio.WinBioEnumBiometricUnits
            WinBioEnumBiometricUnits.argtypes = [
                wintypes.ULONG,
                ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)),
                ctypes.POINTER(ctypes.c_size_t)
            ]
            WinBioEnumBiometricUnits.restype = wintypes.HRESULT
            
            # Her tür için kontrol et
            biometric_types = [
                (WINBIO_TYPE_FINGERPRINT, "fingerprint"),
                (WINBIO_TYPE_FACIAL_FEATURES, "face"),
                (WINBIO_TYPE_IRIS, "iris")
            ]
            
            for bio_type, name in biometric_types:
                unit_array = ctypes.POINTER(ctypes.c_void_p)()
                unit_count = ctypes.c_size_t()
                
                result = WinBioEnumBiometricUnits(
                    bio_type,
                    ctypes.byref(unit_array),
                    ctypes.byref(unit_count)
                )
                
                if result == S_OK and unit_count.value > 0:
                    available_types.append(name)
                    try:
                        WinBioFree = self.winbio.WinBioFree
                        WinBioFree.argtypes = [ctypes.c_void_p]
                        WinBioFree(unit_array)
                    except:
                        pass
        
        except Exception as e:
            print(f"[BIOMETRIC] Type enumeration error: {e}")
        
        return available_types


# Global instance
_biometric_auth: Optional[BiometricAuth] = None


def get_biometric_auth() -> BiometricAuth:
    """Global BiometricAuth instance'ını döndür"""
    global _biometric_auth
    if _biometric_auth is None:
        _biometric_auth = BiometricAuth()
    return _biometric_auth
