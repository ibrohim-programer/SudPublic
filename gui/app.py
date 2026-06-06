# gui/app.py — Asosiy GUI (tkinter + ttkbootstrap darkly mavzu)
# SudParser v3.0 | 850x750 px oyna

import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import time
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

import ttkbootstrap as tb
from ttkbootstrap.constants import *

from api import SudApiClient, COURT_TYPES, INSTANCE_TYPES, DEFAULT_DOC_TYPES
from config import Config
from state_tracker import StateTracker
from logger import CsvLogger, SessionSummary
from downloader import Downloader
from monitor import MonitorEngine
from utils import date_to_timestamp, ensure_dir, get_resource_path, now_str
from gui.components import ScrolledLog, ProgressBar, DateEntry
from gui.tray import TrayManager


class SudParserApp(tb.Window):
    """
    Asosiy dastur oynasi.
    Barcha tarmoq operatsiyalari alohida threadda — GUI hech qachon muzlamaydi.
    """

    APP_TITLE   = "SudParser — public.sud.uz Hujjat Yuklovchi  v3.0"
    WINDOW_SIZE = "850x780"

    def __init__(self):
        super().__init__(themename="darkly")
        self.title(self.APP_TITLE)
        self.geometry(self.WINDOW_SIZE)
        self.resizable(True, True)
        self.minsize(760, 620)

        # Icon o'rnatish
        try:
            icon = get_resource_path("assets/icon.ico")
            self.iconbitmap(icon)
        except Exception:
            pass

        # ─── Asosiy ob'ektlar ─────────────────────────────────────────────
        self.config  = Config.load()
        self.api     = SudApiClient(self.config)
        self.state   = StateTracker(Path(self.config.state_db_path))
        self.csv_log = CsvLogger()
        self.summary = SessionSummary()

        self._stop_event = threading.Event()
        self._work_thread: Optional[threading.Thread] = None
        self._running = False

        # Statistika
        self._stat_success = 0
        self._stat_failed  = 0
        self._stat_skipped = 0
        self._stat_total   = 0

        # Downloader va monitor (keyinroq sozlanadi)
        self.downloader: Optional[Downloader] = None
        self.monitor:    Optional[MonitorEngine] = None

        # ─── GUI qurish ───────────────────────────────────────────────────
        self._build_ui()

        # ─── Tray ─────────────────────────────────────────────────────────
        self.tray = TrayManager(
            on_show=self.deiconify,
            on_quit=self._on_close,
            on_toggle_monitor=self._toggle_monitor_from_tray,
        )
        self.tray.start(get_resource_path("assets/icon.ico"))

        # ─── Hujjat turlarini API dan yuklash ─────────────────────────────
        threading.Thread(target=self._load_doc_types, daemon=True).start()

        # Yopish tugmasini ushlash
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ─────────────────────────────────────────────────────────────────────────
    # UI QURISH
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 4}

        # ── Sarlavha ──────────────────────────────────────────────────────
        hdr = tb.Label(
            self,
            text="🏛️  SudParser — public.sud.uz Hujjat Yuklovchi  v3.0",
            font=("Segoe UI", 13, "bold"),
            bootstyle="inverse-primary",
            anchor="center",
        )
        hdr.pack(fill=X, pady=(0, 4))

        # ── Rejim tanlash ─────────────────────────────────────────────────
        mode_frame = tb.LabelFrame(self, text="⚡ REJA", padding=6)
        mode_frame.pack(fill=X, **pad)
        self._mode_var = tk.StringVar(value="once")
        tb.Radiobutton(mode_frame, text="Bir martalik yuklash",
                       variable=self._mode_var, value="once",
                       bootstyle="primary").pack(side=LEFT, padx=12)
        tb.Radiobutton(mode_frame, text="Monitoring rejimi (Avto-yangilash)",
                       variable=self._mode_var, value="monitor",
                       bootstyle="success").pack(side=LEFT, padx=12)

        # ── Yo'nalishlar ──────────────────────────────────────────────────
        ct_frame = tb.LabelFrame(self, text="📂 YO'NALISH (bir yoki bir necha tanlang)", padding=6)
        ct_frame.pack(fill=X, **pad)
        self._ct_vars: dict[str, tk.BooleanVar] = {}
        row1 = tb.Frame(ct_frame); row1.pack(fill=X)
        row2 = tb.Frame(ct_frame); row2.pack(fill=X)
        items = list(COURT_TYPES.items())
        for i, (code, label) in enumerate(items):
            var = tk.BooleanVar(value=(code == "ECONOMIC"))
            self._ct_vars[code] = var
            row = row1 if i < 3 else row2
            tb.Checkbutton(row, text=label, variable=var,
                           bootstyle="primary-round-toggle").pack(side=LEFT, padx=8, pady=2)

        # ── Filtrlar ──────────────────────────────────────────────────────
        flt_frame = tb.LabelFrame(self, text="🔍 FILTRLAR (ixtiyoriy)", padding=6)
        flt_frame.pack(fill=X, **pad)

        row_a = tb.Frame(flt_frame); row_a.pack(fill=X, pady=2)
        tb.Label(row_a, text="Hujjat turi:", width=14, anchor="w").pack(side=LEFT)
        self._type_var = tk.StringVar()
        self._type_cb  = tb.Combobox(row_a, textvariable=self._type_var, width=24, state="readonly")
        self._type_cb["values"] = [d["name"] for d in DEFAULT_DOC_TYPES]
        self._type_cb.set(DEFAULT_DOC_TYPES[0]["name"])
        self._type_cb.pack(side=LEFT, padx=(0, 20))

        tb.Label(row_a, text="Instansiya:", width=12, anchor="w").pack(side=LEFT)
        self._inst_var = tk.StringVar()
        inst_cb = tb.Combobox(row_a, textvariable=self._inst_var, width=22, state="readonly")
        inst_cb["values"] = list(INSTANCE_TYPES.values())
        inst_cb.set(list(INSTANCE_TYPES.values())[0])
        inst_cb.pack(side=LEFT)
        self._inst_cb = inst_cb

        row_b = tb.Frame(flt_frame); row_b.pack(fill=X, pady=2)
        tb.Label(row_b, text="Sana (dan):", width=14, anchor="w").pack(side=LEFT)
        self._date_from = DateEntry(row_b)
        self._date_from.pack(side=LEFT, padx=(0, 20))
        tb.Label(row_b, text="(gacha):", width=10, anchor="w").pack(side=LEFT)
        self._date_to = DateEntry(row_b)
        self._date_to.pack(side=LEFT, padx=(0, 20))
        tb.Label(row_b, text="Ish raqami:", width=12, anchor="w").pack(side=LEFT)
        self._case_var = tk.StringVar()
        tb.Entry(row_b, textvariable=self._case_var, width=16).pack(side=LEFT)

        # ── Saqlash joyi ──────────────────────────────────────────────────
        path_frame = tb.LabelFrame(self, text="💾 SAQLASH JOYI", padding=6)
        path_frame.pack(fill=X, **pad)
        self._path_var = tk.StringVar(value=self.config.download_path)
        tb.Entry(path_frame, textvariable=self._path_var, width=60).pack(side=LEFT, fill=X, expand=True)
        tb.Button(path_frame, text="📁 Ko'rish", command=self._browse_path,
                  bootstyle="secondary-outline", width=10).pack(side=LEFT, padx=6)

        # ── Sozlamalar ────────────────────────────────────────────────────
        cfg_frame = tb.LabelFrame(self, text="⚙️  SOZLAMALAR", padding=6)
        cfg_frame.pack(fill=X, **pad)
        row_c = tb.Frame(cfg_frame); row_c.pack(fill=X, pady=2)
        tb.Label(row_c, text="Bir vaqtdagi yuklamalar:", width=24, anchor="w").pack(side=LEFT)
        self._workers_var = tk.IntVar(value=self.config.max_workers)
        tb.Spinbox(row_c, from_=1, to=20, textvariable=self._workers_var, width=5).pack(side=LEFT, padx=(0, 20))
        tb.Label(row_c, text="So'rovlar oralig'i (s):", width=22, anchor="w").pack(side=LEFT)
        self._delay_var = tk.DoubleVar(value=self.config.request_delay)
        tb.Spinbox(row_c, from_=0, to=10, increment=0.1, textvariable=self._delay_var,
                   format="%.1f", width=6).pack(side=LEFT)

        row_d = tb.Frame(cfg_frame); row_d.pack(fill=X, pady=2)
        tb.Label(row_d, text="Monitoring: tekshirish oralig'i (daqiqa):", width=36, anchor="w").pack(side=LEFT)
        self._interval_var = tk.IntVar(value=self.config.monitor_interval_minutes)
        tb.Spinbox(row_d, from_=1, to=1440, textvariable=self._interval_var, width=6).pack(side=LEFT, padx=(0, 20))
        self._skip_var2 = tk.BooleanVar(value=self.config.skip_existing)
        tb.Checkbutton(row_d, text="Mavjud fayllarni o'tkazib yubor",
                       variable=self._skip_var2, bootstyle="primary").pack(side=LEFT)

        # ── Tugmalar ──────────────────────────────────────────────────────
        btn_frame = tb.Frame(self)
        btn_frame.pack(fill=X, **pad)
        self._btn_start = tb.Button(btn_frame, text="▶ YUKLAB OLISHNI BOSHLASH",
                                    command=self._start_download,
                                    bootstyle="primary", width=26)
        self._btn_start.pack(side=LEFT, padx=4)
        self._btn_monitor = tb.Button(btn_frame, text="📡 MONITORINGNI YOQISH",
                                      command=self._start_monitor,
                                      bootstyle="success", width=24)
        self._btn_monitor.pack(side=LEFT, padx=4)
        self._btn_stop = tb.Button(btn_frame, text="⏹ TO'XTATISH",
                                   command=self._stop_all,
                                   bootstyle="danger", width=14, state="disabled")
        self._btn_stop.pack(side=LEFT, padx=4)

        # ── Progress ──────────────────────────────────────────────────────
        prog_frame = tb.LabelFrame(self, text="PROGRESS", padding=6)
        prog_frame.pack(fill=X, **pad)
        self._progressbar = ProgressBar(prog_frame)
        self._progressbar.pack(fill=X)
        self._status_var = tk.StringVar(value="Tayyor")
        tb.Label(prog_frame, textvariable=self._status_var,
                 bootstyle="info", anchor="w").pack(fill=X)

        # ── Log ───────────────────────────────────────────────────────────
        log_frame = tb.LabelFrame(self, text="📋 LOG", padding=4)
        log_frame.pack(fill=BOTH, expand=True, **pad)
        btn_log_row = tb.Frame(log_frame)
        btn_log_row.pack(fill=X)
        tb.Button(btn_log_row, text="📂 Papkani Ochish",
                  command=self._open_folder,   bootstyle="info-outline",  width=18).pack(side=LEFT, padx=4)
        tb.Button(btn_log_row, text="📊 CSV Hisobot",
                  command=self._open_csv_log,  bootstyle="warning-outline", width=14).pack(side=LEFT, padx=4)
        tb.Button(btn_log_row, text="🗑 Tozala",
                  command=lambda: self._log.clear(), bootstyle="secondary-outline", width=10).pack(side=RIGHT, padx=4)
        self._log = ScrolledLog(log_frame, height=12)
        self._log.pack(fill=BOTH, expand=True, pady=(4, 0))

    # ─────────────────────────────────────────────────────────────────────────
    # GUI YORDAMCHI METODLAR
    # ─────────────────────────────────────────────────────────────────────────

    def _log_msg(self, msg: str) -> None:
        """Thread-safe log yozish"""
        ts = datetime.now().strftime("%H:%M:%S")
        self.after(0, lambda: self._log.append(f"[{ts}] {msg}"))

    def _set_status(self, status: str) -> None:
        self.after(0, lambda: self._status_var.set(status))

    def _update_progress(self, *, success: int = 0, failed: int = 0, skipped: int = 0) -> None:
        self._stat_success += success
        self._stat_failed  += failed
        self._stat_skipped += skipped
        s, f, sk, t = self._stat_success, self._stat_failed, self._stat_skipped, self._stat_total
        self.after(0, lambda: self._progressbar.update(s, f, sk, t))

    def _get_selected_court_types(self) -> list[str]:
        return [code for code, var in self._ct_vars.items() if var.get()]

    def _get_filter_kwargs(self) -> dict:
        kwargs: dict = {}
        ms_from = self._date_from.get_ms()
        ms_to   = self._date_to.get_ms()
        if ms_from:
            kwargs["start_date_ms"] = ms_from
        if ms_to:
            kwargs["end_date_ms"] = ms_to

        # Hujjat turi
        sel_name = self._type_var.get()
        for d in self._doc_types:
            if d["name"] == sel_name and d["id"] != 0:
                kwargs["type_id"] = d["id"]
                break

        # Instansiya
        sel_inst = self._inst_var.get()
        for code, label in INSTANCE_TYPES.items():
            if label == sel_inst and code:
                kwargs["instance_type"] = code
                break

        # Ish raqami
        case = self._case_var.get().strip()
        if case:
            kwargs["case_number"] = case

        return kwargs

    def _apply_settings(self) -> None:
        """Sozlamalarni config ga qo'llash"""
        self.config.download_path = self._path_var.get() or "./Sud_Hujjatlari"
        self.config.max_workers   = max(1, self._workers_var.get())
        self.config.request_delay = max(0.0, self._delay_var.get())
        self.config.skip_existing = self._skip_var2.get()
        self.config.monitor_interval_minutes = max(1, self._interval_var.get())
        self.config.monitor_interval_seconds = self.config.monitor_interval_minutes * 60
        self.config.save()

    def _browse_path(self) -> None:
        folder = filedialog.askdirectory(title="Saqlash papkasini tanlang",
                                         initialdir=self._path_var.get())
        if folder:
            self._path_var.set(folder)

    def _open_folder(self) -> None:
        path = Path(self._path_var.get())
        ensure_dir(path)
        os.startfile(str(path))

    def _open_csv_log(self) -> None:
        import glob
        files = sorted(glob.glob("logs/download_log_*.csv"), reverse=True)
        if files:
            os.startfile(files[0])
        else:
            messagebox.showinfo("Ma'lumot", "CSV log fayli topilmadi.")

    def _set_buttons(self, running: bool) -> None:
        self._btn_start["state"]   = "disabled" if running else "normal"
        self._btn_monitor["state"] = "disabled" if running else "normal"
        self._btn_stop["state"]    = "normal" if running else "disabled"

    def _reset_stats(self) -> None:
        self._stat_success = self._stat_failed = self._stat_skipped = self._stat_total = 0
        self._progressbar.reset()

    # ─────────────────────────────────────────────────────────────────────────
    # AMALLAR
    # ─────────────────────────────────────────────────────────────────────────

    def _start_download(self) -> None:
        """Bir martalik toplu yuklash"""
        court_types = self._get_selected_court_types()
        if not court_types:
            messagebox.showwarning("Ogohlantirish", "Kamida bitta yo'nalish tanlang!")
            return
        if self._running:
            return

        self._apply_settings()
        self._reset_stats()
        self._stop_event.clear()
        self._running = True
        self._set_buttons(True)
        self._set_status("Skanlanmoqda...")
        self.summary.reset()
        self.summary.mode = "bir_martalik"
        self.summary.court_types = court_types

        filter_kw = self._get_filter_kwargs()
        self._log_msg(f"▶ Yuklash boshlandi: {', '.join(court_types)}")

        # Jami hujjatlar sonini oldindan aniqlash (isteğe bağlı)
        threading.Thread(target=self._prefetch_total,
                         args=(court_types, filter_kw),
                         daemon=True).start()

        self._work_thread = threading.Thread(
            target=self._download_worker,
            args=(court_types, filter_kw),
            daemon=True,
        )
        self._work_thread.start()

    def _prefetch_total(self, court_types: list[str], filter_kw: dict) -> None:
        """Jami hujjatlar sonini birinchi sahifadan taxminlash"""
        total = 0
        for ct in court_types:
            try:
                resp = self.api.fetch_page(ct, page=0, size=1, **filter_kw)
                total += resp.totalElements
            except Exception:
                pass
        if total:
            self._stat_total = total
            self.after(0, lambda: self._progressbar.update(0, 0, 0, total))

    def _download_worker(self, court_types: list[str], filter_kw: dict) -> None:
        """Yuklash ipi (thread)"""
        self.downloader = Downloader(
            api_client=self.api,
            state_tracker=self.state,
            config=self.config,
            csv_logger=self.csv_log,
            on_progress=self._update_progress,
            on_log=self._log_msg,
        )
        try:
            stats = self.downloader.download_all(
                court_types=court_types,
                stop_event=self._stop_event,
                source="bir_martalik",
                **filter_kw,
            )
            self.summary.success  = stats["success"]
            self.summary.failed   = stats["failed"]
            self.summary.skipped  = stats["skipped"]
            self.summary.total_bytes = stats["total_bytes"]
            summary_file = self.summary.save()
            self._log_msg(
                f"✅ Yakunlandi! Muvaffaqiyatli: {stats['success']}, "
                f"Xato: {stats['failed']}, O'tkazildi: {stats['skipped']}"
            )
            self._log_msg(f"📊 Xulosa saqlandi: {summary_file}")
        except Exception as e:
            self._log_msg(f"❌ Umumiy xatolik: {e}")
        finally:
            self._running = False
            self.after(0, lambda: self._set_buttons(False))
            self.after(0, lambda: self._set_status("Tayyor"))

    def _start_monitor(self) -> None:
        """Monitoring rejimini yoqish"""
        court_types = self._get_selected_court_types()
        if not court_types:
            messagebox.showwarning("Ogohlantirish", "Kamida bitta yo'nalish tanlang!")
            return
        if self._running:
            return

        self._apply_settings()
        self._stop_event.clear()
        self._running = True
        self._set_buttons(True)
        self.summary.reset()
        self.summary.mode = f"Monitoring ({self.config.monitor_interval_minutes} daqiqada bir)"
        self.summary.court_types = court_types

        dl = Downloader(
            api_client=self.api,
            state_tracker=self.state,
            config=self.config,
            csv_logger=self.csv_log,
            on_progress=self._update_progress,
            on_log=self._log_msg,
        )
        self.monitor = MonitorEngine(
            api_client=self.api,
            downloader=dl,
            state_tracker=self.state,
            config=self.config,
            on_new_file=self._on_new_file,
            on_log=self._log_msg,
            on_status=self._set_status,
        )
        self.monitor.start(court_types)

    def _on_new_file(self, pub, court_type: str) -> None:
        """Yangi fayl topilganda (monitoring)"""
        self.summary.new_found += 1
        msg = f"📡 YANGI HUJJAT: {pub.filename} ({pub.size_kb} KB) — {court_type}"
        self._log_msg(msg)
        if self.config.notify_on_new_file:
            self.tray.notify("SudParser — Yangi Hujjat", msg)

    def _stop_all(self) -> None:
        """Barcha operatsiyalarni to'xtatish"""
        self._stop_event.set()
        if self.monitor and self.monitor.is_running:
            self.monitor.stop()
        self._running = False
        self._set_buttons(False)
        self._set_status("To'xtatildi")
        self._log_msg("⏹ Foydalanuvchi tomonidan to'xtatildi")

    def _toggle_monitor_from_tray(self) -> None:
        """Tray menusidan monitoring ni yoqish/o'chirish"""
        if self.monitor and self.monitor.is_running:
            self._stop_all()
        else:
            self._start_monitor()

    def _load_doc_types(self) -> None:
        """API dan hujjat turlarini yuklash"""
        try:
            types = self.api.get_types()
            self._doc_types = [{"id": 0, "name": "Barchasi"}] + types
            names = [d["name"] for d in self._doc_types]
            self.after(0, lambda: self._type_cb.configure(values=names))
        except Exception:
            self._doc_types = DEFAULT_DOC_TYPES

    def _on_close(self) -> None:
        """Dasturni to'g'ri yopish"""
        self._stop_event.set()
        if self.monitor:
            self.monitor.stop()
        try:
            self.csv_log.close()
        except Exception:
            pass
        self.tray.stop()
        self.destroy()