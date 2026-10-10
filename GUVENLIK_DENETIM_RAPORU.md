# TaxClip — Güvenlik Denetim Raporu

> **Bağımsız yeniden test (10.10.2026):** Bu ilk statik rapor, düzeltmelerden
> sonra Codex tarafından saldırı girdileri ve otomatik araçlarla yeniden
> doğrulandı. Güncel sonuçlar `GUVENLIK_TEST_RAPORU_CODEX_2026-10-10.md`
> dosyasındadır.

> **Durum (10.10.2026):** Bu belge düzeltme öncesi statik denetimi kaydeder.
> Kritik/yüksek bulgular ve doğrulanan orta/düşük bulgular için kod düzeltmeleri
> uygulanmıştır. Uygulamanın gerçek sürümü `1.2.4`'tür. İlk özetteki sayılandırma
> hatalıdır: 6 değil 7 yüksek bulgu listelenmiş, toplam 38 değil 39 olmalıdır.
> Uygulanan değişiklikler `memory-bank/guvenlik_duzeltmeleri_2026-10-10.md`
> dosyasında kayıtlıdır.

**Uygulama:** TaxClip / ClipStack (pano yöneticisi, Windows, Python 3.10+ / PySide6)
**Sürüm:** v6.6 (repo çalışma dizini: `copyv6.6`)
**Denetim tarihi:** 10.10.2026
**Denetim türü:** Statik kod incelemesi (salt okunur)
**Kapsam:** `clipstack/`, `main.py`, `tools/`, `tests/`, derleme betikleri (`.spec`, `.bat`)
**Kısıt:** Hiçbir kaynak kodunda değişiklik yapılmamıştır. Bu belge denetim tek çıktısıdır.

---

## 1. Yönetici Özeti

Kod tabanı genel olarak **kötü niyetli kütüphane kullanımı açısından temiz**:
`shell=True`, `os.system`, `eval()`, `exec()`, `pickle`, `yaml.load`, `marshal`
hiçbir yerde kullanılmıyor; SQL sorguları tamamen parametreli; bağımlılıklar
`requirements.txt` içinde sürümleriyle sabitlenmiş.

Buna karşılık **kimlik doğrulama/kilit katmanı ve otomatik güncelleme kanalı**
ciddi zafiyetler içeriyor. En kritik üç sorun:

1. **"Windows Hello" doğrulaması hiçbir şeyi doğrulamıyor** — kilit, girilen
   herhangi bir metinle (boş kullanıcı adıyla bile) açılıyor.
2. **Kilit ekranı, şifreleme kapalıyken herhangi bir parolayı kabul ediyor** —
   kilit ve TOTP 2FA tamamen atlatılabilir.
3. **Güncelleme kanalında bütünlük/zorunlu imza doğrulaması yok** — hash
   bulunamazsa yalnızca uyarı verilip indirilen çalıştırılabilir dosya
   çalıştırılıyor / uygulama dizini eziliyor.

### Önem Derecesi Dağılımı

| Önem | Adet |
|------|------|
| 🔴 Kritik | 2 |
| 🟠 Yüksek | 6 |
| 🟡 Orta | 14 |
| 🟢 Düşük | 16 |
| **Toplam** | **38** |

**Metodoloji notu:** Aşağıdaki bulguların tamamı kaynak kodu okunarak doğrulanmıştır.
Önem dereceleri, *mevcut kodun gerçek davranışına dayanan* etki üzerinden
verilmiştir; "ölü kod" (henüz hiçbir yerden çağrılmayan) bileşenler ayrıca
işaretlenmiştir.

---

## 2. 🔴 KRİTİK BULGULAR

### K-1 — "Windows Hello" doğrulaması yapılmıyor; CredUI herhangi bir girdiyle kilit açıyor

| | |
|---|---|
| **Dosya** | `clipstack/biometric_auth.py:59-131` |
| **Kullanım** | `clipstack/app.py:1216-1223`, `clipstack/ui/modern_unlock_dialog.py:270-275` |

```python
# biometric_auth.py:104-127
flags = (CREDUI_FLAGS_GENERIC_CREDENTIALS |
        CREDUI_FLAGS_DO_NOT_PERSIST |
        CREDUI_FLAGS_ALWAYS_SHOW_UI)
result = credui.CredUIPromptForCredentialsW(...)
if result == 0:  # NO_ERROR
    return True, ""
```

**Sorun:** `authenticate()` fonksiyonu WinBio (Windows Hello) API'sini hiç
çağırmıyor. Yalnızca genel amaçlı `CredUIPromptForCredentialsW` penceresi açıyor;
bu API `GENERIC_CREDENTIALS | DO_NOT_PERSIST` bayraklarıyla **kimlik bilgisini
doğrulamaz** — kullanıcı "Tamam"a bastığında `ERROR_SUCCESS` (0) döner.
`winbio.dll` yalnızca `is_available()` kontrolü için yükleniyor (`:42-45`),
doğrulama akışında kullanılmıyor. `check_biometric_enrolled()` (`:136-197`)
tanımlı ama hiçbir yere bağlı değil.

**Etki:** Biyometrik kilit ekranı (`windows_hello_enabled`), başlangıç kilidi
(`biometric_lock_on_startup`) ve hareketlilik kilidi **herhangi bir şeye basınca**
açılır. Kullanıcı "Windows Hello ile kilitlendi" yanılgısındadır; pano geçmişi
(hassas içerik dahil) yetkisiz erişime açıktır.

**Öneri:** `WinBioVerify*` API'leri veya
`Windows.Security.Credentials.UI.UserConsentVerifier` kullanın; kimlik
doğrulanmadan `True` dönmeyin. Hello mevcut değilse kilit yolunu parola/TOTP'ye
zorunlu kılın ve `is_available()` sonucunu `check_biometric_enrolled()` ile
birleştirin.

---

