// Estado compartido de la noche (relojes, contraseña, duelo), peticiones de jugadores al GM y reglas de inventario.
export const ID = "mr-reservoir-mice";
export const t = (k, d) => (d ? game.i18n.format(`MRRM.${k}`, d) : game.i18n.localize(`MRRM.${k}`));
export const esc = (s) => foundry.utils.escapeHTML(String(s ?? ""));
export const ruta = (p) => `modules/${ID}/${p}`;

export const HORAS = ["18:15", "19:00", "20:00", "21:00", "22:00", "23:00", "00:00"];
const BASE = { reloj: 0, cerco: 0, paranoia: 0, contrasena: "", duelo: null, aviso: null };

export function estado() {
  return foundry.utils.mergeObject(foundry.utils.deepClone(BASE), game.settings.get(ID, "estado") ?? {}, { inplace: false });
}
/** Solo el GM escribe: aplica fn a una copia y guarda (los jugadores piden con `pedir`). */
export async function guardar(fn) {
  const e = estado();
  fn(e);
  await game.settings.set(ID, "estado", e);
  return e;
}

export const gms = () => game.users.filter((u) => u.isGM).map((u) => u.id);
export const chatGM = (content) => ChatMessage.create({ content, whisper: gms() });
export const chatPublico = (content, speaker) => ChatMessage.create({ content, speaker });

// ---- Peticiones de jugadores al GM. Se ejecutan de una en una: dos a la vez leerían el mismo estado y una pisaría a la otra.
const ACC = {};
export const registrarAccion = (nombre, fn) => { ACC[nombre] = fn; };
let cola = Promise.resolve();
const enSerie = (fn) => { const p = cola.then(fn); cola = p.catch((e) => console.error(ID, e)); return p; };
export function pedir(nombre, datos = {}) {
  if (game.user.isGM) return enSerie(() => ACC[nombre]?.(datos, game.user.id));
  if (!game.users.activeGM) return ui.notifications.warn(t("SinGM"));
  game.socket.emit(`module.${ID}`, { nombre, datos, de: game.user.id });
}
const OYENTES = {};
/** Mensajes que el GM manda a todos (efectos, ventanas que se abren en cada cliente). */
export const alRecibir = (tipo, fn) => { OYENTES[tipo] = fn; };
export function aTodos(tipo, datos = {}) {
  game.socket.emit(`module.${ID}`, { tipo, datos });
  OYENTES[tipo]?.(datos);
}
export function iniciarSocket() {
  game.socket.on(`module.${ID}`, (m) => {
    if (m.tipo) return OYENTES[m.tipo]?.(m.datos);
    if (!game.user.isActiveGM) return;
    enSerie(() => ACC[m.nombre]?.(m.datos, m.de));
  });
}

// ---- Inventario de la regla del golpe: seis casillas (2 patas, 2 cuerpo, 2 mochila) en las coordenadas de la hoja de Mausritter.
export const CASILLAS = { pata: [-270, -150], torpe: [-270, -20], c1: [-140, -150], c2: [-140, -20], m1: [10, -150], m2: [10, -20] };
/** Orden en que una condición busca hueco: primero la mochila, luego el cuerpo y por último las patas. */
const ORDEN = ["m1", "m2", "c1", "c2", "torpe", "pata"];
function ocupadas(actor) {
  const s = new Set();
  for (const i of actor.items) {
    const x = i.system.sheet?.currentX ?? 0, y = i.system.sheet?.currentY ?? 0;
    const w = i.system.size?.width ?? 1, h = i.system.size?.height ?? 1;
    // la hoja coloca los objetos grandes por su centro
    for (let dx = 0; dx < w; dx++) for (let dy = 0; dy < h; dy++) s.add(`${x - 65 * (w - 1) + 130 * dx},${y - 65 * (h - 1) + 130 * dy}`);
  }
  return s;
}
export function huecoLibre(actor) {
  const o = ocupadas(actor);
  const k = ORDEN.find((c) => !o.has(CASILLAS[c].join(",")));
  return k ? CASILLAS[k] : null;
}
export const tieneCondicion = (actor, slug) => actor.items.some((i) => i.getFlag(ID, "slug") === slug);

/** Añade una condición (objeto del mundo con flag slug) al actor, en una casilla libre. */
export async function darCondicion(actor, slug) {
  const base = game.items.find((i) => i.getFlag(ID, "slug") === slug) ?? (await plantillaCondicion(slug));
  if (!base) { ui.notifications.warn(t("FaltaCondicion", { slug })); return null; }
  const datos = base.toObject();
  delete datos._id; delete datos.folder;
  const hueco = huecoLibre(actor);
  if (hueco) Object.assign(datos.system.sheet, { currentX: hueco[0], currentY: hueco[1], initialX: hueco[0], initialY: hueco[1] });
  const [creada] = await actor.createEmbeddedDocuments("Item", [datos]);
  if (!hueco) chatPublico(`<div class="mrrm-chat mrrm-alerta"><p>${t("SinHueco", { nombre: esc(actor.name), cond: esc(base.name) })}</p></div>`);
  return creada;
}
/** Si el mundo no tiene los objetos de condición (aventura sin importar), se sacan del compendio. */
async function plantillaCondicion(slug) {
  const pack = game.packs.get(`${ID}.aventura`);
  const adv = pack && (await pack.getDocuments())[0];
  const d = adv?.items.find((i) => i.flags?.[ID]?.slug === slug);
  return d ? new Item.implementation(d) : null;
}

export const personajes = () => game.actors.filter((a) => ["pj", "limpiador"].includes(a.getFlag(ID, "tipo")));
export const retrato = (a) => a?.img ?? "icons/svg/mystery-man.svg";
