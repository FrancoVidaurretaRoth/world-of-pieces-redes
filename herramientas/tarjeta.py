"""Dibuja las tarjetas de Instagram (1080x1350, JPEG) con el estilo del logo: fondo azul noche, oro y Cinzel.

- tarjeta_novedad(titulo, texto, fecha, imagen=None): un cambio. Con imagen (una captura del juego) la pone arriba
  enmarcada en oro; sin imagen, va el emblema.
- tarjeta_resumen(titulos, desde, hasta): el resumen semanal, una lista.
"""
from __future__ import annotations

import random
import zlib
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

RAIZ = Path(__file__).resolve().parent.parent
RECURSOS = RAIZ / "recursos"
ANCHO, ALTO = 1080, 1350
MARGEN = 90

ORO_CLARO = (255, 241, 191)
ORO = (240, 199, 94)
ORO_OSCURO = (195, 138, 36)
CREMA = (233, 226, 207)
TINTA = (42, 24, 6)
WEB = "worldofpieces.pages.dev"
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]


def _fuente(nombre: str, tam: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(RECURSOS / "fuentes" / nombre), tam)


def fecha_larga(d: date) -> str:
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def _fondo(semilla: int) -> Image.Image:
    """Degradado radial azul noche + polvo dorado (fijo por semilla)."""
    pequeno = Image.new("RGB", (108, 135))
    px = pequeno.load()
    for y in range(135):
        for x in range(108):
            dx, dy = (x - 54) / 75, (y - 55) / 85
            t = min(1.0, (dx * dx + dy * dy) ** 0.5)
            a, b, c = (27, 67, 97), (12, 34, 54), (5, 12, 22)
            if t < 0.6:
                k = t / 0.6
                col = tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))
            else:
                k = (t - 0.6) / 0.4
                col = tuple(int(b[i] + (c[i] - b[i]) * k) for i in range(3))
            px[x, y] = col
    fondo = pequeno.resize((ANCHO, ALTO), Image.BICUBIC).convert("RGBA")
    capa = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    azar = random.Random(semilla)
    for _ in range(90):
        x, y, r = azar.randrange(ANCHO), azar.randrange(ALTO), azar.choice([1, 1, 2, 2, 3])
        d.ellipse((x - r, y - r, x + r, y + r), fill=ORO + (azar.randint(35, 120),))
    return Image.alpha_composite(fondo, capa)


def _texto_oro(lienzo: Image.Image, xy: tuple[int, int], texto: str, fuente: ImageFont.FreeTypeFont,
               ancla: str = "ma", borde: int = 5) -> None:
    """Texto con degradado dorado, borde tinta y sombra, como el título del logo."""
    caja = ImageDraw.Draw(lienzo).textbbox(xy, texto, font=fuente, anchor=ancla, stroke_width=borde)
    ancho, alto = caja[2] - caja[0] + 20, caja[3] - caja[1] + 20
    origen = (caja[0] - 10, caja[1] - 10)
    rel = (xy[0] - origen[0], xy[1] - origen[1])

    mascara = Image.new("L", (ancho, alto), 0)
    ImageDraw.Draw(mascara).text(rel, texto, font=fuente, anchor=ancla, fill=255)
    contorno = Image.new("L", (ancho, alto), 0)
    ImageDraw.Draw(contorno).text(rel, texto, font=fuente, anchor=ancla, fill=255, stroke_width=borde,
                                  stroke_fill=255)
    # degradado vertical
    grad = Image.new("RGBA", (ancho, alto))
    gd = ImageDraw.Draw(grad)
    paradas = [(0.0, ORO_CLARO), (0.45, ORO), (0.6, (212, 154, 44)), (1.0, (138, 85, 19))]
    for y in range(alto):
        t = y / max(1, alto - 1)
        for i in range(len(paradas) - 1):
            t0, c0 = paradas[i]
            t1, c1 = paradas[i + 1]
            if t0 <= t <= t1:
                k = (t - t0) / (t1 - t0)
                gd.line([(0, y), (ancho, y)], fill=tuple(int(c0[j] + (c1[j] - c0[j]) * k) for j in range(3)) + (255,))
                break
    sombra = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    sombra.putalpha(contorno.filter(ImageFilter.GaussianBlur(6)).point(lambda v: int(v * 0.6)))
    lienzo.alpha_composite(sombra, (origen[0], origen[1] + 6))
    tinta = Image.new("RGBA", (ancho, alto), TINTA + (255,))
    tinta.putalpha(contorno)
    lienzo.alpha_composite(tinta, origen)
    grad.putalpha(mascara)
    lienzo.alpha_composite(grad, origen)


