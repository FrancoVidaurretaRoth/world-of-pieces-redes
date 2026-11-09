"""Hoja de cuadros de un video, para revisarlo antes de que entre a la cola (09/11/2026).

    python herramientas/hoja.py videos/<id>.mp4 [--cuadros 12] [--columnas 4] [--salida hojas/<id>.png]

Arma una grilla con cuadros parejos del video (con su segundo arriba a la izquierda) y avisa si hay tramos congelados
(cuadros seguidos idénticos: el juego trabado o una animación quieta). Qué mirar en la hoja: bugs del juego, que la
toma esté enfocada en lo que muestra, nada en T ni congelado, nada flotando ni atravesando paredes, nada raro.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageStat

sys.path.insert(0, str(Path(__file__).parent))
from clip import _ffmpeg  # noqa: E402


def _duracion(video: Path) -> float:
    r = subprocess.run([_ffmpeg(), "-i", str(video)], capture_output=True, text=True, errors="replace")
    for linea in r.stderr.splitlines():
        if "Duration:" in linea:
            h, m, s = linea.split("Duration:")[1].split(",")[0].strip().split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0


def _congelados(video: Path, tmp: Path) -> list[tuple[float, float]]:
    """Tramos de >= 0,5 s sin cambios (a 10 cuadros por segundo, en chico)."""
    subprocess.run([_ffmpeg(), "-v", "error", "-i", str(video), "-vf", "fps=10,scale=160:-1",
                    str(tmp / "m_%04d.png")], check=True)
    cuadros = sorted(tmp.glob("m_*.png"))
    tramos: list[tuple[float, float]] = []
    ini = -1
    prev = None
    for i, p in enumerate(cuadros):
        img = Image.open(p).convert("L")
        if prev is not None:
            dif = ImageStat.Stat(ImageChops.difference(img, prev)).mean[0]
            if dif < 0.15:
                if ini < 0:
                    ini = i - 1
            else:
                if ini >= 0 and i - ini >= 5:
                    tramos.append((ini / 10.0, i / 10.0))
                ini = -1
        prev = img
    if ini >= 0 and len(cuadros) - ini >= 5:
        tramos.append((ini / 10.0, len(cuadros) / 10.0))
    return tramos


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--cuadros", type=int, default=12)
    ap.add_argument("--columnas", type=int, default=4)
    ap.add_argument("--ancho", type=int, default=360)
    ap.add_argument("--salida", default="")
    a = ap.parse_args()
    video = Path(a.video)
    dur = _duracion(video)
    salida = Path(a.salida) if a.salida else Path("hojas") / (video.stem + ".png")
    salida.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        imgs: list[tuple[float, Image.Image]] = []
        for k in range(a.cuadros):
            seg = dur * (k + 0.5) / a.cuadros
            f = tmp / f"c_{k:02d}.png"
            subprocess.run([_ffmpeg(), "-v", "error", "-ss", f"{seg:.2f}", "-i", str(video), "-frames:v", "1",
                            "-vf", f"scale={a.ancho}:-1", str(f)], check=True)
            if f.exists():
                imgs.append((seg, Image.open(f).convert("RGB")))
        if not imgs:
            sys.exit("No salió ningún cuadro")
        w, h = imgs[0][1].size
        filas = (len(imgs) + a.columnas - 1) // a.columnas
        hoja = Image.new("RGB", (w * a.columnas, h * filas), (20, 20, 20))
        d = ImageDraw.Draw(hoja)
        for i, (seg, img) in enumerate(imgs):
            x, y = (i % a.columnas) * w, (i // a.columnas) * h
            hoja.paste(img, (x, y))
            d.rectangle([x, y, x + 52, y + 20], fill=(0, 0, 0))
            d.text((x + 4, y + 4), f"{seg:.1f}s", fill=(255, 220, 90))
        hoja.save(salida)
        tramos = _congelados(video, tmp)
    print(f"{salida}  ({dur:.1f} s)")
    for a0, a1 in tramos:
        print(f"  CONGELADO {a0:.1f}-{a1:.1f} s")


if __name__ == "__main__":
    main()
