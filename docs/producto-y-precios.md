# Producto y precios · Chatbot MVP

> **Uso de este doc:** referencia interna para preparar la oferta comercial y entender márgenes.
> **Target comercial:** pymes pequeñas (cafeterías, clínicas, tiendas locales, servicios profesionales) con local físico y presencia web. Volumen típico: 500-2000 mensajes/mes por establecimiento.
> **Modelo comercial:** setup absorbido por el operador (gratis para el cliente), cuota mensual o anual, soporte incluido en el precio.

---

## 1. Qué recibe un cliente

### Para el usuario final que visita su web
- **Widget de chat embebible** con una línea de `<script>`. Vive en Shadow DOM, no rompe el CSS de la web del cliente.
- **Chat conversacional con IA** que responde usando la información del negocio (horarios, servicios, FAQs, políticas).
- **Chips de acción fijos** bajo la cabecera del widget: llamar, Google Maps, ver carta, reservar por web, WhatsApp.
- **Selector de idioma** con bandera. Responde en el idioma que elija el usuario final.
- **Formulario de contacto** integrado — el negocio recibe los mensajes por email + quedan guardados en admin.
- **Opcional: página web pública** (`hubdpb.com/negocio/slug`) con datos del negocio + chat embebido + QR para imprimir. Útil para negocios sin web propia.

### Para el dueño del negocio (tenant admin)
- Panel de administración con:
  - Información del negocio (datos básicos + base de conocimiento libre que alimenta la IA).
  - Idiomas soportados (hasta 7 europeos: ES / EN / FR / DE / IT / PT / CA) con traducción IA automática.
  - Textos del widget (título, bienvenida, placeholder) por idioma.
  - Diseño del widget (color, posición, icono, burbuja).
  - Formulario de contacto (campos, textos, email de aviso).
  - Botones de acción (chips).
- **Dashboard** con consumo del mes (mensajes, tokens, coste estimado, tiempo de respuesta medio).
- **Visor de conversaciones** con buscador, filtro por idioma y traducción bajo demanda.
- **Lista de contactos** con estados (nuevo / contactado / cerrado).
- **Gestión de equipo**: invitar otros usuarios como `owner` o `viewer` (solo lectura).
- **Código embed** listo para copiar y pegar.

### Para el operador de la plataforma (superadmin)
- Panel "Plataforma": lista de clientes, métrica global.
- Por tenant: crear, suspender, eliminar, cuota mensual de tokens.
- Configuración de IA por tenant: proveedor (OpenRouter / OpenAI / Anthropic / Gemini / Grok / custom), modelo, API key, precios por millón de tokens. Dropdown dinámico de modelos de OpenRouter.
- Log de incidencias (errores de IA).
- Estadísticas agregadas de los últimos 30 días.

---

## 2. Coste real por cliente / mes

Los tokens son solo una parte. Tabla completa:

| Concepto | Coste mensual por cliente | Notas |
|---|---:|---|
| **Tokens IA** (1000 msgs/mes, gpt-4o-mini) | ~$0.20 | Escala con volumen y modelo, ver tabla abajo |
| **Infraestructura compartida** (DB + contenedor Easypanel) | 0.50-1 € | Despreciable hasta ~30-50 tenants |
| **Pasarela de cobro** (Stripe/Redsys ~1.5% + 0.25€) | 0.70-1.50 € | Sobre una cuota de 40-80€ |
| **Email transaccional** (form contacto) | ~0.10 € | SMTP o Resend |
| **Backups BD compartida** | ~0.05 € | Prorrateado |
| **🕐 Tu tiempo de soporte** | **10-30 €** | El coste dominante, ver apartado 6 |
| **Total realista / cliente / mes** | **12-35 €** | |

### Coste de tokens según modelo y volumen
Un mensaje típico consume ~700 tokens (500 input + 200 output):

| Modelo | Input ($/M) | Output ($/M) | $ / msg | 1000 msgs/mes | 5000 msgs/mes |
|---|---:|---:|---:|---:|---:|
| gemini-2.5-flash | 0.075 | 0.30 | $0.00010 | **$0.10** | **$0.50** |
| gpt-4o-mini | 0.15 | 0.60 | $0.00020 | **$0.20** | **$1.00** |
| claude-haiku-4-5 | 1.00 | 5.00 | $0.00150 | **$1.50** | **$7.50** |
| gpt-4o | 2.50 | 10.00 | $0.00325 | **$3.25** | **$16.25** |
| claude-sonnet-4-5 | 3.00 | 15.00 | $0.00450 | **$4.50** | **$22.50** |

