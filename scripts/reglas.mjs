// Reglas del golpe: salvación de nervios, Flashback 1 (¿quién se llevó el tiro?), relojes, contraseña, duelo de miradas y ayudas.
import { ID, t, esc, ruta, HORAS, estado, guardar, chatGM, chatPublico, registrarAccion, pedir, aTodos, darCondicion, tieneCondicion, retrato } from "./estado.mjs";
import { efecto } from "./efectos.mjs";

const tarjeta = (clase, html) => `<div class="mrrm-chat ${clase}">${html}</div>`;
const habla = (actor) => ChatMessage.getSpeaker({ actor });

// ---------------------------------------------------------------- Salvación de nervios
/** Tira 1d20 contra VOL. Si falla: Paranoico; si ya lo estaba: Dedo flojo. Cualquiera la lanza para su ratón; el GM, para cualquiera. */
export async function salvarNervios(actor, motivo = "") {
  if (!actor) return ui.notifications.warn(t("Nervios.SinActor"));
  if (!actor.isOwner) return pedir("nervios", { actor: actor.id, motivo });
  const vol = actor.system.stats?.will?.value ?? 10;
  const roll = await new Roll("1d20").evaluate();
  const falla = roll.total > vol;
  let cond = null, txt;
  if (!falla) txt = t("Nervios.Aguanta");
  else if (!tieneCondicion(actor, "paranoico")) { cond = "paranoico"; txt = t("Nervios.Paranoico"); }
  else if (!tieneCondicion(actor, "dedo-flojo")) { cond = "dedo-flojo"; txt = t("Nervios.DedoFlojo"); }
  else txt = t("Nervios.Tope");
  const img = cond ? ruta(`assets/items/${cond}.webp`) : retrato(actor);
  await ChatMessage.create({
    speaker: habla(actor), rolls: [roll],
    content: tarjeta(falla ? "mrrm-alerta" : "", `<header><img src="${esc(img)}" alt=""><h3>${t("Nervios.Titulo")}</h3></header>
      ${motivo ? `<p class="mrrm-motivo">${esc(motivo)}</p>` : ""}
      <p class="mrrm-tirada"><strong>${roll.total}</strong> ${t("Nervios.Contra", { vol })} · <em>${falla ? t("Nervios.Falla") : t("Nervios.Supera")}</em></p><p>${txt}</p>`)
  });
  if (cond) { await darCondicion(actor, cond); efecto(cond === "dedo-flojo" ? "amartillar" : "latido"); }
  return { total: roll.total, falla, cond };
}
registrarAccion("nervios", ({ actor, motivo }) => salvarNervios(game.actors.get(actor), motivo));

// ---------------------------------------------------------------- Flashback 1: ¿quién se llevó el tiro?
export async function quienSeLlevoElTiro(actores) {
  actores = actores.filter(Boolean);
  if (actores.length < 2) return ui.notifications.warn(t("Flash1.Pocos"));
  const rolls = [];
  const orden = [];
  for (const a of actores) { const r = await new Roll("1d20").evaluate(); rolls.push(r); orden.push({ a, ini: r.total }); }
  orden.sort((x, y) => y.ini - x.ini);
  const lineas = [];
  let herido = null, umbral = 1;
  while (!herido && umbral <= 6) {
    for (const o of orden) {
      const r = await new Roll("1d6").evaluate(); rolls.push(r);
      const cae = r.total <= umbral;
      lineas.push(`<li>${esc(o.a.name)}: <strong>${r.total}</strong> ${t("Flash1.Umbral", { n: umbral === 1 ? "1" : `1–${umbral}` })}${cae ? ` · <em>${t("Flash1.Cae")}</em>` : ""}</li>`);
      if (cae) { herido = o.a; break; }
      umbral++;
    }
  }
  herido ??= orden.at(-1).a;
  const dano = await new Roll("1d4").evaluate(); rolls.push(dano);
  const pg = herido.system.health?.value ?? 0;
  await herido.update({ "system.health.value": Math.max(0, pg - dano.total) });
  await darCondicion(herido, "herido");
  efecto("disparo");
  await ChatMessage.create({
    rolls,
    content: tarjeta("mrrm-alerta", `<header><img src="${esc(ruta("assets/items/herido.webp"))}" alt=""><h3>${t("Flash1.Titulo")}</h3></header>
      <p>${t("Flash1.Orden")}: ${orden.map((o) => `${esc(o.a.name)} (${o.ini})`).join(" · ")}</p><ol>${lineas.join("")}</ol>
      <p>${t("Flash1.Resultado", { nombre: esc(herido.name), dano: dano.total })}</p>`)
  });
  return herido;
}

