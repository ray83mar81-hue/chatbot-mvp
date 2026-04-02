import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import AdminUser, Business, Intent
from app.routers import auth, business, chat, conversations, intents, metrics

app = FastAPI(title="Chatbot MVP", version="1.0.0")

# CORS — allow widget and admin panel to connect
origins = settings.CORS_ORIGINS.split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(chat.router)
app.include_router(business.router)
app.include_router(intents.router)
app.include_router(conversations.router)
app.include_router(metrics.router)
app.include_router(auth.router)


@app.on_event("startup")
def on_startup():
    """Create tables and seed demo data if DB is empty."""
    Base.metadata.create_all(bind=engine)
    _seed_demo_data()


def _seed_demo_data():
    """Insert demo business + intents if the DB is fresh."""
    db = SessionLocal()
    try:
        if db.query(Business).first():
            return  # Already seeded

        biz = Business(
            name="Café Central",
            description="Cafetería artesanal en el centro de la ciudad. "
            "Especialidad en café de origen, pasteles caseros y brunch los fines de semana.",
            schedule=json.dumps(
                {
                    "lunes a viernes": "7:00 - 20:00",
                    "sábados": "8:00 - 21:00",
                    "domingos": "9:00 - 15:00",
                },
                ensure_ascii=False,
            ),
            address="Calle Mayor 42, Centro",
            phone="+34 612 345 678",
            email="hola@cafecentral.com",
            extra_info="WiFi gratis. Aceptamos reservas para grupos de más de 6 personas. "
            "Tenemos opciones veganas y sin gluten. Parking público a 2 minutos.",
        )
        db.add(biz)
        db.commit()
        db.refresh(biz)

        demo_intents = [
            Intent(
                business_id=biz.id,
                name="horarios",
                keywords=json.dumps(
                    ["horario", "hora", "abierto", "abren", "cierran", "horarios"],
                    ensure_ascii=False,
                ),
                response="Nuestros horarios son:\n"
                "• Lunes a viernes: 7:00 - 20:00\n"
                "• Sábados: 8:00 - 21:00\n"
                "• Domingos: 9:00 - 15:00",
                priority=10,
            ),
            Intent(
                business_id=biz.id,
                name="ubicacion",
                keywords=json.dumps(
                    ["donde", "ubicacion", "direccion", "llegar", "mapa", "dirección", "ubicación"],
                    ensure_ascii=False,
                ),
                response="Estamos en Calle Mayor 42, Centro. "
                "Hay parking público a 2 minutos caminando.",
                priority=10,
            ),
            Intent(
                business_id=biz.id,
                name="precios",
                keywords=json.dumps(
                    ["precio", "precios", "cuesta", "vale", "carta", "menu", "menú"],
                    ensure_ascii=False,
                ),
                response="Nuestros precios orientativos:\n"
                "• Café espresso: 1.80€\n"
                "• Café con leche: 2.20€\n"
                "• Tostada con tomate: 3.50€\n"
                "• Brunch completo (fines de semana): 14.90€\n"
                "Consulta la carta completa en el local o pídela por email.",
                priority=10,
            ),
            Intent(
                business_id=biz.id,
                name="wifi",
                keywords=json.dumps(
                    ["wifi", "internet", "contraseña", "clave"],
                    ensure_ascii=False,
                ),
                response="Sí, tenemos WiFi gratis. "
                "Pide la contraseña en barra cuando hagas tu pedido.",
                priority=5,
            ),
            Intent(
                business_id=biz.id,
                name="reservas",
                keywords=json.dumps(
                    ["reservar", "reserva", "reservas", "grupo", "grupos", "mesa"],
                    ensure_ascii=False,
                ),
                response="Aceptamos reservas para grupos de más de 6 personas. "
                "Puedes reservar llamando al +34 612 345 678 o enviando un email a hola@cafecentral.com.",
                priority=5,
            ),
        ]
        db.add_all(demo_intents)
        db.commit()
    finally:
        db.close()


# ── Static files ──────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # chatbot-mvp/
WIDGET_DIR = PROJECT_ROOT / "widget"
ADMIN_DIR = PROJECT_ROOT / "admin"

if WIDGET_DIR.exists():
    app.mount("/widget", StaticFiles(directory=str(WIDGET_DIR)), name="widget")
if ADMIN_DIR.exists():
    app.mount("/admin", StaticFiles(directory=str(ADMIN_DIR), html=True), name="admin")


@app.get("/")
def root():
    return {
        "app": "Chatbot MVP",
        "version": "1.0.0",
        "endpoints": {
            "admin": "/admin",
            "widget_demo": "/widget/demo.html",
            "api_docs": "/docs",
            "health": "/health",
        },
    }


@app.get("/health")
def health():
    return {"status": "ok"}
