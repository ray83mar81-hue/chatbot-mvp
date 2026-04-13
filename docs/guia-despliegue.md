# Guia de despliegue en VPS (Easypanel + hubdpb.com)

Checklist reutilizable para desplegar este proyecto (o similar) en el VPS de Contabo con Easypanel.

**Infraestructura:** VPS Contabo (24 GB RAM) con Easypanel Free (3 proyectos).
**Proyectos Easypanel:** `hub-core` (infra compartida), `hub-stage` (staging), `hub-prod` (produccion).
**Postgres:** instancia unica `postgres-shared` en `hub-core`, una DB por servicio.

---

## 1. Preparar el codigo

### 1.1 Dockerfile

Asegurate de que el Dockerfile:
- Copia **todas** las carpetas necesarias (backend, widget, admin, flags, etc.)
- Expone el puerto correcto (`EXPOSE 8000`)
- Incluye `HEALTHCHECK` (convencion del servidor)

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY widget/ ./widget/
COPY admin/ ./admin/
COPY flags/ ./flags/

WORKDIR /app/backend

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 1.2 .dockerignore

Excluir todo lo que no necesita el contenedor:

```
n8n-mcp/
**/__pycache__/
**/*.pyc
*.db
.env
.git/
.gitignore
.claude/
*.md
docker-compose.yml
.vscode/
.idea/
venv/
.venv/
```

### 1.3 Dependencias para PostgreSQL

Si el proyecto usa Python + SQLAlchemy, asegurate de incluir el driver:

```
# requirements.txt
psycopg2-binary==2.9.10
```

### 1.4 URLs relativas en frontend

**Nunca** usar `localhost` en archivos que se sirven en produccion. Usar rutas relativas o `window.location.origin`:

```html
<!-- MAL -->
<script src="http://localhost:8000/widget/chat-widget.js"></script>

<!-- BIEN -->
<script src="/widget/chat-widget.js"></script>
```

### 1.5 Verificar endpoint /health

Convencion del servidor: todo servicio debe tener un healthcheck. Verificar que existe:

```python
@app.get("/health")
def health():
    return {"status": "ok"}
```

---

## 2. Subir a GitHub

```bash
# Renombrar rama si es necesario (convencion: main)
git branch -m master main

# Commit y push
git add .
git commit -m "Prepare for VPS deployment"
git push -u origin main

# Si habia rama master en remoto:
gh repo edit --default-branch main
git push origin --delete master
```

**Convencion:** la rama por defecto es siempre `main`.

---

## 3. Crear base de datos en postgres-shared

Acceder a **pgAdmin** (`pgadmin.hubdpb.com`) conectado a `postgres-shared`.

### Convencion de naming

| Elemento | Patron | Ejemplo |
|---|---|---|
| DB staging | `{producto}_stage` | `chatbotmvp_stage` |
| DB produccion | `{producto}_{cliente}` | `chatbotmvp_acme` |
| Usuario DB | `{db}_user` | `chatbotmvp_stage_user` |

### SQL de provisioning

```sql
CREATE USER chatbotmvp_stage_user WITH PASSWORD '<password-seguro>';
CREATE DATABASE chatbotmvp_stage
  OWNER chatbotmvp_stage_user
  ENCODING 'UTF8'
  TEMPLATE template0;
REVOKE CONNECT ON DATABASE chatbotmvp_stage FROM PUBLIC;
GRANT CONNECT ON DATABASE chatbotmvp_stage TO chatbotmvp_stage_user;
GRANT ALL PRIVILEGES ON DATABASE chatbotmvp_stage TO chatbotmvp_stage_user;
```

---

## 4. Google OAuth (si aplica)

Si el proyecto usa Google OAuth (por ejemplo con Better-Auth):

