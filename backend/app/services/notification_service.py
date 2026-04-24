"""Email notification service.

Today covers two flows:
- Contact form submissions (per-tenant): send_contact_notification.
- Monthly token quota warning at 80% (per-tenant): send_quota_warning.

If SMTP is not configured (settings.SMTP_HOST / SMTP_FROM empty) all sends
return False silently — the caller decides if that is fatal.
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings
from app.models.business import Business
from app.models.contact_request import ContactRequest


def _smtp_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_FROM)


def _send_email(
    to_emails: list[str],
    subject: str,
    body_text: str,
    body_html: str,
) -> bool:
    """Low-level SMTP delivery. Returns True on success, False otherwise
    (SMTP not configured, empty recipients, transport error)."""
    if not _smtp_configured():
        return False
    recipients = [e for e in (to_emails or []) if e]
    if not recipients:
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    try:
        if settings.SMTP_USE_TLS:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
            server.starttls()
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)

        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)

        server.sendmail(settings.SMTP_FROM, recipients, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"[SMTP Error] {type(e).__name__}: {e}")
        return False


# ── Contact form notification ────────────────────────────────────────────


def _build_contact_subject(contact: ContactRequest, business: Business) -> str:
    return f"[{business.name}] Nueva solicitud de contacto de {contact.name}"


def _build_contact_text(contact: ContactRequest, business: Business) -> str:
    wa = ""
    if contact.whatsapp_opt_in and business.whatsapp_phone:
        clean_phone = contact.phone.replace(" ", "").replace("+", "")
        wa = f"\nWhatsApp (cliente acepta): https://wa.me/{clean_phone}\n"

    return f"""Nueva solicitud de contacto desde el chatbot de {business.name}
{'=' * 50}

Nombre:    {contact.name}
Teléfono:  {contact.phone}{wa}
Email:     {contact.email}
Idioma:    {contact.language}
WhatsApp:  {"Sí, acepta" if contact.whatsapp_opt_in else "No"}

Mensaje:
{contact.message}

{'=' * 50}
ID: #{contact.id}
Fecha: {contact.created_at}
"""


def _build_contact_html(contact: ContactRequest, business: Business) -> str:
    wa_badge = ""
    if contact.whatsapp_opt_in and business.whatsapp_phone:
        clean_phone = contact.phone.replace(" ", "").replace("+", "")
        wa_badge = (
            f'<a href="https://wa.me/{clean_phone}" '
            f'style="display:inline-block;background:#25D366;color:#fff;'
            f'padding:8px 16px;border-radius:20px;text-decoration:none;'
            f'font-size:13px;margin-top:8px">Contactar por WhatsApp</a>'
        )

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/></head>
<body style="font-family:-apple-system,sans-serif;background:#f4f4f5;padding:32px">
<div style="max-width:540px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.06)">

  <div style="background:#2563eb;color:#fff;padding:20px 24px">
    <h2 style="margin:0;font-size:18px">Nueva solicitud de contacto</h2>
    <p style="margin:4px 0 0;opacity:.85;font-size:13px">{business.name}</p>
  </div>

  <div style="padding:24px">
    <table style="width:100%;border-collapse:collapse;font-size:14px">
      <tr><td style="padding:6px 0;color:#6b7280;width:100px">Nombre</td><td style="padding:6px 0"><strong>{contact.name}</strong></td></tr>
      <tr><td style="padding:6px 0;color:#6b7280">Teléfono</td><td style="padding:6px 0">{contact.phone}</td></tr>
      <tr><td style="padding:6px 0;color:#6b7280">Email</td><td style="padding:6px 0"><a href="mailto:{contact.email}">{contact.email}</a></td></tr>
      <tr><td style="padding:6px 0;color:#6b7280">Idioma</td><td style="padding:6px 0">{contact.language}</td></tr>
      <tr><td style="padding:6px 0;color:#6b7280">WhatsApp</td><td style="padding:6px 0">{"Acepta" if contact.whatsapp_opt_in else "No"}</td></tr>
    </table>

    {wa_badge}

    <div style="margin-top:20px;padding:16px;background:#f7f8fa;border-radius:8px;font-size:14px;line-height:1.5;white-space:pre-wrap">{contact.message}</div>
  </div>

  <div style="padding:16px 24px;border-top:1px solid #e5e7eb;font-size:11px;color:#9ca3af">
    Solicitud #{contact.id} · {contact.created_at}
  </div>
</div>
</body></html>"""


