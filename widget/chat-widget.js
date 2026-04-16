(function () {
  "use strict";

  /* ── Configuration ─────────────────────────────────────────── */
  const script = document.currentScript;
  const CONFIG = {
    apiUrl: script?.getAttribute("data-api-url") || window.location.origin,
    businessId: parseInt(script?.getAttribute("data-business-id") || "1", 10),
    primaryColor: script?.getAttribute("data-primary-color") || "#2563eb",
    title: script?.getAttribute("data-title") || "Chat",
    subtitle: script?.getAttribute("data-subtitle") || "",
    position: script?.getAttribute("data-position") || "right", // "right" | "left"
    welcomeMessage: script?.getAttribute("data-welcome") || "",
    width: script?.getAttribute("data-width") || "380",
    height: script?.getAttribute("data-height") || "540",
    bubbleEmoji: script?.getAttribute("data-bubble-emoji") || "",
    bubbleImage: script?.getAttribute("data-bubble-image") || "",
    // Force a specific language on startup (overrides navigator.language).
    // Used by the hosted landing page so the widget matches the page language.
    forceLang: (script?.getAttribute("data-force-lang") || "").toLowerCase(),
    headerAvatarType: "default",
    headerAvatarEmoji: "",
    headerAvatarImage: "",
  };

  // Fetch design from backend synchronously so CSS/HTML are generated with the
  // admin-configured values. Falls back to data-* attributes if backend is down.
  try {
    const xhr = new XMLHttpRequest();
    xhr.open("GET", `${CONFIG.apiUrl}/business/${CONFIG.businessId}/languages`, false);
    xhr.send();
    if (xhr.status === 200) {
      const data = JSON.parse(xhr.responseText);
      const d = data.widget_design || {};
      if (d.color) CONFIG.primaryColor = d.color;
      if (d.position) CONFIG.position = d.position;
      if (d.width) CONFIG.width = String(d.width);
      if (d.height) CONFIG.height = String(d.height);
      if (d.bubble_emoji) CONFIG.bubbleEmoji = d.bubble_emoji;
      if (d.bubble_image) CONFIG.bubbleImage = d.bubble_image;
      if (d.icon_type === "default") { CONFIG.bubbleEmoji = ""; CONFIG.bubbleImage = ""; }
      if (d.header_avatar_type) CONFIG.headerAvatarType = d.header_avatar_type;
      if (d.header_avatar_emoji) CONFIG.headerAvatarEmoji = d.header_avatar_emoji;
      if (d.header_avatar_image) CONFIG.headerAvatarImage = d.header_avatar_image;
      // Cache the fetched payload so init() doesn't refetch
      window.__cwBootstrap = data;
    }
  } catch (e) { /* backend unavailable — use data-* attributes */ }

  /* ── i18n: hardcoded UI strings ────────────────────────────── */
  const I18N = {
    es: {
      placeholder: "Escribe tu mensaje...", typing: "Escribiendo...",
      welcome: "Hola, ¿en qué puedo ayudarte?",
      error: "Lo siento, hubo un error de conexión. Inténtalo de nuevo.",
      genericError: "Lo siento, no pude procesar tu mensaje.",
      languagePickerTitle: "Selecciona tu idioma", changeLanguage: "Cambiar idioma",
      subtitleDefault: "Te responderemos al instante",
      contactBtn: "Contacto", contactTitle: "Solicitar contacto", contactBack: "Volver al chat",
      contactName: "Nombre", contactPhone: "Teléfono", contactEmail: "Email",
      contactMessage: "Mensaje", contactSend: "Enviar solicitud",
      contactWaConsent: "Acepto la comunicación por WhatsApp",
      contactPrivacy: "He leído y acepto la", contactPrivacyLink: "política de privacidad",
      contactSuccess: "Solicitud enviada correctamente. Nos pondremos en contacto pronto.",
      contactError: "Error al enviar. Inténtalo de nuevo.",
      contactRequired: "Completa todos los campos obligatorios.",
      contactPrivacyRequired: "Debes aceptar la política de privacidad.",
      contactRateLimit: "Has enviado demasiadas solicitudes. Inténtalo más tarde.",
    },
    en: {
      placeholder: "Type your message...", typing: "Typing...",
      welcome: "Hi! How can I help you?",
      error: "Sorry, there was a connection error. Please try again.",
      genericError: "Sorry, I couldn't process your message.",
      languagePickerTitle: "Choose your language", changeLanguage: "Change language",
      subtitleDefault: "We'll reply right away",
      contactBtn: "Contact", contactTitle: "Request contact", contactBack: "Back to chat",
      contactName: "Name", contactPhone: "Phone", contactEmail: "Email",
      contactMessage: "Message", contactSend: "Send request",
      contactWaConsent: "I agree to be contacted via WhatsApp",
      contactPrivacy: "I have read and accept the", contactPrivacyLink: "privacy policy",
      contactSuccess: "Request sent successfully. We'll get back to you soon.",
      contactError: "Error sending request. Please try again.",
      contactRequired: "Please fill in all required fields.",
      contactPrivacyRequired: "You must accept the privacy policy.",
      contactRateLimit: "Too many requests. Please try again later.",
    },
    ca: {
      placeholder: "Escriu el teu missatge...", typing: "Escrivint...",
      welcome: "Hola! En què et puc ajudar?",
      error: "Hi ha hagut un error de connexió. Torna-ho a provar.",
      genericError: "No he pogut processar el teu missatge.",
      languagePickerTitle: "Selecciona el teu idioma", changeLanguage: "Canviar d'idioma",
      subtitleDefault: "Et respondrem de seguida",
      contactBtn: "Contacte", contactTitle: "Sol·licitar contacte", contactBack: "Tornar al xat",
      contactName: "Nom", contactPhone: "Telèfon", contactEmail: "Email",
      contactMessage: "Missatge", contactSend: "Enviar sol·licitud",
      contactWaConsent: "Accepto la comunicació per WhatsApp",
      contactPrivacy: "He llegit i accepto la", contactPrivacyLink: "política de privacitat",
      contactSuccess: "Sol·licitud enviada. Ens posarem en contacte aviat.",
      contactError: "Error en enviar. Torna-ho a provar.",
      contactRequired: "Completa tots els camps obligatoris.",
      contactPrivacyRequired: "Has d'acceptar la política de privacitat.",
      contactRateLimit: "Massa sol·licituds. Torna-ho a provar més tard.",
    },
    fr: {
      placeholder: "Écrivez votre message...", typing: "En train d'écrire...",
      welcome: "Bonjour ! Comment puis-je vous aider ?",
      error: "Désolé, une erreur de connexion s'est produite. Réessayez.",
      genericError: "Désolé, je n'ai pas pu traiter votre message.",
      languagePickerTitle: "Choisissez votre langue", changeLanguage: "Changer de langue",
      subtitleDefault: "Nous répondrons immédiatement",
      contactBtn: "Contact", contactTitle: "Demande de contact", contactBack: "Retour au chat",
      contactName: "Nom", contactPhone: "Téléphone", contactEmail: "Email",
      contactMessage: "Message", contactSend: "Envoyer la demande",
      contactWaConsent: "J'accepte d'être contacté par WhatsApp",
      contactPrivacy: "J'ai lu et j'accepte la", contactPrivacyLink: "politique de confidentialité",
      contactSuccess: "Demande envoyée. Nous vous contacterons bientôt.",
      contactError: "Erreur d'envoi. Veuillez réessayer.",
      contactRequired: "Veuillez remplir tous les champs obligatoires.",
      contactPrivacyRequired: "Vous devez accepter la politique de confidentialité.",
      contactRateLimit: "Trop de demandes. Veuillez réessayer plus tard.",
    },
    de: {
      placeholder: "Schreiben Sie Ihre Nachricht...", typing: "Schreibt...",
      welcome: "Hallo! Wie kann ich Ihnen helfen?",
      error: "Es gab einen Verbindungsfehler. Bitte versuchen Sie es erneut.",
      genericError: "Entschuldigung, ich konnte Ihre Nachricht nicht verarbeiten.",
      languagePickerTitle: "Wählen Sie Ihre Sprache", changeLanguage: "Sprache ändern",
      subtitleDefault: "Wir antworten sofort",
      contactBtn: "Kontakt", contactTitle: "Kontakt anfordern", contactBack: "Zurück zum Chat",
      contactName: "Name", contactPhone: "Telefon", contactEmail: "Email",
      contactMessage: "Nachricht", contactSend: "Anfrage senden",
      contactWaConsent: "Ich stimme der Kontaktaufnahme über WhatsApp zu",
      contactPrivacy: "Ich habe die", contactPrivacyLink: "Datenschutzrichtlinie gelesen und akzeptiere sie",
      contactSuccess: "Anfrage gesendet. Wir melden uns bald.",
      contactError: "Fehler beim Senden. Bitte erneut versuchen.",
      contactRequired: "Bitte füllen Sie alle Pflichtfelder aus.",
      contactPrivacyRequired: "Sie müssen die Datenschutzrichtlinie akzeptieren.",
      contactRateLimit: "Zu viele Anfragen. Bitte versuchen Sie es später erneut.",
    },
    it: {
      placeholder: "Scrivi il tuo messaggio...", typing: "Sta scrivendo...",
      welcome: "Ciao! Come posso aiutarti?",
      error: "Si è verificato un errore di connessione. Riprova.",
      genericError: "Spiacente, non ho potuto elaborare il tuo messaggio.",
      languagePickerTitle: "Seleziona la tua lingua", changeLanguage: "Cambia lingua",
      subtitleDefault: "Ti risponderemo subito",
      contactBtn: "Contatto", contactTitle: "Richiedi contatto", contactBack: "Torna alla chat",
      contactName: "Nome", contactPhone: "Telefono", contactEmail: "Email",
      contactMessage: "Messaggio", contactSend: "Invia richiesta",
      contactWaConsent: "Accetto di essere contattato tramite WhatsApp",
      contactPrivacy: "Ho letto e accetto la", contactPrivacyLink: "informativa sulla privacy",
      contactSuccess: "Richiesta inviata. Ti contatteremo presto.",
      contactError: "Errore nell'invio. Riprova.",
      contactRequired: "Compila tutti i campi obbligatori.",
      contactPrivacyRequired: "Devi accettare l'informativa sulla privacy.",
      contactRateLimit: "Troppe richieste. Riprova più tardi.",
    },
    pt: {
      placeholder: "Escreva sua mensagem...", typing: "A escrever...",
      welcome: "Olá! Como posso ajudar?",
      error: "Houve um erro de ligação. Tente novamente.",
      genericError: "Desculpe, não consegui processar a sua mensagem.",
      languagePickerTitle: "Selecione o seu idioma", changeLanguage: "Mudar idioma",
      subtitleDefault: "Responderemos imediatamente",
      contactBtn: "Contacto", contactTitle: "Solicitar contacto", contactBack: "Voltar ao chat",
      contactName: "Nome", contactPhone: "Telefone", contactEmail: "Email",
      contactMessage: "Mensagem", contactSend: "Enviar pedido",
      contactWaConsent: "Aceito ser contactado por WhatsApp",
      contactPrivacy: "Li e aceito a", contactPrivacyLink: "política de privacidade",
      contactSuccess: "Pedido enviado. Entraremos em contacto brevemente.",
      contactError: "Erro ao enviar. Tente novamente.",
      contactRequired: "Preencha todos os campos obrigatórios.",
      contactPrivacyRequired: "Deve aceitar a política de privacidade.",
      contactRateLimit: "Demasiados pedidos. Tente novamente mais tarde.",
    },
  };

  function t(key) {
    const lang = state.currentLang || "es";
    // Backend overrides take priority over hardcoded I18N
    const override = contactI18nOverrides[lang] && contactI18nOverrides[lang][key];
    if (override) return override;
    return (I18N[lang] && I18N[lang][key]) || I18N.es[key] || key;
  }

  function flagHtml(code) {
    const url = `${CONFIG.apiUrl}/flags/${code}.svg`;
    return `<img src="${url}" alt="${code}" onerror="this.style.display='none'" />`;
  }

  /* ── Session ───────────────────────────────────────────────── */
  const SESSION_KEY = "chatbot_session_id";
  function getSessionId() {
    let id = sessionStorage.getItem(SESSION_KEY);
    if (!id) {
      id = "s_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
      sessionStorage.setItem(SESSION_KEY, id);
    }
    return id;
  }

  /* ── Runtime state ─────────────────────────────────────────── */
  const state = {
    currentLang: "es",
    supportedLangs: [],          // [{code, name, native_name, flag_emoji, ...}]
    welcomeMessages: {},          // {lang_code: text}
    defaultLang: "es",
    initialized: false,
  };

  /* ── Styles ────────────────────────────────────────────────── */
  const css = `
    .cw-root, .cw-root * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
    .cw-root [hidden] { display: none !important; }

    /* Bubble */
    .cw-bubble {
      position: fixed; bottom: 24px; ${CONFIG.position}: 24px; z-index: 99999;
      width: 60px; height: 60px; border-radius: 50%;
      background: ${CONFIG.primaryColor}; color: #fff;
      display: flex; align-items: center; justify-content: center;
      cursor: pointer; box-shadow: 0 4px 16px rgba(0,0,0,.2);
      transition: transform .2s, box-shadow .2s;
      border: none; outline: none;
    }
    .cw-bubble:hover { transform: scale(1.08); box-shadow: 0 6px 24px rgba(0,0,0,.25); }
    .cw-bubble svg { width: 28px; height: 28px; fill: currentColor; }

    /* Window */
    .cw-window {
      position: fixed; bottom: 96px; ${CONFIG.position}: 24px; z-index: 99999;
      width: ${CONFIG.width}px; max-width: calc(100vw - 32px);
      height: ${CONFIG.height}px; max-height: calc(100dvh - 120px);
      border-radius: 16px; overflow: hidden;
      background: #fff; display: flex; flex-direction: column;
      box-shadow: 0 8px 32px rgba(0,0,0,.18);
      opacity: 0; transform: translateY(16px) scale(.96);
      transition: opacity .25s, transform .25s;
      pointer-events: none;
    }
    .cw-window.cw-open { opacity: 1; transform: translateY(0) scale(1); pointer-events: auto; }
    /* On phones, take (almost) the full screen so the keyboard doesn't cover
       the input when it pops up. The visualViewport listener further below
       refines the height when the keyboard is actually showing. */
    @media (max-width: 600px) {
      .cw-window {
        width: 100vw; height: 100dvh; max-width: 100vw; max-height: 100dvh;
        bottom: 0; ${CONFIG.position}: 0; border-radius: 0;
      }
      .cw-bubble { bottom: 16px; ${CONFIG.position}: 16px; }
      /* Extra breathing room above the keyboard when the input is focused */
      .cw-input-area { padding: 12px 16px 18px; }
    }

    /* Header */
    .cw-header {
      background: ${CONFIG.primaryColor}; color: #fff;
      padding: 14px 16px; display: flex; align-items: center; gap: 10px; flex-shrink: 0;
    }
    .cw-header-avatar {
      width: 40px; height: 40px; border-radius: 50%;
      background: rgba(255,255,255,.2); display: flex; align-items: center; justify-content: center;
      flex-shrink: 0;
    }
    .cw-header-avatar svg { width: 22px; height: 22px; fill: #fff; }
    .cw-header-info { flex: 1; min-width: 0; }
    .cw-header-info h3 { font-size: 15px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .cw-header-info p  { font-size: 12px; opacity: .85; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

    /* Header buttons */
    .cw-header-btn {
      background: none; border: none; color: #fff;
      cursor: pointer; padding: 6px; border-radius: 6px; display: flex; align-items: center; justify-content: center;
      flex-shrink: 0;
    }
    .cw-header-btn:hover { background: rgba(255,255,255,.18); }
    .cw-header-btn svg { width: 18px; height: 18px; fill: currentColor; }

    /* Language switcher */
    .cw-lang-wrap { position: relative; }
    .cw-lang-btn {
      background: rgba(255,255,255,.18) !important;
      padding: 6px 10px !important;
      gap: 6px;
      min-height: 32px;
      font-weight: 600;
      font-size: 13px;
    }
    .cw-lang-btn:hover { background: rgba(255,255,255,.30) !important; }
    .cw-lang-flag { font-size: 20px; line-height: 1; display: inline-flex; align-items: center; }
    .cw-lang-flag img { width: 20px; height: 14px; object-fit: cover; border-radius: 2px; vertical-align: middle; }
    .cw-lang-code { color: #fff; letter-spacing: .5px; }
    .cw-lang-caret { font-size: 10px; opacity: .8; line-height: 1; }
    .cw-lang-menu {
      position: absolute; top: calc(100% + 6px); right: 0;
      background: #fff; color: #1a1a1a;
      border-radius: 10px; box-shadow: 0 8px 24px rgba(0,0,0,.18);
      min-width: 180px; padding: 6px; z-index: 10;
      max-height: 280px; overflow-y: auto;
      display: none;
    }
    .cw-lang-menu.cw-open { display: block; }
    .cw-lang-option {
      width: 100%; text-align: left; background: none; border: none;
      padding: 8px 10px; border-radius: 6px; cursor: pointer;
      display: flex; align-items: center; gap: 10px; font-size: 14px;
      color: #1a1a1a;
    }
    .cw-lang-option:hover { background: #f0f2f5; }
    .cw-lang-option.cw-active { background: #eef2ff; font-weight: 600; }
    .cw-lang-option-flag { font-size: 18px; line-height: 1; flex-shrink: 0; display: inline-flex; align-items: center; }
    .cw-lang-option-flag img { width: 22px; height: 16px; object-fit: cover; border-radius: 2px; }

    /* Messages area */
    .cw-messages {
      flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 10px;
      background: #f7f8fa;
    }
    .cw-messages::-webkit-scrollbar { width: 5px; }
    .cw-messages::-webkit-scrollbar-thumb { background: #ccc; border-radius: 4px; }

    .cw-msg { max-width: 82%; padding: 10px 14px; border-radius: 14px; font-size: 14px; line-height: 1.45; word-wrap: break-word; white-space: pre-wrap; }
    .cw-msg-bot { background: #fff; color: #1a1a1a; align-self: flex-start; border-bottom-left-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,.06); }
    .cw-msg-user { background: ${CONFIG.primaryColor}; color: #fff; align-self: flex-end; border-bottom-right-radius: 4px; }

    /* Intent CTA button */
    .cw-cta {
      align-self: flex-start;
      display: inline-flex; align-items: center; gap: 6px;
      background: ${CONFIG.primaryColor}; color: #fff;
      text-decoration: none;
      padding: 9px 16px; border-radius: 20px; font-size: 13px; font-weight: 500;
      box-shadow: 0 2px 6px rgba(0,0,0,.12);
      transition: transform .15s, box-shadow .15s;
      max-width: 82%;
    }
    .cw-cta:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,.18); }
    .cw-cta::after { content: "→"; font-size: 14px; }

    /* Typing indicator */
    .cw-typing { display: flex; gap: 5px; align-items: center; padding: 10px 14px; align-self: flex-start; }
    .cw-typing span {
      width: 8px; height: 8px; background: #bbb; border-radius: 50%;
      animation: cw-bounce .6s infinite alternate;
    }
    .cw-typing span:nth-child(2) { animation-delay: .15s; }
    .cw-typing span:nth-child(3) { animation-delay: .3s; }
    @keyframes cw-bounce { to { opacity: .3; transform: translateY(-4px); } }

    /* Input area */
    .cw-input-area {
      display: flex; align-items: center; gap: 8px;
      padding: 12px 16px; border-top: 1px solid #eee; background: #fff; flex-shrink: 0;
    }
    .cw-input {
      flex: 1; border: 1px solid #ddd; border-radius: 24px;
      padding: 10px 16px; font-size: 14px; outline: none;
      transition: border-color .2s;
    }
    .cw-input:focus { border-color: ${CONFIG.primaryColor}; }
    .cw-send {
      width: 40px; height: 40px; border-radius: 50%; border: none;
      background: ${CONFIG.primaryColor}; color: #fff;
      cursor: pointer; display: flex; align-items: center; justify-content: center;
      transition: opacity .2s; flex-shrink: 0;
    }
    .cw-send:disabled { opacity: .5; cursor: not-allowed; }
    .cw-send svg { width: 18px; height: 18px; fill: currentColor; }

    /* Powered by */
    .cw-powered { text-align: center; font-size: 11px; color: #aaa; padding: 6px 0; background: #fff; }

    /* Loading state */
    .cw-loading {
      flex: 1; display: flex; align-items: center; justify-content: center;
      color: #888; font-size: 13px;
    }

    /* ── Contact form view ─────────────────────────── */
    .cw-view-chat, .cw-view-contact { display: flex; flex-direction: column; flex: 1; min-height: 0; }
    .cw-view-contact { display: none; }
    .cw-window.cw-contact-open .cw-view-chat { display: none; }
    .cw-window.cw-contact-open .cw-view-contact { display: flex; }

    .cw-contact-scroll { flex: 1; overflow-y: auto; padding: 16px; }
    .cw-contact-scroll::-webkit-scrollbar { width: 5px; }
    .cw-contact-scroll::-webkit-scrollbar-thumb { background: #ccc; border-radius: 4px; }

    .cw-contact-back {
      background: none; border: none; color: ${CONFIG.primaryColor};
      font-size: 13px; font-weight: 600; cursor: pointer; padding: 0;
      display: flex; align-items: center; gap: 4px; margin-bottom: 12px;
    }
    .cw-contact-back:hover { text-decoration: underline; }

    .cw-contact-title { font-size: 16px; font-weight: 700; color: #1f2937; margin-bottom: 16px; }

    .cw-field { margin-bottom: 14px; }
    .cw-field label { display: block; font-size: 12px; font-weight: 600; color: #374151; margin-bottom: 5px; }
    .cw-field input, .cw-field textarea {
      width: 100%; padding: 9px 12px; border: 1px solid #d1d5db; border-radius: 8px;
      font-size: 14px; outline: none; transition: border-color .2s; background: #fff; color: #1f2937;
    }
    .cw-field input:focus, .cw-field textarea:focus { border-color: ${CONFIG.primaryColor}; }
    .cw-field textarea { resize: vertical; min-height: 60px; }

    .cw-phone-row { display: flex; gap: 8px; align-items: flex-start; }
    .cw-phone-row .cw-field { flex: 1; }

    .cw-wa-row {
      display: flex; align-items: center; gap: 8px; margin-bottom: 14px;
      font-size: 13px; color: #374151;
    }
    .cw-wa-row input[type=checkbox] { width: 16px; height: 16px; accent-color: ${CONFIG.primaryColor}; flex-shrink: 0; margin: 0; }

    .cw-privacy-row {
      display: flex; align-items: flex-start; gap: 8px; margin-bottom: 14px;
      font-size: 12px; color: #6b7280; line-height: 1.4;
    }
    .cw-privacy-row input[type=checkbox] { width: 16px; height: 16px; accent-color: ${CONFIG.primaryColor}; flex-shrink: 0; margin-top: 1px; }
    .cw-privacy-row a { color: ${CONFIG.primaryColor}; text-decoration: underline; }

    .cw-contact-submit {
      width: 100%; padding: 11px; border: none; border-radius: 10px;
      background: ${CONFIG.primaryColor}; color: #fff;
      font-size: 14px; font-weight: 600; cursor: pointer;
      transition: opacity .2s;
    }
    .cw-contact-submit:disabled { opacity: .5; cursor: not-allowed; }

    .cw-contact-msg {
      margin-top: 10px; padding: 10px 12px; border-radius: 8px;
      font-size: 13px; line-height: 1.4;
    }
    .cw-contact-msg-ok { background: #d1fae5; color: #065f46; }
    .cw-contact-msg-err { background: #fee2e2; color: #991b1b; }

    /* Honeypot (invisible to humans) */
    .cw-hp { position: absolute; left: -9999px; opacity: 0; height: 0; width: 0; overflow: hidden; }

    /* Contact button in header */
    .cw-contact-hdr-btn {
      background: rgba(255,255,255,.18) !important;
      border-radius: 6px !important;
      padding: 6px 10px !important;
      font-size: 12px; font-weight: 600;
      gap: 4px;
    }
    .cw-contact-hdr-btn:hover { background: rgba(255,255,255,.30) !important; }
    .cw-contact-hdr-btn svg { width: 14px; height: 14px; }
  `;

  /* ── Icons ────────────────────────────────────────────────── */
  const ICON_CHAT = `<svg viewBox="0 0 24 24"><path d="M20 2H4a2 2 0 0 0-2 2v18l4-4h14a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2zm0 14H5.17L4 17.17V4h16v12z"/><path d="M7 9h10v2H7zm0-3h10v2H7z"/></svg>`;
  const ICON_CLOSE = `<svg viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>`;
  const ICON_SEND = `<svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>`;
  const ICON_BOT = `<svg viewBox="0 0 24 24"><path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7h1a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-1.07A7 7 0 0 1 14 23h-4a7 7 0 0 1-6.93-4H2a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1h1a7 7 0 0 1 7-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 0 1 2-2zm-4 13a2 2 0 1 0 0 4 2 2 0 0 0 0-4zm8 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4z"/></svg>`;

  /* ── Mount ──────────────────────────────────────────────────── */
  const root = document.createElement("div");
  root.className = "cw-root";
  root.innerHTML = `
    <style>${css}</style>
    <button class="cw-bubble" aria-label="${CONFIG.title}">${
      CONFIG.bubbleImage
        ? `<img src="${CONFIG.bubbleImage}" style="width:32px;height:32px;border-radius:50%;object-fit:cover" alt="" />`
        : CONFIG.bubbleEmoji
          ? `<span style="font-size:28px">${CONFIG.bubbleEmoji}</span>`
          : ICON_CHAT
    }</button>
    <div class="cw-window">
      <div class="cw-header">
        <div class="cw-header-avatar">${
          CONFIG.headerAvatarType === "image" && CONFIG.headerAvatarImage
            ? `<img src="${escapeHtml(CONFIG.headerAvatarImage)}" alt="" style="width:100%;height:100%;border-radius:50%;object-fit:cover" />`
            : CONFIG.headerAvatarType === "emoji" && CONFIG.headerAvatarEmoji
              ? `<span style="font-size:22px">${CONFIG.headerAvatarEmoji}</span>`
              : ICON_BOT
        }</div>
        <div class="cw-header-info">
          <h3>${escapeHtml(CONFIG.title)}</h3>
          <p class="cw-subtitle">${escapeHtml(CONFIG.subtitle)}</p>
        </div>
        <div class="cw-lang-wrap" hidden>
          <button class="cw-header-btn cw-lang-btn" type="button" aria-label="Language">
            <span class="cw-lang-flag">🌐</span>
            <span class="cw-lang-code">--</span>
            <span class="cw-lang-caret">▼</span>
          </button>
          <div class="cw-lang-menu" role="menu"></div>
        </div>
        <button class="cw-header-btn cw-contact-hdr-btn" type="button" hidden>
          <svg viewBox="0 0 24 24"><path fill="currentColor" d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/></svg>
          <span class="cw-contact-hdr-label"></span>
        </button>
        <button class="cw-header-btn cw-close" type="button" aria-label="Close">${ICON_CLOSE}</button>
      </div>
      <!-- Chat view -->
      <div class="cw-view-chat">
        <div class="cw-messages"></div>
        <div class="cw-input-area">
          <input class="cw-input" type="text" autocomplete="off" />
          <button class="cw-send" type="button" aria-label="Send" disabled>${ICON_SEND}</button>
        </div>
      </div>
      <!-- Contact form view -->
      <div class="cw-view-contact">
        <div class="cw-contact-scroll">
          <button class="cw-contact-back" type="button"></button>
          <div class="cw-contact-title"></div>
          <form class="cw-contact-form" novalidate>
            <div class="cw-field"><label class="cw-cf-name-label"></label><input name="name" type="text" required maxlength="120" /></div>
            <div class="cw-field"><label class="cw-cf-phone-label"></label><input name="phone" type="tel" required maxlength="30" /></div>
            <div class="cw-wa-row" hidden>
              <input name="whatsapp_opt_in" type="checkbox" value="1" />
              <span class="cw-cf-wa-label"></span>
            </div>
            <div class="cw-field"><label class="cw-cf-email-label"></label><input name="email" type="email" required maxlength="160" /></div>
            <div class="cw-field"><label class="cw-cf-msg-label"></label><textarea name="message" rows="3" required maxlength="1000"></textarea></div>
            <input class="cw-hp" name="website" type="text" tabindex="-1" autocomplete="off" />
            <div class="cw-privacy-row">
              <input name="privacy" type="checkbox" required />
              <span class="cw-cf-privacy-text"></span>
            </div>
            <button class="cw-contact-submit" type="submit"></button>
            <div class="cw-contact-feedback"></div>
          </form>
        </div>
      </div>
      <div class="cw-powered">Powered by DPB Andorra</div>
    </div>
  `;
  document.body.appendChild(root);

  /* ── DOM refs ───────────────────────────────────────────────── */
  const bubble = root.querySelector(".cw-bubble");
  const window_ = root.querySelector(".cw-window");
  const closeBtn = root.querySelector(".cw-close");
  const messagesEl = root.querySelector(".cw-messages");
  const input = root.querySelector(".cw-input");
  const sendBtn = root.querySelector(".cw-send");
  const titleEl = root.querySelector(".cw-header-info h3");
  const subtitleEl = root.querySelector(".cw-subtitle");
  const langWrap = root.querySelector(".cw-lang-wrap");
  const langBtn = root.querySelector(".cw-lang-btn");
  const langFlagEl = root.querySelector(".cw-lang-flag");
  const langCodeEl = root.querySelector(".cw-lang-code");
  const langMenu = root.querySelector(".cw-lang-menu");

  // Contact form
  const contactHdrBtn = root.querySelector(".cw-contact-hdr-btn");
  const contactHdrLabel = root.querySelector(".cw-contact-hdr-label");
  const contactBackBtn = root.querySelector(".cw-contact-back");
  const contactTitle = root.querySelector(".cw-contact-title");
  const contactForm = root.querySelector(".cw-contact-form");
  const contactSubmitBtn = root.querySelector(".cw-contact-submit");
  const contactFeedback = root.querySelector(".cw-contact-feedback");
  const contactWaRow = root.querySelector(".cw-wa-row");

  let isOpen = false;
  let isSending = false;
  let welcomeShown = false;
  let contactConfig = null; // fetched from /business/{id}/contact-config
  let contactI18nOverrides = {}; // {lang_code: {key: value}} from backend

  /* ── Helpers ────────────────────────────────────────────────── */
  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function scrollBottom() {
    requestAnimationFrame(() => {
      messagesEl.scrollTop = messagesEl.scrollHeight;
    });
  }

  function addMessage(text, role) {
    const div = document.createElement("div");
    div.className = `cw-msg cw-msg-${role}`;
    div.textContent = text;
    messagesEl.appendChild(div);
    scrollBottom();
    return div;
  }

  function addCtaButton(button) {
    if (!button || !button.url || !button.label) return;
    const a = document.createElement("a");
    a.className = "cw-cta";
    a.textContent = button.label;
    a.href = button.url;
    if (button.open_new_tab !== false) {
      a.target = "_blank";
      a.rel = "noopener noreferrer";
    }
    messagesEl.appendChild(a);
    scrollBottom();
  }

  function showTyping() {
    const el = document.createElement("div");
    el.className = "cw-typing";
    el.id = "cw-typing";
    el.setAttribute("aria-label", t("typing"));
    el.innerHTML = "<span></span><span></span><span></span>";
    messagesEl.appendChild(el);
    scrollBottom();
  }

  function hideTyping() {
    const el = document.getElementById("cw-typing");
    if (el) el.remove();
  }

  function clearMessages() {
    messagesEl.innerHTML = "";
    welcomeShown = false;
  }

  function showWelcome() {
    if (welcomeShown) return;
    let welcomeText = "";
    if (state.welcomeMessages && state.welcomeMessages[state.currentLang]) {
      welcomeText = state.welcomeMessages[state.currentLang];
    } else if (CONFIG.welcomeMessage && state.currentLang === state.defaultLang) {
      welcomeText = CONFIG.welcomeMessage;
    } else {
      welcomeText = t("welcome");
    }
    addMessage(welcomeText, "bot");
    welcomeShown = true;
  }

  function applyI18nToUI() {
    // Backend widget_ui_texts take priority over data-* attributes and defaults.
    const ui = (state.widgetUITexts && state.widgetUITexts[state.currentLang]) || {};
    if (ui.title) titleEl.textContent = ui.title;
    else if (CONFIG.title) titleEl.textContent = CONFIG.title;
    if (ui.subtitle) subtitleEl.textContent = ui.subtitle;
    else if (CONFIG.subtitle) subtitleEl.textContent = CONFIG.subtitle;
    else subtitleEl.textContent = t("subtitleDefault");
    input.placeholder = ui.placeholder || t("placeholder");
    closeBtn.setAttribute("aria-label", t("changeLanguage"));
    langBtn.setAttribute("aria-label", t("changeLanguage"));
    langBtn.setAttribute("title", t("changeLanguage"));

    // Contact form labels
    contactHdrLabel.textContent = t("contactBtn");
    contactBackBtn.textContent = "\u2190 " + t("contactBack");
    contactTitle.textContent = t("contactTitle");
    root.querySelector(".cw-cf-name-label").textContent = t("contactName");
    root.querySelector(".cw-cf-phone-label").textContent = t("contactPhone");
    root.querySelector(".cw-cf-email-label").textContent = t("contactEmail");
    root.querySelector(".cw-cf-msg-label").textContent = t("contactMessage");
    root.querySelector(".cw-cf-wa-label").textContent = t("contactWaConsent");
    contactSubmitBtn.textContent = t("contactSend");

    // Privacy with link — per-language URL takes priority
    const privacyText = root.querySelector(".cw-cf-privacy-text");
    const langOverride = contactI18nOverrides[state.currentLang] || {};
    const url = langOverride.privacy_url || (contactConfig && contactConfig.privacy_url) || "";
    if (url) {
      privacyText.innerHTML = `${escapeHtml(t("contactPrivacy"))} <a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(t("contactPrivacyLink"))}</a>`;
    } else {
      privacyText.textContent = t("contactPrivacy") + " " + t("contactPrivacyLink");
    }
  }

  function toggleOpen() {
    isOpen = !isOpen;
    window_.classList.toggle("cw-open", isOpen);
    if (isOpen) {
      if (!welcomeShown) showWelcome();
      input.focus();
      scrollBottom();
    }
  }

  /* ── Language picker ───────────────────────────────────────── */
  function renderLanguageMenu() {
    if (!state.supportedLangs || state.supportedLangs.length <= 1) {
      langWrap.hidden = true;
      return;
    }
    langWrap.hidden = false;

    // Update the visible flag + code
    const current = state.supportedLangs.find((l) => l.code === state.currentLang);
    if (current) {
      langFlagEl.innerHTML = flagHtml(current.code);
      langCodeEl.textContent = current.code.toUpperCase();
    }

    langMenu.innerHTML = "";
    state.supportedLangs.forEach((lang) => {
      const opt = document.createElement("button");
      opt.type = "button";
      opt.className = "cw-lang-option" + (lang.code === state.currentLang ? " cw-active" : "");
      opt.innerHTML = `<span class="cw-lang-option-flag">${flagHtml(lang.code)}</span><span>${escapeHtml(lang.native_name)}</span>`;
      opt.addEventListener("click", () => {
        langMenu.classList.remove("cw-open");
        if (lang.code !== state.currentLang) {
          changeLanguage(lang.code);
        }
      });
      langMenu.appendChild(opt);
    });
  }

  function changeLanguage(code) {
    state.currentLang = code;
    applyI18nToUI();
    renderLanguageMenu();
    clearMessages();
    showWelcome();
  }

  /* ── Init: fetch business languages and pick one ───────────── */
  function pickInitialLanguage(supported, defaultLang) {
    const supportedCodes = supported.map((l) => l.code);
    // data-force-lang wins: used by the landing page to sync chat with the
    // language the visitor is reading the page in.
    if (CONFIG.forceLang && supportedCodes.includes(CONFIG.forceLang)) return CONFIG.forceLang;
    const browserLang = (navigator.language || "").slice(0, 2).toLowerCase();
    if (browserLang && supportedCodes.includes(browserLang)) return browserLang;
    if (supportedCodes.includes(defaultLang)) return defaultLang;
    return supportedCodes[0] || "es";
  }

  async function init() {
    if (state.initialized) return;
    try {
      let data;
      if (window.__cwBootstrap) {
        data = window.__cwBootstrap;
        delete window.__cwBootstrap;
      } else {
        const res = await fetch(`${CONFIG.apiUrl}/business/${CONFIG.businessId}/languages`);
        if (res.ok) data = await res.json();
      }
      if (data) {
        state.supportedLangs = data.supported || [];
        state.welcomeMessages = data.welcome_messages || {};
        state.widgetUITexts = data.widget_ui_texts || {};
        state.defaultLang = data.default_language || "es";
        state.currentLang = pickInitialLanguage(state.supportedLangs, state.defaultLang);
      } else {
        // Fallback if endpoint missing — use defaults
        state.supportedLangs = [{ code: "es", flag_emoji: "🇪🇸", native_name: "Español" }];
        state.currentLang = "es";
        state.defaultLang = "es";
      }
    } catch (e) {
      console.warn("[ChatWidget] Could not fetch languages:", e);
      state.supportedLangs = [{ code: "es", flag_emoji: "🇪🇸", native_name: "Español" }];
      state.currentLang = "es";
      state.defaultLang = "es";
    }
    // Fetch contact form config
    try {
      const cres = await fetch(`${CONFIG.apiUrl}/business/${CONFIG.businessId}/contact-config`);
      if (cres.ok) {
        contactConfig = await cres.json();
        contactI18nOverrides = contactConfig.translations || {};
        if (contactConfig.contact_form_enabled) {
          contactHdrBtn.hidden = false;
          contactWaRow.hidden = !contactConfig.whatsapp_enabled;
        }
      }
    } catch (e) {
      console.warn("[ChatWidget] Could not fetch contact config:", e);
    }

    state.initialized = true;
    applyI18nToUI();
    renderLanguageMenu();
  }

  /* ── API ────────────────────────────────────────────────────── */
  function addBotBubble() {
    const div = document.createElement("div");
    div.className = "cw-msg cw-msg-bot";
    messagesEl.appendChild(div);
    scrollBottom();
    return div;
  }

  async function sendMessage(text) {
    if (isSending || !text.trim()) return;
    if (!state.initialized) await init();
    isSending = true;
    sendBtn.disabled = true;

    addMessage(text, "user");
    input.value = "";
    showTyping();

    const payload = JSON.stringify({
      message: text.trim(),
      session_id: getSessionId(),
      business_id: CONFIG.businessId,
      language: state.currentLang,
    });

    try {
      const res = await fetch(`${CONFIG.apiUrl}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload,
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let botBubble = null;
      let buffer = "";
      let pendingButton = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const event = JSON.parse(line.slice(6));
            if (event.type === "start") {
              hideTyping();
              botBubble = addBotBubble();
            } else if (event.type === "chunk" && botBubble) {
              botBubble.textContent += event.content;
              scrollBottom();
            } else if (event.type === "button") {
              pendingButton = {
                label: event.label,
                url: event.url,
                open_new_tab: event.open_new_tab,
              };
            } else if (event.type === "error") {
              hideTyping();
              addMessage(event.content || t("genericError"), "bot");
            }
          } catch (e) {
            /* skip malformed */
          }
        }
      }

      if (pendingButton) addCtaButton(pendingButton);

      if (!botBubble && !pendingButton) {
        hideTyping();
        addMessage(t("genericError"), "bot");
      }
    } catch (err) {
      hideTyping();
      addMessage(t("error"), "bot");
      console.error("[ChatWidget]", err);
    } finally {
      isSending = false;
      sendBtn.disabled = !input.value.trim();
      input.focus();
    }
  }

  /* ── Contact form ───────────────────────────────────────────── */
  function showContactForm() {
    contactFeedback.innerHTML = "";
    contactForm.reset();
    window_.classList.add("cw-contact-open");
  }

  function hideContactForm() {
    window_.classList.remove("cw-contact-open");
  }

  contactHdrBtn.addEventListener("click", showContactForm);
  contactBackBtn.addEventListener("click", hideContactForm);

  contactForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    contactFeedback.innerHTML = "";

    const fd = new FormData(contactForm);
    const name = (fd.get("name") || "").trim();
    const phone = (fd.get("phone") || "").trim();
    const email = (fd.get("email") || "").trim();
    const message = (fd.get("message") || "").trim();
    const privacy = !!fd.get("privacy");
    const whatsapp = !!fd.get("whatsapp_opt_in");
    const honeypot = (fd.get("website") || "").trim();

    if (!name || !phone || !email || !message) {
      contactFeedback.className = "cw-contact-msg cw-contact-msg-err";
      contactFeedback.textContent = t("contactRequired");
      return;
    }
    if (!privacy) {
      contactFeedback.className = "cw-contact-msg cw-contact-msg-err";
      contactFeedback.textContent = t("contactPrivacyRequired");
      return;
    }

    contactSubmitBtn.disabled = true;
    contactSubmitBtn.textContent = "...";

    try {
      const res = await fetch(`${CONFIG.apiUrl}/contact/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          business_id: CONFIG.businessId,
          session_id: getSessionId(),
          name, phone, email, message,
          language: state.currentLang,
          whatsapp_opt_in: whatsapp,
          privacy_accepted: privacy,
          honeypot: honeypot,
        }),
      });

      if (res.status === 429) {
        contactFeedback.className = "cw-contact-msg cw-contact-msg-err";
        contactFeedback.textContent = t("contactRateLimit");
        return;
      }
      if (!res.ok) throw new Error("HTTP " + res.status);

      contactForm.reset();
      contactFeedback.className = "cw-contact-msg cw-contact-msg-ok";
      contactFeedback.textContent = t("contactSuccess");
    } catch (err) {
      contactFeedback.className = "cw-contact-msg cw-contact-msg-err";
      contactFeedback.textContent = t("contactError");
      console.error("[ChatWidget contact]", err);
    } finally {
      contactSubmitBtn.disabled = false;
      contactSubmitBtn.textContent = t("contactSend");
    }
  });

  /* ── Events ─────────────────────────────────────────────────── */
  bubble.addEventListener("click", async () => {
    if (!state.initialized) await init();
    toggleOpen();
  });
  closeBtn.addEventListener("click", toggleOpen);

  langBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    langMenu.classList.toggle("cw-open");
  });
  document.addEventListener("click", (e) => {
    if (!langWrap.contains(e.target)) {
      langMenu.classList.remove("cw-open");
    }
  });

  input.addEventListener("input", () => {
    sendBtn.disabled = !input.value.trim() || isSending;
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input.value);
    }
  });

  sendBtn.addEventListener("click", () => sendMessage(input.value));

  /* ── Mobile keyboard handling ─────────────────────────────────
     On iOS/Android the on-screen keyboard doesn't resize the layout
     viewport, so a fixed-positioned window ends up with the input
     behind the keyboard. visualViewport reports the area actually
     visible to the user — use it to shrink the window in real time.
  */
  function isMobile() {
    return window.matchMedia("(max-width: 600px)").matches;
  }

  function adjustForKeyboard() {
    if (!isMobile() || !isOpen) return;
    const vv = window.visualViewport;
    if (!vv) return;
    // Anchor the window to the TOP of the visible area (vv.offsetTop accounts
    // for any URL bar offset) with height equal to the visible area. With
    // "bottom: 0" the browser put the widget's bottom behind the keyboard.
    window_.style.top = vv.offsetTop + "px";
    window_.style.bottom = "auto";
    window_.style.height = vv.height + "px";
    // Keep the input scrolled into view once layout settles
    setTimeout(() => {
      if (document.activeElement === input) {
        input.scrollIntoView({ block: "end", behavior: "smooth" });
      }
    }, 50);
  }

  function resetWindowSize() {
    if (!isMobile()) return;
    window_.style.height = "";
    window_.style.top = "";
    window_.style.bottom = "";
  }

  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", adjustForKeyboard);
    window.visualViewport.addEventListener("scroll", adjustForKeyboard);
  }

  input.addEventListener("focus", () => {
    setTimeout(adjustForKeyboard, 100);
  });
  input.addEventListener("blur", () => {
    setTimeout(resetWindowSize, 100);
  });

  /* ── Boot ─────────────────────────────────────────────────── */
  // Pre-fetch languages so the selector is ready before the user opens the bubble
  init();
})();
