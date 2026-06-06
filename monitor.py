# monitor.py — Real-time monitoring engine
# SudParser v3.0 | Har N daqiqada yangi hujjatlarni tekshiradi

import threading
import time
from typing import Callable
from datetime import datetime

from api.models import Publication


class MonitorEngine:
    """
    Real-time monitoring: har N daqiqada yangi hujjatlarni tekshiradi.
    Yangi hujjat topilsa → yuklab oladi → GUI + tray ga xabar beradi.
    Thread-safe. Bir nechta court_type parallel kuzatiladi.
    """

    def __init__(
        self,
        api_client,
        downloader,
        state_tracker,
        config,
        on_new_file:   Callable,   # (pub: Publication, court_type: str) → None
        on_log:        Callable,   # (message: str) → None
        on_status:     Callable,   # (status: str) → None
    ):
        self._api      = api_client
        self._dl       = downloader
        self._state    = state_tracker
        self._config   = config
        self._on_new   = on_new_file
        self._on_log   = on_log
        self._on_status = on_status

        self._stop   = threading.Event()
        self._thread: threading.Thread | None = None
        self.is_running  = False
        self.new_count   = 0     # Sessiyada topilgan yangi fayllar soni
        self.check_count = 0     # Jami tekshiruv sikllari

    # ─── Boshqaruv ──────────────────────────────────────────────────────────

    def start(self, court_types: list[str]) -> None:
        """Monitoring ni boshlash"""
        if self.is_running:
            return
        self._stop.clear()
        self.is_running = True
        self._thread = threading.Thread(
            target=self._loop,
            args=(court_types,),
            daemon=True,
            name="MonitorThread",
        )
        self._thread.start()
        self._on_log("📡 Monitoring rejimi yoqildi")

    def stop(self) -> None:
        """Monitoring ni to'xtatish"""
        self._stop.set()
        self.is_running = False
        self._on_log("⏹ Monitoring to'xtatildi")

    def restart(self, court_types: list[str]) -> None:
        """Monitoring ni qayta ishga tushirish"""
        self.stop()
        time.sleep(0.5)
        self.start(court_types)

    # ─── Asosiy sikl ────────────────────────────────────────────────────────

    def _loop(self, court_types: list[str]) -> None:
        """Monitoring siklining asosiy ko'chasi"""
        while not self._stop.is_set():
            self.check_count += 1
            self._on_log(
                f"📡 Monitoring tekshiruvi #{self.check_count} boshlandi "
                f"({', '.join(court_types)})"
            )
            found = 0

            for ct in court_types:
                if self._stop.is_set():
                    break
                found += self._check_court_type(ct)

            if found:
                self._on_log(
                    f"📡 Monitoring: {found} ta yangi hujjat topildi va yuklandi"
                )
            else:
                self._on_log("📡 Monitoring: yangi hujjat yo'q")

            if not self._stop.is_set():
                next_time = datetime.fromtimestamp(
                    time.time() + self._config.monitor_interval_seconds
                ).strftime("%H:%M")
                self._on_status(f"FAOL | Keyingi tekshiruv: {next_time} da")

                # Keyingi tekshiruvgacha kutish (to'xtatish signali kuzatiladi)
                self._stop.wait(timeout=self._config.monitor_interval_seconds)

    def _check_court_type(self, court_type: str) -> int:
        """
        Yo'nalishni tekshirish, yangi hujjatlarni yuklash.
        Faqat 1-sahifa (page=0, size=50) — sayt yukiga tejamkor.
        Qaytaradi: topilgan yangi hujjatlar soni.
        """
        try:
            last_id = self._state.get_last_id(court_type) or 0
            publications = self._api.get_latest(court_type, size=50)

            # Faqat yangi (katta ID li) hujjatlar
            new_pubs = [p for p in publications if p.id > last_id]
            if not new_pubs:
                return 0

            count = 0
            for pub in new_pubs:
                if self._stop.is_set():
                    break
                if self._state.is_downloaded(pub.id):
                    continue

                result = self._dl.download_publication(
                    pub, court_type, source="monitoring"
                )
                if result == "success":
                    count += 1
                    self.new_count += 1
                    # GUI va tray ga bildiruv
                    try:
                        self._on_new(pub, court_type)
                    except Exception:
                        pass

                time.sleep(self._config.request_delay)

            return count

        except Exception as e:
            self._on_log(f"⚠️ {court_type} monitoring xatosi: {e}")
            return 0