def _partir(texto: str, fuente: ImageFont.FreeTypeFont, ancho: int) -> list[str]:
    lineas: list[str] = []
    for parrafo in texto.split("\n"):
        actual = ""
        for palabra in parrafo.split():
            prueba = f"{actual} {palabra}".strip()
            if fuente.getlength(prueba) <= ancho:
                actual = prueba
            else:
                if actual:
                    lineas.append(actual)
                actual = palabra
        lineas.append(actual)
    return lineas


def _titulo_que_entre(texto: str, ancho: int, max_lineas: int) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    for tam in (78, 70, 62, 56, 50, 44):
        f = _fuente("Cinzel-Black.ttf", tam)
        lineas = _partir(texto.upper(), f, ancho)
        if len(lineas) <= max_lineas:
            return f, lineas
    return f, lineas[:max_lineas]


def _separador(d: ImageDraw.ImageDraw, y: int, texto: str | None = None) -> None:
    cx = ANCHO // 2
    hueco = 0
    if texto:
        f = _fuente("Cinzel-Bold.ttf", 30)
        hueco = int(f.getlength(texto)) // 2 + 24
        d.text((cx, y), texto, font=f, fill=ORO, anchor="mm")
    for lado in (-1, 1):
        x0, x1 = cx + lado * hueco, cx + lado * 330
        d.line([(x0, y), (x1, y)], fill=ORO_OSCURO, width=3)
        d.polygon([(x1, y - 7), (x1 + lado * 12, y), (x1, y + 7), (x1 - lado * 12, y)], fill=ORO)


def _pie(d: ImageDraw.ImageDraw, izquierda: str) -> None:
    f = _fuente("AlegreyaSans-Medium.ttf", 30)
    y = ALTO - 70
    d.line([(MARGEN, y - 40), (ANCHO - MARGEN, y - 40)], fill=ORO_OSCURO + (160,), width=2)
    d.text((MARGEN, y), izquierda, font=f, fill=CREMA, anchor="lm")
    d.text((ANCHO - MARGEN, y), WEB, font=f, fill=ORO, anchor="rm")


