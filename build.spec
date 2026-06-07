# build.spec — PyInstaller konfiguratsiyasi
# SudParser | SUDPUBLIK ijro etiluvchi faylini yaratadi
#
# Ishlatish:
#   Linux/macOS:  pyinstaller build.spec      →  dist/SUDPUBLIK
#   Windows:      pyinstaller build.spec      →  dist/SUDPUBLIK.exe

import sys
import os
from PyInstaller.utils.hooks import collect_all

# Loyiha ildiz papkasi (lokal modullarni topish uchun)
ROOT = os.path.abspath(os.getcwd())

# assets papkasini paketga qo'shish (PyInstaller har OS uchun to'g'ri ajratuvchini qo'yadi)
datas = [("assets", "assets")]
binaries = []
hiddenimports = ["ttkbootstrap", "pystray", "PIL", "PIL.ImageTk", "PIL._tkinter_finder"]

# Loyihaning lokal modullari (main.py ularni funksiya ichida import qiladi —
# PyInstaller avtomatik topa olmasligi mumkin, shuning uchun aniq ko'rsatamiz)
hiddenimports += [
    "gui", "gui.app", "gui.components", "gui.tray",
    "api", "api.client", "api.models", "api.endpoints",
    "config", "downloader", "monitor", "state_tracker", "logger", "utils",
]

# ttkbootstrap va pystray ning barcha ichki modullarini yig'ish
for pkg in ("ttkbootstrap", "pystray"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h


block_cipher = None


a = Analysis(
    ["main.py"],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["selenium", "aiohttp", "bs4"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="SUDPUBLIK",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # GUI dasturi — konsol oynasi ko'rsatilmaydi
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icon.ico",
)
