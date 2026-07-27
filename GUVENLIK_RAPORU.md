# TaxClip (copyv6.3) — Güvenlik Denetim Raporu

**Tarih:** 27 Temmuz 2026  
**Kapsam:** Statik kod analizi, mimari inceleme, saldırı yüzeyi haritalaması  
**Ürün:** TaxClip / ClipStack — Windows masaüstü pano yöneticisi (Python 3.10+ / PySide6 / PyInstaller)  
**Denetim türü:** Kaynak kod tabanlı güvenlik taraması (dinamik pentest değil)

---

## Özet

TaxClip, sistem genelinde pano içeriğini izleyen, SQLite veritabanında saklayan ve isteğe bağlı olarak şifreleme, TOTP 2FA ve Google Drive senkronizasyonu sunan bir Windows masaüstü uygulamasıdır. Uygulama bir web sunucusu barındırmaz; saldırı yüzeyi yerel (pano, veritabanı, kayıt defteri, alt süreçler) ve giden HTTPS bağlantılarından oluşur.

Bu raporda **23 güvenlik bulgusu** tespit edilmiştir:

| Önem Derecesi | Adet |
|---------------|------|
| Kritik        | 3    |
| Yüksek        | 7    |
| Orta          | 8    |
| Düşük         | 3    |
| Bilgi         | 2    |

En acil düzeltilmesi gereken konular: şifreleme anahtarının diske yazılma riski, otomatik güncelleyicide imza doğrulaması eksikliği, hassas veri TOTP kapısının hata durumunda açık kalması ve kısmi veri şifrelemesi.

---

## 1. Proje Profili ve Saldırı Yüzeyi

### Teknoloji yığını

| Bileşen | Değer |
|---------|-------|
| Dil | Python 3.10+ |
| UI | PySide6 (Qt 6) |
| Veritabanı | SQLite (`taxclip.db`) |
| Paketleme | PyInstaller |
| Şifreleme | PyCryptodome (AES-256-GCM, PBKDF2) |
| 2FA | pyotp (TOTP) |
| Bulut | Google Drive OAuth 2.0 |
| Güncelleme | GitHub Releases API |

### Giriş noktaları

| Dosya | Rol |
|-------|-----|
| `main.py` | Ana giriş noktası |
| `clipstack/app.py` | Tray uygulaması, yaşam döngüsü, güvenlik kapıları |
| `clipstack/updater.py` | GitHub üzerinden otomatik güncelleme |
| `clipstack/ui/item_preview_dialog.py` | Uzak paylaşım API'si |
| `clipstack/gdrive_sync.py` | Google Drive OAuth |

### Çalışma zamanı veri konumları

| Konum | İçerik |
|-------|--------|
| `%AppData%\Roaming\TaxClip\` | `settings.json`, `taxclip.db` |
| `%USERPROFILE%\.taxclip\` | `.totp_secret`, `google_token.json`, `google_credentials.json` |

### Güven sınırları (trust boundaries)

```
[Kullanıcı / Windows Oturumu]
        │
        ▼
[TaxClip Süreci] ──► SQLite DB, settings.json
        │
        ├──► Sistem Panosu (tüm uygulamalardan veri)
        ├──► Global kısayol tuşları (RegisterHotKey)
        ├──► SendInput (otomatik yapıştırma)
        ├──► GitHub API (güncelleme)
        ├──► taxclip.com /api/share (uzak paylaşım)
        └──► Google Drive API (yedekleme)
