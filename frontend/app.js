const API_BASE = String(window.OSH_API_BASE || '').replace(new RegExp('/+$'), '');
const API = API_BASE + '/api/v1';
const $ = (id) => document.getElementById(id);
let token = localStorage.getItem('osh_global_token') || '';
let map = null, boundaryFeatures = [], selectedFeature = null, selectedLocationId = null, currentDatasetId = null, currentJobId = null, currentClimateJobId = null;
let drawingAOI = false, drawingPoints = [];
const UZB_COUNTRY = "UZB";
const UZB_ADMIN_LEVELS = {
  ADM1: { count: 14, label: "Viloyat / respublika / Toshkent shahri", vintage: "2017" },
  ADM2: { count: 199, label: "Tuman va shahar", vintage: "2020" }
};
const UZB_ADMIN_NAMES = {
  "Karakalpakstan": "Qoraqalpog‘iston Respublikasi",
  "Republic of Karakalpakstan": "Qoraqalpog‘iston Respublikasi",
  "Andijan": "Andijon viloyati", "Andijan region": "Andijon viloyati",
  "Bukhara": "Buxoro viloyati", "Bukhara region": "Buxoro viloyati",
  "Jizzakh": "Jizzax viloyati", "Jizzakh region": "Jizzax viloyati",
  "Kashkadarya": "Qashqadaryo viloyati", "Kashkadarya region": "Qashqadaryo viloyati",
  "Navoi": "Navoiy viloyati", "Navoi region": "Navoiy viloyati",
  "Namangan": "Namangan viloyati", "Namangan region": "Namangan viloyati",
  "Samarkand": "Samarqand viloyati", "Samarkand region": "Samarqand viloyati",
  "Surkhandarya": "Surxondaryo viloyati", "Surkhandarya region": "Surxondaryo viloyati",
  "Syrdarya": "Sirdaryo viloyati", "Syrdarya region": "Sirdaryo viloyati",
  "Tashkent": "Toshkent viloyati", "Tashkent region": "Toshkent viloyati",
  "Fergana": "Farg‘ona viloyati", "Fergana region": "Farg‘ona viloyati",
  "Khorezm": "Xorazm viloyati", "Khorezm region": "Xorazm viloyati",
  "Tashkent City": "Toshkent shahri"
};
const UZB_CROP_SEASONS = {
  WHEAT:["10-01","06-30"], BARLEY:["10-01","06-15"], COTTON:["04-01","09-30"],
  RICE:["05-01","09-30"], MAIZE:["04-01","09-30"], SORGHUM:["04-01","09-30"],
  POTATO:["03-01","08-31"], TOMATO:["03-01","09-30"], ONION:["10-01","07-31"],
  CUCUMBER:["03-01","08-31"], GRAPES:["03-01","10-31"], MELON:["03-01","08-31"],
  APPLE:["03-01","10-31"], VEGETABLES:["03-01","09-30"]
};
let pendingLocationSave = localStorage.getItem('osh_pending_aoi_save') === '1';
let savingLocationInProgress = false;
const AOI_STORAGE_KEY = 'osh_pending_aoi_v1';
const locations = [];

function authHeaders(json=true){const h={};if(json)h['Content-Type']='application/json';if(token)h.Authorization=`Bearer ${token}`;return h;}
async function api(path, options={}){
  let res;
  try { res=await fetch(API+path,options); }
  catch(error) {
    throw new Error('Server API bilan aloqa yo‘q ('+(API_BASE||'API server')+'). Public xarita ochiq, lekin hisob, saqlash va model uchun backend server ishga tushgan bo‘lishi kerak.');
  }
  const body=await res.json().catch(()=>({detail:res.statusText}));
  if(!res.ok){
    const message=body.detail||`HTTP ${res.status}`;
    const isAuthRoute=path.startsWith('/auth/');
    if(res.status===401&&token&&!isAuthRoute){
      logout('Sessiya yaroqsiz yoki muddati tugagan. Hisobingizga qayta kiring.');
      throw new Error('Sessiya muddati tugagan. Iltimos, qayta kiring.');
    }
    throw new Error(message);
  }
  return body;
}
function toast(el,msg){if(el)el.textContent=msg;}
function openView(name){document.querySelectorAll('.view').forEach(v=>v.classList.toggle('active',v.id===`view-${name}`));document.querySelectorAll('.nav-item').forEach(b=>b.classList.toggle('active',b.dataset.view===name));const labels={overview:'Bosh sahifa',regions:'Hududiy tahlil',forecast:'Hosildorlik prognozi',models:'Model laboratoriyasi',environment:'Iqlim va tuproq',data:'Ma’lumotlar va hisobotlar'};$('page-title').textContent=labels[name]||'OSH Global';if(name==='regions'&&map)setTimeout(()=>map.resize(),100);if(name==='environment'){loadSources();if(token&&selectedLocationId)loadClimate(selectedLocationId);}if(name==='data'){loadDatasets();loadGlobalCropCatalog();loadUzbekOfficialYield();}if(name==='forecast')loadDatasets();}

document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>openView(b.dataset.view)));
document.querySelectorAll('[data-goto]').forEach(b=>b.addEventListener('click',()=>openView(b.dataset.goto)));

