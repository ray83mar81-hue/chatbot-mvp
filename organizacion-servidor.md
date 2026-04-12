# Organización del servidor — hubdpb.com

Documento de referencia con la arquitectura definitiva del servidor y los 3 proyectos de Easypanel.

---

## 1. Infraestructura base

### Dominio
- **Dominio principal:** `hubdpb.com`
- **Registrar:** Raiola Networks
- **DNS:** Cloudflare (plan Free) — migrado desde Contabo DNS
- **IP del VPS:** `45.85.249.168`
- **Wildcard DNS:** `*.hubdpb.com` apuntando al VPS
- **Registros A explícitos:** `easy`, `pgadmin`, `mailing`, `n8n`, `centmobel`, `centmobel-stage`, `www`, raíz
- **Estado proxy:** todos en DNS only (gris) mientras se usa HTTP-01 challenge. Pasarán a Proxied cuando se configure DNS-01 challenge.
- **SSL:** Let's Encrypt vía HTTP-01 (fase inicial) → DNS-01 challenge (cuando se active Cloudflare proxied)
- **Correo:** no hay MX. Correo transaccional externo vía Resend cuando se necesite.

### VPS
- **Proveedor:** Contabo
- **Plan:** 8 vCPU compartidas / 24 GB RAM / 200 GB NVMe / 600 Mbit/s / tráfico ilimitado
- **Coste:** 14,15 €/mes
- **Datacenter recomendado:** Nuremberg o Düsseldorf (latencia ES ~40 ms)
- **Sistema:** Ubuntu LTS + Easypanel (plan Free, 3 proyectos)
- **Swap:** 4 GB con `vm.swappiness=10` (red de seguridad anti-OOM)

### Servicios externos
- **Email transaccional:** Resend (free tier 3.000/mes, 100/día)
- **Backups:** Backblaze B2
- **DNS / WAF / cache:** Cloudflare
- **Pagos:** Redsys (producción y sandbox)

---

## 2. Decisiones arquitectónicas clave

| Decisión | Elección | Razón |
|---|---|---|
| Multi-tenancy | **Una DB por tenant** | Máximo aislamiento, cero riesgo de fugas por bug de aplicación |
| Postgres | **Una sola instancia compartida** | Menos overhead operativo, backups centralizados |
| Routing multi-tenant | **Path-based** (`gastos.hubdpb.com/{tenant}`) | Evita certs wildcard de segundo nivel |
| Mailing | **Resend externo** | Reputación de IP delegada, sin dolor de cabeza |
| centmobel | **Single-tenant, un solo servicio** (frontend + backend en mismo contenedor) | Cliente único, ahorra RAM y elimina CORS |
| Estáticos brownfield (dpblook, virtualIA) | **Patrón B: un container nginx por cliente** | Simplicidad, 64 MB por cliente |
| Auth en proyectos nuevos | **Better-Auth** (no Lucia) | Activamente mantenido, mejor DX |
| ORM en proyectos nuevos | **Drizzle** | Type-safe, ligero, optimizado para Postgres |

---

## 3. Los 3 proyectos de Easypanel

### 🟦 hub-core — Infraestructura compartida

Servicios base que dan soporte a todo lo demás. Aquí vive la única instancia de Postgres, la única instancia de Redis, las herramientas internas y el monitoring.

**Servicios:**

- `postgres-shared`
- `pgadmin`
- `redis-shared`
- `n8n` (imagen fija: `n8nio/n8n:2.2.4` — por compatibilidad con workflows migrados desde `n8n.fantastic-ia.es`)
- `evolution-api`
- `filebrowser`
- `backups`
- `uptime-kuma`
- `dozzle`
- `netdata`

**Subdominios públicos:**

| Servicio | Subdominio |
|---|---|
| Easypanel | `easy.hubdpb.com` |
| pgAdmin | `pgadmin.hubdpb.com` |
| n8n | `n8n.hubdpb.com` |
| evolution-api | `evolution.hubdpb.com` |
| filebrowser | `files.hubdpb.com` |
| uptime-kuma | `status.hubdpb.com` |
| dozzle | `logs.hubdpb.com` |
| netdata | `metrics.hubdpb.com` |

`postgres-shared`, `redis-shared` y `backups` no se exponen al exterior (solo red interna).

---

### 🟨 hub-stage — Preproducción y demos

Espejo reducido de producción con DBs de prueba. Siempre vivo para enseñar demos a clientes potenciales y validar cambios antes de promocionar a producción.

**Servicios:**

- `gastosdpb-stage`
- `mailing-stage`
- `pasarela-stage`
- `agendar-stage`
- `chatbot-stage`
- `centmobel-stage`

