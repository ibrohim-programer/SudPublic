╔══════════════════════════════════════════════════════════════╗
║   SUDPUBLIK — Sud hujjatlarini avtomatik yuklab oluvchi        ║
╚══════════════════════════════════════════════════════════════╝

Bu dastur publication.sud.uz portalidan sud hujjatlarini (PDF)
avtomatik yuklab oladi. O'rnatish kerak emas — bitta fayl.


────────────────────────────────────────────────────────────────
  ISHGA TUSHIRISH (eng oson yo'l)
────────────────────────────────────────────────────────────────

  Linux (Ubuntu va boshqalar):

  1) Fayllar menejerida "SUDPUBLIK" fayliga sichqonchaning
     o'ng tugmasi bilan bosing → "Properties" (Xususiyatlar)
     → "Permissions" → "Allow executing file as program"
     belgisini yoqing.

  2) "SUDPUBLIK" ustiga ikki marta bosing — dastur ochiladi.

  Yoki terminal orqali:

     chmod +x SUDPUBLIK
     ./SUDPUBLIK


────────────────────────────────────────────────────────────────
  MENYUGA QO'SHISH (ixtiyoriy)
────────────────────────────────────────────────────────────────

  Dasturni Ubuntu menyusiga (ilovalar ro'yxatiga) qo'shish uchun:

     ./install.sh

  Shundan keyin "SUDPUBLIK" ni ilovalar menyusidan topib
  ishga tushirishingiz mumkin.


────────────────────────────────────────────────────────────────
  FAYLLAR QAYERGA SAQLANADI?
────────────────────────────────────────────────────────────────

  • Yuklab olingan PDF lar:   ~/Documents/Sud_Hujjatlari/
    (dastur ichidan boshqa papka tanlash mumkin)

  • Sozlama, jurnal, holat:   ~/Documents/SUDPUBLIK/

  Dastur fayllarni o'zi yoza oladigan papkaga saqlaydi —
  shuning uchun SUDPUBLIK ni istalgan joyga qo'yib ishlatsa bo'ladi.


────────────────────────────────────────────────────────────────
  QANDAY ISHLATILADI?
────────────────────────────────────────────────────────────────

  1) "Sud yo'nalishlari" dan kerakli yo'nalishni belgilang.
  2) Kerak bo'lsa, filtrlarni (sana, hujjat turi) tanlang.
  3) "Yuklab olishni boshlash" tugmasini bosing.
  4) Yangi hujjatlarni avtomatik kuzatish uchun
     "Monitoringni yoqish" dan foydalaning.


────────────────────────────────────────────────────────────────
  TEZ-TEZ "Connection refused" XATOSI CHIQSA
────────────────────────────────────────────────────────────────

  Bu sayt sizni juda ko'p so'rov uchun vaqtincha bloklaganini
  bildiradi. "Sozlamalar" da:
    • "Bir vaqtda yuklash" ni 1-2 ga tushiring,
    • "So'rovlar oralig'i" ni 1.5-2.0 soniyaga oshiring.
  Dastur o'zi ham kutib, avtomatik qayta urinadi.

────────────────────────────────────────────────────────────────
