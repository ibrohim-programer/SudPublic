# SUDPUBLIK.exe — Windows uchun qurish yo'riqnomasi

`.exe` faylini **faqat Windows kompyuterda** yaratish mumkin
(PyInstaller bir OS'dan boshqasiga qura olmaydi — Linux'da `.exe` chiqmaydi).

Ikki yo'l bor:

---

## A YO'L — Windows kompyutersiz (GitHub Actions, tavsiya etiladi)

Agar sizda Windows kompyuter bo'lmasa, GitHub o'zining Windows serverida
quradi va siz tayyor `.exe` ni yuklab olasiz.

1. Loyihani GitHub repozitoriyga yuklang (push).
2. Repozitoriyda **Actions** bo'limiga o'ting.
3. **"Build Windows EXE"** workflow'ni tanlab, **"Run workflow"** tugmasini bosing.
   (Yoki `main` branchga push qilsangiz, avtomatik ishga tushadi.)
4. Qurilish tugagach (~3-5 daqiqa), o'sha sahifadan **"SUDPUBLIK-windows"**
   nomli artifact'ni yuklab oling — ichida `SUDPUBLIK.exe` bo'ladi.

> Workflow fayli allaqachon tayyor: `.github/workflows/build-windows.yml`

---

## B YO'L — Windows kompyuterda qo'lda qurish

### 1-qadam — Python 3.12 o'rnatish

[python.org/downloads](https://www.python.org/downloads/release/python-3120/)
dan **Python 3.12** ni yuklab o'rnating.

> ⚠️ Python 3.14 dan foydalanmang — PyInstaller uni hali to'liq
> qo'llab-quvvatlamaydi. 3.11 yoki 3.12 ishonchli.
>
> O'rnatishda **"Add Python to PATH"** belgisini yoqing.

### 2-qadam — Loyihani tayyorlash

PowerShell yoki CMD da, loyiha papkasida:

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install pyinstaller
```

### 3-qadam — .exe ni qurish

```bat
pyinstaller build.spec --noconfirm
```

### 4-qadam — Natija

```
dist\SUDPUBLIK.exe
```

Bu faylni istalgan Windows 10/11 kompyuterga ko'chirib, ikki marta bosib
ishlatish mumkin — Python yoki kutubxona o'rnatish shart emas.

---

## Eslatmalar

- Birinchi ishga tushirishda Windows Defender / SmartScreen ogohlantirishi
  mumkin ("Noma'lum nashriyot"). **"More info" → "Run anyway"** ni bosing.
  Bu PyInstaller .exe lariga xos — virus emas.
- Dastur ma'lumotlari (sozlama, jurnal, holat) `Hujjatlar\SUDPUBLIK\` ga,
  yuklab olingan PDF lar `Hujjatlar\Sud_Hujjatlari\` ga saqlanadi.
- Ikonka `assets\icon.ico` dan olinadi.
