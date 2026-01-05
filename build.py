import os
import subprocess
import sys
import shutil

def build():
    # Install PyInstaller if missing
    try:
        import PyInstaller
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Check for icon
    icon_option = []
    if os.path.exists("icon.ico"):
        icon_option = ["--icon=icon.ico"]
    elif os.path.exists("app.ico"):
        icon_option = ["--icon=app.ico"]
    else:
        print("Warning: No icon found (icon.ico or app.ico). Building with default icon.")

    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name", "ModSupportCheck",
        "--clean",
    ] + icon_option + ["mod_support_check.py"]
    
    print(f"Running: {' '.join(cmd)}")
    subprocess.check_call(cmd)
    print("Build complete. Check 'dist' folder.")

if __name__ == "__main__":
    build()
