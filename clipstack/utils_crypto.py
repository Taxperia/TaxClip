from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import base64
import binascii
import hashlib
import hmac
import os

KDF_ITERATIONS = 210000

def derive_key(password: str, salt: bytes = None) -> tuple:
    """
    Kullanıcı şifresinden güvenli anahtar türet (PBKDF2 ile)
    
    Returns:
        (key, salt) tuple
    """
    if salt is None:
        salt = get_random_bytes(16)
    
    key = _pbkdf2_key(password, salt)
    return key, salt

def _pbkdf2_key(password: str, salt: bytes) -> bytes:
    """PBKDF2-HMAC-SHA256 ile 256 bit anahtar turet."""
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        KDF_ITERATIONS,
        dklen=32,
    )

def encrypt_aes256(text: str, password: str) -> str:
    """
    AES-256-GCM ile şifrele (daha güvenli authenticated encryption)
    
    Format: base64(salt + nonce + tag + ciphertext)
    """
    key, salt = derive_key(password)
    nonce = get_random_bytes(12)  # GCM için 12 byte nonce
    
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(text.encode("utf-8"))
    
    # salt(16) + nonce(12) + tag(16) + ciphertext
    result = salt + nonce + tag + ciphertext
    return base64.b64encode(result).decode("utf-8")

def decrypt_aes256(b64text: str, password: str) -> str:
    """
    AES-256-GCM ile şifre çöz.
    """
    try:
        raw = base64.b64decode(b64text.encode("utf-8"), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Encrypted payload is not valid base64") from exc

    if len(raw) < 44:
        raise ValueError("Unsupported encrypted payload format")

    salt = raw[:16]
    nonce = raw[16:28]
    tag = raw[28:44]
    ciphertext = raw[44:]

    try:
        key, _ = derive_key(password, salt)
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        return plaintext.decode("utf-8")
    except Exception as exc:
        raise ValueError("Unable to decrypt payload with the supplied password or data format") from exc

def generate_secure_password(length: int = 32) -> str:
    """Güvenli rastgele şifre üret"""
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
    return ''.join(alphabet[b % len(alphabet)] for b in os.urandom(length))

def hash_password(password: str) -> str:
    """Şifreyi güvenli şekilde hashle (doğrulama için)"""
    salt = get_random_bytes(16)
    key = _pbkdf2_key(password, salt)
    return base64.b64encode(salt + key).decode("utf-8")

def verify_password(password: str, stored_hash: str) -> bool:
    """Hashlenmiş şifreyi doğrula"""
    try:
        raw = base64.b64decode(stored_hash.encode("utf-8"))
        salt = raw[:16]
        stored_key = raw[16:]
        key = _pbkdf2_key(password, salt)
        return hmac.compare_digest(key, stored_key)
    except Exception:
        return False
