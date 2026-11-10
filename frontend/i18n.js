(() => {
  "use strict";

  const translations = [
    ["Bosh sahifa", "Home", "Главная"],
    ["Hududiy tahlil", "Regional analysis", "Региональный анализ"],
    ["Hosildorlik prognozi", "Yield forecast", "Прогноз урожайности"],
    ["Model laboratoriyasi", "Model laboratory", "Лаборатория моделей"],
    ["Iqlim va tuproq", "Climate & soil", "Климат и почва"],
    ["Ma’lumotlar va hisobotlar", "Data & reports", "Данные и отчёты"],
    ["O‘zbekiston xaritasi", "Uzbekistan map", "Карта Узбекистана"],
    ["O‘zbekiston · viloyatdan dalagacha", "Uzbekistan · from province to field", "Узбекистан · от области до поля"],
    ["Viloyat, tuman yoki o‘z dalangizni tanlang", "Choose a province, district, or your own field", "Выберите область, район или своё поле"],
    ["O‘zbekiston Respublikasi", "Republic of Uzbekistan", "Республика Узбекистан"],
    ["Viloyat / tuman qidirish", "Search province / district", "Поиск области / района"],
    ["Hududni ro‘yxatdan tanlang", "Choose an area from the list", "Выберите территорию из списка"],
    ["Viloyat / respublika / Toshkent shahri", "Province / republic / Tashkent city", "Область / республика / город Ташкент"],
    ["Tuman va shahar", "District and city", "Район и город"],
    ["O‘zbekiston ADM1/ADM2 chegaralari tekshirilmoqda…", "Checking Uzbekistan ADM1/ADM2 boundaries…", "Проверка границ ADM1/ADM2 Узбекистана…"],
    ["SIAT · RASMIY STATISTIKA", "SIAT · OFFICIAL STATISTICS", "SIAT · ОФИЦИАЛЬНАЯ СТАТИСТИКА"],
    ["Viloyatlar bo‘yicha rasmiy hosildorlik manbalari", "Official provincial yield sources", "Официальные источники урожайности по областям"],
    ["Bug‘doy", "Wheat", "Пшеница"],
    ["Kartoshka", "Potato", "Картофель"],
    ["Xom paxta", "Seed cotton", "Хлопок-сырец"],
    ["O‘zbekistonning mahalliy geoma’lumot manbalari", "Uzbekistan local geospatial data sources", "Местные геоданные Узбекистана"],
    ["Vazirlik geoaxborot tizimi", "Ministry geospatial portal", "Геоинформационный портал министерства"],
    ["Ochiq ma’lumotlar reyestri", "Open data registry", "Реестр открытых данных"],
    ["Rasmiy statistika va dala ma’lumotlari", "Official statistics and field data", "Официальная статистика и полевые данные"],
    ["O‘zbekiston · FAOSTAT tarixiy qatori", "Uzbekistan · FAOSTAT historical series", "Узбекистан · исторический ряд FAOSTAT"],
    ["Rasmiy SIAT viloyat qatori yuklanmoqda…", "Loading official SIAT provincial series…", "Загрузка официальных областных рядов SIAT…"],
    ["SIAT viloyat snapshoti hozircha yuklanmadi.", "The SIAT provincial snapshot is not available yet.", "Областной снимок SIAT пока недоступен."],
    ["Ekin", "Crop", "Культура"],
    ["Yil", "Year", "Год"],
    ["Hosildorlik (t/ga)", "Yield (t/ha)", "Урожайность (т/га)"],
    ["Yalpi hosil (t)", "Gross production (t)", "Валовой сбор (т)"],
    ["Ekilgan maydon (ga)", "Sown area (ha)", "Посевная площадь (га)"],
    ["Bu viloyat statistik nisbati, dala o‘lchovi emas.", "This is a provincial statistical ratio, not a field measurement.", "Это областной статистический показатель, а не измерение на поле."],
    ["Dala konturini O‘zbekiston ichida chizing.", "Draw the field boundary inside Uzbekistan.", "Нарисуйте контур поля внутри Узбекистана."],
    ["O‘zbekiston bazaviy xaritasi", "Uzbekistan base map", "Базовая карта Узбекистана"],
    ["O‘zbekiston xaritasini ochish", "Open Uzbekistan map", "Открыть карту Узбекистана"],
    ["Global qishloq xo‘jaligi", "Global agriculture", "Глобальное сельское хозяйство"],
    ["Ma’lumotga asoslangan qarorlar", "Data-driven decisions", "Решения на основе данных"],
    ["Server tekshirilmoqda", "Checking server", "Проверка сервера"],
    ["Server ulanmagan", "Server offline", "Сервер не подключён"],
    ["Kirish", "Sign in", "Войти"],
    ["Mehmon rejimi", "Guest mode", "Гостевой режим"],
    ["Yer ma’lumotlari.", "Land data.", "Данные о земле."],
    ["Hosildorlik aql bilan.", "Smarter yields.", "Урожайность с помощью ИИ."],
    ["Dunyo bo‘yicha hududni tanlang, tarixiy ma’lumotlaringizni yuklang va iqlim bilan birlashtirib tahlil qiling.", "Select a region anywhere in the world, upload historical data, and combine it with climate information for analysis.", "Выберите регион в любой точке мира, загрузите исторические данные и объедините их с климатической информацией для анализа."],
    ["Hudud tanlash", "Select region", "Выбрать регион"],
    ["Environmental manbalar", "Environmental sources", "Источники экологических данных"],
    ["Global hudud qamrovi", "Global geographic coverage", "Глобальный охват территорий"],
    ["Mamlakatga qarab mavjud daraja", "Available levels vary by country", "Доступные уровни зависят от страны"],
    ["Ob-havo pipeline", "Weather pipeline", "Погодный конвейер данных"],
    ["Faol", "Active", "Активен"],
    ["AI holati", "AI status", "Статус ИИ"],
    ["Tadqiqot", "Research", "Исследование"],
    ["Global model hali tasdiqlanmagan", "Global model not yet validated", "Глобальная модель ещё не прошла проверку"],
    ["ISH JARAYONI", "WORKFLOW", "ПРОЦЕСС РАБОТЫ"],
    ["Hududingizdan prognozgacha", "From your region to a forecast", "От вашего региона к прогнозу"],
    ["Hududni tanlang", "Select a region", "Выберите регион"],
    ["Dunyo xaritasidan mamlakat va ma’muriy hududni belgilang.", "Choose a country and administrative area on the world map.", "Выберите страну и административную территорию на карте мира."],
    ["Ma’lumot yuklang", "Upload data", "Загрузите данные"],
    ["Hosildorlik va ekin maydonining tarixiy qatorini CSV orqali kiriting.", "Upload historical yield and crop-area records as a CSV file.", "Загрузите исторические данные об урожайности и посевных площадях в формате CSV."],
    ["NASA POWER ob-havosi avtomatik yig‘iladi; boshqa qatlamlar qamrovi alohida tekshiriladi.", "NASA POWER weather data is collected automatically; coverage of other layers is checked separately.", "Погодные данные NASA POWER собираются автоматически; охват остальных слоёв проверяется отдельно."],
    ["AI tahlil", "AI analysis", "Анализ ИИ"],
    ["Vaqt bo‘yicha validatsiya, Persistence benchmark va prognoz ssenariysi.", "Time-based validation, a persistence benchmark, and a forecast scenario.", "Временная проверка, базовый прогноз Persistence и сценарий прогноза."],
    ["Ilmiy aniqlik:", "Scientific note:", "Научное примечание:"],
    ["hozirgi MVP ob-havoni tanlangan poligonning vakillik nuqtasidan oladi. Bu butun dala yoki poligon bo‘yicha zonal o‘rtacha emas. NDVI, SMAP va SoilGrids ulanishi keyingi connector bosqichida yoqiladi.", "the current MVP retrieves weather for a representative point in the selected polygon. This is not a zonal average for the entire field or polygon. NDVI, SMAP, and SoilGrids connectors will be enabled in a later stage.", "текущая MVP-версия получает погоду для репрезентативной точки выбранного полигона. Это не зональное среднее по всему полю или полигону. Подключение NDVI, SMAP и SoilGrids будет добавлено на следующем этапе."],
    ["Hududiy tahlil", "Regional analysis", "Региональный анализ"],
    ["Mamlakat va ma’muriy darajani tanlang. Chegaralar geoBoundaries manbasidan olinadi; xarita kattalashtiriladi va suriladi.", "Select a country and administrative level. Boundaries come from geoBoundaries; the map can be zoomed and panned.", "Выберите страну и административный уровень. Границы загружаются из geoBoundaries; карту можно масштабировать и перемещать."],
    ["Mamlakat ISO-3", "Country ISO-3", "Страна ISO-3"],
    ["Ma’muriy daraja", "Administrative level", "Административный уровень"],
    ["Chegaralarni yuklash", "Load boundaries", "Загрузить границы"],
    ["Mamlakatni kiriting", "Enter a country", "Введите страну"],
    ["Dunyo xaritasi", "World map", "Карта мира"],
    ["Hudud tanlanmagan", "No region selected", "Регион не выбран"],
    ["Xarita: CARTO / OpenStreetMap. Ma’muriy chegara: geoBoundaries gbOpen. Har bir boundary metadata va litsenziyasi bo‘yicha tekshirilishi kerak.", "Map: CARTO / OpenStreetMap. Administrative boundaries: geoBoundaries gbOpen. Each boundary must be checked for metadata and licensing.", "Карта: CARTO / OpenStreetMap. Административные границы: geoBoundaries gbOpen. Метаданные и лицензия каждой границы должны быть проверены."],
    ["TANLANGAN HUDUD", "SELECTED REGION", "ВЫБРАННЫЙ РЕГИОН"],
    ["Xaritadagi chegarani bosing.", "Click a boundary on the map.", "Нажмите на границу на карте."],
    ["Mamlakat", "Country", "Страна"],
    ["Daraja", "Level", "Уровень"],
    ["Markaz koordinatasi", "Center coordinates", "Координаты центра"],
    ["Tarixiy ma’lumot boshlanish yili", "Historical data start year", "Начальный год исторических данных"],
    ["Hududni saqlash va tahlil qilish", "Save region and analyze", "Сохранить регион и проанализировать"],
    ["Hosildorlik CSV bo‘lmasa ham iqlim tarixi va ob-havo prognozi olinadi. Model faqat haqiqiy hosildorlik ma’lumoti bo‘lganda ishlaydi.", "Climate history and weather forecasts are available even without a yield CSV. The model runs only when observed yield data is available.", "История климата и прогноз погоды доступны и без CSV урожайности. Модель работает только при наличии фактических данных об урожайности."],
    ["REGIONAL CLIMATE INTELLIGENCE", "REGIONAL CLIMATE INTELLIGENCE", "РЕГИОНАЛЬНАЯ КЛИМАТИЧЕСКАЯ АНАЛИТИКА"],
    ["Hudud iqlim tahlili", "Regional climate analysis", "Климатический анализ региона"],
    ["Yillik tarixiy ko‘rsatkichlar, joriy ob-havo va qisqa muddatli prognoz.", "Annual historical indicators, current weather, and a short-term forecast.", "Годовые исторические показатели, текущая погода и краткосрочный прогноз."],
    ["Ma’lumot kutilmoqda", "Waiting for data", "Ожидание данных"],
    ["Hosildorlik ma’lumoti bo‘lmasa, model prognozi hisoblanmaydi.", "The model forecast is not calculated without yield data.", "Без данных об урожайности прогноз модели не рассчитывается."],
    ["Yaqin kunlar prognozi", "Short-term forecast", "Прогноз на ближайшие дни"],
    ["Model prognozi · kuzatuv emas", "Model forecast · not an observation", "Прогноз модели · не наблюдение"],
    ["16 kungacha", "Up to 16 days", "До 16 дней"],
    ["Prognoz kutilmoqda", "Forecast pending", "Ожидание прогноза"],
    ["Yillik iqlim tarixi", "Annual climate history", "Годовая история климата"],
    ["Temp. o‘rtacha", "Mean temperature", "Средняя температура"],
    ["Yog‘in", "Precipitation", "Осадки"],
    ["Issiq kun", "Hot days", "Жаркие дни"],
    ["Sovuq kun", "Frost days", "Холодные дни"],
    ["Qamrov", "Coverage", "Охват"],
    ["Eslatma:", "Note:", "Примечание:"],
    ["NASA POWER tarixiy qiymatlari hudud poligonidagi vakillik nuqtasi bo‘yicha. Bu butun tuman yoki dala uchun zonal o‘rtacha emas. Open-Meteo prognozi esa ob-havo modelining taxmini.", "NASA POWER historical values represent a point within the selected polygon, not a zonal average for the whole district or field. Open-Meteo is a weather-model forecast.", "Исторические значения NASA POWER относятся к репрезентативной точке внутри полигона, а не к зональному среднему по всему району или полю. Open-Meteo предоставляет прогноз погодной модели."],
    ["Hosildorlik ma’lumotingiz bormi?", "Do you have yield data?", "У вас есть данные об урожайности?"],
    ["Bo‘lsa, CSV yuklang. Bo‘lmasa, yuqoridagi iqlim panelidan foydalanishingiz mumkin.", "Upload a CSV if you do. Otherwise, you can use the climate panel above.", "Загрузите CSV, если они есть. В противном случае используйте климатическую панель выше."],
    ["Keyingi qadam: hosildorlik ma’lumotini yuklash", "Next step: upload yield data", "Следующий шаг: загрузить данные об урожайности"],
    ["Avval yuqorida hududni saqlang, so‘ng CSV faylni tanlang.", "First save a region above, then choose a CSV file.", "Сначала сохраните регион выше, затем выберите CSV-файл."],
    ["Saqlangan hudud", "Saved region", "Сохранённый регион"],
    ["Avval xaritada hududni saqlang", "Save a region on the map first", "Сначала сохраните регион на карте"],
    ["Ekin kodi", "Crop code", "Код культуры"],
    ["Hosil mavsumi boshlanishi", "Crop season start", "Начало сельхозсезона"],
    ["Hosil mavsumi tugashi", "Crop season end", "Окончание сельхозсезона"],
    ["Yil ustuni", "Year column", "Столбец года"],
    ["Hosildorlik ustuni", "Yield column", "Столбец урожайности"],
    ["Maydon ustuni (ixtiyoriy)", "Area column (optional)", "Столбец площади (необязательно)"],
    ["Maydon ta’rifi", "Area definition", "Тип площади"],
    ["Noma’lum", "Unknown", "Неизвестно"],
    ["Ekilgan maydon", "Sown area", "Посевная площадь"],
    ["Yig‘ib olingan maydon", "Harvested area", "Убранная площадь"],
    ["CSV fayl tanlash", "Choose CSV file", "Выбрать CSV-файл"],
    ["Datasetimni sifat tekshiruvidan keyin global model tadqiqotida ishlatishga roziman (ixtiyoriy).", "I agree to allow my dataset to be used in global model research after quality checks (optional).", "Я согласен(на) разрешить использование моего набора данных в исследованиях глобальной модели после проверки качества (необязательно)."],
    ["Datasetni tekshirish va yuklash", "Validate and upload dataset", "Проверить и загрузить набор данных"],
    ["Avtomatik tahlil navbatga qo‘yildi", "Automatic analysis queued", "Автоматический анализ добавлен в очередь"],
    ["Hosildorlik prognozi", "Yield forecast", "Прогноз урожайности"],
    ["Tanlangan dataset bo‘yicha tarixiy ob-havo feature'lari bilan vaqtli validatsiya va tadqiqot ssenariysi.", "Time-based validation and a research scenario using historical weather features for the selected dataset.", "Временная проверка и исследовательский сценарий с историческими погодными признаками для выбранного набора данных."],
    ["Dataset", "Dataset", "Набор данных"],
    ["Dataset yuklang", "Upload a dataset", "Загрузите набор данных"],
    ["Maqsadli yil", "Target year", "Целевой год"],
    ["Model", "Model", "Модель"],
    ["Eng yaxshi OOF varianti", "Best OOF option", "Лучший вариант OOF"],
    ["AI prognozini hisoblash", "Run AI forecast", "Рассчитать прогноз ИИ"],
    ["Prognoz uchun datasetni tanlang va environmental processing tugaganini tekshiring.", "Select a dataset and make sure environmental processing is complete before forecasting.", "Выберите набор данных и убедитесь, что обработка экологических данных завершена."],
    ["Model laboratoriyasi", "Model laboratory", "Лаборатория моделей"],
    ["Har bir model faqat bir xil vaqtli validation qatorlarida solishtiriladi. Persistence benchmark doim ko‘rsatiladi.", "Models are compared on the same time-based validation rows. The persistence benchmark is always included.", "Модели сравниваются на одинаковых временных выборках валидации. Базовый прогноз Persistence показывается всегда."],
    ["Model baholash qoidalari", "Model evaluation rules", "Правила оценки моделей"],
    ["Chiziqli challengerlar", "Linear challengers", "Линейные модели-кандидаты"],
    ["Tree ensemble challengerlar", "Tree-ensemble challengers", "Ансамблевые модели деревьев"],
    ["Boosting challenger", "Boosting challenger", "Модель бустинга"],
    ["O‘tgan yilgi hosildorlik benchmarki", "Previous-year yield benchmark", "Базовый уровень: урожайность прошлого года"],
    ["Bu boshlang‘ich lokal-model laboratoriyasi. Ko‘p mamlakatlar bo‘yicha tasdiqlangan global model keyinchalik country-held-out va future-year testlardan o‘tgandan keyingina “global valid” deb belgilanadi.", "This is an initial local-model laboratory. A global model will be labelled “globally validated” only after passing country-held-out and future-year tests across multiple countries.", "Это начальная лаборатория локальных моделей. Глобальная модель получит статус «глобально проверена» только после тестов с исключением стран и проверкой на будущих годах."],
    ["Iqlim va tuproq", "Climate & soil", "Климат и почва"],
    ["Har bir manbaning real ulanish holati, qamrovi va cheklovi ko‘rsatiladi.", "The live connection status, coverage, and limitations of each source are shown.", "Показываются состояние подключения, охват и ограничения каждого источника."],
    ["Manbalar tekshirilmoqda…", "Checking data sources…", "Проверка источников данных…"],
    ["Ma’lumotlar va hisobotlar", "Data & reports", "Данные и отчёты"],
    ["Yuklangan datasetlar, yillar qamrovi, ob-havo integratsiyasi va processing job holati.", "Uploaded datasets, year coverage, weather integration, and processing job status.", "Загруженные наборы данных, охват по годам, интеграция погоды и статус фоновых задач."],
    ["FAOSTAT tarixiy ekinlar bazasi", "FAOSTAT historical crop database", "Историческая база культур FAOSTAT"],
    ["Yangilash", "Refresh", "Обновить"],
    ["FAOSTAT QCL · alohida ekinlar, yig‘ma agregatlar va mahsulot shakllari alohida tasniflanadi. Mavjud yillar mamlakat va itemga qarab farq qiladi. Bu tarixiy kuzatuv, prognoz emas.", "FAOSTAT QCL · individual crops, aggregate groups, and product forms are classified separately. Available years vary by country and item. These are historical observations, not forecasts.", "FAOSTAT QCL · отдельные культуры, агрегированные группы и формы продукции классифицируются отдельно. Доступные годы зависят от страны и позиции. Это исторические наблюдения, а не прогноз."],
    ["Mamlakat / hudud", "Country / area", "Страна / территория"],
    ["Yuklanmoqda…", "Loading…", "Загрузка…"],
    ["Ma’lumot turi", "Data type", "Тип данных"],
    ["Alohida ekinlar", "Individual crops", "Отдельные культуры"],
    ["Yig‘ma ko‘rsatkichlar", "Aggregate indicators", "Сводные показатели"],
    ["Mahsulot shakllari", "Product forms", "Формы продукции"],
    ["Barchasi", "All", "Все"],
    ["Ekin / mahsulot", "Crop / product", "Культура / продукт"],
    ["Boshlanish yili", "Start year", "Начальный год"],
    ["Tugash yili", "End year", "Конечный год"],
    ["Tarixiy ma’lumotni ko‘rsatish", "Show historical data", "Показать исторические данные"],
    ["Hosildorlik trend ssenariysi", "Yield trend scenario", "Сценарий тренда урожайности"],
    ["Global FAOSTAT katalogi yuklanmoqda…", "Loading global FAOSTAT catalogue…", "Загрузка глобального каталога FAOSTAT…"],
    ["Mening datasetlarim", "My datasets", "Мои наборы данных"],
    ["Hisobga kiring va dataset yuklang.", "Sign in and upload a dataset.", "Войдите и загрузите набор данных."],
    ["So‘nggi background job", "Latest background job", "Последняя фоновая задача"],
    ["Hozircha job yo‘q.", "No jobs yet.", "Пока нет задач."],
    ["Datasetlar shaxsiy hisobga biriktiriladi.", "Datasets are linked to your personal account.", "Наборы данных привязываются к вашей учётной записи."],
    ["Parol", "Password", "Пароль"],
    ["Kamida 10 belgi", "At least 10 characters", "Не менее 10 символов"],
    ["Ro‘yxatdan o‘tish", "Create account", "Зарегистрироваться"],
    ["Hudud saqlanmoqda va iqlim tahlili navbatga qo‘yilmoqda…", "Saving region and queueing climate analysis…", "Сохранение региона и добавление климатического анализа в очередь…"],
    ["Hudud saqlandi", "Region saved", "Регион сохранён"],
    ["Hudud saqlandi ·", "Region saved ·", "Регион сохранён ·"],
    ["Chegaralar olinmoqda…", "Loading boundaries…", "Загрузка границ…"],
    ["Chegaralarni yuklash", "Load boundaries", "Загрузить границы"],
    ["Xarita kutubxonasi yuklanmadi. Internetni tekshiring.", "The map library failed to load. Check your internet connection.", "Не удалось загрузить библиотеку карт. Проверьте подключение к интернету."],
    ["Tanlangan chegara geoBoundaries GeoJSON polygonidan olindi.", "The selected boundary comes from a geoBoundaries GeoJSON polygon.", "Выбранная граница получена из полигона GeoJSON geoBoundaries."],
    ["Chegaralar olinmoqda", "Loading boundaries", "Загрузка границ"],
    ["ta chegara yuklandi", "boundaries loaded", "границ загружено"],
    ["Yillik iqlim job", "Annual climate job", "Задача годового климатического анализа"],
    ["boshlandi.", "started.", "запущена."],
    ["Iqlim tahlili xatosi:", "Climate analysis error:", "Ошибка климатического анализа:"],
    ["Yillik iqlim ma’lumoti hali olinmagan.", "Annual climate data has not been retrieved yet.", "Годовые климатические данные ещё не получены."],
    ["Hosildorlik bo‘yicha kuzatuvlar yuklanmagan. Shu sababli yield modeli ishga tushirilmadi; hududning iqlim tarixi va ob-havo prognozi ko‘rsatilmoqda.", "No yield observations have been uploaded. The yield model was not run; the region’s climate history and weather forecast are shown instead.", "Наблюдения урожайности не загружены. Модель урожайности не запускалась; вместо этого показываются история климата региона и прогноз погоды."],
    ["Hosildorlik modeli alohida avtomatik tahlil qiladi.", "The yield model runs its own automatic analysis.", "Модель урожайности выполняет отдельный автоматический анализ."],
    ["Hozircha dataset yo‘q.", "No datasets yet.", "Пока нет наборов данных."],
    ["Prognoz ssenariysi uchun avval hisobga kiring. Tarixiy ma’lumotlar esa ochiq.", "Sign in to run a forecast scenario. Historical data remains public.", "Войдите, чтобы запустить сценарий прогноза. Исторические данные доступны публично."],
    ["Prognoz faqat alohida ekin itemlari uchun mavjud. Agregat va mahsulot shakllari tarixiy tahlil uchun saqlanadi.", "Forecasts are available only for individual crop items. Aggregates and product forms are retained for historical analysis.", "Прогнозы доступны только для отдельных культур. Агрегаты и формы продукции сохраняются для исторического анализа."],
    ["Mamlakat va ekinni tanlang.", "Select a country and crop.", "Выберите страну и культуру."],
    ["Boshlanish yili tugash yilidan katta bo‘lishi mumkin emas.", "The start year cannot be later than the end year.", "Начальный год не может быть позже конечного."],
    ["Tarixiy qator olinmoqda…", "Fetching historical series…", "Загрузка исторического ряда…"],
    ["Tanlangan mamlakat va ekin uchun shu davrda mos kuzatuv topilmadi.", "No matching observations were found for this country and crop in the selected period.", "Для выбранной страны и культуры за этот период наблюдения не найдены."],
    ["Tarixiy ma’lumot tayyor", "Historical data ready", "Исторические данные готовы"],
    ["Mavjud yillar", "Available years", "Доступные годы"],
    ["Birinchi yil", "First year", "Первый год"],
    ["Oxirgi yil", "Last year", "Последний год"],
    ["Manba", "Source", "Источник"],
    ["Hosil maydoni (ha)", "Harvested area (ha)", "Убранная площадь (га)"],
    ["Ishlab chiqarish (t)", "Production (t)", "Производство (т)"],
    ["Hosildorlik (t/ha)", "Yield (t/ha)", "Урожайность (т/га)"],
    ["Yil", "Year", "Год"],
    ["Flag", "Flag", "Флаг"],
    ["Mamlakat yoki hududni tanlang", "Choose a country or area", "Выберите страну или территорию"],
    ["Yog‘in:", "Precipitation:", "Осадки:"],
    ["Ehtimol:", "Probability:", "Вероятность:"],
    ["Hozirgi yog‘in", "Current precipitation", "Текущие осадки"],
    ["Ha", "Yes", "Да"],
    ["Yo‘q", "No", "Нет"],
    ["Persistence’dan yaxshi", "Better than persistence", "Лучше базового Persistence"],
    ["Persistence’dan yaxshi emas", "Not better than persistence", "Не лучше базового Persistence"],
    ["Prognoz ssenariysi hisoblanmoqda…", "Calculating forecast scenario…", "Расчёт сценария прогноза…"],
    ["Tarixiy trend ssenariysi", "Historical trend scenario", "Сценарий исторического тренда"],
    ["Hisobga kiring", "Sign in", "Войдите"],
    ["Dataset topilmadi", "Dataset not found", "Набор данных не найден"],
    ["Hudud topilmadi", "Region not found", "Регион не найден"],
    ["Noma’lum xato", "Unknown error", "Неизвестная ошибка"],
    ["Tanlangan hudud bo‘yicha ekin ko‘rsatkichlari", "Crop indicators for selected area", "Показатели культур для выбранной территории"],
    ["Xaritadan mamlakat yoki ma’muriy hududni tanlang.", "Select a country or administrative area on the map.", "Выберите страну или административную территорию на карте."],
    ["Texnologiya", "Technology", "Технология"],
    ["Jami", "All", "Всего"],
    ["Sug‘oriladigan", "Irrigated", "Орошаемые"],
    ["Lalmikor", "Rainfed", "Богарные"],
    ["Yangilash", "Refresh", "Обновить"],
    ["MAPSPAM 2020 v2r2 — 2020-yil uchun raster baholashlari. Bu joriy yil kuzatuvi yoki dala o‘lchovi emas. Raster kataklari yo‘q hududlarda hosildorlik qiymati mavjud bo‘lmasligi mumkin.", "MAPSPAM 2020 v2r2 provides raster estimates for 2020. These are not current-year observations or field measurements. Areas without raster cells may have no yield value.", "MAPSPAM 2020 v2r2 — растровые оценки за 2020 год. Это не наблюдения текущего года и не измерения на поле. Для территорий без растровых ячеек значение урожайности может отсутствовать."],
    ["Hudud tanlangandan keyin server bazasidan ma’lumot olinadi.", "Data will be retrieved from the server database after an area is selected.", "После выбора территории данные будут загружены из базы сервера."],
    ["Xaritadan hudud tanlang.", "Select an area on the map.", "Выберите территорию на карте."],
    ["Tanlangan hududning admin ID raqami aniqlanmadi.", "The selected area's admin ID could not be resolved.", "Не удалось определить ID выбранной административной территории."],
    ["MAPSPAM ma’lumotlari server bazasidan yuklanmoqda…", "Loading MAPSPAM data from the server database…", "Загрузка данных MAPSPAM из базы сервера…"],
    ["Bu hudud uchun MAPSPAM yozuvlari server bazasida topilmadi. Avval tekshirilgan CSV natijalarini server bazasiga import qilish kerak.", "No MAPSPAM records were found for this area in the server database. Verified CSV results must be imported first.", "В базе сервера не найдены записи MAPSPAM для этой территории. Сначала необходимо импортировать проверенные результаты CSV."],
    ["Ekin", "Crop", "Культура"],
    ["Yig‘ib olingan maydon (ga)", "Harvested area (ha)", "Убранная площадь (га)"],
    ["Ishlab chiqarish (t)", "Production (t)", "Производство (т)"],
    ["Hosildorlik (t/ga)", "Yield (t/ha)", "Урожайность (т/га)"],
    ["Raster kataklari", "Raster cells", "Ячейки растра"],
    ["Fazoviy holat", "Spatial status", "Пространственный статус"],
    ["Diqqat: ayrim ma’muriy chegaralar turli yillarga tegishli; natijalar parent bilan to‘liq konservatsiya qilingan deb talqin qilinmaydi.", "Note: some administrative boundaries come from different years; these results must not be interpreted as fully conserved against the parent level.", "Внимание: некоторые административные границы относятся к разным годам; эти результаты нельзя считать полностью согласованными с родительским уровнем."],
    ["46 ta ekin yozuvi", "46 crop records", "46 записей по культурам"],
    ["MAPSPAM ma’lumotini olishda xato:", "Error loading MAPSPAM data:", "Ошибка загрузки данных MAPSPAM:"]
  ];

  const dictionaries = {
    en: new Map(translations.map(([uz, en]) => [uz, en])),
    ru: new Map(translations.map(([uz, , ru]) => [uz, ru]))
  };
  const sortedKeys = [...new Set(translations.map(([uz]) => uz))].sort((a, b) => b.length - a.length);
  const nodeOriginals = new WeakMap();
  const attributeOriginals = new WeakMap();
  let language = "uz";
  let translating = false;

  function safeReadLanguage() {
    try {
      const saved = localStorage.getItem("osh_language");
      return ["uz", "en", "ru"].includes(saved) ? saved : "uz";
    } catch (_) {
      return "uz";
    }
  }

  function translateValue(value) {
    if (language === "uz") return value;
    const dictionary = dictionaries[language];
    let output = value;
    for (const source of sortedKeys) {
      if (output.includes(source)) output = output.split(source).join(dictionary.get(source) || source);
    }
    return output;
  }

  function translateTextNode(node) {
    if (!node || node.nodeType !== Node.TEXT_NODE) return;
    const parent = node.parentElement;
    if (!parent || parent.closest("[data-i18n-skip],script,style,noscript")) return;
    if (!nodeOriginals.has(node)) nodeOriginals.set(node, node.nodeValue || "");
    const original = nodeOriginals.get(node);
    const translated = translateValue(original);
    if (node.nodeValue !== translated) {
      translating = true;
      node.nodeValue = translated;
      translating = false;
    }
  }

  function translateAttributes(root) {
    const elements = [];
    if (root.nodeType === Node.ELEMENT_NODE) elements.push(root);
    if (root.querySelectorAll) elements.push(...root.querySelectorAll("[placeholder],[title],[aria-label]"));
    for (const element of elements) {
      if (element.closest("[data-i18n-skip]")) continue;
      let originals = attributeOriginals.get(element);
      if (!originals) {
        originals = {};
        attributeOriginals.set(element, originals);
      }
      for (const attr of ["placeholder", "title", "aria-label"]) {
        if (!element.hasAttribute(attr)) continue;
        if (!(attr in originals)) originals[attr] = element.getAttribute(attr);
        const translated = translateValue(originals[attr]);
        if (element.getAttribute(attr) !== translated) element.setAttribute(attr, translated);
      }
    }
  }

  function walk(root = document) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) translateTextNode(node);
    translateAttributes(root);
  }

  function setLanguage(nextLanguage) {
    if (!["uz", "en", "ru"].includes(nextLanguage)) return;
    language = nextLanguage;
    try { localStorage.setItem("osh_language", language); } catch (_) {}
    document.documentElement.lang = language;
    document.title = language === "uz"
      ? "OSH Agriculture AI — O‘zbekiston"
      : language === "en"
        ? "OSH Agriculture AI — Uzbekistan"
        : "OSH Agriculture AI — Узбекистан";
    const selector = document.getElementById("language-select");
    if (selector && selector.value !== language) selector.value = language;
    walk(document);
    window.dispatchEvent(new CustomEvent("osh:languagechange", { detail: { language } }));
  }

  language = safeReadLanguage();
  const selector = document.getElementById("language-select");
  if (selector) {
    selector.value = language;
    selector.addEventListener("change", () => setLanguage(selector.value));
  }

  const observer = new MutationObserver((mutations) => {
    if (translating) return;
    for (const mutation of mutations) {
      if (mutation.type === "characterData") translateTextNode(mutation.target);
      for (const added of mutation.addedNodes || []) {
        if (added.nodeType === Node.TEXT_NODE) translateTextNode(added);
        else if (added.nodeType === Node.ELEMENT_NODE) {
          walk(added);
        }
      }
      if (mutation.type === "attributes") translateAttributes(mutation.target);
    }
  });
  observer.observe(document.documentElement, {
    subtree: true,
    childList: true,
    characterData: true,
    attributes: true,
    attributeFilter: ["placeholder", "title", "aria-label"]
  });

  setLanguage(language);
  window.OSH_I18N = {
    get language() { return language; },
    setLanguage,
    t: translateValue
  };
})();
