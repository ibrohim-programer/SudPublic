# main.py — Dastur kirish nuqtasi
# SudParser v3.0 | python main.py yoki SudParser.exe

import sys
import os


def main():
    """SudParser GUI ni ishga tushirish"""
    # PyInstaller muhitida current directory ni to'g'rilash
    if hasattr(sys, "_MEIPASS"):
        os.chdir(os.path.dirname(sys.executable))

    # Loglar papkasini yaratish
    from pathlib import Path
    Path("logs").mkdir(exist_ok=True)

    # Dasturni ishga tushirish
    from gui.app import SudParserApp
    app = SudParserApp()
    app.mainloop()


if __name__ == "__main__":
    main()