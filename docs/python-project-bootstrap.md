# Python project bootstrap — defensa mínima contra regresiones

Esto NO es específico de chatbot-mvp. Es la plantilla que aplico a **cualquier proyecto Python** que vaya a tener clientes detrás. El motivo está en `chatbot-mvp/docs/chatbot-mvp-lessons.md` (P19): un import faltante (`NameError: timedelta not defined`) rompió `/chat` durante 7 días sin que nadie lo notara, porque el repo no tenía linter, ni CI, ni smoke test, ni monitor. Una sola hora de setup el primer día lo hubiera evitado.

## Capa 1 — Linter en CI (obligatoria, día 0)

Tiempo de setup: **10 minutos**. Coste a futuro: **cero**. Caza:
- `NameError` por imports olvidados (`F821`).
- Imports duplicados o sin usar (`F401`, `F811`).
- Errores de sintaxis (`E9*`).
- Patrones buggy de FastAPI/SQLAlchemy (`B*`).

### `pyproject.toml` mínimo

```toml
[tool.ruff]
target-version = "py312"      # ajustar a la versión real
line-length = 100
extend-exclude = ["*/.venv", "*/migrations/versions", "node_modules"]

[tool.ruff.lint]
# Reglas que cazan bugs reales. Ampliar con el tiempo, NUNCA silenciar
# una regla F sin escribir el motivo aquí.
select = ["E9", "F", "B", "I"]
ignore = [
    "B008",  # FastAPI Depends() en defaults — idiom legítimo
    "E731",  # lambdas de 1 línea — fine para helpers
]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["F401", "F403"]   # fixtures importadas por side effect
```

### `.github/workflows/ci.yml`

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"      # match el Dockerfile
      - run: pip install ruff==0.15.12  # pinear la versión
      - run: ruff check .
```

### Verificación inicial

```bash
pip install ruff==0.15.12
ruff check .                # debe salir limpio antes de configurar el CI
ruff check . --fix          # autofix de I001/F401, suele resolver el 80%
```

Si el repo tiene mucho código legacy y salen 200 issues, **no aplicar autofix masivo**. Empezar con `select = ["F"]` (sólo Pyflakes), que son bugs duros, y limpiar progresivamente.

## Capa 2 — Smoke test en CI

Tiempo de setup: **30-60 minutos**. Sigue al lint en el mismo workflow.

```yaml
  test:
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: pytest -x tests/test_smoke.py
```

Para una API: un test que arranque el app con SQLite/dummy fixtures, pegue al endpoint crítico (login, chat, lo que sea), y compruebe 200. El AI provider o SMTP se mockean.

## Capa 3 — Monitor externo en producción

Tiempo: **15 minutos**. Servicios gratuitos: UptimeRobot (50 monitores gratis), BetterStack (10 gratis), Healthchecks.io.

Configurar al menos **dos** chequeos:
1. `GET /health` cada 5 min — detecta servicio caído.
2. `POST /endpoint-crítico` con payload mínimo cada 5-10 min — detecta bugs que el lint no caza (DB rota, AI sin saldo, encryption desincronizada, etc.).

Alertas: **email + SMS** (gratis en UptimeRobot via Telegram/Discord webhook). Si sólo es email puedes perderte una alerta de domingo.

## Capa 4 — Política de despliegue

Cuando haya clientes pagando:

- Easypanel/Render/Fly auto-deploy desde `main` → ese entorno es **staging**, no producción.
- Producción se despliega manual desde un tag `release-*`.
- **Nunca redeployar producción con un commit que tenga CI roja.** Si sale rojo, fix-forward o revert; nunca silenciar.

## Reglas operativas

- Cualquier nueva categoría de bug que llegue a producción merece (a) entrada en el `docs/<proyecto>-lessons.md`, y (b) si es cazable estáticamente, una nueva regla de ruff (o nuevo test).
- Las reglas de bug-class (`F8*`, `E9*`, `B0*`) **no se silencian sin justificar**. Las reglas estilísticas sí.
- Cuando tengas 5+ proyectos, considera mover el `pyproject.toml` y el `.github/workflows/ci.yml` a un repo `python-template` y usarlo como template GitHub para los nuevos.

## Checklist al arrancar proyecto Python nuevo

- [ ] Crear `pyproject.toml` con la sección `[tool.ruff]` de arriba.
- [ ] `pip install ruff==<version-actual>` y `ruff check .` — limpio antes de seguir.
- [ ] Crear `.github/workflows/ci.yml` con el lint job.
- [ ] Hacer un commit "CI: lint" y verificar el ✅ en GitHub.
- [ ] Pinear la versión de ruff en el workflow para no comerse rule changes.
- [ ] Una vez haya endpoints, añadir un smoke test en el mismo workflow.
- [ ] Cuando despliegue a producción, alta de monitor externo.
- [ ] Documentar en `docs/<proyecto>-lessons.md` los incidentes nuevos a medida que ocurran.
