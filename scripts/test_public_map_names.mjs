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
 assert.deepEqual(unmapped,[],level+" contains non-localized names: "+unmapped.join(", "));
 console.log("PASS UZB "+level+": "+count+" Uzbek-localized names");
}

const andijan=regionFeatureName({properties:{shapeName:"Andijan Region",shapeType:"ADM1"}});
const chilanzar=regionFeatureName({properties:{shapeName:"Chilanzar",shapeType:"ADM2"}});
const tashkentCity=regionFeatureName({properties:{shapeName:"Tashkent",shapeType:"ADM1"}});
assert.equal(andijan,"Andijon viloyati");
assert.equal(chilanzar,"Chilonzor tumani");
assert.equal(tashkentCity,"Toshkent shahri");
assert.ok(normalizeRegionSearch(chilanzar).includes(normalizeRegionSearch("Chilonzor")));
assert.ok(normalizeRegionSearch("Qoraqalpog‘iston").includes(normalizeRegionSearch("Qoraqalpogiston")));

console.log("PASS: "+checked+" ADM names are localized and Uzbek search aliases resolve.");
