import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),"..");
const docs=path.join(root,"docs");
const frontend=path.join(root,"frontend");
const sourceHtml=fs.readFileSync(path.join(frontend,"index.html"),"utf8");
const sourceApp=fs.readFileSync(path.join(frontend,"app.js"),"utf8");
const sourceI18n=fs.readFileSync(path.join(frontend,"i18n.js"),"utf8");
const sourceCss=fs.readFileSync(path.join(frontend,"styles.css"),"utf8");

for(const id of [
  "view-overview","view-regions","view-forecast","view-models",
  "view-environment","view-data","language-select","auth-open",
  "global-crop","global-yield-forecast","uzb-admin-filter","uzb-admin-unit",
  "boundary-level-status","aoi-profile","aoi-crop-code","analyze-aoi-mapspam",
  "uzb-official-crop","uzb-official-region","uzb-official-yield-table"
]){
  assert.ok(sourceHtml.includes('id="'+id+'"'),"Uzbekistan frontend is missing "+id);
}
for(const label of ["O‘zbekcha","English","Русский"]){
  assert.ok(sourceHtml.includes(label),"language selector is missing "+label);
}
assert.ok(sourceApp.includes("const API_BASE = String(window.OSH_API_BASE || '')"),
  "app does not support Pages/Fly API base");
assert.ok(sourceApp.includes('const UZB_COUNTRY = "UZB"'),
  "public app must be locked to Uzbekistan ISO-3");
assert.ok(sourceApp.includes("UZB_ADMIN_LEVELS"),
  "Uzbekistan ADM1/ADM2 coverage catalogue is missing");
assert.ok(sourceApp.includes("populateUzbAdminSelector"),
  "Uzbekistan province/district selection is missing");
assert.ok(sourceApp.includes("pointInGeometry"),
  "drawn field points are not checked against Uzbekistan boundary geometry");
assert.ok(sourceApp.includes("[64.5, 41.3]"),
  "map should open over Uzbekistan");
assert.ok(sourceApp.includes("UZB_ADM1_WHEA_2010_2024.json") &&
          sourceApp.includes("UZB_ADM1_CROPS_2010_2024.json"),
  "official Uzbekistan SIAT crop snapshots are not wired");
assert.ok(sourceApp.includes("persistPendingAOI")&&sourceApp.includes("restorePendingAOI"),
  "drawn AOI is not persisted/restored");
assert.ok(sourceApp.includes("/global-raster-summary/mapspam"),
  "custom AOI raster summary is not wired to the zonal endpoint");
const aoiAnalysisStart=sourceApp.indexOf("async function analyzeCustomAOI()");
const aoiAnalysisEnd=sourceApp.indexOf("$('analyze-aoi-mapspam')",aoiAnalysisStart);
assert.ok(aoiAnalysisStart>=0&&aoiAnalysisEnd>aoiAnalysisStart,
  "custom AOI analysis function is missing");
assert.ok(!sourceApp.slice(aoiAnalysisStart,aoiAnalysisEnd).includes("if(!token)"),
  "public custom AOI raster analysis must not require login");
assert.ok(sourceApp.includes("dataset_id")&&sourceApp.includes("location_id"),
  "dataset-to-location model scope is not surfaced");
assert.ok(sourceHtml.includes("siat.stat.uz/data/1458/") &&
          sourceHtml.includes("siat.stat.uz/data/2389/"),
  "official SIAT source links are missing");
assert.ok(sourceHtml.includes("gov.uz/oz/agro/pages/geoaxborot-tizimi"),
  "Uzbekistan Ministry geospatial portal is missing");
assert.ok(sourceHtml.includes("data.egov.uz/data/6108023c2a2e256d868e879c"),
  "Uzbekistan crop-yield open-data record is missing");
assert.ok(sourceI18n.includes('["uz", "en", "ru"]') ||
          sourceI18n.includes('["uz","en","ru"]'),
  "the app must retain the Uzbek/English/Russian language selector");
assert.ok(sourceCss.includes("url('./assets/hero-field.jpg')"),
  "hero image path is not relative");

for(const file of ["app.js","i18n.js"]){
  const result=spawnSync("node",["--check",path.join(frontend,file)],{encoding:"utf8"});
  assert.equal(result.status,0,file+" syntax check failed: "+result.stderr);
}

const docsIndex=path.join(docs,"index.html");
if(fs.existsSync(docsIndex)){
  const page=fs.readFileSync(docsIndex,"utf8");
  // During Pages deployment the assembler injects the API base and copies all assets.
  // On a normal PR checkout docs/index.html is still the preserved static showcase.
  if(page.includes("window.OSH_API_BASE")){
    assert.ok(page.includes("https://osh-agriculture-ai-global.fly.dev"),
      "Pages API origin does not match fly.toml");
    assert.ok(page.includes('src="./app.js"')&&page.includes('src="./i18n.js"')&&page.includes('href="./styles.css"'),
      "Pages app assets must use relative URLs");
    assert.ok(!page.includes('src="/app.js"')&&!page.includes('href="/styles.css"'),
      "absolute root paths break GitHub Pages project URLs");
    for(const file of ["app.js","i18n.js","styles.css","assets/hero-field.jpg"]){
      assert.ok(fs.existsSync(path.join(docs,file)),"Pages artifact is missing "+file);
    }
    for(const file of [
      "data/boundaries/UZB_ADM1.geojson",
      "data/boundaries/UZB_ADM2.geojson",
      "data/official-yield/UZB_ADM1_WHEA_2010_2024.json",
      "data/official-yield/UZB_ADM1_CROPS_2010_2024.json"
    ]){
      assert.ok(fs.existsSync(path.join(docs,file)),"Pages artifact is missing Uzbekistan data file "+file);
    }
    const app=fs.readFileSync(path.join(docs,"app.js"),"utf8");
    const i18n=fs.readFileSync(path.join(docs,"i18n.js"),"utf8");
    for(const script of ["app.js","i18n.js"]){
      const result=spawnSync("node",["--check",path.join(docs,script)],{encoding:"utf8"});
      assert.equal(result.status,0,script+" deployed syntax check failed: "+result.stderr);
    }
    assert.ok(app.includes('const UZB_COUNTRY = "UZB"'),
      "assembled Pages app lost Uzbekistan-only country configuration");
    assert.ok(i18n.includes("O‘zbekiston xaritasi"),
      "assembled Pages app lost Uzbekistan locale strings");
  }
}
const staticDemo=path.join(docs,"static-demo.html");
if(fs.existsSync(staticDemo)){
  assert.ok(fs.readFileSync(staticDemo,"utf8").includes("Maydon tahlili"),
    "previous static showcase was not preserved separately");
}
console.log("PASS Uzbekistan frontend contract: UZB map, ADM1/ADM2, field AOI guard, SIAT series, local data sources and 3-language selector");
