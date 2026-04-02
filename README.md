# Chatbot MVP

Chatbot inteligente para negocios con panel de administracion. Los clientes chatean desde un widget embebible, las respuestas vienen de intents configurables o de Claude AI como fallback.

## Arquitectura

```
chatbot-mvp/
├── backend/          FastAPI (Python)
│   ├── app/
│   │   ├── routers/  Endpoints: chat, auth, business, intents, conversations, metrics
│   │   ├── services/ Chat engine, AI service (Claude), intent matcher (fuzzy)
│   │   ├── models/   SQLAlchemy: Business, Intent, Conversation, Message, AdminUser
│   │   └── schemas/  Pydantic validation
│   └── requirements.txt
├── widget/           Chat widget embebible (vanilla JS)
│   ├── chat-widget.js
│   └── demo.html
├── admin/            Panel de administracion (vanilla JS)
│   └── index.html
├── Dockerfile
└── docker-compose.yml
```

## Funcionalidades

- **Chat widget** embebible con una linea de codigo `<script>`
- **Streaming** de respuestas IA en tiempo real (SSE)
- **Intent matching** con fuzzy matching (tolera errores tipograficos)
- **Fallback a Claude AI** cuando no hay intent, con contexto del negocio
- **Panel admin**: dashboard con metricas, CRUD de intents, visor de conversaciones, editor de negocio, generador de codigo embed
- **Autenticacion JWT** para administradores
- **API REST** documentada en `/docs` (Swagger)

## Setup rapido

### 1. Clonar e instalar

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Editar .env con tu API key
```

### 2. Arrancar

```bash
uvicorn app.main:app --reload --port 8000
```

### 3. Crear usuario admin

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"tu-password","business_id":1}'
```

### 4. Acceder

| URL | Descripcion |
|-----|-------------|
| http://localhost:8000/admin | Panel de administracion |
| http://localhost:8000/widget/demo.html | Demo del widget |
| http://localhost:8000/docs | API docs (Swagger) |

## Docker

```bash
docker compose up --build
```

## Integrar el widget

Pega esto antes de `</body>` en tu web:

```html
<script
  src="https://tu-servidor.com/widget/chat-widget.js"
  data-api-url="https://tu-servidor.com"
  data-business-id="1"
  data-title="Chat"
  data-primary-color="#2563eb"
></script>
```

O usa el generador de codigo en Admin > Integrar.

## API Endpoints

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| POST | /chat/message | Enviar mensaje (respuesta completa) |
| POST | /chat/stream | Enviar mensaje (streaming SSE) |
| POST | /auth/register | Crear cuenta admin |
| POST | /auth/login | Iniciar sesion |
| GET | /business/{id} | Datos del negocio |
| PUT | /business/{id} | Actualizar negocio |
| GET | /intents/ | Listar intents |
| POST | /intents/ | Crear intent |
| PUT | /intents/{id} | Editar intent |
| DELETE | /intents/{id} | Borrar intent |
| GET | /conversations/ | Listar conversaciones |
| GET | /conversations/{id} | Detalle de conversacion |
| GET | /metrics/ | Metricas del chatbot |

## Stack

- **Backend**: FastAPI, SQLAlchemy, SQLite, Anthropic SDK
- **Frontend**: Vanilla JS (sin frameworks)
- **IA**: Claude via Anthropic API o OpenRouter
- **Auth**: JWT con bcrypt
- **Deploy**: Docker