function initMap(){
  const container = $('global-map');
  if(!window.maplibregl){
    container.innerHTML='<div class="empty-state">Xarita kutubxonasi yuklanmadi. Internetni tekshiring.</div>';
    return;
  }

  map = new maplibregl.Map({
    container: 'global-map',
    style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
    center: [64.5, 41.3],
    zoom: 4.2,
    minZoom: 3.6,
    maxZoom: 18,
    renderWorldCopies: false,
    attributionControl: false,
    maxPitch: 55
  });

  map.addControl(
    new maplibregl.NavigationControl({showCompass:true, showZoom:true, visualizePitch:true}),
    'top-right'
  );
  map.addControl(new maplibregl.ScaleControl({unit:'metric'}), 'bottom-left');
  map.addControl(new maplibregl.AttributionControl({compact:true}), 'bottom-right');

  // MapLibre applies projection and sky as style properties. Re-apply them
  // after style.load so they are not lost when the basemap style is refreshed.
  map.on('style.load', () => {
    try {
      map.setProjection({type:'globe'});
      map.setSky({
        'atmosphere-blend': [
          'interpolate', ['linear'], ['zoom'],
          0, 0.96,
          3, 0.82,
          6, 0.24,
          7, 0
        ]
      });
      const globeStatus = $('globe-status');
      if(globeStatus) globeStatus.textContent = '3D GLOBUS · READY';
    } catch(error) {
      console.warn('Globe projection could not be enabled:', error);
      const globeStatus = $('globe-status');
      if(globeStatus) globeStatus.textContent = 'MAP VIEW · FALLBACK';
    }
  });

  map.on('load', () => {
    map.addSource('admin-boundaries', {
      type:'geojson',
      data:{type:'FeatureCollection',features:[]}
    });
    map.addSource('aoi-draft', {
      type:'geojson',
      data:{type:'FeatureCollection',features:[]}
    });
    map.addSource('aoi-draft-points', {
      type:'geojson',
      data:{type:'FeatureCollection',features:[]}
    });
    map.addLayer({
      id:'aoi-draft-fill',type:'fill',source:'aoi-draft',
      filter:['==',['geometry-type'],'Polygon'],
      paint:{'fill-color':'#f2c879','fill-opacity':0.16}
    });
    map.addLayer({
      id:'aoi-draft-line',type:'line',source:'aoi-draft',
      paint:{'line-color':'#ffd88a','line-width':3,'line-dasharray':[2,1]}
    });
    map.addLayer({
      id:'aoi-draft-points',type:'circle',source:'aoi-draft-points',
      paint:{'circle-radius':5,'circle-color':'#ffd88a','circle-stroke-color':'#102335','circle-stroke-width':2}
    });

    map.addLayer({
      id:'admin-fill',
      type:'fill',
      source:'admin-boundaries',
      paint:{
        'fill-color':'#22c995',
        'fill-opacity':0.13,
        'fill-outline-color':'#45d9ad'
      }
    });

    map.addLayer({
      id:'admin-line',
      type:'line',
      source:'admin-boundaries',
      paint:{
        'line-color':'#55e2b8',
        'line-width':['interpolate',['linear'],['zoom'],1,0.55,6,1.15,10,1.8],
        'line-opacity':0.78
      }
    });

    map.addLayer({
      id:'admin-selected-fill',
      type:'fill',
      source:'admin-boundaries',
      filter:['==',['get','__selected'],1],
      paint:{
        'fill-color':'#f2c879',
        'fill-opacity':0.2
      }
    });

    map.addLayer({
      id:'admin-selected',
      type:'line',
      source:'admin-boundaries',
      filter:['==',['get','__selected'],1],
      paint:{
        'line-color':'#ffd88a',
        'line-width':['interpolate',['linear'],['zoom'],1,1.5,6,2.6,10,3.4],
        'line-opacity':1
      }
    });
    loadBoundaries().then(()=>restorePendingAOI()).catch(error=>toast($('boundary-status'),error.message));
  });

  map.on('click','admin-fill',(event) => {
    if(drawingAOI) return;
    const feature = event.features?.[0];
    if(!feature) return;
    const index = Number(feature.properties.__idx);
    if(Number.isInteger(index) && boundaryFeatures[index]) {
      selectFeature(boundaryFeatures[index]);
    }
  });

  map.on('click',(event) => {
    if(!drawingAOI) return;
    const point=[Number(event.lngLat.lng.toFixed(7)),Number(event.lngLat.lat.toFixed(7))];
    if(!boundaryFeatures.length || !boundaryFeatures.some(feature=>pointInGeometry(point,feature.geometry))){
      toast($('boundary-status'),'Nuqta O‘zbekiston chegarasidan tashqarida. Dala konturini mamlakat ichida chizing.');
      return;
    }
    drawingPoints.push(point);
    updateAOIDraft();
    toast($('boundary-status'),`Maydon chizilmoqda · ${drawingPoints.length} ta nuqta · kamida 3 ta kerak`);
  });

  map.on('mouseenter','admin-fill',() => {
    map.getCanvas().style.cursor='pointer';
  });
  map.on('mouseleave','admin-fill',() => {
    map.getCanvas().style.cursor='';
  });

  map.on('error', event => {
    if(event?.error) console.warn('MapLibre map error:', event.error);
  });
}
function updateAOIDraft(){
  if(!map?.getSource('aoi-draft')) return;
  const features=[];
  if(drawingPoints.length>=2){
    features.push({type:'Feature',properties:{kind:'draft-line'},geometry:{type:'LineString',coordinates:drawingPoints}});
  }
  if(drawingPoints.length>=3){
    const ring=[...drawingPoints,drawingPoints[0]];
    features.push({type:'Feature',properties:{kind:'draft-polygon'},geometry:{type:'Polygon',coordinates:[ring]}});
  }
  map.getSource('aoi-draft').setData({type:'FeatureCollection',features});
  map.getSource('aoi-draft-points').setData({
    type:'FeatureCollection',
    features:drawingPoints.map((point,index)=>({
      type:'Feature',properties:{index:index+1},
      geometry:{type:'Point',coordinates:point}
    }))
  });
}
function setDrawingControls(active){
  $('draw-aoi-start').disabled=active;
  $('draw-aoi-finish').disabled=!active;
  $('draw-aoi-cancel').disabled=!active;
  if(map?.getCanvas()) map.getCanvas().style.cursor=active?'crosshair':'';
}
function startAOIDrawing(){
  if(!map||!map.isStyleLoaded()){
    toast($('boundary-status'),'Xarita hali tayyor emas. Bir ozdan keyin qayta urinib ko‘ring.');
    return;
  }
  drawingAOI=true;
  drawingPoints=[];
  updateAOIDraft();
  setDrawingControls(true);
  toast($('boundary-status'),'Xaritada dala chegarasi bo‘ylab ketma-ket 3+ nuqtani bosing. So‘ng “Tugatish”ni bosing.');
}
function cancelAOIDrawing(){
  drawingAOI=false;
  drawingPoints=[];
  updateAOIDraft();
  setDrawingControls(false);
  toast($('boundary-status'),'Maydon chizish bekor qilindi.');
}
function finishAOIDrawing(){
  if(!drawingAOI) return;
  if(drawingPoints.length<3){
    toast($('boundary-status'),'Poligon uchun kamida 3 ta burchak nuqtasini belgilang.');
    return;
  }
  const ring=[...drawingPoints,drawingPoints[0]];
  const customFeature={
    type:'Feature',
    properties:{
      shapeName:'Foydalanuvchi chizgan maydon',
      __custom_aoi:true,
      boundarySource:'USER_DRAWN',
      boundaryLevel:'CUSTOM'
    },
    geometry:{type:'Polygon',coordinates:[ring]}
  };
  boundaryFeatures=boundaryFeatures.filter(feature=>!feature.properties?.__custom_aoi);
  boundaryFeatures.push(customFeature);
  drawingAOI=false;
  drawingPoints=[];
  updateAOIDraft();
  setDrawingControls(false);
  $('admin-level').value='ADM2';
  persistPendingAOI(customFeature);
  selectFeature(customFeature);
  $('selected-level').textContent='CUSTOM AOI';
  $('selected-area-help').textContent='Dala poligoni tanlandi. Ochiq MAPSPAM 2020 raster tahlili avtomatik boshlanadi; maydonni keyinroq saqlash va shaxsiy hosil datasetini ulash uchun hisobga kiring.';
  toast($('boundary-status'),'Maydon tanlandi va brauzerda saqlandi. Ochiq raster tahlili avtomatik boshlandi; serverda saqlash ixtiyoriy.');
}
$('draw-aoi-start').addEventListener('click',startAOIDrawing);
$('draw-aoi-finish').addEventListener('click',finishAOIDrawing);
$('draw-aoi-cancel').addEventListener('click',cancelAOIDrawing);

function featureName(f){const p=f?.properties||{};return p.shapeName||p.shape_name||p.shapeNameEn||p.NAME_1||p.NAME_2||p.name||p.NAME||p.admin||'Tanlangan hudud';}
function coordsCenter(geom){let x=0,y=0,n=0;const walk=v=>{if(Array.isArray(v)&&typeof v[0]==='number'&&typeof v[1]==='number'){x+=v[0];y+=v[1];n++;}else if(Array.isArray(v))v.forEach(walk);};walk(geom.coordinates);return n?{lat:y/n,lon:x/n}:null;}
function featureBounds(features){let minX=180,minY=90,maxX=-180,maxY=-90;const walk=v=>{if(Array.isArray(v)&&typeof v[0]==='number'&&typeof v[1]==='number'){minX=Math.min(minX,v[0]);maxX=Math.max(maxX,v[0]);minY=Math.min(minY,v[1]);maxY=Math.max(maxY,v[1]);}else if(Array.isArray(v))v.forEach(walk);};features.forEach(f=>walk(f.geometry?.coordinates));return minX<=maxX?[[minX,minY],[maxX,maxY]]:null;}

