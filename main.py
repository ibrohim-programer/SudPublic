# main.py — Dastur kirish nuqtasi
# SUDPUBLIK | python main.py  yoki  SUDPUBLIK(.exe)

import sys
import os
from pathlib import Path


def main():
    """SUDPUBLIK GUI ni ishga tushirish"""
    from utils import is_frozen, get_app_data_dir

    # Paketlangan (SUDPUBLIK.exe) holatda — ma'lumotlarni foydalanuvchining
    # yoziladigan papkasiga saqlaymiz. Shunda binarni istalgan joyga qo'yib
    # ishlatish mumkin (boshqa foydalanuvchida ham).
    if is_frozen():
        os.chdir(str(get_app_data_dir()))

    # Loglar papkasini yaratish
    Path("logs").mkdir(exist_ok=True)

    # Dasturni ishga tushirish
    from gui.app import SudParserApp
    app = SudParserApp()
    app.mainloop()


if __name__ == "__main__":
    main()