```

---

## 2. Güvenlik Bulguları

### 2.1 Kritik Bulgular

#### K-01: Şifreleme parolası diske yazılabilir

**Konum:** `clipstack/app.py:155-158`, `clipstack/settings.py:64-66`  
**Açıklama:** Kullanıcı şifreleme parolası `settings.set("encryption_key", password)` ile ayarlar nesnesine yazılıyor. `settings.save()` çağrıldığında tüm `_data` sözlüğü `settings.json` dosyasına serileştiriliyor. `encryption_key` alanı için herhangi bir filtreleme yok.

**Risk:** Parola düz metin olarak `%AppData%\Roaming\TaxClip\settings.json` içinde kalıcı hale gelebilir. Dosyaya erişen herhangi bir süreç (kötü amaçlı yazılım, yedekleme aracı, başka kullanıcı) tüm şifreli veritabanını çözebilir.

**Öneri:**
- `encryption_key` asla diske yazılmamalı; yalnızca bellekte tutulmalı.
- `settings.save()` öncesinde hassas anahtarlar otomatik olarak çıkarılmalı.
- Parola hash'i (PBKDF2) saklanabilir; gerçek anahtar her oturumda kullanıcıdan istenmeli.

---

#### K-02: Otomatik güncelleyicide imza / checksum doğrulaması yok

**Konum:** `clipstack/updater.py:163-258`  
**Açıklama:** Güncelleme dosyası GitHub'dan indirildikten sonra doğrudan çalıştırılıyor. SHA256 veya Authenticode imza doğrulaması yapılmıyor. İndirilen `.exe` dosyası `subprocess.Popen([file_path], shell=True)` ile başlatılıyor.

**Risk:** GitHub hesabı ele geçirilirse, DNS/HTTPS MITM saldırısı gerçekleşirse veya release asset'leri değiştirilirse, kullanıcılara kötü amaçlı yazılım dağıtılabilir (supply chain saldırısı).

**Öneri:**
- Her release için SHA256 hash'ini GitHub'da yayınlayın ve indirme sonrası doğrulayın.
- Authenticode ile imzalı `.exe` dağıtın; güncelleyicide imza doğrulaması yapın.
- `shell=True` kullanımını kaldırın.
- Zip güncellemelerinde dosya bütünlüğü kontrolü ekleyin.

---

#### K-03: Hassas veri TOTP kapısı hata durumunda açık (fail-open)

**Konum:** `clipstack/sensitive_detector.py:382-384`  
**Açıklama:** TOTP doğrulaması sırasında herhangi bir istisna oluşursa erişim **veriliyor** (`return True`).

```python
except Exception as e:
    print(f"[SENSITIVE] TOTP doğrulama hatası: {e}")
    return True  # Hata durumunda erişime izin ver
```

**Risk:** Kütüphane hatası, dosya bozulması veya kasıtlı müdahale ile TOTP koruması tamamen atlanabilir. Güvenlik mekanizmaları "fail-closed" (hata = erişim reddi) olmalıdır.

**Öneri:** `return False` yapın ve kullanıcıya anlamlı bir hata mesajı gösterin.

---

### 2.2 Yüksek Bulgular

#### Y-01: Kısmi veri şifrelemesi

**Konum:** `clipstack/storage.py`  
**Açıklama:** `encrypt_data=True` iken yalnızca şu alanlar şifreleniyor:
- `clip_items`: `text_content`, `html_content`, `ocr_text` (ancak `image_blob` şifrelenmiyor)
- `notes`: `content`
- `reminders`: `title`, `description`

Şifrelenmeyen tablolar:
- `snippets` ve `snippet_files` (kod parçacıkları)
- `todos` ve `todo_lists`
- `drawings` (çizim verileri, base64 görüntüler)
- `clip_items.image_blob` (pano görselleri)

**Risk:** Kullanıcı "verilerim şifreli" sanırken önemli içerikler düz metin olarak SQLite'ta kalır.

**Öneri:** Tüm hassas tablolar için tutarlı şifreleme katmanı uygulayın veya kullanıcıya hangi verilerin şifrelendiğini açıkça bildirin.

---

#### Y-02: Google OAuth token'ları düz metin olarak saklanıyor

**Konum:** `clipstack/gdrive_sync.py:46-47`  
**Açıklama:** `~/.taxclip/google_token.json` dosyası şifrelenmeden saklanıyor.

**Risk:** Bu dosyaya erişen biri kullanıcının Google Drive'ına (drive.file kapsamında) erişebilir ve yedeklenen pano verilerini okuyabilir.

**Öneri:** Token'ları Windows DPAPI (`CryptProtectData`) veya makineye özel bir anahtarla şifreleyerek saklayın.

---

#### Y-03: TOTP secret anahtarı tahmin edilebilir makine ID'si ile şifreleniyor

**Konum:** `clipstack/totp_manager.py:240-252`  
**Açıklama:** TOTP secret'ı şifrelemek için kullanılan anahtar `hostname + MAC adresi` kombinasyonundan türetiliyor. Bu bilgiler yerel ağda veya sistem bilgisi toplayan araçlarla kolayca elde edilebilir.

**Risk:** `.totp_secret` dosyası kopyalanırsa, makine bilgisi bilinen ortamlarda offline olarak çözülebilir; 2FA atlanabilir.

**Öneri:** Windows DPAPI veya kullanıcı parolası tabanlı anahtar türetme kullanın. Makine ID'si tek başına yeterli olmamalıdır.

---

#### Y-04: Uzak paylaşım API'si — veri sızdırma vektörü

**Konum:** `clipstack/ui/item_preview_dialog.py:178-209`  
**Açıklama:** Pano içeriği kullanıcı tarafından yapılandırılabilir bir sunucuya (`share_server_url`, varsayılan `https://taxclip.com`) POST ediliyor. İçerik, isteğe bağlı paylaşım parolası ve Bearer token ile gönderiliyor.