function ringAreaSqm(ring){
  if(!Array.isArray(ring)||ring.length<4)return 0;
  const radius=6371008.8, rad=Math.PI/180;
  let sum=0;
  for(let i=0;i<ring.length-1;i++){
    const a=ring[i], b=ring[i+1];
    sum+=(b[0]-a[0])*rad*(2+Math.sin(a[1]*rad)+Math.sin(b[1]*rad));
  }
  return Math.abs(sum)*radius*radius/2;
}
function geometryAreaSqm(geometry){
  if(!geometry)return 0;
  const polygons=geometry.type==='Polygon'?[geometry.coordinates]:geometry.type==='MultiPolygon'?geometry.coordinates:[];
  return polygons.reduce((total,rings)=>{
    if(!rings?.length)return total;
    const holes=rings.slice(1).reduce((sum,ring)=>sum+ringAreaSqm(ring),0);
    return total+Math.max(0,ringAreaSqm(rings[0])-holes);
  },0);
}
function geometryVertexCount(geometry){
  const polygons=geometry?.type==='Polygon'?[geometry.coordinates]:geometry?.type==='MultiPolygon'?geometry.coordinates:[];
  return polygons.reduce((sum,rings)=>sum+rings.reduce((n,ring)=>n+Math.max(0,(ring?.length||0)-1),0),0);
}
function updateAOIProfile(feature){
  const target=$('aoi-profile');
  if(!target)return;
  if(!feature){target.textContent='Hudud tanlanmagan';return;}
  const sqm=geometryAreaSqm(feature.geometry), ha=sqm/10000, vertices=geometryVertexCount(feature.geometry);
  const area=ha>=100?ha.toLocaleString('uz-UZ',{maximumFractionDigits:1})+' ga':sqm.toLocaleString('uz-UZ',{maximumFractionDigits:0})+' m²';
  target.textContent='Maydon: '+area+' · Kontur nuqtalari: '+vertices+' · '+(feature.geometry?.type||'—');
}
function refreshBoundaryAvailability(){
  const select=$('admin-level'), previous=select.value||'ADM2';
  select.innerHTML='';
  for(const level of ['ADM1','ADM2']){
    const meta=UZB_ADMIN_LEVELS[level], option=document.createElement('option');
    option.value=level;
    option.textContent=`${level} · ${meta.label} · ${meta.count} ta · chegara ${meta.vintage}`;
    select.appendChild(option);
  }
  select.value=previous==='ADM1'?'ADM1':'ADM2';
  $('country-iso3').value=UZB_COUNTRY;
  toast($('boundary-level-status'),'O‘zbekiston · UZB · ADM1: 14 ta hudud (2017) · ADM2: 199 ta tuman/shahar (2020). Chuqurroq darajalar tekshirilmaguncha tanlovda ko‘rsatilmaydi.');
}
function uzbekAdminName(feature){
  const props=feature?.properties||{};
  const raw=String(props.name_uz||props.shapeName_uz||props.NAME_UZ||props.shapeName||props.name||props.NAME||'Tanlangan hudud').trim();
  return UZB_ADMIN_NAMES[raw]||raw;
}
function populateUzbAdminSelector(){
  const select=$('uzb-admin-unit'), filter=($('uzb-admin-filter')?.value||'').trim().toLocaleLowerCase('uz');
  if(!select)return;
  const currentIndex=boundaryFeatures.indexOf(selectedFeature);
  select.innerHTML='<option value="">Hududni tanlang…</option>';
  boundaryFeatures.forEach((feature,index)=>{
    if(feature.properties?.__custom_aoi)return;
    const name=uzbekAdminName(feature);
    if(filter&&!name.toLocaleLowerCase('uz').includes(filter))return;
    const option=document.createElement('option');
    option.value=String(index);
    option.textContent=name;
    select.appendChild(option);
  });
  if(currentIndex>=0 && Array.from(select.options).some(option=>option.value===String(currentIndex))){
    select.value=String(currentIndex);
  }
}
function pointInRing(point,ring){
  let inside=false;
  for(let i=0,j=ring.length-1;i<ring.length;j=i++){
    const xi=ring[i][0], yi=ring[i][1], xj=ring[j][0], yj=ring[j][1];
    const crosses=((yi>point[1])!==(yj>point[1])) &&
      (point[0]<(xj-xi)*(point[1]-yi)/(yj-yi||1e-15)+xi);
    if(crosses)inside=!inside;
  }
  return inside;
}
function pointInPolygon(point,coordinates){
  if(!coordinates?.length||!pointInRing(point,coordinates[0]))return false;
  for(let i=1;i<coordinates.length;i++)if(pointInRing(point,coordinates[i]))return false;
  return true;
}
function pointInGeometry(point,geometry){
  if(!geometry)return false;
  if(geometry.type==='Polygon')return pointInPolygon(point,geometry.coordinates);
  if(geometry.type==='MultiPolygon')return geometry.coordinates.some(poly=>pointInPolygon(point,poly));
  return false;
}
function persistPendingAOI(feature=selectedFeature){
  if(!feature?.properties?.__custom_aoi)return;
  const record={country_iso3:UZB_COUNTRY,admin_level:'CUSTOM',name:featureName(feature),geojson:feature,updated_at:new Date().toISOString()};
  try{localStorage.setItem(AOI_STORAGE_KEY,JSON.stringify(record));}
  catch(error){toast($('saved-location-status'),'Maydon chizildi, lekin brauzerda saqlanmadi: '+error.message);}
}
function restorePendingAOI(){
  if(!map?.getSource('admin-boundaries'))return;
  let record=null;
  try{record=JSON.parse(localStorage.getItem(AOI_STORAGE_KEY)||'null');}catch(_){}
  if(!record?.geojson?.geometry)return;
  if(record.country_iso3&&record.country_iso3!=='UZB')return;
  $('country-iso3').value=UZB_COUNTRY;
  $('admin-level').value='ADM2';
  selectedFeature=record.geojson;
  selectedFeature.properties={...(selectedFeature.properties||{}),__custom_aoi:true,boundaryLevel:'CUSTOM'};
  boundaryFeatures=boundaryFeatures.filter(item=>!item.properties?.__custom_aoi);
  boundaryFeatures.push(selectedFeature);
  selectFeature(selectedFeature);
  $('selected-level').textContent='CUSTOM AOI';
  $('selected-area-help').textContent='Oldin chizilgan dala konturi tiklandi. Ochiq MAPSPAM tahlili avtomatik yangilanadi; serverda saqlash uchun hisobga kiring.';
  toast($('boundary-status'),'Oldin chizilgan maydon tiklandi · '+featureName(selectedFeature));
  if(token&&pendingLocationSave)saveSelectedLocation();
}
function selectFeature(f){
  if(!f) return;
  selectedFeature=f;
  $('selected-area-name').textContent=featureName(f);
  const isCustom=Boolean(f.properties?.__custom_aoi);
  $('selected-area-help').textContent=isCustom?'Foydalanuvchi chizgan aniq poligon. Tahlil faqat shu GeoJSON geometriyasiga yuboriladi.':'Tanlangan ma’muriy birlik. Tahlil shu hudud chegarasiga bog‘langan.';
  $('selected-country').textContent='O‘zbekiston · UZB';
  $('selected-level').textContent=isCustom?'CUSTOM AOI':$('admin-level').value;
  updateAOIProfile(f);
  if(isCustom)persistPendingAOI(f);
  const center=coordsCenter(f.geometry);
  $('selected-center').textContent=center? `${center.lat.toFixed(4)}, ${center.lon.toFixed(4)}` : '—';
  $('save-location').disabled=!selectedFeature;
  $('save-location').textContent=token?'Maydonni saqlash va dataset ulash':'Kirish va maydonni saqlash';
  if(!isCustom)populateUzbAdminSelector();

  const selectedIndex=boundaryFeatures.indexOf(f);
  const collection={
    type:'FeatureCollection',
    features:boundaryFeatures.map((feature,index)=>({
      ...feature,
      properties:{
        ...(feature.properties||{}),
        __idx:index,
        __selected:index===selectedIndex?1:0
      }
    }))
  };

  if(map?.getSource('admin-boundaries')) {
    map.getSource('admin-boundaries').setData(collection);
  }

  $('map-caption').textContent=featureName(f);
  const bounds=featureBounds([f]);
  if(bounds && map) {
    const level=$('admin-level').value;
    const [[minX,minY],[maxX,maxY]]=bounds;
    const lonSpan=Math.max(0.00005,Math.abs(maxX-minX));
    const latSpan=Math.max(0.00005,Math.abs(maxY-minY));
    const span=Math.max(lonSpan,latSpan);
    const zoomFromExtent=Math.max(8,Math.min(17,Math.log2(360/span)-0.7));
    const maxZoom=level==='ADM0'?5.5:Math.max(zoomFromExtent,level==='ADM1'?8:10);
    map.fitBounds(bounds,{
      padding:{top:58,bottom:58,left:58,right:58},
      maxZoom:Math.min(17,maxZoom),
      duration:850
    });
  }
  loadMapspamSummaries();
}

async function loadBoundaries(){
  const code=UZB_COUNTRY;
  $('country-iso3').value=UZB_COUNTRY;
  const level=$('admin-level').value;
  const status=$('boundary-status');
  if(!/^[A-Z]{3}$/.test(code)){
    toast(status,'ISO-3 kodini kiriting (masalan UZB, KAZ, DEU).');
    return;
  }
  toast(status,'Chegaralar olinmoqda…');
  try{
    let data=null;
    let boundarySource='geoBoundaries API';
    if(level==='ADM1'||level==='ADM2'){
      const staticPath=`./data/boundaries/${code}_${level}.geojson`;
      try{
        const response=await fetch(staticPath,{cache:'no-cache',headers:{Accept:'application/geo+json, application/json'}});
        if(response.ok){
          const candidate=await response.json();
          const metadata=candidate.metadata||{};
          if(candidate.type==='FeatureCollection'&&Array.isArray(candidate.features)
             &&metadata.country_iso3===code&&metadata.admin_level===level){
            data=candidate;
            boundarySource=metadata.source||'Static GeoJSON';
          }
        }
      }catch(_){}
    }
    if(!data){
      data=await api(`/boundaries/${code}/${level}`);
      boundarySource=data.metadata?.source||'geoBoundaries API';
    }
    boundaryFeatures=(data.features||[]).filter(f=>f&&f.geometry&&['Polygon','MultiPolygon'].includes(f.geometry.type));
    selectedFeature=null;
    populateUzbAdminSelector();
    loadMapspamSummaries();
    $('selected-area-name').textContent='Hududni tanlang';
    $('selected-country').textContent=code;
    $('selected-level').textContent=level;
    $('selected-center').textContent='—';
    $('save-location').disabled=true;
    if(map?.getSource('admin-boundaries'))map.getSource('admin-boundaries').setData({
      type:'FeatureCollection',
      features:boundaryFeatures.map((f,i)=>({...f,properties:{...(f.properties||{}),__idx:i}}))
    });
    if(boundaryFeatures.length&&map){
      const bounds=featureBounds(boundaryFeatures);
      if(bounds)map.fitBounds(bounds,{padding:42,maxZoom:level==='ADM0'?4:7,duration:900});
    }
    populateUzbAdminSelector();
    const expected=UZB_ADMIN_LEVELS[level].count;
    toast(status,`${boundaryFeatures.length}/${expected} ta O‘zbekiston ${level} chegarasi yuklandi · ${boundarySource}`);
  }catch(e){
    toast(status,e.message);
  }
}
$('load-boundaries').addEventListener('click',loadBoundaries);
$('admin-level').addEventListener('change',()=>{
  selectedFeature=null;
  $('selected-area-name').textContent='Hududni tanlang';
  $('selected-level').textContent=$('admin-level').value;
  loadBoundaries();
});
$('uzb-admin-filter').addEventListener('input',populateUzbAdminSelector);
$('uzb-admin-unit').addEventListener('change',()=>{
  const index=Number($('uzb-admin-unit').value);
  if(Number.isInteger(index)&&boundaryFeatures[index])selectFeature(boundaryFeatures[index]);
});
refreshBoundaryAvailability();