**Subdominios:**

| Servicio | Subdominio |
|---|---|
| gastosdpb-stage | `gastos-stage.hubdpb.com` |
| mailing-stage | `mailing-stage.hubdpb.com` |
| pasarela-stage | `pasarela-stage.hubdpb.com` |
| agendar-stage | `agendar-stage.hubdpb.com` |
| chatbot-stage | `chatbot-stage.hubdpb.com` |
| centmobel-stage | `centmobel-stage.hubdpb.com` |

`cpu_shares=512` para todos (prioridad baja respecto a producción).

---

### 🟩 hub-prod — Producción real

Todo lo que está vivo de cara a clientes finales. Prioridad máxima de recursos (`cpu_shares=2048`).

**Servicios SaaS multi-tenant (DB por tenant):**

- `gastosdpb-web`
- `mailing-web`
- `pasarela-web`
- `agendar-web`
- `chatbot-api`

**Servicio single-tenant:**

- `centmobel`

**Servicios estáticos brownfield (uno por cliente):**

- `dpblook-{cliente}` × N
- `virtualia-{cliente}` × N

**Subdominios:**

| Servicio | Subdominio |
|---|---|
| gastosdpb-web | `gastos.hubdpb.com/{tenant}` |
| mailing-web | `mailing.hubdpb.com/{tenant}` |
| pasarela-web | `pago.hubdpb.com` |
| agendar-web | `agendar.hubdpb.com/{tenant}` |
| chatbot-api | `chat.hubdpb.com` |
| centmobel | `centmobel.hubdpb.com` |
| dpblook-{cliente} | `{cliente}.dpblook.hubdpb.com` o dominio propio |
| virtualia-{cliente} | `{cliente}.inmobiliaria.hubdpb.com` o dominio propio |

---

## 4. Estructura de bases de datos

Todas las DBs viven dentro de la única instancia `postgres-shared` (en `hub-core`). Cada DB tiene su propio usuario con permisos restringidos solo a esa DB.

```
postgres-shared (instancia única)
│
├── DB: n8n                      → usuario n8n_user
├── DB: gastosdpb_acme           → usuario gastosdpb_acme_user
├── DB: gastosdpb_beta           → usuario gastosdpb_beta_user
├── DB: gastosdpb_{cliente}…     → (uno por cliente)
├── DB: mailing_acme             → usuario mailing_acme_user
├── DB: mailing_{cliente}…       → (uno por cliente)
├── DB: pagos_acme               → usuario pagos_acme_user
├── DB: pagos_{cliente}…         → (uno por cliente)
├── DB: agendar_acme             → usuario agendar_acme_user
├── DB: agendar_{cliente}…       → (uno por cliente)
├── DB: chatbot_acme             → usuario chatbot_acme_user
├── DB: chatbot_{cliente}…       → (uno por cliente)
├── DB: centmobel                → usuario centmobel_user
│
├── DB: gastosdpb_stage_demo     → usuario stage_demo_user
├── DB: mailing_stage_demo
├── DB: pagos_stage_demo
├── DB: agendar_stage_demo
├── DB: chatbot_stage_demo
└── DB: centmobel_stage          → usuario centmobel_stage_user
```

### Configuración de Postgres tuneada para NVMe

```
shared_buffers = 768MB
effective_cache_size = 2GB
work_mem = 16MB
maintenance_work_mem = 256MB
max_connections = 200
random_page_cost = 1.1
effective_io_concurrency = 200
checkpoint_completion_target = 0.9
wal_compression = on
max_wal_size = 4GB
max_worker_processes = 8
max_parallel_workers_per_gather = 4
```

---

## 5. Convenciones globales

### Naming
- **Servicios:** `{producto|cliente}-{rol}` → `gastosdpb-web`, `acme-api`, `dpblook-fulanito`.
- **DBs:** `{producto}_{cliente}` → `gastosdpb_acme`, `mailing_beta`.
- **Usuarios DB:** `{db}_user` → `gastosdpb_acme_user`.
- **Schemas dentro de DB:** `public` por defecto (single tenant por DB).

### Subdominios
- **Producción multi-tenant:** path-based `producto.hubdpb.com/{tenant}`.
- **Producción single-tenant:** subdominio propio `cliente.hubdpb.com`.
- **Staging:** sufijo `-stage` → `producto-stage.hubdpb.com` (ej: `centmobel-stage.hubdpb.com`).
- **Internas:** subdominio descriptivo → `n8n.hubdpb.com`, `files.hubdpb.com`.