**Risk:**
- `share_server_url` saldırgan kontrolündeki bir sunucuya yönlendirilirse tüm paylaşılan içerik sızdırılır.
- HTTPS sertifika sabitleme (pinning) yok.
- Paylaşım parolası JSON payload içinde gönderiliyor.

**Öneri:**
- Sunucu URL'sini yalnızca güvenilir domain listesine kısıtlayın.
- Certificate pinning uygulayın.
- Paylaşım öncesi kullanıcıya hedef sunucuyu açıkça gösterin.

---

#### Y-05: PyInstaller paketi — tersine mühendislik kolaylığı

**Konum:** Genel mimari  
**Açıklama:** Python kaynak kodu PyInstaller ile paketleniyor. `.pyc` dosyaları ve kaynak kodlar `pyinstxtractor`, `uncompyle6`, `decompyle3` gibi araçlarla kolayca çıkarılabilir. Kodda lisans doğrulama veya anti-tamper mekanizması bulunmuyor.

**Risk:** Kötü amaçlı kişiler uygulamayı kolayca decompile edebilir, şifreleme mantığını analiz edebilir, lisans kontrolü ekleyebilir veya crack'lenmiş sürüm dağıtabilir.

**Öneri:** Bölüm 4'teki anti-crack önlemlerine bakın.

---

#### Y-06: `shell=True` ile alt süreç çalıştırma

**Konum:**
- `clipstack/updater.py:230, 258`
- `clipstack/ui/snippet_card_widget.py:262, 281`

**Açıklama:** `subprocess.Popen(..., shell=True)` kullanımı, dosya yolunda veya argümanlarda özel karakterler varsa komut enjeksiyonuna yol açabilir.

**Risk:** Güncelleme dosyası yolu veya snippet dosya adları manipüle edilirse rastgele komut çalıştırılabilir.

**Öneri:** `shell=False` kullanın ve argümanları liste olarak geçirin.

---

#### Y-07: Sistem genelinde pano izleme — gizlilik riski

**Konum:** `clipstack/clipboard_watcher.py`  
**Açıklama:** Uygulama tüm sistem panosunu sürekli izler. Hassas veri maskeleme regex tabanlıdır ve atlatılabilir.

**Risk:** Şifreler, API anahtarları, kişisel veriler kasıtlı veya kasıtsız olarak kaydedilebilir. Regex tabanlı maskeleme tüm formatları yakalayamaz.

**Öneri:**
- Varsayılan olarak hassas veri engelleme (`block_sensitive_data`) açık olmalı.
- Regex yerine daha güçlü PII algılama kütüphaneleri değerlendirilmeli.
- Belirli uygulamalardan gelen pano verilerini hariç tutma seçeneği eklenmeli.

---

### 2.3 Orta Bulgular

#### O-01: Windows Hello yanlış tanıtımı

**Konum:** `clipstack/biometric_auth.py:59-80`  
**Açıklama:** Modül "Windows Hello Biometric Authentication" olarak adlandırılmış ancak gerçekte `CredUIPromptForCredentialsW` (Windows kimlik bilgisi diyaloğu) kullanıyor. Gerçek WinBio biyometrik API'si yükleniyor ama doğrulama için kullanılmıyor.

**Risk:** Kullanıcılar gerçek biyometrik koruma olduğunu sanabilir; güvenlik beklentisi ile gerçeklik uyuşmuyor.

---

