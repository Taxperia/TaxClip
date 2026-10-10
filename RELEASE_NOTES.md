# TaxClip v1.2.4

Clipboard reliability, search accuracy, security hardening, and Settings polish.

## Highlights

- **Reliable image paste:** image cards now copy fresh database content to the Windows clipboard with PNG, DIB, and bitmap formats under a real window owner. This prevents intermittent blank image pastes after copying screenshots.
- **Accurate history search:** search requires every query word to match, supports Turkish character normalization and useful typo tolerance, and excludes internal metadata from visible results.
- **Working search pagination:** Previous and Next keep the active query and load the requested result page instead of showing an empty grid.
- **Filled card pages after deletion:** deleting a card reloads the current page so the next stored item fills the open ninth position.
- **Cleaner Settings UI:** the Security page now uses the same descriptive row layout as General, with compact Google Authenticator actions and clearer explanations.

## User interface

- Removed the dark background behind sidebar icons while preserving the row hover state.
- Removed dotted focus outlines from application buttons.
- Removed borders around the inactivity timeout spin controls.
- Removed the redundant Google Authenticator status row and introductory sentence.
- Reduced the size of Google Authenticator setup, removal, and test buttons.

## Security and privacy

- Added authenticated encrypted backups and strict backup schema and size validation.
- Protected Google Drive tokens and share credentials with Windows protected storage.
- Hardened update downloads with trusted-host, redirect, size, hash, and Authenticode signer checks.
- Added TOTP attempt limiting and replay protection.
- Made unavailable Windows Hello checks fail closed.
- Restricted external image loading to the configured image directory.
- Hardened process execution, resource paths, sensitive-data checks, and dynamic query inputs.
- Added independent security audit and verification reports.

## Validation

- All 47 automated tests pass.
- Native Windows clipboard tests cover PNG, `image/png`, `CF_DIB`, `CF_BITMAP`, repeated copies, real clipboard ownership, and hydrated database payloads.
- Windows executable and bundled version metadata are set to **1.2.4**.

## Install

Download `TaxClip-v1.2.4-windows-x64.zip`, extract it, and run `TaxClip.exe`.

For source installation:

```bash
pip install -r requirements.txt
python main.py
```

**Full Changelog:** https://github.com/Taxperia/TaxClip/compare/v1.2.3...v1.2.4
