# OSH Agriculture AI — Global

**Dunyo bo‘yicha hudud tanlash, qishloq xo‘jaligi ma’lumotlarini birlashtirish va hosildorlikni prognozlash platformasi.**

Bu yangi global loyiha. U sizning mavjud `E:\OSH`, `osh` PostgreSQL bazangiz yoki O‘zbekiston uchun tayyorlangan eski CSV fayllaringizni o‘zgartirmaydi.

## Hozirgi relizda nima ishlaydi?

- Dunyo mamlakatlari uchun geoBoundaries API orqali ADM0–ADM5 ma’muriy chegaralarini qidirish.
- Xarita ustida Polygon/MultiPolygon hududini tanlash va PostGIS’ga saqlash.
- Hisob yaratish va kirish; yuklangan dataset foydalanuvchi hisobiga bog‘lanadi.
- CSV orqali tarixiy hosildorlik qatorlarini yuklash, yil/ustun/ekin mavsumi formatini tekshirish.
- NASA POWER daily API orqali tanlangan hududning vakillik nuqtasi uchun 2010-yildan boshlab yillik iqlim tarixini olish va SQL’ga yozish.
- Open-Meteo orqali joriy ob-havo hamda 16 kungacha qisqa muddatli prognozni olish va SQL’da saqlash.
- Hudud saqlanishi bilan, hosildorlik CSV bo‘lmasa ham, iqlim tahlili avtomatik navbatga tushadi.
- Ob-havoni foydalanuvchi ko‘rsatgan mavsum va hosil yili bilan birlashtirish.
- Background worker orqali uzoq davom etadigan ishlarni web so‘rovlaridan ajratish.
- Hosildorlik CSV yuklanganda ob-havo job’i avtomatik boshlanadi; kamida 8 ta moslangan haqiqiy hosil kuzatuvi va kamida 2 ta usable ob-havo feature bo‘lsa, Linear, Ridge, ElasticNet, Random Forest, Extra Trees va HistGradientBoosting modellarini expanding validation bilan baholaydi va Persistence benchmark bilan solishtiradi.
- Yetarli hosildorlik ma’lumoti bo‘lmasa, model prognozi yasamaydi; mavjud iqlim tarixi, joriy ob-havo va qisqa muddatli prognozni ko‘rsatadi.

## Hozircha ulanmagan manbalar

Sentinel-2 NDVI, SMAP va SoilGrids connector statuslari va integratsiya nuqtalari bor, ammo raster qidirish/yuklash, quality mask va poligon bo‘yicha zonal statistikalar hali ulanmagan. Sayt ularni tayyor ma’lumotdek ko‘rsatmaydi.

## Lokal ishga tushirish (Windows)

### One-command CLI (npm paket e’lon qilingandan keyin)

```powershell
npx osh-agriculture-ai-global install
```

Talablar: Node.js 20+, Python 3.11+ va internet. Lokal CLI har bir kompyuterda alohida SQLite baza yaratadi. Buyruq hozircha npm registry’ga publish qilinmagan; publish qilingach ishlaydi. Boshqa foydalanuvchilarning lokal bazalari sizning kompyuteringizdagi SQL bilan avtomatik birlashmaydi.

CLI boshqaruvi:

```powershell
npx osh-agriculture-ai-global start
npx osh-agriculture-ai-global status
npx osh-agriculture-ai-global stop
npx osh-agriculture-ai-global update
```

1. Docker Desktop o‘rnating va ishga tushiring.
2. Loyihaning asosiy papkasida PowerShell oching.
3. Quyidagilarni bajaring:

```powershell
Copy-Item .env.example .env
```

`.env` ichida `JWT_SECRET` qiymatini uzun, tasodifiy maxfiy kalitga almashtiring. So‘ng:

```powershell
docker compose up --build
```

Brauzer: <http://localhost:8080>

API hujjati: <http://localhost:8080/docs>

## CSV formati

```csv
year,yield_t_ha,area_ha,production_t
2015,4.12,12000,49440
2016,4.25,12100,51425
2017,3.98,11900,47362
```

`yield_t_ha` — t/ha bo‘lishi kerak. `area_ha` ustuni ixtiyoriy; uning ekilgan maydon yoki yig‘ib olingan maydon ekanini tanlash kerak. Har bir dataset ichida bitta hosil yiliga bitta qator qabul qilinadi.

## Ma’lumotlarni qayta ishlash ketma-ketligi

1. Hisob yarating yoki tizimga kiring.
2. Mamlakat ISO-3 kodini (masalan, `UZB`, `KAZ`, `DEU`) va ma’muriy darajani tanlang.
3. Chegaralarni yuklang va xaritada kerakli hududni bosing.
4. Hududni saqlang.
5. Hosildorlik CSV faylini va ustunlarini belgilang, ekin mavsumining boshlanish/tugash sanasini kiriting.
6. Datasetni yuklang. U SQL bazaga yoziladi va ob-havo bilan birlashtirish job’i avtomatik navbatga tushadi.
7. Job tugagach, qamrov va avtomatik model tahlilini ko‘ring. Yetarli tarix bo‘lmasa, model ishlatilmaydi va sabab ko‘rsatiladi.

## Juda muhim ilmiy cheklovlar

- NASA POWER bu MVP’da poligonning vakillik nuqtasidan olinadi; bu butun poligon maydoni bo‘yicha o‘rtacha ob-havo qiymati emas.
- NDVI, SMAP, SoilGrids hali amalda yig‘ilmaydi.
- Kelajak hosil yili uchun haqiqiy ob-havo hali mavjud bo‘lmasligi mumkin. Shunda model oxirgi 5 yillik mavsumiy ob-havo o‘rtachasidan scenario yaratadi va buni alohida belgilaydi.
- Bu bitta datasetga moslangan tadqiqot prognozi; global tasdiqlangan model emas.
- AI yaratgan hindcast/forecast qiymatlari kuzatilgan haqiqiy hosildorlik sifatida global modelga qayta berilmaydi.
- Global treningga qo‘shish roziligi alohida. Rozilikning o‘zi datasetni avtomatik tasdiqlamaydi; avval litsenziya, birlik, manba, vaqt qamrovi va sifat nazorati kerak.

## GitHub’ga yuborish

GitHub’da `osh-agriculture-ai-global` nomli yangi bo‘sh **Public repository** yarating. Keyin loyiha papkasida:

```powershell
git init
git add .
git commit -m "Initial OSH Agriculture AI Global foundation"
git branch -M main
git remote add origin https://github.com/Sherzoddd2002/osh-agriculture-ai-global.git
git push -u origin main
```

`.env`, foydalanuvchilar CSV fayllari, maxfiy API keylar va katta rastrlar `.gitignore` bilan chiqarib tashlangan. Yopiq ma’lumotlarni GitHub’ga qo‘ymang.

## Fly.io

Fly’da web va worker alohida process group bo‘lib ishlaydi. `fly.toml` web uchun autostop’ni o‘chiradi. Alohida managed PostgreSQL cluster yaratib, PostGIS yoqiladi; `DATABASE_URL` va `JWT_SECRET` secrets sifatida qo‘shiladi. Batafsil qadamlar `docs/FLY_DEPLOY.md` va `README.md` ichida.

**Doimiy ishlash xarajatsiz degani emas.** Fly Machines, Managed Postgres, storage va trafik pullik bo‘lishi mumkin. Avval kichik test muhiti va xarajat ogohlantirishlarini sozlang. Bitta server nol downtime kafolati emas.
