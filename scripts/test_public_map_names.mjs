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

const officialCropYield=JSON.parse(fs.readFileSync(path.join(docs,"data","official-yield","UZB_ADM1_CROPS_2010_2024.json"),"utf8"));
assert.equal(officialCropYield.country_iso3,"UZB");
assert.equal(officialCropYield.admin_level,"ADM1");
assert.equal(officialCropYield.license,"CC BY 4.0");
assert.deepEqual(Object.keys(officialCropYield.crops).sort(),["cott","pota"]);
for(const [cropCode,maxYield] of [["pota",200],["cott",20]]){
 const crop=officialCropYield.crops[cropCode];
 assert.equal(crop.crop_code,cropCode);
 assert.equal(crop.license,"CC BY 4.0");
 assert.equal(crop.district_yield_available,false);
 assert.equal(crop.unit,"tonnes per planted hectare");
 assert.equal(crop.regions.length,13);
 for(const region of crop.regions){
  assert.equal(region.records.length,15,cropCode+" must have 2010–2024 for each province");
  assert.deepEqual(region.records.map(row=>row.year),Array.from({length:15},(_,i)=>2010+i));
  for(const row of region.records){
   assert.ok(row.yield>0&&row.yield<maxYield,cropCode+" yield outside broad plausibility bounds");
   assert.ok(row.production_t>0&&row.sown_area_ha>0);
  }
 }
}
const mapspamPath=path.join(docs,"data","mapspam","UZB_MAPSPAM_2020_ADM1_ADM2.json");
assert.ok(fs.existsSync(mapspamPath),"verified MAPSPAM public data package is missing");
const mapspamReference=JSON.parse(fs.readFileSync(mapspamPath,"utf8"));
assert.equal(mapspamReference.dataset_id,"mapspam-2020-v2r2");
assert.equal(mapspamReference.source_year,2020);
assert.equal(mapspamReference.license,"CC BY-SA 4.0");
const cropListStart=html.indexOf("const cropList=[");
assert.notEqual(cropListStart,-1,"website crop list is missing");
const cropListEnd=html.indexOf("\n];",cropListStart);
assert.notEqual(cropListEnd,-1,"website crop list closing bracket is missing");
const cropListLiteral=html.slice(cropListStart+"const cropList=".length,cropListEnd+2);
const publicCropList=new Function("return "+cropListLiteral)();
assert.equal(publicCropList.length,46);
for(const [level,count] of Object.entries({ADM1:14,ADM2:199})){
 const areas=mapspamReference.levels[level].areas;
 assert.equal(Object.keys(areas).length,count,level+" MAPSPAM area count");
 for(const area of Object.values(areas)){
  assert.equal(Object.keys(area.crops).length,46,level+" area must have all 46 crops");
 }
}
const adm1ForMapspam=JSON.parse(fs.readFileSync(path.join(docs,"data","boundaries","UZB_ADM1.geojson"),"utf8"));
const adm2ForMapspam=JSON.parse(fs.readFileSync(path.join(docs,"data","boundaries","UZB_ADM2.geojson"),"utf8"));
const mapspamHarnessSource=[
 nameObject[0],
 "let mapspamReferenceCache=null;let selectedAOI=null;let activeCrop='whea';",
 "const cropList="+cropListLiteral+";",
 "const elements={'region-mapspam-result':{innerHTML:'',textContent:''},'region-crop-select':{}};",
 "Object.defineProperty(elements['region-crop-select'],'value',{get:()=>activeCrop});",
 "function $(id){return elements[id];}",
 "const fetch=(url)=>Promise.resolve({ok:true,json:()=>Promise.resolve(payload)});",
 "function regionEscape(value){return String(value==null?\"\":value);}",
 extractFunction("regionFeatureName"),
 extractFunction("regionFmt"),
 "async "+extractFunction("renderMapspamReference"),
 "return {render:renderMapspamReference,setArea:value=>{selectedAOI=value;},setCrop:value=>{activeCrop=value;},elements};"
].join("\n");
const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
const mapspamHarness=await new AsyncFunction("payload",mapspamHarnessSource)(mapspamReference);
const estimatedEntry=Object.entries(mapspamReference.levels.ADM2.areas).find(([,area])=>area.crops.whea.spatial_status==="ESTIMATED");
assert.ok(estimatedEntry,"at least one district should have a wheat raster estimate");
const [estimatedId,estimatedArea]=estimatedEntry;
const estimatedFeature=adm2ForMapspam.features.find(feature=>feature.properties.shapeID===estimatedId);
assert.ok(estimatedFeature,"estimated district must join to its exact boundary shapeID");
mapspamHarness.setArea(estimatedFeature);
mapspamHarness.setCrop("whea");
const estimatedResult=await mapspamHarness.render(estimatedFeature,"whea");
assert.equal(estimatedResult.status,"ESTIMATED");
assert.ok(estimatedResult.yield>0);
assert.equal(estimatedResult.area,regionFeatureName(estimatedFeature));
assert.ok(mapspamHarness.elements["region-mapspam-result"].innerHTML.includes("t/ha"));
assert.match(mapspamHarness.elements["region-mapspam-result"].innerHTML,new RegExp(regionFeatureName(estimatedFeature)));

