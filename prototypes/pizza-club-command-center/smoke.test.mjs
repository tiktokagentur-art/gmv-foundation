// Dependency-free static smoke checks; does not contact external systems.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
const html=readFileSync(new URL("./index.html",import.meta.url),"utf8");
const css=readFileSync(new URL("./styles.css",import.meta.url),"utf8");
const js=readFileSync(new URL("./app.js",import.meta.url),"utf8");
assert.match(html,/<html lang="de">/);
assert.match(html,/Content-Security-Policy/);
assert.match(html,/connect-src 'none'/);
assert.match(html,/data-view="ceo"/);
assert.match(html,/data-view="aline"/);
assert.match(html,/data-view="approvals"/);
assert.match(html,/data-view="costs"/);
assert.match(html,/id="chatForm"/);
assert.match(html,/id="taskDialog"/);
assert.match(css,/@media\(max-width:530px\)/);
const ids=new Set([...html.matchAll(/id="([^"]+)"/g)].map(m=>m[1]));
for(const [,id] of js.matchAll(/byId\("([^"]+)"\)/g)){
  assert.ok(ids.has(id),"Unbekannte HTML-ID: "+id);
}
const source=js.replace(/\/\*[\s\S]*?\*\//g,"").replace(/^\/\/.*$/gm,"");
for(const forbidden of ["fetch(","XMLHttpRequest","WebSocket","localStorage","sessionStorage","sendBeacon","import(","eval("]){
  assert.equal(source.includes(forbidden),false,"Verbotene Schnittstelle: "+forbidden);
}
assert.equal((css.match(/{/g)||[]).length,(css.match(/}/g)||[]).length,"CSS-Klammern");
new Function(js);
console.log("UI-FOUND-001 static smoke checks: PASS");
