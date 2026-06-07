# utils.py — Yordamchi funksiyalar
# SudParser v3.0

import datetime
import os
import sys
import subprocess
from pathlib import Path


def open_path(path: str | Path) -> None:
    """
    Fayl yoki papkani tizimning standart dasturida ochish.
    Cross-platform: Windows, Linux va macOS da ishlaydi.

    - Windows → os.startfile
    - macOS   → open
    - Linux   → xdg-open
    """
    path_str = str(path)
    try:
        if sys.platform.startswith("win"):
            os.startfile(path_str)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path_str])
        else:
            subprocess.Popen(["xdg-open", path_str])
    except Exception:
        pass


def date_to_timestamp(date_str: str) -> int:
    """
    'DD.MM.YYYY' formatidagi sanani Unix millisekund ga aylantirish.
    Misol: '01.01.2024' → 1704056400000

    400 xatosini oldini olish uchun:
    Sana tanlanmagan bo'lsa — None qaytarish, hech qachon 0 yoki null yuborma!
    """
    dt = datetime.datetime.strptime(date_str.strip(), "%d.%m.%Y")
    return int(dt.timestamp() * 1000)


def timestamp_to_date(ts_ms: int) -> str:
    """Unix millisekund → 'DD.MM.YYYY' format"""
    dt = datetime.datetime.fromtimestamp(ts_ms / 1000)
    return dt.strftime("%d.%m.%Y")


def format_size(size_bytes: int) -> str:
    """Baytni odam o'qiy oladigan formatga o'tkazish"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


def get_resource_path(relative_path: str) -> str:
    """
    PyInstaller .exe ichida resurslarni topish.
    Oddiy ishlatishda ham to'g'ri ishlaydi.
    """
    if hasattr(sys, "_MEIPASS"):
        # PyInstaller paketlangan holat
        base_path = Path(sys._MEIPASS)
    else:
        # Oddiy Python muhit
        base_path = Path(__file__).parent
    return str(base_path / relative_path)


def is_frozen() -> bool:
    """Dastur PyInstaller bilan paketlanganmi (SUDPUBLIK.exe / SUDPUBLIK)?"""
    return getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS")


def get_app_data_dir() -> Path:
    """
    Dastur ma'lumotlari (config, log, state) saqlanadigan papka.
    Har doim foydalanuvchi yoza oladigan joyda — shuning uchun SUDPUBLIK ni
    istalgan papkaga qo'yib ishlatish mumkin (boshqa foydalanuvchida ham).
    Misol: /home/<user>/Documents/SUDPUBLIK
    """
    base = Path.home() / "Documents" / "SUDPUBLIK"
    base.mkdir(parents=True, exist_ok=True)
    return base


def ensure_dir(path: str | Path) -> Path:
    """Papkani yaratish (mavjud bo'lsa ham xato bermaydi)"""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def safe_filename(name: str) -> str:
    """Windows uchun xavfsiz fayl nomi (maxsus belgilarni olib tashlash)"""
    invalid = r'\/:*?"<>|'
    for ch in invalid:
        name = name.replace(ch, "_")
    return name.strip()


def now_str(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Hozirgi vaqtni string sifatida qaytarish"""
    return datetime.datetime.now().strftime(fmt)


def now_file_str() -> str:
    """Fayl nomi uchun vaqt formati: YYYYMMDD_HHMMSS"""
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")