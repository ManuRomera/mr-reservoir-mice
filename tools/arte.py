#!/usr/bin/env python3
"""Convierte el arte generado (Trabajo RM/raw/*.png y las 4 imágenes modelo de Trabajo RM/ref) en los archivos del módulo:
figuras de cuerpo entero, fichas redondas, retratos, escenas 16:9 con miniatura, plano, vehículos, iconos de objeto
(recortados de las hojas de 3×3) y ayudas de juego con su texto compuesto. Todo con la marca MR (regla de la casa).
Uso: python3 tools/arte.py [grupo ...]   grupos: personajes escenas iconos vehiculos ayudas ui   (sin nada: todos)"""
import random, shutil, sys, textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

R = Path(__file__).resolve().parent.parent
TR = Path("/Volumes/Datos_Dock/FoundryVTT/Trabajo RM")
RAW, REF, A = TR / "raw", TR / "ref", R / "assets"
FUENTES = A / "fonts"
sys.path.insert(0, "/Volumes/Datos_Dock/FoundryVTT/Trabajo LOGO/marca")
sys.path.insert(0, str(R / "texto"))
import marca  # noqa: E402
import datos as D  # noqa: E402

PAPEL, TINTA, AMARILLO = (241, 232, 210), (22, 20, 18), (242, 194, 27)


def guarda(im, ruta, q=86):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    im.save(ruta, "WEBP", quality=q, method=6)
    return ruta


def alfa_bbox(im, umbral=14):
    return im.getchannel("A").point(lambda v: 255 if v > umbral else 0).getbbox()


def recorta_alfa(im, margen=0.03):
    bb = alfa_bbox(im)
    if not bb:
        return im
    im = im.crop(bb)
    m = int(max(im.size) * margen)
    out = Image.new("RGBA", (im.width + 2 * m, im.height + 2 * m), (0, 0, 0, 0))
    out.paste(im, (m, m))
    return out


def encaja(im, w, h, fondo=(0, 0, 0, 0)):
    im = im.copy()
    im.thumbnail((w, h), Image.LANCZOS)
    out = Image.new("RGBA", (w, h), fondo)
    out.alpha_composite(im, ((w - im.width) // 2, (h - im.height) // 2))
    return out


def sin_fondo(im):
    """Codex a veces devuelve fondo opaco aunque se pida alfa: se quita por relleno desde las cuatro esquinas."""
    im = im.convert("RGBA")
    if im.getchannel("A").getextrema()[0] < 250:
        return im
    rgb = im.convert("RGB")
    w, h = rgb.size
    clave = (255, 0, 255)
    for p in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        ImageDraw.floodfill(rgb, p, clave, thresh=38)
    r, g, b = rgb.split()
    es_clave = Image.eval(r, lambda v: 255 if v == 255 else 0)
    es_clave = Image.composite(es_clave, Image.new("L", rgb.size, 0), Image.eval(g, lambda v: 255 if v == 0 else 0))
    es_clave = Image.composite(es_clave, Image.new("L", rgb.size, 0), Image.eval(b, lambda v: 255 if v == 255 else 0))
    mascara = ImageOps.invert(es_clave).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1))
    im.putalpha(mascara)
    print("  (fondo opaco quitado)")
    return im


