# Deploy

Guia para desplegar Chatbot MVP en los servicios mas populares.

## Prerequisitos

- Cuenta en el servicio de deploy elegido
- API key de OpenRouter o Anthropic

---

## Railway

1. Fork/sube el repo a GitHub
2. Ve a [railway.app](https://railway.app) > New Project > Deploy from GitHub repo
3. Selecciona el repo `chatbot-mvp`
4. Railway detecta el `Dockerfile` automaticamente
5. Configura las variables de entorno en Settings > Variables:

```
ANTHROPIC_API_KEY=sk-or-v1-xxxx
ANTHROPIC_BASE_URL=https://openrouter.ai/api
AI_MODEL=anthropic/claude-sonnet-4
JWT_SECRET=genera-un-secreto-seguro
DATABASE_URL=sqlite:///./chatbot.db
CORS_ORIGINS=*
```

6. Railway asigna un dominio automatico (ej: `chatbot-mvp-production.up.railway.app`)
7. Accede a `https://tu-dominio.railway.app/admin` para configurar

---

## Render

1. Ve a [render.com](https://render.com) > New > Web Service
2. Conecta tu repo de GitHub
3. Configura:
   - **Runtime**: Docker
   - **Instance type**: Free (o Starter para produccion)
4. Anade variables de entorno (igual que Railway)
5. Deploy automatico al hacer push

**Nota**: En el plan gratuito de Render el servicio se apaga tras 15 min de inactividad. El primer request tarda ~30s en arrancar.

---

## Fly.io

1. Instala `flyctl`: https://fly.io/docs/hands-on/install-flyctl/

2. Desde el directorio del proyecto:

```bash
fly launch --name chatbot-mvp
```

3. Configura los secrets:

```bash
fly secrets set ANTHROPIC_API_KEY=sk-or-v1-xxxx
fly secrets set ANTHROPIC_BASE_URL=https://openrouter.ai/api
fly secrets set AI_MODEL=anthropic/claude-sonnet-4
fly secrets set JWT_SECRET=genera-un-secreto-seguro
fly secrets set DATABASE_URL=sqlite:///./chatbot.db
```

4. Deploy:

```bash
fly deploy
```

5. Accede a `https://chatbot-mvp.fly.dev/admin`

---

## Docker (self-hosted)

En cualquier servidor con Docker:

```bash
git clone https://github.com/ray83mar81-hue/chatbot-mvp.git
cd chatbot-mvp
cp backend/.env.example backend/.env
# Editar backend/.env con tus keys
docker compose up -d --build
```

El servicio queda en `http://tu-servidor:8000`.

---

## Post-deploy

1. Crear usuario admin:
```bash
curl -X POST https://tu-dominio/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@tu-negocio.com","password":"tu-password-seguro","business_id":1}'
```

2. Acceder al panel: `https://tu-dominio/admin`
3. Configurar datos del negocio
4. Crear intents personalizados
5. Copiar codigo embed desde Admin > Integrar
6. Pegar en tu web

## Produccion checklist

- [ ] Cambiar `JWT_SECRET` por un valor seguro y unico
- [ ] Configurar `CORS_ORIGINS` solo con los dominios necesarios
- [ ] Considerar PostgreSQL en vez de SQLite para mayor concurrencia
- [ ] Configurar HTTPS (los servicios cloud lo hacen automatico)
- [ ] Hacer backup regular de la base de datos
