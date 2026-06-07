# gui/app.py — Asosiy GUI (tkinter + ttkbootstrap darkly mavzu)
# SudParser v3.0 | 850x750 px oyna

import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import time
import os
import sys
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
from utils import date_to_timestamp, ensure_dir, get_resource_path, now_str, open_path
from gui.components import ScrolledLog, ProgressBar, DateEntry, StatCard, add_tooltip
from gui.tray import TrayManager


class SudParserApp(tb.Window):
    """
    Asosiy dastur oynasi.
    Barcha tarmoq operatsiyalari alohida threadda — GUI hech qachon muzlamaydi.
    """

    APP_TITLE   = "SudParser — Sud Hujjatlari Yuklovchi"
    APP_VERSION = "v3.1"
    WINDOW_SIZE = "960x860"

    def __init__(self):
        super().__init__(themename="darkly")
        self.title(f"{self.APP_TITLE}  {self.APP_VERSION}")
        self.geometry(self.WINDOW_SIZE)
        self.resizable(True, True)
        self.minsize(820, 680)

        # Icon o'rnatish (cross-platform)
        try:
            icon_path = get_resource_path("assets/icon.ico")
            if sys.platform.startswith("win"):
                # Windows: .ico to'g'ridan-to'g'ri ishlaydi
                self.iconbitmap(icon_path)
            else:
                # Linux/macOS: Pillow orqali PhotoImage ga o'tkazamiz
                from PIL import Image, ImageTk
                self._icon_img = ImageTk.PhotoImage(Image.open(icon_path))
                self.iconphoto(True, self._icon_img)
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

        # Hujjat turlari — oldindan standart ro'yxat bilan to'ldiriladi.
        # API dan yuklangач yangilanadi (_load_doc_types). Shunday qilib
        # foydalanuvchi API javobini kutmasdan ham "Yuklash" tugmasini bosa oladi.
        self._doc_types = list(DEFAULT_DOC_TYPES)

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
        self._build_header()

        # ── Asosiy ish maydoni: ikki ustun ────────────────────────────────
        body = tb.Frame(self, padding=(12, 6))
        body.pack(fill=BOTH, expand=True)

        left  = tb.Frame(body)
        left.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 6))
        right = tb.Frame(body)
        right.pack(side=LEFT, fill=BOTH, expand=True, padx=(6, 0))

        self._build_mode_section(left)
        self._build_court_section(left)
        self._build_filter_section(left)

        self._build_path_section(right)
        self._build_settings_section(right)
        self._build_stats_section(right)

        # ── Amal tugmalari (to'liq kenglik) ───────────────────────────────
        self._build_action_buttons()

        # ── Progress + Log (to'liq kenglik) ───────────────────────────────
        self._build_progress_and_log()

        # ── Pastki holat paneli ───────────────────────────────────────────
        self._build_statusbar()

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self) -> None:
        header = tb.Frame(self, bootstyle="dark", padding=(16, 12))
        header.pack(fill=X)

        title_box = tb.Frame(header, bootstyle="dark")
        title_box.pack(side=LEFT)
        tb.Label(
            title_box, text="🏛️  SudParser",
            font=("Segoe UI", 18, "bold"), bootstyle="inverse-dark",
        ).pack(anchor="w")
        tb.Label(
            title_box,
            text="Sud hujjatlarini avtomatik yuklab oluvchi  •  public.sud.uz",
            font=("Segoe UI", 9), bootstyle="secondary",
        ).pack(anchor="w")

        # O'ng tarafda: mavzu almashtirgich
        right_box = tb.Frame(header, bootstyle="dark")
        right_box.pack(side=RIGHT)
        self._theme_var = tk.StringVar(value="darkly")
        theme_btn = tb.Button(
            right_box, text="🌗  Mavzu", command=self._toggle_theme,
            bootstyle="secondary-outline", width=10,
        )
        theme_btn.pack(side=RIGHT, padx=2)
        add_tooltip(theme_btn, "Yorug' va qorong'u mavzu o'rtasida almashtirish")

        tb.Separator(self, bootstyle="secondary").pack(fill=X)

    # ── Chap ustun: rejim, yo'nalish, filtrlar ──────────────────────────────────

    def _build_mode_section(self, parent) -> None:
        frame = tb.Labelframe(parent, text="  ⚡  Ish rejimi  ", padding=10)
        frame.pack(fill=X, pady=(0, 8))

        self._mode_var = tk.StringVar(value="once")
        rb1 = tb.Radiobutton(
            frame, text="Bir martalik yuklash",
            variable=self._mode_var, value="once", bootstyle="primary",
        )
        rb1.pack(anchor="w", pady=3)
        add_tooltip(rb1, "Tanlangan yo'nalishlardagi barcha mavjud hujjatlarni "
                         "bir marta yuklab oladi va to'xtaydi.")

        rb2 = tb.Radiobutton(
            frame, text="Monitoring (avtomatik kuzatuv)",
            variable=self._mode_var, value="monitor", bootstyle="success",
        )
        rb2.pack(anchor="w", pady=3)
        add_tooltip(rb2, "Belgilangan vaqt oralig'ida saytni kuzatib turadi va "
                         "yangi hujjat chiqishi bilan avtomatik yuklab oladi.")

    def _build_court_section(self, parent) -> None:
        frame = tb.Labelframe(parent, text="  📂  Sud yo'nalishlari  ", padding=10)
        frame.pack(fill=X, pady=8)
        tb.Label(
            frame, text="Kamida bittasini tanlang:",
            font=("Segoe UI", 9), bootstyle="secondary",
        ).pack(anchor="w", pady=(0, 4))

        self._ct_vars: dict[str, tk.BooleanVar] = {}
        for code, label in COURT_TYPES.items():
            var = tk.BooleanVar(value=(code == "ECONOMIC"))
            self._ct_vars[code] = var
            tb.Checkbutton(
                frame, text=label, variable=var,
                bootstyle="primary-round-toggle",
            ).pack(anchor="w", padx=4, pady=2)

    def _build_filter_section(self, parent) -> None:
        frame = tb.Labelframe(parent, text="  🔍  Filtrlar (ixtiyoriy)  ", padding=10)
        frame.pack(fill=X, pady=8)

        # Hujjat turi
        tb.Label(frame, text="Hujjat turi", font=("Segoe UI", 9),
                 bootstyle="secondary").pack(anchor="w")
        self._type_var = tk.StringVar()
        self._type_cb = tb.Combobox(frame, textvariable=self._type_var, state="readonly")
        self._type_cb["values"] = [d["name"] for d in DEFAULT_DOC_TYPES]
        self._type_cb.set(DEFAULT_DOC_TYPES[0]["name"])
        self._type_cb.pack(fill=X, pady=(0, 6))

        # Instansiya
        tb.Label(frame, text="Instansiya", font=("Segoe UI", 9),
                 bootstyle="secondary").pack(anchor="w")
        self._inst_var = tk.StringVar()
        self._inst_cb = tb.Combobox(frame, textvariable=self._inst_var, state="readonly")
        self._inst_cb["values"] = list(INSTANCE_TYPES.values())
        self._inst_cb.set(list(INSTANCE_TYPES.values())[0])
        self._inst_cb.pack(fill=X, pady=(0, 6))

        # Sana oralig'i
        date_row = tb.Frame(frame)
        date_row.pack(fill=X, pady=(0, 6))
        col_from = tb.Frame(date_row); col_from.pack(side=LEFT, expand=True, fill=X)
        tb.Label(col_from, text="Sana (dan)", font=("Segoe UI", 9),
                 bootstyle="secondary").pack(anchor="w")
        self._date_from = DateEntry(col_from)
        self._date_from.pack(anchor="w")
        col_to = tb.Frame(date_row); col_to.pack(side=LEFT, expand=True, fill=X)
        tb.Label(col_to, text="Sana (gacha)", font=("Segoe UI", 9),
                 bootstyle="secondary").pack(anchor="w")
        self._date_to = DateEntry(col_to)
        self._date_to.pack(anchor="w")

        # Ish raqami
        tb.Label(frame, text="Ish raqami", font=("Segoe UI", 9),
                 bootstyle="secondary").pack(anchor="w")
        self._case_var = tk.StringVar()
        case_entry = tb.Entry(frame, textvariable=self._case_var)
        case_entry.pack(fill=X)
        add_tooltip(case_entry, "Aniq ish raqami bo'yicha qidirish (masalan: 4-1901/2024).")

    # ── O'ng ustun: saqlash joyi, sozlamalar, statistika ────────────────────────

    def _build_path_section(self, parent) -> None:
        frame = tb.Labelframe(parent, text="  💾  Saqlash joyi  ", padding=10)
        frame.pack(fill=X, pady=(0, 8))
        self._path_var = tk.StringVar(value=self.config.download_path)
        row = tb.Frame(frame); row.pack(fill=X)
        entry = tb.Entry(row, textvariable=self._path_var)
        entry.pack(side=LEFT, fill=X, expand=True)
        add_tooltip(entry, "Yuklab olingan PDF fayllar shu papkaga saqlanadi.")
        tb.Button(row, text="📁", command=self._browse_path,
                  bootstyle="secondary-outline", width=4).pack(side=LEFT, padx=(6, 0))

    def _build_settings_section(self, parent) -> None:
        frame = tb.Labelframe(parent, text="  ⚙️  Sozlamalar  ", padding=10)
        frame.pack(fill=X, pady=8)

        # Bir vaqtdagi yuklamalar
        r1 = tb.Frame(frame); r1.pack(fill=X, pady=3)
        tb.Label(r1, text="Bir vaqtda yuklash (oqim)", anchor="w").pack(side=LEFT, fill=X, expand=True)
        self._workers_var = tk.IntVar(value=self.config.max_workers)
        sp1 = tb.Spinbox(r1, from_=1, to=20, textvariable=self._workers_var, width=6)
        sp1.pack(side=RIGHT)
        add_tooltip(sp1, "Bir vaqtning o'zida nechta fayl yuklansin. Ko'p bo'lsa tezroq, "
                         "lekin saytga yuk ko'proq tushadi (tavsiya: 5).")

        # So'rovlar oralig'i
        r2 = tb.Frame(frame); r2.pack(fill=X, pady=3)
        tb.Label(r2, text="So'rovlar oralig'i (soniya)", anchor="w").pack(side=LEFT, fill=X, expand=True)
        self._delay_var = tk.DoubleVar(value=self.config.request_delay)
        sp2 = tb.Spinbox(r2, from_=0, to=10, increment=0.1,
                         textvariable=self._delay_var, format="%.1f", width=6)
        sp2.pack(side=RIGHT)
        add_tooltip(sp2, "Har so'rov orasidagi tanaffus. 429 (Too Many Requests) "
                         "xatosi chiqsa, qiymatni oshiring.")

        # Monitoring oralig'i
        r3 = tb.Frame(frame); r3.pack(fill=X, pady=3)
        tb.Label(r3, text="Monitoring oralig'i (daqiqa)", anchor="w").pack(side=LEFT, fill=X, expand=True)
        self._interval_var = tk.IntVar(value=self.config.monitor_interval_minutes)
        sp3 = tb.Spinbox(r3, from_=1, to=1440, textvariable=self._interval_var, width=6)
        sp3.pack(side=RIGHT)
        add_tooltip(sp3, "Monitoring rejimida saytni qancha vaqtda bir tekshirish.")

        # Mavjud fayllarni o'tkazib yuborish
        self._skip_var2 = tk.BooleanVar(value=self.config.skip_existing)
        chk = tb.Checkbutton(frame, text="Mavjud fayllarni o'tkazib yubor",
                             variable=self._skip_var2, bootstyle="primary-round-toggle")
        chk.pack(anchor="w", pady=(6, 0))
        add_tooltip(chk, "Allaqachon yuklab olingan fayllar qayta yuklanmaydi.")

    def _build_stats_section(self, parent) -> None:
        frame = tb.Labelframe(parent, text="  📊  Statistika  ", padding=10)
        frame.pack(fill=BOTH, expand=True, pady=8)
        row = tb.Frame(frame); row.pack(fill=X)

        self._card_success = StatCard(row, "Yuklandi", "0", bootstyle="success")
        self._card_success.pack(side=LEFT, fill=X, expand=True)
        self._card_failed = StatCard(row, "Xato", "0", bootstyle="danger")
        self._card_failed.pack(side=LEFT, fill=X, expand=True)
        self._card_total = StatCard(row, "Bazada jami", str(self.state.total_count()),
                                    bootstyle="info")
        self._card_total.pack(side=LEFT, fill=X, expand=True)

    # ── Amal tugmalari ──────────────────────────────────────────────────────────

    def _build_action_buttons(self) -> None:
        btn_frame = tb.Frame(self, padding=(12, 4))
        btn_frame.pack(fill=X)

        self._btn_start = tb.Button(
            btn_frame, text="▶   Yuklab olishni boshlash",
            command=self._start_download, bootstyle="primary",
        )
        self._btn_start.pack(side=LEFT, fill=X, expand=True, padx=(0, 4), ipady=4)
        add_tooltip(self._btn_start, "Tanlangan yo'nalishlardagi hujjatlarni bir marta yuklaydi.")

        self._btn_monitor = tb.Button(
            btn_frame, text="📡   Monitoringni yoqish",
            command=self._start_monitor, bootstyle="success",
        )
        self._btn_monitor.pack(side=LEFT, fill=X, expand=True, padx=4, ipady=4)
        add_tooltip(self._btn_monitor, "Yangi hujjatlarni avtomatik kuzatishni boshlaydi.")

        self._btn_stop = tb.Button(
            btn_frame, text="⏹   To'xtatish",
            command=self._stop_all, bootstyle="danger", state="disabled",
        )
        self._btn_stop.pack(side=LEFT, fill=X, expand=True, padx=(4, 0), ipady=4)
        add_tooltip(self._btn_stop, "Joriy yuklash yoki monitoringni to'xtatadi.")

    # ── Progress + Log ────────────────────────────────────────────────────────

    def _build_progress_and_log(self) -> None:
        prog_frame = tb.Frame(self, padding=(12, 4))
        prog_frame.pack(fill=X)
        self._progressbar = ProgressBar(prog_frame)
        self._progressbar.pack(fill=X)

        log_frame = tb.Labelframe(self, text="  📋  Jarayon jurnali  ", padding=8)
        log_frame.pack(fill=BOTH, expand=True, padx=12, pady=(4, 8))

        btn_log_row = tb.Frame(log_frame)
        btn_log_row.pack(fill=X, pady=(0, 4))
        b1 = tb.Button(btn_log_row, text="📂  Papkani ochish",
                       command=self._open_folder, bootstyle="info-outline")
        b1.pack(side=LEFT, padx=(0, 4))
        add_tooltip(b1, "Yuklab olingan fayllar papkasini fayl menejerida ochadi.")
        b2 = tb.Button(btn_log_row, text="📊  CSV hisobot",
                       command=self._open_csv_log, bootstyle="warning-outline")
        b2.pack(side=LEFT, padx=4)
        add_tooltip(b2, "Eng so'nggi yuklash hisobotini (CSV) ochadi.")
        b3 = tb.Button(btn_log_row, text="🗑  Tozalash",
                       command=lambda: self._log.clear(), bootstyle="secondary-outline")
        b3.pack(side=RIGHT)
        add_tooltip(b3, "Jurnal oynasini tozalaydi (fayllarga ta'sir qilmaydi).")

        self._log = ScrolledLog(log_frame, height=10)
        self._log.pack(fill=BOTH, expand=True)

    # ── Pastki holat paneli ─────────────────────────────────────────────────────

    def _build_statusbar(self) -> None:
        tb.Separator(self, bootstyle="secondary").pack(fill=X)
        bar = tb.Frame(self, padding=(12, 5))
        bar.pack(fill=X)
        self._status_var = tk.StringVar(value="✅ Tayyor — yo'nalish tanlab, boshlang")
        tb.Label(bar, textvariable=self._status_var, bootstyle="secondary",
                 anchor="w").pack(side=LEFT, fill=X, expand=True)
        tb.Label(bar, text=f"{self.APP_TITLE.split('—')[0].strip()} {self.APP_VERSION}",
                 bootstyle="secondary", anchor="e").pack(side=RIGHT)

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

        def _apply():
            self._progressbar.update(s, f, sk, t)
            self._card_success.set(s)
            self._card_failed.set(f)
            self._card_total.set(self.state.total_count())
        self.after(0, _apply)

    def _toggle_theme(self) -> None:
        """Yorug' va qorong'u mavzu o'rtasida almashtirish"""
        new_theme = "flatly" if self._theme_var.get() == "darkly" else "darkly"
        self._theme_var.set(new_theme)
        try:
            self.style.theme_use(new_theme)
        except Exception:
            pass

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
        from config import default_download_path
        self.config.download_path = self._path_var.get() or default_download_path()
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
        open_path(str(path))

    def _open_csv_log(self) -> None:
        import glob
        files = sorted(glob.glob("logs/download_log_*.csv"), reverse=True)
        if files:
            open_path(files[0])
        else:
            messagebox.showinfo("Ma'lumot", "CSV log fayli topilmadi.")

    def _set_buttons(self, running: bool) -> None:
        self._btn_start["state"]   = "disabled" if running else "normal"
        self._btn_monitor["state"] = "disabled" if running else "normal"
        self._btn_stop["state"]    = "normal" if running else "disabled"

    def _reset_stats(self) -> None:
        self._stat_success = self._stat_failed = self._stat_skipped = self._stat_total = 0
        self._progressbar.reset()
        try:
            self._card_success.set(0)
            self._card_failed.set(0)
            self._card_total.set(self.state.total_count())
        except Exception:
            pass

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