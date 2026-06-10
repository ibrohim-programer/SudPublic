# gui/app.py — SUDPUBLIK asosiy oyna (Dashboard ko'rinishi)
# public.sud.uz uslubidagi karta-dizayn

import tkinter as tk
from tkinter import messagebox
import threading
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


# ─── Sud turlari tuzilmasi ──────────────────────────────────────────────────
# Har kategoriya bir yoki ikki "sub" (yil/tur) dan iborat.
# Iqtisodiy → 2024 gacha (ECONOMIC_OLD) va 2024 dan keyin (ECONOMIC).
CATEGORIES = [
    {
        "name": "ИҚТИСОДИЙ СУДЛАР",
        "icon": "🏦",
        "subs": [
            {"court_type": "ECONOMIC_OLD", "title": "2024 йилдан аввал кўрилган ишлар"},
            {"court_type": "ECONOMIC",     "title": "2024 йилдан кейинги кўрилган ишлар"},
        ],
    },
    {
        "name": "МАЪМУРИЙ СУДЛАР",
        "icon": "📋",
        "subs": [
            {"court_type": "ADMINISTRATIVE", "title": "Барча ишлар"},
        ],
    },
    {
        "name": "ФУҚАРОЛИК ИШЛАРИ БЎЙИЧА СУДЛАР",
        "icon": "👥",
        "subs": [
            {"court_type": "CIVIL", "title": "Барча ишлар"},
        ],
    },
    {
        "name": "ЖИНОЯТ ИШЛАРИ БЎЙИЧА СУДЛАР",
        "icon": "⚖️",
        "subs": [
            {"court_type": "CRIMINAL", "title": "Барча ишлар"},
        ],
    },
    {
        "name": "МАЪМУРИЙ ҲУҚУҚБУЗАРЛИК БЎЙИЧА ИШЛАР",
        "icon": "📑",
        "subs": [
            {"court_type": "ADMINISTRATIVE_OFFENCE", "title": "Барча ишлар"},
        ],
    },
]

