#!/usr/bin/env python3
"""Construye la aventura de Foundry desde texto/ (fuente única):
  _data/aventura.json        documento Adventure (actores, objetos, diarios, escenas, tablas, macros, listas de sonido)
  content/direccion-es.json  paquete para MR- Dirección (escenas, música, motivos, efectos, figuras, hitos)
  content/pizarra-es.json    pizarra de sospechas para MR- Pizarra (formato mr-pizarra-import 1)
Después: node scripts/build.mjs (LevelDB + zip). Uso: python3 tools/foundry.py"""
import hashlib, html, json, sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "texto")); sys.path.insert(0, str(R / "tools"))
sys.path.insert(0, "/Volumes/Datos_Dock/FoundryVTT/Trabajo LOGO/marca")
import datos as D  # noqa: E402
import md  # noqa: E402
import marca  # noqa: E402

ID = "mr-reservoir-mice"
VERSION = json.loads((R / "module.json").read_text())["version"]
A62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
esc = html.escape


def uid(s):
    n = int(hashlib.sha256((ID + s).encode()).hexdigest(), 16); o = ""
    for _ in range(16):
        n, r = divmod(n, 62); o += A62[r]
    return o


def ruta(p):
    return f"modules/{ID}/{p}"


def existe(p):
    return (R / p).exists()


def img(p, defecto="icons/svg/mystery-man.svg"):
    return ruta(p) if existe(p) else defecto


# ------------------------------------------------------------------ carpetas
FOLD = {}


def carpeta(nombre, tipo, orden, color=None):
    f = dict(_id=uid(f"folder:{tipo}:{nombre}"), name=nombre, type=tipo, folder=None, sorting="m", sort=orden, color=color, flags={}, description="")
    FOLD[(tipo, nombre)] = f["_id"]
    return f


folders = [carpeta("La banda", "Actor", 0, "#8e2a1c"), carpeta("PNJ", "Actor", 1), carpeta("Amenazas", "Actor", 2), carpeta("Vehículos", "Actor", 3),
           carpeta("Armas", "Item", 0), carpeta("Equipo", "Item", 1), carpeta("Pistas y botín", "Item", 2), carpeta("Condiciones", "Item", 3),
           carpeta("Reservoir Mice · DJ", "JournalEntry", 0, "#8e2a1c"), carpeta("Dosieres secretos", "JournalEntry", 1, "#161412"), carpeta("Ayudas de juego", "JournalEntry", 2),
           carpeta("Reservoir Mice", "Scene", 0, "#f2c21b"), carpeta("Reservoir Mice", "RollTable", 0), carpeta("Reservoir Mice", "Macro", 0)]

# ------------------------------------------------------------------ objetos
CASILLAS = dict(pata=(-270, -150), torpe=(-270, -20), c1=(-140, -150), c2=(-140, -20), m1=(10, -150), m2=(10, -20))
PISTAS = {"monedas-oro", "libreta-gris", "microrrastreador", "caja-botin", "joyas", "radio", "pila-9v", "sombrero-gris", "cecina-queso", "tapon-cerveza", "baraja", "carne-falso", "farol"}


def sheet(x=0, y=0):
    return dict(active=False, currentX=x, currentY=y, initialX=x, initialY=y, xOffset=0, yOffset=0, rotation=0, curWidth=1, curHeight=1, zIndex=1000 + x + y)


def item_doc(slug, x=0, y=0, suf="", folder=None):
    if slug in D.COND:
        c = D.COND[slug]
        sysd = dict(description=f"<p>{esc(c['d'])}</p><p><strong>Se quita:</strong> {esc(c['quita'])}</p>", clear=c["quita"], desc=c["d"], color="white")
        tipo, nombre, w, h = "condition", c["n"], 1, 1
    else:
        o = D.OBJ[slug]
        tipo, nombre, w, h = o["tipo"], o["n"], o.get("w", 1), o.get("h", 1)
        txt = o["d"] + (f" Daño {o['dmg']}" + (f" ({o['dmg2']} a quemarropa)" if o.get("dmg2") else "") + "." if tipo == "weapon" else "")
        sysd = dict(description=f"<p>{esc(txt)}</p>", color="white", weight=0, cost=0, tag="")
        if tipo == "item":
            sysd["placement"] = "hand"
        if tipo == "weapon":
            sysd.update(placement="hand", weapon=dict(dmg1=o["dmg"], dmg2=o.get("dmg2", ""), selected=0, canSwap=bool(o.get("dmg2"))))
        if tipo == "armor":
            sysd["armor"] = dict(value=o["arm"])
    sysd.update(size=dict(width=w, height=h), sheet=sheet(x, y), pips=dict(value=0, max=D.OBJ.get(slug, {}).get("pips", 0), html=""))
    return dict(_id=uid(f"item:{slug}{suf}"), name=nombre, type=tipo, img=img(f"assets/items/{slug}.webp", "icons/svg/item-bag.svg"), system=sysd,
                effects=[], folder=folder, sort=0, ownership=dict(default=0), flags={ID: dict(slug=slug)})


