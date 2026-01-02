# Minecraft Mod Compatibility Checker (Refactored)

A powerful tool to check Minecraft mod compatibility (Game Version & Loader) using both Online APIs (Modrinth, CurseForge) and Local Metadata.

## Features

- **Refactored Architecture**: Modular design with clear separation of concerns (Core, API, Checker, GUI).
- **Dual Verification**:
  - **Online**: Checks against Modrinth and CurseForge APIs using file hashes.
  - **Local**: Parses `fabric.mod.json`, `mods.toml`, etc. directly from JAR files.
- **Configurable Strategies**: Choose Online, Local, or both.
- **Robust Networking**: Automatic retries, timeout handling, and connection checks.
- **Modern GUI**: Clean `tkinter` interface with professional styling.
- **Internationalization**: Support for multiple languages (English, Simplified Chinese, Traditional Chinese, Japanese, Korean).

## Installation

1. Ensure Python 3.8+ is installed.
2. Clone the repository.
3. Run the application:

```bash
python main.py
```

## Migration Guide (v2 -> v3)

This project has been completely refactored from a single script to a Python package structure.

### Changes
- **Entry Point**: Changed from `mc_mod_compat_check.py` to `main.py`.
- **Config**: Settings are now saved in `mod_compat_config.json` automatically.
- **Cache**: Uses `.mod_compat_cache.json` (if implemented in future, currently direct API).

### How to Upgrade
1. Delete the old `mc_mod_compat_check.py`.
2. Use the new `src/` directory and `main.py`.
3. Your old `mod_compat_config.json` is compatible (keys might be reset if structure changed significantly, but it will be recreated).

## Internationalization (i18n)

The application supports dynamic language switching.

### Supported Languages
- English (US)
- 简体中文 (Simplified Chinese)
- 繁體中文 (Traditional Chinese)
- 日本語 (Japanese)
- 한국어 (Korean)

### How to Add a New Language
1. Create a new JSON file in `src/mc_mod_compat/locales/` (e.g., `fr_FR.json`).
2. Copy the structure from `en_US.json`.
3. Translate the values.
4. Restart the application. The new language will appear in the "Language" dropdown automatically.

### Updating Translations
- Edit the corresponding JSON file in `src/mc_mod_compat/locales/`.
- The application reloads translations on startup or when switching languages.

## Development

- **Tests**: Run `python tests/test_core.py` (ensure `src` is in PYTHONPATH).
- **Structure**:
  - `src/mc_mod_compat/api`: API Clients
  - `src/mc_mod_compat/checker`: Verification Logic (Strategies)
  - `src/mc_mod_compat/core`: Hashing & Metadata Parsing
  - `src/mc_mod_compat/gui`: User Interface
  - `src/mc_mod_compat/locales`: Translation files

## License

MIT
