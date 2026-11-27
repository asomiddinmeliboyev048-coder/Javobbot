# JavobBot AI

Telegram Business uchun shaxsiy AI yordamchi. U oddiy, xavfsiz savollarga tabiiy javob beradi, muhim yoki nozik mavzularni esa egasining tasdig'iga yuboradi.

## Hozirgi MVP imkoniyatlari

- Telegram Business `business_connection` va `business_message` update'larini qabul qilish.
- Oddiy, xavfsiz matnli xabarlarga Google Gemini API orqali javob tayyorlash.
- Har bir Business chat uchun alohida suhbat tarixi.
- Muhim mavzularni admin'ga inline tugmalar bilan yuborish: tasdiqlash yoki rad etish.
- `/stats` va `/pending` admin buyruqlari.
- PostgreSQL'da xabarlar, ulanishlar va tasdiq navbatini saqlash.

## Texnologiyalar

- Python 3.12+
- aiogram 3
- Google Gemini API (REST)
- Supabase PostgreSQL (Session pooler) + asyncpg
- Render Web Service (HTTP health endpoint + Telegram long polling)

## 1. Kerakli ma'lumotlar

1. @BotFather orqali bot yaratib, token oling.
2. BotFather'da bot uchun **Business Mode / Secretary Mode** imkoniyatini yoqing.
3. Telegram akkauntingizda **Settings → Telegram Business → Chatbots** bo'limiga o'tib, botni ulang.
4. Botga kerakli chatlarga kirish va xabarlarga javob berish huquqini bering.
5. O'zingizning Telegram raqamli ID'ingizni aniqlang — bu `ADMIN_ID`.
6. Google AI Studio'dan Gemini API key va PostgreSQL ulanish URL'ini tayyorlang.

## 2. Lokal ishga tushirish

```bash
python -m venv .venv
# Windows:
.venv\\Scripts\\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

`.env.example` faylidan nusxa olib `.env` yarating va qiymatlarni to'ldiring:

```env
BOT_TOKEN=...
ADMIN_ID=...
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash
DATABASE_URL=postgresql://...
DATABASE_SSL=require
PERSONALITY_CONTEXT=Akkaunt egasi haqida tasdiqlangan qisqa ma'lumot
```

So'ng:

```bash
python main.py
```

Avval botning o'ziga shaxsiy chatdan `/start` yuboring. Shunda u muhim xabarlarni sizga yubora oladi.

## 3. Render'ga joylash

1. Render'da **New → Web Service** tanlang.
2. GitHub'dan `asomiddinmeliboyev048-coder/Javobbot` repozitoriyasini ulang.
3. Build command: `pip install -r requirements.txt`.
4. Start command: `python main.py`. Ilova Render bergan `PORT` qiymatida `0.0.0.0` ga HTTP server ochadi; `/health` endpointi health check uchun ishlaydi, Telegram update'lari esa polling orqali olinadi.
5. Environment bo'limiga `BOT_TOKEN`, `ADMIN_ID`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `DATABASE_URL`, `DATABASE_SSL` va `PERSONALITY_CONTEXT` qiymatlarini kiriting.
6. Supabase Dashboard → Connect → **Session pooler** bo'limidan connection string oling. Render'dagi doimiy worker uchun IPv4 tarmog'ida bu mos tanlov; URL'dagi host, username va portni aynan Supabase berganidek saqlang (odatda port 5432).

`render.yaml` boshlang'ich sozlamani beradi. Maxfiy qiymatlarni GitHub'ga yozmang.

## 4. Muhim xavfsizlik qoidalari

- AI faqat `needs_approval=false` bo'lgan javobni avtomatik yuboradi. Noma'lum yoki noto'g'ri formatdagi AI javobi tasdiqqa yuboriladi.
- Uchrashuv, to'lov, qarz, xarid, shaxsiy ma'lumot, sog'liq, huquqiy va boshqa nozik mavzular tasdiq talab qiladi.
- Bot egasi nomidan va'da yoki majburiyat bermasligi kerak.
- Telegram Business ruxsatlari va Telegram'ning oxirgi 24 soatlik javob berish cheklovlari amal qiladi.
- `.env`, tokenlar va API key'larni hech qachon commit qilmang.
- Suhbat xotirasi shaxsiy ma'lumotlarni o'z ichiga olishi mumkin; PostgreSQL'ga kirishni cheklang va kerak bo'lsa ma'lumotlarni o'chirish siyosatini qo'shing.
- Gemini API bepul tarifida so'rov limiti mavjud; limitlar model va hisobga qarab o'zgarishi mumkin. Google AI Studio bepul tarifida yuborilgan kontent mahsulotlarni yaxshilash uchun ishlatilishi mumkin.

## 5. Hozirgi cheklovlar

Bu birinchi MVP: hozircha faqat matnli Business xabarlar qayta ishlanadi. Rasm, ovoz, video, chat uchun alohida yoqish/o'chirish sozlamalari, xotirani tozalash, admin panelni kengaytirish va testlar keyingi bosqichlarda qo'shiladi.

## Admin buyruqlari

- `/start` — admin menyusi haqida ma'lumot
- `/stats` — xabarlar, suhbatlar va tasdiqlar statistikasi
- `/pending` — tasdiq kutayotgan oxirgi 10 ta javob

## Loyiha holati

Javob generatsiyasi Google Gemini API'ga o'tkazilgan. Production'da haqiqiy Telegram Business ulanishi, PostgreSQL va Gemini API kaliti bilan integratsion sinov o'tkazish kerak.