def bloqueo(suf):
    return dict(_id=uid(f"item:sin-sitio{suf}"), name="Sin sitio (regla del golpe)", type="item", img=ruta("assets/ui/sin-sitio.webp"),
                system=dict(description="<p>En Reservoir Mice solo hay seis casillas: dos de patas, dos de cuerpo y dos de mochila. Esta parte de la mochila no existe. Solo el DJ puede quitarla.</p>",
                            weight=0, cost=0, tag="", placement="hand", color="white", size=dict(width=2, height=2), sheet=sheet(205, -85), pips=dict(value=0, max=0, html="")),
                effects=[], folder=None, sort=0, ownership=dict(default=0), flags={ID: dict(slug="sin-sitio", bloqueo=True)})


def carpeta_obj(slug):
    if slug in D.COND:
        return "Condiciones"
    if slug in PISTAS:
        return "Pistas y botín"
    return "Armas" if D.OBJ[slug]["tipo"] == "weapon" or slug == "petardo" else "Equipo"


items = [item_doc(s, folder=FOLD[("Item", carpeta_obj(s))]) for s in list(D.OBJ) + list(D.COND) if s != "mordisco"]

# ------------------------------------------------------------------ actores
def stats(f, d, v):
    return {k: dict(value=x, max=x, label=l) for k, x, l in zip(("strength", "dexterity", "will"), (f, d, v), ("Strength", "Dexterity", "Will"))}


def token(slug, nombre, disp, tam=1, link=False, vision=False):
    return dict(name=nombre, displayName=30, actorLink=link, disposition=disp, width=tam, height=tam, lockRotation=True,
                texture=dict(src=img(f"assets/actors/figures/{slug}.webp"), scaleX=1, scaleY=1, fit="contain", anchorX=0.5, anchorY=0.5),
                bar1=dict(attribute="health"), displayBars=20, sight=dict(enabled=vision, range=30), ring=dict(enabled=False))


def ficha_pj(p, tipo="pj"):
    inv = [item_doc(s, *CASILLAS[k], suf=":" + p["slug"]) for k, s in p["inv"].items()] + [bloqueo(":" + p["slug"])]
    bio = (f"<p><em>{esc(p['edad'])} · {esc(p['rol'])} · {esc(p['lema'])}</em></p><p>{esc(p['aspecto'])}</p>"
           + (f"<p>{esc(p['extra'])}</p>" if p.get("extra") else "") + "<p>Lo que esconde está en su dosier secreto.</p>")
    return dict(_id=uid("actor:" + p["slug"]), name=p["n"], type="character", img=img(f"assets/actors/portraits/{p['slug']}.webp"),
                system=dict(health=dict(value=p["pg"], min=0, max=p["pg"]), hits=dict(value=2, max=2), armor=0, biography=bio, notes="",
                            description=dict(background=p["rol"], birthsign="", coat="", look=p["aspecto"]), level=dict(value=1, xp=0), pips=dict(value=p["pepitas"]),
                            grit=dict(value=0, ignored=""), stats=stats(p["fue"], p["des"], p["vol"]), other=dict(grit=dict(value=0))),
                prototypeToken=token(p["slug"], p["n"], 1, 1, True, True), items=inv, effects=[], folder=FOLD[("Actor", "La banda")], sort=0,
                ownership=dict(default=0), flags={ID: dict(slug=p["slug"], tipo=tipo)})


def ficha_pnj(n):
    atq = [dict(_id=uid(f"atq:{n['slug']}:{i}"), name=a, type="weapon", img=img("assets/items/chispero-38.webp") if "hispero" in a else "icons/svg/sword.svg",
                system=dict(description="", weight=0, cost=0, tag="", placement="hand", color="white", weapon=dict(dmg1=d, dmg2="", selected=0, canSwap=False),
                            size=dict(width=1, height=1), sheet=sheet(), pips=dict(value=0, max=0, html="")), effects=[], folder=None, sort=0, ownership=dict(default=0), flags={})
           for i, (a, d) in enumerate(n["atq"])]
    bio = f"<p>{esc(n['d'])}</p><p><strong>Voz:</strong> {esc(n['voz'])}</p>" + (f"<p><em>{esc(n['frase'])}</em></p>" if n["frase"] else "")
    amenaza = n["slug"] in ("rata", "guardia", "raterillo")
    return dict(_id=uid("actor:" + n["slug"]), name=n["n"], type="creature", img=img(f"assets/actors/portraits/{n['slug']}.webp"),
                system=dict(health=dict(value=n["pg"], min=0, max=n["pg"]), hits=dict(value=2, max=2), armor=n["arm"], biography=bio, notes="",
                            description=dict(disposition=""), stats=stats(n["fue"], n["des"], n["vol"])),
                prototypeToken=token(n["slug"], n["n"], -1 if n["slug"] in ("rata", "guardia") else 0, n.get("tam", 1)), items=atq, effects=[],
                folder=FOLD[("Actor", "Amenazas" if amenaza else "PNJ")], sort=0, ownership=dict(default=0), flags={ID: dict(slug=n["slug"], tipo="pnj")})


