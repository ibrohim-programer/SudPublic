# gui/components.py — Qayta ishlatiladigan GUI komponentlar
# SudParser v3.0 | tkinter + ttkbootstrap

import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable
import ttkbootstrap as tb
from ttkbootstrap.constants import *


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
    """Sana kiritish uchun DD.MM.YYYY formatli widget"""

    PLACEHOLDER = "DD.MM.YYYY"

    def __init__(self, parent, label: str = "", **kw):
        super().__init__(parent, **kw)
        if label:
            tb.Label(self, text=label, width=12, anchor="w").pack(side=LEFT, padx=(0, 4))
        self.var = tk.StringVar(value=self.PLACEHOLDER)
        self.entry = tb.Entry(self, textvariable=self.var, width=12)
        self.entry.pack(side=LEFT)
        self.entry.bind("<FocusIn>",  self._on_in)
        self.entry.bind("<FocusOut>", self._on_out)

    def _on_in(self, e):
        if self.var.get() == self.PLACEHOLDER:
            self.var.set("")
            self.entry.config(foreground="")

    def _on_out(self, e):
        if not self.var.get():
            self.var.set(self.PLACEHOLDER)
            self.entry.config(foreground="gray")

    def get_ms(self) -> Optional[int]:
        """Sanani Unix ms ga aylantirish; to'ldirilmasa None qaytaradi"""
        val = self.var.get().strip()
        if val == self.PLACEHOLDER or not val:
            return None
        from utils import date_to_timestamp
        try:
            return date_to_timestamp(val)
        except ValueError:
            return None

    def get(self) -> str:
        val = self.var.get().strip()
        return "" if val == self.PLACEHOLDER else val


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