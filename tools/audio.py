#!/usr/bin/env python3
"""Banda sonora sintética de Reservoir Mice: funk y cine negro de los setenta (bajo, batería, piano eléctrico, guitarra wah,
órgano, cuerdas y metales), ambientes del muelle y efectos. Bucles sin costura (la cola se suma al principio), −26 LUFS, Ogg Opus.
Es música de sustitución: cualquier pista se puede reemplazar por otra con el mismo nombre.
Uso: python3 tools/audio.py [clave ...]   (claves: music/tema, moods/paranoia, sfx/disparo…; sin nada, todo)"""
import subprocess, sys, tempfile, wave
from pathlib import Path
import numpy as np

R = Path(__file__).resolve().parent.parent
OUT = R / "assets" / "audio"
SR = 44100
rng = np.random.default_rng(1)
ESC = {"men": [0, 2, 3, 5, 7, 8, 10], "dor": [0, 2, 3, 5, 7, 9, 10], "blu": [0, 3, 5, 6, 7, 10], "fri": [0, 1, 3, 5, 7, 8, 10], "may": [0, 2, 4, 5, 7, 9, 11]}


def hz(m): return 440.0 * 2 ** ((m - 69) / 12)
def tt(d): return np.arange(int(d * SR)) / SR


def env(n, a=0.005, r=0.05, dec=None):
    e = np.ones(n)
    na, nr = max(1, int(a * SR)), max(1, int(r * SR))
    e[:min(na, n)] = np.linspace(0, 1, min(na, n))
    if dec:
        e *= np.exp(-np.arange(n) / SR / dec)
    e[max(0, n - nr):] *= np.linspace(1, 0, min(nr, n))
    return e


def lp(x, fc):
    """Paso bajo de un polo por FFT cuando el corte es fijo; por muestras cuando varía (wah)."""
    if np.ndim(fc) == 0:
        X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
        return np.fft.irfft(X / (1 + 1j * f / fc), len(x))
    a = np.exp(-2 * np.pi * fc / SR)
    y = np.empty_like(x); s = 0.0
    for i in range(len(x)):
        s = (1 - a[i]) * x[i] + a[i] * s; y[i] = s
    return y


def saw(f, t): return 2 * ((f * t) % 1) - 1


# ---- instrumentos
def kick(d=0.4):
    t = tt(d); f = 45 + 90 * np.exp(-t * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)


def snare(d=0.25):
    t = tt(d); n = rng.standard_normal(len(t))
    return (0.7 * n * np.exp(-t * 22) + 0.4 * np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30)) * 0.8


def hat(d=0.06, abierto=False):
    t = tt(0.3 if abierto else d); n = rng.standard_normal(len(t))
    n = n - lp(n, 6000)
    return n * np.exp(-t * (9 if abierto else 60)) * 0.35


def bajo(m, d):
    t = tt(d); f = hz(m)
    return lp(saw(f, t) * 0.6 + np.sin(2 * np.pi * f * t), 900) * env(len(t), 0.004, 0.04, 0.5) * 0.9


def epiano(m, d):
    t = tt(d); f = hz(m)
    x = np.sin(2 * np.pi * f * t + 1.2 * np.sin(2 * np.pi * f * t) * np.exp(-t * 6)) + 0.25 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 3)
    return x * env(len(t), 0.003, 0.15, 1.6) * (1 + 0.15 * np.sin(2 * np.pi * 5 * t)) * 0.35


def wah(m, d, vel=4.0):
    t = tt(d); f = hz(m)
    fc = 500 + 1800 * (0.5 + 0.5 * np.sin(2 * np.pi * vel * t - np.pi / 2))
    return lp(lp(saw(f, t), fc), fc) * env(len(t), 0.002, 0.03, 0.25) * 0.5


def organo(m, d):
    t = tt(d); f = hz(m)
    x = sum(a * np.sin(2 * np.pi * f * k * t) for k, a in ((0.5, .5), (1, 1), (2, .5), (3, .3), (4, .2)))
    return x * env(len(t), 0.02, 0.2) * (1 + 0.2 * np.sin(2 * np.pi * 6 * t)) * 0.12


