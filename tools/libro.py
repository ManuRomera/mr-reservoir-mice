#!/usr/bin/env python3
"""Maqueta el libro de Reservoir Mice (HTML → Chrome headless → PDF A4) desde la misma fuente que el módulo:
texto/aventura.md, texto/datos.py y el arte de assets/. Portada a sangre, créditos e índice con páginas, capítulos a dos
columnas justificadas con guionado español, dosieres de los personajes (hoja secreta + ficha de seis casillas),
ayudas recortables y contraportada. Salida: docs/pdf/Reservoir-Mice.pdf
Uso: python3 tools/libro.py"""
import html, json, re, subprocess, sys
from pathlib import Path
import fitz
import pyphen

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "texto")); sys.path.insert(0, str(R / "tools"))
import datos as D  # noqa: E402
import md  # noqa: E402
from arte import COLOR  # el panel de cada ratón, igual que en su retrato

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SAL = R / "docs" / "pdf"; TMP = Path("/Volumes/Datos_Dock/FoundryVTT/Trabajo RM/tmp")
A = R / "assets"
PAPEL = (0.945, 0.910, 0.824)   # #F1E8D2
esc = html.escape
VERSION = json.loads((R / "module.json").read_text())["version"]
GUION = pyphen.Pyphen(lang="es", left=3, right=3)


NUEVA = {"acto1", "acto2", "acto3", "pnj"}  # empiezan en página nueva
ANCHOS = re.compile(r'<div class="tabla">.*?</table></div>|<div class="(?:ancho|tabla ancho)">.*?</table></div>|<div class="mrrm-rejilla">.*?</div>'
                    r'|<figure class="fig-ancha".*?</figure>|<table>.*?</table>', re.S)


def trozo(h):
    # un párrafo suelto repartido en dos columnas deja la capitular en una y el texto en otra
    return f'<div class="cols{" corto" if len(re.sub("<[^>]+>", "", h)) < 500 else ""}">{h}</div>'


def columnas(html):
    """Los bloques a todo el ancho van FUERA del texto a dos columnas: con column-span, Chrome deja páginas medio vacías al imprimir."""
    out, i = [], 0
    for m in ANCHOS.finditer(html):
        b = m.group(0)
        if b.startswith('<div class="tabla">') or (b.startswith("<table>") and b.count("<th") < 3):
            continue  # tablas estrechas: se quedan en la columna
        out += [trozo(html[i:m.start()]), b]; i = m.end()
    out.append(trozo(html[i:]))
    return "".join(x for x in out if re.sub("<[^>]+>", "", x).strip() or "<img" in x or "<figure" in x)


def mapa_vertical():
    """El plano es apaisado: girado llena la página A4."""
    from PIL import Image
    out = TMP / "mapa-vertical.jpg"
    Image.open(A / "scenes" / "mapa-almacen.webp").convert("RGB").rotate(90, expand=True).save(out, quality=88)
    return out.as_uri()


def u(p):
    """Chrome incrusta los WebP descomprimidos (el PDF pesaba 110 MB) y los JPEG tal cual: se pasan a JPEG, o a PNG reducido si tienen transparencia."""
    src = A / p
    if src.suffix != ".webp":
        return src.as_uri()
    from PIL import Image
    out = TMP / "img" / p.replace("/", "_")
    im = Image.open(src)
    alfa = im.mode in ("RGBA", "LA") and im.getchannel("A").getextrema()[0] < 250
    out = out.with_suffix(".png" if alfa else ".jpg")
    if not out.exists() or out.stat().st_mtime < src.stat().st_mtime:
        out.parent.mkdir(parents=True, exist_ok=True)
        im.thumbnail((1400, 1400) if alfa else (2200, 2200), Image.LANCZOS)
        im.save(out, optimize=True) if alfa else im.convert("RGB").save(out, quality=85, optimize=True)
    return out.as_uri()


def figura_justa(slug):
    """La figura del módulo es cuadrada con aire a los lados: en la ficha se usa recortada al cuerpo para que llene la franja."""
    from PIL import Image
    im = Image.open(A / "actors" / "figures" / f"{slug}.webp")
    out = TMP / f"fig-{slug}.png"
    im.crop(im.getchannel("A").getbbox()).save(out)
    return out.as_uri()


def guiona(h):
    """Guiones blandos en palabras de 7+ letras en minúscula, solo en el texto (no en etiquetas)."""
    def palabra(m):
        w = m.group(0)
        return GUION.inserted(w, hyphen="­") if len(w) >= 7 and w.islower() else w
    return re.sub(r">([^<]+)<", lambda m: ">" + re.sub(r"[a-záéíóúñü]+", palabra, m.group(1)) + "<", h)


# ------------------------------------------------------------------ bloques especiales
FIG = {"ref-lancha": "scenes/lancha.webp", "mapa-almacen": "scenes/mapa-almacen.webp"}


