const API = '/api/v1';
const $ = (id) => document.getElementById(id);
let token = localStorage.getItem('osh_global_token') || '';
let map = null, boundaryFeatures = [], selectedFeature = null, selectedLocationId = null, currentDatasetId = null, currentJobId = null, currentClimateJobId = null;
let drawingAOI = false, drawingPoints = [];
const locations = [];

function authHeaders(json=true){const h={};if(json)h['Content-Type']='application/json';if(token)h.Authorization=`Bearer ${token}`;return h;}
async function api(path, options={}){
  const res=await fetch(API+path,options);
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
function openView(name){document.querySelectorAll('.view').forEach(v=>v.classList.toggle('active',v.id===`view-${name}`));document.querySelectorAll('.nav-item').forEach(b=>b.classList.toggle('active',b.dataset.view===name));const labels={overview:'Bosh sahifa',regions:'Hududiy tahlil',forecast:'Hosildorlik prognozi',models:'Model laboratoriyasi',environment:'Iqlim va tuproq',data:'Ma’lumotlar va hisobotlar'};$('page-title').textContent=labels[name]||'OSH Global';if(name==='regions'&&map)setTimeout(()=>map.resize(),100);if(name==='environment'){loadSources();if(token&&selectedLocationId)loadClimate(selectedLocationId);}if(name==='data'){loadDatasets();loadGlobalCropCatalog();}if(name==='forecast')loadDatasets();}

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
    center: [18, 18],
    zoom: 1.12,
    minZoom: 0.85,
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
    drawingPoints.push([Number(event.lngLat.lng.toFixed(7)),Number(event.lngLat.lat.toFixed(7))]);
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
  selectFeature(customFeature);
  $('selected-level').textContent='CUSTOM AOI';
  $('selected-area-help').textContent='Foydalanuvchi chizgan poligon. U ma’muriy chegara emas; rastr ma’lumotlari pixel resolution va qamroviga qarab baholanadi.';
  toast($('boundary-status'),'Maydon tanlandi. Endi hisobga kirib, “Hududni saqlash va tahlil qilish” tugmasini bosing.');
}
$('draw-aoi-start').addEventListener('click',startAOIDrawing);
$('draw-aoi-finish').addEventListener('click',finishAOIDrawing);
$('draw-aoi-cancel').addEventListener('click',cancelAOIDrawing);