let mapspamRequestSequence = 0;

function mapspamSelectedAdminId(feature, countryCode, level) {
  if (feature?.properties?.__custom_aoi) return null;
  if (level === 'ADM0') return countryCode;
  const properties = feature && feature.properties ? feature.properties : {};
  const directId = properties.shapeID || properties.shapeISO;
  if (directId) return String(directId);
  const index = boundaryFeatures.indexOf(feature);
  return index >= 0 ? countryCode + '-' + (index + 1) : null;
}

function mapspamNumber(value, digits = 1) {
  if (value === null || value === undefined || value === '') return '—';
  const number = Number(value);
  return Number.isFinite(number) ? number.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  }) : '—';
}

async function loadMapspamSummaries() {
  const requestId = ++mapspamRequestSequence;
  const status = $('mapspam-summary-status');
  const table = $('mapspam-summary-table');
  if (!selectedFeature) {
    toast(status, 'Xaritadan hudud tanlang.');
    table.innerHTML = '';
    $('mapspam-context').textContent = 'Xaritadan mamlakat yoki ma’muriy hududni tanlang.';
    return;
  }

  const countryCode = $('country-iso3').value.trim().toUpperCase();
  const level = $('admin-level').value;
  if(selectedFeature.properties?.__custom_aoi){
    $('mapspam-context').textContent=countryCode+' · '+featureName(selectedFeature)+' · CUSTOM AOI · faqat tanlangan poligon';
    return analyzeCustomAOI();
  }
  const adminId = mapspamSelectedAdminId(selectedFeature, countryCode, level);
  if (!adminId) {
    toast(status, 'Tanlangan hududning admin ID raqami aniqlanmadi.');
    table.innerHTML = '';
    return;
  }

  const technology = $('mapspam-technology').value || 'all';
  const params = new URLSearchParams({
    country_iso3: countryCode,
    admin_level: level,
    admin_id: adminId,
    source_year: '2020',
    technology: technology,
    dataset_id: 'mapspam-2020-v2r2',
    limit: '100'
  });
  const areaName = featureName(selectedFeature);
  $('mapspam-context').textContent = countryCode + ' · ' + areaName + ' · ' + level + ' · ' + adminId;
  toast(status, 'MAPSPAM ma’lumotlari server bazasidan yuklanmoqda…');
  table.innerHTML = '';

  try {
    const result = await api('/global-raster-summaries?' + params.toString());
    if (requestId !== mapspamRequestSequence) return;
    const rows = result.items || [];
    if (!rows.length) {
      toast(status, 'Bu hudud uchun MAPSPAM yozuvlari server bazasida topilmadi. Avval tekshirilgan CSV natijalarini server bazasiga import qilish kerak.');
      return;
    }

    const headers = [
      'Ekin',
      'Yig‘ib olingan maydon (ga)',
      'Ishlab chiqarish (t)',
      'Hosildorlik (t/ga)',
      'Raster kataklari',
      'Fazoviy holat'
    ];
    const body = rows.map(function(row) {
      return '<tr><td>' + escapeHtml(row.crop_name || row.crop_code || '—') +
        '</td><td>' + mapspamNumber(row.harvested_area_ha, 0) +
        '</td><td>' + mapspamNumber(row.production_t, 0) +
        '</td><td>' + mapspamNumber(row.yield_t_ha_area_weighted, 3) +
        '</td><td>' + mapspamNumber(row.valid_cells, 0) +
        '</td><td>' + escapeHtml(row.spatial_status || '—') + '</td></tr>';
    }).join('');
    table.innerHTML = '<table><thead><tr>' +
      headers.map(function(header) { return '<th>' + header + '</th>'; }).join('') +
      '</tr></thead><tbody>' + body + '</tbody></table>';

    const validationStates = Array.from(new Set(
      rows.map(function(row) { return row.hierarchy_validation_status; }).filter(Boolean)
    ));
    const boundaryWarning = validationStates.some(function(value) {
      return value.includes('NOT_RECONCILED');
    });
    const note = boundaryWarning
      ? 'Diqqat: ayrim ma’muriy chegaralar turli yillarga tegishli; natijalar parent bilan to‘liq konservatsiya qilingan deb talqin qilinmaydi.'
      : '';
    const completeness = rows.length === 46
      ? '46 ta ekin yozuvi'
      : rows.length + ' ta ekin yozuvi (kutilgan: 46)';
    toast(status, completeness + ' topildi · MAPSPAM 2020 v2r2 · ' + technology +
      ' · ' + (validationStates.join(', ') || 'validatsiya holati noma’lum') +
      (note ? ' · ' + note : ''));
  } catch (error) {
    if (requestId !== mapspamRequestSequence) return;
    toast(status, 'MAPSPAM ma’lumotini olishda xato: ' + error.message);
  }
}

$('mapspam-technology').addEventListener('change', loadMapspamSummaries);
$('refresh-mapspam-summary').addEventListener('click', loadMapspamSummaries);

async function analyzeCustomAOI(){
  if(!selectedFeature?.properties?.__custom_aoi){
    toast($('mapspam-summary-status'),'Avval xaritada maydon chizing.');
    return;
  }
  const status=$('mapspam-summary-status'), table=$('mapspam-summary-table');
  const cropCode=$('aoi-crop-code')?.value||'whea';
  const technology=$('mapspam-technology').value||'all';
  const requestId=++mapspamRequestSequence;
  const payload={
    geojson:selectedFeature,
    crop_code:cropCode,
    technology,
    location_name:featureName(selectedFeature),
    admin_level:'CUSTOM'
  };
  table.innerHTML='';
  toast(status,'Tanlangan poligon ichidagi MAPSPAM 2020 raster kataklari hisoblanmoqda…');
  try{
    const result=await api('/global-raster-summary/mapspam',{
      method:'POST',
      headers:authHeaders(),
      body:JSON.stringify(payload)
    });
    if(requestId!==mapspamRequestSequence)return;
    const valid=Number(result.valid_cells||0);
    const values=[
      ['Ekin',result.crop_name||cropCode],
      ['Jismoniy maydon',mapspamNumber(result.physical_area_ha,1)+' ga'],
      ['Yig‘ib olingan maydon',mapspamNumber(result.harvested_area_ha,1)+' ga'],
      ['Ishlab chiqarish',mapspamNumber(result.production_t,1)+' t'],
      ['Hosildorlik',result.yield_t_ha_area_weighted===null?'—':mapspamNumber(result.yield_t_ha_area_weighted,3)+' t/ga'],
      ['Yaroqli raster kataklari',mapspamNumber(valid,0)]
    ];
    table.innerHTML='<div class="kpi-grid">'+values.map(([label,value])=>'<article class="kpi-card"><small>'+escapeHtml(label)+'</small><strong>'+escapeHtml(value)+'</strong></article>').join('')+'</div>';
    const message=valid
      ?'Tanlangan poligon bo‘yicha natija tayyor · '+valid+' ta yaroqli raster katagi · MAPSPAM '+(result.source_year||2020)+'.'
      :'Bu poligon kesimida yaroqli MAPSPAM katagi topilmadi. Buni 0 hosildorlik deb talqin qilmang; raster qamrovi yoki 9.3 km katak o‘lchami sabab bo‘lishi mumkin.';
    toast(status,message);
  }catch(error){
    if(requestId!==mapspamRequestSequence)return;
    toast(status,'Poligon raster tahlili bajarilmadi: '+error.message);
  }
}
$('analyze-aoi-mapspam')?.addEventListener('click',analyzeCustomAOI);
$('aoi-crop-code')?.addEventListener('change',()=>{if(selectedFeature?.properties?.__custom_aoi)analyzeCustomAOI();});

$('country-iso3').addEventListener('keydown',e=>{if(e.key==='Enter')loadBoundaries();});