### Recursos
- **`mem_limit` duro** en todos los servicios sin excepción.
- **`cpu_shares`** en lugar de `cpus` estricto (vCPU compartidas en Contabo).
  - Producción: 2048
  - Herramientas internas: 1024
  - Staging: 512
- **Healthcheck obligatorio** en `/api/health` o equivalente.

### Secretos
- Variables de entorno gestionadas desde el panel de Easypanel por servicio.
- Catálogo de credenciales en `SECRETS.md` versionado en repo (sin valores reales).
- Valores maestros almacenados en 1Password vault.

### Logs
- Salida estándar (stdout/stderr) en formato JSON estructurado.
- Centralizados en Dozzle (`logs.hubdpb.com`).

---

## 6. Política de backups

**Destino:** Backblaze B2 + 3 copias locales en `/var/backups/postgres/`.

**Retención:**
- 3 copias locales (rotación diaria)
- 7 backups diarios
- 4 backups semanales
- 6 backups mensuales

**Frecuencia:** diario a las 03:00 UTC.

**Cobertura:** el script itera todas las DBs del `postgres-shared` y hace `pg_dump -Fc` por cada una.

**Validación:** test de restore automatizado semanal (descarga el último backup, lo restaura en una DB temporal, valida que las tablas clave existen).

**Alerting:** webhook a Uptime Kuma o Telegram si cualquier paso falla.

---

## 7. Recursos estimados

### RAM por bloque (con 10 clientes activos)

| Bloque | RAM estimada |
|---|---|
| Sistema + Easypanel + swap | 1,5 GB |
| `hub-core` | 5,3 GB |
| `hub-stage` | 2,3 GB |
| `hub-prod` | 4,2 GB |
| **Total comprometido** | **~13,3 GB** |
| **Margen libre permanente** | **~10,7 GB** |

### Crecimiento por cliente nuevo
- SaaS multi-tenant: ~50-100 MB de RAM por DB nueva
- Estático (dpblook, virtualIA): 64 MB por cliente
- **Capacidad estimada:** 80-150 clientes nuevos antes de tocar el VPS

### Cuándo ampliar
- Margen libre por debajo de 4 GB de forma sostenida
- `steal time` > 20% en horas pico
- Salto natural: Contabo VPS XL (12 vCPU / 48 GB / 400 GB NVMe) ~30 €/mes

---

## 8. Cómo se monta centmobel en el servidor

### Ubicación
- **Proyecto:** `hub-prod`
- **Servicio:** `centmobel`
- **Subdominio:** `centmobel.hubdpb.com`
- **Recursos:** 512 MB RAM, `cpu_shares=2048`
- **Staging:** servicio `centmobel-stage` en `hub-stage`, subdominio `centmobel-stage.hubdpb.com`, 384 MB RAM

### Arquitectura
**Un solo contenedor** que sirve frontend + API en el mismo proceso. Dos opciones según framework:
- **Next.js full-stack:** API routes integradas + Better-Auth como handler.
- **Vite/Astro + Fastify:** Fastify sirve estáticos del build y maneja `/api/*`.

### Stack
- Backend: Fastify 5 + TypeScript (o Next.js API routes)
- ORM: Drizzle
- Auth: Better-Auth
- Validación: Zod
- Runtime: Node 20-alpine

### SQL de provisioning
```sql
CREATE USER centmobel_user WITH PASSWORD '<password>';
CREATE DATABASE centmobel
  OWNER centmobel_user
  ENCODING 'UTF8'
  TEMPLATE template0;
REVOKE CONNECT ON DATABASE centmobel FROM PUBLIC;
GRANT CONNECT ON DATABASE centmobel TO centmobel_user;
GRANT ALL PRIVILEGES ON DATABASE centmobel TO centmobel_user;
```

### Variables de entorno
```
NODE_ENV=production
PORT=3000
TRUST_PROXY=true
DATABASE_URL=postgresql://centmobel_user:<password>@postgres-shared:5432/centmobel
BETTER_AUTH_SECRET=<openssl rand -base64 32>
BETTER_AUTH_URL=https://centmobel.hubdpb.com
```

### Plan de migración desde Supabase
1. Exportar schema con `pg_dump --schema-only --no-owner --no-acl`.
2. Limpiar SQL: quitar RLS, policies, publication, referencias a `auth.uid()`, extensiones Supabase.
3. Adaptar tablas de auth a Better-Auth.
4. Provisionar la DB `centmobel` en `postgres-shared`.
5. Aplicar el SQL limpio.
6. Exportar y reimportar datos con `pg_dump --data-only`.
7. Levantar `centmobel-stage`, validar.
8. Reescribir las ~10 llamadas `supabase.from(...)` a `fetch('/api/...')`.
9. Reescribir Login + AuthContext contra Better-Auth.
10. Validar todo en `centmobel-stage.hubdpb.com`.
11. Levantar `centmobel` en producción y cambiar DNS.
12. Apagar Supabase tras 7 días sin incidencias.

