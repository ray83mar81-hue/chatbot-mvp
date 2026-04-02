(function () {
  "use strict";

  /* ── Configuration ─────────────────────────────────────────── */
  const script = document.currentScript;
  const CONFIG = {
    apiUrl: script?.getAttribute("data-api-url") || window.location.origin,
    businessId: parseInt(script?.getAttribute("data-business-id") || "1", 10),
    primaryColor: script?.getAttribute("data-primary-color") || "#2563eb",
    title: script?.getAttribute("data-title") || "Chat",
    subtitle: script?.getAttribute("data-subtitle") || "Te responderemos al instante",
    placeholder:
      script?.getAttribute("data-placeholder") || "Escribe tu mensaje...",
    position: script?.getAttribute("data-position") || "right", // "right" | "left"
    welcomeMessage:
      script?.getAttribute("data-welcome") ||
      "Hola! En que puedo ayudarte?",
  };

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

  /* ── Styles ────────────────────────────────────────────────── */
  const css = `
    .cw-root, .cw-root * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }

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
      width: 380px; max-width: calc(100vw - 32px);
      height: 520px; max-height: calc(100vh - 120px);
      border-radius: 16px; overflow: hidden;
      background: #fff; display: flex; flex-direction: column;
      box-shadow: 0 8px 32px rgba(0,0,0,.18);
      opacity: 0; transform: translateY(16px) scale(.96);
      transition: opacity .25s, transform .25s;
      pointer-events: none;
    }
    .cw-window.cw-open { opacity: 1; transform: translateY(0) scale(1); pointer-events: auto; }

    /* Header */
    .cw-header {
      background: ${CONFIG.primaryColor}; color: #fff;
      padding: 16px 20px; display: flex; align-items: center; gap: 12px; flex-shrink: 0;
    }
    .cw-header-avatar {
      width: 40px; height: 40px; border-radius: 50%;
      background: rgba(255,255,255,.2); display: flex; align-items: center; justify-content: center;
    }
    .cw-header-avatar svg { width: 22px; height: 22px; fill: #fff; }
    .cw-header-info h3 { font-size: 15px; font-weight: 600; }
    .cw-header-info p  { font-size: 12px; opacity: .85; margin-top: 2px; }
    .cw-close {
      margin-left: auto; background: none; border: none; color: #fff;
      cursor: pointer; padding: 4px; border-radius: 6px; display: flex;
    }
    .cw-close:hover { background: rgba(255,255,255,.15); }
    .cw-close svg { width: 20px; height: 20px; fill: currentColor; }

    /* Messages area */
    .cw-messages {
      flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 10px;
      background: #f7f8fa;
    }
    .cw-messages::-webkit-scrollbar { width: 5px; }
    .cw-messages::-webkit-scrollbar-thumb { background: #ccc; border-radius: 4px; }

    .cw-msg { max-width: 82%; padding: 10px 14px; border-radius: 14px; font-size: 14px; line-height: 1.45; word-wrap: break-word; }
    .cw-msg-bot { background: #fff; color: #1a1a1a; align-self: flex-start; border-bottom-left-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,.06); }
    .cw-msg-user { background: ${CONFIG.primaryColor}; color: #fff; align-self: flex-end; border-bottom-right-radius: 4px; }

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
  `;

  /* ── HTML ───────────────────────────────────────────────────── */
  const ICON_CHAT = `<svg viewBox="0 0 24 24"><path d="M20 2H4a2 2 0 0 0-2 2v18l4-4h14a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2zm0 14H5.17L4 17.17V4h16v12z"/><path d="M7 9h10v2H7zm0-3h10v2H7z"/></svg>`;
  const ICON_CLOSE = `<svg viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>`;
  const ICON_SEND = `<svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>`;
  const ICON_BOT = `<svg viewBox="0 0 24 24"><path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7h1a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-1.07A7 7 0 0 1 14 23h-4a7 7 0 0 1-6.93-4H2a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1h1a7 7 0 0 1 7-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 0 1 2-2zm-4 13a2 2 0 1 0 0 4 2 2 0 0 0 0-4zm8 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4z"/></svg>`;

  /* ── Mount ──────────────────────────────────────────────────── */
  const root = document.createElement("div");
  root.className = "cw-root";
  root.innerHTML = `
    <style>${css}</style>
    <button class="cw-bubble" aria-label="Abrir chat">${ICON_CHAT}</button>
    <div class="cw-window">
      <div class="cw-header">
        <div class="cw-header-avatar">${ICON_BOT}</div>
        <div class="cw-header-info">
          <h3>${CONFIG.title}</h3>
          <p>${CONFIG.subtitle}</p>
        </div>
        <button class="cw-close" aria-label="Cerrar chat">${ICON_CLOSE}</button>
      </div>
      <div class="cw-messages"></div>
      <div class="cw-input-area">
        <input class="cw-input" type="text" placeholder="${CONFIG.placeholder}" autocomplete="off" />
        <button class="cw-send" aria-label="Enviar" disabled>${ICON_SEND}</button>
      </div>
      <div class="cw-powered">Powered by Chatbot MVP</div>
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

  let isOpen = false;
  let isSending = false;

  /* ── Helpers ────────────────────────────────────────────────── */
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
  }

  function showTyping() {
    const el = document.createElement("div");
    el.className = "cw-typing";
    el.id = "cw-typing";
    el.innerHTML = "<span></span><span></span><span></span>";
    messagesEl.appendChild(el);
    scrollBottom();
  }

  function hideTyping() {
    const el = document.getElementById("cw-typing");
    if (el) el.remove();
  }

  function toggleOpen() {
    isOpen = !isOpen;
    window_.classList.toggle("cw-open", isOpen);
    if (isOpen) {
      input.focus();
      scrollBottom();
    }
  }

  /* ── API ────────────────────────────────────────────────────── */
  async function sendMessage(text) {
    if (isSending || !text.trim()) return;
    isSending = true;
    sendBtn.disabled = true;

    addMessage(text, "user");
    input.value = "";
    showTyping();

    try {
      const res = await fetch(`${CONFIG.apiUrl}/chat/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text.trim(),
          session_id: getSessionId(),
          business_id: CONFIG.businessId,
        }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      hideTyping();
      addMessage(data.response, "bot");
    } catch (err) {
      hideTyping();
      addMessage("Lo siento, hubo un error de conexion. Intenta de nuevo.", "bot");
      console.error("[ChatWidget]", err);
    } finally {
      isSending = false;
      sendBtn.disabled = !input.value.trim();
      input.focus();
    }
  }

  /* ── Events ─────────────────────────────────────────────────── */
  bubble.addEventListener("click", toggleOpen);
  closeBtn.addEventListener("click", toggleOpen);

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

  /* ── Welcome message ────────────────────────────────────────── */
  if (CONFIG.welcomeMessage) {
    addMessage(CONFIG.welcomeMessage, "bot");
  }
})();
