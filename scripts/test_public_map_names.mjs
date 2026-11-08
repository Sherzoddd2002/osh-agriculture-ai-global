import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here=path.dirname(fileURLToPath(import.meta.url));
const docs=path.join(here,"..","docs");
const html=fs.readFileSync(path.join(docs,"index.html"),"utf8");

function extractFunction(name){
 const start=html.indexOf("function "+name+"(");
 assert.notEqual(start,-1,"missing function "+name);
 const braceStart=html.indexOf("{",start);
 let depth=0,quote="",escaped=false,template=false;
 for(let i=braceStart;i<html.length;i+=1){
  const char=html[i];
  if(quote){if(escaped)escaped=false;else if(char==="\\")escaped=true;else if(char===quote)quote="";continue;}
  if(template){if(escaped)escaped=false;else if(char==="\\")escaped=true;else if(char==="\`")template=false;continue;}
  if(char==="'"||char==='"'){quote=char;continue;}
  if(char==="\`"){template=true;continue;}
  if(char==="{")depth+=1;
  else if(char==="}"){depth-=1;if(depth===0)return html.slice(start,i+1);}
 }
 throw new Error("unbalanced function: "+name);
}

const nameObject=html.match(/const UZB_ADMIN_NAMES=(\{[\s\S]*?\n\});/);
assert.ok(nameObject,"UZB Uzbek names dictionary is missing");
const source=[
 nameObject[0],
 extractFunction("normalizeRegionSearch"),
 extractFunction("regionFeatureName"),
 "\nreturn {normalizeRegionSearch,regionFeatureName};",
].join("\n");
const {normalizeRegionSearch,regionFeatureName}=new Function(source)();

const resetHelperSource=extractFunction("clearYieldInputOnContextChange");
assert.match(extractFunction("selectRegionFeature"),/clearYieldInputOnContextChange/,
 "changing the selected ADM/custom area must invalidate the previous CSV");
assert.match(extractFunction("syncCropSelection"),/clearYieldInputOnContextChange/,
 "changing the selected crop must invalidate the previous CSV");
const resetElements={
 "region-yield-file":{files:[{name:"old-district.csv"}],value:"old-district.csv"},
 "region-model-result":{textContent:""}
};
const resetHelper=new Function("$",resetHelperSource+"\nreturn clearYieldInputOnContextChange;")(
 id=>resetElements[id]
);
resetHelper("Hudud tanlovi o‘zgardi.");
assert.equal(resetElements["region-yield-file"].value,"",
 "a stale CSV file must be cleared when the selected area/crop changes");
assert.match(resetElements["region-model-result"].textContent,/qayta tanlang/,
 "the user must be told to choose a CSV for the new area/crop");

const adm1Payload=JSON.parse(fs.readFileSync(path.join(docs,"data","boundaries","UZB_ADM1.geojson"),"utf8"));
const officialYield=JSON.parse(fs.readFileSync(path.join(docs,"data","official-yield","UZB_ADM1_WHEA_2010_2024.json"),"utf8"));
assert.equal(officialYield.regions.length,13,"SIAT wheat source should cover 13 agricultural provinces");
const geoNames=new Set(adm1Payload.features.map(feature=>normalizeRegionSearch(regionFeatureName(feature))));
for(const region of officialYield.regions){
 assert.ok(
  geoNames.has(normalizeRegionSearch(region.name_uz)),
  "SIAT province does not match any localized ADM1 boundary: "+region.name_uz
 );
}
const expected={ADM1:14,ADM2:199};
let checked=0;
for(const [level,count] of Object.entries(expected)){
 const file=path.join(docs,"data","boundaries","UZB_"+level+".geojson");
 const payload=JSON.parse(fs.readFileSync(file,"utf8"));
 assert.equal(payload.features.length,count,level+" boundary count");
 const unmapped=[];
 for(const feature of payload.features){
  const raw=feature.properties?.shapeName||"";
  const display=regionFeatureName(feature);
  if(!display||display===raw)unmapped.push(raw);
  checked+=1;
 }
 if(unmapped.length)console.error("UNMAPPED "+level+":",unmapped.join(" | "));
 assert.deepEqual(unmapped,[],level+" contains non-localized names: "+unmapped.join(", "));
 console.log("PASS UZB "+level+": "+count+" Uzbek-localized names");
}

