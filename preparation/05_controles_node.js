/* Harnais de contrôle hors navigateur : charge le script réellement embarqué
   dans index.html, avec un DOM minimal, et exécute la suite de contrôles
   internes. Sert à vérifier le fichier livré sans ouvrir de navigateur. */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const fichier = path.join(__dirname, "..", "index.html");
const html = fs.readFileSync(fichier, "utf8");
const script = html.match(/<script>([\s\S]*)<\/script>/)[1];

function faussElement(){
  const e = {
    innerHTML: "", textContent: "", value: "", style: {}, className: "", hidden: false,
    children: [],
    setAttribute(){}, getAttribute(){ return null; }, hasAttribute(){ return false; },
    appendChild(c){ this.children.push(c); }, removeChild(){},
    querySelector(){ return null; }, querySelectorAll(){ return []; },
    addEventListener(){}, closest(){ return null; }, scrollIntoView(){}
  };
  return e;
}

const document = {
  documentElement: { get outerHTML(){ return html; } },
  getElementById(){ return faussElement(); },
  querySelector(){ return null; },
  querySelectorAll(){ return []; },
  createElement(){ return faussElement(); },
  addEventListener(){}
};

const contexte = {
  document,
  window: { scrollTo(){} },
  Blob: class { constructor(p){ this.size = Buffer.byteLength(p.join(""), "utf8"); } },
  console, Math, Date, JSON, parseInt, parseFloat, isFinite, Object, Array, String, Number, RegExp, Error
};
contexte.globalThis = contexte;
vm.createContext(contexte);
vm.runInContext(script, contexte, { filename: "index.html" });

const resultats = contexte.lancerControles();
let echecs = 0;
for (const c of resultats){
  if (!c.ok) echecs++;
  console.log((c.ok ? "  réussi  " : "  ÉCHEC   ") + c.nom);
  if (c.detail) console.log("           " + c.detail.replace(/<[^>]*>/g, ""));
}
console.log("\n" + resultats.length + " contrôles, " + echecs + " en échec.");
console.log("Poids du fichier : " + Math.round(fs.statSync(fichier).size / 1024) + " Ko");
process.exit(echecs ? 1 : 0);