Multiplicar por ~0.92 para EUR.

### Volumen esperado por tipo de negocio
- Cafetería / comercio local pequeño: 300-800 mensajes/mes.
- Clínica / servicios profesionales: 500-1500 mensajes/mes.
- Comercio online pequeño: 1000-3000 mensajes/mes.
- Más de 5000/mes → plan Custom, salirse de packaging estándar.

### Traducciones con IA
Coste puntual ~$0.02-0.05 cada vez que el admin pulsa "Traducir con IA" un set completo. No recurrente, solo cuando actualiza contenido. Incluido en el plan.

---

## 3. Modelo de cobro

**Cuota mensual fija por tier, pagadera mensual o anual.** Razones:

- Pymes prefieren previsibilidad (saber qué pagan cada mes).
- El sistema ya hace enforcement de cuota mensual de tokens — si el cliente se pasa, el chat se pausa hasta fin de mes.
- Setup absorbido por ti: simplifica la venta, reduce fricción, no hay "factura sorpresa".
- Anual con 2 meses gratis: cashflow por adelantado + retención.

Otras opciones descartadas:
- **Usage-based puro**: incertidumbre para el cliente → fricción de venta.
- **Fee único sin recurrente**: cliente sigue consumiendo tokens tuyos sin ingreso recurrente.
- **Revenue share / marca blanca**: otro canal, para cuando tengas partners.

---

## 4. Tiers

### 🟢 Básico · 39 €/mes · 390 €/año (2 meses gratis → 32.50 €/mes equivalente)

**"Chat IA para un local, en su idioma principal."**

- 1 tenant
- **1000 mensajes IA/mes** (al alcanzar cuota, el chat se pausa hasta el mes siguiente)
- **1-2 idiomas**
- Modelo: `gpt-4o-mini` (configurado por operador)
- Hasta **5 botones de acción**
- Widget embebible + formulario de contacto + email de aviso
- Soporte por email, respuesta en 48h laborables
- Retención de conversaciones: 6 meses

**No incluye:** página pública, multi-idioma completo, modelo premium.

**Tu coste real estimado:** ~$0.20 IA + ~12-20€ soporte medio = margen ~45-55%.

### 🔵 Pro · 79 €/mes · 790 €/año (2 meses gratis → 65.80 €/mes)

**"Chat profesional multi-idioma con página pública y modelo premium."**

- 1 tenant
- **5000 mensajes IA/mes**
- **Hasta 7 idiomas** (todos los soportados)
- Modelo premium: `claude-haiku-4-5` (configurado por operador)
- Botones de acción ilimitados
- Widget + formulario + **página pública con QR**
- Traducciones con IA ilimitadas
- Usuarios adicionales del equipo (owners + viewers)
- Soporte por email + WhatsApp, respuesta en 24h laborables
- Retención de conversaciones: 24 meses

**Tu coste real estimado:** ~$7.50 IA + ~15-25€ soporte medio = margen ~65-75%.

### ⚫ Custom · desde 200 €/mes

Para casos >10000 msgs/mes, marca blanca, API propia del cliente, integraciones con su CRM, SLA contractual, etc. **Presupuesto a medida.**

### Add-ons

| Add-on | Precio | Cuándo |
|---|---:|---|
| Pack 1000 mensajes extra (pago único ese mes) | 15 € | Cliente puntualmente desborda la cuota |
| +1 idioma extra sobre el límite del plan | 8 €/mes | Cliente en plan Básico que quiere un 3º idioma |
| Modelo premium (subir a claude-haiku desde gpt-4o-mini) | 20 €/mes | Cliente en Básico que quiere mejor calidad |
| Branding: quitar "Powered by DPB Andorra" | 15 €/mes | Cliente con marca fuerte |
| Integraciones con CRM propio | a medida | Solo en Custom |

---

## 5. Setup

**Gratis para el cliente, lo hace el operador.** Incluye:

- Creación del tenant.
- Rellenado de los datos del negocio + base de conocimiento (la clave para que la IA responda bien).
- Configuración inicial de botones de acción (llamar, mapa, carta, reservar, WhatsApp).
- Traducción inicial a los idiomas del plan.
- Personalización visual del widget (color, icono).
- Generación del código embed + instrucciones de integración.
- 1 sesión de revisión (30 min) la 1ª semana para afinar respuestas.

