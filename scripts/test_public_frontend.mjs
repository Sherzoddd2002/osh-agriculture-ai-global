import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),"..");
const docs=path.join(root,"docs");
const frontend=path.join(root,"frontend");
const page=fs.readFileSync(path.join(docs,"index.html"),"utf8");
const sourceHtml=fs.readFileSync(path.join(frontend,"index.html"),"utf8");
const app=fs.readFileSync(path.join(docs,"app.js"),"utf8");
const i18n=fs.readFileSync(path.join(docs,"i18n.js"),"utf8");
const css=fs.readFileSync(path.join(docs,"styles.css"),"utf8");

for(const id of ["view-overview","view-regions","view-forecast","view-models","view-environment","view-data","language-select","auth-open","global-crop","global-yield-forecast"]){
 assert.ok(page.includes('id="'+id+'"'),"full app page is missing "+id);
}
for(const label of ["O‘zbekcha","English","Русский"]){
 assert.ok(page.includes(label),"language selector is missing "+label);
}
assert.ok(page.includes("window.OSH_API_BASE"),"Pages API origin was not injected");
assert.ok(page.includes("https://osh-agriculture-ai-global.fly.dev"),"Pages API origin does not match fly.toml");
assert.ok(page.includes('src="./app.js"')&&page.includes('src="./i18n.js"')&&page.includes('href="./styles.css"'),
 "Pages app assets must use relative URLs");
assert.ok(!page.includes('src="/app.js"')&&!page.includes('href="/styles.css"'),
 "absolute root paths break GitHub Pages project URLs");
assert.ok(app.includes("const API_BASE = String(window.OSH_API_BASE || '')"),"app does not support Pages/Fly API base");
assert.ok(app.includes("./data/boundaries/global/"),"full app does not use global static boundaries");
assert.ok(app.includes("./data/boundaries/"),"full app does not use the validated UZB boundary bundle");
assert.ok(app.includes("refreshBoundaryAvailability"),"country-specific ADM availability UI is missing");
assert.ok(app.includes("availability_levels"),"app does not read country ADM availability metadata");
assert.ok(app.includes("persistPendingAOI")&&app.includes("restorePendingAOI"),"drawn AOI is not persisted/restored");
assert.ok(app.includes("/global-raster-summary/mapspam"),"custom AOI raster summary is not wired to the zonal endpoint");
const aoiAnalysisStart=app.indexOf("async function analyzeCustomAOI()");
const aoiAnalysisEnd=app.indexOf("$('analyze-aoi-mapspam')",aoiAnalysisStart);
assert.ok(aoiAnalysisStart>=0&&aoiAnalysisEnd>aoiAnalysisStart,"custom AOI analysis function is missing");
assert.ok(!app.slice(aoiAnalysisStart,aoiAnalysisEnd).includes("if(!token)"),"public custom AOI raster analysis must not require login");
assert.ok(page.includes("ochiq MAPSPAM 2020 raster hisobi"),"account modal must explain that public AOI analysis is available without login");
assert.ok(app.includes("dataset_id")&&app.includes("location_id"),"dataset-to-location model scope is not surfaced");
for(const id of ["boundary-level-status","aoi-profile","aoi-crop-code","analyze-aoi-mapspam"]){
 assert.ok(page.includes('id="'+id+'"'),"full app page is missing "+id);
}
assert.ok(i18n.includes('["uz", "en", "ru"]')||i18n.includes('["uz","en","ru"]'),
 "the app must retain the supported Uzbek/English/Russian language selector");
assert.ok(css.includes("url('./assets/hero-field.jpg')"),"hero image path is not relative");

const sourceLangCount=(sourceHtml.match(/<option value="/g)||[]).length;
assert.ok(sourceLangCount>=3,"frontend source must retain language choices");
for(const file of ["app.js","i18n.js","styles.css","assets/hero-field.jpg"]){
 assert.ok(fs.existsSync(path.join(docs,file)),"Pages artifact is missing "+file);
}
for(const script of ["app.js","i18n.js"]){
 const result=spawnSync("node",["--check",path.join(docs,script)],{encoding:"utf8"});
 assert.equal(result.status,0,script+" syntax check failed: "+result.stderr);
}
const staticDemo=fs.readFileSync(path.join(docs,"static-demo.html"),"utf8");
assert.ok(staticDemo.includes("Maydon tahlili"),"previous static showcase was not preserved separately");
console.log("PASS full Pages frontend: 6 views, 3-language selector, Fly API config, global ADM bundles and preserved static showcase");