### K-2 — Kilit ekranı: şifreleme kapalıyken herhangi bir parola kilidi açar

| | |
|---|---|
| **Dosya** | `clipstack/app.py:1197-1240` (özellikle `1228-1239`) |
| **Çağrı** | `app.py:909-916` (pencere açılışı), `app.py:362` (başlangıç kilidi) |

```python
# app.py:1228-1239
password, ok = QInputDialog.getText(None, "Kilit", "Parola:", QLineEdit.Password)
if ok and password:
    if self.settings.get("encrypt_data", False):
        if password == self.settings.get("encryption_key"):   # düz == karşılaştırma
            ...
        return False
    self.is_locked = False        # <-- şifreleme KAPALIYKEN doğrulama YOK
    self._last_activity = QDateTime.currentDateTime()
    return True
```

**Sorun:**
- `encrypt_data` varsayılanı `False` (`settings.py:38`) olduğundan **boş olmayan
  her değer kilidi açar**.
- Bu yol `_request_unlock()` içinde TOTP aşamasından **sonra** geldiği için
  TOTP başarısız olsa bile (`app.py:1210-1212`) buraya düşülür → **2FA da bypass
  edilir**.
- TOTP aşamasındaki her hata `except Exception: pass` ile yutuluyor
  (`app.py:1111-1212`) → import/DPAPI hatasında 2FA hiç sorulmadan atlanır.
- Karşılaştırma `==` ile; `utils_crypto.verify_password()` içindeki
  `hmac.compare_digest` kullanılmıyor.

**Etki:** Kilit ve başlangıç kilidi göstermelik hale gelir; TOTP 2FA anlamsızlaşır.

**Öneri:** Kilit parolasını ayrı ve DPAPI ile korunan bir kimlik bilgisi olarak
saklayıp `hash_password()`/`verify_password()` (zaten `utils_crypto.py:109-124`
mevcut) ile doğrulayın; şifreleme kapalıyken bile kilidi **her zaman** parola
hash'ine bağlayın; TOTP/Hello reddedildiğinde yedeği sunmayın (fail-closed);
`hmac.compare_digest` kullanın.

---

## 3. 🟠 YÜKSEK BULGULAR

### Y-1 — Otomatik güncellemede zorunlu bütünlük/imza doğrulaması yok (kod çalıştırma)

| | |
|---|---|
| **Dosya** | `clipstack/updater.py:277-299` (hash yoksa devam), `:310-347` (uygulama) |

```python
# updater.py:296-299
else:
    print("[UPDATER] Uyarı: SHA256 hash bulunamadı; bütünlük doğrulanamadı")
return file_path          # <-- yine de kuruluma devam edilir

# updater.py:317-319
if file_path.endswith('.exe'):
    subprocess.Popen([file_path], shell=False)      # doğrudan çalıştır
```

**Sorun:**
- SHA-256 özeti release body'sinden ya da `.sha256` asset'inden geliyor —
  yani **güvenilirlik zinciri aynı kanalda** (GitHub release ele geçirilirse
  hash de ele geçirilir). **Kod imzası (Authenticode) doğrulaması yok.**
- Hash hiç bulunamazsa **uyarı yazılıp kurulum yine de yürütülüyor**
  (`:296-299`) — bütünlük kontrolü opsiyonel.
- `download_url` asset bulunamazsa `zipball_url`'e (kaynak kod zip'i) düşüyor
  (`:161-162`), yani uygulama dizinine kaynak kod kopyalanabilir.
- `download_url` için alan sınırlaması yok (`releases/download/` alanı kısıtı yok).

**Etki:** GitHub hesabı/CI/release kanalı (veya bir MITM/DNS senaryosu)
ele geçirildiğinde kullanıcı "Şimdi Güncelle" dediğinde **keyfi kod çalıştırma**;
üretimde yalnızca tek satırlık bir `else` dalının geçmesi yeterli.

**Öneri:** Hash bulunamadığında kurulumu **iptal edin** (uyarıyla değil);
her release için imzalı manifest (sigstore/GPG/ed25519) zorunlu kılın; indirilen
`.exe` için Authenticode doğrulaması yapın; `download_url`'i yalnızca
`github.com/<repo>/releases/download/` alanıla sınırlayın.

---

### Y-2 — "Hariç tutulan uygulama" (parola yöneticisi) koruması üç yoldan bypass edilebiliyor

| | |
|---|---|
| **Dosya** | `clipstack/clipboard_watcher.py:139-146`, `:184-194`, `:336-341` (zamanlayıcı `:115-118`) |

```python
# clipboard_watcher.py:139-146
proc = get_foreground_process_name()
if not proc:
    return False          # <-- süreç alınamazsa KORUMA YOK (fail-open)
excluded = self._excluded_apps()
return proc in excluded or any(proc.endswith(x) for x in excluded)
```

**Üç bypass yolu:**
1. **Fail-open (`:143-144`):** Süreç korumalı/hareketsiz/yükseltilmiş bir
   uygulamadaysa `OpenProcess` başarısız olur ve `None` döner; kod `None`
   durumunda koruma uygulamayıp **yakalar** → KeePassXC/1Password'den kopyalanan
   parola düz metin DB'ye yazılır.
2. **TOCTOU (`:188` vs `:194`):** Hariç tutma kararı ile `source_app` kaydı iki
   ayrı `get_foreground_process_name()` çağrısıyla alınır; arada odak
   değişirse karar yanlış süreçle verilir.
3. **Polling tekrarı (`:336-341`):** `dataChanged` olayında hariç tutma nedeniyle
   içerik atlanır ama `_last_poll_text` güncellenmez; 1,5 sn'lik poll aynı
   içerik için `_on_clip_changed()`'i **ikinci kez** çağırır ve o an odak
   farklıysa içerik kaydedilir (dedupe ilk denemede fingerprint yazılmadığı
   için engellemez).