#### O-02: JSON dışa aktarmada zayıf hassas veri filtreleme

**Konum:** `clipstack/ui/settings_dialog.py:1730-1732`  
**Açıklama:** Dışa aktarmada ayarlar filtrelenirken anahtar adında `password`, `secret`, `key`, `token` geçen alanlar çıkarılıyor. Ancak `encryption_key` dışındaki hassas veriler (pano içerikleri, notlar) şifrelenmemiş olarak export ediliyor.

**Risk:** Export dosyası ele geçirilirse tüm pano geçmişi okunabilir.

---

#### O-03: SQLite veritabanı şifrelenmemiş

**Konum:** `%AppData%\Roaming\TaxClip\taxclip.db`  
**Açıklama:** `encrypt_data` kapalıyken veya kısmi şifreleme aktifken veritabanı dosyası düz SQLite formatında diskte duruyor. SQLCipher veya dosya seviyesi şifreleme kullanılmıyor.

**Risk:** Dosyaya erişim = veriye erişim.

---

#### O-04: OAuth localhost redirect — port hijacking

**Konum:** `clipstack/gdrive_sync.py`  
**Açıklama:** Google OAuth akışı `http://localhost` üzerinde rastgele bir porta yönlendirme yapıyor. Başka bir süreç aynı portu dinliyorsa authorization code yakalanabilir.

**Öneri:** Sabit port + state parametresi doğrulaması veya loopback IP kısıtlaması.

---

#### O-05: Bağımlılık güvenlik taraması eksik

**Konum:** `requirements.txt`, CI pipeline  
**Açıklama:** CodeQL Python analizi mevcut ancak bağımlılık CVE taraması (pip-audit, Dependabot) yapılandırılmamış görünüyor.

**Risk:** Bilinen güvenlik açığı olan paket sürümleri fark edilmeden kalabilir.

---

#### O-06: FFmpeg / Tesseract yolu — potansiyel komut enjeksiyonu

**Konum:** `clipstack/ocr_manager.py`, `clipstack/video_recorder.py`  
**Açıklama:** Kullanıcı ayarlarından `tesseract_path` yapılandırılabiliyor. Kötü niyetli bir yol değeri subprocess çağrılarında kullanılabilir.

**Risk:** Düşük (kullanıcının kendi ayarını değiştirmesi gerekir) ancak savunmasızlık prensibi ihlali.

---

#### O-07: HTML pano içeriği — UI enjeksiyon riski

**Konum:** `clipstack/clipboard_watcher.py:40-47`  
**Açıklama:** `javascript:` ve `data:` href'leri filtreleniyor (iyi uygulama). Ancak HTML içerik Qt `QTextDocument` ile işleniyor; tüm XSS vektörleri kapsanmayabilir.

**Risk:** Kötü amaçlı HTML panoya kopyalanırsa UI'da beklenmeyen davranış oluşabilir.

---

#### O-08: Startup kalıcılığı — registry ve kısayol

**Konum:** `clipstack/startup.py`  
**Açıklama:** Uygulama `HKCU\...\Run` kayıt defteri anahtarına ve Startup klasörüne kısayol ekleyebiliyor.

**Risk:** Uygulama veya ayar dosyası değiştirilirse kalıcılık mekanizması kötüye kullanılabilir. (Düşük risk — standart masaüstü uygulaması davranışı.)

---

### 2.4 Düşük Bulgular

#### D-01: `generate_secure_password` mod bias

**Konum:** `clipstack/utils_crypto.py:75-78`  
**Açıklama:** `os.urandom(length)` baytları `alphabet[b % len(alphabet)]` ile eşleniyor. Modulo işlemi hafif entropi kaybına yol açar.

**Öneri:** `secrets.choice(alphabet)` kullanın.

---

#### D-02: Geniş TOTP doğrulama penceresi

**Konum:** `clipstack/totp_manager.py:165`  
**Açıklama:** `valid_window=1` ile önceki ve sonraki 30 saniyelik kodlar da kabul ediliyor (toplam ~90 saniyelik pencere).

**Risk:** Çalınan kodun kullanım süresi uzar.

---

#### D-03: Hata mesajlarında bilgi sızıntısı

**Konum:** Çeşitli `print()` ve `QMessageBox` çağrıları  
**Açıklama:** Hata durumlarında iç detaylar konsola veya kullanıcıya gösterilebiliyor.

