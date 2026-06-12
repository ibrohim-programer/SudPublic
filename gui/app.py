# gui/app.py — SUDPUBLIK asosiy oyna (Dashboard ko'rinishi)
# public.sud.uz uslubidagi karta-dizayn

import tkinter as tk
from tkinter import messagebox
import threading
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

import ttkbootstrap as tb
from ttkbootstrap.constants import *

from api import SudApiClient
from config import Config, default_download_path
from state_tracker import StateTracker
from logger import CsvLogger, SessionSummary
from downloader import Downloader
from utils import get_resource_path, open_path, ensure_dir
from gui.components import DateEntry
from api import INSTANCE_TYPES, DEFAULT_DOC_TYPES
from api.endpoints import result_label


# ─── Sud turlari tuzilmasi ──────────────────────────────────────────────────
# Har kategoriya bir yoki ikki "sub" (yil/tur) dan iborat.
# Iqtisodiy → 2024 gacha (ECONOMIC_OLD) va 2024 dan keyin (ECONOMIC).
CATEGORIES = [
    {
        "name": "IQTISODIY SUDLAR",
        "icon": "🏦",
        "subs": [
            {"court_type": "ECONOMIC_OLD", "title": "2024 yildan avval ko'rilgan ishlar"},
            {"court_type": "ECONOMIC",     "title": "2024 yildan keyingi ko'rilgan ishlar"},
        ],
    },
    {
        "name": "MA'MURIY SUDLAR",
        "icon": "📋",
        "subs": [
            {"court_type": "ADMINISTRATIVE", "title": "Barcha ishlar"},
        ],
    },
    {
        "name": "FUQAROLIK ISHLARI BO'YICHA SUDLAR",
        "icon": "👥",
        "subs": [
            {"court_type": "CIVIL", "title": "Barcha ishlar"},
        ],
    },
    {
        "name": "JINOYAT ISHLARI BO'YICHA SUDLAR",
        "icon": "⚖️",
        "subs": [
            {"court_type": "CRIMINAL", "title": "Barcha ishlar"},
        ],
    },
    {
        "name": "MA'MURIY HUQUQBUZARLIK BO'YICHA ISHLAR",
        "icon": "📑",
        "subs": [
            {"court_type": "ADMINISTRATIVE_OFFENCE", "title": "Barcha ishlar"},
        ],
    },
]

# Instansiya turlari (label + API instanceType kodi)
INSTANCES = [
    ("Birinchi instansiya",      "FIRST"),
    ("Apellyatsiya instansiyasi", "APPEAL"),
    ("Kassatsiya instansiyasi",  "CASSATION"),
    ("Taftish",                  "REVISION"),
]


def _fmt(n) -> str:
    """Sonni 814 591 ko'rinishida formatlash"""
    try:
        return f"{int(n):,}".replace(",", " ")
    except (ValueError, TypeError):
        return "—"


