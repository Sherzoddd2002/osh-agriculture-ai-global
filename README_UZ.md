# Dunyo bo‘yicha hosil prognozi, NASA ma’lumotlari asosida

**OSH Agriculture AI Global** — FAOSTAT tarixiy statistikasi, MAPSPAM fazoviy ekin qatlamlari, iqlim manbalari va ML tahlilini birlashtiruvchi global agrar research platforma.

🌍 **[Global data dashboard’ni ochish](https://sherzoddd2002.github.io/osh-agriculture-ai-global/)** · [GitHub repository](https://github.com/Sherzoddd2002/osh-agriculture-ai-global) · [JSON data manifest](docs/data/catalog.json)

![OSH Agriculture AI Global — verified data dashboard](docs/assets/osh-global-preview.png)

[Qisqa demo: 3D globus, data archive va model laboratoriyasi](docs/assets/demo-walkthrough.gif)

## Ma’lumotlar inventarizatsiyasi · 2026-11-08

| Arxiv | Bazadagi qatorlar | Qamrov |
|---|---:|---|
| FAOSTAT QCL | **610,299** | 1961–2024 · 202 mamlakat/hudud · 169 item kodi |
| IFPRI MAPSPAM 2020 v2r2 | **228,620** | 153 mamlakat · 46 ekin · ADM0/ADM1/ADM2 |
| **Jami** | **838,919** | Ikki alohida manbaning yozuvlari |

**Qo‘shimcha katalog:** CROPGRIDS v1.08 (2020) 173 ekin qatlamiga ega, lekin u markaziy reference bazaga import qilinmagan va yuqoridagi jami qatorlarga kiritilmagan.

> **Ilmiy aniqlik:** FAOSTAT QCL milliy darajadagi yillik statistika; tuman kuzatuvi emas. MAPSPAM 2020 — taxminan 9.3 km gridli bitta reference yil, joriy yil yoki dala o‘lchovi emas. NASA POWER tarixiy ob-havo feature manbasi; hosildorlik modelining o‘zi emas. Public dashboard markaziy PostgreSQL bazasining tekshirilgan inventarizatsiyasini ko‘rsatadi, lekin xom shaxsiy DB qatorlarini ommaga chiqarmaydi. Sentinel-2 STAC sahna qidiruvi ulangan, ammo NDVI raster hisoblanishi hali yo‘q. SMAP SPL3SMP_E v6 mahsuloti mavjud, lekin Earthdata Login va raster adapter kerak. SoilGrids REST API pausada; WCS/WebDAV orqali AOI raster adapteri hali yozilishi kerak.

---

> **Deploy:** GitHub Pages source `GitHub Actions` qilib sozlangach, `main` branchga merge/push qilingan o‘zgarishlar saytni avtomatik yangilaydi. Deployment holati repository’ning **Actions** bo‘limida ko‘rinadi. Sayt manzili: https://sherzoddd2002.github.io/osh-agriculture-ai-global/ .

## Ochiq demo va loyiha haqida

**Dunyo bo‘yicha hudud tanlash, qishloq xo‘jaligi ma’lumotlarini birlashtirish va hosildorlikni prognozlash platformasi.**

Bu yangi global loyiha. U sizning mavjud `E:\OSH`, `osh` PostgreSQL bazangiz yoki O‘zbekiston uchun tayyorlangan eski CSV fayllaringizni o‘zgartirmaydi.

## Hozirgi public relizda nima ishlaydi?

Public sayt **GitHub Pages + GitHub Actions** asosida ishlaydi. Saytni ochgan odamga Python, PostgreSQL yoki alohida server kerak emas.

- Global 3D xaritada mamlakatlar ko‘rinadi va tanlanadi.
- Global statik paketda avval geoBoundaries `gbOpen` mamlakat chegaralari ishlatiladi; yetishmayotgan ADM1/ADM2 qatlamlari World Bank Official Boundaries (WB-GAD) manbasidan to‘ldiriladi. Har bir mamlakat uchun faqat tanlangan ma’muriy darajadagi GeoJSON yuklanadi. Har bir paketda manba, chegaraning yili va CC BY 4.0 litsenziya ma’lumoti saqlanadi. O‘zbekistonning **14 ta ADM1 viloyati** va **199 ta ADM2 tumani** MAPSPAM `shapeID` bog‘lanishini saqlash uchun alohida tekshirilgan paket sifatida qoladi. Hozirgi paketda global manbalardan **245 ta mamlakat/hudud kodi** uchun ADM1 va ADM2 mavjud; bu son har bir yangilanishda qayta tekshiriladi.
- Maydon chizish vositasi bilan xaritada o‘zingizning Polygon hududingizni chizishingiz mumkin.
- Tanlangan hudud markazining taxminiy koordinatasi bo‘yicha Open-Meteo ERA5-Land tarixiy ob-havo qatori va 7 kunlik ob-havo ma’lumoti olinadi. Bu poligon bo‘yicha zonal o‘rtacha emas.
- Copernicus STAC orqali so‘nggi 12 oydagi Sentinel-2 L2A sahnalari (bulutlilik ≤30%) qidiriladi. Bu hozircha scene metadata; NDVI rasteri hisoblanmaydi.
- MAPSPAM katalogidagi **46 ta ekin** to‘liq tanlanadi va qidiriladi.
- MAPSPAM 2020 v2r2 bo‘yicha **14 viloyat × 46 ekin** va **199 tuman × 46 ekin** tarixiy fazoviy reference qiymatlari xaritada tanlangan hududga bog‘langan holda ko‘rsatiladi. Bog‘lanish aniq `shapeID` orqali; raster katagi mavjud bo‘lmagan kombinatsiya `NULL` bo‘lib qoladi.
- Haqiqiy `year,yield_t_ha` CSV fayl brauzerda o‘qiladi. Ridge + ERA5-Land modeli expanding-window OOF natijalarini Persistence benchmark bilan taqqoslaydi. CSV serverga yuborilmaydi.
- Viloyat (ADM1) uchun SIAT’ning 2010–2024 yillik rasmiy statistikasi asosida bug‘doy, kartoshka va xom paxta bo‘yicha avtomatik model ssenariysi mavjud. Hisob `ishlab chiqarish / ekilgan maydon` nisbati (t/ha); bu tuman yoki dala kuzatuvi emas.

## Public demo: tuman va dala tahlili

[Dashboard’ni oching](https://sherzoddd2002.github.io/osh-agriculture-ai-global/) → **Maydon tahlili** bo‘limiga o‘ting.

1. Sayt ochilganda O‘zbekiston **ADM2 · Tumanlar** qatlami avtomatik yuklanadi (199 ta tuman). Boshqa mamlakatni xaritada bosing yoki ISO-3 kodini (masalan, `KAZ`, `DEU`, `USA`) kiriting, so‘ng ADM1/ADM2 qatlamini yuklang.
2. Viloyat kesimiga o‘tish uchun **ADM1 · Viloyatlar** ni tanlang va **Chegaralarni yuklash** tugmasini bosing (14 ta viloyat). Tuman qatlamiga qaytish ham shu usulda bajariladi.
3. **Hududni tahlil qilish** orqali tarixiy ERA5-Land ob-havo qatori va 7 kunlik prognozni oling; Sentinel-2 sahnalari alohida ko‘rsatiladi.
4. Shu natijalar ichida tanlangan tuman/viloyat va 46 ekindan biri uchun **MAPSPAM 2020** hosildorlik, ishlab chiqarish, fizik/yig‘ib olingan maydon hamda yaroqli raster kataklari ko‘rinadi. `NO_RASTER_CELLS` holatida yield `NULL` bo‘ladi; 0 deb ko‘rsatilmaydi.
5. Viloyat (ADM1) tanlanganda bug‘doy, kartoshka yoki xom paxta uchun SIAT 2010–2024 qatori avtomatik ishlaydi. U boshqa ekin yoki tuman uchun ko‘chirilmaydi.
6. Boshqa hudud/ekin juftligi uchun aynan shu joy va ekinga tegishli haqiqiy `year,yield_t_ha` CSV faylini yuklang; shablonni **CSV shablon** havolasidan oling. Kamida 8 ta mos yield-yil va yetarli ob-havo qamrovi kerak.

**MAPSPAM 2020 va AI bashorati farqi:** MAPSPAM paneli — 2020-yil uchun 5 arc-minute (~9.3 km ekvatorda) rasterdan yig‘ilgan tarixiy fazoviy baho; u kelajak prognozi, joriy yil kuzatuvi yoki dala o‘lchovi emas. 199 tuman va 14 viloyat bo‘yicha 46 crop qatlamining mavjudligi har bir kombinatsiyada yaroqli katak borligini anglatmaydi. 

**SIAT viloyat ko‘rsatkichlari:** bug‘doy, kartoshka va xom paxta uchun yillik ishlab chiqarish `ming tonna`dan tonnaga o‘tkazilib, ekilgan maydonga (gektar) bo‘linadi. Natija — viloyat bo‘yicha ishlab chiqarish/ekilgan maydon nisbati; hosil yig‘ilgan maydonga asoslangan alohida dala hosildorligi yoki tuman kuzatuvi deb talqin qilinmasin. SIAT avtomatik qatori Toshkent shahri va tumanlar uchun berilmaydi. Manbalar CC BY 4.0.

**AI bashorati haqida:** bu oldindan tayyorlab qo‘yilgan, barcha tumanlar uchun bir xil qiymat qaytaradigan model emas. U aynan foydalanuvchi yuklagan hudud/ekin tarixiy hosildorlik qatorini ERA5-Land feature’lari bilan birlashtiradi. Kelajak ob-havosi mavjud bo‘lmagani uchun so‘nggi 5 mos mavsumning normasi ishlatiladi. Natija research scenario; O‘zbekistonning barcha tumanlari bo‘yicha mustaqil tasdiqlangan universal prognoz deb talqin qilinmasin. OOF MAE va Persistence benchmark natijalari bashorat bilan birga ko‘rsatiladi.

**Public Pages cheklovlari:** GitHub Pages statik hosting hisoblanadi. U foydalanuvchi loginini, serverda saqlanadigan AOI/datasetlarni yoki markaziy PostgreSQL yozuvlarini bermaydi. Maydon poligoni faqat joriy brauzer sessiyasida turadi. Public dashboard markaziy bazadagi 838,919 qator inventarizatsiya metama’lumotini ko‘rsatadi, shuningdek alohida ochiq manbadagi MAPSPAM 2020 UZB ADM1/ADM2 reference paketini (9,798 admin × crop yozuv) ommaga beradi; maxfiy markaziy PostgreSQL xom qatorlari va foydalanuvchi CSV fayllari tarqatilmaydi. GeoBoundaries chegaralari GitHub Actions build vaqtida yuklanib, sayt fayllari tarkibiga kiritiladi — tashrif buyuruvchining brauzeri Fly/FastAPI API’siga murojaat qilmaydi.

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

