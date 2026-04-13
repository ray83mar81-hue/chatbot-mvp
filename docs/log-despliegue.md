# Log de despliegue — chatbot-mvp en hub-stage

Historial real de errores encontrados durante el primer despliegue de `chatbot-mvp` en `hub-stage` (chatbot-stage.hubdpb.com). Fecha: abril 2026.

---

## Error 1: Banderas (flags SVG) devuelven 404

**Cuando:** Despues del primer deploy exitoso. El admin panel cargaba correctamente pero los chips de idioma mostraban el emoji fallback "🌐" en vez de las banderas SVG.

**Sintoma:**
```
GET https://chatbot-stage.hubdpb.com/flags/es.svg → 404 Not Found
```

**Causa exacta:** El `Dockerfile` copiaba `backend/`, `widget/` y `admin/` al contenedor, pero **no copiaba la carpeta `flags/`**. El directorio no existia dentro del contenedor, asi que FastAPI no montaba la ruta `/flags` y todas las peticiones devolvian 404.

**Como se diagnostico:**
```bash
curl -s -o /dev/null -w "%{http_code}" https://chatbot-stage.hubdpb.com/flags/es.svg
# Resultado: 404
```
Se reviso el Dockerfile y se confirmo que faltaba la linea COPY.

**Solucion:**

Agregar la linea al Dockerfile:
```dockerfile
# Antes (incompleto):
COPY backend/ ./backend/
COPY widget/ ./widget/
COPY admin/ ./admin/

# Despues (correcto):
COPY backend/ ./backend/
COPY widget/ ./widget/
COPY admin/ ./admin/
COPY flags/ ./flags/
```

Commit: `a0511a3 Add missing COPY flags/ to Dockerfile`

**Leccion aprendida:** Cada vez que se agrega una carpeta nueva al proyecto que se sirve como static files, hay que agregarla tambien al Dockerfile. Revisar el bloque COPY completo antes de cada deploy.

---

## Error 2: Chrome pide permiso para "acceder a otras aplicaciones y servicios"

**Cuando:** Al abrir `chatbot-stage.hubdpb.com/widget/demo.html` por primera vez. Chrome mostraba un dialogo de permisos pidiendo acceder a aplicaciones y servicios del dispositivo local.

**Sintoma:** Popup de Chrome "Private Network Access":
> chatbot-stage.hubdpb.com quiere acceder a otras aplicaciones y servicios de este dispositivo

**Causa exacta:** El archivo `widget/demo.html` tenia URLs hardcodeadas apuntando a `localhost`:

```html
<script
  src="http://localhost:8000/widget/chat-widget.js"
  data-api-url="http://localhost:8000"
  ...
```

Chrome detectaba que una web publica (`chatbot-stage.hubdpb.com`) intentaba hacer peticiones a `localhost:8000` (red privada) y activaba la proteccion Private Network Access (PNA).

**Como se diagnostico:** Se inspeccionaron las peticiones de red en DevTools y se busco `localhost` en los archivos del widget:

```bash
grep -n "localhost" widget/demo.html
# Resultado:
# 63:  data-api-url="http://localhost:8000"
# 75:  src="http://localhost:8000/widget/chat-widget.js"
# 76:  data-api-url="http://localhost:8000"
```

**Solucion:**

Reemplazar URLs absolutas de localhost por rutas relativas:
```html
<!-- Antes -->
<script
  src="http://localhost:8000/widget/chat-widget.js"
  data-api-url="http://localhost:8000"

<!-- Despues -->
<script
  src="/widget/chat-widget.js"
  data-api-url=""
```

El widget ya tenia fallback a `window.location.origin` cuando `data-api-url` esta vacio:
```javascript
apiUrl: script?.getAttribute("data-api-url") || window.location.origin,
```

Tambien se corrigio el bloque de ejemplo de integracion:
```html
<!-- Ejemplo que se muestra al usuario -->
<script
  src="https://tu-dominio.com/widget/chat-widget.js"
  data-api-url="https://tu-dominio.com"
```

Commit: `c0e7b68 Fix demo.html: replace localhost URLs with relative paths`

**Leccion aprendida:** Nunca usar `localhost` en archivos que se sirven en produccion. Usar siempre rutas relativas o el patron `window.location.origin`. Antes de deployar, buscar `localhost` en todo el frontend:
```bash
grep -rn "localhost" widget/ admin/
```

---

## Error 3: Base de datos SQLite como default en produccion

**Cuando:** Durante la preparacion del deploy. El default de `DATABASE_URL` en `config.py` apuntaba a SQLite.

**Sintoma:** No era un error en runtime (el servicio arrancaba), pero era un riesgo: si se olvidaba configurar `DATABASE_URL` en las variables de entorno de Easypanel, el servicio usaria SQLite en vez de PostgreSQL, perdiendo datos al reiniciar el contenedor (SQLite se guarda en el filesystem efimero del container).

**Causa exacta:**
```python
# config.py
DATABASE_URL: str = "sqlite:///./chatbot.db"
```

**Como se diagnostico:** Revision del codigo durante la preparacion del deploy.

**Solucion:**

Cambiar el default a PostgreSQL para que falle rapido si no se configura:
```python
# config.py
DATABASE_URL: str = "postgresql://user:pass@localhost:5432/chatbot"
```

