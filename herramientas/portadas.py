"""Las portadas de los posts de la cola que todavía no tienen imagen (10/11/2026): un cuadro de su video, pasado el
título (a mitad de camino de la toma). Las capturas elegidas a mano (`imagen_propia`) no se tocan.

    python herramientas/portadas.py [--todas]     (--todas: también rehace las sacadas antes de un video)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from clip import CIERRE, _ffmpeg  # noqa: E402
from hoja import _duracion  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
COLA = RAIZ / "cola" / "cola.json"


def main() -> None:
    todas = "--todas" in sys.argv
    cola = json.loads(COLA.read_text(encoding="utf-8"))
    hechas = 0
    for e in cola["entradas"]:
        if e.get("publicado") or not e.get("video") or e.get("imagen_propia"):
            continue
        if e.get("imagen") and not todas:
            continue
        video = RAIZ / e["video"]
        if not video.exists():
            continue
        toma = max(1.0, _duracion(video) - CIERRE)
        seg = max(3.6, toma * 0.55)   # (después del título, que se va a los ~3 s)
        destino = RAIZ / "imagenes" / "fuente" / f"{e['id']}.jpg"
        destino.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([_ffmpeg(), "-v", "error", "-y", "-ss", f"{seg:.2f}", "-i", str(video), "-frames:v", "1",
                        "-q:v", "2", str(destino)], check=True)
        e["imagen"] = f"imagenes/fuente/{e['id']}.jpg"
        hechas += 1
        print(f"{e['id']}: portada del segundo {seg:.1f}")
    COLA.write_text(json.dumps(cola, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{hechas} portadas")


if __name__ == "__main__":
    main()
