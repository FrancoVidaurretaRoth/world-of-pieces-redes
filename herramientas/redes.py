"""Publica las novedades de World of Pieces en Instagram (y el resumen semanal también en la web).

Comandos (los corren los workflows de .github/workflows; a mano, con --seco no publica ni pushea nada):
  python herramientas/redes.py sincronizar        lee los commits nuevos del juego y encola los marcados
  python herramientas/redes.py publicar [--seco]  publica en Instagram la primera novedad de la cola (una por corrida)
  python herramientas/redes.py resumen --web DIR [--seco]   resumen de los últimos 7 días: Instagram + noticia en la web
  python herramientas/redes.py verificar          prueba los tokens sin publicar nada
  python herramientas/redes.py renovar            renueva el token de Instagram (60 días) y lo guarda como secreto

Cómo se marca un commit del juego para publicarlo (líneas al final del mensaje, junto a las demás):
  Publicar: Título para los jugadores
  Publicar-texto: Una a tres frases para los jugadores, sin jerga interna.
  Publicar-imagen: ruta/de/una/captura.png        (opcional, ruta dentro del repo del juego)

Variables de entorno:
  JUEGO_REPO   dueño/nombre del repo del juego (por defecto FrancoVidaurretaRoth/world-of-pieces-link)
  JUEGO_RAMA   rama a leer (master)
  GH_PAT       token de GitHub que puede leer el repo del juego (y escribir secretos de este repo, para `renovar`)
  IG_TOKEN     token de la app de Meta (Unified login; permisos instagram_basic + instagram_content_publish)
  IG_USER_ID   id de la cuenta de Instagram (si falta se busca en /me/assigned_instagram_accounts)
  IG_API       opcional: host y versión de la API (por defecto https://graph.facebook.com/v26.0)
  REPO_PUBLICO dueño/nombre de este repo (lo pone GitHub Actions en GITHUB_REPOSITORY)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tarjeta  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
COLA = RAIZ / "cola" / "cola.json"
# Las apps nuevas de Meta (desde fines de 2026) usan "API setup with Unified login": token de usuario del sistema
# sobre graph.facebook.com. Con una app vieja de "Instagram login", IG_API=https://graph.instagram.com/v23.0.
IG_API = os.environ.get("IG_API") or "https://graph.facebook.com/v26.0"
JUEGO_REPO = os.environ.get("JUEGO_REPO", "FrancoVidaurretaRoth/world-of-pieces-link")
JUEGO_RAMA = os.environ.get("JUEGO_RAMA", "master")
REPO_PUBLICO = os.environ.get("GITHUB_REPOSITORY", os.environ.get("REPO_PUBLICO", ""))
RAMA_PUBLICA = os.environ.get("GITHUB_REF_NAME", "main")
MAX_INTENTOS = 3
HASHTAGS = "#worldofpieces #indiegame #indiedev #gamedev #rpg #mmorpg #godotengine #fantasy"
# Lo que nunca puede salir publicado aunque alguien lo escriba en un commit.
PROHIBIDO = re.compile(r"\b(claude|anthropic|chatgpt|openai|\bIA\b|inteligencia artificial)\b", re.IGNORECASE)


# ---------------------------------------------------------------- utilidades

def _log(*a: object) -> None:
    print(*a, flush=True)


def _leer_cola() -> dict:
    if COLA.exists():
        return json.loads(COLA.read_text(encoding="utf-8"))
    return {"ultimo_commit": None, "entradas": []}


def _guardar_cola(cola: dict) -> None:
    COLA.parent.mkdir(parents=True, exist_ok=True)
    COLA.write_text(json.dumps(cola, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _http(url: str, metodo: str = "GET", datos: dict | None = None, cabeceras: dict | None = None,
          crudo: bool = False):
    cuerpo = urllib.parse.urlencode(datos).encode() if datos is not None else None
    req = urllib.request.Request(url, data=cuerpo, method=metodo, headers=cabeceras or {})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            contenido = r.read()
    except urllib.error.HTTPError as e:
        detalle = e.read().decode(errors="replace")
        # nunca imprimir el token
        raise RuntimeError(f"HTTP {e.code} en {url.split('?')[0]}: {detalle[:500]}") from None
    return contenido if crudo else json.loads(contenido)


def _github(ruta: str, crudo: bool = False):
    cab = {"Accept": "application/vnd.github.raw" if crudo else "application/vnd.github+json",
           "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "wop-redes"}
    if os.environ.get("GH_PAT"):
        cab["Authorization"] = f"Bearer {os.environ['GH_PAT']}"
    return _http(f"https://api.github.com{ruta}", cabeceras=cab, crudo=crudo)


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=RAIZ, check=True, capture_output=True, text=True).stdout


def _commit_y_push(mensaje: str, *rutas: Path) -> None:
    _git("add", *[str(r.relative_to(RAIZ)) for r in rutas])
    if not _git("status", "--porcelain"):
        return
    _git("commit", "-m", mensaje)
    for intento in range(3):
        try:
            _git("pull", "--rebase", "--quiet")
            _git("push", "--quiet")
            return
        except subprocess.CalledProcessError:
            time.sleep(5 * (intento + 1))
    raise RuntimeError("no se pudo pushear")


def _limpio(texto: str) -> str:
    """Saca entera cada frase que nombre a la IA (la web y las redes nunca la mencionan)."""
    frases = re.split(r"(?<=[.!?])\s+", texto.strip())
    return " ".join(f for f in frases if not PROHIBIDO.search(f)).strip()


# ---------------------------------------------------------------- 1. sincronizar

def extraer_marcas(mensaje: str) -> list[dict]:
    """Saca las novedades marcadas de un mensaje de commit. Puede haber más de una por commit."""
    novedades: list[dict] = []
    for linea in mensaje.splitlines():
        m = re.match(r"^\s*Publicar(-texto|-imagen)?\s*:\s*(.+?)\s*$", linea, re.IGNORECASE)
        if not m:
            continue
        clave, valor = (m.group(1) or "").lower(), m.group(2)
        if clave == "":
            novedades.append({"titulo": _limpio(valor), "texto": "", "imagen_juego": None})
        elif novedades and clave == "-texto":
            novedades[-1]["texto"] = (novedades[-1]["texto"] + " " + _limpio(valor)).strip()
        elif novedades and clave == "-imagen":
            novedades[-1]["imagen_juego"] = valor
    return [n for n in novedades if n["titulo"]]


def sincronizar(seco: bool) -> None:
    cola = _leer_cola()
    commits: list[dict] = []
    pagina = 1
    while True:
        lote = _github(f"/repos/{JUEGO_REPO}/commits?sha={JUEGO_RAMA}&per_page=100&page={pagina}")
        if not lote:
            break
        corte = False
        for c in lote:
            if c["sha"] == cola["ultimo_commit"]:
                corte = True
                break
            commits.append(c)
        if corte or cola["ultimo_commit"] is None or pagina >= 5:
            break
        pagina += 1
    if cola["ultimo_commit"] is None:
        # Primera vez: no se publica la historia vieja, se arranca desde acá.
        if commits:
            cola["ultimo_commit"] = commits[0]["sha"]
        _log(f"Primera sincronización: arranco desde {str(cola['ultimo_commit'])[:10]}")
        if not seco:
            _guardar_cola(cola)
            _commit_y_push("Cola: punto de partida", COLA)
        return

    ids = {e["id"] for e in cola["entradas"]}
    nuevas: list[Path] = []
    for c in reversed(commits):  # del más viejo al más nuevo
        fecha = c["commit"]["committer"]["date"][:10]
        for i, n in enumerate(extraer_marcas(c["commit"]["message"])):
            ident = f"{c['sha'][:10]}-{i}"
            if ident in ids:
                continue
            imagen = None
            if n["imagen_juego"]:
                try:
                    ruta = urllib.parse.quote(n["imagen_juego"].lstrip("/"))
                    datos = _github(f"/repos/{JUEGO_REPO}/contents/{ruta}?ref={c['sha']}", crudo=True)
                    ext = Path(n["imagen_juego"]).suffix.lower() or ".png"
                    destino = RAIZ / "imagenes" / "fuente" / f"{ident}{ext}"
                    if not seco:
                        destino.parent.mkdir(parents=True, exist_ok=True)
                        destino.write_bytes(datos)
                        nuevas.append(destino)
                    imagen = str(destino.relative_to(RAIZ)).replace("\\", "/")
                except RuntimeError as e:
                    _log(f"  sin imagen para {ident}: {e}")
            cola["entradas"].append({"id": ident, "fecha": fecha, "titulo": n["titulo"], "texto": n["texto"],
                                     "imagen": imagen, "estado": "pendiente", "intentos": 0})
            _log(f"  + {ident}: {n['titulo']}")
    if commits:
        cola["ultimo_commit"] = commits[0]["sha"]
    _log(f"{len(commits)} commits nuevos; {sum(e['estado'] == 'pendiente' for e in cola['entradas'])} en cola")
    if not seco:
        _guardar_cola(cola)
        _commit_y_push("Cola: commits nuevos del juego", COLA, *nuevas)


# ---------------------------------------------------------------- Instagram

def _ig_user_id(token: str) -> str:
    if os.environ.get("IG_USER_ID"):
        return os.environ["IG_USER_ID"]
    if "graph.instagram.com" in IG_API:
        return _http(f"{IG_API}/me?fields=user_id,username&access_token={token}")["user_id"]
    # Unified login: /me es el usuario del sistema; las cuentas de Instagram se listan aparte.
    cuentas = _http(f"{IG_API}/me/assigned_instagram_accounts?access_token={token}").get("data", [])
    if not cuentas:
        raise RuntimeError("el token no tiene cuentas de Instagram asignadas: cargá la variable IG_USER_ID")
    return cuentas[0]["id"]


def _url_publica(ruta: Path) -> str:
    rel = str(ruta.relative_to(RAIZ)).replace("\\", "/")
    return f"https://raw.githubusercontent.com/{REPO_PUBLICO}/{RAMA_PUBLICA}/{rel}"


def _esperar_url(url: str) -> None:
    for _ in range(24):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30) as r:
                if r.status == 200:
                    return
        except urllib.error.URLError:
            pass
        time.sleep(5)
    raise RuntimeError(f"la imagen no quedó pública: {url}")


def publicar_en_instagram(imagen: Path, texto: str) -> dict:
    token = os.environ["IG_TOKEN"]
    usuario = _ig_user_id(token)
    url = _url_publica(imagen)
    _esperar_url(url)
    contenedor = _http(f"{IG_API}/{usuario}/media", "POST",
                       {"image_url": url, "caption": texto, "access_token": token})["id"]
    for _ in range(30):
        estado = _http(f"{IG_API}/{contenedor}?fields=status_code&access_token={token}").get("status_code")
        if estado == "FINISHED":
            break
        if estado in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram rechazó la imagen ({estado})")
        time.sleep(4)
    media = _http(f"{IG_API}/{usuario}/media_publish", "POST",
                  {"creation_id": contenedor, "access_token": token})["id"]
    enlace = _http(f"{IG_API}/{media}?fields=permalink&access_token={token}").get("permalink", "")
    return {"ig_id": media, "enlace": enlace}


def _epigrafe(titulo: str, texto: str) -> str:
    partes = [titulo]
    if texto:
        partes.append(texto)
    partes.append("Todas las novedades en worldofpieces.pages.dev (link en la bio).")
    partes.append(HASHTAGS)
    return "\n\n".join(partes)


# ---------------------------------------------------------------- 2. publicar

MAX_POR_DIA = 5
MIN_ENTRE_POSTS = timedelta(minutes=90)


def publicar(seco: bool) -> None:
    cola = _leer_cola()
    # Freno por si dos disparadores (el reloj y los cron de GitHub) caen juntos: nunca dos posts seguidos ni más de 5
    # en el día (UTC).
    ahora = datetime.now(timezone.utc)
    hechos = [datetime.fromisoformat(e["publicado"]) for e in cola["entradas"] if e.get("publicado")]
    if any(ahora - h < MIN_ENTRE_POSTS for h in hechos):
        _log("Hubo un post hace menos de 90 minutos: este turno no publica.")
        return
    if sum(1 for h in hechos if h.date() == ahora.date()) >= MAX_POR_DIA:
        _log(f"Ya salieron {MAX_POR_DIA} posts hoy: este turno no publica.")
        return
    pendiente = next((e for e in cola["entradas"] if e["estado"] == "pendiente"), None)
    if pendiente is None:
        _log("Nada en la cola.")
        return
    imagen_fuente = RAIZ / pendiente["imagen"] if pendiente.get("imagen") else None
    destino = RAIZ / "imagenes" / "posts" / f"{pendiente['id']}.jpg"
    tarjeta.tarjeta_novedad(pendiente["titulo"], pendiente["texto"], date.fromisoformat(pendiente["fecha"]),
                            destino, imagen_fuente, pendiente.get("etiqueta", "NOVEDAD"))
    epigrafe = _epigrafe(pendiente["titulo"], pendiente["texto"])
    _log(f"Tarjeta: {destino}\n--- epígrafe ---\n{epigrafe}\n---")
    if seco:
        return
    _commit_y_push(f"Post: {pendiente['titulo']}", destino)
    try:
        resultado = publicar_en_instagram(destino, epigrafe)
    except Exception as e:  # noqa: BLE001
        pendiente["intentos"] = pendiente.get("intentos", 0) + 1
        if pendiente["intentos"] >= MAX_INTENTOS:
            pendiente["estado"] = "error"
        pendiente["ultimo_error"] = str(e)[:300]
        _guardar_cola(cola)
        _commit_y_push(f"Cola: falló {pendiente['id']}", COLA)
        raise
    pendiente.update(estado="publicado", publicado=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     **resultado)
    _guardar_cola(cola)
    _commit_y_push(f"Cola: publicado {pendiente['id']}", COLA)
    _log(f"Publicado: {resultado['enlace']}")


# ---------------------------------------------------------------- 3. resumen semanal

def _noticia_web(entradas: list[dict], desde: date, hasta: date, enlace_ig: str) -> tuple[str, str]:
    clave = f"semana-{hasta.isoformat()}"
    titulos = ", ".join(e["titulo"] for e in entradas[:3])
    lineas = [
        "---",
        f"clave: {clave}",
        f'titulo: "Esta semana en World of Pieces ({desde.day}/{desde.month} al {hasta.day}/{hasta.month})"',
        f'descripcion: {json.dumps(f"{len(entradas)} novedades de la semana: {titulos}.", ensure_ascii=False)}',
        f"fecha: {hasta.isoformat()}",
        "tipo: devblog",
        "etiquetas: [semanal]",
        "destacada: false",
        "---",
        "",
        "Lo que cambió en el juego esta semana:",
        "",
    ]
    for e in entradas:
        lineas += [f"## {e['titulo']}", ""]
        if e.get("texto"):
            lineas += [e["texto"], ""]
    if enlace_ig:
        lineas += [f"También lo fui contando en [Instagram]({enlace_ig}).", ""]
    return clave, "\n".join(lineas)


def resumen(web: Path | None, seco: bool, hasta: date | None = None) -> None:
    cola = _leer_cola()
    hasta = hasta or date.today()
    desde = hasta - timedelta(days=6)
    entradas = [e for e in cola["entradas"] if desde <= date.fromisoformat(e["fecha"]) <= hasta
                and e["estado"] != "descartado" and e.get("etiqueta", "NOVEDAD") == "NOVEDAD"]
    if not entradas:
        _log("Semana sin novedades marcadas: no hay resumen.")
        return
    destino = RAIZ / "imagenes" / "posts" / f"semana-{hasta.isoformat()}.jpg"
    tarjeta.tarjeta_resumen([e["titulo"] for e in entradas], desde, hasta, destino)
    epigrafe = "\n".join([f"Esta semana en World of Pieces ({desde.day}/{desde.month} al {hasta.day}/{hasta.month}):",
                          "", *[f"◆ {e['titulo']}" for e in entradas], "",
                          "El detalle de cada cambio, en worldofpieces.pages.dev (link en la bio).", "", HASHTAGS])
    _log(f"Tarjeta: {destino}\n--- epígrafe ---\n{epigrafe}\n---")
    enlace = ""
    if not seco:
        _commit_y_push(f"Resumen semanal {hasta.isoformat()}", destino)
        enlace = publicar_en_instagram(destino, epigrafe)["enlace"]
        _log(f"Publicado: {enlace}")
    if web is not None:
        clave, md = _noticia_web(entradas, desde, hasta, enlace)
        archivo = web / "src" / "content" / "noticias" / "es" / f"{clave}.md"
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(md, encoding="utf-8")
        _log(f"Noticia web: {archivo}")


# ---------------------------------------------------------------- 4. renovar el token

def renovar() -> None:
    if "graph.instagram.com" not in IG_API:
        # Unified login: el token es de usuario del sistema y vence cuando se eligió al crearlo ("Nunca" si se
        # pudo). Si se eligió un vencimiento, hay que generar otro a mano en el panel de Meta.
        _log("Token de Unified login: no se renueva por API (ver README).")
        return
    nuevo = _http(f"https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token"
                  f"&access_token={os.environ['IG_TOKEN']}")
    subprocess.run(["gh", "secret", "set", "IG_TOKEN", "--repo", REPO_PUBLICO, "--body", nuevo["access_token"]],
                   check=True, env={**os.environ, "GH_TOKEN": os.environ["GH_PAT"]})
    _log(f"Token renovado; vence en {int(nuevo.get('expires_in', 0)) // 86400} días.")


def verificar() -> None:
    """Prueba los dos tokens sin publicar nada."""
    token = os.environ.get("IG_TOKEN", "")
    usuario = _ig_user_id(token)
    cuenta = _http(f"{IG_API}/{usuario}?fields=username,media_count&access_token={token}")
    _log(f"Instagram OK: @{cuenta.get('username')} ({cuenta.get('media_count')} publicaciones)")
    try:
        limite = _http(f"{IG_API}/{usuario}/content_publishing_limit?fields=quota_usage,config"
                       f"&access_token={token}")
        _log(f"Cupo de publicación: {json.dumps(limite.get('data', limite), ensure_ascii=False)}")
    except RuntimeError as e:
        _log(f"(no se pudo leer el cupo: {e})")
    if os.environ.get("GH_PAT"):
        ultimo = _github(f"/repos/{JUEGO_REPO}/commits?sha={JUEGO_RAMA}&per_page=1")[0]
        _log(f"GitHub OK: último commit del juego {ultimo['sha'][:10]} ({ultimo['commit']['committer']['date']})")
    else:
        _log("GH_PAT no está cargado.")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("comando", choices=["sincronizar", "publicar", "resumen", "renovar", "verificar"])
    p.add_argument("--seco", action="store_true", help="no publica ni pushea nada")
    p.add_argument("--web", type=Path, help="carpeta del repo de la web (para el resumen)")
    p.add_argument("--hasta", type=date.fromisoformat, help="último día del resumen (por defecto hoy)")
    a = p.parse_args()
    if a.comando == "sincronizar":
        sincronizar(a.seco)
    elif a.comando == "publicar":
        publicar(a.seco)
    elif a.comando == "resumen":
        resumen(a.web, a.seco, a.hasta)
    elif a.comando == "verificar":
        verificar()
    else:
        renovar()


if __name__ == "__main__":
    main()