---

## 9. Checklist de arranque del servidor

### Fase 1 — Infraestructura base
- [x] Contratar VPS Contabo (24 GB / 200 GB NVMe)
- [x] Instalar Ubuntu LTS + Easypanel
- [x] Comprar dominio `hubdpb.com` en Raiola
- [x] Cambiar URL del panel Easypanel a `easy.hubdpb.com`
- [x] Crear cuenta Cloudflare y añadir dominio
- [x] Añadir registros DNS en Cloudflare (wildcard + subdominios explícitos, todos en DNS only)
- [ ] Cambiar nameservers en Raiola a los de Cloudflare
- [ ] Verificar propagación DNS (`nslookup -type=NS hubdpb.com`)
- [ ] Configurar swap de 4 GB con `swappiness=10`
- [ ] Solicitar delisting de Google Safe Browsing para `hubdpb.com`
- [ ] Configurar DNS-01 challenge en Easypanel (API token Cloudflare)
- [ ] Activar Cloudflare Proxied selectivamente en subdominios de admin

### Fase 2 — hub-core
- [x] Crear proyecto `hub-core` en Easypanel
- [x] Levantar `postgres-shared` con configuración tuneada para NVMe
- [x] Levantar `pgadmin` conectado a postgres-shared
- [x] Levantar `n8n` (imagen `n8nio/n8n:2.2.4`, DB propia en postgres-shared)
- [ ] Migrar workflows desde `n8n.fantastic-ia.es` a `n8n.hubdpb.com`
- [ ] Levantar `redis-shared`
- [ ] Levantar `evolution-api` con volumen persistente
- [ ] Levantar `filebrowser` con basic auth
- [ ] Levantar `uptime-kuma`, `dozzle`, `netdata`
- [ ] Configurar `backups` con cron diario y test de restore semanal

### Fase 3 — hub-stage
- [ ] Crear proyecto `hub-stage`
- [ ] Provisionar DBs `*_stage_demo` en postgres-shared
- [ ] Levantar los 6 servicios de staging
- [ ] Validar conectividad con postgres-shared
- [ ] Validar SSL y subdominios

### Fase 4 — hub-prod
- [ ] Crear proyecto `hub-prod`
- [ ] Provisionar DBs por cliente para SaaS multi-tenant
- [ ] Provisionar DB `centmobel`
- [ ] Levantar los 5 servicios SaaS multi-tenant
- [ ] Migrar y levantar `centmobel`
- [ ] Migrar dpblook y virtualIA brownfield (cliente por cliente)
- [ ] Validar healthchecks y monitoring

### Fase 5 — Operación
- [ ] Documentar `SECRETS.md` (catálogo sin valores)
- [ ] Configurar alertas en Uptime Kuma
- [ ] Configurar alerta de `steal time > 20%` en Netdata
- [ ] Test de restore manual del primer backup
- [ ] Plan de comunicación con clientes brownfield para migración DNS

---

## 10. Riesgos y plan de escalado

| Riesgo | Mitigación |
|---|---|
| vCPU compartidas Contabo (vecino ruidoso) | Alerta `steal time > 20%`, plan B: migrar a Hetzner CCX13 |
| OOM por pico inesperado | Swap de 4 GB + `mem_limit` duro en todos los servicios |
| Pérdida de datos | Backups 3 locales + 7-4-6 en B2 + test de restore semanal |
| Filtración entre clientes | DB por tenant, usuarios con permisos restringidos |
| Saturación del VPS | Monitoring permanente, salto a Contabo VPS XL cuando margen < 4 GB |
| Reputación SMTP | Delegado a Resend, no se autohospeda email |
| Caída de Easypanel | Estado en disco, recuperable con `docker compose up` manual |

### Señales para pasar a Easypanel Pro (~19 €/mes)
- Necesidad de más de 3 proyectos por separación de equipos o compliance
- Necesidad de roles y permisos por usuario
- Más de 30 servicios totales (gestión visual se complica)

### Señales para migrar a Coolify/Dokploy
- Crecimiento a múltiples VPS gestionados desde un único panel
- Necesidad de pipelines CI/CD nativos más sofisticados
- Requisitos de open source estricto

---

**Documento mantenido en:** `/sessions/funny-optimistic-feynman/mnt/outputs/organizacion-servidor-hubdpb.md`

**Última actualización:** abril 2026