"""Lee texto/aventura.md (Markdown con directivas propias) y lo convierte en capítulos HTML.
Lo usan tools/foundry.py (diarios) y tools/libro.py (PDF); cada uno decide cómo pintar imágenes y bloques especiales.

  # Título {id=slug kicker="01 · …"}   capítulo           ## Título            sección
  > texto                               caja de lectura    :::regla Título … :::  regla   :::caja Título … :::  recuadro
  :::rejilla … :::                      tarjetas           @@fig id pos [cap="…"]   imagen   @@nombre args   bloque especial"""
import re
from pathlib import Path
import markdown

R = Path(__file__).resolve().parent.parent
CAP = re.compile(r'^# (.+?)\s*\{id=(\S+)\s+kicker="([^"]*)"\}\s*$')


def md(t):
    h = markdown.markdown(t, extensions=["tables"])
    return h.replace("<blockquote>", '<blockquote class="mrrm-lectura">')


def capitulos(fig, especial, ruta=R / "texto" / "aventura.md"):
    """fig(id, pos, cap) -> html ; especial(nombre, args) -> html. Devuelve [{id, titulo, kicker, html}]."""
    caps, cur, buf, caja = [], None, [], None

    def vuelca():
        if buf and cur is not None:
            cur["partes"].append(md("\n".join(buf)))
        buf.clear()

    for linea in ruta.read_text(encoding="utf-8").splitlines():
        m = CAP.match(linea)
        if m:
            vuelca()
            cur = dict(titulo=m.group(1), id=m.group(2), kicker=m.group(3), partes=[])
            caps.append(cur)
            continue
        if caja is not None:
            if linea.strip() == ":::":
                tipo, tit, cuerpo = caja
                h = f"<h4>{tit}</h4>" if tit else ""
                cur["partes"].append(f'<div class="mrrm-{tipo}">{h}{md(chr(10).join(cuerpo))}</div>')
                caja = None
            else:
                caja[2].append(linea)
            continue
        if linea.startswith(":::"):
            vuelca()
            tipo, _, tit = linea[3:].partition(" ")
            caja = (tipo.strip(), tit.strip(), [])
            continue
        if linea.startswith("@@"):
            vuelca()
            partes = linea[2:].split(None, 1)
            nombre, args = partes[0], (partes[1] if len(partes) > 1 else "")
            if nombre == "fig":
                cap = re.search(r'cap="([^"]*)"', args)
                a = args.split()
                cur["partes"].append(fig(a[0], a[1] if len(a) > 1 else "full", cap.group(1) if cap else ""))
            else:
                cur["partes"].append(especial(nombre, args.strip()))
            continue
        buf.append(linea)
    vuelca()
    for c in caps:
        c["html"] = "\n".join(c.pop("partes"))
    return caps
