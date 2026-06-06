# logger.py — Logging tizimi
# SudParser v3.0

import logging
import csv
import os
from pathlib import Path
from datetime import datetime
from utils import now_str, now_file_str, ensure_dir


def setup_logger(log_level: str = "INFO", log_dir: str = "./logs") -> logging.Logger:
    """Asosiy logger ni sozlash"""
    ensure_dir(log_dir)
    log_file = Path(log_dir) / f"sudparser_{datetime.now().strftime('%Y%m%d')}.log"

    level = getattr(logging, log_level.upper(), logging.INFO)
    logger = logging.getLogger("SudParser")
    logger.setLevel(level)

    if not logger.handlers:
        # Fayl handler
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        logger.addHandler(fh)

        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.WARNING)
        ch.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger.addHandler(ch)

    return logger


class CsvLogger:
    """
    Yuklangan fayllar CSV logi.
    Format: timestamp, court_type, pub_id, file_id, filename, file_size_kb, file_path, result, source
    """
    HEADERS = [
        "timestamp", "court_type", "pub_id", "file_id",
        "filename", "file_size_kb", "file_path", "result", "source"
    ]

    def __init__(self, log_dir: str = "./logs"):
        self.log_dir = Path(log_dir)
        ensure_dir(self.log_dir)
        self._file: Path | None = None
        self._writer = None
        self._handle = None
        self._open_today_file()

    def _open_today_file(self) -> None:
        """Bugungi kun uchun CSV faylni ochish/yaratish"""
        date_str = datetime.now().strftime("%Y%m%d")
        new_file = self.log_dir / f"download_log_{date_str}.csv"

        # Eski fayl boshqa kun bo'lsa yoping
        if self._handle and self._file != new_file:
            self._handle.close()
            self._handle = None

        if not self._handle:
            file_exists = new_file.exists()
            self._handle = open(new_file, "a", newline="", encoding="utf-8")
            self._writer = csv.DictWriter(self._handle, fieldnames=self.HEADERS)
            if not file_exists:
                self._writer.writeheader()
            self._file = new_file

    def log(
        self,
        court_type: str,
        pub_id: int,
        file_id: int,
        filename: str,
        file_size_kb: float,
        file_path: str,
        result: str,
        source: str = "bir_martalik",
    ) -> None:
        """Bitta yozuv qo'shish"""
        # Kun almashgan bo'lsa yangi fayl
        self._open_today_file()
        self._writer.writerow({
            "timestamp":    now_str(),
            "court_type":   court_type,
            "pub_id":       pub_id,
            "file_id":      file_id,
            "filename":     filename,
            "file_size_kb": file_size_kb,
            "file_path":    file_path,
            "result":       result,
            "source":       source,
        })
        self._handle.flush()

    def close(self) -> None:
        if self._handle:
            self._handle.close()
            self._handle = None


class SessionSummary:
    """Sessiya yakunida statistika chiqarish"""

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self.mode = "bir_martalik"
        self.court_types: list[str] = []
        self.check_cycles = 0
        self.new_found = 0
        self.success = 0
        self.failed = 0
        self.skipped = 0
        self.total_bytes = 0
        self.start_time = datetime.now()

    def save(self, log_dir: str = "./logs") -> str:
        """Sessiya xulosasini faylga saqlash"""
        ensure_dir(log_dir)
        fname = Path(log_dir) / f"summary_{now_file_str()}.txt"
        elapsed = datetime.now() - self.start_time
        elapsed_str = str(elapsed).split(".")[0]

        lines = [
            "=== SudParser Sessiya Xulosasi ===",
            f"Boshlanish vaqti : {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Davomiyligi       : {elapsed_str}",
            f"Ish rejimi        : {self.mode}",
            f"Yo'nalishlar      : {', '.join(self.court_types) if self.court_types else '—'}",
            f"Jami tekshiruv    : {self.check_cycles}",
            f"Yangi topilgan    : {self.new_found}",
            f"Muvaffaqiyatli    : {self.success}",
            f"O'tkazib yuborildi: {self.skipped}",
            f"Xatolik           : {self.failed}",
            f"Umumiy hajm       : {self.total_bytes / (1024*1024):.2f} MB",
        ]

        fname.write_text("\n".join(lines), encoding="utf-8")
        return str(fname)