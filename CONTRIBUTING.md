# Contributing

Thanks for helping improve TaxClip.

## Before You Start

- Open an issue for larger changes before implementing them.
- Keep pull requests focused on one problem or feature.
- Do not commit local databases, virtual environments, build folders, or generated release archives.

## Local Setup

```bash
pip install -r requirements.txt
python main.py
```

## Tests

Run the test suite before opening a pull request:

```bash
python -m unittest discover tests
```

## Build

To build the Windows distribution:

```bat
build_with_runtime_dir.bat
```

The source repository should not include `build/` or `dist/`; attach build artifacts to GitHub Releases instead.

## Security

Do not open public issues with secrets, credentials, or working exploit details. Share security findings privately with the maintainers.
