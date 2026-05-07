# Chatbot MVP — Lessons Learned

## 1. ESPECIFICACIONES

### Stack

| Capa | Tecnología | Versión |
|---|---|---|
| Runtime | Python | 3.12 |
| Framework API | FastAPI | 0.115.6 |
| ORM | SQLAlchemy | 2.0.36 |
| DB | PostgreSQL | compartida (postgres-shared en Easypanel) |
| IA (chat + traducciones) | OpenAI SDK → OpenRouter | openai 1.59.7 |
| Widget | Vanilla JS (Shadow DOM) | 0 dependencias |
| Admin panel | Vanilla HTML + CSS + JS | SPA en un solo index.html |
| Contenedor | Docker (python:3.12-slim) | Easypanel lo gestiona |
| Auth | JWT (python-jose) + bcrypt | HS256 |
| File upload | python-multipart | 0.0.20 |

### Dependencias clave (requirements.txt)

```
fastapi, uvicorn[standard], sqlalchemy, pydantic-settings,
python-jose[cryptography], bcrypt, anthropic, openai,
psycopg2-binary, python-multipart, python-dotenv,
email-validator, alembic, pytest, httpx
```

### Decisiones arquitectónicas

| Decisión | Elección | Razón |
|---|---|---|
| Multi-tenancy | Una DB compartida con `business_id` como discriminador | MVP rápido; migrar a DB-por-tenant si escala mucho |
| Widget isolation | Shadow DOM | CSS del host no afecta al widget; es lo que usan Intercom/Drift |
| IA provider | OpenAI SDK contra OpenRouter | Acceso a modelos baratos (GPT-4o-mini, Gemini Flash) sin lock-in |
| Auth | JWT stateless + bcrypt | Sin Redis necesario; el token lleva role + business_id |
| Traducciones | AI on-demand (no i18n estático) | El admin traduce con un clic; no hay archivos .po |
| Migraciones DB | Lightweight (ALTER TABLE en startup) | Sin Alembic para MVP; cada columna nueva se añade idempotentemente |
| Frontend admin | Monolito HTML vanilla | Evita build step, bundler, node_modules. Funciona en cualquier hosting estático |
| Rate limiting | In-memory (dict) | Sin Redis. Resetea al reiniciar. Suficiente para MVP |
| Landing pages | Server-rendered (f-string templates) | Sin Jinja2. Cambiable a templates si crece |

---

## 2. PROBLEMAS ENCONTRADOS

### P01 — Dockerfile no copiaba la carpeta flags/

**Qué pasó:** Las banderas SVG devolvían 404 en el widget porque `COPY flags/ ./flags/` faltaba en el Dockerfile. Solo se copiaban `backend/`, `widget/` y `admin/`.

**Cómo lo descubrí:** `curl -s -o /dev/null -w "%{http_code}" .../flags/es.svg` → 404.

**Cómo lo solucioné:** Añadí la línea COPY al Dockerfile.

**Regla para futuros:** Cada vez que se añade una carpeta nueva que se sirve como static files, hay que añadirla al Dockerfile Y verificar con curl que el servidor la sirve.

---

### P02 — Chrome "Private Network Access" por localhost hardcodeado

**Qué pasó:** `demo.html` tenía `http://localhost:8000` en los atributos del script. Al servir desde un dominio público, Chrome bloqueaba la petición con un popup de permisos.

**Cómo lo descubrí:** Popup visible al abrir demo.html en producción.

**Cómo lo solucioné:** Reemplacé URLs absolutas por rutas relativas (`/widget/chat-widget.js`). El widget ya tenía fallback a `window.location.origin`.

**Regla para futuros:** NUNCA usar `localhost` en archivos que se sirven en producción. Antes de deployar: `grep -rn "localhost" widget/ admin/`.

---

### P03 — SQLite como default de DATABASE_URL

**Qué pasó:** El default en `config.py` apuntaba a SQLite. Si alguien olvidaba configurar `DATABASE_URL` en Easypanel, la app arrancaba con SQLite en el filesystem efímero del container → datos perdidos al reiniciar.

**Cómo lo descubrí:** Revisión preventiva durante preparación del deploy.

**Cómo lo solucioné:** Cambié el default a `postgresql://user:pass@localhost:5432/chatbot` para que falle rápido si no se configura.

