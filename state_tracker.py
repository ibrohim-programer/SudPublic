# state_tracker.py — Yuklangan hujjatlar JSON bazasi
# SudParser v3.0 | Monitoring rejimi uchun muhim

import json
import threading
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional
from utils import now_str


@dataclass
class DownloadedRecord:
    """Bitta yuklangan hujjat yozuvi"""
    pub_id:        int    # Publication ID
    file_id:       int    # FileData ID
    filename:      str    # Lokal fayl nomi (1221154_53831.pdf)
    court_type:    str    # ECONOMIC, CRIMINAL, ...
    downloaded_at: str    # Vaqt (YYYY-MM-DD HH:MM:SS)
    file_path:     str    # To'liq saqlash yo'li


class StateTracker:
    """
    Yuklangan hujjatlar bazasi (JSON fayl).
    Monitoring rejimida:
      - pub_id → allaqachon yuklanganmi? deb tekshiradi
      - court_type bo'yicha eng oxirgi pub_id saqlanadi
    Thread-safe (Lock ishlatiladi).
    Dastur qayta ishga tushsa ham eslab qoladi.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._lock = threading.Lock()
        self._downloaded: dict[int, DownloadedRecord] = {}  # pub_id → yozuv
        self._last_ids:   dict[str, int] = {}               # court_type → max pub_id
        self._load()

    # ─── Ommaviy metodlar ───────────────────────────────────────────────────

    def is_downloaded(self, pub_id: int) -> bool:
        """Hujjat yuklanganmi?"""
        with self._lock:
            return pub_id in self._downloaded

    def mark(self, record: DownloadedRecord) -> None:
        """Yangi yuklanganlar ro'yxatiga qo'shish va saqlash"""
        with self._lock:
            self._downloaded[record.pub_id] = record
            # court_type bo'yicha maksimal ID ni yangilash
            current = self._last_ids.get(record.court_type, 0)
            if record.pub_id > current:
                self._last_ids[record.court_type] = record.pub_id
            self._save_unsafe()

    def get_last_id(self, court_type: str) -> Optional[int]:
        """Monitoring: bu yo'nalishda eng oxirgi yuklangan publication ID"""
        with self._lock:
            return self._last_ids.get(court_type)

    def total_count(self) -> int:
        """Jami yuklangan hujjatlar soni"""
        with self._lock:
            return len(self._downloaded)

    def reset(self) -> None:
        """Bazani tozalash (faqat xotira; faylni o'chirmaydi)"""
        with self._lock:
            self._downloaded.clear()
            self._last_ids.clear()
            self._save_unsafe()

    # ─── Ichki metodlar ─────────────────────────────────────────────────────

    def _load(self) -> None:
        """JSON fayldan yuklash"""
        if not self.db_path.exists():
            return
        try:
            with open(self.db_path, encoding="utf-8") as f:
                data = json.load(f)

            for k, v in data.get("downloaded", {}).items():
                try:
                    rec = DownloadedRecord(**v)
                    self._downloaded[int(k)] = rec
                except Exception:
                    pass

            for k, v in data.get("last_ids", {}).items():
                try:
                    self._last_ids[k] = int(v)
                except Exception:
                    pass
        except Exception:
            # Buzilgan DB — bo'sh boshlaymiz
            self._downloaded = {}
            self._last_ids = {}

    def _save_unsafe(self) -> None:
        """Lock olmagan holda saqlash (ichki foydalanish uchun)"""
        try:
            data = {
                "downloaded": {
                    str(k): asdict(v)
                    for k, v in self._downloaded.items()
                },
                "last_ids": self._last_ids,
            }
            # Avval vaqtinchalik faylga yozib, so'ng almashtirish (atom)
            tmp = self.db_path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            tmp.replace(self.db_path)
        except Exception:
            pass