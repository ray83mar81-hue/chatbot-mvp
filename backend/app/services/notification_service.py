"""
Email notification service for contact form submissions.

Sends a plain-text + HTML email to the business notification address
when a customer submits the contact form. If SMTP is not configured
(all SMTP_* env vars empty), the send is silently skipped — the contact
request is still saved in the database.
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings
from app.models.business import Business
from app.models.contact_request import ContactRequest


def _smtp_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_FROM)


def _build_subject(contact: ContactRequest, business: Business) -> str:
    return f"[{business.name}] Nueva solicitud de contacto de {contact.name}"


def _build_body_text(contact: ContactRequest, business: Business) -> str:
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


def _build_body_html(contact: ContactRequest, business: Business) -> str:
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


def send_contact_notification(
    contact: ContactRequest, business: Business
) -> bool:
    """
    Send email notification for a new contact request.
    Returns True if sent, False if skipped (SMTP not configured) or failed.
    """
    if not _smtp_configured():
        return False

    to_email = business.contact_notification_email or business.email
    if not to_email:
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = _build_subject(contact, business)
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_email

    msg.attach(MIMEText(_build_body_text(contact, business), "plain", "utf-8"))
    msg.attach(MIMEText(_build_body_html(contact, business), "html", "utf-8"))

    try:
        if settings.SMTP_USE_TLS:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
            server.starttls()
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)

        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)

        server.sendmail(settings.SMTP_FROM, [to_email], msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"[SMTP Error] {type(e).__name__}: {e}")
        return False