**Etki:** Güvenlik ayarına rağmen parola yöneticisi içerikleri pano geçmişine
sızar.

**Öneri:** Kaynak uygulamayı tek seferde belirleyip bellekte sabitleyin;
`if not proc: return True` (fail-closed); hariç tutulan kaynaktan gelen içeriği
kayıt yerine pano olayını tamamen yutun; poll tarafında "görüldü" kümesi tutun.

---

### Y-3 — Kilitliyken veri erişilebilir: kompakt panel, tam ekran, yapıştırma kısayolu ve Ayarlar

| | |
|---|---|
| **Dosya** | `clipstack/app.py:1171-1195`, `:931-967`, `:1045-1084` |
| **Doğru karşı örnek** | `app.py:909-916` (`toggle_window` kilit kontrolü yapıyor) |

```
is_locked YALNIZCA şu satırlarda kontrol ediliyor: app.py:909
(is_locked başka hiçbir dosyada okunmuyor — grep ile doğrulandı)
```

**Bypass yolları:**
- **`show_compact_panel()` (`:1171-1183`)** — kilit kontrolü yok; kompakt panel
  son öğelerin **ham içeriğini** gösterir (`compact_panel.py:84-85`) ve
  doğrulamasız kopyalar/yapıştırır (`:113-124`).
- **`_open_full_from_compact()` (`:1185-1195`)** — `prepare_for_show()` çağırıyor
  ama `_request_unlock()` çağırmıyor → kilit tamamen aşılır.
- **`paste_last_item()` (`:931-967`)** — kilit kontrolü yok; son öğe panoya
  alınıp aktif pencereye Ctrl+V ile yapıştırılıyor. (`:957`'deki kapı yalnızca
  hassas-veri TOTP kapısıdır, kilit kapısı değil.)
- **`open_settings()` (`:1045-1084`)** — tepsiden Ayarlar açılıp tüm veri
  **dışa aktarılabilir** (bkz. Y-4), kilit sorulmuyor.

**Etki:** "Uygulama kilitli" iken pano geçmişi görüntülenir, kopyalanır,
yapıştırılır ve tamamı düz metin JSON olarak dışa aktarılabilir.

**Öneri:** Kilidi tek bir `ensure_unlocked(reason)` API'sine taşıyın; dört
yolun da ilk satırında kilit kontrolü olsun; kilitliyken kompakt panelde satır
metni yerine "🔒 Kilitli" gösterilsin.

---

### Y-4 — Dışa aktarma/içe aktarma ve Google Drive yedeği şifrelemeyi baypas ediyor

| | |
|---|---|
| **Dosya** | `clipstack/ui/settings_dialog.py:2311-2393` (dışa aktarma), `:2726-2735` (Drive), `:2440-2540` (içe aktarma) |

```python
# settings_dialog.py:2311 — list_items() _decrypt_clip_row() ile ÇÖZÜLMÜŞ veri döner
clips = storage.list_items(limit=10000)
...
# :2392
with open(file_path, 'w', encoding='utf-8') as f:
    json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)
```

**Sorun:**
- `encrypt_data` **açıkken bile** tüm pano geçmişi, notlar, hatırlatıcılar,
  snippet'ler ve çizimler **çözülmüş halde** seçilen diske yazılır; dosyada ne
  parola koruması ne MAC/imza var.
- Aynı veri Google Drive'a **düz metin JSON** olarak yükleniyor
  (`settings_dialog.py:2726-2735` → `gdrive_sync.py:266-307`); bulut kopyası
  cihazdaki şifrelemenin tamamen dışında.
- Dışa aktarılan dosya yedeğe alınıp düzenlenebiliyor: içe aktarmada **şema,
  `version`, imza/MAC ve boyut kontrolü yok** (`:2441`, `version` alanı hiç
  okunmuyor); `image_base64` için boyut sınırı yok (bellek DoS); satır bazlı
  `except: pass` (`:2479, 2491, 2504, 2517, 2528, 2539`) hataları yutuyor.

**Etki:** Şifreleme, tek tıkla dışa aktarımla baypas olur; bulut/taşınan yedek
ele geçirilirse tüm hassas veri açık metindir; kötü niyetli yedek dosyası
veritabanına doğrudan yazılabilir.

**Öneri:** Dışa aktarımda zorunlu parola girip AES-256-GCM ile istemci tarafında
şifreleyin (`version + salt + nonce + tag` başlığı ekleyin); içe aktarmada şema +
`version` + HMAC doğrulayın, boyut/uzunluk sınırı koyun, hataları toplu raporlayın.

---

### Y-5 — Şifreleme sonradan açıldığında mevcut kayıtlar şifrelenmiyor; harici görseller hiç şifrelenmiyor

| | |
|---|---|
| **Dosya** | `clipstack/storage.py:109-146`, `:500-534`; `clipstack/ui/settings_dialog.py:2169`; varsayılan `settings.py:38` |

```python
# storage.py:109-112 — düz metin satırlar sessizce geri verilir
if not _looks_like_encrypted_value(value):
    return value

# storage.py:515-519 — resim şifrelemeden ÖNCE diske yazılır
file_path.write_bytes(image_bytes)
image_bytes = None          # şifreleme adımına hiç girmez
# :524 yorum: "harici kayıtta resimler şifrelenmez"
```

**Sorun:**
- Şifreleme anahtarı **yalnızca yazma anında** türetilir; `encrypt_data`
  sonradan açıldığında eski satırlar **ölene kadar düz metin** kalır.
  Kod tabanında migrasyon/re-encrypt fonksiyonu **yok** (grep ile doğrulandı).
  Kullanıcı "Panoyu şifrele" etiketini görünce tüm verisinin korunduğunu sanar.
