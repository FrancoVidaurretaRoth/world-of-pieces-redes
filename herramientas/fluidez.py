"""¿El video va fluido? (09/11/2026) Mide, en la parte del juego (sin el cierre), cuántos cuadros salen repetidos o casi
iguales al anterior mientras la imagen se está moviendo: eso se ve como tirones (bajos FPS).

    python herramientas/fluidez.py videos/<id>.mp4 [más videos…]

Por cada video: el % de cuadros "trabados" y el salto más largo. Más de ~8 % trabados, o tramos de 3+ cuadros quietos en
medio del movimiento, se nota.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

sys.path.insert(0, str(Path(__file__).parent))
from clip import CIERRE, _ffmpeg  # noqa: E402
from hoja import _duracion  # noqa: E402


def medir(video: Path) -> tuple[float, int, list[float]]:
    dur = _duracion(video) - CIERRE
    with tempfile.TemporaryDirectory() as t:
        subprocess.run([_ffmpeg(), "-v", "error", "-t", f"{max(dur, 1):.2f}", "-i", str(video), "-vf", "scale=270:-1",
                        str(Path(t) / "f_%05d.png")], check=True)
        cuadros = sorted(Path(t).glob("f_*.png"))
        difs: list[float] = []
        prev = None
        for p in cuadros:
            img = Image.open(p).convert("L")
            if prev is not None:
                difs.append(ImageStat.Stat(ImageChops.difference(img, prev)).mean[0])
            prev = img
    if not difs:
        return 0.0, 0, difs
    # Trabado: casi igual al anterior, cuando alrededor (±3 cuadros) la imagen sí se mueve.
    trabados = 0
    racha = 0
    peor = 0
    for i, d in enumerate(difs):
        vecinos = difs[max(0, i - 3):i] + difs[i + 1:i + 4]
        mov = sorted(vecinos)[len(vecinos) // 2] if vecinos else 0.0
        if mov > 0.6 and d < mov * 0.25:
            trabados += 1
            racha += 1
            peor = max(peor, racha)
        else:
            racha = 0
    return 100.0 * trabados / len(difs), peor, difs


def main() -> None:
    for a in sys.argv[1:]:
        pct, peor, _ = medir(Path(a))
        marca = "  <-- TIRONES" if pct > 8 or peor >= 3 else ""
        print(f"{Path(a).name:28s} trabados {pct:5.1f} %  peor racha {peor}{marca}")


if __name__ == "__main__":
    main()
