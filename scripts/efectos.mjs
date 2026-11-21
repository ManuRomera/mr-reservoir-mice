// Efectos de sonido y destellos compartidos: el GM (o quien lance la regla) los dispara y suenan en todas las pantallas.
import { ID, ruta, alRecibir, aTodos } from "./estado.mjs";

const VISUAL = { disparo: "rojo", standoff: "rojo", campanadas: "amarillo", pintada: "negro", sirena: "azul", amartillar: "rojo" };

function reproducir({ nombre }) {
  if (game.settings.get(ID, "efectosSonido")) {
    const volume = Number(game.settings.get(ID, "volumenEfectos")) || 0;
    if (volume > 0) foundry.audio.AudioHelper.play({ src: ruta(`assets/audio/sfx/${nombre}.ogg`), volume, loop: false }, false).catch(() => {});
  }
  const color = VISUAL[nombre];
  if (!color || !game.settings.get(ID, "efectosVisuales") || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const el = document.createElement("div");
  el.className = `mrrm-destello mrrm-destello-${color}`;
  el.setAttribute("aria-hidden", "true");
  document.body.append(el);
  setTimeout(() => el.remove(), 1200);
}
alRecibir("efecto", reproducir);

/** Suena en todos los clientes conectados. */
export const efecto = (nombre) => aTodos("efecto", { nombre });