Tambien se actualizo `.env.example`:
```env
# === Database (PostgreSQL) ===
DATABASE_URL=postgresql://user:pass@localhost:5432/chatbot
```

Y se agrego `psycopg2-binary` a requirements.txt:
```
psycopg2-binary==2.9.10
```

Los tests siguen usando SQLite en memoria (rapido y aislado):
```python
# conftest.py
TEST_DB_URL = "sqlite:///./test.db"
```

Commit: `7b6a83d Switch default database from SQLite to PostgreSQL`

**Leccion aprendida:** Los defaults de configuracion deben reflejar el entorno de produccion, no el de desarrollo local. Si el servicio necesita PostgreSQL, el default debe ser PostgreSQL para que falle rapido si falta la configuracion.

---

## Error 4: Rama por defecto era `master` en vez de `main`

**Cuando:** Al configurar el repositorio en Easypanel. El resto de proyectos usan `main` como rama por defecto.

**Sintoma:** Inconsistencia con el resto de repos. Riesgo de configurar la rama incorrecta en Easypanel.

**Causa exacta:** El repo se creo con `git init` que por defecto usa `master` (dependiendo de la configuracion de Git).

**Como se diagnostico:** Al preguntar que rama seleccionar en Easypanel, se detecto la inconsistencia.

**Solucion:**
```bash
# Renombrar local
git branch -m master main

# Push nueva rama
git push -u origin main

# Cambiar default en GitHub
gh repo edit --default-branch main

# Borrar master del remoto
git push origin --delete master
```

**Leccion aprendida:** Estandarizar la rama por defecto a `main` desde el inicio. Configurar Git globalmente si es necesario:
```bash
git config --global init.defaultBranch main
```

---

## Error 5: Seccion "Integrar" del admin muestra codigo embed vacio

**Cuando:** Al navegar directamente a la seccion "Integrar" del panel admin sin haber visitado antes la seccion "Negocio".

**Sintoma:** La seccion "Codigo para tu web" aparecia sin contenido. El bloque `<code>` estaba vacio.

**Causa exacta:** La seccion embed depende de `bizDataState.langs` y `bizLangState.welcomes` para generar el codigo. Estos datos solo se cargan cuando se visita la seccion "Negocio" (`loadBusiness()`). Si el usuario iba directamente a "Integrar", estos estados estaban vacios.

```javascript
// Linea 682 — handler de navegacion
if (section === "embed") { loadEmbedTexts(); updateEmbed(); }
// loadEmbedTexts() usa bizDataState.langs que esta vacio → codigo vacio
```

**Como se diagnostico:** Se rastreo el flujo de datos desde `updateEmbed()` hasta `bizDataState.langs` y se confirmo que `loadBusiness()` nunca se llamaba al entrar a la seccion embed.

**Solucion:**

Cargar los datos del negocio antes de renderizar el embed:
```javascript
// Antes:
if (section === "embed") { loadEmbedTexts(); updateEmbed(); }

// Despues:
if (section === "embed") { loadBusiness().then(() => { loadEmbedTexts(); updateEmbed(); }); }
```

**Leccion aprendida:** Cada seccion del admin debe ser autosuficiente — no debe depender de que el usuario haya visitado otra seccion antes. Si necesita datos, debe cargarlos ella misma.

---

## Checklist pre-deploy

Ejecutar antes de cada despliegue para no repetir estos errores:

### Codigo
- [ ] `grep -rn "localhost" widget/ admin/` — no hay referencias a localhost en frontend
- [ ] Todas las carpetas con static files tienen su `COPY` en el Dockerfile
- [ ] `requirements.txt` incluye `psycopg2-binary` (o el driver de DB correspondiente)
- [ ] Endpoint `/health` existe y responde `{"status": "ok"}`
- [ ] `config.py` tiene defaults de produccion (PostgreSQL, no SQLite)
- [ ] `.dockerignore` excluye `.claude/`, `.env`, `*.md`, `.git/`

### Git
- [ ] Rama por defecto es `main`
- [ ] Todos los cambios estan commiteados y pusheados
- [ ] Build local con `docker build .` pasa sin errores

### Easypanel
- [ ] DB creada en postgres-shared con usuario restringido
- [ ] Servicio creado con nombre siguiendo convencion (`{producto}-stage`)
- [ ] Variables de entorno configuradas (especialmente `DATABASE_URL` con hostname correcto)
- [ ] Hostname cross-project usa underscore: `hub-core_postgres-shared`
- [ ] Dominio configurado con SSL Let's Encrypt
- [ ] `CORS_ORIGINS` apunta al dominio correcto con `https://`

### Post-deploy
- [ ] `https://{subdominio}/health` responde 200
- [ ] `https://{subdominio}/docs` carga Swagger
- [ ] `https://{subdominio}/admin` carga el panel
- [ ] Archivos estaticos cargan (flags, widget, etc.)
- [ ] Usuario admin creado con `curl`
- [ ] Logs sin errores en Dozzle (`logs.hubdpb.com`)

---

**Documento creado:** abril 2026
**Proyecto:** chatbot-mvp
**Entorno:** hub-stage (chatbot-stage.hubdpb.com)