**Tiempo real que consume:** 1.5-3h para un cliente típico. Absorbido por ti como coste de adquisición — queda amortizado por las primeras 2-3 cuotas mensuales.

**Para acotar esto:** pide al cliente que **mande por email** antes de la alta:
- Horarios exactos
- Dirección + teléfono + email
- Lista de servicios/productos principales
- FAQs típicas que reciben
- URL de carta/reservas si tienen
- Colores corporativos y logo

Si lo envían bien, setup es 1h. Si no, son 3h con varias idas y venidas — el coste lo asumes tú.

---

## 6. Soporte: cómo acotarlo para que no coma el margen

El soporte está **incluido en el precio**, pero hay que acotar expectativas para no perder dinero.

### Qué ES soporte (incluido)
- Dudas sobre cómo usar el panel admin.
- Incidencias técnicas (el chat no carga, el email de contacto no llega, el widget se ve raro).
- Ajustes menores de diseño del widget.
- Revisión trimestral de calidad de respuestas si el cliente lo pide.

### Qué NO es soporte (extra o se factura)
- "Escríbeme las FAQs del chatbot." → Eso es consultoría, se factura aparte (50 €/h).
- "Quiero integrar el chat con mi CRM." → Sale de packaging, es add-on Custom.
- "Cámbiame el widget a 5 idiomas que mi plan no incluye." → Upgrade de plan o add-on.
- "Haz tú las respuestas, no quiero escribir nada." → Consultoría de contenido (tarifa aparte) o plan Custom.

### Tiempo que vas a dedicar realmente (estimación)

| Tipo de cliente | Primer mes | Steady state |
|---|---:|---:|
| **Cliente organizado** (envía info ordenada, entiende el producto) | 1h | 10-20 min/mes |
| **Cliente medio** (algún ajuste, alguna duda recurrente) | 2h | 30-45 min/mes |
| **Cliente difícil** (no lee la docu, cambia requisitos) | 4h | 1-2h/mes |

Regla de oro: **presupuesta 30-45 min/cliente/mes de media en tu cabeza.** Al precio de 40-60 €/h tuyas, son 20-45 € de coste mensual. Con la cuota Básica (39 €) justa sale, con la Pro (79 €) cómoda.

### Cuándo un cliente deja de ser rentable

Si un cliente te consume >3h/mes de soporte durante 2 meses seguidos, hay opciones:

1. Subirle a Pro (si está en Básico) argumentando que su volumen/necesidad lo pide.
2. Cobrar horas extra de consultoría (50 €/h, con aviso previo).
3. Ajustar expectativas: "el soporte incluido cubre X, lo que pides es Y, factura aparte".
4. Dejarlo ir en el siguiente ciclo de facturación.

El 5-10% de clientes te van a comer el margen. Es ley de SaaS. Úsalo como señal para filtrar en futuras ventas.

---

## 7. Trial y política comercial

- **Demo pública** con Café Central (la del seed). URL: `chatbot-stage.hubdpb.com/widget/demo.html`. Reutilizable en presentaciones.
- **Trial de 14 días** gratis con el plan Básico, sin tarjeta. Tras el trial, si no convierte, el chat se pausa pero los datos quedan 30 días (si reactivan, todo sigue).
- **Facturación mensual** en avance, o **anual con descuento** (pago único).
- **Sin permanencia** en Básico ni Pro al pagar mensual. Anual es compromiso de 12 meses.
- **Cancelación**: en cualquier momento en mensual. Al vencimiento del año en anual.
- **Reembolso prorrateado** solo si la caída del servicio es imputable al operador (uptime <95% mensual).

---

## 8. SLA por plan

| | Básico | Pro |
|---|:---:|:---:|
| Tiempo de respuesta soporte | 48h laborables | 24h laborables |
| Canal de soporte | Email | Email + WhatsApp |
| Uptime objetivo | 95% | 97% |
| Acceso a nuevas features | Normal | Anticipado |

(Los uptime son objetivos, no compensación económica contractual — revisar cuando la infra sea redundante.)

---

## 9. Checklist comercial antes del alta

Pide por escrito:
- [ ] Nombre legal del negocio y CIF/NIF (para factura).
- [ ] Dominio donde embeberán el widget (para CORS).
- [ ] Persona de contacto técnico (si tiene dev) y comercial (dueño/gerente).
- [ ] Idiomas necesarios.
- [ ] Plan elegido (Básico mensual, Básico anual, Pro mensual, Pro anual).
- [ ] Para el setup (ver apartado 5): horarios, dirección, teléfono, email, servicios/productos principales, FAQs típicas, URL de carta/reservas, colores, logo.
- [ ] Confirmación escrita del acuerdo (email basta).