async function saveSelectedLocation(){
  if(!selectedFeature)return;
  if(savingLocationInProgress)return;
  if(!token){
    pendingLocationSave=true;
    localStorage.setItem('osh_pending_aoi_save','1');
    persistPendingAOI(selectedFeature);
    toast($('saved-location-status'),'Poligon brauzerda saqlandi. Ochiq raster tahlili guest rejimida ishlaydi; hisobga kirgach aynan shu kontur serverga saqlanadi.');
    openAuth();
    return;
  }
  savingLocationInProgress=true;
  try{
    const code=UZB_COUNTRY;
    const level=selectedFeature.properties?.__custom_aoi?'CUSTOM':$('admin-level').value;
    const payload={
      country_iso3:code,
      name:featureName(selectedFeature),
      admin_level:level,
      climate_start_year:Number($('climate-start-year').value)||2010,
      geojson:selectedFeature,
      source:selectedFeature.properties?.__custom_aoi?'User-drawn AOI':'geoBoundaries gbOpen'
    };
    toast($('saved-location-status'),'Tanlangan poligon serverga saqlanmoqda…');
    const res=await api('/locations',{method:'POST',headers:authHeaders(),body:JSON.stringify(payload)});
    selectedLocationId=res.id;
    pendingLocationSave=false;
    localStorage.removeItem('osh_pending_aoi_save');
    localStorage.removeItem(AOI_STORAGE_KEY);
    toast($('saved-location-status'),'Hudud saqlandi · '+res.name+'. Faqat shu hudud uchun iqlim job #'+res.climate_job_id+' boshlandi.');
    await loadLocations();
    $('location-select').value=String(res.id);
    $('environment-location-select').value=String(res.id);
    pollClimateJob(res.climate_job_id,res.id);
    if(selectedFeature.properties?.__custom_aoi)await analyzeCustomAOI();
  }catch(e){
    toast($('saved-location-status'),'Hudud saqlanmadi: '+e.message);
  }finally{
    savingLocationInProgress=false;
  }
}
$('save-location').addEventListener('click',saveSelectedLocation);



function openAuth(){$('auth-modal').hidden=false;$('auth-message').textContent='';}
function closeAuth(){$('auth-modal').hidden=true;}
$('auth-open').addEventListener('click',()=>token?(logout()):openAuth());$('auth-close').addEventListener('click',closeAuth);
async function authAction(mode){
  const email=$('auth-email').value.trim(),password=$('auth-password').value;
  if(!email||!password){toast($('auth-message'),'Email va parolni kiriting.');return;}
  if(mode==='register'&&password.length<10){toast($('auth-message'),'Yangi parol kamida 10 belgidan iborat bo‘lishi kerak.');return;}
  try{
    const res=await api('/auth/'+mode,{method:'POST',headers:authHeaders(),body:JSON.stringify({email,password})});
    token=res.access_token;
    localStorage.setItem('osh_global_token',token);
    setAuthUI(res.user);
    closeAuth();
    await loadLocations();
    await loadDatasets();
    if(pendingLocationSave&&selectedFeature)await saveSelectedLocation();
  }catch(e){toast($('auth-message'),e.message);}
}
$('register-button').addEventListener('click',()=>authAction('register'));
$('login-button').addEventListener('click',()=>authAction('login'));
function setAuthUI(user){
  $('user-label').textContent=user?.email||'Mehmon rejimi';
  $('auth-open').textContent=user?'Chiqish':'Kirish';
  $('save-location').disabled=!selectedFeature;
  $('save-location').textContent=user?'Maydonni saqlash va dataset ulash':'Kirish va maydonni saqlash';
}
function logout(reason='Hisobdan chiqildi.'){token='';selectedLocationId=null;currentDatasetId=null;currentJobId=null;currentClimateJobId=null;localStorage.removeItem('osh_global_token');setAuthUI(null);locations.length=0;$('dataset-list').textContent='Hisobga kiring va dataset yuklang.';$('forecast-dataset').innerHTML='<option value="">Dataset yuklang</option>';$('process-dataset').disabled=true;$('location-select').innerHTML='<option value="">Avval xaritada hududni saqlang</option>';$('environment-location-select').innerHTML='<option value="">Avval hududni saqlang</option>';$('location-climate-results').hidden=true;toast($('saved-location-status'),reason);toast($('environment-status'),reason);}

async function loadLocations(){if(!token)return;try{const rows=await api('/locations',{headers:authHeaders(false)});locations.splice(0,locations.length,...rows);const options='<option value="">Hududni tanlang</option>'+rows.map(x=>`<option value="${x.id}">${escapeHtml(x.name)} · ${escapeHtml(x.country_iso3)} · ${escapeHtml(x.admin_level)}</option>`).join('');$('location-select').innerHTML=options;$('environment-location-select').innerHTML=options;if(!selectedLocationId&&rows.length)selectedLocationId=rows[0].id;if(selectedLocationId&&rows.some(x=>x.id===selectedLocationId)){$('location-select').value=String(selectedLocationId);$('environment-location-select').value=String(selectedLocationId);loadClimate(selectedLocationId);}else if(!rows.length){selectedLocationId=null;$('environment-status').textContent='Hali saqlangan hudud yo‘q. Avval Hududiy tahlil bo‘limida hudud tanlang.';$('location-climate-results').hidden=true;}}catch(e){console.warn(e);}}
$('location-select').addEventListener('change',()=>{selectedLocationId=Number($('location-select').value)||null;$('environment-location-select').value=selectedLocationId?String(selectedLocationId):'';if(selectedLocationId)loadClimate(selectedLocationId);});
$('environment-location-select').addEventListener('change',()=>{selectedLocationId=Number($('environment-location-select').value)||null;$('location-select').value=selectedLocationId?String(selectedLocationId):'';if(selectedLocationId)loadClimate(selectedLocationId);else $('location-climate-results').hidden=true;});
$('refresh-climate').addEventListener('click',async()=>{if(!token){openAuth();return;}const id=Number($('environment-location-select').value)||selectedLocationId;if(!id){toast($('environment-status'),'Avval Hududiy tahlil bo‘limida hududni saqlang.');return;}try{const job=await api('/locations/'+id+'/analyze',{method:'POST',headers:authHeaders()});currentClimateJobId=null;toast($('environment-status'),`Iqlim tahlili navbatga qo‘yildi · Job #${job.job_id}`);pollClimateJob(job.job_id,id);}catch(e){toast($('environment-status'),e.message);}});

function fmt(value,digits=1){return value===null||value===undefined||Number.isNaN(Number(value))?'—':Number(value).toFixed(digits);}
function pollClimateJob(jobId,locationId){if(currentClimateJobId===jobId)return;currentClimateJobId=jobId;const check=async()=>{try{const j=await api(`/location-climate-jobs/${jobId}`,{headers:authHeaders(false)});const progressText=`Iqlim tahlili: ${j.status} · ${j.progress}% · ${j.message||''}`;toast($('saved-location-status'),progressText);toast($('environment-status'),progressText);$('location-climate-results').hidden=false;$('climate-title').textContent='Hudud iqlim tahlili';$('climate-subtitle').textContent=j.message||'Tarixiy qator va prognoz olinmoqda.';$('climate-source-status').textContent=j.status;if(j.status==='COMPLETED'){currentClimateJobId=null;await loadClimate(locationId);return;}if(j.status==='FAILED'){currentClimateJobId=null;toast($('saved-location-status'),`Iqlim tahlili xatosi: ${j.error||'Noma’lum xato'}`);return;}setTimeout(check,3000);}catch(e){toast($('saved-location-status'),e.message);}};check();}
async function searchSentinel2Scenes(){
  if(!token){openAuth();toast($('sentinel2-search-status'),'Sentinel-2 katalogini saqlangan hudud bo‘yicha qidirish uchun hisobga kiring.');return;}
  const locationId=Number($('environment-location-select').value||selectedLocationId);
  if(!locationId){toast($('sentinel2-search-status'),'Avval xaritada hududni chizing yoki tanlang va saqlang.');return;}
  const start=$('sentinel2-start-date').value||'2024-01-01';
  const end=$('sentinel2-end-date').value||new Date().toISOString().slice(0,10);
  const cloud=Number($('sentinel2-max-cloud').value);
  if(start>end){toast($('sentinel2-search-status'),'Boshlanish sanasi tugash sanasidan keyin bo‘lishi mumkin emas.');return;}
  const results=$('sentinel2-scene-results');
  results.innerHTML='';
  toast($('sentinel2-search-status'),'Copernicus STAC katalogidan hududga kesishadigan L2A sahnalari qidirilmoqda…');
  try{
    const params=new URLSearchParams({start_date:start,end_date:end,max_cloud_percent:String(Number.isFinite(cloud)?cloud:30),limit:'50'});
    const data=await api(`/locations/${locationId}/sentinel2-scenes?${params.toString()}`,{headers:authHeaders(false)});
    if(!data.items?.length){
      toast($('sentinel2-search-status'),`Sahna topilmadi · ${data.start_date}–${data.end_date} · cloud ≤ ${data.max_cloud_percent}%`);
      results.innerHTML='<div class="empty-state">Ushbu davr va hudud uchun mos Sentinel-2 L2A sahnasi topilmadi. Sanani kengaytiring yoki cloud limitni oshiring.</div>';
      return;
    }
    results.innerHTML=`<table><thead><tr><th>Acquisition date</th><th>Scene ID</th><th>Cloud %</th><th>Assets</th></tr></thead><tbody>${data.items.map(item=>`<tr><td>${escapeHtml(item.datetime||'—')}</td><td>${escapeHtml(item.id||'—')}</td><td>${fmt(item.cloud_cover_percent,1)}</td><td>${escapeHtml((item.assets_available||[]).join(', ')||'No B04/B08/SCL asset keys in response')}</td></tr>`).join('')}</tbody></table>`;
    toast($('sentinel2-search-status'),`${data.returned} ta Sentinel-2 L2A sahnasi topildi · STAC katalog qidiruvi. NDVI hali hisoblanmagan.${data.next_page_available?' Keyingi sahifa ham mavjud.':''}`);
  }catch(e){toast($('sentinel2-search-status'),e.message);}
}
$('search-sentinel2').addEventListener('click',searchSentinel2Scenes);