def fig(i, pos, cap):
    p = FIG.get(i) or (f"scenes/{i[4:]}.webp" if i.startswith("esc-") else f"actors/portraits/{i[4:]}.webp" if i.startswith("por-") else f"{i}.webp")
    clase = "fig-dcha" if pos in ("right", "left") else "fig-ancha"
    return f'<figure class="{clase}"><img src="{u(p)}" alt="">' + (f"<figcaption>{esc(cap)}</figcaption>" if cap else "") + "</figure>"


def portador(slug):
    return ", ".join(p["n"] for p in D.TODOS if slug in p["inv"].values()) or ("Coche 2 (Rojo)" if slug == "rifle-aguja" else "Todos")


ARMAS = ["mordisco", "automatica-sacapuntas", "chispero-38", "revolver-tambor", "chispero-reglamentario", "chispero-gemelo-der", "la-italiana", "canon-perno-44", "rifle-aguja", "petardo"]


def arsenal():
    filas = []
    for s in ARMAS:
        o = D.OBJ[s]
        dano = o.get("dmg", "d10 / d6") + (f" · {o['dmg2']} a quemarropa" if o.get("dmg2") else "")
        icono = f'<img src="{u(f"items/{s}.webp")}" alt="">' if (A / f"items/{s}.webp").exists() else ""
        nombre = "Chisperos gemelos" if s == "chispero-gemelo-der" else o["n"]
        filas.append(f"<tr><td class='ic'>{icono}</td><td><strong>{esc(nombre)}</strong><br>{esc(o['d'])}</td><td class='dano'>{esc(dano)}</td><td>{esc(portador(s))}</td></tr>")
    return ('<div class="ancho"><h3>Arsenal reciclado</h3><table class="arsenal"><thead><tr><th></th><th>Arma</th><th>Daño</th><th>Quién la lleva</th></tr></thead><tbody>'
            + "".join(filas) + "</tbody></table></div>")


def tabla(clave):
    t = D.TABLAS[clave]
    cab = "".join(f"<th>{esc(c)}</th>" for c in (t["dado"],) + t["cols"])
    filas = "".join("<tr><td class='n'>%d</td>%s</tr>" % (i + 1, "".join(f"<td>{esc(x)}</td>" for x in f)) for i, f in enumerate(t["filas"]))
    ancho = " ancho" if len(t["cols"]) > 1 else ""
    return f'<div class="tabla{ancho}"><h3>{esc(t["n"])} · {t["dado"]}</h3><table><thead><tr>{cab}</tr></thead><tbody>{filas}</tbody></table></div>'


def pnj():
    out = []
    for n in D.PNJ:
        atq = ", ".join(f"{a} {d}" for a, d in n["atq"]) or "sin armas"
        out.append(f'<div class="pnj"><img src="{u("actors/portraits/" + n["slug"] + ".webp")}" alt=""><div><h4>{esc(n["n"])}</h4>'
                   f'<p class="st">FUE {n["fue"]} · DES {n["des"]} · VOL {n["vol"]} · PG {n["pg"]}{" · Arm. " + str(n["arm"]) if n["arm"] else ""} · {esc(atq)}</p>'
                   f'<p>{esc(n["d"])}</p><p class="voz"><em>{esc(n["voz"])}</em>{" " + esc(n["frase"]) if n["frase"] else ""}</p></div></div>')
    return "".join(out)


def especial(nombre, args):
    return {"arsenal": arsenal, "pnj": pnj}.get(nombre, lambda: tabla(args))()


# ------------------------------------------------------------------ dosieres
RANURAS = (("pata", "Pata hábil"), ("torpe", "Pata torpe"), ("c1", "Cuerpo"), ("c2", "Cuerpo"), ("m1", "Mochila"), ("m2", "Mochila"))


def casilla(p, k, lbl):
    s = p["inv"].get(k)
    if not s:
        extra = esc(p.get("extra", "")) if k == "m1" and p.get("extra") else ""
        return f'<div class="cas vacia"><span class="lbl">{lbl}</span><span class="libre">Libre</span>{f"<small>{extra}</small>" if extra else ""}</div>'
    o = D.OBJ[s]
    dano = (f" · {o['dmg']}" + (f"/{o['dmg2']}" if o.get("dmg2") else "")) if o["tipo"] == "weapon" else (f" · Arm. {o['arm']}" if o["tipo"] == "armor" else "")
    return (f'<div class="cas"><span class="lbl">{lbl}</span><img src="{u(f"items/{s}.webp")}" alt=""><strong>{esc(o["n"])}{dano}</strong>'
            f'<small>{esc(o["d"])}</small></div>')


