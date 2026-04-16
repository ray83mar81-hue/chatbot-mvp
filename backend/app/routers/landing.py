"""Public landing page for tenants without their own website.

Served at /negocio/{slug}. Renders a self-contained HTML page (no template
engine) with business info, SEO metadata, JSON-LD LocalBusiness, and the
embedded chatbot widget. Multi-language via ?lang= query or Accept-Language.
"""
import html
import json
import re
import unicodedata

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import assert_business_access, assert_business_write, get_current_user
from app.models.admin_user import AdminUser
from app.models.business import Business
from app.models.business_translation import BusinessTranslation

router = APIRouter(tags=["landing"])

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$")


def _esc(s: str | None) -> str:
    """HTML-escape for safe interpolation into the template."""
    return html.escape(s or "", quote=True)


def _slugify(name: str) -> str:
    # Normalise accents, lowercase, replace non-alphanum with dashes
    n = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    n = n.lower()
    n = re.sub(r"[^a-z0-9]+", "-", n)
    n = n.strip("-")
    return n[:50] or "negocio"


# ── Admin endpoints ──────────────────────────────────────────────────


VALID_THEMES = {"clean", "elegant", "minimal", "warm"}


class LandingSettings(BaseModel):
    slug: str | None = None
    landing_enabled: bool = False
    theme: str = "clean"
    logo_url: str = ""
    public_url: str | None = None  # computed — built by the server


class LandingUpdate(BaseModel):
    slug: str | None = None
    landing_enabled: bool | None = None
    theme: str | None = None
    logo_url: str | None = None