**Regla para futuros:** Los defaults de config deben reflejar el entorno de producción. Si necesitas PostgreSQL, el default debe ser PostgreSQL.

---

### P04 — `</script>` literal dentro de template literal JS

**Qué pasó:** Al generar el código embed inline, el template string contenía `></script>`. El parser HTML del navegador cerró el `<script>` del admin ahí → todo el JS posterior (incluido `handleLogin`) no se definió.

**Cómo lo descubrí:** Error en consola: `handleLogin is not defined`.

**Cómo lo solucioné:** Escapar la barra: `><\/script>`.

**Regla para futuros:** NUNCA escribir `</script>` literal dentro de un `<script>` inline. Usar siempre `<\/script>` o `<` + `/script>` concatenado.

---

### P05 — `hidden` attribute no funciona con `display: flex`

**Qué pasó:** El contacto del widget tenía `<button hidden>` pero la clase `.cw-header-btn` declaraba `display: flex` que ganaba sobre `hidden`. El botón de contacto era visible aunque `contact_form_enabled=false`.

**Cómo lo descubrí:** El usuario reportó que el formulario aparecía desactivado en admin pero visible en el widget.

**Cómo lo solucioné:** Regla CSS `.cw-root [hidden] { display: none !important; }`.

**Regla para futuros:** Si usas `display: flex/grid/inline-flex` en un elemento que puede llevar `[hidden]`, añadir siempre `[hidden] { display: none !important }` en el scope.

---

### P06 — Selector de intent panes no scoped

**Qué pasó:** `captureCurrentTab()` usaba `document.querySelector('.lang-pane.active')` global, que matcheaba el pane activo de otra sección (Negocio/Widget/Contacto) en vez del de Intents.

**Cómo lo descubrí:** Navegación entre idiomas en intents no funcionaba.

**Cómo lo solucioné:** Cambié a `document.querySelector('#intentLangPanes .lang-pane.active')`.

**Regla para futuros:** Todos los `querySelector` en el admin deben estar scopados al contenedor de su sección (usando un ID padre). Nunca usar selectores globales de clase.

---

### P07 — FastAPI route order: static vs dynamic paths

**Qué pasó:** `GET /intents/template.csv` estaba definido DESPUÉS de `GET /intents/{intent_id}`. FastAPI intentaba parsear `"template.csv"` como int → 422.

**Cómo lo descubrí:** El botón "Descargar plantilla" devolvía error.

**Cómo lo solucioné:** Mover las rutas estáticas (`/template.csv`, `/conflicts`, `/bulk`) ANTES de `/{intent_id}`.

**Regla para futuros:** En FastAPI, SIEMPRE declarar rutas con path literal antes de rutas con path parameters dinámicos. Orden de declaración = orden de matching.

---

### P08 — XHR síncrono bloqueaba la web del cliente

**Qué pasó:** El widget hacía un `XMLHttpRequest` síncrono al arrancar para obtener el diseño antes de inyectar CSS. Esto bloqueaba el hilo principal del host (~100-300ms) y Chrome mostraba un warning deprecation.

**Cómo lo descubrí:** Test-host.html + Chrome DevTools warnings.

**Cómo lo solucioné:** Refactor a `async function()` IIFE + `await fetch()` con `AbortController` timeout de 2s. El CSS se construye DESPUÉS del fetch, no antes.

**Regla para futuros:** NUNCA usar XMLHttpRequest síncrono. Siempre fetch async. Si necesitas datos antes de renderizar, usa await al inicio del IIFE.

---

### P09 — `document.currentScript` null con async/defer

**Qué pasó:** Cuando el host cargaba el widget con `<script async>` o `<script defer>`, `document.currentScript` era null. CONFIG se inicializaba con defaults vacíos → widget sin colores ni business_id correctos.

**Cómo lo descubrí:** Test-host.html con `?async=1` y `?defer=1`.

**Cómo lo solucioné:** Fallback `_findScript()` que busca el script por su `src` attribute: `document.querySelectorAll('script[src*="chat-widget.js"]')`.

**Regla para futuros:** No depender de `document.currentScript`. Siempre tener un fallback por `src` para scripts embebibles.

---

### P10 — CSS del host rompía el widget

