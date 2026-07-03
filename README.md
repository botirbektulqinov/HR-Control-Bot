# HR Control Bot

Telegram bot: xodimlar **keldim/ketdim** qiladi, joylashuv (geofence) bilan
tasdiqlanadi; HR/admin bot ichidan statistika ko'radi va **Excel** hisobot oladi.

## Stack
aiogram 3 · SQLAlchemy 2 (async) · PostgreSQL · openpyxl · Docker.
Ortiqcha qatlamlar (DDD/CQRS/Celery/Redis) yo'q — kerak bo'lganda qo'shiladi.

## Ishga tushirish (Docker)
```bash
cp .env.example .env      # BOT_TOKEN va SUPER_ADMIN_IDS ni to'ldiring
docker compose up --build
```
Compose: `db` (Postgres) + `bot`. `bot` ishga tushganda jadval yaratadi va namuna
ma'lumot qo'shadi (`scripts/seed.py`, idempotent), keyin polling boshlaydi.

## Serverga joylash (deploy — Ubuntu + Docker)
Bot **polling** ishlaydi — ochiq port, domen yoki Nginx kerak emas.

```bash
# 1) Docker (agar yo'q bo'lsa)
curl -fsSL https://get.docker.com | sh

# 2) Kod
git clone https://github.com/botirbektulqinov/HR-Control-Bot.git
cd HR-Control-Bot

# 3) Sozlama — .env yarating (git'ga tushmaydi)
cp .env.example .env
nano .env        # BOT_TOKEN va SUPER_ADMIN_IDS ni to'ldiring

# 4) Ishga tushirish (fon rejimida, avto-restart)
docker compose up -d --build
docker compose logs -f bot      # tekshirish
```

Yangilash (kod o'zgarsa):
```bash
git pull && docker compose up -d --build
```
Xavfsizlik: `.env` va Postgres ma'lumotlari serverdan chiqmaydi (`.gitignore`,
`.dockerignore`; DB porti tashqariga ochilmagan). Ma'lumotlar `pgdata` volume'da
saqlanadi — `docker compose down` (`-v` siz) ularni o'chirmaydi.

## Lokal (Docker'siz)
```bash
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
# .env dagi DATABASE_URL host = localhost bo'lsin, Postgres ishlab tursin
python -m scripts.seed
python -m app.main
```

## Foydalanuvchi oqimi
1. `/start` → til (uz/ru/en) → **JSHSHIR** (14 raqam).
2. Bazadan xodim topiladi, Telegram ID bir marta bog'lanadi (qayta bog'lash faqat
   admin orqali — `🔗 Telegram uzish`).
3. Menyu: **🟢 Keldim / 🔴 Ketdim / 👤 Profil / 📅 Tarix**.
4. Keldim/Ketdim → joylashuv so'raladi → geofence + status hisoblanadi.

Test JSHSHIR (seed): `12345678901234`, `98765432109876` (HR).
Super admin: `.env` dagi `SUPER_ADMIN_IDS`.

## Joylashuvni tekshirish — halol chegara
Telegram fake-GPS'ni **100% to'xtata olmaydi** (root/emulyator). Amaliy himoya
qatlamlari (`app/services/location.py`, `LOCATION_STRICTNESS=strict|medium|light`):
geofence (radius) · eskirgan/forward joylashuvni rad etish · aniqlik tekshiruvi ·
live-location'ni afzal ko'rish. Kuchliroq kerak bo'lsa: selfie tasdiq,
IP-geolokatsiya, admin tasdiq oqimi (keyin qo'shiladi).

## Struktura
```
app/
  config.py            .env sozlamalari
  constants.py         Role/Status enumlar
  db/                  base (engine/Session) + models
  i18n/                uz/ru/en lug'at
  services/            geo, location(anti-spoof), attendance(status), punch, reports(excel), auth
  bot/
    keyboards, states, middlewares(session+auth)
    handlers/          start(onboarding), attendance, profile, admin
  main.py              entrypoint
scripts/seed.py        jadval + namuna ma'lumot
migrations/            Alembic (schema o'zgarganda: alembic revision --autogenerate)
```

## Self-check (framework yo'q)
```bash
python -m app.services.geo          # geofence masofasi
python -m app.services.attendance   # status hisoblash
```

## Keyingi qadamlar (kerak bo'lganda)
- Ish tugashidan oldin eslatma / kechikkanlarga HR alert (APScheduler).
- Xodimlarni Excel'dan ommaviy import.
- Bayram/ta'til kunlari jadvali.
- Selfie / admin tasdiq oqimi (shubhali yozuvlar).
- Alembic'da birinchi migratsiya (hozir dev'da `seed.py` create_all qiladi).
