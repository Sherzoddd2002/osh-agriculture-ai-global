import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const html = fs.readFileSync(path.join(here, "..", "docs", "index.html"), "utf8");

function extractFunction(name) {
  const marker = "function " + name + "(";
  const start = html.indexOf(marker);
  assert.notEqual(start, -1, "missing function " + name);
  const braceStart = html.indexOf("{", start);
  let depth = 0;
  let quote = "";
  let escaped = false;
  let template = false;
  for (let i = braceStart; i < html.length; i += 1) {
    const char = html[i];
    if (quote) {
      if (escaped) escaped = false;
      else if (char === "\\") escaped = true;
      else if (char === quote) quote = "";
      continue;
    }
    if (template) {
      if (escaped) escaped = false;
      else if (char === "\\") escaped = true;
      else if (char === "\`") template = false;
      continue;
    }
    if (char === "'" || char === '"') {
      quote = char;
      continue;
    }
    if (char === "\`") {
      template = true;
      continue;
    }
    if (char === "{") depth += 1;
    else if (char === "}") {
      depth -= 1;
      if (depth === 0) return html.slice(start, i + 1);
    }
  }
  throw new Error("unbalanced function body: " + name);
}

const source = [
  extractFunction("parseRegionCsvLine"),
  extractFunction("solveLinearSystem"),
  extractFunction("fitRegionRidge"),
  extractFunction("runRegionRidge"),
].join("\n");
const { parseRegionCsvLine, runRegionRidge } = new Function(
  source + "\nreturn { parseRegionCsvLine, runRegionRidge };"
)();

assert.deepEqual(
  parseRegionCsvLine('year,yield_t_ha,"district, name"', ","),
  ["year", "yield_t_ha", "district, name"],
  "CSV parser should preserve quoted commas"
);
assert.deepEqual(
  parseRegionCsvLine('2020;4,25;"district; name"', ";"),
  ["2020", "4,25", "district; name"],
  "CSV parser should preserve quoted separators"
);

const series = [];
const climateByYear = {};
for (let year = 2008; year <= 2024; year += 1) {
  const yieldValue = 4.2 + 0.025 * (year - 2008) +
    0.12 * Math.sin((year - 2008) * 0.8);
  series.push({ year, yield: Number(yieldValue.toFixed(4)) });
  climateByYear[year] = {
    usable: true,
    tmean: 15 + 0.1 * (year - 2008),
    tmax: 22 + 0.12 * (year - 2008),
    tmin: 8,
    precipitation: 250 + 3 * Math.sin(year),
    et0: 950 + year - 2008,
    gdd: 1400,
    coverage: 0.98,
  };
}

const result = runRegionRidge(series, 2025, climateByYear);
assert.equal(result.rows, 17);
assert.ok(result.oof.length > 0);
assert.ok(Number.isFinite(result.forecast) && result.forecast >= 0);
assert.ok(Number.isFinite(result.mae) && result.mae >= 0);
assert.ok(Number.isFinite(result.persistenceMae) && result.persistenceMae >= 0);
assert.equal(result.climateNormalYears.length, 5);
assert.ok(Math.abs(result.coverageMean - 0.98) < 1e-12);

console.log(
  "PASS browser Ridge model smoke test:",
  JSON.stringify({
    forecast: Number(result.forecast.toFixed(4)),
    ridge_oof_mae: Number(result.mae.toFixed(4)),
    persistence_mae: Number(result.persistenceMae.toFixed(4)),
    oof_rows: result.oof.length,
    climate_normal_years: result.climateNormalYears,
  })
);
