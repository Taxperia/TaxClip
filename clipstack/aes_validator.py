"""
AES-256 Encryption/Decryption Test Tool
Şifreleme doğruluğunu ve performansını test eder
"""
import time
import hashlib
from clipstack.utils_crypto import encrypt_aes256, decrypt_aes256


class AESValidator:
    """AES-256 doğrulayıcı"""
    
    def __init__(self):
        self.test_results = []
    
    def test_basic_encryption(self, password: str = "test123") -> dict:
        """Temel şifreleme testi"""
        test_data = "Hello, World! Bu bir test mesajıdır. 🔐"
        
        # Şifrele
        start = time.perf_counter()
        encrypted = encrypt_aes256(test_data, password)
        encrypt_time = time.perf_counter() - start
        
        # Deşifrele
        start = time.perf_counter()
        decrypted = decrypt_aes256(encrypted, password)
        decrypt_time = time.perf_counter() - start
        
        # Doğrula
        is_correct = decrypted == test_data
        
        return {
            "test_name": "Basic Encryption",
            "success": is_correct,
            "original": test_data,
            "encrypted_length": len(encrypted),
            "decrypted": decrypted,
            "encrypt_time_ms": round(encrypt_time * 1000, 3),
            "decrypt_time_ms": round(decrypt_time * 1000, 3)
        }
    
    def test_empty_string(self, password: str = "test123") -> dict:
        """Boş string testi"""
        test_data = ""
        
        try:
            encrypted = encrypt_aes256(test_data, password)
            decrypted = decrypt_aes256(encrypted, password)
            is_correct = decrypted == test_data
        except Exception as e:
            return {
                "test_name": "Empty String",
                "success": False,
                "error": str(e)
            }
        
        return {
            "test_name": "Empty String",
            "success": is_correct,
            "decrypted": decrypted
        }
    
    def test_large_data(self, password: str = "test123") -> dict:
        """Büyük veri testi (1MB)"""
        test_data = "A" * (1024 * 1024)  # 1MB
        
        start = time.perf_counter()
        encrypted = encrypt_aes256(test_data, password)
        encrypt_time = time.perf_counter() - start
        
        start = time.perf_counter()
        decrypted = decrypt_aes256(encrypted, password)
        decrypt_time = time.perf_counter() - start
        
        is_correct = decrypted == test_data
        
        return {
            "test_name": "Large Data (1MB)",
            "success": is_correct,
            "original_size_kb": len(test_data) // 1024,
            "encrypted_size_kb": len(encrypted) // 1024,
            "encrypt_time_ms": round(encrypt_time * 1000, 3),
            "decrypt_time_ms": round(decrypt_time * 1000, 3),
            "throughput_mbps": round((len(test_data) / (1024 * 1024)) / encrypt_time, 2)
        }
    
    def test_special_characters(self, password: str = "test123") -> dict:
        """Özel karakter testi"""
        test_data = "!@#$%^&*()_+-=[]{}|;':\",./<>?`~\n\t\r" + "äöüğışçÖÜĞİŞÇ" + "中文日本語한국어"
        
        encrypted = encrypt_aes256(test_data, password)
        decrypted = decrypt_aes256(encrypted, password)
        
        is_correct = decrypted == test_data
        
        return {
            "test_name": "Special Characters",
            "success": is_correct,
            "original": test_data,
            "decrypted": decrypted
        }
    
    def test_wrong_password(self, password: str = "test123") -> dict:
        """Yanlış şifre testi"""
        test_data = "Secret message"
        
        encrypted = encrypt_aes256(test_data, password)
        
        try:
            decrypted = decrypt_aes256(encrypted, "wrongpassword")
            # Yanlış şifre ile farklı sonuç gelmeli
            is_correct = decrypted != test_data
        except:
            # Hata vermesi de beklenen bir sonuç
            is_correct = True
        
        return {
            "test_name": "Wrong Password",
            "success": is_correct,
            "note": "Should fail or return different data"
        }
    
    def test_binary_data(self, password: str = "test123") -> dict:
        """Binary veri testi"""
        test_data = bytes([i % 256 for i in range(1000)])
        
        # bytes'ı string'e çevir
        test_str = test_data.hex()
        
        encrypted = encrypt_aes256(test_str, password)
        decrypted = decrypt_aes256(encrypted, password)
        
        is_correct = decrypted == test_str
        
        return {
            "test_name": "Binary Data",
            "success": is_correct,
            "original_length": len(test_data),
            "decrypted_length": len(bytes.fromhex(decrypted))
        }
    
    def test_repeated_encryption(self, password: str = "test123", rounds: int = 10) -> dict:
        """Tekrarlı şifreleme testi"""
        test_data = "Consistency test"
        
        encrypted_values = []
        for _ in range(rounds):
            encrypted = encrypt_aes256(test_data, password)
            decrypted = decrypt_aes256(encrypted, password)
            
            if decrypted != test_data:
                return {
                    "test_name": f"Repeated Encryption ({rounds} rounds)",
                    "success": False,
                    "note": "Decryption failed in one of the rounds"
                }
            
            encrypted_values.append(encrypted)
        
        # Her şifreleme farklı olmalı (IV random)
        unique_count = len(set(encrypted_values))
        all_unique = unique_count == rounds
        
        return {
            "test_name": f"Repeated Encryption ({rounds} rounds)",
            "success": all_unique,
            "unique_encryptions": unique_count,
            "total_rounds": rounds,
            "note": "Each encryption should be unique due to random IV"
        }
    
    def run_all_tests(self, password: str = "ClipStack2024!") -> list:
        """Tüm testleri çalıştır"""
        self.test_results = []
        
        tests = [
            self.test_basic_encryption,
            self.test_empty_string,
            self.test_large_data,
            self.test_special_characters,
            self.test_wrong_password,
            self.test_binary_data,
            self.test_repeated_encryption
        ]
        
        for test_func in tests:
            try:
                result = test_func(password)
                self.test_results.append(result)
            except Exception as e:
                self.test_results.append({
                    "test_name": test_func.__name__,
                    "success": False,
                    "error": str(e)
                })
        
        return self.test_results
    
    def get_summary(self) -> dict:
        """Test sonuçlarının özeti"""
        if not self.test_results:
            return {"error": "No tests run yet"}
        
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r.get("success", False))
        failed = total - passed
        
        return {
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "success_rate": round((passed / total) * 100, 2)
        }
    
    def print_results(self):
        """Sonuçları terminale yazdır"""
        print("\n" + "="*60)
        print("🔐 AES-256 ENCRYPTION VALIDATION RESULTS")
        print("="*60)
        
        for result in self.test_results:
            status = "✅ PASS" if result.get("success") else "❌ FAIL"
            print(f"\n{status} - {result['test_name']}")
            
            for key, value in result.items():
                if key not in ['test_name', 'success']:
                    print(f"  {key}: {value}")
        
        print("\n" + "="*60)
        summary = self.get_summary()
        print(f"📊 SUMMARY")
        print(f"  Total Tests: {summary['total_tests']}")
        print(f"  Passed: {summary['passed']}")
        print(f"  Failed: {summary['failed']}")
        print(f"  Success Rate: {summary['success_rate']}%")
        print("="*60 + "\n")


def validate_aes():
    """CLI'dan AES doğrulama çalıştır"""
    validator = AESValidator()
    validator.run_all_tests()
    validator.print_results()
    return validator.get_summary()


if __name__ == "__main__":
    validate_aes()