---

### 2.5 Bilgi / Olumlu Bulgular

#### B-01: Güçlü şifreleme primitifleri

**Konum:** `clipstack/utils_crypto.py`  
- AES-256-GCM (authenticated encryption)
- PBKDF2-HMAC-SHA256, 210.000 iterasyon
- `hmac.compare_digest` ile zamanlama saldırısına karşı güvenli parola karşılaştırması

#### B-02: SQL enjeksiyonuna karşı koruma

**Konum:** `clipstack/storage.py`  
Tüm SQL sorguları parametreli (`?` placeholder) — SQL injection riski düşük.

#### B-03: CodeQL CI entegrasyonu

**Konum:** `.github/workflows/codeql.yml`  
Haftalık ve push tetiklemeli statik analiz mevcut.

---

## 3. Kod Düzeltme Öncelik Listesi

| Öncelik | Bulgu | Tahmini Efor | Etki |
|---------|-------|--------------|------|
| 1 | K-01: encryption_key diske yazılmasın | 2 saat | Kritik |
| 2 | K-03: TOTP fail-closed yap | 15 dakika | Kritik |
| 3 | K-02: Güncelleyicide imza/hash doğrulama | 1 gün | Kritik |
| 4 | Y-01: Tüm tabloları şifrele | 2-3 gün | Yüksek |
| 5 | Y-02: OAuth token DPAPI ile koru | 4 saat | Yüksek |
| 6 | Y-03: TOTP secret anahtarını güçlendir | 4 saat | Yüksek |
| 7 | Y-06: shell=True kaldır | 1 saat | Yüksek |
| 8 | O-05: pip-audit CI'ye ekle | 2 saat | Orta |
| 9 | Y-04: Share URL whitelist | 2 saat | Yüksek |
| 10 | D-01: secrets.choice kullan | 15 dakika | Düşük |

---

## 4. Program Kırılmaya Karşı Koruma (Anti-Crack / Anti-Tamper)

TaxClip bir Python/PyInstaller uygulaması olduğundan, kaynak kodu ve mantığı tersine mühendislikle çıkarılabilir. **Hiçbir koruma %100 güvenli değildir**; amaç saldırı maliyetini yükseltmek ve casual cracking'i zorlaştırmaktır.

### 4.1 Kod Koruma Katmanları

#### Katman 1: Derleme ve Obfuscation (Temel)

| Araç | Açıklama | Maliyet |
|------|----------|---------|
| **PyArmor** | Python bytecode şifreleme ve obfuscation. En yaygın Python koruma aracı. | Ücretsiz (sınırlı) / Pro ~$50-200 |
| **Cython** | Kritik modülleri (`utils_crypto.py`, `totp_manager.py`, lisans modülü) `.pyd` native extension'a derleyin. | Ücretsiz |
| **Nuitka** | PyInstaller yerine Nuitka ile tam native derleme. Tersine mühendislik çok daha zor. | Ücretsiz |

**Önerilen strateji:**
```
Kritik modüller → Cython .pyd
Geri kalan UI kodu → PyArmor obfuscation
Paketleme → Nuitka veya PyInstaller + PyArmor runtime
```

#### Katman 2: Lisans ve Aktivasyon Sistemi

Şu anda kodda **runtime lisans doğrulaması yok**. Eklenmesi önerilen yapı:

```
[Uygulama Başlangıcı]
      │
      ▼
[Lisans Anahtarı Doğrulama] ──► Yerel: imzalı JWT/License dosyası
      │                         Uzak: API sunucusu (opsiyonel)
      ▼
[HWID Bağlama] ──► CPU ID + Disk Serial + MAC (hash)
      │
      ▼
[Periyodik Yeniden Doğrulama] ──► 24-72 saatte bir online check
```

**Lisans sistemi sağlayıcıları:**

| Sağlayıcı | Özellik | Fiyat |
|-----------|---------|-------|
| **Keygen.sh** | API tabanlı lisans, HWID binding, offline activation | $0-49/ay |
| **Cryptolens** | .NET/Python SDK, trial, subscription | Ücretsiz tier mevcut |
| **Gumroad License API** | Basit lisans doğrulama | Satış komisyonu |
| **Lemon Squeezy** | Ödeme + lisans yönetimi | %5 + $0.50/işlem |
| **Kendi API'niz** | Tam kontrol, FastAPI + RSA imzalı lisans | Sunucu maliyeti |