def cuerdas(m, d):
    t = tt(d); f = hz(m)
    return lp(sum(saw(f * (1 + dt), t) for dt in (-0.004, 0, 0.005)), 1600) * env(len(t), 0.5, 0.6) * 0.08


def metal(m, d):
    t = tt(d); f = hz(m)
    x = saw(f, t) + 0.5 * saw(f * 1.003, t)
    fc = 300 + 3500 * np.exp(-t * 8)
    return lp(x, fc) * env(len(t), 0.01, 0.08) * 0.25


def vibra(m, d):
    t = tt(d); f = hz(m)
    x = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 4 * f * t) * np.exp(-t * 8)
    return x * env(len(t), 0.002, 0.2, 1.2) * (1 + 0.35 * np.sin(2 * np.pi * 5.5 * t)) * 0.3


def poner(pista, x, s, g=1.0):
    i = int(s * SR)
    if i >= len(pista):
        return
    n = min(len(x), len(pista) - i)
    pista[i:i + n] += x[:n] * g


# ---- compositor: patrones de funk/noir sobre una progresión de grados
def tema(cfg):
    bpm, compases = cfg["bpm"], cfg.get("compases", 16)
    neg = 60 / bpm; comp = 4 * neg; dur = compases * comp
    pista = np.zeros(int((dur + 5) * SR))
    raiz, esc, prog = cfg["raiz"], ESC[cfg.get("escala", "men")], cfg["prog"]
    g = lambda grado, octv=0: raiz + esc[grado % len(esc)] + 12 * (grado // len(esc) + octv)
    swing = cfg.get("swing", 0.0)
    for c in range(compases):
        t0, gr = c * comp, prog[c % len(prog)]
        if cfg.get("bateria", True):
            for b in range(4):
                if b == 0 or (cfg.get("bombo2") and b == 2):
                    poner(pista, kick(), t0 + b * neg, 0.9)
                if b in (1, 3):
                    poner(pista, snare(), t0 + b * neg, cfg.get("caja", 0.5))
                for s in range(2):
                    poner(pista, hat(abierto=(s == 1 and b == 3)), t0 + b * neg + s * neg / 2 + (swing * neg / 2 if s else 0), 0.6)
            if cfg.get("fantasma"):
                poner(pista, snare(0.08), t0 + 2.75 * neg, 0.15)
        elif cfg.get("pulso"):
            for b in range(4):
                poner(pista, kick(0.3), t0 + b * neg, 0.35)
        for (b, inter, d) in cfg.get("bajo", [(0, 0, .5), (1.5, 0, .25), (2, 4, .5), (3, 7, .25), (3.5, 6, .25)]):
            poner(pista, bajo(g(gr, -2) + inter - (12 if cfg.get("bajo_grave") else 0), d * neg), t0 + b * neg)
        inst = cfg.get("acorde", "epiano")
        fn = {"epiano": epiano, "organo": organo, "cuerdas": cuerdas, "vibra": vibra}[inst]
        for b in cfg.get("golpes", [0.5, 2.5]) if inst not in ("organo", "cuerdas") else [0]:
            for k in (0, 2, 4, 6):
                poner(pista, fn(g(gr + k), comp * 1.02 if inst in ("organo", "cuerdas") else neg * 1.5), t0 + b * neg)
        if cfg.get("wah"):
            for s in range(8):
                if (c * 8 + s) % 3 != 2:
                    poner(pista, wah(g(gr + (s % 3) * 2), neg / 2.2, cfg["wah"]), t0 + s * neg / 2, 0.5)
        if cfg.get("melodia") and c % 4 in (1, 3):
            voz = {"metal": metal, "vibra": vibra, "epiano": epiano}[cfg.get("voz", "metal")]
            for (b, gm, d) in cfg["melodia"]:
                poner(pista, voz(g(gr + gm, 1), d * neg), t0 + b * neg, 0.7)
        if cfg.get("pad"):
            for k in (0, 2, 4):
                poner(pista, cuerdas(g(gr + k), comp * 1.02), t0, 0.7)
    return pista, dur


def cerrar_bucle(pista, dur):
    n = int(dur * SR)
    out = pista[:n].copy()
    cola = pista[n:]
    out[:min(len(cola), n)] += cola[:n]
    return out


# ---- ambientes y efectos
def ruido(d): return rng.standard_normal(int(d * SR))


def muelle(d=60):
    out = lp(ruido(d), 400) * (0.6 + 0.4 * np.sin(2 * np.pi * tt(d) / 5.3) ** 2) * 3
    for _ in range(6):   # gaviotas lejanas
        tg = tt(0.6); f = 1400 + 600 * np.sin(np.pi * tg / 0.6) - 500 * tg
        poner(out, 0.08 * np.sin(2 * np.pi * np.cumsum(f) / SR) * env(len(tg), 0.05, 0.2), rng.uniform(0, d - 2))
    for _ in range(25):  # chapoteo contra los pilotes
        poner(out, lp(ruido(0.3), 1200) * env(int(0.3 * SR), 0.01, 0.2, 0.08) * 0.5, rng.uniform(0, d - 1))
    return out


def zumbido(d=40):
    t = tt(d)
    x = sum(a * np.sin(2 * np.pi * 50 * k * t) for k, a in ((1, .3), (2, .2), (3, .12), (5, .05))) * (0.8 + 0.2 * np.sin(2 * np.pi * 0.13 * t))
    for _ in range(30):
        poner(x, ruido(0.02) * 0.4, rng.uniform(0, d - 0.1))
    return x + lp(ruido(d), 300) * 0.4   # lluvia sobre la chapa


def sfx(nombre):
    if nombre == "disparo":
        t = tt(1.2); return lp(ruido(1.2) * np.exp(-t * 9) + kick(1.2) * 1.5, 3000)
    if nombre == "amartillar":
        x = np.zeros(int(0.5 * SR)); poner(x, hat(0.02) * 4, 0); poner(x, hat(0.03) * 5, 0.18); return x
    if nombre == "golpes-maletero":
        x = np.zeros(int(3 * SR))
        for s in (0, .45, .8, 1.6, 2.0):
            poner(x, lp(kick(0.35), 500) * 1.5 + lp(ruido(0.35), 800) * .3, s)
        return x
    if nombre == "persiana":
        t = tt(2.2); x = ruido(2.2) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 18 * t))) * env(len(t), 0.05, 0.5)
        return lp(x, 2500) - lp(x, 200)
    if nombre == "chispazo":
        x = np.zeros(int(0.8 * SR))
        for _ in range(8):
            poner(x, ruido(0.03) * rng.uniform(.4, 1), rng.uniform(0, 0.6))
        return x
    if nombre == "campanadas":
        x = np.zeros(int(15 * SR)); tb = tt(3)
        b = sum(a * np.sin(2 * np.pi * 220 * r * tb) * np.exp(-tb * dcy) for r, a, dcy in ((1, 1, 1), (2.4, .5, 2), (3, .3, 3), (4.2, .2, 4)))
        for k in range(12):
            poner(x, b * 0.4, k * 1.0)
        return x
    if nombre in ("sirena", "sirenaLejos"):
        t = tt(5); f = 650 + 250 * np.sin(2 * np.pi * 0.5 * t)
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(len(t), 0.5, 1)
        return lp(x, 900 if nombre == "sirenaLejos" else 3000) * (0.25 if nombre == "sirenaLejos" else 0.6)
    if nombre == "motor-lancha":
        t = tt(6); x = saw(38 + 4 * np.sin(2 * np.pi * 0.3 * t), t) * (0.6 + 0.4 * np.sin(2 * np.pi * 11 * t))
        return lp(x, 600) * env(len(t), 1.5, 2)
    if nombre == "maullido":
        t = tt(1.6); f = 380 + 260 * np.sin(np.pi * t / 1.6) ** 0.7
        x = sum(a * np.sin(2 * np.pi * np.cumsum(f * k) / SR) for k, a in ((1, 1), (2, .6), (3, .4), (4, .2)))
        return lp(x * env(len(t), 0.1, 0.4), 2500) * 0.6
    if nombre == "radio":
        t = tt(3); n = ruido(3)
        voz = saw(140 + 30 * np.sin(2 * np.pi * 3 * t), t) * (np.sin(2 * np.pi * 4 * t) > 0)
        return lp((n - lp(n, 600)) * 0.3 + 0.3 * (lp(voz, 1800) - lp(voz, 400)), 3500)
    if nombre == "rata":
        x = np.zeros(int(2 * SR))
        for k in range(5):
            tc = tt(0.12)
            poner(x, np.sin(2 * np.pi * (3000 + 800 * np.sin(40 * tc)) * tc) * env(len(tc), 0.005, 0.05) * .4, k * 0.3 + rng.uniform(0, .1))
            poner(x, lp(ruido(0.15), 3000) * .2, k * 0.33)
        return x
    if nombre == "latido":
        x = np.zeros(int(2.4 * SR))
        for s in (0, .28, 1.2, 1.48):
            poner(x, lp(kick(0.3), 200) * 1.5, s)
        return x
    if nombre == "tictac":
        x = np.zeros(int(4 * SR))
        for k in range(8):
            poner(x, hat(0.015) * (3 if k % 2 else 2), k * 0.5)
        return x
    if nombre == "pintada":
        t = tt(2.5); n = ruido(2.5)
        return (n - lp(n, 2000)) * (0.4 + 0.4 * np.sin(2 * np.pi * 2.5 * t) ** 2) * env(len(t), 0.05, 0.3) * .5
    if nombre == "standoff":
        x = np.zeros(int(5 * SR))
        for k in (0, 3, 7):
            poner(x, metal(45 + k, 4.5), 0, 0.8)
        poner(x, kick(1.5) * 1.5, 0); poner(x, snare(0.6), 0)
        return x
    raise KeyError(nombre)


