# TaxClip Bağımsız Güvenlik Testi

**Tarih:** 10 Ekim 2026
**Sürüm:** 1.2.4
**Kapsam:** `clipstack/`, `main.py`, `tools/`, bağımlılıklar, güncelleme,
şifreleme, yedekleme, TOTP, pano izleme, harici dosyalar ve paylaşım akışı.

## Sonuç

Denetimde doğrudan kullanılabilen üç yüksek, üç orta ve bir düşük riskli sorun
doğrulandı. Kodla düzeltilebilenlerin tamamı bu çalışma sırasında kapatıldı.
Test sonrasında açık kalan kritik kod zafiyeti bulunmadı.

Dağıtım için kalan önemli konu, üretilen `TaxClip.exe` dosyasının Authenticode
ile imzalı olmamasıdır. Kod artık imzasız veya bilinmeyen yayıncıyla imzalanmış
bir güncellemeyi çalıştırmıyor. Bu nedenle otomatik güncellemenin çalışabilmesi
için resmi sürümlerin bir kod imzalama sertifikasıyla imzalanması gerekir.

## Uygulanan testler

- Bandit ile 20.761 satır Python kodu statik olarak tarandı.
- `pip-audit` ile doğrudan ve geçişli toplam 43 Python paketi denetlendi.
- `detect-secrets` ile kaynak kod ve derleme dosyaları tarandı.
- SQL enjeksiyonu, URL ayrıştırma, yönlendirme, dosya yolu kaçışı, UNC/SMB,
  bozuk yedek, yanlış parola, TOTP tekrar kullanımı ve güncelleme boyutu için
  saldırı girdileri çalıştırıldı.
- Windows DPAPI, AES-256-GCM, PBKDF2, Authenticode ve pano koruma yolları elle
  incelendi.

## Doğrulanan ve kapatılan bulgular

### Yüksek — Güncelleme yönlendirmesi hedef adres denetimini atlıyordu

GitHub URL'si ilk çağrıda doğrulanıyor, fakat HTTP yönlendirmesinden sonra varılan
adres yeniden kontrol edilmiyordu. Son adres artık HTTPS, izin verilen GitHub
alan adı, standart 443 portu ve kullanıcı bilgisi içermeme kurallarıyla yeniden
doğrulanıyor.

### Yüksek — İmzasız ZIP güncellemesi uygulama dizinini değiştirebiliyordu

SHA-256 özeti aynı yayın kanalından gelen ZIP paketi uygulama dizinine
çıkarılabiliyordu. ZIP güncelleme desteği kaldırıldı. Güncelleyici yalnızca
Authenticode doğrulanabilen `.exe` paketlerini kabul ediyor.

### Yüksek — Herhangi bir geçerli kod imzalama sertifikası kabul ediliyordu

Önceki denetim yalnızca imzanın `Valid` olmasına bakıyordu. Artık indirilen
paketin sertifika SHA-256 izi, çalışan imzalı TaxClip sürümünün sertifikasıyla
veya önceden sabitlenmiş güvenilir sertifika iziyle eşleşmek zorunda.

### Orta — Güncelleme ve checksum indirmelerinde boyut sınırı yoktu

Güncelleme paketi 512 MiB, checksum dosyası 1 MiB ile sınırlandı. Hem
`Content-Length` hem de gerçek akan bayt sayısı kontrol ediliyor.

### Orta — Harici görsel kaydı UNC/SMB yoluna otomatik temas edebiliyordu

Kötü hazırlanmış bir veritabanı veya içe aktarma kaydı, görsel yüklenirken
`\\sunucu\paylaşım` adresine bağlantı başlatabilirdi. Harici görseller artık
yalnızca kullanıcının ayarladığı harici görsel klasörünün içinden okunuyor.

### Orta — Eski Google OAuth tokenı düz metin kalabiliyordu

Eski token dosyası ilk başarılı okumada DPAPI biçimine taşınıyor. DPAPI ile
korunan gizli dosyalar geçici dosya + `os.replace` kullanılarak atomik yazılıyor.

### Düşük — URL kullanıcı bilgisi ve özel port ayrıştırma belirsizliği

Paylaşım ve güncelleme URL'lerinde `kullanıcı@host`, parola ve uzak sunucularda
standart dışı portlar reddediliyor.

## Araç sonuçlarının değerlendirmesi

- `pip-audit`: 43 pakette bilinen güvenlik açığı bulunmadı.
- `detect-secrets`: Bir kayıt verdi; bu gerçek anahtar değil,
  `TAXCLIP_GOOGLE_CLIENT_SECRET` ortam değişkeninin adıdır.
- Bandit'in üç yüksek bulgusu `Crypto.*` importlarını eski PyCrypto sanıyor.
  Projede sabitlenmiş paket `pycryptodome==3.21.0`; `pip-audit` bu sürümde
  bilinen açık bulmadı.
- Bandit'in SQL uyarıları elle incelendi. Dinamik parçalar sabit tablo/sütun
  listelerinden, `ORDER BY` izin listesinden veya `?` placeholder sayısından
  oluşuyor. Saldırı girdisiyle tablo silme denemesi başarısız oldu ve veri
  tabanı sağlam kaldı.
- Bandit'in `urlopen` uyarılarındaki bütün URL'ler çağrı öncesi ve yönlendirme
  sonrasında HTTPS alan adı izin listesinden geçiyor.

## Kalan riskler ve sınırlar

1. **Dağıtım imzası:** Mevcut `TaxClip.exe` Authenticode durumu `NotSigned`.
   Güvenilir otomatik güncelleme ve Windows yayıncı kimliği için kod imzalama
   sertifikası gerekir. Sertifika olmadan güncelleme güvenli biçimde reddedilir.
2. **Paylaşım gizliliği:** Paylaşım içeriği ve isteğe bağlı paylaşım parolası TLS
   üzerinden sunucuya gönderiliyor; uçtan uca şifreleme yok. Sunucu operatörü
   içeriği görebilir. Bunun düzeltilmesi istemci ve sunucu protokolünün birlikte
   değiştirilmesini gerektirir.
3. **Harici servis kapsamı:** `taxclip.com`, Google OAuth ve GitHub hesaplarının
   sunucu tarafında penetrasyon testi yapılmadı. Bu denetim masaüstü istemcisi ve
   onun ağ sınırlarıyla sınırlıdır.
4. **Eski TOTP biçimi:** Önceki sürümün makine kimliğine dayalı TOTP dosyası,
   geriye uyumluluk için bir kez okunup DPAPI'ye taşınır. Güncel biçim yalnızca
   DPAPI kullanır.

## Son doğrulama

- 47 otomatik test geçti.
- Python derleme kontrolü geçti.
- `git diff --check` hata vermedi.
- Güvenlik düzeltmelerini içeren build başarıyla üretildi.
- EXE SHA-256: `C5DBF898D4CFB21C26E94A5A0C3B7B2E3EC8DC7793B7CF2F06C2B8851C1A12E9`