- `save_images_externally` aktifse pano görselleri (ekran görüntüleri,
  belgeler, TOTP QR'ları) açık PNG olarak yazılır ve bu yol şifreleme
  dışında **kasıtlı olarak** bırakılmıştır (`:524`).

**Etki:** Yanıltıcı güvenlik algısı; şifreli modda bile hassas piksel verisi
açık halde diskte durur.

**Öneri:** `encrypt_data` açıldığında tüm tabloları tek seferde re-encrypt eden
migrasyon ekleyin; harici görselleri `encrypt_bytes()` ile şifreleyin (uzantı
`.enc`) veya şifreli modda özelliği devre dışı bırakıp uyarı gösterin.

---

### Y-6 — Hassas-veri 2FA kapısı fail-open: secret dosyası silinince/pasifleşince kapı tamamen açılıyor

| | |
|---|---|
| **Dosya** | `clipstack/sensitive_detector.py:336-371`, `:69-131` |

```python
# sensitive_detector.py:358-371
if not settings:
    return True                                  # settings None → AÇIK
if not settings.get("totp_for_sensitive", False):
    return True
...
if not totp.is_enabled():                        # secret dosyası yoksa → AÇIK
    return True
```

**Sorun:**
- `is_enabled()` hem `totp_enabled` ayarını hem `~/.taxclip/.totp_secret`
  dosyasını kontrol eder; dosya silinirse veya ayar düzenlenirse kapı **sessizce
  açık** hale gelir — uyarı/log yok.
- `requires_sensitive_access()` → `contains_sensitive_data()` →
  `detect_sensitive_data()` zinciri her kategoriyi ilgili `mask_*` ayarına bağlı
  çalıştırır. Yani kullanıcı "kredi kartlarını maskele"yı **kapatırsa** kredi
  kartları artık "hassas" sayılmaz ve **2FA kapısı da kapanır**. Görünür
  kısayol ayarı, güvenlik denetimini devre dışı bırakıyor.

**Etki:** 2FA'nın koruma altına aldığı içerikler (kredi kartı, TC kimlik, IBAN)
kimlik doğrulamasız görüntülenir; kullanıcı 2FA'nın aktif olduğunu sanır.

**Öneri:** 2FA etkinleştirildiyse secret dosyası yoksa **fail-closed** davranıp
2FA'yı yeniden kurdurmaya zorlayın; erişim denetimini maskeleme ayarlarından
bağımsız, her zaman çalışan ayrı bir `detect_all()` üzerinden çalıştırın.

---

### Y-7 — TOTP doğrulamada brute-force koruması yok

| | |
|---|---|
| **Dosya** | `clipstack/ui/totp_dialog.py:205-233`, `clipstack/totp_manager.py:160-175` |

```python
# totp_dialog.py — 6 hane dolunca 200 ms sonra otomatik gönderim
if len(text) == 6:
    QTimer.singleShot(200, self._verify)
# totp_manager.py
return totp.verify(code, valid_window=1)
```

**Sorun:** Deneme sayacı, gecikme, kilitlenme (lockout) veya CAPTCHA **hiç yok**.
`valid_window=1` ile her an ~3 geçerli kod kabul ediliyor (≈ 3/1.000.000).
Otomatik gönderimle dakikada binlerce deneme yapılabildiğinden kod dakikalar
içinde tahmin edilebilir. `verify()` ayrıca boş/None kodu açıkça reddetmiyor.

**Etki:** Kilidi/2FA kapısı otomatikleştirilmiş denemelerle açılabilir.

**Öneri:** 5 başarısız denemeden sonra 30-60 sn gecikme + oturum başı deneme
limiti; `valid_window=1` yerine 0 (veya yalnızca geriye dönük 1 pencere);
`verify()` içinde `if not code or len(code) != 6: return False`.

---

## 4. 🟡 ORTA BULGULAR

### O-1 — `tesseract_path` ayar dosyasından geldiği için keyfi çalıştırılabilir dosya çalıştırılıyor
`clipstack/ocr_manager.py:111-119`, `:184-189`; tetikleyici `storage.py:476-483`
```python
custom_path = self.settings.get("tesseract_path", "")
if custom_path and Path(custom_path).exists():
    possible_paths.insert(0, custom_path)
```
Serbest metin (`settings_dialog.py:750-751`), `settings.json` doğrulama olmadan
yükleniyor. Pano'ya **görsel** düştüğünde OCR otomatik çalıştığı için,
`%APPDATA%\TaxClip\settings.json`'a yazma yetkisi olan ama kod çalıştıramayan
bir süreç sessizce kod çalıştırabilir (penceresiz, `CREATE_NO_WINDOW`).
**Öneri:** Yolu kaydetmeden/çalıştırmadan önce doğrulayın: dosya adı
`tesseract.exe` olmalı, Authenticode imzası kontrol edilmeli, salt-okunur
dizinde olmalı; doğrulanamazsa otomatik keşif yoluna düşmeli.

### O-2 — Öngörülebilir sabit isimli geçici `.bat` (TOCTOU)
`clipstack/updater.py:331`, `:337-347`
```python
update_script = os.path.join(tempfile.gettempdir(), 'taxclip_update.bat')
with open(update_script, 'w', encoding='utf-8') as f: ...
subprocess.Popen(['cmd', '/c', update_script], shell=False)
```
Dosya adı sabit (`%TEMP%\taxclip_update.bat`); yazma↔çalıştırma arasında aynı
kullanıcıdaki kötü niyetli bir süreç dosyayı değiştirebilir. Betik
`xcopy /E /Y` ile uygulama dizinini **tamamen** ezip uygulamayı yeniden başlatıyor.
**Öneri:** `tempfile.mkstemp()` (rastgele ad, `O_EXCL`) kullanın; `.bat` yerine
güncelleme adımlarını doğrudan Python içinde yapın.

### O-3 — Pano/DB kaynaklı dosya yolları: otomatik SMB/NTLM teması ve doğrudan çalıştırma
`clipstack/smart_content.py:108-116`, `:166-172`; `clipstack/ui/item_widget.py:461-468`
```python
p = Path(raw); exists = p.exists()      # UNC ise anında SMB bağlantısı gider
...
QDesktopServices.openUrl(QUrl.fromLocalFile(path))   # ShellExecute, uzantı kontrolü yok
```
- Saldırgan panoya `\\saldirgan\paylasim\x` UNC yolu sokabilir; kullanıcı **hiç
  tıklamadan** yalnızca kart çizildiği için NTLM hash sızar (relay/kırma).
- "Dosyayı aç" yalnızca varlık kontrolü sonrası ShellExecute çağırıyor →
  `.exe .bat .cmd .ps1 .js .vbs .hta .lnk .scr .msi` tek tıkla çalışır; kartta
  sadece "N dosya" yazar.

**Öneri:** UNC/`file://` (uzak host'lu) yolları yakalamada reddedin;
`exists()/stat()` çağrısını kart çiziminden kaldırıp varlığı ekleme anında
hesaplayın; çalıştırılabilir uzantılarda tam yolu gösteren onay diyaloğu açın.

### O-4 — Sistem ikillerinin göreli (path'siz) çağrılması → search-order hijack
`clipstack/ocr_manager.py:150`, `:230`; `clipstack/startup.py:144`;
`clipstack/updater.py:347`; `clipstack/video_recorder.py:172`;
`clipstack/ui/item_widget.py:480`
`CreateProcess` önce uygulama dizinini, sonra System32'yi, sonra **CWD ve PATH'i**
tarar; taşınabilir/zip dağıtımda CWD yazılabilir olduğundan sahte ikililer
kazanabilir.
**Öneri:** Sistem ikillerini mutlak yolla çağırın
(`%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe`, `cmd.exe`,
`explorer.exe`, `where.exe`) ve `cwd=` parametresini sabitleyin.

### O-5 — Hassas-veri/TOTP kapıları sağ tık menüsü ve ikincil eylemlerle bypass ediliyor
`clipstack/ui/item_widget.py:392-431` (menü), `:496` (doğru kapı)
```python
# :496 — yalnızca ana "Kopyala" kapıyı soruyor
if self._requires_sensitive_access and not self._ensure_sensitive_access(): ...
# :420-427 — diğer kopyalama eylemleri DOĞRUDAN panoya alır
menu.addAction("Biçimlendirilmiş kopyala", lambda: QApplication.clipboard().setText(...))
menu.addAction("Düz metin kopyala", ...)
```
`_show_context_menu` başlangıcında kapı yok → "Biçimlendirilmiş/Küçültülmüş/Düz
metin/RGB/Yolu kopyala" eylemleri hiç doğrulamadan hassas veriyi panoya alır.
**Öneri:** Menünün **tamamını** tek bir `_requires_sensitive_access` kontrolüyle
kilitleyin.

### O-6 — Kompakt panelde hassas-veri gösterim/kopyalama kapısı hiç yok
`clipstack/ui/compact_panel.py:74-85`, `:94-124`
`_label_for` içeriği ham gösterir, `_copy_row`/`_paste_current` doğrulamasız
çalışır; ana penceredeki (`item_widget.py:130-135`, `:496`) kapı burada yoktur.
**Öneri:** `requires_sensitive_access()` sonucuna göre metni maskeleyin;
`_copy_row` içinde `ensure_sensitive_access()` çağırın.

### O-7 — Güvenilmeyen pano içeriği QLabel `AutoText` ile HTML olarak yorumlanıyor (UI spoofing)
`clipstack/ui/item_widget.py:274`, `:278`; `clipstack/ui/main_window.py:2381`
```python
title = custom_title or self._smart.title   # PLAIN'de title = içeriğin ilk 40 karakteri
self.lbl_title.setText(title)               # QLabel varsayılanı HTML yorumlar
```
Offscreen doğrulamada `QLabel('<div style="color:red">ACME</div>')` zengin metin
olarak çizildi (112 kırmızı piksel). Pano'ya `<div style="color:#22c55e">✓
Doğrulandı</div>` kopyalandığında kart başlığı yeşil "doğrulandı" metni olarak
görünebilir. Otomatik dosya yüklenmiyor / link tıklanmıyor → etki spoofing ile
sınırlı. (`card_common.highlight_code()` escape ediyor — güvenli.)
**Öneri:** Pano verisi basılan **tüm** QLabel'lerde `setTextFormat(Qt.PlainText)`
veya `html.escape()` kullanın; `updater.py:452`'deki sürüm metnini de escape edin.

### O-8 — Ayar dosyasından gelen `external_images_path` ile keyfi dizine yazma
`clipstack/storage.py:500-517`
Dizin tamamen `settings.json`'dan geliyor; pano içeriği saldırganın belirlediği
herhangi bir yere (ör. paylaşım/Startup klasörü) yazılabilir; `mkdir(parents=True)`
ile istenmeyen klasör ağacı oluşur.
**Öneri:** `os.path.realpath` + izinli taban dizin (`resolve().is_relative_to`)
kontrolü; yolu yalnızca `QFileDialog` sonucu olarak kabul edin.

### O-9 — `share_api_key` düz metin `settings.json`'a yazılıyor
`clipstack/settings.py:45` (varsayılan), `:96-100` (yazma filtresi)
```python
if k not in _EPHEMERAL_KEYS and k not in _SENSITIVE_PERSIST_KEYS   # share_api_key listede DEĞİL
```
`_SENSITIVE_PERSIST_KEYS` yalnızca `encryption_key` ve `google_client_secret`
içeriyor. Anahtar `Authorization: Bearer` başlığıyla gönderiliyor
(`item_preview_dialog.py:323-324`). Proje genelinde dosya ACL sertleştirmesi
(`os.chmod`/`icacls`) **hiç yok**; `taxclip.db`, `settings.json`, `.totp_secret`,
`google_token.json` varsayılan izinlerle yazılıyor.
**Öneri:** `share_api_key`'i `_SENSITIVE_PERSIST_KEYS`'e ekleyip DPAPI ile
saklayın; hassas dosyalara yalnızca-sahip DACL uygulayın.

### O-10 — FFmpeg ikili dosyasının çözümlemesi (uygulama dizini / `where` / CWD+PATH)
`clipstack/video_recorder.py:159-196`, `:356-362`, `:563-569`
```python
bundled = app_dir / "ffmpeg" / "ffmpeg.exe"   # kullanıcıca yazılabilir dizin
...
result = subprocess.run(["where", "ffmpeg"], ...)   # CWD + PATH tarar
```
Sahte `ffmpeg.exe`/`ffmpeg` PATH'e konulduğunda ekran kaydı başladığında kod
çalışır; bulunamazsa sessizce devam edilir.
**Öneri:** Yolu yalnızca mutlak ve doğrulanabilir kaynaklardan alın;
`shutil.which(..., path=<sanitized PATH>)` ile **CWD hariç** arayın ve dosya
imzasını doğrulayın.

### O-11 — TOTP secret'ının eski (legacy) şifreleme anahtarı tahmin edilebilir
`clipstack/totp_manager.py:228-244`
```python
hostname = platform.node(); mac = uuid.getnode()
return f"{hostname}-{mac}"     # kamuya açık bilgi
...
return "taxclip-default-key"   # istisnada HER MAKİNEDE AYNI sabit anahtar
```
Eski AES-GCM formatındaki secret (2FA'nın kök gizli anahtarı) makine
bilgilerinden türetilen anahtarla şifrelenmiş; istisna durumunda sabit anahtara
düşüyor → dosya başka makineye kopyalanıp çözülebilir.
**Öneri:** Legacy çözüm yolunu kaldırın; DPAPI migrasyonunu zorunlu kılın
(mevcut `except` ile sessizce geçmeyin).

### O-12 — `secure_storage` düz metin fallback'i okumaya devam ediyor; DPAPI dışı platformda "şifreleme" base64
`clipstack/secure_storage.py:20-21`, `:65-66`, `:127-133`
```python
if not _is_windows():
    return base64.b64encode(plaintext)     # koruma yok
...
# Eski düz metin formatı (geriye uyumluluk)
try: return raw.decode("utf-8")            # magic olmayan her dosya düz metin kabul edilir
```
`DPAPI1:` magisi yazmamış herhangi bir dosya (ör. saldırganın
`google_token.json`'u düz metne çevirmesi) uygulama tarafından çözülmüş gibi
kabul edilir → token/secret sızıntısı gizlenir. TOTP için de aynı desen geçerli.
**Öneri:** Düz metin fallback'ini geçiş dönemiyle kaldırın; okunamıyorsa
"şifreleme bozuldu" hatası verin (fail-closed).

### O-13 — PowerShell'e `-Command` ile dize birleştirme; kaçış tek karaktere sınırlı, timeout yok
`clipstack/startup.py:40-41`, `:128-153`
```python
def _ps_escape(value: str) -> str:
    return value.replace("'", "''")
...
subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                "; ".join(script_parts)], check=True)
```
Kaçış yalnızca `'`; yeni satır/backtick gibi karakterler ifadeyi
sonlandırabilir. Süreçte `timeout` ve `CREATE_NO_WINDOW` yok. (Karşılaştırma:
`ocr_manager.py` aynı kaçışı terk edip `-EncodedCommand + ortam değişkeni`
kullanmış — startup tarafı da aynı modele geçmeli.)
**Öneri:** Sabit betiği `-EncodedCommand` (utf-16le base64) ile gönderin,
değişkenleri ortam değişkeniyle taşıyın; `timeout=15` ve `CREATE_NO_WINDOW` ekleyin.

