import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),"..");
const dir=path.join(root,"docs","data","boundaries","global");
const manifestPath=path.join(dir,"manifest.json");
assert.ok(fs.existsSync(manifestPath),"global geoBoundaries manifest is missing");
const manifest=JSON.parse(fs.readFileSync(manifestPath,"utf8"));
assert.equal(manifest.dataset,"geoBoundaries gbOpen + CGAZ fallback");
assert.equal(manifest.release_type,"gbOpen with CGAZ fallback");
assert.equal(manifest.global_composite_fallback?.license,"CC BY 4.0");
assert.ok(manifest.global_composite_fallback?.source_commit,"CGAZ source revision is not pinned");
assert.ok(manifest.countries&&Object.keys(manifest.countries).length>100,
  "global manifest should include more than 100 countries/territories");
for(const level of ["ADM1","ADM2"]){
 const summary=manifest.level_summary?.[level];
 assert.ok(summary?.country_count>=190,level+" country coverage is unexpectedly small after CGAZ fallback");
 assert.ok(summary?.feature_count>summary.country_count,level+" polygon count is inconsistent");
}
const fallbackSample=Object.entries(manifest.countries).find(([,country])=>
 country.levels?.ADM2?.is_global_composite_fallback
);
assert.ok(fallbackSample,"missing ADM2 packages were not supplemented from CGAZ");
const sample=Object.entries(manifest.countries).find(([,country])=>
 country.levels?.ADM1?.file&&country.levels?.ADM2?.file
);
assert.ok(sample,"at least one country should expose both ADM1 and ADM2 packages");
const [iso,country]=sample;
for(const level of ["ADM1","ADM2"]){
 const info=country.levels[level];
 const file=path.join(root,"docs","data",info.file);
 assert.ok(fs.existsSync(file),iso+"/"+level+" static GeoJSON is missing");
 const payload=JSON.parse(fs.readFileSync(file,"utf8"));
 assert.equal(payload.type,"FeatureCollection");
 assert.equal(payload.metadata.country_iso3,iso);
 assert.equal(payload.metadata.admin_level,level);
 assert.equal(payload.features.length,info.feature_count);
 assert.ok(payload.features.length>0);
 for(const feature of payload.features.slice(0,Math.min(10,payload.features.length))){
  assert.ok(["Polygon","MultiPolygon"].includes(feature.geometry?.type));
  assert.ok(feature.properties?.shapeName);
  assert.equal(feature.properties?.shapeType,level);
  assert.equal(feature.properties?.countryISO3,iso);
 }
}
const html=fs.readFileSync(path.join(root,"docs","index.html"),"utf8");
assert.ok(html.includes("./data/boundaries/global/"),"browser loader is not wired to global country files");
assert.ok(html.includes("metadata.country_iso3!==iso"),"browser loader must verify the selected country code");
console.log("PASS global GeoJSON package: "+manifest.level_summary.ADM1.country_count+
 " ADM1 countries / "+manifest.level_summary.ADM2.country_count+
 " ADM2 countries; browser path verified using "+iso);
