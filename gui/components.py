# gui/components.py — Qayta ishlatiladigan GUI komponentlar
# SudParser v3.0 | tkinter + ttkbootstrap

import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable
import ttkbootstrap as tb
from ttkbootstrap.constants import *


class Tooltip:
    """
    Vidjet ustiga sichqoncha kelganda chiqadigan kichik yordam oynasi.
    Foydalanuvchi har bir sozlama nima qilishini darhol tushunadi.
    """

    def __init__(self, widget, text: str, delay: int = 450):
        self.widget = widget
        self.text = text
        self.delay = delay
        self._tip: Optional[tk.Toplevel] = None
        self._after_id: Optional[str] = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None):
        self._cancel()
        self._after_id = self.widget.after(self.delay, self._show)

    def _cancel(self):
        if self._after_id:
            self.widget.after_cancel(self._after_id)
            self._after_id = None

    def _show(self):
        if self._tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 16
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self._tip = tk.Toplevel(self.widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        lbl = tk.Label(
            self._tip,
            text=self.text,
            justify="left",
            background="#11111b",
            foreground="#cdd6f4",
            relief="solid",
            borderwidth=1,
            font=("Segoe UI", 9),
            padx=8,
            pady=5,
            wraplength=320,
        )
        lbl.pack()

    def _hide(self, _event=None):
        self._cancel()
        if self._tip:
            self._tip.destroy()
            self._tip = None


def add_tooltip(widget, text: str) -> Tooltip:
    """Qisqa yordamchi: vidjetga tooltip biriktirish"""
    return Tooltip(widget, text)


class StatCard(tb.Frame):
    """
    Bitta statistika kartasi: katta raqam + ostida izoh.
    Masalan: "128 \n Yuklab olindi".
    """

    def __init__(self, parent, title: str, value: str = "0",
                 bootstyle: str = "secondary", **kw):
        super().__init__(parent, padding=10, **kw)
        self._value_var = tk.StringVar(value=value)
        self._value_lbl = tb.Label(
            self, textvariable=self._value_var,
            font=("Segoe UI", 20, "bold"), bootstyle=bootstyle,
            anchor="center",
        )
        self._value_lbl.pack(fill=X)
        tb.Label(
            self, text=title, font=("Segoe UI", 9),
            bootstyle="secondary", anchor="center",
        ).pack(fill=X)

    def set(self, value) -> None:
        self._value_var.set(str(value))


class LabeledEntry(tb.Frame):
    """Label + Entry birlashgan widget"""

    def __init__(self, parent, label: str, placeholder: str = "", width: int = 20, **kw):
        super().__init__(parent, **kw)
        tb.Label(self, text=label, width=16, anchor="w").pack(side=LEFT, padx=(0, 4))
        self.var = tk.StringVar()
        self.entry = tb.Entry(self, textvariable=self.var, width=width)
        self.entry.pack(side=LEFT, fill=X, expand=True)
        if placeholder:
            self._set_placeholder(placeholder)

    def _set_placeholder(self, text: str) -> None:
        def on_focus_in(e):
            if self.var.get() == text:
                self.var.set("")
                self.entry.config(foreground="")
        def on_focus_out(e):
            if not self.var.get():
                self.var.set(text)
                self.entry.config(foreground="gray")
        self.var.set(text)
        self.entry.config(foreground="gray")
        self.entry.bind("<FocusIn>", on_focus_in)
        self.entry.bind("<FocusOut>", on_focus_out)

    def get(self) -> str:
        return self.var.get().strip()

    def set(self, value: str) -> None:
        self.var.set(value)


class DateEntry(tb.Frame):
    """
    Kalendardan sana tanlash widgeti (qo'lda yozilmaydi).
    📅 tugmasi kalendar oynasini ochadi, ✕ tugmasi tanlovni tozalaydi.
    Sana ixtiyoriy — tanlanmasa filtr qo'llanmaydi.
    """

    PLACEHOLDER = "kun.oy.yil"

    def __init__(self, parent, label: str = "", **kw):
        super().__init__(parent, **kw)
        self._date = None  # datetime.date yoki None

        if label:
            tb.Label(self, text=label, width=12, anchor="w").pack(side=LEFT, padx=(0, 4))

        self.var = tk.StringVar(value=self.PLACEHOLDER)
        self.entry = tb.Entry(self, textvariable=self.var, width=11, state="readonly")
        self.entry.pack(side=LEFT)

        self._btn_pick = tb.Button(
            self, text="📅", width=3, bootstyle="secondary-outline",
            command=self._pick_date, takefocus=False,
        )
        self._btn_pick.pack(side=LEFT, padx=(3, 0))

        self._btn_clear = tb.Button(
            self, text="✕", width=2, bootstyle="secondary-outline",
            command=self.clear, takefocus=False,
        )
        self._btn_clear.pack(side=LEFT, padx=(2, 0))

    def _pick_date(self) -> None:
        """Kalendar oynasini ochib, tanlangan sanani saqlash"""
        from ttkbootstrap.dialogs import Querybox
        try:
            selected = Querybox.get_date(
                parent=self,
                title="Sanani tanlang",
                startdate=self._date,
                bootstyle="primary",
            )
        except Exception:
            return
        if selected:
            self._date = selected
            self.var.set(selected.strftime("%d.%m.%Y"))

    def clear(self) -> None:
        """Tanlangan sanani bekor qilish"""
        self._date = None
        self.var.set(self.PLACEHOLDER)

    def get_ms(self) -> Optional[int]:
        """Tanlangan sanani Unix ms ga aylantirish; tanlanmasa None"""
        if not self._date:
            return None
        import datetime
        dt = datetime.datetime(self._date.year, self._date.month, self._date.day)
        return int(dt.timestamp() * 1000)

    def get(self) -> str:
        """Tanlangan sana matni (DD.MM.YYYY) yoki bo'sh satr"""
        return "" if not self._date else self._date.strftime("%d.%m.%Y")


class ScrolledLog(tb.Frame):
    """Avtomatik skrollanadigan log matni"""

    MAX_LINES = 2000  # Xotira tejash uchun cheklov

    def __init__(self, parent, height: int = 10, **kw):
        super().__init__(parent, **kw)
        self.text = tk.Text(
            self,
            height=height,
            state="disabled",
            wrap="word",
            font=("Consolas", 9),
            background="#1e1e2e",
            foreground="#cdd6f4",
        )
        sb = tb.Scrollbar(self, orient=VERTICAL, command=self.text.yview, bootstyle="secondary")
        self.text.configure(yscrollcommand=sb.set)
        self.text.pack(side=LEFT, fill=BOTH, expand=True)
        sb.pack(side=RIGHT, fill=Y)

        # Rang teglari
        self.text.tag_configure("ok",   foreground="#a6e3a1")
        self.text.tag_configure("err",  foreground="#f38ba8")
        self.text.tag_configure("warn", foreground="#fab387")
        self.text.tag_configure("info", foreground="#89dceb")

    def append(self, message: str) -> None:
        """Log qatorini qo'shish (thread-safe emas — GUI threadda chaqirilsin)"""
        tag = "ok" if "✅" in message else \
              "err" if "❌" in message else \
              "warn" if "⚠️" in message else "info"

        self.text.configure(state="normal")
        self.text.insert(END, message + "\n", tag)

        # Cheklovdan oshsa eski qatorlarni o'chirish
        line_count = int(self.text.index(END).split(".")[0]) - 1
        if line_count > self.MAX_LINES:
            self.text.delete("1.0", f"{line_count - self.MAX_LINES}.0")

        self.text.configure(state="disabled")
        self.text.see(END)

    def clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", END)
        self.text.configure(state="disabled")


class ProgressBar(tb.Frame):
    """Progressbar + statistika etiketi"""

    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self.progress = tb.Progressbar(
            self, orient=HORIZONTAL, mode="determinate", bootstyle="success-striped"
        )
        self.progress.pack(fill=X, pady=(2, 4))

        stats_frame = tb.Frame(self)
        stats_frame.pack(fill=X)
        self._ok_var   = tk.StringVar(value="✅ 0")
        self._err_var  = tk.StringVar(value="❌ 0")
        self._skip_var = tk.StringVar(value="⏭️ 0")
        self._pct_var  = tk.StringVar(value="0 / 0  (0%)")

        tb.Label(stats_frame, textvariable=self._ok_var,   bootstyle="success").pack(side=LEFT, padx=8)
        tb.Label(stats_frame, textvariable=self._err_var,  bootstyle="danger").pack(side=LEFT, padx=8)
        tb.Label(stats_frame, textvariable=self._skip_var, bootstyle="secondary").pack(side=LEFT, padx=8)
        tb.Label(stats_frame, textvariable=self._pct_var).pack(side=RIGHT, padx=8)

    def update(self, success: int, failed: int, skipped: int, total: int) -> None:
        done = success + failed + skipped
        pct = (done / total * 100) if total > 0 else 0
        self.progress["maximum"] = total
        self.progress["value"]   = done
        self._ok_var.set(f"✅ Muvaffaqiyatli: {success}")
        self._err_var.set(f"❌ Xato: {failed}")
        self._skip_var.set(f"⏭️ O'tkazildi: {skipped}")
        self._pct_var.set(f"{done:,} / {total:,}  ({pct:.1f}%)")

    def reset(self) -> None:
        self.progress["value"] = 0
        self._ok_var.set("✅ 0")
        self._err_var.set("❌ 0")
        self._skip_var.set("⏭️ 0")
        self._pct_var.set("0 / 0  (0%)")