**Qué pasó:** Test-host.html demostró que `button { background: red !important }` del host pisaba el estilo de `.cw-bubble`. Nuestras clases `.cw-*` no ganaban contra `!important` en selectores de tag.

**Cómo lo descubrí:** Visual en test-host.html: burbuja roja con borde morado.

**Cómo lo solucioné:** Refactor completo a Shadow DOM. El widget ahora vive dentro de `host.attachShadow({mode: "open"})`. CSS del host no puede entrar.

**Regla para futuros:** Todo widget embebible en webs de terceros DEBE usar Shadow DOM. Es la única forma de garantizar aislamiento CSS bidireccional.

---

### P11 — Traducciones AI vacías por "human approved" erróneo

**Qué pasó:** Al guardar el formulario de contacto se creaba una fila `BusinessTranslation` con `auto_translated=False, needs_review=False` pero campos principales vacíos. Después, al correr "Traducir con IA", el servicio las consideraba "aprobadas por humano" y las saltaba.

**Cómo lo descubrí:** Tras traducir, los campos de negocio en CA/FR aparecían en blanco.

**Cómo lo solucioné:** La check de "human approved" ahora requiere que `name` o `description` tengan contenido real. Filas vacías no bloquean.

**Regla para futuros:** Un flag booleano (`auto_translated=False`) no es suficiente para determinar "aprobado". Siempre verificar que hay contenido real antes de decidir no sobreescribir.

---

### P12 — Welcome message en dos sitios (Business vs BusinessTranslation)

**Qué pasó:** `Business.welcome_messages` (JSON) y `BusinessTranslation.welcome` (columna) almacenaban el mismo dato sin sincronización. Tras traducir con IA, el widget mostraba el mensaje viejo porque leía de `Business.welcome_messages`.

**Cómo lo descubrí:** Audit del flujo multi-idioma.

**Cómo lo solucioné:** Después de cada traducción IA, el servicio sincroniza los welcomes en `Business.welcome_messages`. `saveWidgetTexts` del admin también escribe en ambos sitios.

**Regla para futuros:** Un dato debe tener UNA fuente de verdad. Si existe en dos tablas, documentar cuál es la primaria y mantener sync automatizado. Mejor: eliminar la duplicación.

---

### P13 — Formulario de contacto no se traducía con IA

**Qué pasó:** `translateAll()` en el admin rellenaba los textos del formulario de contacto con defaults hardcodeados (I18N_CONTACT) en vez de llamar a la IA. Los textos custom del admin se sobrescribían con traducciones genéricas.

**Cómo lo descubrí:** Audit del flujo multi-idioma.

**Cómo lo solucioné:** Extendí el prompt de `business_translation_service` para incluir `contact_texts` como campo a traducir. El admin lee las traducciones AI del response en vez de usar defaults.

**Regla para futuros:** Cuando un flujo "traduce todo", verificar que REALMENTE traduce TODO. Listar los campos al inicio y cruzar con el prompt de traducción.

---

### P14 — Foreign key bloquea DELETE de intents

**Qué pasó:** `Message.intent_matched_id` referencia `intents.id` sin `ondelete`. Al borrar intents que habían matcheado mensajes históricos → FK violation → 500.

**Cómo lo descubrí:** Error 500 al usar "Borrar todos los intents".

**Cómo lo solucioné:** Antes de borrar, pongo `intent_matched_id = NULL` en los mensajes afectados. Aplicado tanto al delete individual como al bulk.

**Regla para futuros:** Antes de crear un endpoint DELETE, verificar TODAS las foreign keys que apuntan al modelo. Añadir `ondelete="SET NULL"` o `"CASCADE"` según el caso. Si el modelo ya existe sin eso, hacer el NULL manualmente en el código del delete.

---

### P15 — Browser cache servía diseño viejo del widget

**Qué pasó:** Admin guardaba nuevo diseño. Widget en preview.html mostraba el viejo. El backend tenía los datos nuevos (confirmado con curl) pero el browser cacheaba la respuesta de `/business/1/languages`.

**Cómo lo descubrí:** El usuario reportó "no guarda los cambios".

**Cómo lo solucioné:** `cache: "no-store"` en el fetch del widget al arrancar.

