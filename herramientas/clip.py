"""Arma el video de un post (la segunda lámina del carrusel) con los cuadros que graba el juego.

El juego graba la toma cuadro por cuadro con la prueba `clips_redes` (repo del juego, `herramientas/pruebas/`), a
1080x1350 y 30 cuadros por segundo. Este script la junta en un MP4 listo para Instagram:

  - el título de la novedad arriba, que aparece y se va en los primeros segundos;
  - de fondo, un pedazo de "Brisa del Mundo" (la música del juego; el pedazo depende del post, así no suenan todos
    igual), con fundido al entrar y al salir;
  - al final, un cierre de 2 s con el emblema y la web, que entra con un fundido;
  - H.264 + AAC, a los fps de la toma (su fps.txt: 60 desde el 09/11/2026; las viejas, 30), faststart (lo que pide la API de Instagram para un video de carrusel).

Corre en la PC, no en GitHub: la música queda solo en el repo del juego (este repo es público). Usa el ffmpeg del
sistema o, si no hay, el de `pip install imageio-ffmpeg`.

  python herramientas/clip.py lote1-06 bestiario
  python herramientas/clip.py lote1-06 bestiario --cuadros D:/otra/carpeta --sin-cola
  python herramientas/clip.py lote1-26 ui_hud+ui_inventario+ui_mapa      (varias tomas seguidas, con corte)

Las tomas de la pantalla del juego (la interfaz, apaisadas) se acomodan solas al 4:5: el centro recortado y escalado
al ancho, con la misma imagen difuminada de fondo arriba y abajo.

Deja `videos/<id>.mp4` y anota el video en la entrada de la cola (`cola/cola.json`). Después: commit y push.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tarjeta  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
COLA = RAIZ / "cola" / "cola.json"
FPS = 30
CIERRE = 2.0          # segundos del cierre con el emblema
FUNDIDO = 0.5         # cruce entre la toma y el cierre
TITULO_HASTA = 3.2    # el título se va a los ~3 s
MUSICA = Path(os.environ.get("WOP_MUSICA", RAIZ.parent / "world-of-pieces-githud" / "sonidos" / "musica"
                             / "brisa_del_mundo.mp3"))
CUADROS = Path(os.environ.get("TEMP", tempfile.gettempdir())) / "wop_headless" / "capturas" / "clips"
# 🎵 (09/11/2026, pedido del usuario: que no suenen todos igual) Los temas del juego (`sonidos/musica/temas/`): cada post
# usa el de lo que muestra (la ciudad, el mar, el combate…) y, si nada encaja, uno de todos según el post.
TEMAS = MUSICA.parent / "temas"
TEMA_POR_PALABRA = [
    (r"ventoria|coliseo|palacio", "ventoria"),
    (r"n[aá]cara|bajo el mar|sumergid", "nacara"),
    (r"hondabrasa|volc[aá]n|ascuas|magma", "hondabrasa"),
    (r"umbrafuego|elfos? oscuro", "umbrafuego"),
    (r"nelulen", "nelulen"),
    (r"zahra|desierto|sahrim|especias|seda", "zahra"),
    (r"cirro|nubes|cielo", "puerto_cirro"),
    (r"tr[eé]bol|blink", "puerto_trebol"),
    (r"contrabando|piratas?|barbanegra", "puerto_escondido"),
    (r"forjahonda|yunque|albacumbre|conf[ií]n|nieve|helad", "forjahonda"),
    (r"dinosaurio|isla perdida|naufragio|raptor|pantano", "campamento_naufragio"),
    (r"faro|bruma|horizonte", "refugio_faro"),
    (r"\bmar\b|barco|velas|santa mar[ií]a|guerreros del mar|kraken", "mar"),
    (r"profundidades|mazmorra|\bcuevas?\b|\bminas?\b", "mazmorra"),
    (r"golpes|armas|combate|jefe|yeti|coloso|desaf[ií]o|puntinazo|raros|eventos", "jefe"),
    (r"pueblo del [aá]ngel|posada|primeros pasos|[aá]ngel", "pueblo_angel"),
]


def tema_para(ident: str, texto: str, largo: float) -> Path:
    """El tema de un post: el de lo que muestra (por palabras del título y el texto) o, si nada encaja, uno de todos
    elegido por el post (siempre el mismo para el mismo post). Que dure lo que el video; si no, otro."""
    import re
    todos = sorted(t for t in TEMAS.glob("*") if t.suffix in (".mp3", ".wav", ".ogg")) + [MUSICA]
    ffmpeg = _ffmpeg()
    alcanza = [t for t in todos if _duracion(ffmpeg, t) > largo + 1]
    # (primero el título, la primera línea: el texto nombra a veces otros lugares de paso)
    for t in [p.lower() for p in (texto or "").split("\n", 1)]:
        for patron, nombre in TEMA_POR_PALABRA:
            if re.search(patron, t):
                for c in alcanza:
                    if c.stem == nombre:
                        return c
    semilla = int(hashlib.sha1(ident.encode()).hexdigest()[:8], 16)
    return alcanza[semilla % len(alcanza)] if alcanza else MUSICA


def _ffmpeg() -> str:
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    try:
        import imageio_ffmpeg
    except ImportError:
        sys.exit("Falta ffmpeg: instalalo o corré  pip install imageio-ffmpeg")
    return imageio_ffmpeg.get_ffmpeg_exe()


def _duracion(ffmpeg: str, archivo: Path) -> float:
    salida = subprocess.run([ffmpeg, "-hide_banner", "-i", str(archivo)], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", salida)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 0.0


def _titulo(texto: str, destino: Path) -> None:
    """El título en dorado sobre una franja oscura difuminada arriba (PNG transparente del tamaño del video)."""
    lienzo = Image.new("RGBA", (tarjeta.ANCHO, tarjeta.ALTO), (0, 0, 0, 0))
    franja = Image.new("RGBA", (tarjeta.ANCHO, tarjeta.ALTO), (0, 0, 0, 0))
    ImageDraw.Draw(franja).rectangle((0, 0, tarjeta.ANCHO, 250), fill=(5, 12, 22, 170))
    lienzo.alpha_composite(franja.filter(ImageFilter.GaussianBlur(40)))
    fuente, lineas = tarjeta._titulo_que_entre(texto, tarjeta.ANCHO - 2 * tarjeta.MARGEN, 2)
    y = 70
    for linea in lineas:
        tarjeta._texto_oro(lienzo, (tarjeta.ANCHO // 2, y), linea, fuente, borde=4)
        y += int(fuente.size * 1.1)
    lienzo.save(destino)


def _cierre(semilla: int, destino: Path) -> None:
    """El cierre: fondo de la tarjeta, el emblema y la web."""
    lienzo = tarjeta._fondo(semilla)
    emblema = Image.open(tarjeta.RECURSOS / "emblema.png").convert("RGBA").resize((560, 560), Image.LANCZOS)
    halo = Image.new("RGBA", lienzo.size, (0, 0, 0, 0))
    ImageDraw.Draw(halo).ellipse((tarjeta.ANCHO // 2 - 340, 230, tarjeta.ANCHO // 2 + 340, 910),
                                 fill=tarjeta.ORO + (45,))
    lienzo.alpha_composite(halo.filter(ImageFilter.GaussianBlur(70)))
    lienzo.alpha_composite(emblema, ((tarjeta.ANCHO - 560) // 2, 290))
    tarjeta._texto_oro(lienzo, (tarjeta.ANCHO // 2, 940), "WORLD OF PIECES", tarjeta._fuente("Cinzel-Black.ttf", 70))
    ImageDraw.Draw(lienzo).text((tarjeta.ANCHO // 2, 1060), tarjeta.WEB, font=tarjeta._fuente("AlegreyaSans-Medium.ttf", 40),
                                fill=tarjeta.ORO, anchor="ma")
    lienzo.convert("RGB").save(destino, quality=95)


def _vertical(origen: Path, destino: Path) -> None:
    """Un cuadro apaisado (la pantalla del juego) al 4:5: el centro (4:3) al ancho, sobre él mismo difuminado."""
    img = Image.open(origen).convert("RGB")
    w, h = img.size
    if w <= h * 0.9:
        img.resize((tarjeta.ANCHO, tarjeta.ALTO), Image.LANCZOS).save(destino, quality=93)
        return
    fondo = img.resize((int(w * tarjeta.ALTO / h), tarjeta.ALTO), Image.BILINEAR)
    x = (fondo.width - tarjeta.ANCHO) // 2
    fondo = fondo.crop((x, 0, x + tarjeta.ANCHO, tarjeta.ALTO)).filter(ImageFilter.GaussianBlur(28))
    fondo = Image.blend(fondo, Image.new("RGB", fondo.size, (5, 12, 22)), 0.45)
    ancho = min(w, int(h * 4 / 3))
    centro = img.crop(((w - ancho) // 2, 0, (w - ancho) // 2 + ancho, h))
    centro = centro.resize((tarjeta.ANCHO, int(h * tarjeta.ANCHO / ancho)), Image.LANCZOS)
    fondo.paste(centro, (0, (tarjeta.ALTO - centro.height) // 2 + 60))
    fondo.save(destino, quality=93)


def _juntar(carpetas: list[Path], destino: Path) -> None:
    """Los cuadros de varias tomas, uno detrás del otro, numerados de corrido y al tamaño del video."""
    i = 0
    for c in carpetas:
        lista = sorted(c.glob("*.jpg"))
        if not lista:
            sys.exit(f"No hay cuadros en {c}: grabá la toma con la prueba clips_redes")
        for f in lista:
            _vertical(f, destino / f"{i:04d}.jpg")
            i += 1


def armar(ident: str, nombre: str, cuadros: Path, titulo: str, fps: int = FPS, texto: str = "",
          musica: Path | None = None) -> Path:
    FPS = fps  # noqa: N806 (los cuadros por segundo de esta toma)
    ffmpeg = _ffmpeg()
    lista = sorted(cuadros.glob("*.jpg"))
    if len(lista) < FPS * 3:
        sys.exit(f"Muy pocos cuadros en {cuadros} ({len(lista)}): grabá la toma con la prueba clips_redes")
    # 🖼️ (10/11/2026, pedido del usuario: la portada salía siempre con el emblema) La portada del post: un cuadro de la
    # toma (sin el título encima), a mitad de camino.
    portada = RAIZ / "imagenes" / "fuente" / f"{ident}.jpg"
    portada.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(lista[int(len(lista) * 0.55)], portada)
    toma = len(lista) / FPS
    total = toma + CIERRE - FUNDIDO
    semilla = int(hashlib.sha1(ident.encode()).hexdigest()[:8], 16)
    MUSICA = musica or tema_para(ident, f"{titulo}\n{texto}", total)  # noqa: N806
    largo_musica = _duracion(ffmpeg, MUSICA)
    if largo_musica <= 0:
        sys.exit(f"No encuentro la música: {MUSICA}")
    # Un pedazo distinto por post, siempre empezando en un segundo redondo y con lugar para todo el video.
    desde = (semilla % max(1, int(largo_musica - total - 1))) if largo_musica > total + 1 else 0
    destino = RAIZ / "videos" / f"{ident}.mp4"
    destino.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        png_titulo, jpg_cierre = Path(tmp) / "titulo.png", Path(tmp) / "cierre.jpg"
        _titulo(titulo, png_titulo)
        _cierre(semilla, jpg_cierre)
        filtro = (
            f"[1:v]format=rgba,fade=t=in:st=0.3:d=0.5:alpha=1,fade=t=out:st={TITULO_HASTA - 0.6}:d=0.6:alpha=1[t];"
            f"[0:v][t]overlay=0:0:shortest=1,format=yuv420p,setsar=1[v0];"
            f"[2:v]format=yuv420p,setsar=1,fps={FPS}[v1];"
            f"[v0][v1]xfade=transition=fade:duration={FUNDIDO}:offset={toma - FUNDIDO:.3f},scale=out_range=tv,format=yuv420p[v];"
            f"[3:a]afade=t=in:st=0:d=0.6,afade=t=out:st={total - 1.4:.3f}:d=1.4[a]"
        )
        cmd = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-framerate", str(FPS), "-i", str(cuadros / "%04d.jpg"),
            "-loop", "1", "-framerate", str(FPS), "-t", f"{toma:.3f}", "-i", str(png_titulo),
            "-loop", "1", "-framerate", str(FPS), "-t", f"{CIERRE:.3f}", "-i", str(jpg_cierre),
            "-ss", str(desde), "-t", f"{total:.3f}", "-i", str(MUSICA),
            "-filter_complex", filtro, "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "slow", "-crf", "23", "-profile:v", "high", "-pix_fmt", "yuv420p", "-color_range", "tv",
            "-r", str(FPS), "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
            "-movflags", "+faststart", "-t", f"{total:.3f}", str(destino),
        ]
        subprocess.run(cmd, check=True)
    mb = destino.stat().st_size / 1e6
    print(f"{destino.relative_to(RAIZ)}: {total:.1f} s, {mb:.1f} MB (toma '{nombre}', {MUSICA.stem} desde {desde} s)")
    if mb > 15:
        print("  ojo: pesa mucho para un post; acortá la toma")
    return destino


def _fps_de(carpeta: Path) -> int:
    """Los cuadros por segundo con que se grabó la toma (`fps.txt` de clips_redes; sin el archivo, 30)."""
    f = carpeta / "fps.txt"
    return int(f.read_text().strip()) if f.exists() else 30


def _apaisado(carpeta: Path) -> bool:
    """Si los cuadros no vienen ya a 1080×1350 (la pantalla apaisada o la ventana vertical de la interfaz, 864×1080),
    hay que pasarlos por `_vertical`."""
    primero = next(iter(sorted(carpeta.glob("*.jpg"))), None)
    if primero is None:
        return False
    return Image.open(primero).size != (tarjeta.ANCHO, tarjeta.ALTO)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("id", help="la entrada de la cola (ej. lote1-06)")
    p.add_argument("nombre", help="el nombre de la toma en clips_redes (ej. bestiario)")
    p.add_argument("--cuadros", type=Path, help="carpeta de los cuadros (por defecto la de clips_redes)")
    p.add_argument("--titulo", help="título sobre el video (por defecto el de la entrada de la cola)")
    p.add_argument("--sin-cola", action="store_true", help="no anotar el video en la cola")
    p.add_argument("--musica", help="el tema a usar (nombre de sonidos/musica/temas, sin extensión; por defecto, elegido)")
    a = p.parse_args()
    cola = json.loads(COLA.read_text(encoding="utf-8"))
    entrada = next((e for e in cola["entradas"] if e["id"] == a.id), None)
    if entrada is None and not a.titulo:
        sys.exit(f"No hay una entrada '{a.id}' en la cola (o pasá --titulo)")
    titulo = a.titulo or entrada["titulo"]
    texto = (entrada or {}).get("texto", "")
    musica = None
    if a.musica:
        musica = next((t for t in TEMAS.glob(a.musica + ".*") if t.suffix in (".mp3", ".wav", ".ogg")), None)
        if musica is None:
            sys.exit(f"No hay un tema '{a.musica}' en {TEMAS}")
    carpetas = [(a.cuadros or CUADROS) / n for n in a.nombre.split("+")]
    fps_tomas = {_fps_de(c) for c in carpetas}
    if len(fps_tomas) > 1:
        sys.exit(f"Las tomas tienen distintos cuadros por segundo ({sorted(fps_tomas)}): regrabalas al mismo")
    fps = fps_tomas.pop()
    if "+" in a.nombre or a.cuadros is None and _apaisado(CUADROS / a.nombre):
        with tempfile.TemporaryDirectory() as tmp:
            _juntar([(a.cuadros or CUADROS) / n for n in a.nombre.split("+")], Path(tmp))
            destino = armar(a.id, a.nombre, Path(tmp), titulo, fps, texto, musica)
    else:
        destino = armar(a.id, a.nombre, a.cuadros or CUADROS / a.nombre, titulo, fps, texto, musica)
    if entrada is not None and not a.sin_cola:
        entrada["video"] = str(destino.relative_to(RAIZ)).replace("\\", "/")
        if not entrada.get("imagen_propia"):   # (una captura elegida a mano, `Publicar-imagen:`, no se pisa)
            entrada["imagen"] = f"imagenes/fuente/{a.id}.jpg"
        COLA.write_text(json.dumps(cola, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"  anotado en la cola: {a.id}")


if __name__ == "__main__":
    main()