#### Katman 3: Anti-Debug ve Anti-Tamper

| Teknik | Uygulama |
|--------|----------|
| **Anti-debug** | `IsDebuggerPresent()`, `CheckRemoteDebuggerPresent()` Win32 API çağrıları |
| **Integrity check** | Uygulama dosyalarının SHA256 hash'ini başlangıçta doğrula |
| **Anti-VM** | Sanal makine tespiti (VMware, VirtualBox registry anahtarları) — dikkatli kullanın, false positive riski |
| **Zamanlama kontrolü** | Debug altında kod yavaşlar; kritik fonksiyonlarda süre ölçümü |
| **String obfuscation** | API URL'leri, lisans sunucu adresleri şifreli saklanmalı |

**Native koruma araçları (EXE sarmalayıcı):**

| Araç | Açıklama | Fiyat |
|------|----------|-------|
| **VMProtect** | Sanal makine tabanlı koruma, en güçlü seçenek | ~$200-500 |
| **Themida / WinLicense** | Anti-debug, anti-dump, code virtualization | ~$300 |
| **Enigma Protector** | Orta seviye koruma, lisans yönetimi dahil | ~$150 |

#### Katman 4: Code Signing (Kod İmzalama)

| Sertifika Türü | Sağlayıcı | Fiyat/yıl | Fayda |
|----------------|-----------|-----------|-------|
| **Standard Code Signing** | Sectigo, DigiCert | $200-400 | SmartScreen uyarısını azaltır |
| **EV Code Signing** | DigiCert, GlobalSign | $400-700 | Anında SmartScreen güveni, en yüksek koruma |

İmzasız `.exe` dosyaları Windows SmartScreen tarafından engellenir ve kullanıcılar "tanınmayan yayıncı" uyarısı görür. EV sertifika bu sorunu büyük ölçüde çözer.

### 4.2 Mimari Öneriler

```
┌─────────────────────────────────────────────┐
│           VMProtect / Themida Sarmalayıcı     │
│  ┌───────────────────────────────────────┐  │
│  │         Nuitka Native Binary          │  │
│  │  ┌─────────────┐  ┌────────────────┐  │  │
│  │  │ Cython .pyd │  │ PyArmor UI     │  │  │
│  │  │ - crypto    │  │ - dialogs      │  │  │
│  │  │ - license   │  │ - widgets      │  │  │
│  │  │ - totp      │  │ - themes       │  │  │
│  │  └─────────────┘  └────────────────┘  │  │
│  └───────────────────────────────────────┘  │
│  + Anti-debug checks                        │
│  + Integrity verification                   │
│  + License validation                       │
└─────────────────────────────────────────────┘
         │
         ▼
   [License Server API]
   (RSA signed tokens)
```

### 4.3 Dağıtım Güvenliği

1. **Her release için SHA256 hash yayınlayın** (zaten `release/` klasöründe `.sha256` var — güncelleyicide kullanın).
2. **Authenticode imzası** ile `.exe` imzalayın.
3. **VirusTotal'a yükleyin** ve sonuç linkini release notlarına ekleyin.
4. **Güncellemeleri yalnızca imzalı/hash'li dosyalardan yapın.**
5. **Kaynak kodu public repo'da tutuyorsanız**, lisans doğrulama mantığını sunucu tarafında tutun.

---

## 5. Önerilen Güvenlik Yazılımları ve Araçları

### 5.1 Geliştirme ve CI/CD Güvenliği

| Araç | Amaç | Fiyat |
|------|------|-------|
| **GitHub Dependabot** | Bağımlılık CVE taraması, otomatik PR | Ücretsiz (GitHub) |
| **pip-audit** | Python paket güvenlik açığı taraması | Ücretsiz |
| **Bandit** | Python statik güvenlik analizi (SAST) | Ücretsiz |
| **Safety** | `requirements.txt` CVE kontrolü | Ücretsiz / Pro |
| **CodeQL** | GitHub entegre SAST (zaten aktif) | Ücretsiz |
| **Trivy** | Container ve dosya sistemi taraması | Ücretsiz |
| **pre-commit hooks** | Commit öncesi otomatik güvenlik kontrolü | Ücretsiz |

