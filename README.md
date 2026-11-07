# World of Pieces: redes

Publica solas las novedades del juego en Instagram ([@world_of_pieces_wop](https://www.instagram.com/world_of_pieces_wop/))
y arma un resumen semanal (Instagram + noticia en [worldofpieces.pages.dev](https://worldofpieces.pages.dev)). Todo
gratis: GitHub Actions en un repo público (minutos sin límite) + la API de Instagram.

## Cómo funciona

1. Un commit del juego que traiga algo interesante para los jugadores lleva, al final del mensaje:
   ```
   Publicar: Ventoria se llena de vida
   Publicar-texto: Los ciudadanos de la capital ahora tienen rutina: abren sus tiendas, charlan en la plaza y vuelven a casa al anochecer.
   Publicar-imagen: docs/capturas/ventoria.png      (opcional: una captura que esté en el repo del juego)
   Publicar-categoria: ciudades                     (opcional: si falta, se deduce del título y el texto)
   ```
   Los commits sin `Publicar:` no se publican nunca. Un commit puede traer varias novedades.
2. **Cinco veces por día** (12:07, 14:37, 17:07, 19:37 y 22:07, hora argentina) el workflow `Publicar novedad` lee los
   commits nuevos que ya estén **pusheados** a `master`, encola los marcados (`cola/cola.json`) y publica **uno**. Así
   nunca pasan de 5 por día y lo que sobra sale los días siguientes, sin perderse nada.
3. **Domingos a las 20:00**, `Resumen semanal` publica una tarjeta con todo lo de la semana y pushea una noticia a la
   web (`src/content/noticias/es/semana-AAAA-MM-DD.md`), que Cloudflare despliega sola (un build por semana).
4. El token de Instagram vence a los 60 días: `Renovar token de Instagram` lo renueva el 1 y el 15 de cada mes.

Las tarjetas (1080×1350) salen de `herramientas/tarjeta.py` con el emblema del logo, Cinzel y el oro del juego. Con
`Publicar-imagen` la captura va arriba, enmarcada. Las imágenes publicadas quedan en `imagenes/posts/` (Instagram
las baja de acá, por eso el repo es público).

**La categoría** (mapa, islas, ciudades, terreno, npcs, misiones, enemigos, combate, clases, personajes, monturas,
barcos, objetos, oficios, dioses, eventos, interfaz, multijugador, cuenta, rendimiento; la lista y las pistas para
deducirla están en `CATEGORIAS` y `PISTAS_CATEGORIA` de `redes.py`) va como un sello arriba a la izquierda de la
tarjeta y como una línea del epígrafe ("Categoría: Islas"). Queda anotada en la entrada de la cola (`categoria`).

**Video antes que el post**: si el commit todavía no está pusheado (no hay entrada en la cola), el video se arma igual
con el id que va a tener (`<sha de 10>-0`): `python herramientas/clip.py 4e3b0eb75c-0 puntinazo --titulo "…" --sin-cola`.
Al sincronizar, la entrada nueva lo toma sola.

**Ningún post sale sin su video**: el que todavía no lo tiene espera en la cola y sale el siguiente que sí (el log
del workflow los nombra: "Esperando su video"). La única excepción: si Instagram rechazó el video dos veces, el tercer
intento sale con la portada sola.

Por seguridad, cualquier frase que nombre a la IA se saca sola antes de publicar.

**El reloj** (`.github/workflows/reloj.yml`): los cron de GitHub no se disparan en este repo, así que un workflow espera
dormido hasta el próximo horario, lanza el que toque (publicar, resumen o token) y se vuelve a lanzar solo. Si la
cadena se cortara: Actions → Reloj → Run workflow. La publicación nunca saca dos posts con menos de 90 minutos entre
sí ni más de 5 por día, aunque se disparen dos cosas juntas.

## Videos: el carrusel portada + juego

Cada post sale como **carrusel**: la tarjeta de siempre y, deslizando, un **video corto del juego real** (~9 s, 4:5):
la toma en movimiento, el título arriba los primeros segundos, un pedazo de "Brisa del Mundo" de fondo y un cierre
con el emblema. Una novedad sin video sale con la portada sola.

1. **Grabar la toma** (en el repo del juego, con el editor cerrado). Las tomas son las de la prueba de fotos
   `capturas_redes.gd` (cada `_toca("nombre")`): la prueba `clips_redes.gd` las arma igual pero, donde saca la foto,
   graba la cámara moviéndose. Para una novedad nueva, se agrega su toma en `capturas_redes.gd` y sirve para las dos.
   ```powershell
   powershell -ExecutionPolicy Bypass -File herramientas\correr_headless.ps1 -Ventana -Segundos 1800 -MaxMB 3800 `
     -Argumentos "--fixed-fps 30 escenas/main.tscn -- --prueba=clips_redes --solo=bestiario"
   ```
   Los cuadros quedan en `%TEMP%\wop_headless\capturas\clips\<nombre de la foto>\`.
2. **Armar el video** (acá; la música se lee del repo del juego, que no es público):
   ```bash
   pip install imageio-ffmpeg pillow                 # una vez (o un ffmpeg del sistema)
   python herramientas/clip.py lote1-06 bestiario    # id de la cola + nombre de la toma
   ```
   Deja `videos/<id>.mp4` y lo anota en la entrada de la cola. Para un commit nuevo, el id es el que le pone la
   sincronización (`<sha de 10>-0`): si todavía no está en la cola, esperá a que la sincronice el próximo horario.
3. Commit y push de `videos/` y `cola/cola.json`. Instagram baja el video por jsDelivr (lo sirve como `video/mp4`).

`Verificar tokens` arma el carrusel de la próxima con video hasta dejarlo listo en Instagram, sin publicarlo: sirve
para probar un video nuevo. Si Instagram rechaza un video dos veces, el tercer intento sale con la portada sola.

## Puesta en marcha (una sola vez)

1. **Cuenta profesional**: en la app de Instagram → Configuración → Tipo de cuenta y herramientas → *Cambiar a cuenta
   profesional* → **Creador** (gratis, no pide página de Facebook).
2. **App de Meta** (con tu Facebook personal: nadie lo ve): [developers.facebook.com](https://developers.facebook.com)
   → *Crear app* → caso de uso **Administrar mensajes y contenido en Instagram** (filtro *Administración de
   contenido*) → *Personalizar* → **API setup with Unified login** (las apps nuevas ya no tienen "Instagram login").
   - Pide un **portfolio comercial** (gratis, Meta Business Suite): creá `World of Pieces` y, si lo pide, sumale la
     cuenta de Instagram como activo.
   - *Crear nueva configuración*: vencimiento del token **Nunca** (si lo ofrece), permisos `instagram_basic` +
     `instagram_content_publish`, URL de redirección `https://worldofpieces.pages.dev/` → *Usar esta configuración*.
   - *Generar tokens de acceso* → *Agregar cuenta* (invita a la cuenta como tester: aceptar en instagram.com →
     Configuración → Permisos de sitios web → Apps y sitios web → Invitaciones de tester) → **Generar token**. Se
     muestra UNA vez: va directo al secreto `IG_TOKEN`. Con la app en modo desarrollo alcanza (no hace falta revisión).
   - Si el token tiene vencimiento, anotá la fecha: se genera otro igual y se reemplaza el secreto.
3. **Token de GitHub** (fine-grained, en GitHub → Settings → Developer settings → Personal access tokens), con acceso a
   tres repos:
   - `world-of-pieces-link` (el juego): *Contents* **Read**.
   - `world-of-pieces-web`: *Contents* **Read and write**.
   - `world-of-pieces-redes` (este): *Secrets* **Read and write**.
   Vencimiento: el más largo que permita (y anotá cuándo vence).
4. En este repo → Settings → *Secrets and variables* → *Actions*:
   - Secretos: `IG_TOKEN` (paso 2) y `GH_PAT` (paso 3).
   - Variable `IG_USER_ID`: el id de la cuenta de Instagram que muestra el panel de Meta (si falta, se busca sola).
5. **Prender los workflows** (quedaron apagados hasta tener los secretos): Actions → cada uno de los tres → *Enable
   workflow*.
6. **Primera corrida**: Actions → *Publicar novedad* → *Run workflow* con "Solo probar" tildado. La primera vez solo
   anota el último commit del juego (no publica la historia vieja); desde ahí, todo commit marcado entra en la cola.

## A mano

```bash
python herramientas/redes.py publicar --seco      # arma la tarjeta y muestra el texto, sin publicar
python herramientas/redes.py resumen --web ../World-of-pieces-web --seco
```
Para sacar una novedad de la cola, en `cola/cola.json` cambiale `"estado"` a `"descartado"`. Las que fallaron 3 veces
quedan en `"error"` (con `ultimo_error`); volviéndolas a `"pendiente"` se reintentan.

Fuentes: Cinzel y Alegreya Sans, licencia SIL OFL (`recursos/fuentes/`).