MUSICA = {  # pistas de escena
 "tema": dict(bpm=96, raiz=50, escala="dor", prog=[0, 0, 3, 3, 0, 0, 4, 3], wah=4, melodia=[(0, 4, 1), (1.5, 6, .5), (2, 7, 1.5)], fantasma=True, swing=.15),
 "espera": dict(bpm=72, raiz=45, escala="men", prog=[0, 0, 5, 3], acorde="epiano", golpes=[0, 2.5], bateria=False, pulso=True, bajo=[(0, 0, 1), (2, 7, 1)], pad=True),
 "huida": dict(bpm=132, raiz=52, escala="blu", prog=[0, 0, 2, 3], wah=6, bombo2=True, caja=.7, melodia=[(0, 0, .5), (.5, 2, .5), (1, 3, .5), (1.5, 4, 1)]),
 "botin": dict(bpm=100, raiz=53, escala="dor", prog=[0, 3, 0, 4], acorde="organo", wah=3, swing=.1, melodia=[(0, 4, .5), (1, 2, .5), (2, 0, 1)], voz="vibra"),
 "desague": dict(bpm=64, raiz=44, escala="fri", prog=[0, 1, 0, 6], acorde="cuerdas", bateria=False, bajo=[(0, 0, 2)], melodia=[(0, 1, 2), (2, 0, 2)], voz="vibra"),
 "sardinas": dict(bpm=88, raiz=55, escala="may", prog=[0, 5, 1, 4], acorde="epiano", golpes=[0, 1.5, 2.5], swing=.25, melodia=[(0, 4, 1), (1, 2, 1), (2, 0, 2)], voz="vibra"),
 "medianoche": dict(bpm=60, raiz=45, escala="fri", prog=[0, 0, 1, 0], acorde="cuerdas", bateria=False, pulso=True, bajo=[(0, 0, 4)], melodia=[(0, 4, 3)], voz="metal"),
 "epilogo": dict(bpm=92, raiz=51, escala="may", prog=[0, 3, 4, 3], acorde="organo", wah=3, swing=.2, melodia=[(0, 2, 1), (1, 4, 1), (2, 7, 2)]),
 "amanecer": dict(bpm=70, raiz=48, escala="men", prog=[0, 5, 3, 4], acorde="epiano", bateria=False, pad=True, bajo=[(0, 0, 2), (2, 4, 2)]),
}
MOTIVOS = {
 "tension": dict(bpm=80, raiz=45, escala="men", prog=[0, 0, 0, 1], acorde="cuerdas", bateria=False, pulso=True, bajo=[(0, 0, .5), (1, 0, .5), (2, 0, .5), (3, 0, .5)]),
 "paranoia": dict(bpm=84, raiz=46, escala="fri", prog=[0, 1, 0, 1], acorde="vibra", golpes=[0, 1.75, 3], bateria=False, pulso=True, bajo=[(0, 0, 1), (1.5, 1, .5)]),
 "persecucion": dict(bpm=144, raiz=52, escala="blu", prog=[0, 0, 3, 2], wah=7, bombo2=True, caja=.8, melodia=[(0, 0, .5), (.5, 3, .5), (1, 4, .5)]),
 "standoff": dict(bpm=58, raiz=45, escala="fri", prog=[0, 0, 1, 1], acorde="cuerdas", bateria=False, bajo=[(0, 0, 4)], melodia=[(0, 7, 4)], voz="metal"),
 "calma": dict(bpm=76, raiz=50, escala="dor", prog=[0, 3, 0, 4], acorde="epiano", swing=.2, caja=.25),
 "misterio": dict(bpm=66, raiz=47, escala="men", prog=[0, 5, 0, 6], acorde="vibra", bateria=False, bajo=[(0, 0, 1), (2, 4, 1)], pad=True),
 "oscuridad": dict(bpm=56, raiz=40, escala="fri", prog=[0, 1], acorde="cuerdas", bateria=False, bajo=[(0, 0, 4)], bajo_grave=True),
 "triunfo": dict(bpm=104, raiz=53, escala="may", prog=[0, 3, 4, 0], acorde="organo", wah=4, melodia=[(0, 4, .5), (.5, 5, .5), (1, 7, 2)]),
 "derrota": dict(bpm=62, raiz=45, escala="men", prog=[0, 5, 3, 4], acorde="cuerdas", bateria=False, bajo=[(0, 0, 4)], melodia=[(0, 4, 2), (2, 2, 2)], voz="vibra"),
}
EFECTOS = ["disparo", "amartillar", "golpes-maletero", "persiana", "chispazo", "campanadas", "sirena", "sirenaLejos", "motor-lancha", "maullido", "radio", "rata",
           "latido", "tictac", "pintada", "standoff"]