**Hemen eklenebilecek CI adımı:**
```yaml
# .github/workflows/security.yml
- name: Audit Python dependencies
  run: pip install pip-audit && pip-audit -r requirements.txt

- name: Run Bandit
  run: pip install bandit && bandit -r clipstack/ -ll
```

### 5.2 Kod Koruma ve Anti-Crack

| Araç | Amaç | Fiyat |
|------|------|-------|
| **PyArmor** | Python obfuscation | $0-200 |
| **Nuitka** | Native derleme | Ücretsiz |
| **Cython** | Kritik modül derleme | Ücretsiz |
| **VMProtect** | EXE koruma, virtualization | ~$200-500 |
| **Themida** | Anti-debug, anti-dump | ~$300 |
| **Enigma Protector** | Lisans + koruma | ~$150 |

### 5.3 Kod İmzalama

| Sağlayıcı | Tür | Fiyat/yıl |
|-----------|-----|-----------|
| **DigiCert** | EV Code Signing | ~$500-700 |
| **Sectigo (Comodo)** | Standard Code Signing | ~$200-300 |
| **GlobalSign** | EV Code Signing | ~$400-600 |
| **SSL.com** | eSigner (bulut imzalama) | ~$100-300 |

### 5.4 Lisans Yönetimi

| Araç | Amaç | Fiyat |
|------|------|-------|
| **Keygen.sh** | API lisans yönetimi | $0-49/ay |
| **Cryptolens** | Lisans + ödeme | Ücretsiz tier |
| **Gumroad** | Satış + basit lisans | Komisyon bazlı |
| **Lemon Squeezy** | Ödeme + lisans API | %5 komisyon |
| **Paddle** | Global satış + vergi | %5 + $0.50 |

### 5.5 Uç Nokta ve Ağ Güvenliği (Kullanıcı Tarafı)

| Yazılım | Amaç |
|---------|------|
| **Windows Defender** | Temel antivirüs (Windows 10/11 dahili) |
| **Malwarebytes** | Ek malware koruması |
| **Bitdefender / Kaspersky** | Tam özellikli endpoint protection |
| **GlassWire** | Ağ trafiği izleme (hangi uygulama nereye bağlanıyor) |
| **Wireshark** | Ağ trafiği analizi (geliştirici debug) |

### 5.6 Gizlilik ve Veri Koruma

| Araç | Amaç |
|------|------|
| **VeraCrypt** | Kullanıcı veri klasörünü şifreli disk olarak mount etme |
| **Windows BitLocker** | Tam disk şifreleme |
| **7-Zip (AES-256)** | Yedekleme dosyalarını şifreli arşivleme |

### 5.7 Güvenlik Test Araçları

| Araç | Amaç |
|------|------|
| **OWASP ZAP** | Web API güvenlik testi (share API için) |
| **Burp Suite Community** | HTTP trafik analizi ve test |
| **Process Monitor (Sysinternals)** | Dosya/registry/alt süreç izleme |
| **API Monitor** | Win32 API çağrı izleme |
| **x64dbg / IDA Free** | Tersine mühendislik testi (kendi uygulamanızı test edin) |
| **VirusTotal** | Release dosyalarını 70+ antivirüsle tarama |

---

## 6. Güvenlik Yol Haritası

### Faz 1 — Acil (1-2 hafta)

- [ ] `encryption_key` diske yazılmasını engelle
- [ ] TOTP fail-closed düzeltmesi
- [ ] `shell=True` kaldır
- [ ] `pip-audit` ve `bandit` CI'ye ekle
- [ ] Güncelleyicide SHA256 doğrulama ekle

### Faz 2 — Kısa Vadeli (1 ay)

- [ ] Tüm veritabanı tablolarında tutarlı şifreleme
- [ ] OAuth token'ları DPAPI ile koru
- [ ] TOTP secret anahtarını güçlendir (DPAPI)
- [ ] Share API URL whitelist
- [ ] Code signing sertifikası al ve imzala

### Faz 3 — Orta Vadeli (2-3 ay)

