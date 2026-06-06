# SudParser — Dasturchi uchun Qo'llanma (README_BUILD.md)

## Loyiha haqida
`SudParser` — **publication.sud.uz** ochiq portalidan sud hujjatlarini (PDF) avtomatik yuklab oluvchi Windows dastur.

- **REST API** orqali ishlaydi (Selenium kerak emas)
- Real-time **monitoring rejimi** — yangi hujjatlar tushishi bilan avtomatik yuklab oladi
- **PyInstaller** bilan `.exe` paketlanadi

---

## Talab qilinadigan muhit

| Dastur | Versiya |
|--------|---------|
| Python | 3.10+ (3.11 yoki 3.12 tavsiya) |
| pip    | 22+    |
| OS     | Windows 10/11 (64-bit) |

---

## O'rnatish va ishga tushirish (dasturchiga)

```bash
# 1. Loyihani yuklab oling
git clone <repo_url>
cd sudparser

# 2. Virtual muhit yarating
python -m venv venv
venv\Scripts\activate

# 3. Kutubxonalarni o'rnating
pip install -r requirements.txt

# 4. Dasturni ishga tushiring
python main.py
```

---

## EXE yaratish

```bash
# Virtual muhit faol bo'lsin
venv\Scripts\activate

# PyInstaller o'rnating (agar yo'q bo'lsa)
pip install pyinstaller

# EXE yaratish (build.spec orqali)
pyinstaller build.spec

# Natija: dist/SudParser.exe
```

### Muqobil (qo'lda buyruq bilan):
```bash
pyinstaller --onefile --windowed ^
            --icon=assets/icon.ico ^
            --name=SudParser ^
            --add-data="assets;assets" ^
            --hidden-import=ttkbootstrap ^
            --hidden-import=pystray ^
            --collect-all=ttkbootstrap ^
            --collect-all=pystray ^
            main.py
```

---

## Loyiha tuzilmasi

```
sudparser/
├── main.py              # Kirish nuqtasi
├── config.py            # Sozlamalar (JSON ga saqlanadi)
├── utils.py             # Yordamchi funksiyalar
├── logger.py            # CSV log + sessiya xulosasi
├── state_tracker.py     # Yuklangan fayllar JSON bazasi
├── downloader.py        # Fayl yuklab olish
├── monitor.py           # Real-time monitoring engine
├── api/
│   ├── __init__.py
│   ├── endpoints.py     # URL va konstantalar
│   ├── models.py        # Dataclass modellari
│   └── client.py        # API bilan ishlash
├── gui/
│   ├── __init__.py
│   ├── app.py           # Asosiy GUI (tkinter + ttkbootstrap)
│   ├── components.py    # Qayta ishlatiladigan komponentlar
│   └── tray.py          # Sistem tray (pystray)
├── assets/
│   └── icon.ico         # Dastur ikonkasi
├── requirements.txt
├── build.spec           # PyInstaller konfiguratsiya
├── README_BUILD.md      # Shu fayl
└── README_USER.md       # Foydalanuvchi uchun
```

---

## API haqida

**Base URL:** `https://publication.sud.uz`

| Endpoint | Tavsif |
|---------|--------|
| `GET /unauthorized/publications` | Hujjatlar ro'yxati (parametrlar bilan) |
| `GET /types` | Hujjat turlari |
| `GET /category` | Kategoriyalar |
| `GET /file/{id}` | PDF faylni yuklab olish |

**Muhim:** `startDate` parametrini hech qachon `null` sifatida yuborma — `400 Bad Request` beradi. Faqat sana tanlangan bo'lsa qo'sh.

---

## Muhim texnik eslatmalar

1. `requests.Session()` ishlatiladi — har safar yangi connection ochilmaydi
2. Barcha tarmoq operatsiyalari alohida **threadda** — GUI hech qachon muzlamaydi
3. Monitoring: faqat **1-sahifa** (`page=0, size=50`) tekshiriladi — sayt yukiga tejamkor
4. `StateTracker` — monitoring rejimida har yuklash JSON bazaga yoziladi (dastur qayta ishga tushsa ham eslab qoladi)
5. EXE ichida resurslar `sys._MEIPASS` orqali topiladi
6. CSV log va sessiya xulosasi `logs/` papkasiga saqlanadi

---

## Xatolarni bartaraf etish

| Xato | Yechim |
|------|--------|
| `ModuleNotFoundError: ttkbootstrap` | `pip install ttkbootstrap` |
| EXE ishga tushmaydi | Antivirus tekshiring, `dist/` papkasida ishga tushiring |
| `400 Bad Request` | `startDate` parametrini tekshiring — null bo'lmasligi kerak |
| `429 Too Many Requests` | So'rovlar oralig'ini oshiring (0.5s → 1s) |
| Tray ikonkasi ko'rinmaydi | `pystray` to'g'ri o'rnatilganini tekshiring |