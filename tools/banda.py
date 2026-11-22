#!/usr/bin/env python3
"""Banda sonora de Reservoir Mice a partir de grabaciones con licencia libre (ver NOTICE.md):
música de Kevin MacLeod (incompetech.com, CC BY 4.0) y efectos/ambientes de Freesound (CC0).
Idea: como en la película, la música es «la radio de los setenta». En el almacén suena por un transistor (filtro RADIO);
en los flashbacks y el clímax, limpia. Todo pasa por el mismo master de cinta y los efectos comparten la misma sala,
para que suene a una sola película. Bucles a compás sin hueco y loudnorm −26 LUFS.
Fuentes en «Trabajo RM/audio-fuentes» (macleod/*.mp3, freesound/*). Uso: python3 tools/banda.py [clave ...]"""
import subprocess, sys
from pathlib import Path
import numpy as np

R = Path(__file__).resolve().parent.parent
SRC = Path("/Volumes/Datos_Dock/FoundryVTT/Trabajo RM/audio-fuentes")
OUT = R / "assets" / "audio"
SR = 48000
CINTA = "highpass=f=45,lowpass=f=12500,acompressor=threshold=-20dB:ratio=2:attack=15:release=250"
SALA = "aecho=0.85:0.55:38|83:0.16|0.09"
RADIO = "highpass=f=260,lowpass=f=4300,acompressor=threshold=-26dB:ratio=4:attack=5:release=120,asoftclip=type=tanh,aecho=0.7:0.35:9:0.18"

# música: (pista de MacLeod, ¿por la radio del almacén?)
MUSICA = {
    "music/tema": ("Style Funk", False),             # los créditos: la banda camina hacia la cámara
    "music/espera": ("Late Night Radio", True),       # la radio del almacén, de fondo, mientras se espera
    "music/huida": ("Mistake the Getaway", False),    # Flashback 1: la huida en coche
    "music/botin": ("Covert Affair", False),          # las cajas del botín
    "music/desague": ("Fork and Spoon", True),        # el retrete y el maletero: la radio, alegre, mientras pasa lo peor
    "music/sardinas": ("Whiskey on the Mississippi", True),  # la máquina de discos de la cafetería
    "music/medianoche": ("Spy Groove", False),        # el clímax en el embarcadero
    "music/epilogo": ("Night on the Docks - Sax", False),
    "music/amanecer": ("DD Groove", False),
    "moods/tension": ("On the Ground", False), "moods/paranoia": ("Dances and Dames", False),
    "moods/persecucion": ("Pulse", False), "moods/standoff": ("Western Streets", False),
    "moods/calma": ("Clean Soul", True), "moods/misterio": ("Bass Walker", False),
    "moods/oscuridad": ("Long Note Two", False), "moods/triunfo": ("Got Funk", False),
    "moods/derrota": ("Night on the Docks - Trumpet", False),
}
# ambientes: capas (archivo, ganancia dB, inicio, duración)
AMBIENTES = {
    "ambient/muelle": [("agua", 0, 0, 44), ("madera", -8, 30, 44)],
    "ambient/zumbido": [("fluorescente", 0, 0.5, 18)],
}
# efectos: capas (archivo, ganancia dB, inicio, duración, retardo)
EFECTOS = {
    "disparo": [("disparo", 0, 0, 0.9, 0)],
    "amartillar": [("amartillar", 0, 0.3, 1.8, 0)],
    "standoff": [("cerrojo", 20, 0, 0.6, 0), ("amartillar", 20, 0.3, 1.2, 0.45), ("cerrojo", 18, 0, 0.6, 1.2), ("gong", -16, 0, 3.0, 1.7)],   # las armas se grabaron a −38 dB
    "golpes-maletero": [("bajos", 0, 8, 3.6, 0)],
    "persiana": [("persiana", 0, 0.8, 3.1, 0)],
    "chispazo": [("chispazo", 0, 0.5, 1.9, 0)],
    "campanadas": [("campanadas", 0, 22.6, 42, 0)],
    "sirena": [("sirenas-guardia", 0, 0, 7, 0)],
    "sirenaLejos": [("sirenas-guardia", -6, 0, 7, 0)],
    "motor-lancha": [("motor", 0, 6, 9, 0)],
    "maullido": [("gato", 0, 0, 7.5, 0)],
    "radio": [("radio", 0, 0, 9, 0)],
    "rata": [("ratas", 0, 0, 4.4, 0)],
    "latido": [("latido", 0, 0, 6.2, 0)],
    "tictac": [("tictac", 0, 0, 6, 0)],
    "pintada": [("agitar", 0, 0.2, 1.6, 0), ("spray", 0, 0, 3.2, 1.5)],
}
# filtro propio de algunos efectos (antes del master)
FILTRO = {"sirenaLejos": "lowpass=f=1800,aecho=0.8:0.7:120|260:0.3|0.2", "radio": RADIO, "golpes-maletero": "lowpass=f=2500"}


