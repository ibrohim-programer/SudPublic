# config.py — Dastur sozlamalari
# SudParser v3.0

from dataclasses import dataclass, asdict, field
from pathlib import Path
import json

from utils import get_app_data_dir

CONFIG_FILE = "sudparser_config.json"


def default_download_path() -> str:
    """
    Standart saqlash papkasi: foydalanuvchining Documents papkasi ichida.
    Cross-platform (Windows, Linux, macOS).
    Misol: /home/ubuntu/Documents/Sud_Hujjatlari
    """
    return str(Path.home() / "Documents" / "Sud_Hujjatlari")


@dataclass
class Config:
    # Yuklab olish
    download_path: str = field(default_factory=default_download_path)
    max_workers: int = 5
    request_delay: float = 0.5
    retry_count: int = 3
    timeout: int = 30
    skip_existing: bool = True
    log_level: str = "INFO"

    # Monitoring
    monitor_interval_minutes: int = 10
    monitor_interval_seconds: int = 600
    notify_on_new_file: bool = True
    state_db_path: str = field(
        default_factory=lambda: str(get_app_data_dir() / "sudparser_state.json")
    )

    def __post_init__(self):
        # monitor_interval_seconds ni minutdan hisobla
        self.monitor_interval_seconds = self.monitor_interval_minutes * 60

    def save(self, path: str = CONFIG_FILE) -> None:
        """Sozlamalarni JSON faylga saqlash"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str = CONFIG_FILE) -> "Config":
        """JSON fayldan sozlamalarni yuklash"""
        p = Path(path)
        if p.exists():
            try:
                with open(p, encoding="utf-8") as f:
                    data = json.load(f)
                # Faqat mavjud maydonlarni olish (eski config versiyalari uchun)
                valid_keys = cls.__dataclass_fields__.keys()
                valid_data = {k: v for k, v in data.items() if k in valid_keys}
                cfg = cls(**valid_data)
                cfg.__post_init__()
                return cfg
            except Exception:
                pass
        return cls()