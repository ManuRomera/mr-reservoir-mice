// HUD «Medianoche»: la hora, el cerco y la paranoia a la vista de toda la mesa. El GM los mueve; todos ven el aviso.
// Se arrastra con el botón derecho (posición por navegador) y se oculta desde Ajustes. Incluye el duelo de miradas de los jugadores.
import { ID, t, esc, HORAS, estado, alRecibir, retrato } from "./estado.mjs";
import { RELOJES, moverReloj, elegirEnDuelo, revelarDuelo, cerrarDuelo, salvarNervios } from "./reglas.mjs";

let raiz = null;
let ultimoAviso = 0;

const pips = (n, max, clase) => Array.from({ length: max }, (_, i) => `<span class="mrrm-pip ${clase} ${i < n ? "on" : ""}"></span>`).join("");
const miActor = () => game.user.character ?? null;
/** Quién elige por mí en el duelo: un jugador, sus ratones; el GM, los participantes que no tienen jugador. */
const sinJugador = (a) => !game.users.some((u) => !u.isGM && a.testUserPermission(u, "OWNER"));
const eligePorMi = (a) => (game.user.isGM ? sinJugador(a) : a.isOwner);

function html() {
  const e = estado(), gm = game.user.isGM;
  const masmenos = (k) => (gm ? `<span class="mrrm-mm"><button type="button" data-k="${k}" data-d="-1" aria-label="${t("Hud.Menos")}">−</button><button type="button" data-k="${k}" data-d="1" aria-label="${t("Hud.Mas")}">+</button></span>` : "");
  const fila = (k, icono) => `<div class="mrrm-hud-fila" data-tooltip="${esc(t(`Reloj.${k}.Pub${e[k]}`))}"><i class="fa-solid ${icono}" aria-hidden="true"></i><span class="mrrm-hud-lbl">${t(`Reloj.${k}.Corto`)}</span>
    <span class="mrrm-pips" role="img" aria-label="${t(`Reloj.${k}.Titulo`)} ${e[k]}/${RELOJES[k]}">${pips(e[k], RELOJES[k], k)}</span>${masmenos(k)}</div>`;
  let duelo = "";
  const d = e.duelo;
  if (d && !d.revelado) {
    const mios = d.participantes.map((id) => game.actors.get(id)).filter((a) => a && eligePorMi(a));
    const faltan = mios.filter((a) => d.elecciones[a.id] === undefined);
    duelo = `<div class="mrrm-hud-duelo"><i class="fa-solid fa-gun" aria-hidden="true"></i> ${t("Duelo.Abierto")}
      ${faltan.length ? `<button type="button" data-a="apuntar">${t("Duelo.Apuntar")}</button>` : mios.length ? `<em>${t("Duelo.Hecho")}</em>` : ""}
      ${gm ? `<span>${Object.keys(d.elecciones).length}/${d.participantes.length}</span><button type="button" data-a="revelar">${t("Duelo.Revelar")}</button><button type="button" data-a="cerrar" aria-label="${t("Cerrar")}"><i class="fa-solid fa-xmark"></i></button>` : ""}</div>`;
  }
  const nervios = !gm && miActor() ? `<button type="button" class="mrrm-hud-nervios" data-a="nervios"><i class="fa-solid fa-heart-pulse" aria-hidden="true"></i> ${t("Nervios.Boton")}</button>` : "";
  return `<div class="mrrm-hud-hora" data-tooltip="${esc(t(`Reloj.reloj.Pub${e.reloj}`))}"><span class="mrrm-hud-kicker">${t("Hud.Medianoche")}</span>
      <strong>${HORAS[e.reloj]}</strong>${masmenos("reloj")}<span class="mrrm-pips">${pips(e.reloj, 6, "reloj")}</span></div>
    <div class="mrrm-hud-cuerpo">${fila("cerco", "fa-tower-broadcast")}${fila("paranoia", "fa-eye")}${nervios}${duelo}</div>`;
}

export function pintarHud() {
  const ver = game.settings.get(ID, "mostrarHud") && game.ready;
  if (!ver) { raiz?.remove(); raiz = null; return; }
  if (!raiz) {
    raiz = document.createElement("section");
    raiz.id = "mrrm-hud";
    raiz.className = `${ID} mrrm-hud`;
    raiz.setAttribute("aria-label", t("Hud.Titulo"));
    document.body.append(raiz);
    raiz.addEventListener("click", alPulsar);
    arrastrable(raiz);
  }
  raiz.classList.toggle("es-gm", game.user.isGM);
  raiz.innerHTML = html();
  colocar();
  avisar();
}

function colocar() {
  const p = game.settings.get(ID, "posHud") ?? {};
  if (Number.isFinite(p.x)) { raiz.style.left = `${Math.max(0, Math.min(innerWidth - 80, p.x))}px`; raiz.style.top = `${Math.max(0, Math.min(innerHeight - 60, p.y))}px`; raiz.style.bottom = "auto"; raiz.style.transform = "none"; }
  else { raiz.style.left = ""; raiz.style.top = ""; raiz.style.bottom = ""; raiz.style.transform = ""; }
}

