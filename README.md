# Mod Support Check Tool

Minecraft Mod version compatibility detection tool.

## Features
- Detects mod loader (Forge, NeoForge, Fabric, Quilt, LiteLoader)
- Checks Minecraft version compatibility
- Supports reading metadata from `.jar`, `.zip`, `.litemod`
- Network check via Modrinth API
- Multilingual support (English, Simplified Chinese, Traditional Chinese, Japanese, Korean)

## Usage
### GUI
Run the executable directly.

### CLI
```bash
mod_support_check.exe --mc-version 1.20.1 --loader any --mods-dir "C:\Path\To\Mods"
```

## Building
1. Install Python 3.12+
2. Install PyInstaller: `pip install pyinstaller`
3. Run build: `python build.py`
