import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),"..");
const html=fs.readFileSync(path.join(root,"docs","index.html"),"utf8");
assert.ok(html.includes('id="map"'),"map container is missing");
assert.ok(html.includes('id="region-load"'),"ADM boundary loader is missing");
assert.ok(html.includes('id="region-draw-start"'),"custom field drawing is missing");
assert.ok(html.includes('id="region-draw-undo"'),"custom field undo control is missing");
assert.ok(html.includes('id="region-area"'),"selected area measurement is missing");
assert.ok(html.includes('id="country-data-status"')&&html.includes('id="country-data-insights"'),"dynamic country data coverage panel is missing");
assert.ok(html.includes("loadPublicBoundaryManifest")&&html.includes("loadPublicMapspamManifest"),"country boundary/MAPSPAM coverage manifests are not wired");
assert.ok(html.includes("regionRingAreaM2")&&html.includes("regionAreaHa"),"custom field area calculation is missing");
const ids=[...html.matchAll(/\\bid=["']([^"']+)["']/g)].map(match=>match[1]);
const duplicateIds=[...new Set(ids.filter((id,index)=>ids.indexOf(id)!==index))];
assert.deepEqual(duplicateIds,[],"HTML contains duplicate element IDs");
assert.ok(html.includes('id="region-analyze"'),"area analysis control is missing");
assert.ok(html.includes('id="region-run-model"'),"yield scenario control is missing");
assert.ok(html.includes("./data/boundaries/global/"),"country ADM bundle path is missing");
assert.ok(!/fly\.dev|OSH_API_BASE/i.test(html),"public Pages html must not call Fly or expose a private API origin");
assert.ok(html.includes("renderMapspamReference"),"selected-area MAPSPAM view is missing");
assert.ok(html.includes("fetchYieldClimateHistory"),"observed-yield climate ML workflow is missing");
assert.ok(html.includes('const modelButton=$("region-run-model");')&&html.includes('if(center&&modelButton&&!modelButton.disabled)modelButton.click();'),"an available official area prediction must start when an area is selected");
assert.ok(html.includes('if(selectedAOI&&modelButton&&!modelButton.disabled)modelButton.click();'),"available prediction must refresh when crop or CSV input changes");
assert.ok(html.includes('loadPublicMapspamCountry'),"country-level MAPSPAM loader is missing");
assert.ok(html.includes('./data/mapspam/global/"+iso+".json.gz'),"country-level MAPSPAM package path is missing");
assert.ok(html.includes("top_crops:top"),"selected-area crop insight summary is missing");
assert.ok(!/FAOSTAT/i.test(html),"non-cleared national time-series source must not be exposed in the public showcase");
assert.ok(html.includes("Qo‘lda chizilgan maydon"),"custom AOI guidance is missing");
assert.ok(html.includes("NO_RASTER_CELLS"),"missing raster support must remain NULL, not zero");
const inline=[...html.matchAll(/<script>([\s\S]*?)<\/script>/gi)];
assert.equal(inline.length,1,"expected one inline application script");
const tmp=path.join(root,".static-demo-check.js");
try {
 fs.writeFileSync(tmp,inline[0][1],"utf8");
} finally {
 const {spawnSync}=await import("node:child_process");
 const result=spawnSync("node",["--check",tmp],{encoding:"utf8"});
 fs.rmSync(tmp,{force:true});
 assert.equal(result.status,0,result.stderr||"inline app syntax check failed");
}
console.log("PASS public static demo: map, global ADM, custom AOI, selected-area insights, ML controls and no Fly dependency");