async function alPulsar(ev) {
  const b = ev.target.closest("button");
  if (!b) return;
  if (b.dataset.k) return moverReloj(b.dataset.k, Number(b.dataset.d));
  const a = b.dataset.a;
  if (a === "nervios") return salvarNervios(miActor());
  if (a === "apuntar") return dialogoApuntar();
  if (a === "revelar") return revelarDuelo();
  if (a === "cerrar") return cerrarDuelo();
}

/** Botón derecho + arrastrar mueve el HUD; la posición se guarda en este navegador. */
function arrastrable(el) {
  el.addEventListener("contextmenu", (e) => e.preventDefault());
  el.addEventListener("pointerdown", (e) => {
    if (e.button !== 2) return;
    const r = el.getBoundingClientRect(), dx = e.clientX - r.left, dy = e.clientY - r.top;
    let pos = { x: r.left, y: r.top };
    try { el.setPointerCapture(e.pointerId); } catch { /* sin captura también funciona */ }
    const mover = (m) => { pos = { x: m.clientX - dx, y: m.clientY - dy }; el.style.left = `${pos.x}px`; el.style.top = `${pos.y}px`; el.style.bottom = "auto"; el.style.transform = "none"; };
    const soltar = () => { el.removeEventListener("pointermove", mover); game.settings.set(ID, "posHud", pos); };
    el.addEventListener("pointermove", mover);
    el.addEventListener("pointerup", soltar, { once: true });
  });
}

/** Cuando el GM mueve un reloj hacia delante, todos ven un rótulo grande con la hora y una frase. */
function avisar() {
  const av = estado().aviso;
  if (!av?.sube || av.t <= ultimoAviso) return;
  const primera = ultimoAviso === 0;
  ultimoAviso = av.t;
  if (primera && Date.now() - av.t > 10000) return;   // al recargar no se repite un aviso viejo
  const el = document.createElement("div");
  el.className = `mrrm-rotulo mrrm-rotulo-${av.clave}`;
  el.setAttribute("role", "status");
  const titulo = av.clave === "reloj" ? HORAS[av.n] : t(`Reloj.${av.clave}.Titulo`);
  el.innerHTML = `<strong>${esc(titulo)}</strong><span>${esc(t(`Reloj.${av.clave}.Pub${av.n}`))}</span>`;
  document.body.append(el);
  setTimeout(() => el.classList.add("fuera"), 4200);
  setTimeout(() => el.remove(), 5200);
}

// ---------------------------------------------------------------- Duelo: elección secreta y revelación
async function dialogoApuntar() {
  const d = estado().duelo;
  if (!d) return;
  const mios = d.participantes.map((id) => game.actors.get(id)).filter((a) => a && eligePorMi(a) && d.elecciones[a.id] === undefined);
  for (const yo of mios) {
    const otros = d.participantes.filter((id) => id !== yo.id).map((id) => game.actors.get(id)).filter(Boolean);
    const botones = otros.map((a) => ({ action: a.id, label: a.name, icon: "fa-solid fa-crosshairs" }));
    botones.push({ action: "nadie", label: t("Duelo.Nadie"), icon: "fa-solid fa-hand" });
    const r = await foundry.applications.api.DialogV2.wait({
      window: { title: t("Duelo.Elige", { nombre: yo.name }), icon: "fa-solid fa-gun" }, classes: [ID, "mrrm-dlg-duelo"],
      content: `<div class="mrrm-duelo-caras">${otros.map((a) => `<figure><img src="${esc(retrato(a))}" alt=""><figcaption>${esc(a.name)}</figcaption></figure>`).join("")}</div><p>${t("Duelo.Secreto")}</p>`,
      buttons: botones, rejectClose: false
    });
    if (r) elegirEnDuelo(yo.id, r === "nadie" ? "" : r);
  }
}
alRecibir("duelo-abre", ({ ids }) => {
  if (ids.some((id) => { const a = game.actors.get(id); return a && eligePorMi(a); })) dialogoApuntar();
});
alRecibir("duelo-revela", () => {
  const d = estado().duelo;
  if (!d) return;
  const el = document.createElement("div");
  el.className = "mrrm-standoff";
  el.setAttribute("role", "dialog");
  el.setAttribute("aria-label", t("Duelo.Titulo"));
  el.innerHTML = `<h2>${t("Duelo.Titulo")}</h2><ul>${d.participantes.map((id) => {
    const a = game.actors.get(id), o = d.elecciones[id], b = o ? game.actors.get(o) : null;
    if (!a) return "";
    return `<li><figure><img src="${esc(retrato(a))}" alt=""><figcaption>${esc(a.name)}</figcaption></figure><i class="fa-solid fa-arrow-right-long" aria-hidden="true"></i>
      ${b ? `<figure><img src="${esc(retrato(b))}" alt=""><figcaption>${esc(b.name)}</figcaption></figure>` : `<figure class="nadie"><figcaption>${o === undefined ? t("Duelo.SinDecidir") : t("Duelo.Nadie")}</figcaption></figure>`}</li>`;
  }).join("")}</ul><p>${t("Duelo.Cerrar")}</p>`;
  el.addEventListener("click", () => el.remove());
  document.body.append(el);
  setTimeout(() => el.remove(), 12000);
});
