# Dunyo bo‘yicha hosil prognozi, NASA ma’lumotlari asosida

**OSH Agriculture AI Global** — MAPSPAM fazoviy ekin qatlamlari, global ma’muriy chegaralar, iqlim manbalari va hududiy AI research ssenariylarini birlashtiruvchi global agrar demo.

🌍 **[Global data dashboard’ni ochish](https://sherzoddd2002.github.io/osh-agriculture-ai-global/)** · [GitHub repository](https://github.com/Sherzoddd2002/osh-agriculture-ai-global) · [JSON data manifest](docs/data/catalog.json)

![OSH Agriculture AI Global — verified data dashboard](docs/assets/osh-global-preview.png)

[Qisqa demo: 3D globus, data archive va model laboratoriyasi](docs/assets/demo-walkthrough.gif)

## Public demo ma’lumotlar qamrovi · 2026-11-10

| Ochiq qatlam | Qamrov |
|---|---:|
| Global ma’muriy chegaralar | 245 mamlakat/hudud · ADM1 + ADM2 katalogi |
| IFPRI MAPSPAM 2020 v2r2 | 153 mamlakat · 46 ekin · 228,620 admin xulosasi |
| O‘zbekiston public reference | 14 viloyat · 199 tuman · 46 ekin |
| CROPGRIDS v1.08 katalogi | 173 ekin qatlami (public Pages prediction input emas) |

**Ilmiy aniqlik:** MAPSPAM 2020 — bitta reference yil va taxminan 9.3 km ekvivalent gridli fazoviy baho; joriy yil kuzatuvi, dala o‘lchovi yoki kelajak prognozi emas. FAOSTAT milliy statistikasi va boshqa ichki reference qatorlari ommaviy demo paketiga avtomatik chiqarilmaydi. NDVI/SMAP/SoilGrids raster feature’lari hozircha AI modeliga to‘liq ulanmagan.
---|---:|---|
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

## Hozirgi public global demo

Asosiy sayt GitHub Pages’da statik ishlaydi. U Fly.io, FastAPI yoki PostgreSQL API’siga ulanmaydi. GitHub Actions chegaralar va ruxsat berilgan statik data paketlarini tayyorlaydi.

- **Global xarita:** 245 mamlakat/hudud kodi uchun ADM1 va ADM2 statik chegaralari; faqat manbada mavjud poligonlar ko‘rsatiladi.
- **Hudud tanlash:** mamlakatni globusda bosish uning ADM qatlamini yuklaydi; viloyat/tuman poligonini bosish tanlangan hududni belgilaydi va iqlim, Sentinel-2 metadata hamda mavjud MAPSPAM 2020 ko‘rsatkichlarini avtomatik yuklaydi.
- **Maydon chizish:** foydalanuvchi xaritada o‘z dala poligonini chizishi mumkin. Bu custom maydonning o‘ziga xos yield statistikasi yo‘q bo‘lsa, tuman yoki viloyat natijasi unga ko‘chirib berilmaydi.
- **MAPSPAM 2020:** 46 ekin, 153 mamlakat, 2020-yil spatial reference. Bu bitta tarixiy yil; joriy hosil yoki kelajak prognozi emas. `NO_RASTER_CELLS` holatidagi yield NULL bo‘lib qoladi.
- **O‘zbekiston SIAT:** 2010–2024 viloyat qatorlaridan bug‘doy, kartoshka va xom paxta uchun ishlab chiqarish/ekilgan maydon nisbati. Tuman yoki dala o‘lchovi emas.
- **AI modeli:** Ridge research scenario + expanding-window OOF MAE va Persistence benchmark. Yetarli haqiqiy yield tarixi va mos ob-havo qatori bo‘lmasa, model prognoz bermasligi kerak. Barcha davlat va tumanlar uchun universal tasdiqlangan global model deb taqdim etilmaydi.
- **Global MAPSPAM paketlari:** hozircha O‘zbekiston paketi Pages’da tayyor. 153 mamlakat bo‘yicha ichki MAPSPAM summary arxivini public statik paketlarga chiqarish uchun maintainer lokal PostgreSQL’dan `python scripts/export_public_mapspam_global.py` eksportchini ishga tushiradi. Tekshirilgan `docs/data/mapspam/global/*.json.gz` paketlari keyin alohida commit qilinadi.

## Public Pages cheklovlari

GitHub Pages foydalanuvchi akkaunti, serverda saqlanadigan dataset, markaziy PostgreSQL yoki uzoq davom etadigan Python ML joblarini ishga tushirmaydi. Xarita/ma’lumot yuklash va Ridge CSV ssenariysi foydalanuvchi brauzerida bajariladi. Foydalanuvchi CSV fayli avtomatik serverga yuborilmaydi. Public sayt faqat litsenziyasi va manbasi ko‘rsatilgan, tarqatishga ruxsat berilgan statik aggregate ma’lumotlarni olishi kerak; xususiy DB yozuvlari, login ma’lumotlari va foydalanuvchi fayllari ommaviy paketga qo‘shilmaydi.
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