VEH = [("furgoneta", "Furgoneta blanca", ["caja-botin"] * 4), ("coche1", "Coche 1 · deportivo rojo", []), ("coche2", "Coche 2 · sedán", ["rifle-aguja"])]


def vehiculo(slug, nombre, carga):
    inv = [item_doc(s, 10 + 130 * (i % 3), 10 + 130 * (i // 3), suf=f":{slug}:{i}") for i, s in enumerate(carga)]
    for i, it in enumerate(inv):
        if it["flags"][ID]["slug"] == "caja-botin":
            it["name"] = f"Caja {i + 1} del botín" + (" (doble fondo)" if i == 3 else "")
    t = token(slug, nombre, 0, 2)
    t["texture"]["src"] = img(f"assets/vehicles/{slug}.webp")
    t.update(displayBars=0, bar1=dict(attribute=None), lockRotation=False)
    return dict(_id=uid("actor:" + slug), name=nombre, type="storage", img=img(f"assets/vehicles/{slug}.webp"),
                system=dict(health=dict(value=0, min=0, max=0), hits=dict(value=0, max=0), armor=0, biography="", notes="", description=dict(disposition=""), size=dict(width=3, height=2), storeDiv=""),
                prototypeToken=t, items=inv, effects=[], folder=FOLD[("Actor", "Vehículos")], sort=0, ownership=dict(default=3), flags={ID: dict(slug=slug, tipo="vehiculo")})


actors = [ficha_pj(p) for p in D.PJ] + [ficha_pj(D.LIMPIADOR, "limpiador")] + [ficha_pnj(n) for n in D.PNJ] + [vehiculo(*v) for v in VEH]

# ------------------------------------------------------------------ tablas
def tabla(clave):
    t = D.TABLAS[clave]
    res = [dict(_id=uid(f"res:{clave}:{i}"), type="text", name=f[0] if len(f) > 1 else str(i + 1), description=f"<p>{esc(f[-1])}</p>", img="icons/svg/d20-black.svg",
                range=[i + 1, i + 1], weight=1, drawn=False, flags={}) for i, f in enumerate(t["filas"])]
    return dict(_id=uid("tabla:" + clave), name=t["n"], img=img("assets/items/baraja.webp"), description="", formula=t["dado"], replacement=True, displayRoll=True,
                results=res, folder=FOLD[("RollTable", "Reservoir Mice")], sort=0, ownership=dict(default=0), flags={ID: dict(slug=clave)})


tablas = [tabla(k) for k in D.TABLAS]
TABLA_ID = {k: uid("tabla:" + k) for k in D.TABLAS}

# ------------------------------------------------------------------ diarios
FIG = {"ref-lancha": "assets/scenes/lancha.webp", "mapa-almacen": "assets/scenes/mapa-almacen.webp"}


def fig_ruta(i):
    if i in FIG:
        return FIG[i]
    if i.startswith("esc-"):
        return f"assets/scenes/{i[4:]}.webp"
    if i.startswith("por-"):
        return f"assets/actors/portraits/{i[4:]}.webp"
    return f"assets/{i}.webp"


def fig_html(i, pos, cap):
    clase = ' class="derecha"' if pos in ("right", "left") else ""
    return f'<figure{clase}><img src="{img(fig_ruta(i), "")}" alt="">' + (f"<figcaption>{esc(cap)}</figcaption>" if cap else "") + "</figure>"


def portador(slug):
    return ", ".join(p["n"] for p in D.TODOS if slug in p["inv"].values()) or ("Coche 2 (Rojo)" if slug == "rifle-aguja" else "Todos")


def tabla_html(clave, enlace=True):
    t = D.TABLAS[clave]
    cab = "".join(f"<th>{esc(c)}</th>" for c in (t["dado"],) + t["cols"])
    filas = "".join("<tr><td>%d</td>%s</tr>" % (i + 1, "".join(f"<td>{esc(x)}</td>" for x in f)) for i, f in enumerate(t["filas"]))
    link = f"<p>@UUID[RollTable.{TABLA_ID[clave]}]{{Tirar: {esc(t['n'])}}}</p>" if enlace else ""
    return f"<h3>{esc(t['n'])} · {t['dado']}</h3><table><thead><tr>{cab}</tr></thead><tbody>{filas}</tbody></table>{link}"


ARMAS = ["mordisco", "automatica-sacapuntas", "chispero-38", "revolver-tambor", "chispero-reglamentario", "chispero-gemelo-der", "la-italiana", "canon-perno-44", "rifle-aguja", "petardo"]


def arsenal_html():
    filas = []
    for s in ARMAS:
        o = D.OBJ[s]
        dano = o.get("dmg", "d10 / d6") + (f" ({o['dmg2']} a quemarropa)" if o.get("dmg2") else "")
        nombre = "Chisperos gemelos" if s == "chispero-gemelo-der" else o["n"]
        filas.append(f"<tr><td><strong>{esc(nombre)}</strong></td><td>{esc(o['d'])}</td><td>{esc(dano)}</td><td>{esc(portador(s))}</td></tr>")
    return "<h3>Arsenal reciclado</h3><table><thead><tr><th>Arma</th><th>A escala ratón</th><th>Daño</th><th>Quién la lleva</th></tr></thead><tbody>" + "".join(filas) + "</tbody></table>"


def pnj_html():
    out = []
    for n in D.PNJ:
        atq = ", ".join(f"{a} {d}" for a, d in n["atq"]) or "sin armas"
        out.append(f'<div class="mrrm-caja"><h4>@UUID[Actor.{uid("actor:" + n["slug"])}]{{{esc(n["n"])}}}</h4><p><strong>FUE {n["fue"]} · DES {n["des"]} · VOL {n["vol"]} · PG {n["pg"]}'
                   f'{" · Armadura " + str(n["arm"]) if n["arm"] else ""}</strong> · {esc(atq)}</p><p>{esc(n["d"])}</p><p><em>{esc(n["voz"])}</em> {esc(n["frase"])}</p></div>')
    return "".join(out)


def especial(nombre, args):
    return {"arsenal": arsenal_html, "pnj": pnj_html}.get(nombre, lambda: tabla_html(args))()


caps = md.capitulos(fig_html, especial)


def pagina(nombre, contenido, orden, tipo="text", src=None, titulo=True):
    p = dict(_id=uid(f"pag:{nombre}:{orden}"), name=nombre, type=tipo, sort=orden * 1000, title=dict(show=titulo, level=1), ownership=dict(default=-1), flags={})
    if tipo == "image":
        p.update(src=src, image=dict(caption=contenido))
    else:
        p.update(text=dict(content=contenido, format=1))
    return p


USO_FOUNDRY = """<p class="mrrm-kicker">00 · Cómo se juega en Foundry</p>
<p>Todo lo de la mesa está en la barra de herramientas de la izquierda, en el grupo <strong>Reservoir Mice</strong> (icono de saco de dinero), y en el <strong>Panel del DJ</strong>:</p>
<ul><li><strong>La banda.</strong> Elige qué jugador lleva cada ratón. Recibe la ficha, su dosier secreto se le abre en pantalla y nadie más puede leerlo.</li>
<li><strong>La noche.</strong> Los tres relojes (hora, cerco y paranoia) se ven en una esquina de la pantalla de todos. Al avanzarlos, la mesa ve un rótulo grande; tú recibes en privado lo que toca hacer. Apunta aquí la contraseña del Flashback 2.</li>
<li><strong>Reglas del golpe.</strong> Salvación de nervios para los ratones marcados (mete Paranoico o Dedo flojo en una casilla libre), la rueda del Flashback 1 y el <strong>duelo de miradas</strong>: cada jugador elige en secreto a quién apunta y tú lo revelas de golpe.</li>
<li><strong>Ayudas.</strong> La pintada a toda la mesa, la libreta del Sr. Gris solo al elegido y el plano del almacén.</li></ul>
<p>Los jugadores tienen en la misma barra su botón de <strong>Salvación de nervios</strong>. Las fichas de la banda tienen seis casillas: la parte de la mochila que no existe está tapada por «Sin sitio».</p>
<p><strong>Integraciones.</strong> Con <em>MR- Dirección</em> activo, sus escenas, música, motivos, efectos, figuras e hitos aparecen en su barra. Con <em>MR- Pizarra</em> activo, el botón <em>Pizarra de sospechas</em> la deja preparada por capas para ir revelándola.</p>"""

guia_paginas = [pagina("Reservoir Mice", "Un golpe ratonil que salió como el culo.", 0, "image", ruta("assets/cover.webp")), pagina("Cómo se juega en Foundry", f'<div class="mrrm-diario">{USO_FOUNDRY}</div>', 1)]
for k, c in enumerate(caps):
    guia_paginas.append(pagina(c["titulo"], f'<div class="mrrm-diario"><p class="mrrm-kicker">{esc(c["kicker"])}</p>{c["html"]}</div>', k + 2))
diarios = [dict(_id=uid("diario:guia"), name="Reservoir Mice · Guía del DJ", pages=guia_paginas, folder=FOLD[("JournalEntry", "Reservoir Mice · DJ")], sort=0,
                ownership=dict(default=0), flags={ID: dict(guia=True)}, categories=[])]


def dosier_html(p):
    inv = "".join(f"<dt>{lbl}</dt><dd>{esc(D.OBJ[p['inv'][k]]['n']) if k in p['inv'] else '—'}</dd>"
                  for k, lbl in (("pata", "Pata hábil"), ("torpe", "Pata torpe"), ("c1", "Cuerpo 1"), ("c2", "Cuerpo 2"), ("m1", "Mochila 1"), ("m2", "Mochila 2")))
    op = "".join(f"<dt>{esc(next(x['n'] for x in D.PJ if x['slug'] == k))}</dt><dd>{esc(v)}</dd>" for k, v in p["opina"].items())
    foto = img(f"assets/actors/portraits/{p['slug']}.webp", "")
    return (f'<div class="mrrm-dosier"><span class="mrrm-sello">CONFIDENCIAL</span><img class="mrrm-foto" src="{foto}" alt="">'
            f'<h1>{esc(p["n"])}</h1><p><em>{esc(p["edad"])} · {esc(p["rol"])} · {esc(p["lema"])}</em></p>'
            f'<div class="mrrm-stats"><span>FUE {p["fue"]}</span><span>DES {p["des"]}</span><span>VOL {p["vol"]}</span><span>PG {p["pg"]}</span><span>{p["pepitas"]} pepitas</span></div>'
            f'<h3>Quién eres</h3><p>{esc(p["historia"])}</p><h3>Tu objetivo oculto</h3><p>{esc(p["objetivo"])}</p>'
            + (f"<p>{esc(p['extra'])}</p>" if p.get("extra") else "")
            + (f"<h3>Qué opinas de los demás</h3><dl>{op}</dl>" if op else "")
            + f"<h3>Lo que llevas (seis casillas)</h3><dl>{inv}</dl></div>")


for p in D.TODOS:
    paginas = [pagina("Dosier", dosier_html(p), 0, titulo=False)]
    if existe(f"assets/handouts/carne-{p['slug']}.webp"):
        paginas.append(pagina("Tu carné", "Documento falso a nombre de Roberto Meléndez.", 1, "image", ruta(f"assets/handouts/carne-{p['slug']}.webp")))
    diarios.append(dict(_id=uid("diario:dosier:" + p["slug"]), name=f"Dosier · {p['n']}", pages=paginas, folder=FOLD[("JournalEntry", "Dosieres secretos")],
                        sort=D.TODOS.index(p), ownership=dict(default=0), flags={ID: dict(dosier=p["slug"])}, categories=[]))

tarjetas = "".join(f'<div class="mrrm-regla"><h4>{esc(c["n"])}</h4><p>{esc(c["d"])}</p><p><strong>Se quita:</strong> {esc(c["quita"])}</p></div>' for c in D.COND.values())
libreta_txt = "".join(f"<p><strong>{h}</strong> — {esc(t)}</p>" for h, t in D.LIBRETA) + f"<p><em>{esc(D.FIRMA_LIBRETA)}</em></p>"
ayudas_pag = [pagina("1 · La pintada", " / ".join(D.PINTADA), 0, "image", ruta("assets/handouts/pintada.webp")),
              pagina("2 · La libreta del Sr. Gris", "", 1, "image", ruta("assets/handouts/libreta-gris.webp")),
              pagina("2 · La libreta (texto)", f'<div class="mrrm-dosier">{libreta_txt}</div>', 2),
              pagina("Plano del almacén", "El almacén visto desde arriba. La línea discontinua es la pasarela elevada.", 3, "image", ruta("assets/scenes/mapa-almacen.webp")),
              pagina("Tarjetas de estado", f'<div class="mrrm-diario">{tarjetas}</div>', 4)]
diarios.append(dict(_id=uid("diario:ayudas"), name="Ayudas de juego", pages=ayudas_pag, folder=FOLD[("JournalEntry", "Ayudas de juego")], sort=0,
                    ownership=dict(default=0), flags={ID: dict(ayudas=True)}, categories=[]))
PAG_CAP = {c["id"]: uid(f"pag:{c['titulo']}:{k + 2}") for k, c in enumerate(caps)}

# ------------------------------------------------------------------ sonido
MUSICA = [("tema", "Reservoir Mice (tema)"), ("espera", "La espera"), ("huida", "La huida"), ("botin", "El botín"), ("desague", "El desagüe"),
          ("sardinas", "La Lata de Sardinas"), ("medianoche", "Medianoche"), ("epilogo", "Otra vida"), ("amanecer", "Amanecer en tierra")]
MOTIVOS = [("tension", "Tensión", "hourglass-half"), ("paranoia", "Paranoia", "eye"), ("persecucion", "Persecución", "car-burst"), ("standoff", "Duelo", "gun"),
           ("calma", "Calma tensa", "smoking"), ("misterio", "Misterio", "user-secret"), ("oscuridad", "A oscuras", "lightbulb"), ("triunfo", "Triunfo", "sack-dollar"), ("derrota", "Derrota", "skull")]
AMBIENTES = [("muelle", "Agua bajo el muelle"), ("zumbido", "Zumbido de la pila")]
EFECTOS = [("disparo", "Disparo", "gun"), ("amartillar", "Amartillar", "hand-point-right"), ("golpes-maletero", "Golpes en el maletero", "car"), ("persiana", "La persiana", "warehouse"),
           ("chispazo", "Chispazo de la pila", "bolt"), ("campanadas", "Doce campanadas", "bell"), ("sirena", "Sirenas", "tower-broadcast"), ("sirenaLejos", "Sirenas lejanas", "tower-broadcast"),
           ("motor-lancha", "Motor de la lancha", "ship"), ("maullido", "El gato del Gigante", "cat"), ("radio", "Radio de la Guardia", "radio"), ("rata", "Ratas", "paw"),
           ("latido", "Latido", "heart-pulse"), ("tictac", "Tictac", "clock"), ("pintada", "La pintada", "spray-can"), ("standoff", "Duelo", "gun")]


def sonido(carpeta, slug, nombre, canal, repetir, vol):
    return dict(_id=uid(f"sonido:{carpeta}:{slug}"), name=nombre, description="", path=ruta(f"assets/audio/{carpeta}/{slug}.ogg"), channel=canal, playing=False, pausedTime=None,
                repeat=repetir, volume=vol, fade=2000 if repetir else None, sort=0, flags={ID: dict(slug=f"{carpeta}-{slug}")})


def lista(nombre, carpeta, elems, canal, repetir, vol, orden):
    return dict(_id=uid("lista:" + carpeta), name=nombre, description="", mode=0, channel=canal, sounds=[sonido(carpeta, e[0], e[1], canal, repetir, vol) for e in elems],
                playing=False, folder=None, sorting="m", sort=orden, seed=None, fade=None, ownership=dict(default=0), flags={ID: dict(lista=carpeta)})


playlists = [lista("Reservoir Mice · Música", "music", MUSICA, "music", True, 0.5, 0), lista("Reservoir Mice · Motivos", "moods", MOTIVOS, "music", True, 0.5, 1),
             lista("Reservoir Mice · Ambiente", "ambient", AMBIENTES, "environment", True, 0.4, 2), lista("Reservoir Mice · Efectos", "sfx", EFECTOS, "interface", False, 0.8, 3)]

# ------------------------------------------------------------------ escenas
# (orden, slug, nombre, música, capítulo de la guía, reparto de figuras)
BANDA = [p["slug"] for p in D.PJ]
ESC = [(0, "muelle", "El muelle", "tema", "acto1", []), (1, "nave", "A1 · La nave principal", "espera", "almacen", BANDA + ["gris"]),
       (2, "mapa-almacen", "Plano del almacén", "espera", "almacen", []), (3, "callejon", "Flashback 1 · La huida", "huida", "acto1", ["verde", "rojo", "negro"]),
       (4, "furgoneta", "El botín", "botin", "pistas", []), (5, "cocina", "A4 · La cocina y la pila", "espera", "almacen", []),
       (6, "pasarela", "A5 · La pasarela", "espera", "almacen", []), (7, "retrete", "A2 · El retrete", "desague", "acto2", []),
       (8, "maletero", "El maletero", "desague", "acto2", ["pescador"]), (9, "cafeteria", "Flashback 2 · La Lata de Sardinas", "sardinas", "acto2", BANDA + ["vito"]),
       (10, "apagon", "A oscuras", "desague", "tablas", []), (11, "lancha", "Medianoche", "medianoche", "acto3", ["barquero"]),
       (12, "palacio", "Epílogo · La otra orilla", "epilogo", "epilogos", []), (13, "amanecer", "Epílogo · En tierra", "amanecer", "epilogos", []),
       (14, "comisaria", "Postcréditos · Comisaría", "amanecer", "epilogos", [])]


def escena(orden, slug, nombre, musica, cap, _reparto):
    mapa = slug == "mapa-almacen"
    w, h = (2304, 1536) if mapa else (1920, 1080)
    mx, my, mw, mh = marca.caja_animada(w, h)
    tiles = [dict(_id=uid(f"tile:{slug}:marca"), texture=dict(src=ruta("assets/brand/mr-marca.webm"), scaleX=1, scaleY=1, tint="#ffffff", alphaThreshold=0, fit="fill", anchorX=0.5, anchorY=0.5),
                  x=mx, y=my, width=mw, height=mh, elevation=0, sort=0, rotation=0, alpha=1, hidden=False, locked=True, restrictions=dict(light=False, weather=False),
                  occlusion=dict(mode=0, alpha=0), video=dict(loop=True, autoplay=True, volume=0), flags={})]
    tokens = []
    if mapa:
        for i, (v, n, _) in enumerate(VEH):
            a = next(x for x in actors if x["flags"][ID]["slug"] == v)
            tokens.append(dict(_id=uid(f"tok:{v}"), name=n, actorId=a["_id"], actorLink=True, x=60 + i * 230, y=1536 - 300, width=2, height=2, rotation=0,
                               texture=dict(src=a["prototypeToken"]["texture"]["src"], scaleX=1, scaleY=1, fit="contain"), disposition=0, displayName=30, displayBars=0,
                               lockRotation=False, hidden=False, sight=dict(enabled=False), ring=dict(enabled=False), flags={}))
    return dict(_id=uid("escena:" + slug), name=nombre, active=False, navigation=orden < 12, navOrder=orden, navName=nombre,
                background=dict(src=ruta(f"assets/scenes/{slug}.webp")), width=w, height=h, padding=0, backgroundColor="#161412",
                grid=dict(type=1 if mapa else 0, size=96 if mapa else 100, style="solidLines", thickness=1, color="#000000", alpha=0.15 if mapa else 0, distance=1, units="m"),
                initial=None, tokenVision=False, fog=dict(exploration=False), environment=dict(darknessLevel=0.6 if slug == "apagon" else 0, globalLight=dict(enabled=True)),
                thumb=img(f"assets/scenes/thumbs/{slug}.webp", None), tiles=tiles, tokens=tokens, drawings=[], lights=[], notes=[], sounds=[], templates=[], walls=[], regions=[],
                journal=diarios[0]["_id"], journalEntryPage=PAG_CAP.get(cap), playlist=playlists[0]["_id"], playlistSound=uid(f"sonido:music:{musica}"),
                folder=FOLD[("Scene", "Reservoir Mice")], sort=orden * 1000, ownership=dict(default=0), flags={ID: dict(slug=slug, orden=orden)})


escenas = [escena(*e) for e in ESC]

# ------------------------------------------------------------------ macros
MAC = [("Panel del DJ", "panel()", "assets/actors/portraits/gris.webp"), ("Salvación de nervios", "salvarNervios(game.user.character ?? canvas.tokens.controlled[0]?.actor)", "assets/items/paranoico.webp"),
       ("Mostrar la pintada", 'mostrarAyuda("pintada")', "assets/handouts/pintada.webp"), ("Contraseña a medianoche", "decirContrasena()", "assets/actors/portraits/barquero.webp"),
       ("Pizarra de sospechas", "abrirPizarra()", "assets/items/libreta-gris.webp"), ("Importar la aventura", "importarAventura()", "assets/cover.webp")]
macros = [dict(_id=uid("macro:" + n), name=n, type="script", img=img(i, "icons/svg/dice-target.svg"), scope="global", command=f'game.modules.get("{ID}").api.{c};',
               author=uid("autor"), folder=FOLD[("Macro", "Reservoir Mice")], sort=k * 1000, ownership=dict(default=0), flags={ID: dict(macro=True)}) for k, (n, c, i) in enumerate(MAC)]

adv = dict(_id=uid("adventure"), name="MR- Reservoir Mice", img=ruta("assets/cover.webp"),
           caption="<p>Un golpe ratonil que salió como el culo. Thriller criminal para Mausritter.</p>",
           description="<p>Seis ratones trajeados, cuatro cajas de diamantes y un poli infiltrado. Incluye la guía del DJ, los dosieres secretos, las ayudas de juego, escenas, música y herramientas de mesa.</p>",
           actors=actors, combats=[], items=items, journal=diarios, scenes=escenas, tables=tablas, macros=macros, cards=[], playlists=playlists, folders=folders,
           folder=None, sort=0, flags={ID: dict(version=VERSION)})
(R / "_data").mkdir(exist_ok=True)
json.dump([adv], open(R / "_data" / "aventura.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)

# ------------------------------------------------------------------ paquete de MR- Dirección
def fl(slug):
    return {"flag": [ID, "slug", slug]}


dir_escenas = []
for e, s in zip(ESC, escenas):
    orden, slug, nombre, musica, cap, reparto = e
    dir_escenas.append(dict(ref=fl(slug), order=orden, name=nombre, reading={"uuid": f"JournalEntry.{diarios[0]['_id']}.JournalEntryPage.{PAG_CAP[cap]}"},
                            music=fl(f"music-{musica}"), motifs=None, cues=[], ambient=fl("ambient-zumbido" if orden in (1, 4, 5, 6, 7, 10) else "ambient-muelle"),
                            figures=[dict(ref=fl(a), label="") for a in reparto], handouts=[], notes="", thumb=s["thumb"] or "",
                            stage=dict(eye=0.5, anchors=[[0.2, 0.9], [0.35, 0.92], [0.5, 0.93], [0.65, 0.92], [0.8, 0.9]])))
direccion = dict(schema=1, id=ID, title="MR- Reservoir Mice", version=VERSION, author="Manu Romera", license="CC BY-NC-SA 4.0",
                 settings=dict(fade=3, motifs=[dict(id=i, label=l, icon=ic, music=fl(f"moods-{i}")) for i, l, ic in MOTIVOS],
                               effects=[dict(id=i, label=l, icon=ic, sound=fl(f"sfx-{i}")) for i, l, ic in EFECTOS],
                               markers=dict(milestones=[dict(id="rastreador", label="El rastreador de la Caja 4"), dict(id="maletero", label="El guardia del maletero"),
                                                        dict(id="gris", label="El Sr. Gris desaparece"), dict(id="pintada", label="La pintada"),
                                                        dict(id="contrasena", label="La contraseña del barquero"), dict(id="topo", label="Plata, descubierto", public=False)],
                                            clocks=[])),
                 scenes=dir_escenas)
(R / "content").mkdir(exist_ok=True)
json.dump(direccion, open(R / "content" / "direccion-es.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)

# ------------------------------------------------------------------ pizarra de MR- Pizarra
P = []
cx = [420, 820, 1220, 1620, 2020, 2420]
for k, p in enumerate(D.PJ):
    P.append(dict(ref=p["slug"], type="entity", name=p["n"], kind="Actor", frame="polaroid", showToAll=True, layer="banda", x=cx[k], y=260, w=220, rot=[-4, 3, -2, 4, -3, 2][k]))
P += [dict(ref="caso", type="clipping", layer="banda", title="EL GOLPE DE LA JOYERÍA", text="Cuatro cajas. Tres coches. Seis colores. La Guardia llegó demasiado pronto. ¿Quién avisó?", paper="periodico-2", x=1300, y=760, w=360, rot=-2),
      dict(ref="sello-topo", type="stamp", layer="banda", kind="marco-rect-rojo", text="HAY UN TOPO", x=1350, y=1230, w=230, rot=-6),
      dict(ref="rastreador", type="entity", name="Microrrastreador", kind="Item", frame="diapositiva", layer="botin", x=300, y=820, w=210, rot=3),
      dict(ref="llamada", type="note", layer="banda", text="Rojo oyó a Púrpura hablar con una chica sobre «sus planes».", color="amarillo", x=1620, y=620, w=190, rot=4),
      dict(ref="huida", type="note", layer="banda", text="Beige huyó en un golpe anterior con Verde.", color="rosa", x=2050, y=620, w=190, rot=-3),
      dict(ref="agente", type="entity", name="El agente del maletero", kind="Actor", frame="foto-instantanea-80", layer="maletero", x=2400, y=900, w=220, rot=-3),
      dict(ref="cunado", type="note", layer="maletero", text="Mira a Verde como si lo conociera.", color="rosa", x=2050, y=1000, w=190, rot=2),
      dict(ref="gris", type="entity", name="Sr. Gris", kind="Actor", frame="foto-sepia-esquinas", layer="gris", x=650, y=1300, w=220, rot=2),
      dict(ref="libreta", type="clipping", layer="gris", title="Libreta del Sr. Gris", text=" · ".join(f"{h} {t}" for h, t in D.LIBRETA[2:4]), paper="libreta-rayas", x=980, y=1450, w=320, rot=-3),
      dict(ref="pintada", type="clipping", layer="gris", title="EN EL ESPEJO", text=" ".join(D.PINTADA), paper="papel-viejo-2", x=1650, y=1450, w=320, rot=3),
      dict(ref="bridas", type="note", layer="verdad", text="Bridas reglamentarias en el bolsillo de Plata.", color="azul", x=2700, y=520, w=190, rot=-4),
      dict(ref="verdad", type="stamp", layer="verdad", kind="marco-circular-rojo", text="INFILTRADO", x=2650, y=300, w=230, rot=8)]


def hilo(a, b, color, estilo, etiqueta=""):
    return {"from": a, "to": b, "color": color, "style": estilo, "label": etiqueta}


L = [hilo("rojo", "llamada", "ambar", "punteado", "lo oyó"), hilo("llamada", "purpura", "ambar", "punteado", "¿cabo suelto?"),
     hilo("verde", "huida", "negro", "solido", "rencor"), hilo("huida", "beige", "ambar", "discontinuo", "¿cobarde?"),
     hilo("agente", "cunado", "violeta", "solido"), hilo("cunado", "verde", "violeta", "punteado", "¿familia?"),
     hilo("rastreador", "caso", "rojo", "solido", "la Guardia sabe dónde"), hilo("gris", "libreta", "rojo", "solido", "se la dio a alguien"),
     hilo("libreta", "sello-topo", "rojo", "solido", "uno de los seis"), hilo("pintada", "sello-topo", "rojo", "solido"),
     hilo("bridas", "plata", "rojo", "solido", "es él"), hilo("agente", "plata", "violeta", "solido", "compañeros"), hilo("verdad", "plata", "rojo", "solido")]
pizarra = {"format": "mr-pizarra-import", "version": 1, "mode": "board", "title": "Reservoir Mice · Pizarra de sospechas", "background": "corcho-claro",
           "pinPreset": {"pin": "auto", "color": "", "layout": "auto"},
           "layers": [{"ref": "banda", "name": "La banda", "revealed": True}, {"ref": "botin", "name": "El botín", "revealed": False},
                      {"ref": "maletero", "name": "El maletero", "revealed": False}, {"ref": "gris", "name": "El Sr. Gris", "revealed": False},
                      {"ref": "verdad", "name": "La verdad", "revealed": False}],
           "items": P, "links": L}
json.dump(pizarra, open(R / "content" / "pizarra-es.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)

faltan = sorted({p for p in (x.rstrip("\\") for x in json.dumps(adv).split('"')) if p.startswith(f"modules/{ID}/assets/") and not p.endswith(".ogg") and not existe(p[len(f'modules/{ID}/'):])})
print(f"{len(actors)} actores · {len(items)} objetos · {len(diarios)} diarios · {len(escenas)} escenas · {len(tablas)} tablas · {len(macros)} macros · {sum(len(p['sounds']) for p in playlists)} sonidos")
print("imágenes que faltan:", len(faltan), *faltan[:60], sep="\n  ")