**Regla para futuros:** Endpoints que devuelven configuración mutable deben servirse con `Cache-Control: no-store` en el header, O el cliente debe pedirlos con `cache: "no-store"`. Especialmente importante para widgets embebidos donde no controlas el entorno.

---

### P16 — Conflictos de keywords entre intents (caso paella)

**Qué pasó:** Intent "arroces" con keyword `paella` e intent "encargar_paella" con keyword `encargar paella`. Cuando el usuario escribía "quiero encargar una paella", la palabra "una" rompía el substring match de "encargar paella" y solo matcheaba "paella" del intent genérico.

**Cómo lo descubrí:** Caso de estudio real del usuario con capturas de pantalla.

**Cómo lo solucioné:** En vez de hacer el matcher más "inteligente", hice los conflictos visibles: endpoint `/intents/conflicts` detecta duplicados y substrings, banner de conflictos en la UI con las keywords top implicadas, badges rojos en la tabla y en el editor de chips.

**Regla para futuros:** No resolver problemas de diseño de datos con heurísticas de matching. Hacer que los errores de diseño sean VISIBLES para el usuario. El conflicto es del dato, no del algoritmo.

---

### P17 — Import CSV con keywords genéricas generó 480 conflictos

**Qué pasó:** El usuario importó un CSV con keywords tipo "de", "que", "para" — preposiciones que aparecen en cualquier frase. Cada intent conflictaba con todos los demás.

**Cómo lo descubrí:** Banner de conflictos mostraba 480 conflictos tras importar.

**Cómo lo solucioné:** Botón "Borrar todos" con type-to-confirm. Banner mejorado con top keywords implicadas + recomendación nuclear si >50 conflictos. Prompt de generación de intents con blacklist de palabras genéricas.

**Regla para futuros:** El CSV de import debería validar keywords contra una blacklist de stopwords ANTES de crear los intents. O al menos mostrar un warning pre-import.

---

### P18 — Información del negocio mostraba `[object Object]` en el prompt

**Qué pasó:** El campo `schedule` contenía JSON anidado (`{"horarios": {"lunes": "9-18"}}`). El código hacía `Object.entries(sch).map(...)` y el value era un objeto, no un string.

**Cómo lo descubrí:** El usuario reportó texto roto en el modal de "Generar con IA externa".

**Cómo lo solucioné:** Helper `_formatSchedule()` que desempaqueta un nivel si detecta un solo entry que es objeto, y stringify recursivo para nested objects.

**Regla para futuros:** Nunca concatenar un objeto directamente en un string. Siempre `JSON.stringify()` o formatear explícitamente. Validar tipos de datos antes de interpolar.

---

### P19 — `NameError: timedelta` rompió `/chat` durante 7 días sin que nadie lo viese

**Qué pasó:** El commit `d507a8c` (30/4/2026, "Conversation retention: auto-archive at 30d idle") añadió `timedelta(days=AUTO_ARCHIVE_DAYS)` en `chat_engine._get_or_create_conversation()` pero olvidó añadir `timedelta` al `from datetime import datetime, timezone`. Cada llamada a `POST /chat/message` y `POST /chat/stream` levantaba `NameError: name 'timedelta' is not defined` desde ese commit. En streaming el síntoma cara al cliente era `ERR_HTTP2_PROTOCOL_ERROR` (la excepción cierra el stream a medias y Traefik lo reporta como protocol error sobre HTTP/2). En el endpoint no-streaming era 500 limpio. **Ningún tenant pudo chatear desde el 30/4 hasta el 7/5.**

**Cómo lo descubrí:** El usuario probó el bot recién desplegado en staging, vio "Hi ha hagut un error de connexió" en la burbuja, y reportó. Confirmado mirando los logs de Easypanel — había una traza Python por cada mensaje enviado.

**Cómo lo solucioné:** Una línea — añadir `timedelta` al import (commit `bd4b143`).

**Por qué nadie lo vio antes:** El repo no tenía linter, ni pre-commit, ni CI, ni smoke test, ni monitor externo. El commit pasó directo a `main`, Easypanel auto-desplegó, y como nadie chateó en staging durante días el bug pasó silencioso. Cuando alguien probó el chat, fallaba.

**Regla para futuros:** ver R13.

---

### P20 — Traducción de negocio fallaba con "Unterminated string" desde abril por `max_tokens` insuficiente + UI mostraba modelo equivocado