async function loadClimate(locationId){if(!token||!locationId)return;try{const data=await api(`/locations/${locationId}/climate`,{headers:authHeaders(false)});$('environment-location-select').value=String(locationId);$('location-select').value=String(locationId);$('environment-status').textContent=`Tanlangan hudud: ${data.location.name} · NASA POWER va Open-Meteo holati yangilandi.`;$('location-climate-results').hidden=false;$('climate-title').textContent=`${data.location.name} · yillik iqlim`;$('climate-subtitle').textContent=`Koordinata: ${fmt(data.location.centroid.lat,4)}, ${fmt(data.location.centroid.lon,4)} · tarixiy kuzatuvlar va joriy prognoz`;const weather=data.weather||{};const current=weather.current||{};const units=weather.current_units||{};const cards=[['Hozirgi harorat',current.temperature_2m,units.temperature_2m||'°C'],['His qilinadi',current.apparent_temperature,units.apparent_temperature||'°C'],['Nisbiy namlik',current.relative_humidity_2m,units.relative_humidity_2m||'%'],['Hozirgi yog‘in',current.precipitation,units.precipitation||'mm'],['Shamol',current.wind_speed_10m,units.wind_speed_10m||'km/h']];$('climate-current-kpis').innerHTML=cards.map(([label,value,unit])=>`<article class="climate-kpi"><small>${label}</small><strong>${fmt(value,1)} <em>${unit}</em></strong></article>`).join('');const days=weather.daily||[];$('climate-forecast-days').innerHTML=days.slice(0,8).map(day=>`<div class="forecast-day"><b>${escapeHtml(day.date)}</b><strong>${fmt(day.temperature_max_c,0)}° / ${fmt(day.temperature_min_c,0)}°</strong><span>Yog‘in: ${fmt(day.precipitation_sum_mm,1)} mm</span><span>Ehtimol: ${fmt(day.precipitation_probability_max_pct,0)}%</span></div>`).join('')||'<div class="empty-state">Prognoz mavjud emas. Manba holatini tekshiring.</div>';const annual=data.annual||[];$('annual-row-count').textContent=`${annual.length} yil`;$('annual-climate-rows').innerHTML=annual.slice().reverse().map(row=>`<tr><td>${row.year}</td><td>${fmt(row.wx_t2m_mean_c,1)} °C</td><td>${fmt(row.wx_precip_sum_mm,0)} mm</td><td>${fmt(row.wx_hot_days_ge_35c,0)}</td><td>${fmt(row.wx_frost_days_lt_0c,0)}</td><td>${fmt(row.wx_coverage_pct,1)}%</td></tr>`).join('')||'<tr><td colspan="6" class="empty-state">Yillik iqlim ma’lumoti hali olinmagan.</td></tr>';const forecastStatus=weather.status||'PENDING';$('climate-source-status').textContent=`NASA: ${annual.length?'AVAILABLE':'PENDING'} · Prognoz: ${forecastStatus}`;const latest=data.latest_job;const modelStatus=latest?.result?.model_status;if(modelStatus==='NOT_RUN_NO_YIELD_DATA')$('climate-model-note').textContent='Hosildorlik bo‘yicha kuzatuvlar yuklanmagan. Shu sababli yield modeli ishga tushirilmadi; hududning iqlim tarixi va ob-havo prognozi ko‘rsatilmoqda.';else if(modelStatus)$('climate-model-note').textContent=`Hudud iqlim job’i: ${latest.status}. Ekin datasetini yuklasangiz, hosildorlik modeli alohida avtomatik tahlil qiladi.`;else $('climate-model-note').textContent='Hosildorlik ma’lumoti bo‘lmasa, model prognozi hisoblanmaydi.';if(latest&&['QUEUED','RUNNING'].includes(latest.status))pollClimateJob(latest.id,locationId);}catch(e){console.warn(e);toast($('saved-location-status'),e.message);}}

$('upload-dataset').addEventListener('click',async()=>{if(!token){openAuth();return;}const locationId=Number($('location-select').value),file=$('yield-file').files[0];if(!locationId||!file){toast($('upload-status'),'Hududni tanlang va CSV faylni biriktiring.');return;}const form=new FormData();form.append('location_id',locationId);form.append('crop_code',$('crop-code').value||'WHEAT');form.append('name',file.name);form.append('year_column',$('year-column').value||'year');form.append('yield_column',$('yield-column').value||'yield_t_ha');form.append('area_column',$('area-column').value||'');form.append('area_basis',$('area-basis').value);form.append('season_start',$('season-start').value);form.append('season_end',$('season-end').value);form.append('global_consent',$('global-consent').checked?'true':'false');form.append('file',file);toast($('upload-status'),'CSV tekshirilmoqda va bazaga yozilmoqda…');try{const res=await api('/datasets/upload',{method:'POST',headers:authHeaders(false),body:form});currentDatasetId=res.dataset_id;toast($('upload-status'),`Dataset SQL bazaga saqlandi: ${res.row_count} qator · ${res.year_range[0]}–${res.year_range[1]}. Avtomatik ob-havo va model tahlili job #${res.analysis_job_id} boshlandi.`);await loadDatasets();$('forecast-dataset').value=String(currentDatasetId);$('process-dataset').disabled=true;currentJobId=res.analysis_job_id;pollJob();}catch(e){toast($('upload-status'),e.message);}});

async function loadDatasets(){if(!token)return;try{const ds=await api('/datasets',{headers:authHeaders(false)});$('dataset-list').innerHTML=ds.length?ds.map(d=>{const loc=locations.find(x=>x.id===d.location_id);return `<div class="dataset-row"><span><b>${escapeHtml(d.name)}</b><small> · ${escapeHtml(d.crop_code)} · ${escapeHtml(loc?.name||'Hudud #'+d.location_id)} · ${d.first_year}–${d.last_year} · ${d.row_count} qator</small></span><span class="status-chip">${escapeHtml(d.status)}</span></div>`;}).join(''):'<div class="empty-state">Hozircha dataset yo‘q.</div>';if(ds.length){$('forecast-dataset').innerHTML=ds.map(d=>{const loc=locations.find(x=>x.id===d.location_id);return `<option value="${d.id}">${escapeHtml(loc?.name||'Hudud #'+d.location_id)} · ${escapeHtml(d.crop_code)} · ${escapeHtml(d.name)}</option>`;}).join('');if(!currentDatasetId)currentDatasetId=ds[0].id;if(ds.some(d=>d.id===currentDatasetId))$('forecast-dataset').value=String(currentDatasetId);$('process-dataset').disabled=false;}}catch(e){console.warn(e);}}
function escapeHtml(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}