# ------------------------------------------------------------------ personajes
def figura(im, lado=1024, visible=0.97, pie=0.01):
    """Cuerpo entero en un lienzo cuadrado, pies abajo (MR- Dirección mide el alfa real de cada figura)."""
    im = recorta_alfa(im, 0)
    alto = round(lado * visible)
    ancho = round(im.width * alto / im.height)
    if ancho > lado:
        ancho, alto = lado, round(im.height * lado / im.width)
    im = im.resize((ancho, alto), Image.LANCZOS)
    out = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    out.alpha_composite(im, ((lado - ancho) // 2, round(lado * (1 - pie)) - alto))
    return out


def redondo(im, lado=400):
    """Ficha redonda opcional: cabeza y hombros de la figura sobre papel crema, con aro de tinta y cuña amarilla."""
    im = recorta_alfa(im, 0)
    cab = im.crop((0, 0, im.width, min(im.height, int(im.width * 0.95))))
    cab = encaja(cab, lado - 40, lado - 40)
    base = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)
    d.ellipse((4, 4, lado - 5, lado - 5), fill=PAPEL + (255,))
    d.pieslice((4, 4, lado - 5, lado - 5), 200, 340, fill=AMARILLO + (255,))
    mask = Image.new("L", (lado, lado), 0)
    ImageDraw.Draw(mask).ellipse((14, 14, lado - 15, lado - 15), fill=255)
    capa = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    capa.alpha_composite(cab, (20, 24))
    base.paste(capa, (0, 0), Image.composite(capa.getchannel("A"), Image.new("L", (lado, lado), 0), mask))
    ImageDraw.Draw(base).ellipse((6, 6, lado - 7, lado - 7), outline=TINTA + (255,), width=10)
    return marca.discreta(base, 300, 330, 18)


def retrato_compuesto(fig, w=1024, h=1365):
    """PNJ genéricos sin retrato propio: su figura sobre papel crema con el panel amarillo de la serie."""
    out = Image.new("RGBA", (w, h), PAPEL + (255,))
    ImageDraw.Draw(out).polygon([(w * .14, h * .1), (w * .9, h * .07), (w * .93, h * .86), (w * .1, h * .9)], fill=AMARILLO + (255,))
    f = recorta_alfa(fig, 0)
    f = f.crop((0, 0, f.width, min(f.height, int(f.width * 1.35))))
    f = encaja(f, int(w * .92), int(h * .95))
    out.alpha_composite(f, ((w - f.width) // 2, h - f.height))
    return out


def personajes():
    for s in [p["slug"] for p in D.TODOS] + [n["slug"] for n in D.PNJ]:
        src = RAW / f"fig-{s}.png"
        if not src.exists():
            print("  falta", src.name); continue
        fig = sin_fondo(Image.open(src))
        guarda(redondo(fig), A / "actors" / "tokens" / f"{s}.webp")
        guarda(marca.hombro(figura(fig)), A / "actors" / "figures" / f"{s}.webp", 88)
        por = RAW / f"por-{s}.png"
        if s == "limpiador":
            p = Image.open(REF / "roberto.png").convert("RGBA")
        elif por.exists():
            p = Image.open(por).convert("RGBA")
        else:
            p = retrato_compuesto(fig)
        p = ImageOps.fit(p, (768, 1024), Image.LANCZOS, centering=(0.5, 0.3))
        guarda(marca.esquina(p), A / "actors" / "portraits" / f"{s}.webp")
        print("hecho", s)


# ------------------------------------------------------------------ escenas
ESCENAS = ["muelle", "nave", "callejon", "furgoneta", "retrete", "cocina", "pasarela", "cafeteria", "maletero", "apagon", "palacio", "amanecer", "comisaria"]


def escenas():
    for s in ESCENAS + ["lancha"]:
        src = REF / "lancha.png" if s == "lancha" else RAW / f"esc-{s}.png"
        if not src.exists():
            print("  falta", src.name); continue
        im = ImageOps.fit(Image.open(src).convert("RGB"), (1920, 1080), Image.LANCZOS)
        guarda(marca.esquina(im), A / "scenes" / f"{s}.webp", 85)
        guarda(im.resize((400, 225), Image.LANCZOS), A / "scenes" / "thumbs" / f"{s}.webp", 80)
        print("hecho", s)
    m = RAW / "mapa-almacen.png"
    if m.exists():
        im = ImageOps.fit(Image.open(m).convert("RGB"), (2304, 1536), Image.LANCZOS)
        guarda(marca.esquina(im), A / "scenes" / "mapa-almacen.webp", 88)
        guarda(im.resize((400, 267), Image.LANCZOS), A / "scenes" / "thumbs" / "mapa-almacen.webp", 80)
        print("hecho mapa")
    guarda(marca.esquina(Image.open(REF / "cover.png").convert("RGB")), A / "cover.webp", 88)


# ------------------------------------------------------------------ iconos (hojas de 3×3)
def celdas(hoja):
    im = sin_fondo(Image.open(hoja))
    w, h = im.size
    out = []
    for f in range(3):
        for c in range(3):
            cel = im.crop((c * w // 3, f * h // 3, (c + 1) * w // 3, (f + 1) * h // 3))
            # restos del icono vecino pegados al borde de la celda: fuera
            a = cel.getchannel("A"); b = int(cel.width * .035)
            m = Image.new("L", cel.size, 0); ImageDraw.Draw(m).rectangle((b, b, cel.width - b - 1, cel.height - b - 1), fill=255)
            cel.putalpha(Image.composite(a, m, m))
            out.append(encaja(recorta_alfa(cel, .06), 256, 256))
    return out


def iconos():
    hojas = {}
    for slug, o in {**D.OBJ, **D.COND}.items():
        if not o.get("ic"):
            continue
        h, n = o["ic"]
        if h not in hojas:
            src = RAW / f"hoja-{h}.png"
            hojas[h] = celdas(src) if src.exists() else None
            if not hojas[h]:
                print("  falta", src.name)
        if hojas[h]:
            ic = hojas[h][n - 1]
            if slug.endswith("-izq"):  # la pareja del gemelo, en espejo
                ic = ImageOps.mirror(ic)
            guarda(marca.discreta(ic, 200, 226, 22), A / "items" / f"{slug}.webp")
    print("iconos:", len(list((A / "items").glob("*.webp"))))


def vehiculos():
    for v in ("furgoneta", "coche1", "coche2"):
        src = RAW / f"veh-{v}.png"
        if src.exists():
            im = recorta_alfa(sin_fondo(Image.open(src)), .02)
            guarda(marca.discreta(encaja(im, 512, 768), 256, 600, 26), A / "vehicles" / f"{v}.webp")
            print("hecho", v)


# ------------------------------------------------------------------ ayudas de juego
def fuente(nombre, tam):
    return ImageFont.truetype(str(FUENTES / nombre), tam)


def pintada():
    """El espejo del retrete (imagen modelo) con la frase escrita a dedo con grasa de motor."""
    bg = Image.open(REF / "pintada.png").convert("RGB").resize((1536, 1024), Image.LANCZOS)
    capa = Image.new("L", bg.size, 0)
    d = ImageDraw.Draw(capa)
    f = fuente("Anton-Regular.ttf", 92)
    rnd = random.Random(7)
    y = 205
    for i, linea in enumerate(D.PINTADA):
        ancho = d.textlength(linea, font=f)
        x = (bg.width - ancho) / 2 + (i - 1) * 14
        d.text((x, y), linea, font=f, fill=255)
        for _ in range(int(ancho / 55)):   # chorretones de grasa
            gx = x + rnd.random() * ancho
            d.line((gx, y + 100, gx + rnd.randint(-2, 2), y + 100 + rnd.randint(18, 90)), fill=210, width=rnd.randint(3, 7))
        y += 140
    capa = capa.filter(ImageFilter.GaussianBlur(1.6)).point(lambda v: 255 if v > 90 else int(v * 2.2))
    grano = Image.effect_noise(bg.size, 70).point(lambda v: 255 if v > 95 else 140)
    capa = Image.composite(capa, Image.new("L", bg.size, 0), grano)
    out = Image.composite(Image.new("RGB", bg.size, (18, 14, 12)), bg, capa)
    guarda(marca.esquina(out), A / "handouts" / "pintada.webp", 88)


def libreta(cajas=((335, 190, 735, 880), (805, 190, 1090, 880))):
    """Las páginas claras de bg-libreta se midieron en el PNG (izq. 308-756, dcha. 778-1130; la goma negra a partir de 1130)."""
    src = RAW / "bg-libreta.png"
    if not src.exists():
        print("  falta bg-libreta"); return
    bg = ImageOps.fit(Image.open(src).convert("RGB"), (1536, 1024), Image.LANCZOS)
    d = ImageDraw.Draw(bg)
    f, fb = fuente("Caveat-Regular.ttf", 34), fuente("Caveat-Bold.ttf", 38)
    entradas = [[("b", h)] + [("n", t)] for h, t in D.LIBRETA] + [[("b", D.FIRMA_LIBRETA)]]
    caja, y = 0, cajas[0][1]
    def parte(ent, ancho):
        out = []
        for tipo, txt in ent:
            fu, linea = (fb if tipo == "b" else f), ""
            for w in txt.split():
                prueba = (linea + " " + w).strip()
                if d.textlength(prueba, font=fu) > ancho and linea:
                    out.append((tipo, linea)); linea = w
                else:
                    linea = prueba
            out.append((tipo, linea))
        return out
    for ent in entradas:
        x0, y0, x1, y1 = cajas[caja]
        lineas = parte(ent, x1 - x0)
        if y + 38 * len(lineas) > y1 and caja + 1 < len(cajas):
            caja += 1; x0, y0, x1, y1 = cajas[caja]; y = y0
            lineas = parte(ent, x1 - x0)
        for tipo, l in lineas:
            d.text((x0, y), l, font=fb if tipo == "b" else f, fill=(120, 24, 18) if tipo == "b" else (36, 30, 66))
            y += 38
        y += 16
    if y > cajas[-1][3]:
        print("  AVISO: la libreta se sale de la página")
    guarda(marca.esquina(bg), A / "handouts" / "libreta-gris.webp", 88)


def carnes(foto=(228, 322, 595, 757), texto_x=700, renglones=(309, 394, 470, 550, 638)):
    """Marco de foto y renglones medidos en el PNG de bg-carne."""
    src = RAW / "bg-carne.png"
    if not src.exists():
        print("  falta bg-carne"); return
    f1, f2 = fuente("SpecialElite-Regular.ttf", 44), fuente("SpecialElite-Regular.ttf", 34)
    x0, y0, x1, y1 = foto
    for k, p in enumerate(D.TODOS):
        bg = Image.open(src).convert("RGB").resize((1536, 1024), Image.LANCZOS)
        por = A / "actors" / "portraits" / f"{p['slug']}.webp"
        if por.exists():
            ft = ImageOps.grayscale(ImageOps.fit(Image.open(por).convert("RGB"), (x1 - x0, y1 - y0), Image.LANCZOS, centering=(0.5, 0.2)))
            bg.paste(ImageOps.colorize(ft, (40, 34, 30), (236, 226, 204)), (x0, y0))
        d = ImageDraw.Draw(bg)
        filas = [("ROBERTO MELÉNDEZ", f1, TINTA), (f"«{p['apodo']}»", f2, TINTA), (p["edad"].upper(), f2, TINTA),
                 (f"Nº {417300 + 37 * k:06d}", f2, (110, 30, 20))]
        for (txt, fu, col), r in zip(filas, renglones):
            d.text((texto_x, r - 6), txt, font=fu, fill=col, anchor="ls")
        guarda(marca.esquina(bg), A / "handouts" / f"carne-{p['slug']}.webp", 86)


def ayudas():
    pintada(); libreta(); carnes()
    print("ayudas hechas")


def ui():
    """«Sin sitio»: el objeto que tapa las cuatro casillas de mochila que no existen en la regla del golpe."""
    lado = 512
    base = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    ImageDraw.Draw(base).rectangle((8, 8, lado - 9, lado - 9), fill=(40, 36, 32, 255), outline=TINTA + (255,), width=12)
    rayas = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    d = ImageDraw.Draw(rayas)
    for k in range(-lado, lado, 46):
        d.line((k, lado, k + lado, 0), fill=AMARILLO + (200,), width=14)
    m = Image.new("L", (lado, lado), 0)
    ImageDraw.Draw(m).rectangle((22, 22, lado - 23, lado - 23), fill=255)
    base.paste(rayas, (0, 0), Image.composite(rayas.getchannel("A"), Image.new("L", (lado, lado), 0), m))
    guarda(base, A / "ui" / "sin-sitio.webp")
    (A / "brand").mkdir(parents=True, exist_ok=True)
    shutil.copy("/Volumes/Datos_Dock/FoundryVTT/Trabajo LOGO/marca/mr-marca.webm", A / "brand" / "mr-marca.webm")


GRUPOS = dict(personajes=personajes, escenas=escenas, iconos=iconos, vehiculos=vehiculos, ayudas=ayudas, ui=ui)
if __name__ == "__main__":
    for g in sys.argv[1:] or GRUPOS:
        print("==", g)
        GRUPOS[g]()