def dosier(p):
    op = "".join(f"<dt>{esc(next(x['n'] for x in D.PJ if x['slug'] == k))}</dt><dd>{esc(v)}</dd>" for k, v in p["opina"].items())
    secreta = (f'<section class="pag dosier"><div class="sello">Confidencial</div><img class="polaroid" src="{u("actors/portraits/" + p["slug"] + ".webp")}" alt="">'
               f'<p class="kick">Hoja secreta · solo para quien lleve a este ratón</p><h1>{esc(p["n"])}</h1><p class="sub">{esc(p["edad"])} · {esc(p["rol"])}</p>'
               f'<h3>Quién eres</h3><p>{esc(p["historia"])}</p><h3>Tu objetivo oculto</h3><p>{esc(p["objetivo"])}</p>'
               + (f"<h3>Qué sabes y opinas de los demás</h3><dl>{op}</dl>" if op else "") + "</section>")
    stats = "".join(f'<div><span>{k}</span><b>{v}</b></div>' for k, v in (("FUE", p["fue"]), ("DES", p["des"]), ("VOL", p["vol"]), ("PG", p["pg"]), ("Pepitas", p["pepitas"])))
    franja = "#%02x%02x%02x" % COLOR[p["slug"]] if p["slug"] in COLOR else "var(--am)"
    ficha = (f'<section class="pag ficha" style="--franja: {franja}"><img class="cuerpo" src="{figura_justa(p["slug"])}" alt="">'
             f'<div class="cab"><p class="kick">Ficha · Mausritter</p><h1>{esc(p["n"])}</h1><p class="sub">{esc(p["lema"])}</p></div>'
             f'<div class="stats">{stats}</div><p class="aspecto"><strong>Aspecto.</strong> {esc(p["aspecto"])}</p><h3>Seis casillas</h3><div class="inv">'
             + "".join(casilla(p, k, l) for k, l in RANURAS) + '</div><p class="nota">Las condiciones ocupan casillas. Si no queda sitio, suelta algo.</p></section>')
    return secreta + ficha


# ------------------------------------------------------------------ apéndice recortable
def recortables():
    tarj = []
    for s, c in D.COND.items():
        tarj.append(f'<div class="tarjeta"><img src="{u(f"items/{s}.webp")}" alt=""><h4>{esc(c["n"])}</h4><p>{esc(c["d"])}</p><p class="q"><strong>Se quita:</strong> {esc(c["quita"])}</p><span>1 casilla</span></div>')
    for s in ("libreta-gris", "microrrastreador", "monedas-oro", "joyas", "caja-botin", "botiquin"):
        o = D.OBJ[s]
        tarj.append(f'<div class="tarjeta clave"><img src="{u(f"items/{s}.webp")}" alt=""><h4>{esc(o["n"])}</h4><p>{esc(o["d"])}</p><span>Objeto clave</span></div>')
    carnes = "".join(f'<img src="{u("handouts/carne-" + p["slug"] + ".webp")}" alt="">' for p in D.TODOS if p["slug"] != "limpiador" and (A / f"handouts/carne-{p['slug']}.webp").exists())
    return (f'<section class="pag apendice"><p class="kick">Apéndice · Ayudas de juego</p><h1>Ayuda 1 · La pintada</h1><img class="ayuda" src="{u("handouts/pintada.webp")}" alt="">'
            f'<h1>Ayuda 2 · La libreta del Sr. Gris</h1><img class="ayuda" src="{u("handouts/libreta-gris.webp")}" alt=""></section>'
            f'<section class="pag apendice"><p class="kick">Apéndice · Recortables</p><h1>Tarjetas de estado y objetos clave</h1><div class="tarjetas">{"".join(tarj)}</div></section>'
            f'<section class="pag apendice"><p class="kick">Apéndice · Recortables</p><h1>Los carnés de Roberto Meléndez</h1><div class="carnes">{carnes}</div></section>'
            f'<section class="lamina mapa"><img src="{mapa_vertical()}" alt=""><p>El almacén del muelle visto desde arriba</p></section>')