def send_contact_notification(contact: ContactRequest, business: Business) -> bool:
    """Email to the business notification address on new contact submissions."""
    to_email = business.contact_notification_email or business.email
    if not to_email:
        return False
    return _send_email(
        to_emails=[to_email],
        subject=_build_contact_subject(contact, business),
        body_text=_build_contact_text(contact, business),
        body_html=_build_contact_html(contact, business),
    )


# ── Quota warning notification (80% reached) ─────────────────────────────


def _build_quota_subject(business: Business, pct: int) -> str:
    return f"[{business.name}] Tu chatbot está al {pct}% de la cuota mensual"


def _build_quota_text(business: Business, used: int, quota: int, pct: int) -> str:
    remaining = max(0, quota - used)
    return f"""El chatbot de {business.name} ha consumido el {pct}% de su cuota mensual de tokens.

Consumo: {used:,} / {quota:,} tokens  (~{remaining:,} tokens restantes).

Si se alcanza el 100%, el chat con IA se pausa automáticamente hasta el primer día del mes siguiente. Los botones (llamar, mapa, carta, etc.) y el formulario de contacto siguen activos.

Para evitar el corte puedes:
- Ampliar el plan (más mensajes incluidos al mes)
- Contratar un pack de mensajes extra para este mes
- Contactar con el operador de la plataforma

Consulta el consumo detallado en tu panel de administración.
"""


def _build_quota_html(business: Business, used: int, quota: int, pct: int) -> str:
    remaining = max(0, quota - used)
    bar_color = "#dc2626" if pct >= 90 else "#f59e0b" if pct >= 70 else "#10b981"
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/></head>
<body style="font-family:-apple-system,sans-serif;background:#f4f4f5;padding:32px">
<div style="max-width:540px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.06)">

  <div style="background:{bar_color};color:#fff;padding:20px 24px">
    <h2 style="margin:0;font-size:18px">⚠️ Cuota mensual al {pct}%</h2>
    <p style="margin:4px 0 0;opacity:.9;font-size:13px">{business.name}</p>
  </div>

  <div style="padding:24px">
    <p style="margin:0 0 12px;font-size:14px;color:#1f2937">
      El chatbot ha consumido <strong>{used:,}</strong> de los <strong>{quota:,}</strong> tokens del mes. Quedan aproximadamente <strong>{remaining:,}</strong>.
    </p>

    <div style="background:#e5e7eb;border-radius:999px;height:10px;overflow:hidden;margin:16px 0">
      <div style="background:{bar_color};height:100%;width:{min(100, pct)}%"></div>
    </div>

    <p style="margin:16px 0 8px;font-size:14px;color:#1f2937"><strong>Si se alcanza el 100%:</strong></p>
    <ul style="margin:4px 0 16px 20px;padding:0;font-size:13px;color:#4b5563;line-height:1.6">
      <li>El chat con IA se pausa hasta el primer día del mes siguiente.</li>
      <li>Los <strong>botones de acción</strong> (llamar, mapa, carta, WhatsApp) siguen activos.</li>
      <li>El <strong>formulario de contacto</strong> sigue activo.</li>
    </ul>

    <p style="margin:16px 0 8px;font-size:14px;color:#1f2937"><strong>Opciones para evitar el corte:</strong></p>
    <ul style="margin:4px 0 0 20px;padding:0;font-size:13px;color:#4b5563;line-height:1.6">
      <li>Ampliar a un plan con más mensajes/mes.</li>
      <li>Contratar un pack de mensajes extra puntual.</li>
      <li>Contactar con el operador de la plataforma.</li>
    </ul>
  </div>

  <div style="padding:16px 24px;border-top:1px solid #e5e7eb;font-size:11px;color:#9ca3af">
    Este aviso se envía una sola vez por mes al superar el 80% de cuota. El contador se reinicia el día 1 de cada mes.
  </div>
</div>
</body></html>"""


def send_quota_warning(
    business: Business,
    used: int,
    quota: int,
    to_emails: list[str],
) -> bool:
    """Fire the 80% quota-reached warning email. Returns True if sent."""
    if quota <= 0:
        return False
    pct = int(round((used / quota) * 100))
    return _send_email(
        to_emails=to_emails,
        subject=_build_quota_subject(business, pct),
        body_text=_build_quota_text(business, used, quota, pct),
        body_html=_build_quota_html(business, used, quota, pct),
    )
