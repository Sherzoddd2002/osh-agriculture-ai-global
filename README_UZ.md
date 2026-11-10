# O‘zbekiston dala ma’lumotlari va hosildorlik tahlili

**OSH Agriculture AI — Uzbekistan Edition** O‘zbekiston viloyatlari, tumanlari va foydalanuvchi chizgan dala poligonlarini yagona geografik identifikatorga bog‘laydi. Maqsad — xaritada butun mamlakatni ko‘rsatish emas, tanlangan dala uchun ma’lumot manbalarini, qamrovini va prognozga yaroqliligini alohida ko‘rsatish.

**[O‘zbekiston dashboard’ini ochish](https://sherzoddd2002.github.io/osh-agriculture-ai-global/)** · [GitHub repository](https://github.com/Sherzoddd2002/osh-agriculture-ai-global) · [Data manifest](docs/data/catalog.json)

## Mahsulot doirasi

- Mamlakat: **O‘zbekiston (ISO-3: UZB)**. Foydalanuvchi boshqa davlatga tasodifan o‘tib ketmaydi.
- ADM1: **14 ta hududiy birlik** uchun statik chegara snapshoti; manba geometriya yili **2017**.
- ADM2: **199 ta tuman/shahar** uchun statik chegara snapshoti; manba geometriya yili **2020**.
- Chuqurroq ADM3–ADM5 darajalari O‘zbekiston uchun tekshirilgan, to‘liq paket sifatida hozircha berilmaydi. Ularni interfeysda mavjud deb ko‘rsatmaymiz.
- Dala poligoni kamida uchta nuqta bilan chiziladi. Nuqta O‘zbekiston ADM1/ADM2 geometriyalari tashqarisida bo‘lsa, qabul qilinmaydi.
- Ochiq xarita va MAPSPAM 2020 bo‘yicha bitta poligonning zonal hisobi login talab qilmaydi; maydonni doimiy saqlash, shaxsiy hosil CSV va model joblari uchun hisob kerak.

**Chegara yili muhim:** 2017/2020 — ishlatilayotgan geometriya snapshotining manba vintage’i. Bu yilgi chegaralarni 2026-yilgi ma’muriy ro‘yxat bilan avtomatik bir xil deb hisoblamaymiz. Chegaraning nomi va identifikatori saqlanadi; statistik ma’lumot boshqa yil/vintage’dan bo‘lsa, farqi qayd etiladi.

## O‘zbekiston uchun ma’lumot manbalari

| Manba | Hozirgi qamrov / roli | Muhim cheklov |
|---|---|---|
| geoBoundaries | UZB ADM1 (14), ADM2 (199) | 2017/2020 geometriya vintage’i |
| SIAT rasmiy statistikasi | Bug‘doy, kartoshka, xom paxta; 2010–2024; 13 qishloq xo‘jaligi viloyati | Viloyat darajasi, tuman yoki dala kuzatuvi emas |
| FAOSTAT QCL | O‘zbekiston uchun milliy ekin statistikasi, agar bazada mavjud bo‘lsa | Milliy daraja; dala yoki tuman statistikasi emas |
| IFPRI MAPSPAM 2020 v2r2 | 46 ekin; O‘zbekiston hududi bo‘yicha raster zonal hisob | Taxminan 9,3 km; 2020-yil tarixiy bahosi, dala o‘lchovi emas |
| NASA POWER | Tarixiy meteorologik feature’lar | Hozirgi MVP vakillik nuqtasidan foydalanadi, butun poligon zonal o‘rtachasi emas |
| Open-Meteo | Joriy ob-havo va qisqa muddatli prognoz | Model prognozi; tarixiy kuzatuv yoki hosil o‘lchovi emas |
| Sentinel-2 / Copernicus | AOI bo‘yicha L2A sahna katalogi qidiruvi | NDVI/B04/B08 raster, cloud-shadow mask va mavsumiy zonal statistika hali to‘liq ulanmagan |
| Vazirlik geoaxborot tizimi va data.egov.uz | Ekin konturlari, hosil va qishloq xo‘jaligi suv ma’lumotlari uchun rasmiy kataloglar | Havola mavjudligi OSH bazasiga import qilingan degani emas; format, hudud kodi, davr va litsenziya alohida tekshiriladi |

**SIAT rasmiy viloyat qatorlari:** build jarayoni bug‘doy, kartoshka va xom paxta uchun ishlab chiqarish hajmini ekilgan maydonga bo‘lib, 2010–2024 yillik t/ha nisbatini tuzadi. SIAT’da ishlab chiqarish ming tonnada berilgan qatorlar tonnaga o‘tkaziladi. Natija — **ishlab chiqarish / ekilgan maydon**; hosil yig‘ib olingan maydonga nisbatan dala o‘lchovi emas. Hozirgi bundle 13 qishloq xo‘jaligi hududini o‘z ichiga oladi; Toshkent shahri va tuman darajasi bu hosildorlik qatorida yo‘q. Manbalar CC BY 4.0.

Rasmiy manbalar:
- [SIAT — bug‘doy yalpi hosili](https://siat.stat.uz/data/1458/) · [bug‘doy ekilgan maydoni](https://siat.stat.uz/data/2761/)
- [SIAT — kartoshka yalpi hosili](https://siat.stat.uz/data/323/) · [kartoshka ekilgan maydoni](https://siat.stat.uz/data/2040/)
- [SIAT — xom paxta yalpi hosili](https://siat.stat.uz/data/2389/) · [paxta ekilgan maydoni](https://siat.stat.uz/data/2039/)
- [Qishloq xo‘jaligi vazirligi geoaxborot tizimi](https://gov.uz/oz/agro/pages/geoaxborot-tizimi)
- [Ekin maydonlari konturlari](https://data.egov.uz/data/60faa9032a2e256d868e8245) · [hosil ma’lumotlari](https://data.egov.uz/data/6108023c2a2e256d868e879c) · [suv resurslari](https://data.egov.uz/data/610802fc2a2e256d868e87a1)

## Saytdan foydalanish oqimi

1. **O‘zbekiston xaritasi** ochiladi. ADM2 (tuman/shahar) yoki ADM1 (viloyat/respublika/Toshkent shahri) darajasini tanlang.
2. Viloyat/tumanni qidiruv maydonida yozib toping yoki xaritada belgilang.
3. O‘z dalangiz bo‘lsa, **Maydon chizish** tugmasini bosing; O‘zbekiston chegarasi ichida kamida uchta nuqta qo‘ying va **Tugatish**ni bosing.
4. Poligon geometriyasi, maydoni (ga), markaz koordinatasi va raster hisobining manbasi/holati ko‘rsatiladi.
5. Dala ekinini tanlang. MAPSPAM 2020 ochiq raster hisoboti shu poligon uchun avtomatik so‘raladi. Yaroqli raster katagi topilmasa, natija “ma’lumot yo‘q” bo‘lib qoladi; **0 hosil** deb talqin qilinmaydi.
6. Dala geometriyasini serverda saqlash va o‘zining kuzatilgan hosil tarixini ulash uchun hisobga kiring. CSV formati: `year,yield_t_ha`; ekin va mavsum bitta datasetga biriktiriladi.
7. Hosildorlik modeli faqat shu saqlangan dala + ekin datasetidagi haqiqiy kuzatuvlar va mos ob-havo feature’lari asosida ishlaydi. Hozirgi pipeline kamida 8 ta mos hosil yilini talab qiladi; aks holda model “yetarli kuzatuv yo‘q” deb to‘xtaydi.

## Dala modeli qanday talqin qilinadi?

- **Global/national reference**: FAOSTAT yoki MAPSPAM kabi katta hudud statistikasi — kontekst va baseline. Bu dalaning haqiqiy o‘lchovi emas.
- **Mahalliy viloyat qatori**: SIAT — bug‘doy, kartoshka va xom paxta bo‘yicha 13 qishloq xo‘jaligi viloyatining statistik nisbati. Uni tuman yoki kichik dalaga nusxalamaymiz.
- **Dala modeli**: foydalanuvchining aynan o‘sha dala uchun bir necha yillik haqiqiy hosil CSV’si bo‘lsa, vaqtli validatsiya qilinadi. Bunday kuzatuv bo‘lmasa, sun’iy “individual model” deb e’lon qilinmaydi.
- **Kelajak hosili**: kelajak ob-havosi hali kuzatilmagani uchun ssenariy farazi alohida ko‘rsatiladi; prognoz kuzatilgan fakt sifatida yozilmaydi.

## Hozirgi texnik holat

Frontend GitHub Pages’da, API FastAPI/Fly.io’da alohida ishlaydi. Public sahifa ochilishi backend, worker va PostgreSQL ishlayapti degani emas. AOI zonal tahlili uchun Fly API online bo‘lishi va serverda MAPSPAM COG raster fayllari mavjud bo‘lishi kerak. Fly deploy workflow hozircha `FLY_API_TOKEN` secret’iga bog‘liq; katta raster fayllar uchun persistent disk ham kerak. Health endpointda DB va worker holati tekshiriladi.

## Environmental connectorlar holati

- **Sentinel-2:** Copernicus STAC scene discovery ishlaydi. B04/B08 raster olish, SCL/CLD cloud-shadow mask, NDVI va mavsumiy zonal statistikalar hali bajarilmagan.
- **NASA SMAP:** SPL3SMP_E v6 daily 9 km mahsuloti mavjud; download uchun bepul NASA Earthdata Login, quality flag filtri va raster zonal adapter kerak. 9 km signal dala o‘lchovi emas.
- **SoilGrids:** 250 m global tuproq xaritalari va noaniqlik qatlamlari mavjud. ISRIC REST API pausada; WCS GetCoverage/WebDAV VRT orqali AOI subset va zonal-statistika adapteri hali kerak.

Texnik endpointlar, aniqlik va keyingi processing bosqichlari: [docs/ENVIRONMENT_CONNECTORS.md](docs/ENVIRONMENT_CONNECTORS.md).

## Ixtiyoriy: markaziy server — barcha foydalanuvchilar uchun bitta PostgreSQL

Agar barcha odamlarning ma’lumotlari sizning PostgreSQL serveringizga saqlanishi kerak bo‘lsa, lokal SQLite installer emas, markaziy server rejimini ishlating.

**Faqat PostgreSQL 17.11 ishlayotgan sizning Windows kompyuteringizda** (npm paketi e’lon qilingandan keyin):

```powershell
npx osh-agriculture-ai-global server-install
npx osh-agriculture-ai-global server-status
```

Bu rejim:
- mavjud `osh_agriculture_global` bazasiga `osh_global_app` roli orqali ulanadi;
- FastAPI web-server va background worker’ni ishga tushiradi;
- har bir akkauntning hududlari, datasetlari va job natijalarini markaziy PostgreSQL’ga saqlaydi;
- foydalanuvchilar orasida shaxsiy ma’lumotlarni account ownership orqali ajratadi.

Server boshqaruvi:

```powershell
npx osh-agriculture-ai-global server-start
npx osh-agriculture-ai-global server-status
npx osh-agriculture-ai-global server-stop
npx osh-agriculture-ai-global server-update
```

End users uchun bu buyruqlar kerak emas. Ular siz e’lon qilgan HTTPS sayt manziliga brauzerdan kiradi.

**Internetga chiqarish:** Cloudflare Tunnel orqali faqat `http://127.0.0.1:8080` ni e’lon qiling. PostgreSQL `5433` portini internetga ochmang. Vaqtinchalik Quick Tunnel faqat sinov uchun; doimiy domenli tunnel kerak. Batafsil: [docs/CENTRAL_WINDOWS_POSTGRES.md](docs/CENTRAL_WINDOWS_POSTGRES.md).

**Muhim:** barcha foydalanuvchilarning bazasi bitta bo‘lsa-da, hozirgi model tahlili har bir foydalanuvchining o‘z hosildorlik datasetida bajariladi. Boshqa foydalanuvchilar ma’lumotini global modelga qo‘shish rozilik, litsenziya va sifat tekshiruvi bilan alohida boshqarilishi kerak.

## Har bir foydalanuvchi o‘z kompyuterida (tavsiya etiladi)

Bu rejimda har bir odam dasturni GitHub'dan olib, o‘z kompyuterida ishga tushiradi. Fly.io, markaziy server, PostgreSQL yoki Docker shart emas.

**Talablar:** Node.js 20+, Python 3.11+ va birinchi o‘rnatish hamda tashqi ob-havo/chegara API'lari uchun internet.

Windows PowerShell:

```powershell
git clone https://github.com/Sherzoddd2002/osh-agriculture-ai-global.git
cd osh-agriculture-ai-global
.\ops\local.ps1 install
```

Yoki CLI'ni bevosita ishga tushiring:

```powershell
node .\bin\cli.js install
```

O‘rnatish tugagach brauzerda <http://127.0.0.1:8080> ochiladi. Web-server ishlayotgan paytda terminal oynasini yopmang.

Boshqarish:

```powershell
.\ops\local.ps1 start
.\ops\local.ps1 status
.\ops\local.ps1 stop
.\ops\local.ps1 update
```

CLI ma’lumotlarni foydalanuvchining o‘z kompyuterida saqlaydi:

- Windows: `%LOCALAPPDATA%\OSH\AgricultureAI\data\agriculture.sqlite3`
- macOS: `~/Library/Application Support/OSH/AgricultureAI/data/agriculture.sqlite3`
- Linux: `~/.local/share/osh-agriculture-ai-global/data/agriculture.sqlite3`

Har bir kompyuterning bazasi alohida. Bir odam yuklagan CSV yoki tahlil natijasi boshqa odamning kompyuteriga avtomatik o‘tmaydi. Server faqat `127.0.0.1` ga bog‘langan: boshqa kompyuterlardan unga kirib bo‘lmaydi.

**MAPSPAM bo‘yicha muhim eslatma:** ishlab chiquvchining PostgreSQL bazasiga import qilingan ADM0–ADM1 (109 112 qator) yangi lokal o‘rnatishga avtomatik ko‘chmaydi. Hozircha lokal o‘rnatish bo‘sh MAPSPAM jadvali yaratadi. MAPSPAM natijalarini barcha foydalanuvchilarga tarqatish uchun alohida, versiyalangan ma’lumotlar paketi va import buyrug‘i kerak bo‘ladi. GeoBoundaries, NASA POWER va Open-Meteo kabi tashqi manbalar esa internet orqali ishlaydi.

Boshqa odamlar bilan bitta umumiy ma’lumotlar bazasidan foydalanish kerak bo‘lsa, quyidagi markaziy server rejimini tanlang.

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

## GitHub manbasi

Loyihaning rasmiy public repository manzili: <https://github.com/Sherzoddd2002/osh-agriculture-ai-global>.

Yangi foydalanuvchilar yuqoridagi `git clone` buyrug‘i bilan kodni oladi. Mavjud clone'ni yangilash uchun:

```powershell
git pull --ff-only origin main
```

`.env`, foydalanuvchilarning CSV fayllari, maxfiy API keylar, SQLite bazalari va katta rastrlar GitHub’ga joylanmasligi kerak. Ular `.gitignore` bilan chiqarib tashlangan bo‘lsa ham, commit qilishdan oldin tekshiring.

