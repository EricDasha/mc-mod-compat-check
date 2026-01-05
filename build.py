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

    # Prepare icon
    if os.path.exists("image_1862.png"):
        print("Found image_1862.png, converting to icon.ico...")
        try:
            from PIL import Image
            img = Image.open("image_1862.png")
            # Save as ICO containing multiple sizes for best quality on Windows
            img.save("icon.ico", format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
            print("Conversion successful.")
        except ImportError:
            print("Pillow not installed. Skipping icon conversion. Please run: pip install Pillow")
        except Exception as e:
            print(f"Error converting icon: {e}")

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