### O-14 — FFmpeg concat listesi ve `video_format` dosya adına doğrudan giriyor
`clipstack/video_recorder.py:619-632`, `:60`, `:346-348`
`concat_list.txt` sabit adlı ve paylaşılan dizinde (TOCTOU); `seg` yolu tırnak
içerirse concat sözdizimi bozulur; `self.format` doğrudan dosya adına girdiği
için `..\..\...\Startup\x` yazılabilir.
**Öneri:** `tempfile.NamedTemporaryFile` kullanın; `video_format`'ı
`{"mp4","mkv","mov"}` allow-list ile sınırlandırın; `seg` yollarını escape edin.

---

## 5. 🟢 DÜŞÜK BULGULAR

| # | Bulgu | Konum | Etki / Öneri |
|---|-------|-------|--------------|
| D-1 | OCR çıktısının ilk 50 karakteri konsola loglanıyor | `storage.py:485` (`ocr_text[:50]`) | TC/kart no/parola ekranı sızabilir. `print` satırını kaldırın; yalnızca uzunluk loglayın. |
| D-2 | `resource_path()` göreli yolu normalizasyonsuz birleştiriyor | `utils.py:11-15`; tüketen `app.py:435-438`, `settings_dialog.py:2059` | `tray_icon` ayarı `..\..\` ile paket dışına çıkıp keyfi dosya okunur. `resolve()` + `is_relative_to(base)` kontrolü. |
| D-3 | i18n JSON'da bütünlük yok; `lang_code` yola gömülüyor | `i18n.py:17-31` | Güvenlik diyalogl metinleri (kilit/uyarı) değiştirilerek spoof edilebilir; `../../` ile keyfi `.json` okunabilir. `re.fullmatch(r"[a-z]{2}")` + bilinen dil beyaz listesi + hash doğrulama. |
| D-4 | Paylaşım: içerik + paylaşım şifresi tek düz JSON'da, API anahtarı opsiyonel | `item_preview_dialog.py:314-333` | İstemcide şifreleme yok, koruma tamamen sunucuda; `api_key` boşsa hiç auth yok. İçeriği istemcide AES-GCM ile şifreleyin, API anahtarını zorunlu kılın. (URL whitelist `:19-55` **doğru** uygulanmış.) |
| D-5 | Silme işlemleri yalnızca SQL `DELETE`; `VACUUM`/`secure_delete` yok | `storage.py:1022-1025`, `:1282-1285` | Silinen içerik serbest sayfalarda/WAL'de kalır. `PRAGMA secure_delete=ON` + `VACUUM`. |
| D-6 | Temp dosya temizliği hata yolunda atlanıyor (çözülmüş yedek %TEMP%'te kalır) | `gdrive_sync.py:286-310` (`unlink` yalnızca başarıda), `ui/drawing_modal.py:207-216`, `ui/drawing_widget.py:199-213`, `ui/main_window.py:3470-3479` | Ağ hatasında tüm pano içeriği açık JSON olarak kalır. `try/finally` + `delete=True`; hassas veriyi bellekten (`BytesIO`) yükleyin. |
| D-7 | Şifreli DB'de `snippet_files.filename` düz metin | `storage.py:1448-1461`, `:1505-1518` | `content` şifrelenirken dosya adı/ proje yolu şifrelenmiyor. `filename`'ı da `_encrypt_text_field` ile koruyun. |
| D-8 | Parola/PIN sabit-zamanlı karşılaştırılmıyor | `app.py:1232`, `modern_unlock_dialog.py:246` | `==` yerine `hmac.compare_digest`; PIN'i `verify_password` ile hash üzerinden karşılaştırın. |
| D-9 | İndirme dosya adı URL'den türetiliyor (`\` içerebilir) | `updater.py:237-242` | `os.path.join(temp_dir, "b\\..\\..\\evil.zip")` ile temp dizini dışına yazma. `Path(urlparse(url).path).name` + tek segment doğrulaması. |
| D-10 | Kayıt defteri `Run` anahtarı hedef doğrulanmadan yazılıyor | `startup.py:168-176`, `:188-217` | Taşınabilir/indirilenler klasöründen çalıştırmada saldırganın ikiliyi değiştirerek her girişte çalıştırması yeterli. Hedef adı/imzası doğrulayın. |
| D-11 | `reminder_sound_file` doğrulanmaz → UNC ile NTLM sızıntısı | `app.py:1464-1502`, `sound_player.py:104-114` | `\\saldirgan\share\x.wav` ayara yazılırsa hatırlatma anında SMB/NetNTLM hash sızar. Yerel sürücü + `.wav/.mp3` uzantısı zorunluluğu; UNC/`\\?\` reddi. |
| D-12 | FILE tipi öğeler hassas-veri denetiminden tamamen muaf | `clipboard_watcher.py:196-208`, `storage.py:176-216` (`_protect_clip_item` içinde FILE dalı yok) | Dosya yollarındaki hassas veri ne maskelenir ne bloklanır; HTML/URL dalları da yakalama katmanında kontrolsüz. Denetimi tüm tiplere yayın; `is_sensitive` bayrağını otomatik türetin. |
| D-13 | TOTP replay koruması yalnızca bellek içi | `ui/totp_dialog.py:17-32` | Yeniden başlatma sonrası aynı kod (~30 sn) tekrar kabul edilebilir. Son başarılı counter'ı DPAPI korumalı dosyaya yazın. |
| D-14 | Menüden URL/`mailto:` onaysız açılıyor | `item_widget.py:416`, `:418` | Otomatik açılma **yok** (olumlu), şema `^https?://` ile kısıtlı; kalan risk kullanıcı yardımlı phishing. Tam URL'yi gösteren onay diyaloğu ekleyin. |
| D-15 | `is_available()` yalnızca `winbio.dll` yüklenmesine bakıyor | `biometric_auth.py:40-49` | Kullanıcıya var olmayan/hiç kaydedilmemiş biyometrik seçenek sunuluyor. `check_biometric_enrolled()` sonucunu bağlayın. |
| D-16 | Derleme: sürüm sabitlenmemiş `pip install pillow` + `upx=True` | `tools/make_icon.py:11-13`, `TaxClip.spec:33,49`, `build_with_runtime_dir.bat:5,12` | Bağımlılık karıştırma (dependency confusion) ve UPX'in imzalama/AV ile uyumsuzluğu. `requirements` ile sabitleyin, `upx=False`, release ikilisini kod imzalayın. |