def lee(ruta, ini=0.0, dur=None):
    cmd = ["ffmpeg", "-v", "error", "-ss", str(ini)] + (["-t", str(dur)] if dur else []) + ["-i", str(ruta), "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32).reshape(-1, 2).copy()


def fundidos(x, a=0.005, b=0.08):
    n, na, nb = len(x), int(a * SR), int(b * SR)
    x[:na] *= np.linspace(0, 1, na)[:, None]
    x[n - nb:] *= np.linspace(1, 0, nb)[:, None]
    return x


def bucle(x, xf=4.0):
    """Fundido circular de potencia constante: la cola se funde con el arranque y el archivo empieza donde acaba."""
    n = int(xf * SR)
    t = np.linspace(0, np.pi / 2, n)[:, None]
    cabeza, cola = x[:n], x[-n:]
    return np.concatenate([cola * np.cos(t) + cabeza * np.sin(t), x[n:-n]])


def corte_en_compas(x, n, intro=20):
    """Bucle x[s0:c] con s0 en los primeros `intro` s (para saltar una intro distinta) y c en los últimos ~45 s, elegidos
    para que x[c:] ≈ x[s0:] y el fundido circular no descuadre el ritmo: envolvente de energía a 10 ms y ajuste fino
    por correlación de la onda."""
    from numpy.lib.stride_tricks import sliding_window_view as ventanas
    h = SR // 100
    mono = x.mean(axis=1)
    L = len(mono) // h * h
    env = np.sqrt(np.add.reduceat(mono[:L] ** 2, np.arange(0, L, h)) / h)
    m = 2 * n // h
    norm = lambda W: (W - W.mean(axis=-1, keepdims=True)) / (W.std(axis=-1, keepdims=True) + 1e-9)
    c0 = max(m + intro * 100, len(env) - 4500)
    W = norm(ventanas(env[c0:], m))
    S = norm(ventanas(env[: intro * 100 + m], m)[::10])            # inicios cada 0,1 s
    R = S @ W.T / m
    R[0] += 0.05                                                     # a igualdad, mejor no saltarse nada
    a, b = np.unravel_index(np.argmax(R), R.shape)
    s0, c = a * 10 * h, (c0 + b) * h
    w = mono[s0:s0 + n // 2]
    lo, hi = max(0, c - h), min(len(mono) - n // 2, c + h)
    c = lo + int(np.argmax([float(np.dot(w, mono[k:k + n // 2])) for k in range(lo, hi)]))
    return s0, c, float(R[a, b])


def sin_cola(x, umbral=-50):
    e = np.abs(x).max(axis=1)
    sonido = np.where(e > 10 ** (umbral / 20))[0]
    return x[: sonido[-1] + 1] if len(sonido) else x


def escribe(x, destino, es_bucle, filtro):
    destino.parent.mkdir(parents=True, exist_ok=True)
    ln = "loudnorm=I=-26:TP=-2:LRA=11" if es_bucle else "loudnorm=I=-18:TP=-1.5"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                    "-af", f"{filtro},{ln}", "-ar", "48000", "-c:a", "libopus", "-b:a", "96k" if es_bucle else "80k", str(destino)],
                   input=x.astype(np.float32).tobytes(), check=True)
    print("hecho", destino.relative_to(R))


def musica(clave):
    pista, radio = MUSICA[clave]
    x = sin_cola(lee(SRC / "macleod" / f"{pista}.mp3"))
    x = x[: len(x) - int(3 * SR)]   # fuera los últimos 3 s (el final con ritardando)
    n = int(1.5 * SR)
    s0, c, r = corte_en_compas(x, n)
    t = np.linspace(0, np.pi / 2, n)[:, None]
    y = np.concatenate([x[c:c + n] * np.cos(t) + x[s0:s0 + n] * np.sin(t), x[s0 + n:c]])   # tras c sigue x[c:] ≈ x[s0:]
    print(f"  {clave}: bucle {s0 / SR:.1f}–{c / SR:.1f} s de {len(x) / SR:.1f} s (parecido {r:.2f})")
    escribe(y, OUT / f"{clave}.ogg", True, f"{RADIO},{CINTA}" if radio else CINTA)


def fuente(nombre):
    return next((SRC / "freesound").glob(f"{nombre}.*"))


def mezcla(capas, con_retardo):
    pistas = []
    for c in capas:
        nombre, db, ini, dur = c[:4]
        x = fundidos(lee(fuente(nombre), ini, dur)) * 10 ** (db / 20)
        if con_retardo and c[4]:
            x = np.concatenate([np.zeros((int(c[4] * SR), 2), np.float32), x])
        pistas.append(x)
    n = max(len(p) for p in pistas)
    return sum(np.pad(p, ((0, n - len(p)), (0, 0))) for p in pistas)


def construir(clave):
    if clave in MUSICA:
        return musica(clave)
    if clave in AMBIENTES:
        return escribe(bucle(mezcla(AMBIENTES[clave], False), 3.0), OUT / f"{clave}.ogg", True, CINTA)
    nombre = clave.split("/")[-1]
    x = np.concatenate([mezcla(EFECTOS[nombre], True), np.zeros((int(0.6 * SR), 2), np.float32)])   # sitio para la cola de sala
    filtro = f"{FILTRO[nombre]},{CINTA},{SALA}" if nombre in FILTRO else f"{CINTA},{SALA}"
    escribe(fundidos(x, 0.002, 0.3), OUT / "sfx" / f"{nombre}.ogg", False, filtro)


TODO = list(MUSICA) + list(AMBIENTES) + [f"sfx/{k}" for k in EFECTOS]
if __name__ == "__main__":
    for clave in sys.argv[1:] or TODO:
        construir(clave)