---

## 10. Qué pasa si un cliente alcanza la cuota mensual

Cada plan tiene un límite de mensajes/mes (Básico 1000, Pro 5000). El sistema **enforza la cuota automáticamente** — es parte del acuerdo comercial y debe quedar claro al cliente.

### Comportamiento técnico

Antes de cada mensaje, el backend suma los tokens consumidos por ese tenant desde el día 1 del mes. Si supera el límite, la llamada a la IA **se salta** (no se consumen tokens adicionales ni coste).

### Qué ve el usuario final del widget
Un mensaje canned en su idioma, que aparece como si fuera una respuesta más del bot:

- ES: *"El asistente ha alcanzado su límite mensual. Por favor, contacta directamente con el negocio."*
- EN / CA / FR / DE / IT / PT: equivalentes.

El usuario final **no sabe** que es un corte por cuota — ve un mensaje pidiéndole que contacte directamente.

### Qué sigue funcionando (aunque la cuota esté agotada)
- ✅ **Chips de acción** (llamar, Google Maps, carta, reservar, WhatsApp) — son enlaces estáticos, siempre activos.
- ✅ **Formulario de contacto** — el cliente sigue captando leads aunque el chat esté pausado.
- ✅ **Multi-idioma, diseño, página pública** — todo visible normal.

### Qué no funciona
- ❌ **Chat con IA** hasta el día 1 del mes siguiente.

### Reset automático
El contador se reinicia **automáticamente** el día 1 de cada mes a las 00:00 UTC. Sin intervención manual. El chat vuelve a funcionar solo.

### Qué puede hacer el operador en cualquier momento
Desde el panel Plataforma, con un click:

- **Subir la cuota** del tenant → el chat se reactiva en el momento.
- **Ponerla a sin límite** → uso ilimitado (solo en plan Custom).
- **Vender un add-on de +1000 mensajes extra** (15 €, pago único) → se suma a la cuota del mes en curso. Al mes siguiente vuelve al límite normal del plan.

### Cómo se ve en el Dashboard del cliente
Barra de progreso de consumo con código de color:
- Verde (<70%) — uso normal.
- Ámbar (70-89%) — aviso visual.
- Rojo (≥90%) — riesgo inminente de corte.

### Recomendación comercial

Cuando cierres una venta, **explica esto explícitamente** y refléjalo en el acuerdo. Frases tipo:

> *"El plan Básico incluye 1000 mensajes de IA al mes. Si los superas, el chat se pausa automáticamente hasta el mes siguiente, aunque los botones (llamar, mapa, etc.) y el formulario de contacto siguen activos. Te avisaremos por email cuando llegues al 80% de tu cuota para que podamos subirte de plan o añadir un pack extra antes del corte."*

### ⚠️ Pendiente de implementar (conocido)

- **Aviso automático por email al 80-90% de cuota.** Hoy el operador tiene que revisar el panel para verlo. Sin aviso proactivo, un cliente puede llegar al corte sin margen para ampliar. **Prioridad alta antes de vender al primer cliente real.**
- **Log de histórico de cortes por cuota.** Ayudaría a identificar clientes que recurrentemente agotan cuota — candidatos naturales a upgrade de plan.

---

## 11. Cosas a decidir antes del primer cliente de pago

- [ ] ¿Dominio comercial de la marca? (hoy `chatbot-stage.hubdpb.com` es staging; para clientes reales conviene algo tipo `chatbot.hubdpb.com` o dominio propio).
- [ ] ¿Método de cobro? (Stripe Billing recomendado para SaaS; Redsys también vale; domiciliación/transferencia manual para MVP).
- [ ] ¿Cambias "Powered by DPB Andorra" por algo más comercial? ¿O lo mantienes como branding gratuito y lo vendes como add-on removable?
- [ ] ¿Política de exportación de datos si un cliente se va? (Descarga JSON de conversaciones + contactos).
- [ ] ¿RGPD: DPA firmado con el cliente?
- [ ] ¿Términos legales / condiciones del servicio redactados?

---

**Última actualización:** 2026-04-23. Revisar cada 3-6 meses o cuando cambien precios de los modelos de IA. Si los tiers no convierten en 3 meses, bajar precio del Básico a 29 €/mes (probado suele mover conversión) antes de añadir más features.
