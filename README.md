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
   ```
   Los commits sin `Publicar:` no se publican nunca. Un commit puede traer varias novedades.
2. **Cinco veces por día** (12:00, 14:30, 17:00, 19:30 y 22:00, hora argentina) el workflow `Publicar novedad` lee los
   commits nuevos que ya estén **pusheados** a `master`, encola los marcados (`cola/cola.json`) y publica **uno**. Así
   nunca pasan de 5 por día y lo que sobra sale los días siguientes, sin perderse nada.
3. **Domingos a las 20:00**, `Resumen semanal` publica una tarjeta con todo lo de la semana y pushea una noticia a la
   web (`src/content/noticias/es/semana-AAAA-MM-DD.md`), que Cloudflare despliega sola (un build por semana).
4. El token de Instagram vence a los 60 días: `Renovar token de Instagram` lo renueva el 1 y el 15 de cada mes.

Las tarjetas (1080×1350) salen de `herramientas/tarjeta.py` con el emblema del logo, Cinzel y el oro del juego. Con
`Publicar-imagen` la captura va arriba, enmarcada. Las imágenes publicadas quedan en `imagenes/posts/` (Instagram
las baja de acá, por eso el repo es público).

Por seguridad, cualquier frase que nombre a la IA se saca sola antes de publicar.

## Puesta en marcha (una sola vez)

1. **Cuenta profesional**: en la app de Instagram → Configuración → Tipo de cuenta y herramientas → *Cambiar a cuenta
   profesional* → **Creador** (gratis, no pide página de Facebook).
2. **App de Meta** (puede ser la misma que use el feed de la web): [developers.facebook.com](https://developers.facebook.com)
   → *Create app* → tipo *Business* → producto **Instagram** → *API setup with Instagram login*.
   - En *Roles* agregá tu cuenta de Instagram como **Instagram tester** y aceptá la invitación desde la app de
     Instagram (Configuración → Apps y sitios web). Con la app en modo desarrollo y vos como tester, no hace falta la
     revisión de Meta.
   - En *Generate access tokens* agregá la cuenta con los permisos `instagram_business_basic` y
     `instagram_business_content_publish` y copiá el token (es el largo, de 60 días).
3. **Token de GitHub** (fine-grained, en GitHub → Settings → Developer settings → Personal access tokens), con acceso a
   tres repos:
   - `world-of-pieces-link` (el juego): *Contents* **Read**.
   - `world-of-pieces-web`: *Contents* **Read and write**.
   - `world-of-pieces-redes` (este): *Secrets* **Read and write**.
   Vencimiento: el más largo que permita (y anotá cuándo vence).
4. En este repo → Settings → *Secrets and variables* → *Actions*:
   - Secretos: `IG_TOKEN` (paso 2) y `GH_PAT` (paso 3).
   - Variable opcional: `IG_USER_ID` (si no está, se consulta sola).
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