def escribe(x, destino, bucle):
    destino.parent.mkdir(parents=True, exist_ok=True)
    x = x / (np.max(np.abs(x)) + 1e-9) * 0.9
    with tempfile.NamedTemporaryFile(suffix=".wav") as f:
        with wave.open(f.name, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes((x * 32767).astype(np.int16).tobytes())
        filtro = "loudnorm=I=-26:TP=-2:LRA=11" if bucle else "loudnorm=I=-20:TP=-1.5"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f.name, "-af", filtro, "-ar", "48000", "-c:a", "libopus", "-b:a", "96k", str(destino)], check=True)


def construir(clave):
    carpeta, nombre = clave.split("/")
    if carpeta in ("music", "moods"):
        pista, dur = tema((MUSICA if carpeta == "music" else MOTIVOS)[nombre])
        x = cerrar_bucle(pista, dur)
        if dur < 45:   # bucles cortos: se repiten hasta ~1 min
            x = np.tile(x, int(np.ceil(60 / dur)))
        escribe(x, OUT / carpeta / f"{nombre}.ogg", True)
    elif carpeta == "ambient":
        d = 60 if nombre == "muelle" else 40
        escribe(cerrar_bucle({"muelle": muelle, "zumbido": zumbido}[nombre](d + 3), d), OUT / carpeta / f"{nombre}.ogg", True)
    else:
        escribe(sfx(nombre), OUT / "sfx" / f"{nombre}.ogg", False)
    print("hecho", clave, flush=True)


TODO = [f"music/{k}" for k in MUSICA] + [f"moods/{k}" for k in MOTIVOS] + ["ambient/muelle", "ambient/zumbido"] + [f"sfx/{k}" for k in EFECTOS]
if __name__ == "__main__":
    for c in sys.argv[1:] or TODO:
        construir(c)