// ---------------------------------------------------------------- Relojes
export const RELOJES = { reloj: 6, cerco: 4, paranoia: 4 };
export async function moverReloj(clave, delta) {
  if (!game.user.isGM) return;
  const e0 = estado();
  const n = Math.max(0, Math.min(RELOJES[clave], e0[clave] + delta));
  if (n === e0[clave]) return;
  await guardar((e) => { e[clave] = n; e.aviso = { clave, n, sube: delta > 0, t: Date.now() }; });
  if (delta > 0) {
    chatGM(tarjeta("", `<h3>${t(`Reloj.${clave}.Titulo`)} · ${clave === "reloj" ? HORAS[n] : `${n}/${RELOJES[clave]}`}</h3><p>${t(`Reloj.${clave}.GM${n}`)}</p>`));
    if (clave === "reloj") efecto(n === 6 ? "campanadas" : "tictac");
    if (clave === "cerco") efecto(n >= 3 ? "sirena" : "sirenaLejos");
  }
}
export const reiniciarNoche = () => guardar((e) => { Object.assign(e, { reloj: 0, cerco: 0, paranoia: 0, contrasena: "", duelo: null, aviso: null }); });

// ---------------------------------------------------------------- Contraseña del barquero
export async function fijarContrasena() {
  const r = await foundry.applications.api.DialogV2.prompt({
    window: { title: t("Contrasena.Titulo"), icon: "fa-solid fa-key" }, classes: [ID],
    content: `<p>${t("Contrasena.Ayuda")}</p><input type="text" name="c" value="${esc(estado().contrasena)}" autofocus>`,
    ok: { label: t("Guardar"), icon: "fa-solid fa-floppy-disk", callback: (ev, btn) => btn.form.elements.c.value.trim() }
  }).catch(() => null);
  if (r !== null && r !== undefined) await guardar((e) => { e.contrasena = r; });
}
export async function decirContrasena() {
  const c = estado().contrasena;
  if (!c) return ui.notifications.warn(t("Contrasena.Vacia"));
  chatPublico(tarjeta("mrrm-barquero", `<header><img src="${esc(ruta("assets/actors/portraits/barquero.webp"))}" alt=""><h3>${t("Contrasena.Barquero")}</h3></header><p class="mrrm-cita">«${esc(c)}»</p>`));
}

// ---------------------------------------------------------------- Ayudas de juego
export const AYUDAS = {
  pintada: { img: "assets/handouts/pintada.webp", titulo: "Ayuda.Pintada" },
  libreta: { img: "assets/handouts/libreta-gris.webp", titulo: "Ayuda.Libreta" },
  mapa: { img: "assets/scenes/mapa-almacen.webp", titulo: "Ayuda.Mapa" },
};
/** Muestra una imagen a todos o a unos usuarios (la libreta, solo al elegido) y la abre en la pantalla del GM. */
export function mostrarAyuda(clave, users = []) {
  const a = AYUDAS[clave] ?? { img: clave, titulo: "Ayuda.Imagen" };
  const src = a.img.startsWith("modules/") ? a.img : ruta(a.img);
  const title = t(a.titulo);
  foundry.documents.collections.Journal.showImage(src, { users, title, showTitle: true });
  new foundry.applications.apps.ImagePopout({ src, window: { title } }).render({ force: true });
  if (clave === "pintada") efecto("pintada");
}

// ---------------------------------------------------------------- Duelo de miradas
/** El GM abre el duelo: cada participante elige en secreto a quién apunta. Nadie ve nada hasta que el GM revela. */
export async function abrirDuelo(actores) {
  const ids = actores.map((a) => a.id);
  if (ids.length < 2) return ui.notifications.warn(t("Duelo.Pocos"));
  await guardar((e) => { e.duelo = { participantes: ids, elecciones: {}, revelado: false }; });
  efecto("amartillar");
  aTodos("duelo-abre", { ids });
}
registrarAccion("duelo-elige", async ({ actor, objetivo }, userId) => {
  const e = estado();
  if (!e.duelo || e.duelo.revelado || !e.duelo.participantes.includes(actor)) return;
  const a = game.actors.get(actor);
  if (!a?.testUserPermission(game.users.get(userId), "OWNER")) return;
  await guardar((x) => { x.duelo.elecciones[actor] = objetivo ?? ""; });
});
export const elegirEnDuelo = (actor, objetivo) => pedir("duelo-elige", { actor, objetivo });
export async function revelarDuelo() {
  const e = estado();
  if (!e.duelo) return;
  await guardar((x) => { x.duelo.revelado = true; });
  const filas = e.duelo.participantes.map((id) => game.actors.get(id)).filter(Boolean)
    .sort((x, y) => (y.system.stats?.dexterity?.value ?? 0) - (x.system.stats?.dexterity?.value ?? 0))
    .map((a) => {
      const obj = e.duelo.elecciones[a.id];
      const b = obj ? game.actors.get(obj) : null;
      const destino = obj === undefined ? `<em>${t("Duelo.SinDecidir")}</em>` : b ? `<img src="${esc(retrato(b))}" alt=""> ${esc(b.name)}` : `<em>${t("Duelo.Nadie")}</em>`;
      return `<li><img src="${esc(retrato(a))}" alt=""> ${esc(a.name)} <span class="mrrm-dex">DES ${a.system.stats?.dexterity?.value ?? "?"}</span> <i class="fa-solid fa-gun"></i> ${destino}</li>`;
    });
  efecto("standoff");
  await chatPublico(tarjeta("mrrm-duelo", `<h3>${t("Duelo.Titulo")}</h3><ul>${filas.join("")}</ul><p>${t("Duelo.Orden")}</p>`));
  aTodos("duelo-revela", {});
}
export const cerrarDuelo = () => guardar((e) => { e.duelo = null; });