# ------------------------------------------------------------------ documento
def documento(pags=None):
    pags = pags or {}
    css = (R / "tools" / "libro.css").read_text().replace("ASSETS/", A.as_uri() + "/")
    caps = md.capitulos(fig, especial)
    indice = "".join(f'<li><span>{esc(c["kicker"].split(" · ")[0])}</span><b>{esc(c["titulo"])}</b><i>{pags.get(c["titulo"], "")}</i></li>' for c in caps)
    indice += (f'<li><span>13</span><b>Los dosieres</b><i>{pags.get("Los dosieres", "")}</i></li>'
               f'<li><span>14</span><b>Apéndice · Ayudas de juego</b><i>{pags.get("Ayuda 1 · La pintada", "")}</i></li>')
    cuerpo = "".join(f'<section class="cap{" nueva" if c["id"] in NUEVA else ""}" id="{c["id"]}"><header><p class="kick">{esc(c["kicker"])}</p><h1>{esc(c["titulo"])}</h1></header>{columnas(guiona(c["html"]))}</section>'
                     for c in caps)
    logo = u("brand/MR_11_Formal_Marfil_Transparente.png")
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Reservoir Mice</title><style>{css}</style></head><body>
<section class="portada"><img src="{u("cover.webp")}" alt=""><div class="titulo"><h1>Reservoir<br>Mice</h1><p>Un golpe ratonil que salió como el culo</p></div>
<div class="pie"><span>Una aventura para <b>Mausritter</b> · 3–6 jugadores · una sesión</span><img src="{logo}" alt="MR"></div></section>
<section class="pag creditos"><div class="gancho"><p class="kick">Iba a ser un golpe limpio</p><p class="grande">Aparcar los coches teledirigidos, esperar hasta medianoche y cruzar la bahía para cobrar. Pero uno viene desangrándose en el asiento de atrás, otro trae un guardia atado en el maletero y la pila de 9 V empieza a parpadear.</p></div>
<h2>Índice</h2><ol class="indice">{indice}</ol>
<div class="cred"><p><b>Adaptación, texto, arte, maquetación y módulo de Foundry:</b> Manu Romera (MR-). Edición revisada {VERSION}.</p>
<p><b>Basada en la estructura de</b> <i>Dockside Dogs</i>, de Paul Fricker (Chaosium), y en el cine de atracos de los noventa. Tercera entrega de la «Trilogía Ratoncino» con <i>The Ratefoul Eight</i> y <i>Malditos Maustardos</i>.</p>
<p><i>Reservoir Mice</i> es una producción independiente de Manu Romera y no está afiliada a Losing Games ni a Chaosium. Se publica bajo la licencia de terceros de Mausritter. <i>Mausritter</i> es © Losing Games.</p>
<p>Texto e ilustraciones bajo licencia CC BY-NC-SA 4.0. Se permite imprimir y fotocopiar para uso personal.</p></div></section>
{cuerpo}
<section class="lamina parte" id="dosieres"><img src="{u("scenes/nave.webp")}" alt=""><div><p class="kick">Para los jugadores</p><h1>Los dosieres</h1><p>Recorta cada pareja de páginas y métela en un sobre. Cada jugador ve solo la suya.</p></div></section>
{"".join(dosier(p) for p in D.TODOS)}
{recortables()}
<section class="contra"><img src="{u("scenes/lancha.webp")}" alt=""><div><h2>Seis colores y ningún inocente</h2><p>Seis ratones trajeados. Cuatro pastilleros llenos de diamantes. Un almacén bajo el embarcadero y una certeza que quema más que la pólvora: uno de ellos lleva placa de la Guardia.</p>
<p>Thriller criminal de una sesión para <b>Mausritter</b>, con dosieres secretos, relojes hasta medianoche, salvación de nervios y un duelo de miradas para terminar como manda el género.</p>
<img class="logo" src="{logo}" alt="MR"></div></section>
</body></html>"""


def imprime(h, nombre):
    TMP.mkdir(parents=True, exist_ok=True); SAL.mkdir(parents=True, exist_ok=True)
    f = TMP / f"{nombre}.html"; f.write_text(h, encoding="utf-8")
    pdf = SAL / f"{nombre}.pdf"
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--allow-file-access-from-files", "--virtual-time-budget=30000",
                    f"--print-to-pdf={pdf}", f.as_uri()], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    d = fitz.open(pdf)
    for p in d:   # papel a sangre por debajo (Chrome deja los márgenes en blanco)
        p.draw_rect(p.rect, color=None, fill=PAPEL, overlay=False)
    tmp = pdf.with_suffix(".tmp.pdf"); d.save(tmp, garbage=3, deflate=True); d.close(); tmp.replace(pdf)
    return pdf


def paginas(pdf, titulos):
    d = fitz.open(pdf); res = {}
    for i, p in enumerate(d):
        for b in p.get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                if not ln["spans"] or max(sp["size"] for sp in ln["spans"]) < 20:
                    continue
                txt = " ".join("".join(sp["text"] for sp in ln["spans"]).replace("­", "").split()).lower()
                for t in titulos:
                    if len(txt) > 5 and t.lower().startswith(txt):
                        res.setdefault(t, i + 1)
    return res


if __name__ == "__main__":
    nombre = "Reservoir-Mice"
    pdf = imprime(documento(), nombre)
    titulos = [c["titulo"] for c in md.capitulos(fig, especial)] + ["Los dosieres", "Ayuda 1 · La pintada"]
    pdf = imprime(documento(paginas(pdf, titulos)), nombre)
    print(pdf, fitz.open(pdf).page_count, "páginas")
