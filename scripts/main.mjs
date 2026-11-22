// MR- Reservoir Mice · arranque: ajustes, API, importación automática, barra de herramientas y reglas de inventario.
import { ID, t, estado, iniciarSocket, personajes } from "./estado.mjs";
import "./efectos.mjs";
import { salvarNervios, quienSeLlevoElTiro, moverReloj, mostrarAyuda, abrirDuelo, revelarDuelo, fijarContrasena, decirContrasena, reiniciarNoche } from "./reglas.mjs";
import { pintarHud } from "./hud.mjs";
import { PanelDJ } from "./panel.mjs";
import { registrarDireccion, abrirPizarra } from "./integraciones.mjs";
import { registrarVentanas } from "./ventanas.mjs";
import { registrarPiel, ponerPortada } from "./piel.mjs";

const PACK = `${ID}.aventura`;

Hooks.once("init", () => {
  const cli = (clave, type, def, extra = {}) => game.settings.register(ID, clave, { name: `MRRM.Ajustes.${clave}.Name`, hint: `MRRM.Ajustes.${clave}.Hint`, scope: "client", config: true, type, default: def, ...extra });
  cli("mostrarHud", Boolean, true, { onChange: () => pintarHud() });
  cli("efectosSonido", Boolean, true);
  cli("volumenEfectos", Number, 0.7, { range: { min: 0, max: 1, step: 0.05 } });
  cli("efectosVisuales", Boolean, true);
  cli("textoGrande", Boolean, false, { onChange: (v) => document.body.classList.toggle("mrrm-texto-grande", v) });
  cli("altoContraste", Boolean, false, { onChange: (v) => document.body.classList.toggle("mrrm-alto-contraste", v) });
  game.settings.register(ID, "estiloToken", { name: "MRRM.Ajustes.estiloToken.Name", hint: "MRRM.Ajustes.estiloToken.Hint", scope: "world", config: true, type: String, default: "cuerpo",
    choices: { cuerpo: "MRRM.Ajustes.estiloToken.Cuerpo", redondo: "MRRM.Ajustes.estiloToken.Redondo" } });
  game.settings.register(ID, "estado", { scope: "world", config: false, type: Object, default: {}, onChange: () => { pintarHud(); Hooks.callAll("mrrm.estado", estado()); } });
  game.settings.register(ID, "importada", { scope: "world", config: false, type: Boolean, default: false });
  game.settings.register(ID, "posHud", { scope: "client", config: false, type: Object, default: {} });
  game.settings.register(ID, "ventanas", { scope: "client", config: false, type: Object, default: {} });
  game.settings.registerMenu(ID, "restablecer", { name: "MRRM.Ajustes.restablecer.Name", label: "MRRM.Ajustes.restablecer.Label", hint: "MRRM.Ajustes.restablecer.Hint",
    icon: "fa-solid fa-arrows-to-dot", restricted: false, type: class extends foundry.applications.api.ApplicationV2 {
      async render() { await game.settings.set(ID, "posHud", {}); await game.settings.set(ID, "ventanas", {}); pintarHud(); ui.notifications.info(t("Ajustes.restablecer.Hecho")); return this; }
    } });
  registrarVentanas();
  registrarPiel();
});

/* ---------------- Importación de la aventura ---------------- */
function mundoVacio() {
  const sinContenido = ["actors", "items", "journal", "playlists", "macros", "tables", "cards"].every((c) => !game[c]?.size);
  return sinContenido && game.scenes.contents.every((s) => s.background?.src?.startsWith("nue/") && !s.tokens.size);
}
export async function importarAventura({ confirmar = true } = {}) {
  if (!game.user.isGM) return ui.notifications.warn(t("SoloGM"));
  const pack = game.packs.get(PACK);
  if (!pack) return ui.notifications.error(t("Importar.SinPack"));
  if (confirmar && !mundoVacio()) {
    const ok = await foundry.applications.api.DialogV2.confirm({
      window: { title: t("Importar.Titulo"), icon: "fa-solid fa-file-import" }, content: `<p>${t("Importar.Aviso")}</p>`,
      yes: { label: t("Importar.Si"), icon: "fa-solid fa-file-import" }, no: { label: t("Cancelar") }, rejectClose: false
    });
    if (!ok) return;
  }
  ui.notifications.info(t("Importar.Empieza"));
  const adv = (await pack.getDocuments())[0];
  await adv.import({ dialog: false });
  await game.settings.set(ID, "importada", true);
  await game.scenes.find((s) => s.getFlag(ID, "orden") === 0)?.activate();
  ui.notifications.info(t("Importar.Hecho"));
  game.journal.find((j) => j.getFlag(ID, "guia"))?.sheet.render({ force: true });
}