const missingEntry=Object.entries(mapspamReference.levels.ADM2.areas).find(([,area])=>area.crops.whea.spatial_status==="NO_RASTER_CELLS");
assert.ok(missingEntry,"district wheat NO_RASTER_CELLS case should be represented");
const [missingId]=missingEntry;
const missingFeature=adm2ForMapspam.features.find(feature=>feature.properties.shapeID===missingId);
mapspamHarness.setArea(missingFeature);
const missingResult=await mapspamHarness.render(missingFeature,"whea");
assert.equal(missingResult.status,"NO_RASTER_CELLS");
assert.ok(mapspamHarness.elements["region-mapspam-result"].innerHTML.includes("NULL / mavjud emas"));
assert.ok(!mapspamHarness.elements["region-mapspam-result"].innerHTML.includes("0.00 t/ha"));

const customFeature={type:"Feature",properties:{shapeName:"Custom field"},geometry:{type:"Polygon",coordinates:[[[0,0],[1,0],[1,1],[0,1],[0,0]]]}};
mapspamHarness.setArea(customFeature);
const customResult=await mapspamHarness.render(customFeature,"whea");
assert.equal(customResult.status,"CUSTOM_AOI");
assert.match(mapspamHarness.elements["region-mapspam-result"].textContent,/Qo‘lda chizilgan maydon/);
console.log("PASS MAPSPAM browser lookup: exact ADM2 shapeID, localized result, estimated yield, NULL handling and custom AOI guard");
assert.equal(officialYield.regions.length,13,"SIAT wheat source should cover 13 agricultural provinces");
const geoNames=new Set(adm1Payload.features.map(feature=>normalizeRegionSearch(regionFeatureName(feature))));
for(const region of officialYield.regions){
 assert.ok(
  geoNames.has(normalizeRegionSearch(region.name_uz)),
  "SIAT province does not match any localized ADM1 boundary: "+region.name_uz
 );
}
for(const cropCode of ["pota","cott"]){
 for(const region of officialCropYield.crops[cropCode].regions){
  assert.ok(
   geoNames.has(normalizeRegionSearch(region.name_uz)),
   "SIAT "+cropCode+" province does not match any localized ADM1 boundary: "+region.name_uz
  );
 }
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

const officialNamesMatch=html.match(/const OFFICIAL_PROVINCE_ADM1_NAMES=(\[[\s\S]*?\]);/);
assert.ok(officialNamesMatch,"official ADM1 province allow-list is missing");
const officialCropsMatch=html.match(/const OFFICIAL_PROVINCE_CROP_CONFIG=(\{[\s\S]*?\n\});/);
assert.ok(officialCropsMatch,"official province crop configuration is missing");
const gateSource=[
 nameObject[0],
 extractFunction("normalizeRegionSearch"),
 extractFunction("regionFeatureName"),
 officialNamesMatch[0],
 officialCropsMatch[0],
 'let selectedAOI=null;let selectedCrop="whea";function $(id){return {value:selectedCrop};}',
 extractFunction("canUseOfficialProvinceCrop"),
 'return {check:()=>canUseOfficialProvinceCrop(),setArea:value=>{selectedAOI=value;},setCrop:value=>{selectedCrop=value;}};'
].join("\n");
const gate=new Function(gateSource)();
gate.setArea({properties:{shapeName:"Andijan Region",shapeType:"ADM1"}});
for(const cropCode of ["whea","pota","cott"]){
 gate.setCrop(cropCode);
 assert.equal(gate.check(),true,"Andijan ADM1 "+cropCode+" should use its official SIAT series");
}
gate.setArea({properties:{shapeName:"Tashkent",shapeType:"ADM1"}});
assert.equal(gate.check(),false,"Tashkent city has no agricultural province crop forecast series");
gate.setArea({properties:{shapeName:"Andijan Region",shapeType:"ADM2"}});
for(const cropCode of ["whea","pota","cott"]){
 gate.setCrop(cropCode);
 assert.equal(gate.check(),false,"districts must not inherit ADM1 "+cropCode+" yield");
}
gate.setArea({properties:{shapeName:"Andijan Region",shapeType:"ADM1"}});
gate.setCrop("rice");
assert.equal(gate.check(),false,"other crops must require their own authentic yield data");
gate.setCrop("pota");
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