def _sello(lienzo: Image.Image, texto: str, x: int, y: int) -> None:
    """El sello de la categoría: una placa oscura con borde dorado y el nombre en mayúsculas (arriba a la izquierda)."""
    f = _fuente("Cinzel-Bold.ttf", 34)
    texto = texto.upper()
    ancho = int(f.getlength(texto)) + 56
    alto = 62
    sombra = Image.new("RGBA", lienzo.size, (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle((x + 4, y + 6, x + ancho + 4, y + alto + 6), radius=14, fill=(0, 0, 0, 120))
    lienzo.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(6)))
    d = ImageDraw.Draw(lienzo)
    d.rounded_rectangle((x, y, x + ancho, y + alto), radius=14, fill=TINTA + (235,), outline=ORO, width=4)
    d.text((x + ancho // 2, y + alto // 2 + 1), texto, font=f, fill=ORO_CLARO, anchor="mm")


def _cabecera(lienzo: Image.Image, imagen: Path | None) -> int:
    """Pone arriba la captura (enmarcada) o el emblema. Devuelve la y donde termina."""
    if imagen and imagen.exists():
        foto = Image.open(imagen).convert("RGB")
        ancho, alto = ANCHO - 2 * MARGEN + 40, 560
        if foto.width / foto.height >= 1.3:
            # apaisada: llena el marco recortando lo que sobra
            escala = max(ancho / foto.width, alto / foto.height)
            foto = foto.resize((int(foto.width * escala), int(foto.height * escala)), Image.LANCZOS)
            x0, y0 = (foto.width - ancho) // 2, (foto.height - alto) // 2
            foto = foto.crop((x0, y0, x0 + ancho, y0 + alto))
        else:
            # vertical o cuadrada (retratos): entra entera, sobre un fondo difuminado de ella misma
            escala = max(ancho / foto.width, alto / foto.height)
            fondo = foto.resize((int(foto.width * escala), int(foto.height * escala)), Image.LANCZOS)
            x0, y0 = (fondo.width - ancho) // 2, (fondo.height - alto) // 2
            fondo = fondo.crop((x0, y0, x0 + ancho, y0 + alto)).filter(ImageFilter.GaussianBlur(28))
            fondo = Image.blend(fondo, Image.new("RGB", fondo.size, (8, 20, 34)), 0.45)
            escala = alto / foto.height
            frente = foto.resize((int(foto.width * escala), alto), Image.LANCZOS)
            fondo.paste(frente, ((ancho - frente.width) // 2, 0))
            foto = fondo
        x, y = (ANCHO - ancho) // 2, 70
        d = ImageDraw.Draw(lienzo)
        d.rounded_rectangle((x - 10, y - 10, x + ancho + 10, y + alto + 10), radius=18, fill=TINTA, outline=ORO,
                            width=5)
        lienzo.paste(foto, (x, y))
        return y + alto + 50
    emblema = Image.open(RECURSOS / "emblema.png").convert("RGBA").resize((470, 470), Image.LANCZOS)
    halo = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
    ImageDraw.Draw(halo).ellipse((ANCHO // 2 - 300, 40, ANCHO // 2 + 300, 640), fill=ORO + (40,))
    lienzo.alpha_composite(halo.filter(ImageFilter.GaussianBlur(60)))
    lienzo.alpha_composite(emblema, ((ANCHO - 470) // 2, 70))
    return 70 + 470 + 30


def tarjeta_novedad(titulo: str, texto: str, fecha: date, destino: Path, imagen: Path | None = None,
                    etiqueta: str = "NOVEDAD", categoria: str = "") -> Path:
    lienzo = _fondo(zlib.crc32(titulo.encode()))
    y = _cabecera(lienzo, imagen)
    if categoria:
        _sello(lienzo, categoria, MARGEN - 4, 46)
    d = ImageDraw.Draw(lienzo)
    _separador(d, y, etiqueta)
    y += 60

    con_foto = imagen is not None and imagen.exists()
    f_tit, lineas = _titulo_que_entre(titulo, ANCHO - 2 * MARGEN, 2 if con_foto else 3)
    alto_linea = int(f_tit.size * 1.18)
    for linea in lineas:
        _texto_oro(lienzo, (ANCHO // 2, y), linea, f_tit)
        y += alto_linea
    y += 25

    d = ImageDraw.Draw(lienzo)
    espacio = ALTO - 150 - y
    for tam in (42, 38, 34, 31, 28):
        f_txt = _fuente("AlegreyaSans-Regular.ttf", tam)
        lineas_txt = _partir(texto, f_txt, ANCHO - 2 * MARGEN - 20)
        if len(lineas_txt) * tam * 1.35 <= espacio:
            break
    max_lineas = int(espacio // (f_txt.size * 1.35))
    if len(lineas_txt) > max_lineas:
        lineas_txt = lineas_txt[:max_lineas]
        lineas_txt[-1] = lineas_txt[-1].rstrip(".,;: ") + "…"
    for linea in lineas_txt:
        d.text((ANCHO // 2, y), linea, font=f_txt, fill=CREMA, anchor="ma")
        y += int(f_txt.size * 1.35)

    _pie(d, fecha_larga(fecha))
    destino.parent.mkdir(parents=True, exist_ok=True)
    lienzo.convert("RGB").save(destino, "JPEG", quality=92, optimize=True)
    return destino


def tarjeta_resumen(titulos: list[str], desde: date, hasta: date, destino: Path) -> Path:
    lienzo = _fondo(desde.toordinal())
    emblema = Image.open(RECURSOS / "emblema.png").convert("RGBA").resize((260, 260), Image.LANCZOS)
    lienzo.alpha_composite(emblema, ((ANCHO - 260) // 2, 50))
    y = 345
    _texto_oro(lienzo, (ANCHO // 2, y), "ESTA SEMANA", _fuente("Cinzel-Black.ttf", 76))
    y += 95
    d = ImageDraw.Draw(lienzo)
    d.text((ANCHO // 2, y), "EN WORLD OF PIECES", font=_fuente("Cinzel-Bold.ttf", 36), fill=ORO, anchor="ma")
    y += 80
    _separador(d, y)
    y += 50

    maximo = 8
    visibles = titulos[:maximo]
    f = _fuente("AlegreyaSans-Medium.ttf", 40 if len(visibles) <= 6 else 35)
    paso = int(f.size * 1.5)
    for t in visibles:
        linea = _partir(t, f, ANCHO - 2 * MARGEN - 50)[0]
        if linea != t:
            linea = linea.rstrip(".,;: ") + "…"
        d.polygon([(MARGEN + 8, y + f.size * 0.55 - 9), (MARGEN + 17, y + f.size * 0.55),
                   (MARGEN + 8, y + f.size * 0.55 + 9), (MARGEN - 1, y + f.size * 0.55)], fill=ORO)
        d.text((MARGEN + 40, y), linea, font=f, fill=CREMA)
        y += paso
    if len(titulos) > maximo:
        d.text((MARGEN + 40, y), f"y {len(titulos) - maximo} {'cambio' if len(titulos) - maximo == 1 else 'cambios'} más en la web",
               font=_fuente("AlegreyaSans-Regular.ttf", 34), fill=ORO)

    _pie(d, f"{desde.day}/{desde.month} al {hasta.day}/{hasta.month}/{hasta.year}")
    destino.parent.mkdir(parents=True, exist_ok=True)
    lienzo.convert("RGB").save(destino, "JPEG", quality=92, optimize=True)
    return destino