- [ ] Lisans/aktivasyon sistemi entegrasyonu
- [ ] Kritik modülleri Cython ile derle
- [ ] PyArmor obfuscation uygula
- [ ] Anti-debug kontrolleri ekle
- [ ] Authenticode imza doğrulama (güncelleyici)

### Faz 4 — Uzun Vadeli (3-6 ay)

- [ ] Nuitka'ya geçiş değerlendirmesi
- [ ] VMProtect/Themida sarmalayıcı
- [ ] Sunucu tarafı lisans doğrulama API'si
- [ ] Penetrasyon testi (profesyonel veya OWASP metodolojisi)
- [ ] Bug bounty programı değerlendirmesi

---

## 7. Sonuç

TaxClip, güçlü şifreleme primitifleri (AES-256-GCM, PBKDF2) ve parametreli SQL sorguları gibi iyi güvenlik uygulamalarına sahip. Ancak **kritik yapılandırma hataları** (şifre diske yazılması, fail-open TOTP), **kısmi şifreleme kapsamı** ve **supply chain riskleri** (imzasız güncelleyici) acil müdahale gerektiriyor.

Program kırılmaya karşı koruma açısından, Python/PyInstaller mimarisi doğası gereği savunmasızdır. **Çok katmanlı koruma** (Cython derleme + PyArmor + lisans sistemi + code signing + isteğe bağlı VMProtect) saldırı maliyetini önemli ölçüde artıracaktır.

Hiçbir koruma sistemi %100 güvenli değildir; hedef, casual cracking'i zorlaştırmak ve ciddi saldırganlar için bile zaman/maliyet bariyeri oluşturmaktır.

---

## Ek: Bulgu Referans Tablosu

| ID | Önem | Konum | Özet |
|----|------|-------|------|
| K-01 | Kritik | `app.py:155-158` | Şifreleme parolası settings.json'a yazılabilir |
| K-02 | Kritik | `updater.py:163-258` | Güncelleyicide imza/hash doğrulama yok |
| K-03 | Kritik | `sensitive_detector.py:382-384` | TOTP hata durumunda erişim veriliyor |
| Y-01 | Yüksek | `storage.py` | Snippet/todo/drawing/image şifrelenmiyor |
| Y-02 | Yüksek | `gdrive_sync.py:46` | OAuth token düz metin |
| Y-03 | Yüksek | `totp_manager.py:240-252` | TOTP secret zayıf makine anahtarı |
| Y-04 | Yüksek | `item_preview_dialog.py:178-209` | Uzak paylaşım veri sızdırma riski |
| Y-05 | Yüksek | Genel | PyInstaller kolay tersine mühendislik |
| Y-06 | Yüksek | `updater.py`, `snippet_card_widget.py` | shell=True komut enjeksiyonu |
| Y-07 | Yüksek | `clipboard_watcher.py` | Sistem geneli pano izleme |
| O-01 | Orta | `biometric_auth.py` | Windows Hello yanlış tanıtım |
| O-02 | Orta | `settings_dialog.py:1730` | Export'ta zayıf filtreleme |
| O-03 | Orta | `taxclip.db` | Veritabanı dosyası şifrelenmemiş |
| O-04 | Orta | `gdrive_sync.py` | OAuth localhost port hijacking |
| O-05 | Orta | CI pipeline | Bağımlılık CVE taraması eksik |
| O-06 | Orta | `ocr_manager.py` | Tesseract yolu enjeksiyon riski |
| O-07 | Orta | `clipboard_watcher.py` | HTML UI enjeksiyon riski |
| O-08 | Orta | `startup.py` | Registry kalıcılığı |
| D-01 | Düşük | `utils_crypto.py:75-78` | Parola üretiminde mod bias |
| D-02 | Düşük | `totp_manager.py:165` | Geniş TOTP penceresi |
| D-03 | Düşük | Çeşitli | Hata mesajı bilgi sızıntısı |
| B-01 | Bilgi | `utils_crypto.py` | Güçlü şifreleme primitifleri |
| B-02 | Bilgi | `storage.py` | Parametreli SQL sorguları |
| B-03 | Bilgi | `.github/workflows/codeql.yml` | CodeQL CI entegrasyonu |

---

*Bu rapor statik kod analizi ile hazırlanmıştır. Dinamik penetrasyon testi, fuzzing veya runtime analizi kapsam dışındadır.*