---

## 6. 🔵 KAPSAM DIŞI / LATENT (ölü kod) BULGULAR

### L-1 — `ModernUnlockDialog`: hardcoded PIN `123456` + Windows Hello sonucu her koşulda başarılı
`clipstack/ui/modern_unlock_dialog.py:240-249`, `:270-275`
```python
# Demo: "123456" kabul edilir
correct_pin = self.settings.get("app_pin", "123456") if self.settings else "123456"
...
result = self.biometric.authenticate("ClipStack kilidi açılıyor...")
if result:                    # authenticate() her zaman TUPLE döndürür → hep truthy
    self.authenticated = True
    self.accept()
```
- `app_pin` ayarı kod tabanında **hiçbir yerde set edilmiyor** → varsayılan her
  zaman `"123456"`.
- `authenticate()` `(False, "Doğrulama iptal edildi")` gibi bir tuple döndürür;
  Python'da tuple truthy olduğundan **iptal etmek bile kilidi açar**.

**Durum:** `ModernUnlockDialog` grep ile **hiçbir yerden import edilmiyor**
(ölü kod) — bu yüzden Kritik değil, *latent* olarak sınıflandırıldı. Ancak bir
yere bağlandığı anda ciddi arka kapı olur.
**Öneri:** Ya tamamen silin ya da `ok, msg = ...` unpack + `ok is True`
kontrolü ve hash'lenmiş PIN (`hash_password`/`verify_password`) ile düzeltin.

