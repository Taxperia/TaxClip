"""
OCR (Optik Karakter Tanıma) Yöneticisi
1) Tesseract OCR (varsa) ile tanıma
2) Windows native OCR (Windows.Media.Ocr) fallback
"""
import base64
import os
import sys
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from io import BytesIO

try:
    import pytesseract  # type: ignore
    from PIL import Image  # type: ignore
    TESSERACT_IMPORTS = True
except ImportError:
    TESSERACT_IMPORTS = False
    pytesseract = None  # type: ignore
    Image = None  # type: ignore


# Windows native OCR PowerShell komutu
_WIN_OCR_SCRIPT = r'''
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [Console]::OutputEncoding
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Storage.Streams.RandomAccessStream, Windows.Foundation, ContentType=WindowsRuntime]

function Await($WinRtTask, $ResultType) {
    $asTask = $WinRtTask.GetType().GetMethod('AsTask', [Type[]]@())
    if (-not $asTask) {
        $asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
            $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
            $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
        } | Select-Object -First 1
        $asTask = $asTask.MakeGenericMethod($ResultType)
        $task = $asTask.Invoke($null, @($WinRtTask))
    } else {
        $task = $asTask.Invoke($WinRtTask, @())
    }
    $task.Wait(-1) | Out-Null
    $task.Result
}

$imagePath = $env:CLIPSTACK_OCR_IMAGE_PATH
$lang = if ($env:CLIPSTACK_OCR_LANG) { $env:CLIPSTACK_OCR_LANG } else { "tr" }

try {
    if ([string]::IsNullOrWhiteSpace($imagePath)) {
        throw "OCR image path is missing."
    }
    $stream = [System.IO.File]::OpenRead($imagePath)
    $randomStream = [System.IO.WindowsRuntimeStreamExtensions]::AsRandomAccessStream($stream)
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($randomStream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $softBitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])

    $ocrEngine = $null
    try {
        $langTag = [Windows.Globalization.Language]::new($lang)
        if ([Windows.Media.Ocr.OcrEngine]::IsLanguageSupported($langTag)) {
            $ocrEngine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($langTag)
        }
    } catch {}

    if (-not $ocrEngine) {
        $ocrEngine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
    }
    if (-not $ocrEngine) {
        throw "Windows OCR engine could not be created."
    }

    $result = Await ($ocrEngine.RecognizeAsync($softBitmap)) ([Windows.Media.Ocr.OcrResult])
    Write-Output $result.Text
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
} finally {
    if ($randomStream) { $randomStream.Dispose() }
    if ($stream) { $stream.Dispose() }
}
'''

_WIN_OCR_SCRIPT_B64 = base64.b64encode(_WIN_OCR_SCRIPT.encode("utf-16le")).decode("ascii")