function featureName(f){const p=f?.properties||{};return p.shapeName||p.shape_name||p.shapeNameEn||p.NAME_1||p.NAME_2||p.name||p.NAME||p.admin||'Tanlangan hudud';}
function coordsCenter(geom){let x=0,y=0,n=0;const walk=v=>{if(Array.isArray(v)&&typeof v[0]==='number'&&typeof v[1]==='number'){x+=v[0];y+=v[1];n++;}else if(Array.isArray(v))v.forEach(walk);};walk(geom.coordinates);return n?{lat:y/n,lon:x/n}:null;}
function featureBounds(features){let minX=180,minY=90,maxX=-180,maxY=-90;const walk=v=>{if(Array.isArray(v)&&typeof v[0]==='number'&&typeof v[1]==='number'){minX=Math.min(minX,v[0]);maxX=Math.max(maxX,v[0]);minY=Math.min(minY,v[1]);maxY=Math.max(maxY,v[1]);}else if(Array.isArray(v))v.forEach(walk);};features.forEach(f=>walk(f.geometry?.coordinates));return minX<=maxX?[[minX,minY],[maxX,maxY]]:null;}
function selectFeature(f){
  if(!f) return;
  selectedFeature=f;
  $('selected-area-name').textContent=featureName(f);
  $('selected-area-help').textContent='Tanlangan chegara geoBoundaries GeoJSON polygonidan olindi.';
  $('selected-country').textContent=$('country-iso3').value.toUpperCase();
  $('selected-level').textContent=$('admin-level').value;
  const center=coordsCenter(f.geometry);
  $('selected-center').textContent=center? `${center.lat.toFixed(4)}, ${center.lon.toFixed(4)}` : '—';
  $('save-location').disabled=!selectedFeature;
  $('save-location').textContent=token?'Hududni saqlash va tahlil qilish':'Kirish va hududni saqlash';

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

async function loadBoundaries(){const code=$('country-iso3').value.trim().toUpperCase(),level=$('admin-level').value;const status=$('boundary-status');if(!/^[A-Z]{3}$/.test(code)){toast(status,'ISO-3 kodini kiriting (masalan UZB, KAZ, DEU).');return;}toast(status,'Chegaralar olinmoqda…');try{const data=await api(`/boundaries/${code}/${level}`);boundaryFeatures=data.features||[];selectedFeature=null;loadMapspamSummaries();$('selected-area-name').textContent='Hududni tanlang';$('selected-country').textContent=code;$('selected-level').textContent=level;$('selected-center').textContent='—';$('save-location').disabled=true;if(map?.getSource('admin-boundaries'))map.getSource('admin-boundaries').setData({type:'FeatureCollection',features:boundaryFeatures.map((f,i)=>({...f,properties:{...(f.properties||{}),__idx:i}}))});if(boundaryFeatures.length&&map){const bounds=featureBounds(boundaryFeatures);if(bounds)map.fitBounds(bounds,{padding:42,maxZoom:level==='ADM0'?4:7,duration:900});}toast(status,`${boundaryFeatures.length} ta chegara yuklandi · ${data.metadata?.source||'geoBoundaries'}`);}catch(e){toast(status,e.message);}}
$('load-boundaries').addEventListener('click',loadBoundaries);

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
    toast(status,'Bu maxsus chizilgan dala poligoni. MAPSPAM faqat bazada oldindan bog‘langan ADM0–ADM2 hududlari uchun mavjud; dala darajasidagi tahlil uchun Sentinel-2 10 m zonal statistikasi kerak.');
    $('mapspam-context').textContent=countryCode+' · '+featureName(selectedFeature)+' · CUSTOM AOI';
    table.innerHTML='';
    return;
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

$('country-iso3').addEventListener('keydown',e=>{if(e.key==='Enter')loadBoundaries();});

$('save-location').addEventListener('click',async()=>{if(!selectedFeature)return;if(!token){toast($('saved-location-status'),'Maydon tanlandi. Saqlash va tahlil qilish uchun hisobga kiring yoki ro‘yxatdan o‘ting.');openAuth();return;}try{const code=$('country-iso3').value.toUpperCase(),level=selectedFeature.properties?.__custom_aoi?'CUSTOM':$('admin-level').value;const payload={country_iso3:code,name:featureName(selectedFeature),admin_level:level,climate_start_year:Number($('climate-start-year').value)||2010,geojson:selectedFeature,source:selectedFeature.properties?.__custom_aoi?'User-drawn AOI':'geoBoundaries gbOpen'};toast($('saved-location-status'),'Hudud saqlanmoqda va iqlim tahlili navbatga qo‘yilmoqda…');const res=await api('/locations',{method:'POST',headers:authHeaders(),body:JSON.stringify(payload)});selectedLocationId=res.id;toast($('saved-location-status'),`Hudud saqlandi · ${res.name}. Yillik iqlim job #${res.climate_job_id} boshlandi.`);await loadLocations();$('location-select').value=String(res.id);$('environment-location-select').value=String(res.id);pollClimateJob(res.climate_job_id,res.id);}catch(e){toast($('saved-location-status'),e.message);}});

function openAuth(){$('auth-modal').hidden=false;$('auth-message').textContent='';}
function closeAuth(){$('auth-modal').hidden=true;}
$('auth-open').addEventListener('click',()=>token?(logout()):openAuth());$('auth-close').addEventListener('click',closeAuth);
async function authAction(mode){const email=$('auth-email').value.trim(),password=$('auth-password').value;if(!email||!password){toast($('auth-message'),'Email va parolni kiriting.');return;}try{const res=await api(`/auth/${mode}`,{method:'POST',headers:authHeaders(),body:JSON.stringify({email,password})});token=res.access_token;localStorage.setItem('osh_global_token',token);setAuthUI(res.user);closeAuth();await loadLocations();await loadDatasets();}catch(e){toast($('auth-message'),e.message);}}
$('register-button').addEventListener('click',()=>authAction('register'));$('login-button').addEventListener('click',()=>authAction('login'));
function setAuthUI(user){$('user-label').textContent=user?.email||'Mehmon rejimi';$('auth-open').textContent=user?'Chiqish':'Kirish';$('save-location').disabled=!selectedFeature;$('save-location').textContent=user?'Hududni saqlash va tahlil qilish':'Kirish va hududni saqlash';}
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

async function loadDatasets(){if(!token)return;try{const ds=await api('/datasets',{headers:authHeaders(false)});$('dataset-list').innerHTML=ds.length?ds.map(d=>`<div class="dataset-row"><span><b>${escapeHtml(d.name)}</b><small> · ${escapeHtml(d.crop_code)} · ${d.first_year}–${d.last_year} · ${d.row_count} qator</small></span><span class="status-chip">${escapeHtml(d.status)}</span></div>`).join(''):'<div class="empty-state">Hozircha dataset yo‘q.</div>';if(ds.length){$('forecast-dataset').innerHTML=ds.map(d=>`<option value="${d.id}">${escapeHtml(d.name)} · ${d.crop_code}</option>`).join('');if(!currentDatasetId)currentDatasetId=ds[0].id;if(ds.some(d=>d.id===currentDatasetId))$('forecast-dataset').value=String(currentDatasetId);$('process-dataset').disabled=false;}}catch(e){console.warn(e);}}
function escapeHtml(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}

async function startProcessing(){if(!token||!currentDatasetId){toast($('job-list'),'Avval hisobga kiring va dataset yuklang.');return;}try{const j=await api(`/datasets/${currentDatasetId}/process`,{method:'POST',headers:authHeaders()});currentJobId=j.job_id;toast($('job-list'),`Job #${j.job_id}: ${j.status}`);pollJob();}catch(e){toast($('job-list'),e.message);}}
function pollJob(){if(!currentJobId)return;const check=async()=>{try{const j=await api(`/jobs/${currentJobId}`,{headers:authHeaders(false)});const automatic=j.result?.automatic_analysis;$('job-list').innerHTML=`<b>Job #${j.id}</b> · ${j.status} · ${j.progress}%<p>${escapeHtml(j.message||'')}</p>${j.error?`<p class="amber-text">${escapeHtml(j.error)}</p>`:''}${automatic?`<div class="notice"><b>AI model holati:</b> ${escapeHtml(automatic.status)}<br>${escapeHtml(automatic.reason||automatic.note||'')}</div>`:''}${j.result?`<pre>${escapeHtml(JSON.stringify(j.result,null,2))}</pre>`:''}`;if(['COMPLETED','FAILED'].includes(j.status)){if(automatic?.prediction)renderPrediction({...automatic.prediction,dataset_id:currentDatasetId,location:'Tanlangan hudud',crop_code:'Dataset'});loadDatasets();return;}setTimeout(check,3000);}catch(e){toast($('job-list'),e.message);}};check();}
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
    countrySelect.innerHTML=(countries.countries||[]).map(x=>`<option value="${escapeHtml(x.country_iso3)}">${escapeHtml(x.area_name)} · ${escapeHtml(x.country_iso3)}</option>`).join('');
    $('global-start-year').value='1961';
    $('global-end-year').value='2024';
    globalCropCatalogLoaded=true;
    const counts=catalog.item_type_counts||{};
    toast(status,`FAOSTAT katalogi tayyor · ${catalog.total_item_count||0} item · ${counts.CROP||0} alohida ekin · ${counts.AGGREGATE||0} agregat · ${counts.PRODUCT_FORM||0} mahsulot shakli · ${(countries.countries||[]).length} hudud`);
    if(cropSelect.value&&countrySelect.value)await loadGlobalSeries();
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

async function boot(){try{
  const h=await api('/health');
  const worker=h.background_worker||{};
  const workerLabel=worker.status==='ONLINE'?'worker online':'worker OFFLINE';
  $('server-status').textContent=`API online · DB ${h.database||'unknown'} · ${workerLabel}`;
}catch(e){$('server-status').textContent='API server ulanmagan';}
initMap();loadSources();$('sentinel2-end-date').value=new Date().toISOString().slice(0,10);
if(token){setAuthUI({email:'Hisobga ulangan'});await loadLocations();await loadDatasets();}else setAuthUI(null);}
boot();
