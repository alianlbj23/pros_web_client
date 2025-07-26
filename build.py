import os
import platform
import shutil
import subprocess
import sys


def install_pyinstaller():
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("[INFO] Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])


def build_executable():
    system = platform.system()
    arch = platform.machine()

    print(f"[INFO] Detected platform: {system} ({arch})")

    main_script = "main.py"
    if not os.path.exists(main_script):
        print("[ERROR] main.py not found.")
        sys.exit(1)

    dist_dir = "dist"
    build_dir = "build"
    spec_file = "main.spec"

    # Clean up old builds
    for path in [dist_dir, build_dir, spec_file]:
        if os.path.exists(path):
            if os.path.isfile(path):
                os.remove(path)
            else:
                shutil.rmtree(path)

    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onefile",  # 把全部打包成一個檔案
        "--clean",
        main_script,
    ]

    print("[INFO] Running PyInstaller...")
    subprocess.check_call(cmd)

    output_file = os.path.join(dist_dir, "main.exe" if system == "Windows" else "main")
    print(f"[SUCCESS] Executable generated: {output_file}")


if __name__ == "__main__":
    install_pyinstaller()
    build_executable()