async function startProcessing(){if(!token||!currentDatasetId){toast($('job-list'),'Avval hisobga kiring va dataset yuklang.');return;}try{const j=await api(`/datasets/${currentDatasetId}/process`,{method:'POST',headers:authHeaders()});currentJobId=j.job_id;toast($('job-list'),`Job #${j.job_id}: ${j.status}`);pollJob();}catch(e){toast($('job-list'),e.message);}}
function pollJob(){if(!currentJobId)return;const check=async()=>{try{const j=await api(`/jobs/${currentJobId}`,{headers:authHeaders(false)});const automatic=j.result?.automatic_analysis;$('job-list').innerHTML=`<b>Job #${j.id}</b> · ${j.status} · ${j.progress}%<p>${escapeHtml(j.message||'')}</p>${j.error?`<p class="amber-text">${escapeHtml(j.error)}</p>`:''}${automatic?`<div class="notice"><b>AI model holati:</b> ${escapeHtml(automatic.status)}<br>${escapeHtml(automatic.reason||automatic.note||'')}</div>`:''}${j.result?`<pre>${escapeHtml(JSON.stringify(j.result,null,2))}</pre>`:''}`;if(['COMPLETED','FAILED'].includes(j.status)){if(automatic?.prediction){const location=locations.find(x=>x.id===Number($('location-select').value));renderPrediction({...automatic.prediction,dataset_id:currentDatasetId,location:location?.name||'Tanlangan poligon',crop_code:$('crop-code').value||'Tanlangan ekin'});}loadDatasets();return;}setTimeout(check,3000);}catch(e){toast($('job-list'),e.message);}};check();}
$('refresh-datasets').addEventListener('click',loadDatasets);$('process-dataset').addEventListener('click',startProcessing);

$('run-prediction').addEventListener('click',async()=>{if(!token){openAuth();return;}const datasetId=Number($('forecast-dataset').value)||currentDatasetId;if(!datasetId){toast($('prediction-result'),'Avval dataset yuklang.');return;}const payload={dataset_id:datasetId,target_year:Number($('target-year').value)};if($('forecast-model').value)payload.model=$('forecast-model').value;$('prediction-result').innerHTML='<div class="empty-state">Model hisoblayapti…</div>';try{const r=await api('/predictions',{method:'POST',headers:authHeaders(),body:JSON.stringify(payload)});renderPrediction(r);}catch(e){$('prediction-result').textContent=e.message;}});
function renderPrediction(r){$('prediction-result').innerHTML=`<div class="panel-title"><div><span class="eyebrow">${escapeHtml(r.prediction_type)}</span><h3>${escapeHtml(r.location)} · ${r.target_year} scenario</h3></div><span class="source-pill">${escapeHtml(r.selected_model)}</span></div><div class="result-kpis"><div><small>Hosildorlik ssenariysi</small><strong>${Number(r.predicted_yield_t_ha).toFixed(3)} t/ha</strong></div><div><small>Oxirgi kuzatilgan</small><strong>${Number(r.reference_last_observed_yield_t_ha).toFixed(3)} t/ha</strong></div><div><small>OOF MAE</small><strong>${r.selected_model_oof_mae_t_ha===null?'—':Number(r.selected_model_oof_mae_t_ha).toFixed(4)}</strong></div></div><p><b>Benchmark:</b> Persistence MAE ${Number(r.persistence_oof_mae_t_ha).toFixed(4)} t/ha · ${escapeHtml(r.benchmark_status)}</p><p><b>Ob-havo farazi:</b> ${escapeHtml(r.weather_assumption)}</p><h4>Modellar taqqoslanishi</h4><div class="table-wrap"><table><thead><tr><th>Model</th><th>OOF qator</th><th>MAE t/ha</th><th>Persistence'dan yaxshi</th></tr></thead><tbody>${r.model_comparison.map(m=>`<tr><td>${escapeHtml(m.model)}</td><td>${m.oof_rows}</td><td>${m.oof_mae_t_ha===null?'—':Number(m.oof_mae_t_ha).toFixed(4)}</td><td>${m.beats_persistence?'Ha':'Yo‘q'}</td></tr>`).join('')}</tbody></table></div><div class="notice">${escapeHtml(r.governance_note)}</div>`;}

async function loadSources(){try{
  const r=await api('/sources');
  $('source-cards').innerHTML=Object.entries(r.sources).map(([key,source])=>{
    const status=source.status||'UNKNOWN';
    const stateClass=status==='ACTIVE'?'':'partial';
    const label=source.status_label||(status==='ACTIVE'?'ULANGAN':'ULANMAGAN');
    return `<article class="source-card"><span class="source-state ${stateClass}">${escapeHtml(label)}</span><h3>${escapeHtml(key)}</h3><p>${escapeHtml(source.coverage)}</p><small>${escapeHtml(source.note)}</small><p><a href="${source.url}" target="_blank" rel="noopener">Manba →</a></p></article>`;
  }).join('');
}catch(e){$('source-cards').textContent=e.message;}}



let uzbOfficialYieldCache = null;
const UZB_SIAT_SOURCES = {
  whea: [
    ["Bug‘doy yalpi hosili", "https://siat.stat.uz/data/1458/"],
    ["Bug‘doy ekilgan maydoni", "https://siat.stat.uz/data/2761/"]
  ],
  pota: [
    ["Kartoshka yalpi hosili", "https://siat.stat.uz/data/323/"],
    ["Kartoshka ekilgan maydoni", "https://siat.stat.uz/data/2040/"]
  ],
  cott: [
    ["Xom paxta yalpi hosili", "https://siat.stat.uz/data/2389/"],
    ["Paxta ekilgan maydoni", "https://siat.stat.uz/data/2039/"]
  ]
};
async function loadUzbekOfficialYield(){
  const status=$('uzb-official-yield-status');
  if(uzbOfficialYieldCache){populateUzbekOfficialYieldControls();return;}
  try{
    toast(status,'SIAT rasmiy statistik qatorlari yuklanmoqda…');
    const [wheatResponse,cropsResponse]=await Promise.all([
      fetch('./data/official-yield/UZB_ADM1_WHEA_2010_2024.json',{cache:'no-cache'}),
      fetch('./data/official-yield/UZB_ADM1_CROPS_2010_2024.json',{cache:'no-cache'})
    ]);
    if(!wheatResponse.ok||!cropsResponse.ok)throw new Error('SIAT public snapshot fayllari topilmadi');
    const wheat=await wheatResponse.json();
    const crops=await cropsResponse.json();
    if(wheat.country_iso3!=='UZB'||wheat.admin_level!=='ADM1'||wheat.crop_code!=='whea'||!Array.isArray(wheat.regions))throw new Error('SIAT bug‘doy snapshot identifikatsiyasi noto‘g‘ri');
    if(crops.country_iso3!=='UZB'||crops.admin_level!=='ADM1'||!crops.crops)throw new Error('SIAT ekin snapshot identifikatsiyasi noto‘g‘ri');
    uzbOfficialYieldCache={
      years:wheat.years||[2010,2024],
      geographic_coverage:wheat.geographic_coverage||crops.geographic_coverage||'13 ta qishloq xo‘jaligi hududi',
      crops:{
        whea:{...wheat,crop_code:'whea',crop_name_uz:wheat.crop_name_uz||'Bug‘doy'},
        ...(crops.crops||{})
      }
    };
    populateUzbekOfficialYieldControls();
  }catch(error){
    toast(status,'SIAT viloyat snapshoti hozircha yuklanmadi. Rasmiy manba havolalari orqali tekshiring: '+error.message);
    $('uzb-official-yield-table').innerHTML='<div class="empty-state">SIAT fayllari GitHub Pages build paketida mavjud bo‘lganda bu yerda rasmiy viloyat qatori ko‘rsatiladi. Yuqoridagi rasmiy SIAT havolalari ochiq.</div>';
  }
}
function populateUzbekOfficialYieldControls(){
  if(!uzbOfficialYieldCache)return;
  const cropSelect=$('uzb-official-crop');
  const regionSelect=$('uzb-official-region');
  const cropCode=cropSelect.value||'whea';
  const crop=uzbOfficialYieldCache.crops[cropCode]||uzbOfficialYieldCache.crops.whea;
  const previousRegion=regionSelect.value;
  const regions=(crop.regions||[]).slice().sort((a,b)=>String(a.name_uz).localeCompare(String(b.name_uz),'uz'));
  regionSelect.innerHTML=regions.map(region=>'<option value="'+escapeHtml(region.admin_code)+'">'+escapeHtml(region.name_uz)+'</option>').join('');
  if(regions.some(region=>String(region.admin_code)===previousRegion))regionSelect.value=previousRegion;
  renderUzbekOfficialYield();
}
function renderUzbekOfficialYield(){
  if(!uzbOfficialYieldCache)return;
  const cropCode=$('uzb-official-crop').value||'whea';
  const regionCode=$('uzb-official-region').value;
  const crop=uzbOfficialYieldCache.crops[cropCode];
  const region=(crop?.regions||[]).find(item=>String(item.admin_code)===regionCode);
  const status=$('uzb-official-yield-status');
  const table=$('uzb-official-yield-table');
  if(!crop||!region){
    toast(status,'Tanlangan ekin va viloyat uchun SIAT qatori topilmadi.');
    table.innerHTML='';
    return;
  }
  const rows=(region.records||[]).slice().sort((a,b)=>Number(a.year)-Number(b.year));
  const fmt=(value,digits=2)=>value===null||value===undefined||!Number.isFinite(Number(value))?'—':Number(value).toLocaleString('uz-UZ',{minimumFractionDigits:digits,maximumFractionDigits:digits});
  table.innerHTML=rows.length
    ?'<table><thead><tr><th>Yil</th><th>Hosildorlik (t/ga)</th><th>Yalpi hosil (t)</th><th>Ekilgan maydon (ga)</th></tr></thead><tbody>'+
      rows.map(row=>'<tr><td>'+escapeHtml(row.year)+'</td><td>'+fmt(row.yield,3)+'</td><td>'+fmt(row.production_t,0)+'</td><td>'+fmt(row.sown_area_ha,0)+'</td></tr>').join('')+
      '</tbody></table>'
    :'<div class="empty-state">Bu viloyat uchun kuzatuv topilmadi.</div>';
  toast(status,`SIAT · CC BY 4.0 · O‘zbekiston · ${region.name_uz} · ${crop.crop_name_uz||cropCode} · ${rows.length} yillik kuzatuv · ${uzbOfficialYieldCache.geographic_coverage}. Bu viloyat statistik nisbati, dala o‘lchovi emas.`);
}
$('uzb-official-crop').addEventListener('change',populateUzbekOfficialYieldControls);
$('uzb-official-region').addEventListener('change',renderUzbekOfficialYield);

