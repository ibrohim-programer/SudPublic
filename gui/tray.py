# gui/tray.py — Sistem tray (pystray + Pillow)
# SudParser v3.0

import threading
from typing import Callable, Optional

try:
    import pystray
    from PIL import Image, ImageDraw
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False


def _create_icon_image(size: int = 64) -> "Image.Image":
    """
    Icon.ico topilmasa — dasturiy tarzda oddiy ikonka yaratish.
    Ko'k fon ustida oq 'S' harfi.
    """
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (size, size), color=(30, 60, 120))
    draw = ImageDraw.Draw(img)
    # Oddiy S harfi
    draw.text((size // 4, size // 6), "S", fill=(255, 255, 255))
    return img


class TrayManager:
    """
    Sistem tray ikonkasini boshqarish.
    pystray mavjud bo'lmasa — jim ishlaydi (xato chiqarmaydi).
    """

    def __init__(
        self,
        on_show:    Optional[Callable] = None,   # Oynani ko'rsatish
        on_quit:    Optional[Callable] = None,   # Dasturni yopish
        on_toggle_monitor: Optional[Callable] = None,
    ):
        self._on_show    = on_show
        self._on_quit    = on_quit
        self._on_toggle  = on_toggle_monitor
        self._icon: Optional["pystray.Icon"] = None
        self._thread: Optional[threading.Thread] = None
        self._monitor_active = False

    def start(self, icon_path: Optional[str] = None) -> None:
        """Tray ikonkasini fonda ishga tushirish"""
        if not PYSTRAY_AVAILABLE:
            return

        try:
            # Ikonka rasmini yuklash
            if icon_path:
                try:
                    img = Image.open(icon_path)
                except Exception:
                    img = _create_icon_image()
            else:
                img = _create_icon_image()

            menu = pystray.Menu(
                pystray.MenuItem("SudParser ni Ko'rsatish", self._show, default=True),
                pystray.MenuItem("Monitoring",              self._toggle_monitor),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Yopish",                 self._quit),
            )

            self._icon = pystray.Icon(
                name="SudParser",
                icon=img,
                title="SudParser — Sud Hujjatlari Yuklovchi",
                menu=menu,
            )

            self._thread = threading.Thread(
                target=self._icon.run,
                daemon=True,
                name="TrayThread",
            )
            self._thread.start()
        except Exception:
            pass

    def stop(self) -> None:
        """Tray ikonkasini yopish"""
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass

    def notify(self, title: str, message: str) -> None:
        """Bildiruv ko'rsatish"""
        if self._icon and PYSTRAY_AVAILABLE:
            try:
                self._icon.notify(message=message, title=title)
            except Exception:
                pass

    def set_monitor_state(self, active: bool) -> None:
        """Monitoring holati (menyu belgisi uchun)"""
        self._monitor_active = active

    # ─── Ichki callback lar ──────────────────────────────────────────────────

    def _show(self, icon, item) -> None:
        if self._on_show:
            self._on_show()

    def _quit(self, icon, item) -> None:
        self.stop()
        if self._on_quit:
            self._on_quit()

    def _toggle_monitor(self, icon, item) -> None:
        if self._on_toggle:
            self._on_toggle()