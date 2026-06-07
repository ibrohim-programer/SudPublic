# SudParser — Dasturchi uchun Qo'llanma (README_BUILD.md)

## Loyiha haqida
`SudParser` — **publication.sud.uz** ochiq portalidan sud hujjatlarini (PDF) avtomatik yuklab oluvchi **cross-platform** dastur (Windows va Linux/Ubuntu).

- **REST API** orqali ishlaydi (Selenium kerak emas)
- Real-time **monitoring rejimi** — yangi hujjatlar tushishi bilan avtomatik yuklab oladi
- **PyInstaller** bilan `.exe` (Windows) yoki binar (Linux) paketlanadi

---

## Talab qilinadigan muhit

| Dastur | Versiya |
|--------|---------|
| Python | 3.10+ (3.11 yoki 3.12 tavsiya) |
| pip    | 22+    |
| OS     | Windows 10/11 (64-bit) **yoki** Ubuntu 20.04+ / boshqa Linux |

---

## O'rnatish va ishga tushirish (dasturchiga)

### Windows

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

### Linux / Ubuntu

```bash
# 1. Tizim paketlari (tkinter + tray uchun)
sudo apt update
sudo apt install -y python3 python3-venv python3-pip python3-tk \
                    gir1.2-appindicator3-0.1     # tray ikonkasi uchun (ixtiyoriy)

# 2. Loyihani yuklab oling
git clone <repo_url>
cd sudparser

# 3. Virtual muhit yarating
python3 -m venv venv
source venv/bin/activate

# 4. Kutubxonalarni o'rnating
pip install -r requirements.txt

# 5. Dasturni ishga tushiring
python3 main.py
```

> **Eslatma (Linux):** `python3-tk` o'rnatilmagan bo'lsa GUI ishga tushmaydi.
> Tray ikonkasi ko'rinmasa `gir1.2-appindicator3-0.1` paketini o'rnating —
> bu bo'lmasa ham dastur ishlaydi, faqat tray menyusi bo'lmaydi.

---

## EXE / Binar yaratish

`build.spec` allaqachon sozlangan — u **SUDPUBLIK** ijro etiluvchi faylini yaratadi
(lokal modullar, assets, ttkbootstrap/pystray va PIL._tkinter_finder avtomatik qo'shiladi).

### Linux (binar) — Ubuntu

```bash
source .venv/bin/activate
pip install pyinstaller

pyinstaller build.spec --noconfirm

# Natija: dist/SUDPUBLIK   (ELF ijro etiluvchi)
chmod +x dist/SUDPUBLIK
./dist/SUDPUBLIK
```

Ish stolidan ochish uchun `dist/SUDPUBLIK.desktop` yorlig'ini ishlatishingiz mumkin
(Exec va Icon yo'llarini o'z papkangizga moslang).

### Windows (.exe)

```bash
venv\Scripts\activate
pip install pyinstaller

pyinstaller build.spec --noconfirm

# Natija: dist/SUDPUBLIK.exe
```

> **Diqqat:** PyInstaller cross-compile qilmaydi — Linux binarni Linux'da,
> `.exe` ni Windows'da alohida qurish kerak.

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
| `ModuleNotFoundError: tkinter` (Linux) | `sudo apt install python3-tk` |
| EXE ishga tushmaydi | Antivirus tekshiring, `dist/` papkasida ishga tushiring |
| Linux binar ishga tushmaydi | `chmod +x dist/SudParser` qiling |
| `400 Bad Request` | `startDate` parametrini tekshiring — null bo'lmasligi kerak |
| `429 Too Many Requests` | So'rovlar oralig'ini oshiring (0.5s → 1s) |
| Tray ikonkasi ko'rinmaydi (Windows) | `pystray` to'g'ri o'rnatilganini tekshiring |
| Tray ikonkasi ko'rinmaydi (Linux) | `sudo apt install gir1.2-appindicator3-0.1` |