# TaxClip v1.2.2

Security and quality maintenance release, plus refreshed English documentation.

## Highlights

- **Dependencies:** Pillow bumped to **12.3.0** (closes Dependabot CVE alerts)
- **Code quality:** Clipboard dedupe fingerprints no longer use cryptographic hashes on sensitive clipboard text (fixes CodeQL `py/weak-sensitive-data-hashing`)
- **Docs:** README, LICENSE, release notes, and GitHub / app description refreshed in English

## Security & quality

- Address all open Dependabot alerts for Pillow (&lt; 12.3.0)
- Replace SHA-256 / Blake2b clipboard fingerprints with a non-crypto content ID (`length` + Adler32 + CRC32) used only for short-lived deduplication — not for password storage or authentication
- Re-enable / re-run CodeQL; Security and quality overview should show **0** open alerts on `main`

## Documentation

- Full English **README** with current feature set (smart cards, secret mode, compact panel, files, encryption, etc.)
- English **Miyotu Software License** (same terms: personal / educational use; no commercial use; attribution required)
- Updated product description for GitHub and the in-app About defaults

## Install

```bash
pip install -r requirements.txt
python main.py
```

Windows EXE packages may be attached to this release when available; running from source is fully supported.

**Full Changelog:** https://github.com/Taxperia/TaxClip/compare/v1.2.1...v1.2.2