const officialNamesMatch=html.match(/const OFFICIAL_WHEAT_ADM1_NAMES=(\[[\s\S]*?\]);/);
assert.ok(officialNamesMatch,"official ADM1 wheat allow-list is missing");
const gateSource=[
 nameObject[0],
 extractFunction("normalizeRegionSearch"),
 extractFunction("regionFeatureName"),
 officialNamesMatch[0],
 'let selectedAOI=null;let selectedCrop="whea";function $(id){return {value:selectedCrop};}',
 extractFunction("canUseOfficialProvinceWheat"),
 'return {check:()=>canUseOfficialProvinceWheat(),setArea:value=>{selectedAOI=value;},setCrop:value=>{selectedCrop=value;}};'
].join("\n");
const gate=new Function(gateSource)();
gate.setArea({properties:{shapeName:"Andijan Region",shapeType:"ADM1"}});
assert.equal(gate.check(),true,"Andijan ADM1 wheat should use official SIAT");
gate.setArea({properties:{shapeName:"Tashkent",shapeType:"ADM1"}});
assert.equal(gate.check(),false,"Tashkent city has no official province wheat time series");
gate.setArea({properties:{shapeName:"Andijan Region",shapeType:"ADM2"}});
assert.equal(gate.check(),false,"districts must not inherit province yield");
gate.setArea({properties:{shapeName:"Andijan Region",shapeType:"ADM1"}});
gate.setCrop("cott");
assert.equal(gate.check(),false,"non-wheat crops must require their own yield data");
gate.setCrop("whea");
gate.setArea({properties:{shapeName:"Custom field"}});
assert.equal(gate.check(),false,"custom AOIs must require user-provided yield data");

const andijan=regionFeatureName({properties:{shapeName:"Andijan Region",shapeType:"ADM1"}});
const chilanzar=regionFeatureName({properties:{shapeName:"Chilanzar",shapeType:"ADM2"}});
const tashkentCity=regionFeatureName({properties:{shapeName:"Tashkent",shapeType:"ADM1"}});
assert.equal(andijan,"Andijon viloyati");
assert.equal(chilanzar,"Chilonzor tumani");
assert.equal(tashkentCity,"Toshkent shahri");
assert.ok(normalizeRegionSearch(chilanzar).includes(normalizeRegionSearch("Chilonzor")));
assert.ok(normalizeRegionSearch("Qoraqalpog‘iston").includes(normalizeRegionSearch("Qoraqalpogiston")));

const centerSource=[
 extractFunction("regionGeometryPositions"),
 extractFunction("regionRingCentroid"),
 extractFunction("regionPolygonCentroid"),
 extractFunction("regionCenter"),
 "\nreturn {regionCenter};",
].join("\n");
const {regionCenter}=new Function(centerSource)();
const rectangle={type:"Feature",properties:{},geometry:{type:"Polygon",coordinates:[[[0,0],[4,0],[4,2],[0,2],[0,0]]]}};
const rectangleCenter=regionCenter(rectangle);
assert.ok(Math.abs(rectangleCenter.lon-2)<1e-10);
assert.ok(Math.abs(rectangleCenter.lat-1)<1e-10);
const multi={type:"Feature",properties:{},geometry:{type:"MultiPolygon",coordinates:[
 [[[0,0],[2,0],[2,2],[0,2],[0,0]]],
 [[[8,0],[10,0],[10,2],[8,2],[8,0]]],
]}};
const multiCenter=regionCenter(multi);
assert.ok(Math.abs(multiCenter.lon-5)<1e-10);
assert.ok(Math.abs(multiCenter.lat-1)<1e-10);

console.log("PASS: "+checked+" ADM names are localized and Uzbek search aliases resolve.");