**Qué pasó:** El endpoint `POST /business/{id}/translate` llamaba a `chat_json(..., max_tokens=2000, business=business)`. Con prompts largos (un `extra_info` de ~5000 palabras como el del Assistent Digital), el modelo escribía la respuesta JSON, llegaba al límite de 2000 tokens de salida, y se cortaba a media palabra → JSON no parseable, error `AI response was not valid JSON: Unterminated string starting at: line 6 column 1...`. El admin veía "Error al traducir: Error" sin más pista. El bug llevaba semanas: incidencias del 23/4 (Comidas La Cartoixa #2), 5/5 y 7/5 (Assistent Digital #3) registran exactamente el mismo síntoma.

Encima, la línea "Precios usados: openai/gpt-4o-mini — input $0.15/M, output $0.6/M" del panel de plataforma confundía al operador: es un dump del endpoint `/superadmin/pricing` que devuelve **siempre la config GLOBAL** (env vars), incluso cuando se está viendo un tenant que tiene config per-tenant distinta (Haiku 4.5 por OpenRouter en este caso). Un cliente podía configurar su propia IA y la UI seguía diciendo que se usaba la global.

**Cómo lo descubrí:** Marta creó el primer tenant con un prompt largo (Assistent Digital), intentó traducir desde el panel de Idiomas, vio "Error al traducir: Error", y revisó el panel de incidencias. La incidencia con el JSON truncado dio la pista, y el código revelaba el `max_tokens=2000` hardcoded.

**Cómo lo solucioné:**
1. `max_tokens` subido de 2000 → 16000 en `business_translation_service.py`. Haiku 4.5 acepta 64k de output, así que 16k da margen para 5+ idiomas largos en una sola llamada sin coste runaway (Haiku son $5/M output, ~$0.08 por traducción completa de 16k tokens).
2. `/superadmin/pricing` ahora acepta `?business_id=X` opcional. Sin parámetro, devuelve la config global como antes (compatibilidad). Con parámetro, resuelve la config efectiva del tenant (per-tenant si la tiene, fallback global). El admin frontend puede usarlo para mostrar precios reales en vistas per-tenant.
3. Relabeled la línea "Precios usados" → "Modelo y precios por defecto del sistema (env globales)" en el panel de plataforma para que el operador no asuma que son los precios usados realmente.

**Regla para futuros:**

- **`max_tokens` en cualquier llamada a la IA debe escalar con el tamaño esperado de la entrada.** Hardcodear un número pequeño porque "los prompts de prueba eran cortos" es una bomba de relojería en cuanto un cliente real pega un prompt grande. Siempre dejar el límite con holgura ≥3× el peor caso conocido y comentar el porqué.
- **Cuando un dato existe en dos niveles (global + per-tenant), la UI tiene que ser clara sobre cuál está mostrando.** "Precios usados" sin contexto es ambiguo; "precios por defecto del sistema" o "precios efectivos de este tenant" no lo son.
- **JSON parse errors de respuestas AI casi siempre son truncamiento por `max_tokens`.** Antes de tocar el parser, mirar el `finish_reason` y el límite. (TODO: añadir log de `finish_reason` en `chat_json` para que la incidencia diga "truncado" en vez de un parse error genérico.)

---

## 3. REGLAS PARA FUTUROS

### R01 — Checklist pre-deploy
Antes de cada push a producción:
```bash
grep -rn "localhost" widget/ admin/
grep -rn "</script" admin/index.html  # sin escapar
docker build . --no-cache             # todas las COPY ok
curl /health                          # endpoint responde
```

### R02 — FastAPI route order
Rutas estáticas (`/template.csv`, `/conflicts`, `/bulk`) SIEMPRE antes de rutas dinámicas (`/{id}`). Comentar en el código por qué.

### R03 — Foreign keys
Al crear un modelo con FK: decidir `ondelete` (SET NULL o CASCADE) en el momento de la creación, no después. Al crear un endpoint DELETE: listar TODAS las FK entrantes.

### R04 — Single source of truth
Un dato vive en UN sitio. Si necesitas cache, la cache se invalida al escribir. Documentar cuál es la tabla primaria.

### R05 — Widget embed robustness
- Shadow DOM obligatorio
- `document.currentScript` con fallback por `src`
- `document.body` readiness check (DOMContentLoaded)
- `cache: "no-store"` en fetches de configuración
- No `XMLHttpRequest` síncrono
- Test contra `test-host.html` antes de cada release

### R06 — CSS `[hidden]` rule
Si el widget usa `display: flex/grid` en elementos que pueden llevar `[hidden]`, añadir `[hidden] { display: none !important }` al scope.

### R07 — Admin querySelector scope
Todos los `querySelector` en admin deben estar scopados a un contenedor con ID. Nunca `.lang-pane.active` global.

### R08 — Blacklist de stopwords en keywords de intents
Antes de crear un intent (manual, CSV o plantilla), validar keywords contra esta lista:
```
de, a, en, con, por, para, sobre, y, o, que, si, como, cuando, donde,
hola, buenos, buenas, yo, tú, me, mi, tu, tener, querer, saber, poder, hacer
```

### R09 — Config defaults = producción
`config.py` defaults deben reflejar el entorno real. Si necesitas PostgreSQL en prod, el default es PostgreSQL. Fail fast > fail silent.

### R10 — Test de aislamiento antes de vender
Antes de onboardear un cliente nuevo, abrir `/widget/test-host.html` y verificar:
- Widget se ve bien con CSS agresivo del host
- Funciona con async, defer, head
- Consola limpia (sin warnings propios)
- Network: una sola petición a languages, no duplicada

### R11 — Traducciones end-to-end
Cada vez que se añade un campo traducible:
1. Añadirlo al modelo BusinessTranslation (o al que toque)
2. Incluirlo en el prompt de traducción AI
3. Incluirlo en el UI de traducción del admin
4. Incluirlo en la respuesta del endpoint que lee traducciones
5. Incluirlo en el widget / landing que lo renderiza
6. Probar: cambiar en admin → traducir → ver en widget en otro idioma

### R12 — Documentar el "por qué" de cada hack
Si algo se hace de forma no-obvia (sync XHR, doble storage, skip de rows), comentar en el código POR QUÉ. El "qué" se lee; el "por qué" se pierde.

### R13 — Defensa por capas contra regresiones (ver P19)

**Capa 1 — Linter en CI (obligatoria, montada el 7/5/2026):**
- `pyproject.toml` con `ruff` configurado: reglas `F` (Pyflakes — `F821 undefined-name` habría cazado P19), `E9` (errores de sintaxis), `B` (bugbear), `I` (orden de imports).
- `.github/workflows/ci.yml` corre `ruff check .` en cada push y PR.
- Si la build sale roja (❌ en GitHub), **no redeployar ese commit en Easypanel**. Easypanel todavía despliega de `main` directamente, así que el rojo de CI es la única señal de stop.
- Para correr local antes de commitear: `pip install ruff==0.15.12 && ruff check .`

**Capa 2 — Smoke test (pendiente):**
- `pytest backend/tests/test_chat_smoke.py` que arranca FastAPI con SQLite en memoria y un mock de la AI, pega a `POST /chat/message`, asserta 200. Se añade al mismo workflow tras `ruff check`.

**Capa 3 — Monitor externo (pendiente):**
- UptimeRobot / BetterStack pegando a `/health` y a `/chat/message` cada 5 min. Alerta por email + SMS si falla 2 veces seguidas. Es la única red que detecta bugs ya en producción que el linter no cazó.

**Capa 4 — Política de despliegue (cuando haya clientes en producción):**
- `main` → staging automático.
- Tag `release-*` → producción manual.
- Nunca redeployar un commit con CI roja.

**Reglas operativas:**
- Toda regla de bug-class (`F821`, `F811`, `F501`, `E9*`) en `[tool.ruff.lint]` está prohibida silenciar sin escribir el motivo en el `pyproject.toml`. Las reglas estilísticas (`E501`, etc.) sí se pueden ignorar libremente.
- Cualquier nueva categoría de bug que llegue a producción merece nueva entrada Pxx aquí, y, si es posible cazarla con un linter, una regla nueva en `pyproject.toml`. Las defensas se construyen incidente a incidente.

---

**Documento generado:** abril 2026
**Última actualización:** mayo 2026 (P19, R13)
**Proyecto:** chatbot-mvp
**Entorno:** hub-stage (chatbot-stage.hubdpb.com)