# Instansiya turlari (label + API instanceType kodi)
INSTANCES = [
    ("Биринчи инстанция",      "FIRST"),
    ("Апелляция инстанцияси",  "APPEAL"),
    ("Кассация инстанцияси",   "CASSATION"),
    ("Тафтиш",                 "REVISION"),
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
            text="Интернет тармоғида\nэълон қилинган\nсуд қарорлари",
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
        self._status_var = tk.StringVar(value="Тайёр")
        self._status_lbl = tb.Label(right, textvariable=self._status_var,
                                     bootstyle="secondary", anchor="center",
                                     font=("Segoe UI", 10))
        self._status_lbl.pack(side=BOTTOM, fill=X, pady=6)

        # O'ng kontent
        self._content = tb.Frame(right, padding=18)
        self._content.pack(side=TOP, fill=BOTH, expand=True)

    def _clear_content(self) -> None:
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
        tb.Label(header, text="Суд қарорлари — йўналишлар",
                 font=("Segoe UI", 15, "bold")).pack(side=LEFT)

        for idx, cat in enumerate(CATEGORIES):
            self._make_category_card(self._content, idx, cat)

        self._set_status("Тайёр — йўналишни танланг")
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
        tb.Button(header, text="←  Орқага", bootstyle="secondary",
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
        ("court",    "Суд номи",           220),
        ("instance", "Суд инстанцияси",    130),
        ("case",     "Иш рақами",          130),
        ("judge",    "Ишни кўрган судья",  180),
        ("date",     "Иш кўрилган сана",   120),
        ("result",   "Иш натижаси",        160),
        ("doctype",  "Суд хужжати тури",   160),
    ]

    def show_search(self, sub: dict) -> None:
        self._clear_content()
        self._count_updaters = []
        self._search_sub = sub
        self._search_rows = []   # joriy natijalar (raw dict lar)

        # Sarlavha + orqaga
        top = tb.Frame(self._content)
        top.pack(fill=X)
        tb.Button(top, text="←  Орқага", bootstyle="secondary",
                  command=lambda: self.show_detail(self._current_cat)).pack(side=LEFT)
        tb.Label(top, text="   " + sub["title"], font=("Segoe UI", 13, "bold")).pack(side=LEFT)

        # ── Filtrlar paneli ───────────────────────────────────────────────
        flt = tb.Labelframe(self._content, text="  🔎  Филтрлар  ", padding=10)
        flt.pack(fill=X, pady=(10, 8))

        r1 = tb.Frame(flt); r1.pack(fill=X, pady=3)
        tb.Label(r1, text="Суд хужжати тури:", width=18, anchor="w").pack(side=LEFT)
        self._f_type = tk.StringVar()
        type_cb = tb.Combobox(r1, textvariable=self._f_type, state="readonly", width=28)
        type_cb["values"] = [d["name"] for d in self._doc_types]
        type_cb.set(self._doc_types[0]["name"])
        type_cb.pack(side=LEFT, padx=(0, 18))
        tb.Label(r1, text="Суд инстанцияси:", width=16, anchor="w").pack(side=LEFT)
        self._f_inst = tk.StringVar()
        inst_cb = tb.Combobox(r1, textvariable=self._f_inst, state="readonly", width=22)
        inst_cb["values"] = list(INSTANCE_TYPES.values())
        inst_cb.set(list(INSTANCE_TYPES.values())[0])
        inst_cb.pack(side=LEFT)

        r2 = tb.Frame(flt); r2.pack(fill=X, pady=3)
        tb.Label(r2, text="Санадан:", width=18, anchor="w").pack(side=LEFT)
        self._f_date_from = DateEntry(r2); self._f_date_from.pack(side=LEFT, padx=(0, 18))
        tb.Label(r2, text="Санагача:", width=10, anchor="w").pack(side=LEFT)
        self._f_date_to = DateEntry(r2); self._f_date_to.pack(side=LEFT, padx=(0, 18))
        tb.Label(r2, text="Иш рақами:", width=12, anchor="w").pack(side=LEFT)
        self._f_case = tk.StringVar()
        tb.Entry(r2, textvariable=self._f_case, width=18).pack(side=LEFT)

        r3 = tb.Frame(flt); r3.pack(fill=X, pady=(6, 0))
        tb.Button(r3, text="🔍  Қидириш", bootstyle="success",
                  command=self._do_search).pack(side=LEFT)
        tb.Button(r3, text="Тозалаш", bootstyle="secondary-outline",
                  command=self._clear_search_filters).pack(side=LEFT, padx=6)
        self._search_info = tk.StringVar(value="")
        tb.Label(r3, textvariable=self._search_info, bootstyle="info").pack(side=LEFT, padx=12)
        tb.Button(r3, text="⬇  Барчасини юклаш", bootstyle="primary",
                  command=self._download_all_search).pack(side=RIGHT)

        # ── Natijalar jadvali ─────────────────────────────────────────────
        table_frame = tb.Frame(self._content)
        table_frame.pack(fill=BOTH, expand=True, pady=(4, 0))

        cols = [c[0] for c in self.TABLE_COLS] + ["pdf"]
        self._tree = tb.Treeview(table_frame, columns=cols, show="headings",
                                 bootstyle="primary", height=12)
        for key, label, width in self.TABLE_COLS:
            self._tree.heading(key, text=label)
            self._tree.column(key, width=width, anchor="w")
        self._tree.heading("pdf", text="Хужжат")
        self._tree.column("pdf", width=80, anchor="center")

        vsb = tb.Scrollbar(table_frame, orient=VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side=LEFT, fill=BOTH, expand=True)
        vsb.pack(side=RIGHT, fill=Y)
        # Qatorga 2 marta bosilsa — o'sha faylni yuklash
        self._tree.bind("<Double-1>", self._download_selected_row)

        self._set_status("Филтрни танлаб 'Қидириш' ни босинг")

    def _clear_search_filters(self) -> None:
        self._f_type.set(self._doc_types[0]["name"])
        self._f_inst.set(list(INSTANCE_TYPES.values())[0])
        self._f_date_from.clear()
        self._f_date_to.clear()
        self._f_case.set("")

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
        case = self._f_case.get().strip()
        if case: kw["case_number"] = case
        return kw

    def _do_search(self) -> None:
        ct = self._search_sub["court_type"]
        kw = self._search_filter_kwargs()
        self._set_status("⏳ Қидирилмоқда...")
        for i in self._tree.get_children():
            self._tree.delete(i)

        def work():
            try:
                d = self.api.fetch_raw_page(ct, page=0, size=50, **kw)
            except Exception as e:
                self._set_status(f"❌ Қидириш хатоси: {e}")
                return
            rows = d.get("content", []) or []
            total = d.get("totalElements", len(rows))
            self._search_rows = rows
            self.after(0, lambda: self._populate_tree(rows, total))

        threading.Thread(target=work, daemon=True).start()

    def _populate_tree(self, rows: list, total) -> None:
        for i in self._tree.get_children():
            self._tree.delete(i)
        for idx, item in enumerate(rows, 1):
            vals = self._row_values(idx, item) + ["📄 PDF"]
            self._tree.insert("", "end", iid=str(idx - 1), values=vals)
        self._search_info.set(f"Жами: {_fmt(total)} та  (кўрсатилди: {len(rows)})")
        self._set_status(f"✅ {len(rows)} та натижа кўрсатилди (жами {_fmt(total)})")

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
            str(item.get("judge") or ""),
            str(date),
            str(item.get("result") or ""),
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
            messagebox.showinfo("Маълумот", "Бу ёзувда файл йўқ.")
            return
        fd = atts[0].get("fileData") or {}
        file_id = fd.get("id")
        name = f"{item.get('id')}_{fd.get('name', 'hujjat.pdf')}"
        if not file_id:
            return
        self._set_status(f"⏳ Юкланмоқда: {name}")

        def work():
            try:
                data = self.api.download_file_bytes(file_id)
                from api import COURT_FOLDERS
                folder = COURT_FOLDERS.get(self._search_sub["court_type"], self._search_sub["court_type"])
                dest = ensure_dir(Path(self.config.download_path) / folder) / name
                dest.write_bytes(data)
                self._set_status(f"✅ Юкланди: {name}")
            except Exception as e:
                self._set_status(f"❌ Хато: {e}")

        threading.Thread(target=work, daemon=True).start()

    def _download_all_search(self) -> None:
        """Топилган барча файлларни (филтр бўйича) юклаш."""
        if self._is_busy():
            messagebox.showinfo("Маълумот", "Аввалги юклаш тугашини кутинг.")
            return
        ct = self._search_sub["court_type"]
        kw = self._search_filter_kwargs()
        self._apply_settings()
        self._stop_event.clear()
        self._running = True
        self._stat_success = 0
        self._stat_failed = 0
        self._active_prog_var = None
        self._set_status("⏳ Барча файллар юкланмоқда...")

        def work():
            dl = Downloader(api_client=self.api, state_tracker=self.state,
                            config=self.config, csv_logger=self.csv_log,
                            on_progress=self._update_progress, on_log=self._set_status)
            try:
                stats = dl.download_all(court_types=[ct], stop_event=self._stop_event,
                                        source="qidiruv", **kw)
                self._set_status(f"✅ Тугади — Юкланди: {stats['success']}, "
                                 f"Хато: {stats['failed']}, Ўтказилди: {stats['skipped']}")
            except Exception as e:
                self._set_status(f"❌ Хатолик: {e}")
            finally:
                self._running = False

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
        - Иqтисодий: publication.sud.uz/report/counts (real).
        - Qolganlari: endpoint hali aniqlanmagan → "—" (soxta son ko'rsatmaymiz).
        """
        rc = self.api.report_counts()
        if rc and rc.get("total") is not None:
            self._counts["ECONOMIC"] = {
                "total":     rc.get("total"),
                "FIRST":     rc.get("first"),
                "APPEAL":    rc.get("appeal"),
                "CASSATION": rc.get("cassation"),
                "REVISION":  rc.get("control"),
            }
            self._refresh_counts_ui()
            self._set_status("✅ Иqтисодий сонлари юкланди")
        else:
            self._set_status("⚠️ Сонларни юклашда муаммо (сайт ёпиқ бўлиши мумкин)")

    # ─────────────────────────────────────────────────────────────────────────
    # YUKLASH
    # ─────────────────────────────────────────────────────────────────────────

    def _start_download(self, court_type: str, title: str) -> None:
        """Bitta yo'nalish (yil/tur) bo'yicha yuklashni boshlash."""
        if self._is_busy():
            messagebox.showinfo("Маълумот", "Аввалги юклаш тугашини кутинг ёки тўхтатинг.")
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
        self._set_status(f"⏳ Юкланмоқда: {title}")
        if self._active_prog_var:
            self._active_prog_var.set("⏳ Бошланди...")

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
            msg = (f"✅ Тугади — Юкланди: {stats['success']}, "
                   f"Хато: {stats['failed']}, Ўтказилди: {stats['skipped']}")
            self._set_status(msg)
            if self._active_prog_var:
                self.after(0, lambda: self._active_prog_var.set(msg))
        except Exception as e:
            self._set_status(f"❌ Хатолик: {e}")
        finally:
            self._running = False

    def _update_progress(self, *, success: int = 0, failed: int = 0, skipped: int = 0) -> None:
        self._stat_success += success
        self._stat_failed += failed
        if self._active_prog_var:
            txt = f"⏳ Юкланди: {self._stat_success}  |  Хато: {self._stat_failed}"
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