let globalCropCatalogLoaded = false;

async function loadGlobalCropCatalog(){
  const status=$('global-data-status');
  try{
    toast(status,'FAOSTAT ekin va hudud katalogi olinmoqda…');
    const itemType=$('global-item-type').value||'CROP';
    const [catalog,countries]=await Promise.all([
      api(`/global-crops?item_type=${encodeURIComponent(itemType)}`),
      api('/global-crops/countries')
    ]);
    const cropSelect=$('global-crop');
    const previousCrop=cropSelect.value;
    const countrySelect=$('global-country');
    cropSelect.innerHTML=(catalog.crops||[]).map(x=>`<option value="${escapeHtml(x.crop_code)}" data-item-type="${escapeHtml(x.item_type)}">${escapeHtml(x.crop_name)} · ${escapeHtml(x.item_type_label)} · ${escapeHtml(x.crop_code)}</option>`).join('');
    if((catalog.crops||[]).some(x=>x.crop_code===previousCrop))cropSelect.value=previousCrop;
    const uzbRecord=(countries.countries||[]).find(x=>x.country_iso3==='UZB');
    countrySelect.innerHTML='<option value="UZB">O‘zbekiston · UZB</option>';
    countrySelect.value='UZB';
    $('global-start-year').value='1992';
    $('global-end-year').value='2024';
    globalCropCatalogLoaded=true;
    const counts=catalog.item_type_counts||{};
    toast(status,`FAOSTAT katalogi tayyor · ${catalog.total_item_count||0} item · ${counts.CROP||0} alohida ekin · ${counts.AGGREGATE||0} agregat · ${counts.PRODUCT_FORM||0} mahsulot shakli · ${(countries.countries||[]).length} hudud`);
    if(cropSelect.value&&countrySelect.value)await loadGlobalSeries();
    if(!uzbRecord)toast(status,'FAOSTAT bazasida UZB qatori topilmadi. Rasmiy SIAT havolalari ma’lumotlar bo‘limida mavjud.');
  }catch(e){toast(status,`FAOSTAT katalogi yuklanmadi: ${e.message}`);}
}

async function loadGlobalSeries(){
  const country=$('global-country').value;
  const crop=$('global-crop').value;
  const start=Number($('global-start-year').value)||1961;
  const end=Number($('global-end-year').value)||2024;
  const status=$('global-data-status');
  if(!country||!crop){toast(status,'Mamlakat va ekinni tanlang.');return;}
  if(start>end){toast(status,'Boshlanish yili tugash yilidan katta bo‘lishi mumkin emas.');return;}
  toast(status,'Tarixiy qator olinmoqda…');
  $('global-prediction-result').textContent='';
  try{
    const data=await api(`/global-crops/series/${encodeURIComponent(country)}/${encodeURIComponent(crop)}?start_year=${start}&end_year=${end}`);
    const rows=data.series||[];
    $('global-crop-summary').innerHTML=[
      ['Mavjud yillar',rows.length],
      ['Birinchi yil',rows.length?rows[0].year:'—'],
      ['Oxirgi yil',rows.length?rows[rows.length-1].year:'—'],
      ['Manba','FAOSTAT QCL']
    ].map(([label,value])=>`<article class="kpi-card"><small>${escapeHtml(label)}</small><strong>${escapeHtml(value)}</strong></article>`).join('');
    $('global-crop-table').innerHTML=rows.length?`<table><thead><tr><th>Yil</th><th>Hosil maydoni (ha)</th><th>Ishlab chiqarish (t)</th><th>Hosildorlik (t/ha)</th><th>Flag</th></tr></thead><tbody>${rows.map(row=>`<tr><td>${row.year}</td><td>${fmt(row.harvested_area_ha,0)}</td><td>${fmt(row.production_t,0)}</td><td>${fmt(row.yield_t_ha,3)}</td><td>${escapeHtml([row.area_flag,row.production_flag,row.yield_flag].filter(Boolean).join(' / ')||'—')}</td></tr>`).join('')}</tbody></table>`:'<div class="empty-state">Tanlangan mamlakat va ekin uchun shu davrda mos kuzatuv topilmadi.</div>';
    toast(status,`Tarixiy ma’lumot tayyor · ${country} · ${crop} · ${rows.length} yillik yozuv · FAOSTAT`);
  }catch(e){toast(status,e.message);}
}

async function runGlobalYieldForecast(){
  const country=$('global-country').value;
  const crop=$('global-crop').value;
  const target=Number($('global-end-year').value)||2024;
  const selectedType=$('global-crop').selectedOptions[0]?.dataset.itemType;
  if(selectedType&&selectedType!=='CROP'){
    $('global-prediction-result').textContent='Prognoz faqat alohida ekin itemlari uchun mavjud. Agregat va mahsulot shakllari tarixiy tahlil uchun saqlanadi.';
    return;
  }
  if(!country||!crop){toast($('global-data-status'),'Mamlakat va ekinni tanlang.');return;}
  const result=$('global-prediction-result');
  result.textContent='Tarixiy trend ssenariysi hisoblanmoqda…';
  try{
    const r=await api('/global-predictions/yield',{method:'POST',headers:authHeaders(),body:JSON.stringify({country_iso3:country,crop_code:crop,target_year:target+1})});
    result.innerHTML=`<div class="notice"><b>${escapeHtml(r.prediction_type)}</b><p>Maqsadli yil: ${r.target_year} · Prognoz ssenariysi: <b>${fmt(r.predicted_yield_t_ha,3)} t/ha</b></p><p>Oxirgi kuzatilgan yil: ${r.last_observed_year} · Mamlakat qatori: ${r.country_observed_years} yil · Global qator: ${r.global_observed_years} yil</p><p>OOF MAE: ${fmt(r.oof_mae_t_ha,3)} t/ha · Persistence MAE: ${fmt(r.persistence_oof_mae_t_ha,3)} t/ha · ${escapeHtml(r.beats_persistence?'Persistence’dan yaxshi':'Persistence’dan yaxshi emas')}</p><p>${escapeHtml(r.limitations||'')}</p><small>Bu baseline trend ssenariysi, tasdiqlangan global hosil prognozi emas.</small></div>`;
  }catch(e){result.textContent=e.message;}
}

$('global-item-type').addEventListener('change',()=>{globalCropCatalogLoaded=false;loadGlobalCropCatalog();});
$('refresh-global-crops').addEventListener('click',()=>{globalCropCatalogLoaded=false;loadGlobalCropCatalog();});
$('load-global-series').addEventListener('click',loadGlobalSeries);
$('global-yield-forecast').addEventListener('click',runGlobalYieldForecast);

function applyUzbekCropSeason(){
  const code=String($('crop-code').value||'').trim().toUpperCase();
  const season=UZB_CROP_SEASONS[code];
  if(!season)return;
  $('season-start').value=season[0];
  $('season-end').value=season[1];
}
$('crop-code').addEventListener('change',applyUzbekCropSeason);

async function boot(){try{
  const h=await api('/health');
  const worker=h.background_worker||{};
  const workerLabel=worker.status==='ONLINE'?'worker online':'worker OFFLINE';
  $('server-status').textContent=`API online · DB ${h.database||'unknown'} · ${workerLabel}`;
}catch(e){$('server-status').textContent='API server ulanmagan';}
initMap();loadSources();$('sentinel2-end-date').value=new Date().toISOString().slice(0,10);
if(token){setAuthUI({email:'Hisobga ulangan'});await loadLocations();await loadDatasets();}else setAuthUI(null);}
boot();