### L-2 — `main_window.py:2808` → `import_items_from_json` fonksiyonu tanımlı değil
Projede tek eşleşme bu satır; import bloğunda da yok → "Notu İçe Aktar"
özellikle her çağrıda `NameError` fırlatır. Güvenlik etkisi yok, işlevsel hata.

---

## 7. ✅ DOĞRULANAN İYİ UYGULAMALAR

Denetim sırasında olumlu olarak doğrulanan noktalar:

| Konum | Doğrulanan davranış |
|-------|---------------------|
| Genel (`clipstack/**`) | **`shell=True`, `os.system`, `eval()`, `exec()`, `pickle`, `yaml.load`, `marshal` hiç kullanılmıyor** (grep ile doğrulandı). |
| `storage.py:927-944`, `:991-994`, `:799`, `:1251+` | SQL sorguları tamamen parametreli; f-string yalnızca güvenilir şema/PRAGMA sütun adları ve `?` yer tutucuları için. **SQL injection yok.** |
| `utils_crypto.py:9-48`, `:109-124` | PBKDF2-HMAC-SHA256 **210.000** iterasyon, 16B rastgele salt, 12B rastgele nonce, **AES-256-GCM**; `verify_password` `hmac.compare_digest` kullanıyor; rastgelelik `secrets`/`get_random_bytes`. |
| `settings.py:5-14`, `:96-100` | `encryption_key` ve `google_client_secret` diske yazılmıyor, yüklenirken temizleniyor. |
| `totp_manager.py:192-203` | Yeni TOTP secret formatı DPAPI ile korunuyor; secret üretimi `pyotp.random_base32()`. |
| `ui/item_preview_dialog.py:19-55` | Paylaşım sunucu URL'si **host + scheme whitelist** + uzak sunucuda zorunlu HTTPS — SSRF/başka domaine gönderim engellenmiş. |
| `ui/settings_dialog.py:2387-2388` | Dışa aktarımda `password/secret/key/token` içeren ayar anahtarları filtreleniyor (`share_api_key` dahil). |
| `clipboard_watcher.py:49-50`, `smart_content.py:37` | `javascript:`/`data:`/`file:` protokolleri reddediliyor; URL deseni `^https?://` ile kısıtlı; href'ten `http→https` yükseltme var. |
| `ocr_manager.py:230-247` | PowerShell betiği sabit `-EncodedCommand` (base64); görsel yolu ve dil **ortam değişkeniyle** iletiliyor → **komut enjeksiyonu yok**; `timeout` mevcut. |
| `ui/item_widget.py:474-482` | `explorer /select,` **argüman listesiyle** ve `shell=False` çağrılıyor. |
| `ui/card_common.py:45-64` | Pygments çıktısı escape ediliyor (`</font>`/`<img onerror>` testte ham geçmedi). |
| `app.py:207-215` | Başlangıçta TOTP başarısızsa uygulama `sys.exit(1)` ile kapanıyor. |
| `sensitive_detector.py:382-384` | TOTP dialog hatalarında fail-closed (`return False`). |
| `requirements.txt` | Tüm bağımlılıklar sürümleriyle sabitlenmiş. |
| `hotkey.py:36-67` | `_parse_hotkey` yalnızca bilinen modifier/tuş aralıklarını kabul ediyor. |
| `.gitignore` | `*.db`, `.env`, `*.key`, `*.pem` dışa bırakılmış; repo içinde takip edilen gizli anahtar/token **bulunamadı** (grep + `git ls-files` ile doğrulandı). |

