# CLAUDE.md — chatbot-mvp

Chatbot multi-tenant con widget embebible (Shadow DOM), panel admin y backend FastAPI.
Respuestas por intents configurables + fallback a IA vía OpenRouter.

## Estado
- **Fase:** MVP desplegado en staging, iterando features.
- **Producción:** `chatbot-stage.hubdpb.com` (Easypanel, proyecto `hub-stage`).
- **Documentación viva:** [docs/chatbot-mvp-lessons.md](docs/chatbot-mvp-lessons.md) — 18 problemas resueltos + 12 reglas. **Leer antes de tocar código nuevo.**

## Stack

| Capa | Tecnología |
|---|---|
| Runtime | Python 3.12 |
| API | FastAPI 0.115 + Uvicorn |
| ORM | SQLAlchemy 2.0 |
| DB prod | PostgreSQL compartido (`postgres-shared` en Easypanel) |
| DB local | SQLite (`backend/chatbot.db`) |
| IA | OpenAI SDK → OpenRouter (GPT-4o-mini, Gemini Flash, Claude) |
| Auth | JWT (python-jose HS256) + bcrypt |
| Widget | Vanilla JS + Shadow DOM, 0 deps |
| Admin | Vanilla HTML/CSS/JS (SPA de 1 `index.html`) |
| Contenedor | `python:3.12-slim`, puerto 8000 |

## Estructura

```
backend/app/
  main.py          # entrypoint uvicorn
  config.py        # settings (pydantic-settings)
  database.py      # SQLAlchemy engine + Session
  deps.py          # get_db, get_current_user
  models/          # Business, Intent, Conversation, Message, AdminUser, BusinessTranslation
  routers/         # chat, auth, business, intents, conversations, metrics
  schemas/         # Pydantic
  services/        # chat engine, intent matcher (fuzzy), AI service, translation service
  templates/       # landing pages (f-string, sin Jinja2)
widget/            # chat-widget.js + demo.html + test-host.html
admin/             # index.html (monolito)
flags/             # SVGs de idiomas (servidos estáticos)
```

## Decisiones arquitectónicas

- **Multi-tenancy:** una DB compartida, `business_id` como discriminador en cada tabla.
- **Widget isolation:** Shadow DOM obligatorio (el CSS del host rompía el widget — ver P10).
- **Migraciones:** ALTER TABLE idempotentes en startup, NO Alembic (pese a que la carpeta exista, no se usa).
- **Rate limiting:** in-memory (dict), sin Redis. Resetea al reiniciar.
- **Traducciones:** AI on-demand, no i18n estático. Una fila `BusinessTranslation` por idioma.
- **Landing pages:** server-rendered con f-strings, sin templating engine.

## Deploy

- **Easypanel:** proyecto `hub-stage`, servicio chatbot.
- **Health check:** `GET /health` (puerto 8000).
- **Build:** Docker multistage vía `Dockerfile` — copia `backend/`, `widget/`, `admin/`, `flags/` (CRÍTICO: si añades una carpeta estática nueva, añadirla al COPY — ver P01).
- **Env vars clave:** `DATABASE_URL`, `JWT_SECRET`, `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, `AI_MODEL`, `CORS_ORIGINS`.

## Reglas no negociables (resumidas de [docs/chatbot-mvp-lessons.md](docs/chatbot-mvp-lessons.md))

### Backend
- **FastAPI route order:** rutas literales (`/template.csv`, `/conflicts`, `/bulk`) SIEMPRE antes de `/{id}`. El orden de declaración = orden de matching (P07).
- **Foreign keys:** al crear un endpoint DELETE, listar TODAS las FK entrantes y decidir `ondelete` o hacer `SET NULL` manual en el código (P14).
- **Config defaults:** deben reflejar producción. Si prod es PostgreSQL, el default es PostgreSQL (P03).
- **Single source of truth:** un dato vive en una sola columna. Si duplicas por cache, documenta cuál es la primaria e invalida al escribir (P12).

### Widget
- **Shadow DOM siempre.** Nada de CSS sin aislamiento (P10).
- **`document.currentScript`** tiene fallback por `src` (compatible con async/defer — P09).
- **Fetches de config:** `cache: "no-store"` obligatorio (P15).
- **Sin XHR síncrono.** Siempre `await fetch` con `AbortController` (P08).
- **`[hidden] { display: none !important }`** en el scope, porque `display: flex` gana sobre `hidden` (P05).

### Admin
- **Todos los `querySelector` scopados** a un ID padre. Nunca `.lang-pane.active` global (P06).
- **`</script>` literal dentro de template literals → escaparlo como `<\/script>`** (P04).
- **Validar tipos antes de interpolar en strings.** Nunca concatenar un objeto directamente (P18).

### Flujos multi-idioma
- Cuando añadas un campo traducible, actualizar: modelo → prompt IA → UI admin → endpoint lectura → widget/landing. Probar end-to-end (R11).
- "Human approved" no se decide por un booleano; verificar que hay contenido real (P11).

### Intents
- Keywords validadas contra blacklist de stopwords (`de`, `que`, `para`, `hola`...) antes de crearse (R08, P17).
- Conflictos se hacen VISIBLES al usuario, no se resuelven con heurísticas en el matcher (P16).

## Checklist pre-deploy

```bash
grep -rn "localhost" widget/ admin/           # P02: no URLs absolutas
grep -rn "</script" admin/index.html          # P04: sin </script> sin escapar
docker build . --no-cache                     # P01: todas las COPY ok
curl http://localhost:8000/health             # endpoint responde
```

## Cómo arrancar en local

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # rellenar ANTHROPIC_API_KEY + JWT_SECRET
uvicorn app.main:app --reload --port 8000
```

Admin en `/admin`, demo widget en `/widget/demo.html`, Swagger en `/docs`.

## Contacto

- **Responsable:** Marta
- **Repo:** github.com/ray83mar81-hue/chatbot-mvp
