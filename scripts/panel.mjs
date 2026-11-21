// Panel del DJ: repartir dosieres, la noche (relojes y contraseña), escenas, reglas del golpe, ayudas, tablas e integraciones.
// Recuerda posición, tamaño y secciones abiertas en este navegador.
import { ID, t, esc, HORAS, estado, personajes, retrato } from "./estado.mjs";
import { RELOJES, moverReloj, reiniciarNoche, fijarContrasena, decirContrasena, mostrarAyuda, salvarNervios, quienSeLlevoElTiro, abrirDuelo, revelarDuelo, cerrarDuelo } from "./reglas.mjs";
import { abrirPizarra } from "./integraciones.mjs";

const { ApplicationV2 } = foundry.applications.api;
const flag = (d, k) => d?.flags?.[ID]?.[k];
const porSlug = (slug) => game.actors.find((a) => flag(a, "slug") === slug);
const dosierDe = (actor) => game.journal.find((j) => flag(j, "dosier") === flag(actor, "slug"));
const jugadores = () => game.users.filter((u) => !u.isGM);

export class PanelDJ extends ApplicationV2 {
  static #instancia;
  static abrir() { (this.#instancia ??= new PanelDJ()).render({ force: true }); }

  static DEFAULT_OPTIONS = {
    id: "mrrm-panel", classes: [ID, "mrrm-panel"], tag: "section",
    window: { title: "MRRM.Panel.Titulo", icon: "fa-solid fa-user-secret", resizable: true },
    position: { width: 560, height: 760 }
  };

  constructor(o) {
    super(o);
    const m = game.settings.get(ID, "ventanas")?.panel;
    if (m?.pos) Object.assign(this.options.position, m.pos);
    this.abiertas = new Set(m?.abiertas ?? ["mesa", "noche"]);
  }

  _onPosition(pos) {
    super._onPosition?.(pos);
    clearTimeout(this._g);
    this._g = setTimeout(() => this.#memoria(), 400);
  }
  #memoria() {
    const v = foundry.utils.deepClone(game.settings.get(ID, "ventanas") ?? {});
    const { left, top, width, height } = this.position;
    v.panel = { pos: { left, top, width, height }, abiertas: [...this.abiertas] };
    game.settings.set(ID, "ventanas", v);
  }

  async _renderHTML() {
    const e = estado();
    const sec = (id, icono, cuerpo) => `<details data-sec="${id}" ${this.abiertas.has(id) ? "open" : ""}><summary><i class="fa-solid ${icono}" aria-hidden="true"></i> ${t(`Panel.${id}`)}</summary><div class="mrrm-sec">${cuerpo}</div></details>`;
    const opcUsuarios = (sel) => `<option value="">${t("Panel.NadieAsignado")}</option>` + jugadores().map((u) => `<option value="${u.id}" ${u.id === sel ? "selected" : ""}>${esc(u.name)}</option>`).join("");
    const pjs = personajes();
    const dueno = (a) => jugadores().find((u) => a.testUserPermission(u, "OWNER"))?.id ?? "";
    const mesa = pjs.length ? `<p class="mrrm-ayuda">${t("Panel.MesaAyuda")}</p><ul class="mrrm-reparto">${pjs.map((a) => `<li>
        <img src="${esc(retrato(a))}" alt=""><span>${esc(a.name)}</span>
        <select data-reparto="${a.id}" aria-label="${t("Panel.Jugador")} ${esc(a.name)}">${opcUsuarios(dueno(a))}</select>
        <button type="button" data-act="dosier" data-id="${a.id}" data-tooltip="${t("Panel.MostrarDosier")}" aria-label="${t("Panel.MostrarDosier")}"><i class="fa-solid fa-envelope-open-text"></i></button></li>`).join("")}</ul>`
      : `<p>${t("Panel.SinAventura")}</p><button type="button" data-act="importar"><i class="fa-solid fa-file-import"></i> ${t("Panel.Importar")}</button>`;
    const reloj = (k) => `<div class="mrrm-reloj"><span>${t(`Reloj.${k}.Titulo`)}</span><button type="button" data-reloj="${k}" data-d="-1" aria-label="${t("Hud.Menos")}">−</button>
      <strong>${k === "reloj" ? HORAS[e[k]] : `${e[k]}/${RELOJES[k]}`}</strong><button type="button" data-reloj="${k}" data-d="1" aria-label="${t("Hud.Mas")}">+</button>
      <small>${esc(t(`Reloj.${k}.GM${e[k]}`))}</small></div>`;
    const noche = `${reloj("reloj")}${reloj("cerco")}${reloj("paranoia")}
      <div class="mrrm-fila"><span>${t("Contrasena.Titulo")}: <strong>${e.contrasena ? `«${esc(e.contrasena)}»` : "—"}</strong></span>
        <button type="button" data-act="fijar-contrasena"><i class="fa-solid fa-key"></i> ${t("Contrasena.Fijar")}</button>
        <button type="button" data-act="decir-contrasena"><i class="fa-solid fa-ship"></i> ${t("Contrasena.Decir")}</button></div>
      <button type="button" data-act="reiniciar" class="mrrm-discreto"><i class="fa-solid fa-rotate-left"></i> ${t("Panel.Reiniciar")}</button>`;
    const escenas = game.scenes.filter((s) => flag(s, "orden") !== undefined).sort((a, b) => flag(a, "orden") - flag(b, "orden"));
    const esc_ = escenas.length ? `<ul class="mrrm-escenas">${escenas.map((s) => `<li class="${s.active ? "activa" : ""}"><button type="button" data-escena="${s.id}">
        <img src="${esc(s.thumb ?? "")}" alt=""><span>${esc(s.name)}</span></button></li>`).join("")}</ul>` : `<p>${t("Panel.SinEscenas")}</p>`;
    const casillas = (nombre, def) => pjs.concat(["gris", "barquero", "agente"].map(porSlug).filter(Boolean)).map((a) => `<label class="mrrm-chip"><input type="checkbox" name="${nombre}" value="${a.id}" ${def(a) ? "checked" : ""}><img src="${esc(retrato(a))}" alt=""> ${esc(a.name)}</label>`).join("");
    const enCoche2 = (a) => ["verde", "rojo", "negro"].includes(flag(a, "slug"));
    const conDueno = (a) => flag(a, "tipo") === "pj" && Boolean(dueno(a));
    const reglas = `<h4>${t("Nervios.Titulo")}</h4><div class="mrrm-chips" data-grupo="nervios">${casillas("nervios", () => false)}</div>
      <div class="mrrm-fila"><select name="motivo" aria-label="${t("Nervios.Motivo")}">${["", "libreta", "rastreador", "pintada", "maletero", "gris", "muerto", "radio"].map((m) => `<option value="${m}">${m ? t(`Motivo.${m}`) : t("Nervios.SinMotivo")}</option>`).join("")}</select>
      <button type="button" data-act="nervios"><i class="fa-solid fa-heart-pulse"></i> ${t("Nervios.Lanzar")}</button></div>
      <h4>${t("Flash1.Titulo")}</h4><div class="mrrm-chips" data-grupo="flash1">${casillas("flash1", enCoche2)}</div>
      <button type="button" data-act="flash1"><i class="fa-solid fa-car-burst"></i> ${t("Flash1.Lanzar")}</button>
      <h4>${t("Duelo.Titulo")}</h4><div class="mrrm-chips" data-grupo="duelo">${casillas("duelo", conDueno)}</div>
      <div class="mrrm-fila">${e.duelo ? `<span>${Object.keys(e.duelo.elecciones).length}/${e.duelo.participantes.length} ${t("Duelo.HanElegido")}</span>
        <button type="button" data-act="revelar"><i class="fa-solid fa-eye"></i> ${t("Duelo.Revelar")}</button><button type="button" data-act="cerrar-duelo"><i class="fa-solid fa-xmark"></i> ${t("Cerrar")}</button>`
        : `<button type="button" data-act="duelo"><i class="fa-solid fa-gun"></i> ${t("Duelo.Abrir")}</button>`}</div>`;
    const ayudas = `<div class="mrrm-fila"><button type="button" data-ayuda="pintada"><i class="fa-solid fa-spray-can"></i> ${t("Ayuda.Pintada")}</button>
      <button type="button" data-ayuda="mapa"><i class="fa-solid fa-map"></i> ${t("Ayuda.Mapa")}</button></div>
      <div class="mrrm-fila"><select name="elegido" aria-label="${t("Ayuda.ParaQuien")}">${opcUsuarios("")}</select>
      <button type="button" data-ayuda="libreta"><i class="fa-solid fa-book"></i> ${t("Ayuda.Libreta")}</button></div>`;
    const tablas = game.tables.filter((tb) => flag(tb, "slug")).map((tb) => `<button type="button" data-tabla="${tb.id}"><i class="fa-solid fa-dice"></i> ${esc(tb.name)}</button>`).join("");
    const piz = game.modules.get("mr-pizarra")?.active;
    const dir = game.modules.get("mr-direccion")?.active;
    const integ = `<p><i class="fa-solid fa-${dir ? "check" : "minus"}"></i> ${t(dir ? "Integ.DireccionSi" : "Integ.DireccionNo")}</p>
      <p><i class="fa-solid fa-${piz ? "check" : "minus"}"></i> ${t(piz ? "Integ.PizarraSi" : "Integ.PizarraNo")}</p>
      ${piz ? `<button type="button" data-act="pizarra"><i class="fa-solid fa-thumbtack"></i> ${t("Integ.AbrirPizarra")}</button>` : ""}`;
    return `<div class="mrrm-panel-cuerpo">${sec("mesa", "fa-users", mesa)}${sec("noche", "fa-clock", noche)}${sec("escenas", "fa-film", esc_)}
      ${sec("reglas", "fa-gun", reglas)}${sec("ayudas", "fa-file-image", ayudas)}${sec("tablas", "fa-table-list", `<div class="mrrm-fila">${tablas}</div>`)}${sec("integ", "fa-plug", integ)}</div>`;
  }

  _replaceHTML(result, content) {
    content.innerHTML = result;
    if (content.dataset.mrrm) return;   // los oyentes van una sola vez sobre el contenedor (si no, se multiplican en cada render)
    content.dataset.mrrm = "1";
    content.addEventListener("toggle", (ev) => {
      const d = ev.target.closest?.("details[data-sec]");
      if (!d) return;
      d.open ? this.abiertas.add(d.dataset.sec) : this.abiertas.delete(d.dataset.sec);
      this.#memoria();
    }, true);
    content.addEventListener("change", (ev) => { const s = ev.target.closest("select[data-reparto]"); if (s) this.#repartir(s.dataset.reparto, s.value); });
    content.addEventListener("click", (ev) => this.#clic(ev, content));
  }

  async #clic(ev, root) {
    const b = ev.target.closest("button");
    if (!b) return;
    const marcados = (g) => [...root.querySelectorAll(`[data-grupo="${g}"] input:checked`)].map((i) => game.actors.get(i.value)).filter(Boolean);
    const d = b.dataset;
    if (d.reloj) return moverReloj(d.reloj, Number(d.d));
    if (d.escena) return game.scenes.get(d.escena)?.view();
    if (d.ayuda) {
      const u = d.ayuda === "libreta" ? root.querySelector("select[name=elegido]").value : "";
      if (d.ayuda === "libreta" && !u) return ui.notifications.warn(t("Ayuda.EligeJugador"));
      return mostrarAyuda(d.ayuda, u ? [u] : []);
    }
    if (d.tabla) return game.tables.get(d.tabla)?.draw();
    switch (d.act) {
      case "importar": return game.modules.get(ID).api.importarAventura();
      case "dosier": { const a = game.actors.get(d.id), j = dosierDe(a); return j?.sheet.render({ force: true }); }
      case "fijar-contrasena": return fijarContrasena();
      case "decir-contrasena": return decirContrasena();
      case "reiniciar": {
        const ok = await foundry.applications.api.DialogV2.confirm({ window: { title: t("Panel.Reiniciar") }, content: `<p>${t("Panel.ReiniciarSeguro")}</p>` });
        return ok && reiniciarNoche();
      }
      case "nervios": {
        const motivo = root.querySelector("select[name=motivo]").value;
        for (const a of marcados("nervios")) await salvarNervios(a, motivo ? t(`Motivo.${motivo}`) : "");
        return;
      }
      case "flash1": return quienSeLlevoElTiro(marcados("flash1"));
      case "duelo": return abrirDuelo(marcados("duelo"));
      case "revelar": return revelarDuelo();
      case "cerrar-duelo": return cerrarDuelo();
      case "pizarra": return abrirPizarra();
    }
  }

  /** Da el ratón a un jugador: propietario del actor, observador de su dosier y personaje asignado. Lo quita a los demás. */
  async #repartir(actorId, userId) {
    const a = game.actors.get(actorId);
    if (!a) return;
    const j = dosierDe(a);
    const own = { default: 0 };
    for (const u of jugadores()) own[u.id] = 0;
    if (userId) own[userId] = 3;
    await a.update({ ownership: own });
    if (j) await j.update({ ownership: Object.fromEntries(Object.entries(own).map(([k, v]) => [k, v ? 2 : 0])) });
    for (const u of jugadores()) if (u.character?.id === a.id && u.id !== userId) await u.update({ character: null });
    if (userId) {
      await game.users.get(userId).update({ character: a.id });
      if (j) foundry.documents.collections.Journal.show(j, { force: true, users: [userId] });
    }
    this.render();
  }
}

Hooks.on("updateSetting", (s) => { if (s.key === `${ID}.estado`) foundry.applications.instances.get("mrrm-panel")?.render(); });
Hooks.on("updateScene", () => foundry.applications.instances.get("mrrm-panel")?.render());
