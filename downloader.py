# downloader.py — Fayl yuklab olish va saqlash
# SudParser v3.0

import time
import threading
from pathlib import Path
from typing import Callable, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from api import Publication, COURT_FOLDERS
from state_tracker import StateTracker, DownloadedRecord
from utils import ensure_dir, now_str


class Downloader:
    """
    PDF fayllarni yuklab olish va papkalarga saqlash.
    ThreadPoolExecutor orqali parallel yuklash.
    """

    def __init__(self, api_client, state_tracker: StateTracker, config,
                 csv_logger=None,
                 on_progress: Optional[Callable] = None,
                 on_log: Optional[Callable] = None):
        self._api = api_client
        self._state = state_tracker
        self._config = config
        self._csv_logger = csv_logger
        self._on_progress = on_progress or (lambda *a, **kw: None)
        self._on_log = on_log or (lambda msg: None)

    # ─── Bir martalik toplu yuklash ─────────────────────────────────────────

    def download_all(
        self,
        court_types: list[str],
        stop_event: threading.Event,
        on_done: Optional[Callable] = None,
        source: str = "bir_martalik",
        **filter_kwargs,
    ) -> dict:
        """
        Berilgan yo'nalishlar bo'yicha barcha hujjatlarni yuklab olish.
        Parallel ThreadPoolExecutor ishlatiladi.
        stop_event.set() → to'xtaydi.
        Natija: {"success": N, "failed": N, "skipped": N, "total_bytes": N}
        """
        stats = {"success": 0, "failed": 0, "skipped": 0, "total_bytes": 0}

        with ThreadPoolExecutor(max_workers=self._config.max_workers) as pool:
            futures = {}

            for ct in court_types:
                if stop_event.is_set():
                    break

                self._on_log(f"📂 {ct} yo'nalishi skanlanmoqda...")
                try:
                    for pub in self._api.iter_all_pages(ct, stop_event=stop_event, **filter_kwargs):
                        if stop_event.is_set():
                            break

                        if self._config.skip_existing and self._state.is_downloaded(pub.id):
                            stats["skipped"] += 1
                            self._on_progress(skipped=1)
                            continue

                        if pub.primary_file is None:
                            stats["skipped"] += 1
                            continue

                        future = pool.submit(
                            self.download_publication, pub, ct, source=source
                        )
                        futures[future] = pub
                        time.sleep(self._config.request_delay)

                except Exception as e:
                    self._on_log(f"⚠️ {ct} xatolik: {e}")

            # Natijalarni yig'ish
            for future in as_completed(futures):
                pub = futures[future]
                try:
                    result = future.result()
                    if result == "success":
                        stats["success"] += 1
                        f = pub.primary_file
                        stats["total_bytes"] += f.size if f else 0
                        self._on_progress(success=1)
                    elif result == "skipped":
                        stats["skipped"] += 1
                        self._on_progress(skipped=1)
                    else:
                        stats["failed"] += 1
                        self._on_progress(failed=1)
                except Exception as e:
                    stats["failed"] += 1
                    self._on_log(f"⚠️ Yuklash xatosi: {e}")
                    self._on_progress(failed=1)

        if on_done:
            on_done(stats)
        return stats

    # ─── Bitta hujjatni yuklash ──────────────────────────────────────────────

    def download_publication(
        self,
        pub: Publication,
        court_type: str,
        source: str = "bir_martalik",
    ) -> str:
        """
        Bitta publication ni yuklab papkaga saqlash.
        Qaytaradi: "success" | "skipped" | "failed"
        """
        file_data = pub.primary_file
        if not file_data:
            return "skipped"

        # Saqlash papkasini aniqlash
        folder_rel = COURT_FOLDERS.get(court_type, court_type)
        save_dir = ensure_dir(Path(self._config.download_path) / folder_rel)
        dest = save_dir / pub.filename

        # Mavjud bo'lsa o'tkazib yuborish
        if self._config.skip_existing and dest.exists():
            if not self._state.is_downloaded(pub.id):
                self._state.mark(DownloadedRecord(
                    pub_id=pub.id, file_id=file_data.id,
                    filename=pub.filename, court_type=court_type,
                    downloaded_at=now_str(), file_path=str(dest)
                ))
            return "skipped"

        # Yuklash
        try:
            data = self._api.download_file_bytes(file_data.id)
            dest.write_bytes(data)

            # Holat bazasiga yozish
            record = DownloadedRecord(
                pub_id=pub.id, file_id=file_data.id,
                filename=pub.filename, court_type=court_type,
                downloaded_at=now_str(), file_path=str(dest)
            )
            self._state.mark(record)

            # CSV logi
            if self._csv_logger:
                self._csv_logger.log(
                    court_type=court_type, pub_id=pub.id,
                    file_id=file_data.id, filename=pub.filename,
                    file_size_kb=pub.size_kb, file_path=str(dest),
                    result="success", source=source
                )

            self._on_log(
                f"✅ {pub.filename} yuklandi ({pub.size_kb} KB)"
            )
            return "success"

        except Exception as e:
            err_msg = str(e)
            self._on_log(f"❌ {pub.filename} xatolik: {err_msg}")
            if self._csv_logger:
                self._csv_logger.log(
                    court_type=court_type, pub_id=pub.id,
                    file_id=file_data.id, filename=pub.filename,
                    file_size_kb=pub.size_kb, file_path=str(dest),
                    result=f"failed: {err_msg[:60]}", source=source
                )
            return "failed"