class OCRManager:
    def __init__(self, settings=None):
        self.settings = settings
        self.tesseract_path = None
        self._has_tesseract = False
        self._has_win_ocr = None  # lazy check
        self._check_tesseract()
    
    def _check_tesseract(self):
        """Tesseract'ın kurulu olup olmadığını kontrol et"""
        if not TESSERACT_IMPORTS:
            return False
        
        possible_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            r"C:\Tesseract-OCR\tesseract.exe",
        ]
        
        if self.settings:
            custom_path = self.settings.get("tesseract_path", "")
            if custom_path and Path(custom_path).exists():
                possible_paths.insert(0, custom_path)
        
        for path in possible_paths:
            if Path(path).exists():
                self.tesseract_path = path
                pytesseract.pytesseract.tesseract_cmd = path
                self._has_tesseract = True
                return True
        
        try:
            result = subprocess.run(
                ["tesseract", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            )
            if result.returncode == 0:
                self._has_tesseract = True
                self.tesseract_path = "tesseract"
                return True
        except Exception:
            pass
        
        return False
    
    def _check_win_ocr(self) -> bool:
        """Windows native OCR'nin kullanılabilir olup olmadığını kontrol et"""
        if self._has_win_ocr is not None:
            return self._has_win_ocr
        
        if sys.platform != "win32":
            self._has_win_ocr = False
            return False
        
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null; Write-Output 'OK'"],
                capture_output=True, timeout=10,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            )
            self._has_win_ocr = b"OK" in (result.stdout or b"")
        except Exception:
            self._has_win_ocr = False
        
        print(f"[OCR] Windows native OCR: {'available' if self._has_win_ocr else 'unavailable'}")
        return self._has_win_ocr
    
    def is_available(self) -> bool:
        """OCR kullanılabilir mi? (Tesseract veya Windows native)"""
        if self._has_tesseract:
            return True
        return self._check_win_ocr()
    
    def extract_text(self, image_bytes: bytes, lang: str = "tur+eng") -> Optional[str]:
        """
        Resimden metin çıkar.
        Önce Tesseract dener, yoksa Windows native OCR kullanır.
        """
        if self._has_tesseract:
            result = self._extract_tesseract(image_bytes, lang)
            if result:
                return result
        
        if self._check_win_ocr():
            return self._extract_win_ocr(image_bytes, lang)
        
        return None
    
    def _extract_tesseract(self, image_bytes: bytes, lang: str) -> Optional[str]:
        """Tesseract OCR ile metin çıkar"""
        try:
            image = Image.open(BytesIO(image_bytes))
            try:
                text = pytesseract.image_to_string(image, lang=lang)
            except PermissionError:
                print("[OCR] Tesseract izin hatası")
                return None
            except OSError as e:
                if "740" in str(e):
                    print("[OCR] Tesseract yükseltme gerektiriyor")
                    return None
                raise
            
            text = text.strip()
            return text if text else None
        except Exception as e:
            print(f"[OCR Tesseract] Hata: {e}")
            return None
    
    def _extract_win_ocr(self, image_bytes: bytes, lang: str = "tur+eng") -> Optional[str]:
        """Windows native OCR ile metin çıkar"""
        tmp_path = None
        try:
            # Geçici dosyaya yaz
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name
                tmp.write(image_bytes)
            
            # Dil eşleme (Tesseract format → BCP-47)
            lang_map = {
                "tur": "tr", "eng": "en", "deu": "de", "fra": "fr",
                "spa": "es", "ita": "it", "rus": "ru", "jpn": "ja",
                "chi_sim": "zh-Hans", "chi_tra": "zh-Hant", "kor": "ko",
                "ara": "ar", "por": "pt", "nld": "nl", "pol": "pl",
            }
            
            # İlk dili al (tur+eng → tur → tr)
            first_lang = lang.split("+")[0] if "+" in lang else lang
            win_lang = lang_map.get(first_lang, "en")

            env = os.environ.copy()
            env["CLIPSTACK_OCR_IMAGE_PATH"] = tmp_path
            env["CLIPSTACK_OCR_LANG"] = win_lang
            
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-EncodedCommand",
                    _WIN_OCR_SCRIPT_B64,
                ],
                capture_output=True,
                timeout=30,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                env=env,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            
            if result.returncode == 0:
                text = (result.stdout or "").strip()
                return text if text else None
            else:
                err = (result.stderr or "").strip()
                print(f"[OCR WinNative] Hata: {err}")
                return None
                
        except subprocess.TimeoutExpired:
            print("[OCR WinNative] Zaman aşımı")
            return None
        except Exception as e:
            print(f"[OCR WinNative] Hata: {e}")
            return None
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
    
    def get_engine_name(self) -> str:
        """Hangi OCR engine kullanılıyor"""
        if self._has_tesseract:
            return "Tesseract OCR"
        if self._check_win_ocr():
            return "Windows OCR"
        return "Yok"
    
    def get_install_message(self) -> str:
        """OCR kurulum talimatı mesajı"""
        if self._check_win_ocr():
            return (
                "Windows yerleşik OCR kullanılabilir.\n"
                "Daha iyi sonuçlar için Tesseract OCR'yi de yükleyebilirsiniz:\n\n"
                "https://github.com/UB-Mannheim/tesseract/wiki"
            )
        
        return (
            "OCR (Optik Karakter Tanıma) özelliğini kullanmak için:\n\n"
            "Seçenek 1: Windows 10/11'de yerleşik OCR\n"
            "  Ayarlar > Zaman ve Dil > Dil'den Türkçe ekleyin.\n\n"
            "Seçenek 2: Tesseract OCR\n"
            "  1. https://github.com/UB-Mannheim/tesseract/wiki adresinden indirin\n"
            "  2. Kurulumda Türkçe dil paketini seçin\n"
            "  3. Uygulamayı yeniden başlatın"
        )
