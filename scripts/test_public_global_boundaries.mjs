import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),"..");
const dir=path.join(root,"docs","data","boundaries","global");
const manifestPath=path.join(dir,"manifest.json");
assert.ok(fs.existsSync(manifestPath),"global geoBoundaries manifest is missing");
const manifest=JSON.parse(fs.readFileSync(manifestPath,"utf8"));
assert.equal(manifest.dataset,"geoBoundaries gbOpen + World Bank fallback");
assert.equal(manifest.release_type,"gbOpen with World Bank fallback");
assert.equal(manifest.world_bank_fallback?.license,"CC BY 4.0");
assert.ok(manifest.world_bank_fallback?.service_url,"World Bank feature service metadata is missing");
assert.equal(manifest.world_bank_fallback?.catalog_updated,"2026-10-21");
assert.ok(manifest.countries&&Object.keys(manifest.countries).length>100,
  "global manifest should include more than 100 countries/territories");
assert.deepEqual(manifest.availability_catalog?.levels,["ADM0","ADM1","ADM2","ADM3","ADM4","ADM5"],
  "the catalog must report country-specific ADM0–ADM5 availability");
assert.ok(manifest.availability_catalog?.country_count>100,
  "ADM availability catalog should cover more than 100 countries/territories");
assert.ok(manifest.availability_catalog?.country_level_records>manifest.availability_catalog?.country_count,
  "ADM availability catalog should contain multiple country-level records");
for(const [iso,country] of Object.entries(manifest.countries)){
 assert.ok(Array.isArray(country.available_levels),iso+" must expose available_levels");
 assert.ok(country.availability_levels&&typeof country.availability_levels==="object",iso+" must expose availability_levels");
 const sorted=country.available_levels.slice().sort((a,b)=>Number(a.slice(-1))-Number(b.slice(-1)));
 assert.deepEqual(country.available_levels,sorted,iso+" ADM levels must be ordered");
 assert.equal(country.max_available_level,country.available_levels.at(-1)||null,iso+" max ADM level must match its level list");
 for(const level of country.available_levels)assert.match(level,/^ADM[0-5]$/,iso+" contains an unsupported ADM level");
}
for(const level of ["ADM1","ADM2"]){
 const summary=manifest.level_summary?.[level];
 assert.ok(summary?.country_count>=240,level+" country coverage is unexpectedly small after World Bank fallback");
 assert.ok(summary?.feature_count>summary.country_count,level+" polygon count is inconsistent");
}
const fallbackCounts=manifest.world_bank_fallback?.added_by_level;
assert.ok(fallbackCounts?.ADM1?.country_count>=40 && fallbackCounts?.ADM2?.country_count>=60,
  "World Bank fallback did not add the expected missing country/level packages");
for(const level of ["ADM1","ADM2"]){
 const fallback=Object.entries(manifest.countries).find(([,country])=>country.levels?.[level]?.is_global_composite_fallback);
 assert.ok(fallback,level+" World Bank fallback feature package is missing");
 const [fallbackIso,fallbackCountry]=fallback;
 const info=fallbackCountry.levels[level];
 const payload=JSON.parse(fs.readFileSync(path.join(root,"docs","data",info.file),"utf8"));
 assert.equal(payload.metadata.country_iso3,fallbackIso);
 assert.equal(payload.metadata.admin_level,level);
 assert.equal(payload.metadata.source,"World Bank Official Boundaries (WB-GAD)");
 assert.equal(payload.metadata.license,"CC BY 4.0");
 assert.ok(payload.features.length>0);
 }
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