/* ---------------- API ---------------- */
const API = {
  importarAventura, panel: () => PanelDJ.abrir(), salvarNervios, quienSeLlevoElTiro, moverReloj, mostrarAyuda,
  abrirDuelo, revelarDuelo, fijarContrasena, decirContrasena, reiniciarNoche, abrirPizarra, estado
};

Hooks.once("ready", async () => {
  game.modules.get(ID).api = API;
  iniciarSocket();
  document.body.classList.toggle("mrrm-texto-grande", game.settings.get(ID, "textoGrande"));
  document.body.classList.toggle("mrrm-alto-contraste", game.settings.get(ID, "altoContraste"));
  registrarDireccion();
  pintarHud();
  if (game.user.isGM) {
    // las macros del compendio llevan un autor ficticio: pasan al GM que las importa
    for (const m of game.macros.filter((m) => m.getFlag(ID, "macro") && !game.users.has(m.author?.id))) await m.update({ author: game.user.id });
    if (game.user === game.users.activeGM && !game.settings.get(ID, "importada") && mundoVacio()) await importarAventura({ confirmar: false });
    if (game.user === game.users.activeGM && game.settings.get(ID, "importada")) ponerPortada();
  }
});

/* ---------------- Barra de herramientas ---------------- */
// Lo que usan los jugadores va aquí y no en macros (no pueden ejecutar macros de script).
Hooks.on("getSceneControlButtons", (controls) => {
  const gm = game.user.isGM;
  const herr = (name, title, icon, fn, soloGM = false) => ({ name, title, icon, button: true, visible: gm || !soloGM, onChange: () => fn() });
  const tools = [
    herr("panel", "MRRM.Barra.Panel", "fa-solid fa-user-secret", API.panel, true),
    herr("nervios", "MRRM.Barra.Nervios", "fa-solid fa-heart-pulse", () => salvarNervios(game.user.character ?? canvas.tokens?.controlled[0]?.actor)),
    herr("hud", "MRRM.Barra.Hud", "fa-solid fa-clock", () => game.settings.set(ID, "mostrarHud", !game.settings.get(ID, "mostrarHud"))),
    herr("pintada", "MRRM.Barra.Pintada", "fa-solid fa-spray-can", () => mostrarAyuda("pintada"), true),
    herr("pizarra", "MRRM.Barra.Pizarra", "fa-solid fa-thumbtack", abrirPizarra, true)
  ];
  controls.mrrm = { name: "mrrm", title: "MRRM.Barra.Titulo", icon: "fa-solid fa-sack-dollar", order: 90, visible: true, activeTool: "",
    tools: Object.fromEntries(tools.map((x, i) => [x.name, { ...x, order: i }])) };
});

/* ---------------- Estilo de ficha ---------------- */
Hooks.on("preCreateToken", (token) => {
  const slug = token.actor?.getFlag?.(ID, "slug");
  if (!slug || game.settings.get(ID, "estiloToken") !== "redondo") return;
  token.updateSource({ "texture.src": `modules/${ID}/assets/actors/tokens/${slug}.webp`, "ring.enabled": false });
});

/* ---------------- Regla del golpe: seis casillas ---------------- */
// La hoja de Mausritter es un lienzo libre. En los ratones de la banda, las cuatro casillas de mochila de la derecha están
// ocupadas por «Sin sitio» (objeto fijo): ni se mueve ni se borra salvo el GM, y nada se coloca encima.
const esDeLaBanda = (actor) => personajes().includes(actor);
const BLOQUEADAS = new Set([[140, -150], [270, -150], [140, -20], [270, -20]].map((p) => p.join(",")));
Hooks.on("preUpdateItem", (item, cambios, _o, userId) => {
  if (!item.parent || !esDeLaBanda(item.parent) || game.users.get(userId)?.isGM) return;
  if (item.getFlag(ID, "bloqueo")) return false;
  const x = foundry.utils.getProperty(cambios, "system.sheet.currentX");
  if (x === undefined) return;
  const y = foundry.utils.getProperty(cambios, "system.sheet.currentY") ?? item.system.sheet.currentY;
  const w = item.system.size?.width ?? 1, h = item.system.size?.height ?? 1;
  for (let dx = 0; dx < w; dx++) for (let dy = 0; dy < h; dy++) {
    if (BLOQUEADAS.has(`${x - 65 * (w - 1) + 130 * dx},${y - 65 * (h - 1) + 130 * dy}`)) { ui.notifications.warn(t("Casillas.Aviso")); return false; }
  }
});
Hooks.on("preDeleteItem", (item, _o, userId) => {
  if (item.getFlag(ID, "bloqueo") && !game.users.get(userId)?.isGM) { ui.notifications.warn(t("Casillas.NoSeQuita")); return false; }
});