@router.get("/business/{business_id}/landing", response_model=LandingSettings)
def get_landing(
    business_id: int,
    request: Request,
    current: AdminUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assert_business_access(current, business_id)
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    public_url = None
    if business.slug and business.landing_enabled:
        public_url = str(request.base_url).rstrip("/") + f"/negocio/{business.slug}"

    return LandingSettings(
        slug=business.slug,
        landing_enabled=bool(business.landing_enabled),
        theme=business.landing_theme or "clean",
        logo_url=business.logo_url or "",
        public_url=public_url,
    )


@router.put("/business/{business_id}/landing", response_model=LandingSettings)
def update_landing(
    business_id: int,
    data: LandingUpdate,
    request: Request,
    current: AdminUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assert_business_write(current, business_id)
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    if data.slug is not None:
        s = data.slug.strip().lower()
        if not s:
            # Auto-generate from name
            s = _slugify(business.name or f"negocio-{business.id}")
        if not SLUG_RE.match(s):
            raise HTTPException(
                status_code=422,
                detail=(
                    "Slug inválido. Usa 3-50 caracteres: letras minúsculas, "
                    "números y guiones. No puede empezar ni acabar en guion."
                ),
            )
        # Uniqueness check
        clash = (
            db.query(Business)
            .filter(Business.slug == s, Business.id != business.id)
            .first()
        )
        if clash:
            raise HTTPException(status_code=409, detail=f"El slug '{s}' ya está en uso por otro negocio")
        business.slug = s

    if data.landing_enabled is not None:
        if data.landing_enabled and not (business.slug or data.slug):
            raise HTTPException(
                status_code=422,
                detail="Asigna un slug antes de publicar la página",
            )
        business.landing_enabled = data.landing_enabled

    if data.theme is not None:
        if data.theme not in VALID_THEMES:
            raise HTTPException(status_code=422, detail=f"Plantilla inválida. Usa una de: {', '.join(sorted(VALID_THEMES))}")
        business.landing_theme = data.theme

    if data.logo_url is not None:
        url = data.logo_url.strip()
        if url and not (url.startswith("http://") or url.startswith("https://")):
            raise HTTPException(status_code=422, detail="La URL del logo debe empezar por http:// o https://")
        business.logo_url = url

    db.commit()
    db.refresh(business)

    public_url = None
    if business.slug and business.landing_enabled:
        public_url = str(request.base_url).rstrip("/") + f"/negocio/{business.slug}"

    return LandingSettings(
        slug=business.slug,
        landing_enabled=bool(business.landing_enabled),
        theme=business.landing_theme or "clean",
        logo_url=business.logo_url or "",
        public_url=public_url,
    )


# ── Public landing page ─────────────────────────────────────────────


def _pick_language(request: Request, supported: list[str], default_lang: str, override: str | None) -> str:
    if override and override in supported:
        return override
    accept = request.headers.get("accept-language", "")
    # Very lightweight parsing: first 2 chars of each candidate
    for part in accept.split(","):
        code = part.split(";")[0].strip().lower()[:2]
        if code in supported:
            return code
    return default_lang if default_lang in supported else (supported[0] if supported else "es")


def _get_translation(business: Business, lang: str, db: Session) -> dict:
    """Return a dict of translated text fields for the given language, falling
    back to the legacy Business fields when no translation row exists."""
    t = (
        db.query(BusinessTranslation)
        .filter_by(business_id=business.id, language_code=lang)
        .first()
    )
    if t:
        return {
            "name": t.name or business.name or "",
            "description": t.description or business.description or "",
            "address": t.address or business.address or "",
            "schedule": t.schedule or business.schedule or "{}",
            "extra_info": t.extra_info or business.extra_info or "",
            "welcome": t.welcome or "",
        }
    return {
        "name": business.name or "",
        "description": business.description or "",
        "address": business.address or "",
        "schedule": business.schedule or "{}",
        "extra_info": business.extra_info or "",
        "welcome": "",
    }


def _build_jsonld(business: Business, t: dict, public_url: str) -> dict:
    """LocalBusiness structured data for SEO."""
    data = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": t["name"],
        "description": t["description"],
        "url": public_url,
    }
    if business.phone:
        data["telephone"] = business.phone
    if business.email:
        data["email"] = business.email
    if t["address"]:
        data["address"] = {"@type": "PostalAddress", "streetAddress": t["address"]}
    # Opening hours from schedule JSON if it's a plain {day: "HH:MM - HH:MM"} map
    try:
        sched = json.loads(t["schedule"] or "{}")
        if isinstance(sched, dict) and sched:
            data["openingHoursSpecification"] = [
                {"@type": "OpeningHoursSpecification", "dayOfWeek": day, "description": hours}
                for day, hours in sched.items()
            ]
    except Exception:
        pass
    return data


LABELS = {
    "es": {
        "contact": "Contacto", "schedule": "Horarios", "address": "Dirección",
        "more": "Más información", "call": "Llamar", "email": "Enviar email",
        "whatsapp": "WhatsApp", "chat_cta": "Chatear con nosotros",
        "share": "Compartir", "share_copied": "Enlace copiado",
        "powered": "Este negocio usa Chatbot MVP",
    },
    "en": {
        "contact": "Contact", "schedule": "Hours", "address": "Address",
        "more": "More info", "call": "Call", "email": "Email",
        "whatsapp": "WhatsApp", "chat_cta": "Chat with us",
        "share": "Share", "share_copied": "Link copied",
        "powered": "This business uses Chatbot MVP",
    },
    "ca": {
        "contact": "Contacte", "schedule": "Horaris", "address": "Adreça",
        "more": "Més informació", "call": "Trucar", "email": "Enviar email",
        "whatsapp": "WhatsApp", "chat_cta": "Xateja amb nosaltres",
        "share": "Compartir", "share_copied": "Enllaç copiat",
        "powered": "Aquest negoci fa servir Chatbot MVP",
    },
    "fr": {
        "contact": "Contact", "schedule": "Horaires", "address": "Adresse",
        "more": "Plus d'infos", "call": "Appeler", "email": "Email",
        "whatsapp": "WhatsApp", "chat_cta": "Discuter avec nous",
        "share": "Partager", "share_copied": "Lien copié",
        "powered": "Cette entreprise utilise Chatbot MVP",
    },
    "de": {
        "contact": "Kontakt", "schedule": "Öffnungszeiten", "address": "Adresse",
        "more": "Mehr Infos", "call": "Anrufen", "email": "E-Mail",
        "whatsapp": "WhatsApp", "chat_cta": "Mit uns chatten",
        "share": "Teilen", "share_copied": "Link kopiert",
        "powered": "Dieses Unternehmen nutzt Chatbot MVP",
    },
    "it": {
        "contact": "Contatti", "schedule": "Orari", "address": "Indirizzo",
        "more": "Altre info", "call": "Chiama", "email": "Email",
        "whatsapp": "WhatsApp", "chat_cta": "Chatta con noi",
        "share": "Condividi", "share_copied": "Link copiato",
        "powered": "Questa attività usa Chatbot MVP",
    },
    "pt": {
        "contact": "Contacto", "schedule": "Horários", "address": "Morada",
        "more": "Mais info", "call": "Ligar", "email": "Email",
        "whatsapp": "WhatsApp", "chat_cta": "Fala connosco",
        "share": "Partilhar", "share_copied": "Link copiado",
        "powered": "Este negócio usa Chatbot MVP",
    },
}


def _theme_css(theme: str, color: str) -> str:
    """Return the CSS block for the chosen landing theme. HTML structure is
    the same across themes; only styling varies."""
    if theme == "elegant":
        # Dark, serif, luxury feel. Gold accent on the brand color.
        return f"""
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: "Georgia", "Times New Roman", serif; background: #111827; color: #e5e7eb; line-height: 1.7; }}
    a {{ color: {color}; }}
    .hero {{ padding: 100px 24px 80px; text-align: center; background: radial-gradient(ellipse at top, #1f2937 0%, #111827 70%); position: relative; border-bottom: 1px solid #374151; }}
    .hero h1 {{ margin: 0 0 16px; font-size: clamp(36px, 5vw, 64px); font-weight: 400; letter-spacing: -0.02em; color: #fff; }}
    .hero p {{ margin: 0 auto 32px; max-width: 620px; font-size: 19px; color: #9ca3af; font-style: italic; }}
    .btn-primary {{ display: inline-block; padding: 14px 36px; background: transparent; color: {color} !important; border: 2px solid {color}; border-radius: 2px; text-decoration: none; font-weight: 600; font-size: 14px; letter-spacing: 0.1em; text-transform: uppercase; font-family: -apple-system, sans-serif; transition: all .2s; }}
    .btn-primary:hover {{ background: {color}; color: #111827 !important; }}
    main {{ max-width: 780px; margin: 60px auto; padding: 0 24px; }}
    .card {{ background: #1f2937; border: 1px solid #374151; border-radius: 2px; padding: 40px; margin-bottom: 24px; }}
    .card h2 {{ margin: 0 0 20px; font-size: 26px; font-weight: 400; color: #fff; letter-spacing: -0.01em; border-bottom: 1px solid {color}; padding-bottom: 12px; display: inline-block; }}
    .prose {{ color: #d1d5db; }}
    ul.schedule {{ list-style: none; padding: 0; margin: 0; }}
    ul.schedule li {{ padding: 10px 0; border-bottom: 1px solid #374151; color: #d1d5db; }}
    ul.schedule li:last-child {{ border-bottom: none; }}
    .contact-grid {{ display: grid; gap: 12px; font-family: -apple-system, sans-serif; }}
    .contact-grid a, .contact-grid div {{ color: #d1d5db; text-decoration: none; }}
    .cta-row {{ display: flex; gap: 12px; flex-wrap: wrap; margin-top: 24px; }}
    .cta {{ flex: 1; min-width: 140px; padding: 14px 20px; background: transparent; color: {color} !important; border: 1px solid {color}; border-radius: 2px; text-align: center; font-weight: 600; text-decoration: none; font-family: -apple-system, sans-serif; font-size: 14px; letter-spacing: 0.05em; transition: all .2s; }}
    .cta:hover {{ background: {color}; color: #111827 !important; }}
    .map-wrap {{ margin-top: 20px; }}
    .map-wrap iframe {{ filter: grayscale(40%) brightness(0.8); }}
    .lang-switcher {{ position: absolute; top: 24px; right: 24px; display: flex; gap: 2px; background: rgba(255,255,255,.05); padding: 4px; border-radius: 2px; font-family: -apple-system, sans-serif; }}
    .lang-switcher a {{ padding: 4px 10px; color: #9ca3af; text-decoration: none; font-size: 11px; letter-spacing: 0.1em; }}
    .lang-switcher a.active {{ color: {color}; }}
    footer {{ text-align: center; padding: 40px 24px; color: #6b7280; font-size: 12px; font-family: -apple-system, sans-serif; border-top: 1px solid #374151; }}
"""
    if theme == "minimal":
        # Black & white, typographic, lots of whitespace. Brand color as single accent.
        return f"""
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #fff; color: #000; line-height: 1.6; }}
    a {{ color: #000; }}
    .hero {{ padding: 120px 24px 100px; position: relative; border-bottom: 1px solid #000; }}
    .hero h1 {{ max-width: 900px; margin: 0 auto 24px; font-size: clamp(40px, 7vw, 96px); font-weight: 900; line-height: 0.95; letter-spacing: -0.03em; }}
    .hero p {{ max-width: 640px; margin: 0 auto 40px; font-size: 20px; color: #525252; }}
    .btn-primary {{ display: inline-block; padding: 16px 32px; background: #000; color: #fff !important; border-radius: 0; text-decoration: none; font-weight: 700; font-size: 15px; border-bottom: 4px solid {color}; transition: transform .15s; }}
    .btn-primary:hover {{ transform: translate(-2px, -2px); box-shadow: 4px 4px 0 {color}; }}
    main {{ max-width: 860px; margin: 80px auto; padding: 0 24px; }}
    .card {{ margin-bottom: 60px; border-top: 1px solid #000; padding-top: 40px; }}
    .card h2 {{ margin: 0 0 24px; font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.15em; color: #000; }}
    .prose {{ font-size: 18px; color: #262626; }}
    ul.schedule {{ list-style: none; padding: 0; margin: 0; font-size: 16px; }}
    ul.schedule li {{ padding: 12px 0; border-bottom: 1px solid #e5e5e5; display: flex; justify-content: space-between; }}
    ul.schedule li strong {{ font-weight: 700; }}
    .contact-grid {{ display: grid; gap: 12px; font-size: 16px; }}
    .contact-grid a, .contact-grid div {{ color: #000; text-decoration: none; }}
    .cta-row {{ display: flex; gap: 0; flex-wrap: wrap; margin-top: 32px; }}
    .cta {{ flex: 1; min-width: 160px; padding: 20px; background: #fff; color: #000 !important; border: 1px solid #000; margin: -1px -1px 0 0; text-align: center; font-weight: 700; text-decoration: none; transition: background .15s; }}
    .cta:hover {{ background: {color}; color: #000 !important; }}
    .map-wrap {{ margin-top: 24px; }}
    .map-wrap iframe {{ border: 1px solid #000 !important; border-radius: 0 !important; filter: grayscale(100%) contrast(1.1); }}
    .lang-switcher {{ position: absolute; top: 24px; right: 24px; display: flex; gap: 0; }}
    .lang-switcher a {{ padding: 6px 12px; color: #737373; text-decoration: none; font-size: 12px; font-weight: 700; letter-spacing: 0.1em; border: 1px solid transparent; }}
    .lang-switcher a.active {{ color: #000; border-color: #000; }}
    footer {{ text-align: center; padding: 40px 24px; color: #737373; font-size: 13px; border-top: 1px solid #000; }}
"""
    if theme == "warm":
        # Rounded, soft pastel tones, friendly illustrative feel.
        return f"""
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #fef6e4; color: #3d3a4e; line-height: 1.6; }}
    a {{ color: {color}; }}
    .hero {{ padding: 80px 24px 60px; text-align: center; position: relative; background: #fef6e4; }}
    .hero::before {{ content: ""; position: absolute; top: -100px; left: -100px; width: 300px; height: 300px; background: {color}; opacity: 0.15; border-radius: 50%; z-index: 0; }}
    .hero::after {{ content: ""; position: absolute; bottom: -80px; right: -80px; width: 250px; height: 250px; background: #f3d2c1; border-radius: 50%; z-index: 0; }}
    .hero > * {{ position: relative; z-index: 1; }}
    .hero h1 {{ margin: 0 0 16px; font-size: clamp(32px, 5vw, 56px); font-weight: 800; color: #001858; }}
    .hero p {{ margin: 0 auto 28px; max-width: 620px; font-size: 18px; color: #3d3a4e; }}
    .btn-primary {{ display: inline-block; padding: 16px 32px; background: {color}; color: #fff !important; border-radius: 999px; text-decoration: none; font-weight: 700; font-size: 16px; box-shadow: 0 6px 0 #001858; transition: all .15s; }}
    .btn-primary:hover {{ transform: translateY(2px); box-shadow: 0 4px 0 #001858; }}
    main {{ max-width: 760px; margin: 20px auto 60px; padding: 0 24px; }}
    .card {{ background: #fff; border-radius: 28px; padding: 32px; margin-bottom: 24px; border: 2px solid #001858; box-shadow: 6px 6px 0 #001858; }}
    .card h2 {{ margin: 0 0 20px; font-size: 22px; color: #001858; font-weight: 800; }}
    .prose {{ color: #3d3a4e; }}
    ul.schedule {{ list-style: none; padding: 0; margin: 0; }}
    ul.schedule li {{ padding: 10px 16px; margin-bottom: 6px; background: #fef6e4; border-radius: 16px; }}
    .contact-grid {{ display: grid; gap: 10px; }}
    .contact-grid a, .contact-grid div {{ color: #3d3a4e; text-decoration: none; padding: 10px 14px; background: #fef6e4; border-radius: 12px; }}
    .cta-row {{ display: flex; gap: 12px; flex-wrap: wrap; margin-top: 24px; }}
    .cta {{ flex: 1; min-width: 140px; padding: 14px 20px; background: #001858; color: #fff !important; border-radius: 999px; text-align: center; font-weight: 700; text-decoration: none; transition: transform .15s; }}
    .cta:hover {{ transform: translateY(-2px); }}
    .map-wrap {{ margin-top: 20px; }}
    .map-wrap iframe {{ border-radius: 20px !important; }}
    .lang-switcher {{ position: absolute; top: 24px; right: 24px; display: flex; gap: 4px; background: #fff; border: 2px solid #001858; border-radius: 999px; padding: 4px; z-index: 2; }}
    .lang-switcher a {{ padding: 4px 12px; color: #3d3a4e; text-decoration: none; font-size: 12px; font-weight: 700; border-radius: 999px; }}
    .lang-switcher a.active {{ background: {color}; color: #fff; }}
    footer {{ text-align: center; padding: 30px 24px; color: #6b7280; font-size: 13px; }}
"""
    # "clean" (default)
    return f"""
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #f9fafb; color: #1f2937; line-height: 1.6; }}
    a {{ color: inherit; }}
    .hero {{ background: linear-gradient(135deg, {color} 0%, {color}dd 100%); color: #fff; padding: 80px 24px 60px; text-align: center; position: relative; }}
    .hero h1 {{ margin: 0 0 12px; font-size: clamp(32px, 5vw, 56px); font-weight: 800; }}
    .hero p {{ margin: 0 auto 24px; max-width: 640px; font-size: 18px; opacity: .95; }}
    .btn-primary {{ display: inline-block; padding: 14px 28px; background: #fff; color: {color}; border-radius: 999px; text-decoration: none; font-weight: 700; font-size: 16px; box-shadow: 0 4px 14px rgba(0,0,0,.15); transition: transform .15s; }}
    .btn-primary:hover {{ transform: translateY(-2px); }}
    main {{ max-width: 760px; margin: -32px auto 60px; padding: 0 24px; position: relative; }}
    .card {{ background: #fff; border-radius: 16px; padding: 28px; box-shadow: 0 2px 8px rgba(0,0,0,.06); margin-bottom: 20px; }}
    .card h2 {{ margin: 0 0 16px; font-size: 22px; color: #111827; }}
    .prose {{ color: #374151; }}
    ul.schedule {{ list-style: none; padding: 0; margin: 0; }}
    ul.schedule li {{ padding: 8px 0; border-bottom: 1px solid #f3f4f6; }}
    ul.schedule li:last-child {{ border-bottom: none; }}
    .contact-grid {{ display: grid; gap: 12px; margin-top: 8px; }}
    .contact-grid a, .contact-grid div {{ text-decoration: none; color: #374151; }}
    .cta-row {{ display: flex; gap: 12px; flex-wrap: wrap; margin-top: 20px; }}
    .cta {{ flex: 1; min-width: 140px; padding: 12px 20px; background: {color}; color: #fff !important; border-radius: 10px; text-align: center; font-weight: 600; text-decoration: none; transition: opacity .15s; }}
    .cta:hover {{ opacity: .9; }}
    .map-wrap {{ margin-top: 16px; }}
    .lang-switcher {{ position: absolute; top: 16px; right: 24px; display: flex; gap: 4px; background: rgba(255,255,255,.15); backdrop-filter: blur(8px); padding: 4px; border-radius: 8px; }}
    .lang-switcher a {{ padding: 4px 10px; color: #fff; text-decoration: none; border-radius: 4px; font-size: 12px; font-weight: 600; }}
    .lang-switcher a.active {{ background: rgba(255,255,255,.3); }}
    footer {{ text-align: center; padding: 32px 24px; color: #9ca3af; font-size: 13px; }}
    footer a {{ color: inherit; }}
    @media (max-width: 600px) {{
      .hero {{ padding: 60px 16px 40px; }}
      main {{ padding: 0 16px; margin-top: -24px; }}
      .card {{ padding: 20px; }}
    }}
"""


def _render_landing(business: Business, t: dict, lang: str, public_url: str, labels: dict) -> str:
    # Widget design → brand color
    try:
        design = json.loads(business.widget_design or "{}") or {}
    except Exception:
        design = {}
    color = design.get("color") or "#2563eb"

    # Schedule as list items
    schedule_items = ""
    try:
        sched = json.loads(t["schedule"] or "{}")
        if isinstance(sched, dict):
            for day, hours in sched.items():
                schedule_items += f'<li><strong>{_esc(day)}:</strong> {_esc(hours)}</li>'
    except Exception:
        pass

    # Contact CTAs
    ctas = []
    if business.phone:
        ctas.append(f'<a class="cta" href="tel:{_esc(business.phone)}">📞 {_esc(labels["call"])}</a>')
    if business.email:
        ctas.append(f'<a class="cta" href="mailto:{_esc(business.email)}">✉️ {_esc(labels["email"])}</a>')
    if business.whatsapp_enabled and business.whatsapp_phone:
        wa = re.sub(r"\D", "", business.whatsapp_phone)
        ctas.append(f'<a class="cta" href="https://wa.me/{_esc(wa)}" target="_blank" rel="noopener">💬 WhatsApp</a>')
    cta_block = "".join(ctas) if ctas else ""

    extra_block = ""
    if (t["extra_info"] or "").strip():
        extra_block = f'''
        <section class="card">
            <h2>{_esc(labels["more"])}</h2>
            <div class="prose">{_esc(t["extra_info"]).replace(chr(10), '<br>')}</div>
        </section>'''

    map_block = ""
    if t["address"]:
        q = _esc(t["address"])
        map_block = f'''
        <div class="map-wrap">
          <iframe
            loading="lazy" allowfullscreen
            src="https://www.google.com/maps?q={q}&output=embed"
            width="100%" height="260" style="border:0;border-radius:12px"></iframe>
        </div>'''

    jsonld = json.dumps(_build_jsonld(business, t, public_url), ensure_ascii=False)
    meta_desc = (t["description"] or t["name"])[:160]

    # Language switcher links
    try:
        supported_codes = json.loads(business.supported_languages or '["es"]')
    except Exception:
        supported_codes = ["es"]
    lang_links = "".join(
        f'<a href="?lang={c}" class="{"active" if c == lang else ""}">{c.upper()}</a>'
        for c in supported_codes
    )

    return f"""<!DOCTYPE html>
<html lang="{_esc(lang)}">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{_esc(t["name"])}</title>
  <meta name="description" content="{_esc(meta_desc)}" />
  <meta property="og:title" content="{_esc(t["name"])}" />
  <meta property="og:description" content="{_esc(meta_desc)}" />
  <meta property="og:type" content="business.business" />
  <meta property="og:url" content="{_esc(public_url)}" />
  {'<meta property="og:image" content="' + _esc(business.logo_url) + '" />' if business.logo_url else ''}
  <link rel="canonical" href="{_esc(public_url)}" />
  <script type="application/ld+json">{jsonld}</script>
  <style>
    {_theme_css(business.landing_theme or "clean", color)}
    .logo-wrap {{ margin-bottom: 20px; }}
    .logo-wrap img {{ max-height: 80px; max-width: 240px; object-fit: contain; }}
    .share-btn {{
      position: absolute; top: 16px; left: 24px;
      background: rgba(255,255,255,.15); backdrop-filter: blur(8px);
      color: #fff; border: none; padding: 6px 14px; border-radius: 999px;
      font-size: 13px; font-weight: 600; cursor: pointer; display: inline-flex;
      align-items: center; gap: 6px; transition: background .15s;
    }}
    .share-btn:hover {{ background: rgba(255,255,255,.28); }}
    .share-btn svg {{ width: 14px; height: 14px; fill: currentColor; }}
    .share-toast {{
      position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
      background: #111827; color: #fff; padding: 10px 20px; border-radius: 999px;
      font-size: 14px; opacity: 0; pointer-events: none; transition: opacity .2s;
      z-index: 999;
    }}
    .share-toast.show {{ opacity: 1; }}
  </style>
</head>
<body>
  <header class="hero" style="position:relative">
    <button type="button" class="share-btn" onclick="sharePage()" aria-label="{_esc(labels["share"])}">
      <svg viewBox="0 0 24 24"><path d="M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7c.05-.23.09-.46.09-.7s-.04-.47-.09-.7l7.05-4.11c.54.5 1.25.81 2.04.81 1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3c0 .24.04.47.09.7L8.04 9.81C7.5 9.31 6.79 9 6 9c-1.66 0-3 1.34-3 3s1.34 3 3 3c.79 0 1.5-.31 2.04-.81l7.12 4.16c-.05.21-.08.43-.08.65 0 1.61 1.31 2.92 2.92 2.92 1.61 0 2.92-1.31 2.92-2.92 0-1.61-1.31-2.92-2.92-2.92z"/></svg>
      {_esc(labels["share"])}
    </button>
    <div class="lang-switcher">{lang_links}</div>
    {'<div class="logo-wrap"><img src="' + _esc(business.logo_url) + '" alt="' + _esc(t["name"]) + '" /></div>' if business.logo_url else ''}
    <h1>{_esc(t["name"])}</h1>
    <p>{_esc(t["description"])}</p>
    <a href="#chat" class="btn-primary" onclick="document.querySelector('.cw-bubble')?.click();return false;">{_esc(labels["chat_cta"])}</a>
  </header>
  <div class="share-toast" id="shareToast">{_esc(labels["share_copied"])}</div>
  <script>
    async function sharePage() {{
      const data = {{
        title: {json.dumps(t["name"])},
        text: {json.dumps(meta_desc)},
        url: {json.dumps(public_url)},
      }};
      try {{
        if (navigator.share) {{
          await navigator.share(data);
        }} else if (navigator.clipboard) {{
          await navigator.clipboard.writeText(data.url);
          const toast = document.getElementById('shareToast');
          toast.classList.add('show');
          setTimeout(() => toast.classList.remove('show'), 2000);
        }} else {{
          window.prompt('Copia este enlace:', data.url);
        }}
      }} catch (e) {{ /* user cancelled or error — silently ignore */ }}
    }}
  </script>

  <main>
    <section class="card">
      <h2>{_esc(labels["contact"])}</h2>
      <div class="contact-grid">
        {'<a href="tel:' + _esc(business.phone) + '">📞 ' + _esc(business.phone) + '</a>' if business.phone else ''}
        {'<a href="mailto:' + _esc(business.email) + '">✉️ ' + _esc(business.email) + '</a>' if business.email else ''}
        {'<div>📍 ' + _esc(t["address"]) + '</div>' if t["address"] else ''}
      </div>
      {map_block}
      <div class="cta-row">{cta_block}</div>
    </section>

    {'<section class="card"><h2>' + _esc(labels["schedule"]) + '</h2><ul class="schedule">' + schedule_items + '</ul></section>' if schedule_items else ''}

    {extra_block}
  </main>

  <footer>
    <a href="https://chatbot-stage.hubdpb.com" target="_blank" rel="noopener">{_esc(labels["powered"])}</a>
  </footer>

  <script
    src="/widget/chat-widget.js"
    data-business-id="{business.id}"
    data-api-url=""
  ></script>
</body>
</html>"""


@router.get("/negocio/{slug}", response_class=HTMLResponse)
def public_landing(
    slug: str,
    request: Request,
    lang: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Public landing page. No auth. Rendered dynamically from business data."""
    business = db.query(Business).filter(Business.slug == slug).first()
    if not business or not business.is_active or not business.landing_enabled:
        raise HTTPException(status_code=404, detail="Página no encontrada")

    try:
        supported = json.loads(business.supported_languages or '["es"]')
    except json.JSONDecodeError:
        supported = ["es"]
    default_lang = business.default_language or "es"

    active_lang = _pick_language(request, supported, default_lang, lang)
    t = _get_translation(business, active_lang, db)

    public_url = str(request.base_url).rstrip("/") + f"/negocio/{slug}"
    labels = LABELS.get(active_lang) or LABELS["es"]

    html_content = _render_landing(business, t, active_lang, public_url, labels)
    return HTMLResponse(content=html_content)
