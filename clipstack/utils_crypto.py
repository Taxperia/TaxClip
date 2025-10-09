from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import base64
import hashlib

def derive_key(password):
    # Kullancı şifresinden 32 byte (256 bit) anahtar türet
    return hashlib.sha256(password.encode("utf-8")).digest()

def encrypt_aes256(text, password):
    key = derive_key(password)
    iv = get_random_bytes(16)
    cipher = AES.new(key, AES.MODE_CFB, iv)
    ciphertext = cipher.encrypt(text.encode("utf-8"))
    return base64.b64encode(iv + ciphertext).decode("utf-8")

def decrypt_aes256(b64text, password):
    raw = base64.b64decode(b64text.encode("utf-8"))
    iv = raw[:16]
    ciphertext = raw[16:]
    key = derive_key(password)
    cipher = AES.new(key, AES.MODE_CFB, iv)
    return cipher.decrypt(ciphertext).decode("utf-8")