class SudParserApp(tb.Window):
    """SUDPUBLIK — Dashboard uslubidagi asosiy oyna."""

    APP_TITLE   = "SUDPUBLIK"
    APP_VERSION = "v4.0"
    WINDOW_SIZE = "1040x680"

    def __init__(self):
        super().__init__(themename="sandstone")
        self.title(f"{self.APP_TITLE}  {self.APP_VERSION}")
        self.geometry(self.WINDOW_SIZE)
        self.minsize(940, 600)

        # ─── Backend ob'ektlar ────────────────────────────────────────────
        self.config  = Config.load()
        self.api     = SudApiClient(self.config)
        self.state   = StateTracker(Path(self.config.state_db_path))
        self.csv_log = CsvLogger()
        self.summary = SessionSummary()

        self._stop_event = threading.Event()
        self._work_thread: Optional[threading.Thread] = None
        self._running = False

        # Statistika (yuklash uchun)
        self._stat_success = 0
        self._stat_failed  = 0

        # Sonlar keshi: court_type → {"total": n, "FIRST": n, ...}
        self._counts: dict[str, dict] = {}
        self._count_vars: dict[str, tk.StringVar] = {}   # "<ct>:<inst>" → StringVar
        self._total_vars: dict[str, tk.StringVar] = {}   # "<ct>" → StringVar

        # Hujjat turlari (filtr uchun)
        self._doc_types = list(DEFAULT_DOC_TYPES)
        self._categories = [{"id": 0, "name": "Barchasi"}]   # Ish turkumi (API dan yuklanadi)
        self._search_token = None   # progressive qidiruvni bekor qilish uchun

        self._build_layout()
        self.show_dashboard()

        # Sonlarni fonda yuklash
        threading.Thread(target=self._fetch_all_counts, daemon=True).start()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ─────────────────────────────────────────────────────────────────────────
    # UMUMIY TUZILMA: chap panel + o'ng kontent
    # ─────────────────────────────────────────────────────────────────────────

    def _build_layout(self) -> None:
        # ── Chap panel (sarlavha + emblema) ───────────────────────────────
        sidebar = tb.Frame(self, bootstyle="secondary", width=240)
        sidebar.pack(side=LEFT, fill=Y)
        sidebar.pack_propagate(False)

        tb.Label(
            sidebar,
            text="Internet tarmog'ida\ne'lon qilingan\nsud qarorlari",
            font=("Segoe UI", 12, "bold"),
            bootstyle="inverse-secondary",
            justify="left",
        ).pack(anchor="w", padx=16, pady=(20, 10))

        tb.Label(
            sidebar, text=f"{self.APP_TITLE} {self.APP_VERSION}",
            font=("Segoe UI", 8), bootstyle="inverse-secondary",
        ).pack(side=BOTTOM, anchor="w", padx=16, pady=10)

        # ── O'ng konteyner (kontent + holat paneli) ───────────────────────
        right = tb.Frame(self)
        right.pack(side=LEFT, fill=BOTH, expand=True)

        # Pastki holat paneli (faqat kontent ostida)
        self._status_var = tk.StringVar(value="Tayyor")
        self._status_lbl = tb.Label(right, textvariable=self._status_var,
                                     bootstyle="secondary", anchor="center",
                                     font=("Segoe UI", 10))
        self._status_lbl.pack(side=BOTTOM, fill=X, pady=6)

        # O'ng kontent
        self._content = tb.Frame(right, padding=18)
        self._content.pack(side=TOP, fill=BOTH, expand=True)

    def _clear_content(self) -> None:
        # Ketayotgan qidiruvni bekor qilamiz (jadval yo'qolганda xato bo'lmasin)
        self._search_token = None
        for w in self._content.winfo_children():
            w.destroy()

    # ─────────────────────────────────────────────────────────────────────────
    # DASHBOARD KO'RINISHI (kategoriyalar)
    # ─────────────────────────────────────────────────────────────────────────

    def show_dashboard(self) -> None:
        self._clear_content()
        self._count_updaters = []   # sonlarni yangilovchi funksiyalar

        header = tb.Frame(self._content)
        header.pack(fill=X, pady=(0, 12))
        tb.Label(header, text="Sud qarorlari — yo'nalishlar",
                 font=("Segoe UI", 15, "bold")).pack(side=LEFT)

        for idx, cat in enumerate(CATEGORIES):
            self._make_category_card(self._content, idx, cat)

        self._set_status("Tayyor — yo'nalishni tanlang")
        self._refresh_counts_ui()

    def _make_category_card(self, parent, idx: int, cat: dict) -> None:
        subs_cts = [s["court_type"] for s in cat["subs"]]

        outer = tk.Frame(parent, bg="#cfc4b0", padx=1, pady=1)
        outer.pack(fill=X, pady=5)
        card = tb.Frame(outer, padding=12, bootstyle="light")
        card.pack(fill=X)

        # Ikonka
        tb.Label(card, text=cat["icon"], font=("Segoe UI", 26),
                 bootstyle="inverse-light").grid(row=0, column=0, rowspan=2, padx=(4, 14))

        # Nomi
        tb.Label(card, text=cat["name"], font=("Segoe UI", 12, "bold"),
                 wraplength=200, justify="left", bootstyle="inverse-light").grid(
                     row=0, column=1, rowspan=2, sticky="w", padx=(0, 18))

        # Instansiya jadvali
        inst_box = tb.Frame(card, bootstyle="light")
        inst_box.grid(row=0, column=2, rowspan=2, sticky="w", padx=(0, 18))
        for r, (label, code) in enumerate(INSTANCES):
            tb.Label(inst_box, text=label, font=("Segoe UI", 9),
                     bootstyle="inverse-light").grid(row=r, column=0, sticky="w", padx=(0, 16))
            var = tk.StringVar(value="…")
            tb.Label(inst_box, textvariable=var, font=("Segoe UI", 9, "bold"),
                     bootstyle="inverse-light").grid(row=r, column=1, sticky="e")
            self._count_updaters.append(
                lambda v=var, cts=subs_cts, c=code: v.set(_fmt(self._sum_counts(cts, c)))
            )

        card.columnconfigure(3, weight=1)

        # Umumiy son (katta quti)
        total_var = tk.StringVar(value="…")
        total_box = tk.Frame(card, bg="white", highlightbackground="#b9ad95",
                             highlightthickness=1)
        total_box.grid(row=0, column=4, rowspan=2, padx=10)
        tb.Label(total_box, textvariable=total_var, font=("Segoe UI", 15, "bold"),
                 background="white", width=10, anchor="center").pack(padx=10, pady=10)
        self._count_updaters.append(
            lambda v=total_var, cts=subs_cts: v.set(_fmt(self._sum_counts(cts, "total")))
        )

        # Kirish tugmasi →
        tb.Button(card, text="→", width=3, bootstyle="warning-outline",
                  command=lambda c=cat: self.show_detail(c)).grid(
                      row=0, column=5, rowspan=2, padx=(6, 4))

    # ─────────────────────────────────────────────────────────────────────────
    # DETAL KO'RINISHI (yillar / yuklash)
    # ─────────────────────────────────────────────────────────────────────────

    def show_detail(self, cat: dict) -> None:
        self._clear_content()
        self._count_updaters = []
        self._current_cat = cat

        header = tb.Frame(self._content)
        header.pack(fill=X, pady=(0, 12))
        tb.Button(header, text="←  Orqaga", bootstyle="secondary",
                  command=self.show_dashboard).pack(side=LEFT)
        tb.Label(header, text="   " + cat["name"], font=("Segoe UI", 14, "bold")).pack(side=LEFT)

        for sub in cat["subs"]:
            self._make_detail_card(self._content, sub)

        self._refresh_counts_ui()

    def _make_detail_card(self, parent, sub: dict) -> None:
        ct = sub["court_type"]

        outer = tk.Frame(parent, bg="#cfc4b0", padx=1, pady=1)
        outer.pack(fill=X, pady=6)
        card = tb.Frame(outer, padding=14, bootstyle="light")
        card.pack(fill=X)

        tb.Label(card, text="📄", font=("Segoe UI", 24),
                 bootstyle="inverse-light").grid(row=0, column=0, rowspan=2, padx=(4, 14))
        tb.Label(card, text=sub["title"], font=("Segoe UI", 13, "bold"),
                 wraplength=220, justify="left", bootstyle="inverse-light").grid(
                     row=0, column=1, rowspan=2, sticky="w", padx=(0, 18))

        inst_box = tb.Frame(card, bootstyle="light")
        inst_box.grid(row=0, column=2, rowspan=2, sticky="w", padx=(0, 18))
        for r, (label, code) in enumerate(INSTANCES):
            tb.Label(inst_box, text=label, font=("Segoe UI", 9),
                     bootstyle="inverse-light").grid(row=r, column=0, sticky="w", padx=(0, 16))
            var = tk.StringVar(value="…")
            tb.Label(inst_box, textvariable=var, font=("Segoe UI", 9, "bold"),
                     bootstyle="inverse-light").grid(row=r, column=1, sticky="e")
            self._count_updaters.append(
                lambda v=var, c=code, t=ct: v.set(_fmt(self._sum_counts([t], c)))
            )

        card.columnconfigure(3, weight=1)

        total_var = tk.StringVar(value="…")
        total_box = tk.Frame(card, bg="white", highlightbackground="#b9ad95",
                             highlightthickness=1)
        total_box.grid(row=0, column=4, rowspan=2, padx=10)
        tb.Label(total_box, textvariable=total_var, font=("Segoe UI", 14, "bold"),
                 background="white", width=10, anchor="center").pack(padx=10, pady=8)
        self._count_updaters.append(
            lambda v=total_var, t=ct: v.set(_fmt(self._sum_counts([t], "total")))
        )

        # Kirish tugmasi → (qidiruv/jadval ko'rinishini ochadi)
        btns = tb.Frame(card, bootstyle="light")
        btns.grid(row=0, column=5, rowspan=2, padx=(6, 4))
        tb.Button(btns, text="→", width=3, bootstyle="warning",
                  command=lambda s=sub: self.show_search(s)).pack(pady=2)

        prog_var = tk.StringVar(value="")
        prog_lbl = tb.Label(card, textvariable=prog_var, font=("Segoe UI", 10, "bold"),
                            bootstyle="inverse-light", anchor="w")
        prog_lbl.grid(row=2, column=0, columnspan=6, sticky="we", pady=(8, 0))

        sub["_prog_var"] = prog_var

    # ─────────────────────────────────────────────────────────────────────────
    # QIDIRUV / JADVAL KO'RINISHI
    # ─────────────────────────────────────────────────────────────────────────

    TABLE_COLS = [
        ("no",       "№",                  46),
        ("court",    "Sud nomi",           200),
        ("instance", "Sud instansiyasi",   120),
        ("case",     "Ish raqami",         120),
        ("reason",   "Natija sababi",      200),
        ("judge",    "Ishni ko'rgan sudya", 170),
        ("date",     "Ish ko'rilgan sana", 110),
        ("result",   "Ish natijasi",       150),
        ("doctype",  "Sud hujjati turi",   150),
    ]

    # Sud darajalari ("Суд тури"): nom → courtType raqami
    COURT_LEVELS = [
        ("Sud turi (barchasi)", None),
        ("Oliy sud", 1),
        ("Viloyat sudi", 2),
        ("Tumanlararo / tuman sudi", 3),
    ]

    def show_search(self, sub: dict) -> None:
        self._clear_content()
        self._count_updaters = []
        self._search_sub = sub
        self._search_rows = []   # joriy natijalar (raw dict lar)
        self._courts = [{"id": None, "name": "Sud (barchasi)"}]
        self._ph_list = []

        # Sarlavha + orqaga
        top = tb.Frame(self._content)
        top.pack(fill=X)
        tb.Button(top, text="←  Orqaga", bootstyle="secondary",
                  command=lambda: self.show_detail(self._current_cat)).pack(side=LEFT)
        tb.Label(top, text="   " + sub["title"], font=("Segoe UI", 13, "bold")).pack(side=LEFT)

        # ── Filtrlar paneli (2×4 grid, doimiy ko'rinadi) ──────────────────
        flt = tb.Labelframe(self._content, text="  🔎  Filtrlar  ", padding=10)
        flt.pack(fill=X, pady=(10, 6))
        for c in range(4):
            flt.columnconfigure(c, weight=1, uniform="f")

        def cell(r, c):
            f = tb.Frame(flt)
            f.grid(row=r, column=c, sticky="ew", padx=5, pady=4)
            return f

        # — Qator 0 —
        # Суд тури (sud darajasi)
        c0 = cell(0, 0)
        self._f_courttype = tk.StringVar(value=self.COURT_LEVELS[0][0])
        ct_cb = tb.Combobox(c0, textvariable=self._f_courttype, state="readonly",
                            values=[x[0] for x in self.COURT_LEVELS])
        ct_cb.pack(fill=X)
        ct_cb.bind("<<ComboboxSelected>>", lambda e: self._on_court_level_change())
        # Суд (aniq sud)
        c1 = cell(0, 1)
        self._f_court = tk.StringVar(value=self._courts[0]["name"])
        self._court_cb = tb.Combobox(c1, textvariable=self._f_court, state="readonly",
                                     values=[x["name"] for x in self._courts])
        self._court_cb.pack(fill=X)
        # Ишни кўрган судья
        c2 = cell(0, 2)
        self._f_judge = tk.StringVar()
        self._ph_entry(c2, self._f_judge, "Ishni ko'rgan sudya")
        # Иш туркуми
        c3 = cell(0, 3)
        self._f_cat = tk.StringVar(value=self._categories[0]["name"])
        self._cat_cb = tb.Combobox(c3, textvariable=self._f_cat, state="readonly",
                                   values=[c["name"] for c in self._categories])
        self._cat_cb.pack(fill=X)

        # — Qator 1 —
        # Иш рақами
        c4 = cell(1, 0)
        self._f_case = tk.StringVar()
        self._ph_entry(c4, self._f_case, "Ish raqami")
        # Sana (dan — gacha)
        c5 = cell(1, 1)
        drow = tb.Frame(c5); drow.pack(fill=X)
        self._f_date_from = DateEntry(drow); self._f_date_from.pack(side=LEFT)
        tb.Label(drow, text="—").pack(side=LEFT, padx=3)
        self._f_date_to = DateEntry(drow); self._f_date_to.pack(side=LEFT)
        # Суд инстанцияси
        c6 = cell(1, 2)
        self._f_inst = tk.StringVar(value=list(INSTANCE_TYPES.values())[0])
        inst_cb = tb.Combobox(c6, textvariable=self._f_inst, state="readonly",
                             values=list(INSTANCE_TYPES.values()))
        inst_cb.pack(fill=X)
        # Суд хужжати тури
        c7 = cell(1, 3)
        self._f_type = tk.StringVar(value=self._doc_types[0]["name"])
        type_cb = tb.Combobox(c7, textvariable=self._f_type, state="readonly",
                             values=[d["name"] for d in self._doc_types])
        type_cb.pack(fill=X)

        # — Tugmalar qatori —
        btnrow = tb.Frame(flt)
        btnrow.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        tb.Button(btnrow, text="Tozalash", bootstyle="secondary",
                  command=self._clear_search_filters).pack(side=LEFT)
        tb.Button(btnrow, text="🔍  Qidirish", bootstyle="success",
                  command=self._do_search).pack(side=RIGHT)
        self._btn_dl_all = tb.Button(btnrow, text="⬇  Barchasini yuklash", bootstyle="primary",
                                     command=self._download_all_search)
        self._btn_dl_all.pack(side=RIGHT, padx=6)
        self._btn_more = tb.Button(btnrow, text="⬇ Ko'proq yuklash", bootstyle="info-outline",
                                   command=self._fetch_search_page, state="disabled")
        self._btn_more.pack(side=RIGHT, padx=6)
        self._search_info = tk.StringVar(value="")
        tb.Label(btnrow, textvariable=self._search_info, bootstyle="info").pack(side=RIGHT, padx=12)

        # ── Natijalar jadvali ─────────────────────────────────────────────
        self._res_lf = res_lf = tb.Labelframe(self._content, text="  📁  Natijalar  ", padding=4)
        res_lf.pack(fill=BOTH, expand=True, pady=(4, 4))
        table_frame = tb.Frame(res_lf)
        table_frame.pack(fill=BOTH, expand=True)

        cols = [c[0] for c in self.TABLE_COLS] + ["pdf"]
        self._tree = tb.Treeview(table_frame, columns=cols, show="headings",
                                 bootstyle="primary", height=9)
        for key, label, width in self.TABLE_COLS:
            self._tree.heading(key, text=label)
            self._tree.column(key, width=width, anchor="w")
        self._tree.heading("pdf", text="Hujjat")
        self._tree.column("pdf", width=80, anchor="center")

        vsb = tb.Scrollbar(table_frame, orient=VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side=LEFT, fill=BOTH, expand=True)
        vsb.pack(side=RIGHT, fill=Y)
        self._tree.bind("<Double-1>", self._download_selected_row)

        # ── Yuklanayotgan fayllar (jonli) ─────────────────────────────────
        dl_lf = tb.Labelframe(self._content, text="  ⬇  Yuklanayotgan fayllar  ", padding=4)
        dl_lf.pack(fill=X, pady=(4, 0))
        dframe = tb.Frame(dl_lf)
        dframe.pack(fill=X)
        self._dl_tree = tb.Treeview(dframe, columns=("no", "file", "size", "status"),
                                    show="headings", bootstyle="success", height=6)
        for key, label, w in [("no", "№", 46), ("file", "Fayl nomi", 460),
                              ("size", "Hajm (KB)", 100), ("status", "Holat", 120)]:
            self._dl_tree.heading(key, text=label)
            self._dl_tree.column(key, width=w, anchor="w")
        dvsb = tb.Scrollbar(dframe, orient=VERTICAL, command=self._dl_tree.yview)
        self._dl_tree.configure(yscrollcommand=dvsb.set)
        self._dl_tree.pack(side=LEFT, fill=X, expand=True)
        dvsb.pack(side=RIGHT, fill=Y)
        self._dl_count = 0

        # Standart holatda — barcha fayllarni avtomatik yuklab ko'rsatamiz
        self._set_status("⏳ Ro'yxat yuklanmoqda...")
        self.after(150, self._do_search)

    def _toggle_advanced(self) -> None:
        """Kengaytirilgan filtrlar panelini ko'rsatish/yashirish."""
        self._adv_visible = not self._adv_visible
        if self._adv_visible:
            self._adv_frame.pack(fill=X, pady=(0, 8), before=self._res_lf)
            self._btn_adv.configure(text="⚙  Filtrlarni yashirish")
        else:
            self._adv_frame.pack_forget()
            self._btn_adv.configure(text="⚙  Kengaytirilgan qidirish")

    def _ph_entry(self, parent, var, placeholder):
        """Placeholder matnli Entry (bo'sh bo'lsa kulrang matn ko'rsatadi)."""
        if not hasattr(self, "_ph_list"):
            self._ph_list = []
        self._ph_list.append((var, placeholder))
        e = tb.Entry(parent, textvariable=var, foreground="grey")
        e.pack(fill=X)
        var.set(placeholder)

        def on_in(_):
            if var.get() == placeholder:
                var.set("")
                e.configure(foreground="black")

        def on_out(_):
            if not var.get().strip():
                var.set(placeholder)
                e.configure(foreground="grey")
        e.bind("<FocusIn>", on_in)
        e.bind("<FocusOut>", on_out)
        return e

    def _val(self, var) -> str:
        """Entry qiymati (placeholder bo'lsa bo'sh qaytaradi)."""
        v = var.get().strip()
        for vr, ph in getattr(self, "_ph_list", []):
            if vr is var and v == ph:
                return ""
        return v

    def _on_court_level_change(self) -> None:
        """Sud darajasi tanlanganda — o'sha darajadagi sudlar ro'yxatini yuklash."""
        level = None
        for name, num in self.COURT_LEVELS:
            if name == self._f_courttype.get():
                level = num
                break
        if not level:
            self._courts = [{"id": None, "name": "Sud (barchasi)"}]
            self._court_cb["values"] = [c["name"] for c in self._courts]
            self._f_court.set(self._courts[0]["name"])
            return

        def work():
            courts = self.api.get_courts(level)
            self._courts = [{"id": None, "name": "Sud (barchasi)"}] + [
                {"id": c.get("id"), "name": c.get("name", "")} for c in courts
            ]
            def apply():
                self._court_cb["values"] = [c["name"] for c in self._courts]
                self._f_court.set(self._courts[0]["name"])
            try:
                self.after(0, apply)
            except Exception:
                pass
        threading.Thread(target=work, daemon=True).start()

    def _clear_search_filters(self) -> None:
        self._f_type.set(self._doc_types[0]["name"])
        self._f_inst.set(list(INSTANCE_TYPES.values())[0])
        self._f_cat.set(self._categories[0]["name"])
        self._f_courttype.set(self.COURT_LEVELS[0][0])
        self._courts = [{"id": None, "name": "Sud (barchasi)"}]
        self._court_cb["values"] = [c["name"] for c in self._courts]
        self._f_court.set(self._courts[0]["name"])
        # placeholder entry larni tiklash
        for var, ph in getattr(self, "_ph_list", []):
            var.set(ph)
        self._f_date_from.clear()
        self._f_date_to.clear()

    def _search_filter_kwargs(self) -> dict:
        kw = {}
        mf = self._f_date_from.get_ms(); mt = self._f_date_to.get_ms()
        if mf: kw["start_date_ms"] = mf
        if mt: kw["end_date_ms"] = mt
        sel = self._f_type.get()
        for d in self._doc_types:
            if d["name"] == sel and d["id"]:
                kw["type_id"] = d["id"]; break
        seli = self._f_inst.get()
        for code, label in INSTANCE_TYPES.items():
            if label == seli and code:
                kw["instance_type"] = code; break
        # Ish turkumi (kategoriya)
        selc = self._f_cat.get()
        for c in self._categories:
            if c["name"] == selc and c["id"]:
                kw["category"] = c["id"]; break
        # Sud darajasi (Суд тури) — faqat sudlar ro'yxatini chiqarish uchun
        # Aniq sud (Суд) → dbName orqali filtr
        selct = self._f_court.get()
        for c in getattr(self, "_courts", []):
            if c["name"] == selct and c.get("id"):
                kw["court_name"] = c["name"]; break
        # Sudya
        jg = self._val(self._f_judge)
        if jg:
            kw["judge"] = jg
        case = self._val(self._f_case)
        if case:
            kw["case_number"] = case
        return kw

    def _do_search(self) -> None:
        ct = self._search_sub["court_type"]
        self._search_kw = self._search_filter_kwargs()
        self._search_page = 0
        self._search_shown = 0
        self._search_total = None
        self._set_status("⏳ Qidirilmoqda...")
        for i in self._tree.get_children():
            self._tree.delete(i)
        self._search_rows = []
        self._fetch_search_page(reset=True)

    def _fetch_search_page(self, reset: bool = False) -> None:
        """Bitta sahifani (100 ta) yuklab, jadvalga qo'shadi."""
        if getattr(self, "_search_loading", False):
            return
        self._search_loading = True
        ct = self._search_sub["court_type"]
        page = self._search_page
        if hasattr(self, "_btn_more"):
            self._btn_more.configure(state="disabled")

        def work():
            try:
                d = self.api.fetch_raw_page(ct, page=page, size=100, **self._search_kw)
            except Exception as e:
                self._search_loading = False
                self._set_status(f"❌ Qidirish xatosi: {e}")
                return
            rows = d.get("content", []) or []
            total = d.get("totalElements", 0)
            last = d.get("last") or page >= (d.get("totalPages", 1) - 1)
            self.after(0, lambda: self._on_page_loaded(rows, total, last))

        threading.Thread(target=work, daemon=True).start()

    def _on_page_loaded(self, rows: list, total, last: bool) -> None:
        self._search_total = total
        start = self._search_shown
        self._search_rows.extend(rows)
        for off, item in enumerate(rows):
            idx = start + off + 1
            vals = self._row_values(idx, item) + ["📄 PDF"]
            self._tree.insert("", "end", iid=str(idx - 1), values=vals)
        self._search_shown += len(rows)
        self._search_page += 1
        self._search_loading = False
        self._search_info.set(f"Jami: {_fmt(total)} ta  (ko'rsatildi: {self._search_shown})")
        # "Ko'proq" tugmasi holati
        has_more = (not last) and len(rows) > 0
        if hasattr(self, "_btn_more"):
            self._btn_more.configure(state=("normal" if has_more else "disabled"))
        if self._search_shown == 0:
            self._set_status("Hech narsa topilmadi (filtrlarni tekshiring)")
        elif has_more:
            self._set_status(f"✅ {self._search_shown} ta ko'rsatildi (jami {_fmt(total)}) — "
                             f"davomi uchun 'Ko'proq yuklash'")
        else:
            self._set_status(f"✅ Hammasi ko'rsatildi: {self._search_shown} ta")

    def _populate_tree(self, rows: list, total) -> None:
        for i in self._tree.get_children():
            self._tree.delete(i)
        for idx, item in enumerate(rows, 1):
            vals = self._row_values(idx, item) + ["📄 PDF"]
            self._tree.insert("", "end", iid=str(idx - 1), values=vals)
        self._search_info.set(f"Jami: {_fmt(total)} ta  (ko'rsatildi: {len(rows)})")
        self._set_status(f"✅ {len(rows)} ta natija ko'rsatildi (jami {_fmt(total)})")

    def _row_values(self, idx: int, item: dict) -> list:
        # Sud nomi — fayl ichidagi db.orgName dan
        court = ""
        try:
            atts = item.get("attachmentsList") or []
            if atts:
                db = (atts[0].get("fileData") or {}).get("db") or {}
                court = db.get("orgName", "")
        except Exception:
            pass
        pt = item.get("publicationType") or {}
        date = item.get("hearingDate") or ""
        if isinstance(date, (int, float)):
            try:
                date = datetime.fromtimestamp(date / 1000).strftime("%d-%m-%Y")
            except Exception:
                date = str(date)
        return [
            idx,
            court,
            str(item.get("instance") or ""),
            str(item.get("caseNumber") or ""),
            str(item.get("category") or ""),
            str(item.get("judge") or ""),
            str(date),
            result_label(item.get("result")),
            str(pt.get("name") or ""),
        ]

    def _download_selected_row(self, _event=None) -> None:
        sel = self._tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx >= len(self._search_rows):
            return
        item = self._search_rows[idx]
        atts = item.get("attachmentsList") or []
        if not atts:
            messagebox.showinfo("Ma'lumot", "Bu yozuvda fayl yo'q.")
            return
        fd = atts[0].get("fileData") or {}
        file_id = fd.get("id")
        name = f"{item.get('id')}_{fd.get('name', 'hujjat.pdf')}"
        if not file_id:
            return
        self._set_status(f"⏳ Yuklanmoqda: {name}")

        def work():
            try:
                data = self.api.download_file_bytes(file_id)
                from api import COURT_FOLDERS
                folder = COURT_FOLDERS.get(self._search_sub["court_type"], self._search_sub["court_type"])
                dest = ensure_dir(Path(self.config.download_path) / folder) / name
                dest.write_bytes(data)
                self._set_status(f"✅ Yuklandi: {name}")
            except Exception as e:
                self._set_status(f"❌ Xato: {e}")

        threading.Thread(target=work, daemon=True).start()

    def _download_all_search(self) -> None:
        """Topilgan barcha fayllarni (filtr bo'yicha) yuklash."""
        if self._is_busy():
            messagebox.showinfo("Ma'lumot", "Avvalgi yuklash tugashini kuting.")
            return
        ct = self._search_sub["court_type"]
        kw = self._search_filter_kwargs()
        self._apply_settings()
        self._stop_event.clear()
        self._running = True
        self._stat_success = 0
        self._stat_failed = 0
        self._active_prog_var = None

        # Tugmani "Yuklanmoqda..." holatiga o'tkazamiz
        self._btn_dl_all.configure(text="⏳  Yuklanmoqda...", state="disabled", bootstyle="warning")
        # Jonli jadvalni tozalaymiz
        for i in self._dl_tree.get_children():
            self._dl_tree.delete(i)
        self._dl_count = 0
        self._set_status("⏳ Barcha fayllar yuklanmoqda...")

        def on_file(filename, size_kb, result):
            def add():
                self._dl_count += 1
                status = "✅ Yuklandi" if result == "success" else (
                    "⏭ O'tkazildi" if result == "skipped" else "❌ Xato")
                self._dl_tree.insert("", "end", values=(self._dl_count, filename,
                                                         _fmt(size_kb), status))
                # oxirgi qatorga avtomatik aylantirish
                kids = self._dl_tree.get_children()
                if kids:
                    self._dl_tree.see(kids[-1])
            try:
                self.after(0, add)
            except Exception:
                pass

        def restore_btn():
            try:
                self._btn_dl_all.configure(text="⬇  Barchasini yuklash",
                                           state="normal", bootstyle="primary")
            except Exception:
                pass

        def work():
            dl = Downloader(api_client=self.api, state_tracker=self.state,
                            config=self.config, csv_logger=self.csv_log,
                            on_progress=self._update_progress, on_log=self._set_status,
                            on_file=on_file)
            try:
                stats = dl.download_all(court_types=[ct], stop_event=self._stop_event,
                                        source="qidiruv", **kw)
                self._set_status(f"✅ Tugadi — Yuklandi: {stats['success']}, "
                                 f"Xato: {stats['failed']}, O'tkazildi: {stats['skipped']}")
            except Exception as e:
                self._set_status(f"❌ Xatolik: {e}")
            finally:
                self._running = False
                try:
                    self.after(0, restore_btn)
                except Exception:
                    pass

        self._work_thread = threading.Thread(target=work, daemon=True)
        self._work_thread.start()

    # ─────────────────────────────────────────────────────────────────────────
    # SONLARNI YUKLASH (fon)
    # ─────────────────────────────────────────────────────────────────────────

    def _sum_counts(self, court_types: list[str], key: str):
        """Berilgan court_type lar bo'yicha 'key' (total/FIRST/...) yig'indisi."""
        vals = []
        for ct in court_types:
            d = self._counts.get(ct)
            if d and d.get(key) is not None:
                vals.append(d[key])
        if not vals:
            return None
        return sum(vals)

    def _refresh_counts_ui(self) -> None:
        def _apply():
            for upd in getattr(self, "_count_updaters", []):
                try:
                    upd()
                except Exception:
                    pass
        try:
            self.after(0, _apply)
        except Exception:
            pass

    def _fetch_all_counts(self) -> None:
        """
        Sonlarni olish.
        - Iqtisodiy: publication.sud.uz/report/counts (real).
        - Qolganlari: endpoint hali aniqlanmagan → "—" (soxta son ko'rsatmaymiz).
        """
        rc = self.api.report_counts()
        if rc and rc.get("total") is not None:
            # 814591 — bu 2024 yildan AVVALGI (eski) iqtisodiy ma'lumot
            self._counts["ECONOMIC_OLD"] = {
                "total":     rc.get("total"),
                "FIRST":     rc.get("first"),
                "APPEAL":    rc.get("appeal"),
                "CASSATION": rc.get("cassation"),
                "REVISION":  rc.get("control"),
            }
            self._refresh_counts_ui()
            self._set_status("✅ Iqtisodiy (2024 gacha) sonlari yuklandi")
        else:
            self._set_status("⚠️ Sonlarni yuklashda muammo (sayt yopiq bo'lishi mumkin)")

        # Ish turkumi (kategoriya) ro'yxatini yuklash
        try:
            cats = self.api.get_categories()
            if isinstance(cats, list) and cats:
                self._categories = [{"id": 0, "name": "Barchasi"}] + [
                    {"id": c.get("id"), "name": c.get("name", "")} for c in cats
                ]
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────────
    # YUKLASH
    # ─────────────────────────────────────────────────────────────────────────

    def _start_download(self, court_type: str, title: str) -> None:
        """Bitta yo'nalish (yil/tur) bo'yicha yuklashni boshlash."""
        if self._is_busy():
            messagebox.showinfo("Ma'lumot", "Avvalgi yuklash tugashini kuting yoki to'xtating.")
            return

        self._apply_settings()
        self._stop_event.clear()
        self._running = True
        self._stat_success = 0
        self._stat_failed = 0
        self.summary.reset()
        self.summary.mode = "bir_martalik"
        self.summary.court_types = [court_type]

        # Faol kartaning progress o'zgaruvchisini topish
        self._active_prog_var = self._find_prog_var(court_type)
        self._set_status(f"⏳ Yuklanmoqda: {title}")
        if self._active_prog_var:
            self._active_prog_var.set("⏳ Boshlandi...")

        self._work_thread = threading.Thread(
            target=self._download_worker,
            args=(court_type, title),
            daemon=True,
        )
        self._work_thread.start()

    def _find_prog_var(self, court_type: str) -> Optional[tk.StringVar]:
        for cat in CATEGORIES:
            for sub in cat["subs"]:
                if sub["court_type"] == court_type and "_prog_var" in sub:
                    return sub["_prog_var"]
        return None

    def _download_worker(self, court_type: str, title: str) -> None:
        downloader = Downloader(
            api_client=self.api,
            state_tracker=self.state,
            config=self.config,
            csv_logger=self.csv_log,
            on_progress=self._update_progress,
            on_log=self._set_status,
        )
        try:
            stats = downloader.download_all(
                court_types=[court_type],
                stop_event=self._stop_event,
                source="bir_martalik",
            )
            msg = (f"✅ Tugadi — Yuklandi: {stats['success']}, "
                   f"Xato: {stats['failed']}, O'tkazildi: {stats['skipped']}")
            self._set_status(msg)
            if self._active_prog_var:
                self.after(0, lambda: self._active_prog_var.set(msg))
        except Exception as e:
            self._set_status(f"❌ Xatolik: {e}")
        finally:
            self._running = False

    def _update_progress(self, *, success: int = 0, failed: int = 0, skipped: int = 0) -> None:
        self._stat_success += success
        self._stat_failed += failed
        if self._active_prog_var:
            txt = f"⏳ Yuklandi: {self._stat_success}  |  Xato: {self._stat_failed}"
            self.after(0, lambda: self._active_prog_var.set(txt))

    def _apply_settings(self) -> None:
        self.config.download_path = self.config.download_path or default_download_path()
        self.config.max_workers = 1
        try:
            self.config.save()
        except Exception:
            pass

    def _is_busy(self) -> bool:
        if self._work_thread and self._work_thread.is_alive():
            return True
        if self._running:
            self._running = False
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # HOLAT / YOPISH
    # ─────────────────────────────────────────────────────────────────────────

    def _set_status(self, text: str) -> None:
        try:
            self.after(0, lambda: self._status_var.set(text))
        except Exception:
            pass

    def _on_close(self) -> None:
        self._stop_event.set()
        try:
            self.csv_log.close()
        except Exception:
            pass
        self.destroy()