1. Ir a [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Crear credenciales OAuth 2.0
3. Agregar URIs de redireccion autorizados:
   - `https://{servicio}-stage.hubdpb.com/api/auth/callback/google` (staging)
   - `https://{servicio}.hubdpb.com/api/auth/callback/google` (produccion)
4. Copiar `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET`
5. Configurar como variables de entorno en Easypanel

---

## 5. Crear servicio en Easypanel

### 5.1 Acceder al panel

Ir a `easy.hubdpb.com` > seleccionar proyecto (`hub-stage` o `hub-prod`).

### 5.2 Crear servicio

1. **New Service** > **App**
2. **Source:** GitHub
3. **Repository:** `ray83mar81-hue/{repo-name}`
4. **Branch:** `main`
5. **Build method:** Dockerfile (deteccion automatica)

### 5.3 Convencion de naming para servicios

| Entorno | Nombre servicio | Subdominio |
|---|---|---|
| Staging | `{producto}-stage` | `{producto}-stage.hubdpb.com` |
| Produccion | `{producto}` o `{producto}-web` | `{producto}.hubdpb.com` |

### 5.4 Recursos

| Entorno | Memory limit | CPU shares |
|---|---|---|
| Staging | 384 MB | 512 |
| Produccion | 512 MB | 2048 |

---

## 6. Variables de entorno

Configurar en Easypanel > servicio > **Environment**.

### Hostname cross-project (IMPORTANTE)

Cuando un servicio necesita conectar con otro servicio **de otro proyecto** en Easypanel, el hostname sigue este patron:

```
{proyecto}_{servicio}
```

Con **underscore**, no guion. Ejemplos:

| Destino | Proyecto | Servicio | Hostname interno |
|---|---|---|---|
| PostgreSQL | hub-core | postgres-shared | `hub-core_postgres-shared` |
| Redis | hub-core | redis-shared | `hub-core_redis-shared` |

> **Dentro del mismo proyecto** se usa el nombre del servicio directamente: `postgres-shared`.
> **Cross-project** se usa `{proyecto}_{servicio}`.

### Variables tipicas para este chatbot

```env
# === Database ===
DATABASE_URL=postgresql://chatbotmvp_stage_user:<password>@hub-core_postgres-shared:5432/chatbotmvp_stage

# === AI Provider ===
ANTHROPIC_API_KEY=sk-or-v1-xxxx
ANTHROPIC_BASE_URL=https://openrouter.ai/api
AI_MODEL=anthropic/claude-sonnet-4

# === Auth ===
JWT_SECRET=<openssl rand -base64 32>

# === CORS ===
CORS_ORIGINS=https://chatbot-stage.hubdpb.com

# === GDPR ===
IP_HASH_SALT=<openssl rand -base64 16>
```

### Generar secretos seguros

```bash
# JWT_SECRET
openssl rand -base64 32

# IP_HASH_SALT
openssl rand -base64 16

# Password de DB
openssl rand -base64 24
```

---

## 7. Dominio y SSL

En Easypanel > servicio > **Domains**:

1. Agregar dominio: `{producto}-stage.hubdpb.com`
2. SSL: **Let's Encrypt** (HTTP-01 challenge)
3. Verificar que existe registro DNS en Cloudflare:
   - Tipo: `A`
   - Nombre: el subdominio o wildcard `*`
   - IP: `45.85.249.168`
   - Proxy: **DNS only** (gris) mientras se use HTTP-01

> Si el subdominio no esta como registro A explicito, funciona el wildcard `*.hubdpb.com`.

---

## 8. Deploy y verificacion

### 8.1 Desplegar

En Easypanel > servicio > **Deploy**. Si hay auto-deploy configurado con GitHub, basta con hacer push.

### 8.2 Verificar

| Check | URL | Esperado |
|---|---|---|
| Raiz | `https://{subdominio}/` | JSON con info de la app |
| Health | `https://{subdominio}/health` | `{"status": "ok"}` |
| API docs | `https://{subdominio}/docs` | Swagger UI |
| Admin | `https://{subdominio}/admin` | Panel de admin |
| Widget | `https://{subdominio}/widget/demo.html` | Demo del widget |

### 8.3 Crear usuario admin

```bash
curl -X POST https://{subdominio}/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@hubdpb.com","password":"<password>","business_id":1}'
```

### 8.4 Verificar logs

En Easypanel > servicio > **Logs**, o en `logs.hubdpb.com` (Dozzle).

---

## 9. Errores comunes y soluciones

| Error | Causa | Solucion |
|---|---|---|
| `Connection refused` a PostgreSQL | Hostname incorrecto | Usar `hub-core_postgres-shared` (cross-project) en vez de `postgres-shared` o `localhost` |
| 404 en archivos estaticos (flags, widget) | Falta `COPY` en Dockerfile | Verificar que **todas** las carpetas estan en el Dockerfile |
| Chrome pide permiso "acceder a dispositivos" | URLs `localhost` hardcodeadas en frontend | Usar rutas relativas (`/widget/...`) en vez de `http://localhost:8000/...` |
| SSL no se genera | DNS no apunta al VPS | Verificar registro A en Cloudflare, proxy en modo DNS only (gris) |
| Container se reinicia en loop | OOM (memoria) | Subir `mem_limit` o revisar memory leaks en logs |
| `password authentication failed` | Usuario/password DB incorrectos | Verificar credenciales en pgAdmin, recrear usuario si es necesario |
| Build falla por dependencias | Falta driver de DB | Asegurar `psycopg2-binary` en requirements.txt |
| CORS bloqueado | `CORS_ORIGINS` mal configurado | Poner el dominio exacto con `https://`, sin trailing slash |
| Health check failing | Endpoint `/health` no existe o app no arranca | Revisar logs del contenedor, verificar que la app levanta en el puerto correcto |
| `ModuleNotFoundError` en container | Carpeta no copiada o WORKDIR incorrecto | Verificar estructura de COPY y WORKDIR en Dockerfile |

---

## 10. Convenciones de naming (resumen)

| Elemento | Patron | Ejemplo |
|---|---|---|
| Rama Git | `main` | `main` |
| Servicio staging | `{producto}-stage` | `chatbot-stage` |
| Servicio produccion | `{producto}-web` o `{producto}` | `chatbot-web` |
| Subdominio staging | `{producto}-stage.hubdpb.com` | `chatbot-stage.hubdpb.com` |
| Subdominio produccion | `{producto}.hubdpb.com` | `chat.hubdpb.com` |
| DB staging | `{producto}_stage` | `chatbotmvp_stage` |
| DB produccion | `{producto}_{cliente}` | `chatbotmvp_acme` |
| Usuario DB | `{db}_user` | `chatbotmvp_stage_user` |
| Hostname mismo proyecto | `{servicio}` | `postgres-shared` |
| Hostname cross-project | `{proyecto}_{servicio}` | `hub-core_postgres-shared` |

---

**Documento creado:** abril 2026
**Proyecto de referencia:** chatbot-mvp