---

## 8. Öncelikli Aksiyon Planı

**Sprint 1 — Kilit/ kimlik doğrulama (Kritik):**
1. K-1: Windows Hello yerine gerçek WinBio/UserConsentVerifier; `CredUI` ile
   doğrulama yapmadan `True` dönmeyi kaldır.
2. K-2: Kilit parolasını DPAPI + PBKDF2 hash'e bağlayın; şifreleme kapalıyken
   de doğrulama zorunlu; TOTP aşamasında `except: pass` → fail-closed.

**Sprint 2 — Güvenilir güncelleme kanalı (Yüksek):**
3. Y-1: Hash yoksa kurulumu iptal et; release imzası (sigstore/GPG) veya
   Authenticode doğrulaması zorunlu kıl; `download_url` alan kısıtı ekle.
4. O-2: Sabit isimli `.bat` yerine `mkstemp` / süreç-içi güncelleme.

**Sprint 3 — Veri koruma (Yüksek):**
5. Y-4: Şifreli yedek dışa aktarma/içe aktarma (AES-GCM + HMAC) ve Drive
   yedeğini istemcide şifreleme.
6. Y-5: `encrypt_data` açılışında re-encrypt migrasyonu; harici görsel şifreleme.
7. Y-2: Hariç uygulama korumasında fail-closed + tek okumalı karar + poll
   "görüldü" kümesi.

**Sprint 4 — Orta seviye:**
8. Y-3 + O-5 + O-6: Kilit ve hassas-veri kapılarını tek API'ye toplayıp tüm
   erişim yollarına (kompakt panel, menü, yapıştırma, Ayarlar) uygulayın.
9. O-1, O-3, O-4, O-10: Dış ikili çözümlemede imza doğrulamalı mutlak yol +
   UNC yasağı.
10. Y-6, Y-7: 2FA fail-closed + brute-force limiti.

**Sprint 5 — Düşük / savunma derinliği:**
11. Log temizliği (D-1), ACL/DPAPI sertleştirme (O-9, D-5), düz metin
    fallback'lerinin kaldırılması (O-12), derleme zinciri (D-16).

---

*Bu rapor yalnızca statik kod incelemesine dayanır; dinamik/zafiyet taraması
(sızma testi) yapılmamıştır. Kod değişikliği talep edilmediği için hiçbir
dosya düzenlenmemiştir.*
