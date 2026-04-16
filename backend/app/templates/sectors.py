"""Sector templates.

Each template is a dict with pre-configured intents + suggested text for
business.description, business.extra_info and the default welcome message.

Applying a template NEVER overwrites existing data:
- Intents are created by name; duplicates are skipped.
- description/extra_info/welcome are only filled if currently empty.

All text is in Spanish (default language). After applying, the admin
can translate the intents to the other supported languages via the
existing "Traducir todos con IA" flow.
"""

SECTOR_TEMPLATES = [
    # ══════════════════════════════════════════════════════════════════
    {
        "id": "restaurante",
        "name": "Restaurante / Cafetería",
        "icon": "🍽️",
        "description": "Bares, restaurantes, cafeterías, food trucks, pastelerías",
        "business_description": "Restaurante de cocina tradicional con productos de proximidad. Terraza, opciones veganas y sin gluten. Ideal para comidas de grupo y celebraciones.",
        "extra_info": "- **WiFi gratis**, pide la contraseña en barra\n- **Terraza** climatizada todo el año\n- **Mascotas** pequeñas bienvenidas en terraza\n- Opciones **veganas y sin gluten** en toda la carta\n- **Parking** público a 2 min caminando\n- Aceptamos **tarjeta, efectivo y Bizum**",
        "welcome": "¡Hola! Soy el asistente de nuestro restaurante. Puedo ayudarte con horarios, reservas, nuestra carta o cualquier duda. ¿En qué te ayudo?",
        "intents": [
            {"name": "horarios", "keywords": ["horario", "hora", "abierto", "abren", "cierran", "horarios"], "priority": 10,
             "response": "Nuestros horarios son:\n• Lunes a viernes: 13:00-16:00 y 20:00-23:30\n• Sábados: 13:00-16:30 y 20:00-24:00\n• Domingos: 13:00-16:30 (noche cerrado)"},
            {"name": "reservas", "keywords": ["reservar", "reserva", "mesa", "reservar mesa", "tengo reserva"], "priority": 10,
             "response": "Aceptamos reservas para cualquier día. Puedes llamar al teléfono del restaurante o escribirnos por email. Para grupos de más de 8 personas recomendamos reservar con 48h de antelación."},
            {"name": "carta", "keywords": ["carta", "menu", "menú", "plato", "precio", "precios", "tenéis", "ofrecéis"], "priority": 10,
             "response": "Tenemos una carta variada con platos tradicionales y opciones modernas. Incluye entrantes (8-14€), platos principales (15-24€), postres caseros (5-8€) y menú del día (14,50€ lunes a viernes). Te recomendamos preguntar por las sugerencias del chef."},
            {"name": "vegano_alergenos", "keywords": ["vegano", "vegana", "vegetariano", "celiac", "gluten", "alergia", "alérgenos", "sin gluten", "sin lactosa", "intolerancia"], "priority": 9,
             "response": "Tenemos opciones veganas, vegetarianas y sin gluten claramente señaladas en la carta. Si tienes alguna alergia o intolerancia, avísanos al pedir y nuestro equipo de cocina te orienta personalmente."},
            {"name": "ubicacion", "keywords": ["dónde", "donde", "ubicación", "dirección", "direccion", "cómo llegar", "mapa", "estáis"], "priority": 10,
             "response": "Estamos en el centro de la ciudad, fácilmente accesible en transporte público. Tenemos parking público a 2 minutos caminando. Si me dices tu ubicación puedo orientarte mejor."},
            {"name": "eventos_grupos", "keywords": ["evento", "celebración", "celebracion", "cumpleaños", "grupo", "grupos", "comida empresa", "cena privada"], "priority": 8,
             "response": "Organizamos celebraciones para grupos: cumpleaños, comidas de empresa, cenas privadas. Disponemos de un salón reservado para grupos de hasta 25 personas y menús cerrados desde 25€ por persona. Pídenos presupuesto por email."},
            {"name": "para_llevar", "keywords": ["llevar", "take away", "takeaway", "a domicilio", "delivery", "recoger"], "priority": 7,
             "response": "Ofrecemos servicio de comida para llevar. Puedes llamar con 30 minutos de antelación y pasar a recoger. No tenemos reparto a domicilio propio, pero estamos disponibles en las apps habituales de delivery."},
        ],
    },
    # ══════════════════════════════════════════════════════════════════
    {
        "id": "clinica",
        "name": "Clínica / Consulta médica",
        "icon": "🏥",
        "description": "Clínicas privadas, consultorios, dentistas, fisioterapeutas, psicólogos",
        "business_description": "Clínica médica con servicio personalizado. Especialistas cualificados y tecnología moderna. Atención a pacientes particulares y con seguros médicos concertados.",
        "extra_info": "- **Cita previa obligatoria** — llama o reserva por email\n- Aceptamos las principales **mutuas y seguros privados**\n- Consultas **particulares** también disponibles\n- **Parking gratuito** para pacientes\n- Acceso para **personas con movilidad reducida**\n- En **urgencias graves** llama al 112",
        "welcome": "Hola, soy el asistente de la clínica. Puedo ayudarte con citas, servicios, precios orientativos o seguros aceptados. Para urgencias graves llama al 112.",
        "intents": [
            {"name": "horarios", "keywords": ["horario", "hora", "abierto", "abren", "cierran"], "priority": 10,
             "response": "Horario de atención:\n• Lunes a viernes: 9:00-14:00 y 16:00-20:00\n• Sábados: 9:00-13:00 (solo urgencias programadas)\n• Domingos y festivos: cerrado"},
            {"name": "citas", "keywords": ["cita", "citar", "pedir cita", "reservar", "visita", "consulta"], "priority": 10,
             "response": "Puedes pedir cita llamando por teléfono en horario de atención o enviando un email. Indícanos tu nombre, el motivo de consulta y disponibilidad horaria. Te confirmaremos la cita en el mismo día."},
            {"name": "servicios", "keywords": ["servicio", "tratamiento", "especialidad", "qué hacéis", "ofrecéis"], "priority": 9,
             "response": "Ofrecemos servicios de medicina general, pruebas diagnósticas y seguimiento personalizado. Para tratamientos específicos, cuéntame qué necesitas y te derivo al especialista correspondiente."},
            {"name": "precios", "keywords": ["precio", "precios", "cuesta", "vale", "tarifa", "importe"], "priority": 9,
             "response": "Los precios varían según el tipo de consulta y tratamiento. Primera consulta desde 50€, revisiones desde 35€. Para presupuestos de tratamientos concretos, agenda una primera cita gratuita de valoración."},
            {"name": "seguros", "keywords": ["seguro", "mutua", "sanitas", "adeslas", "asisa", "mapfre", "axa", "dkv", "cubre", "póliza"], "priority": 9,
             "response": "Trabajamos con las principales mutuas y seguros privados. Dinos qué seguro tienes y te confirmamos si está concertado con nosotros. También atendemos a pacientes particulares."},
            {"name": "urgencias", "keywords": ["urgencia", "emergencia", "urgente", "112", "ya", "hoy", "ahora"], "priority": 10,
             "response": "⚠️ Si es una **urgencia médica grave**, llama al **112** inmediatamente. Para consultas urgentes pero no graves, llámanos en horario de atención y priorizaremos tu caso."},
            {"name": "ubicacion", "keywords": ["dónde", "donde", "ubicación", "dirección", "direccion", "cómo llegar", "aparcar", "parking"], "priority": 10,
             "response": "Nuestra clínica está céntrica y bien comunicada. Disponemos de parking gratuito para pacientes y la entrada es accesible para personas con movilidad reducida."},
        ],
    },
    # ══════════════════════════════════════════════════════════════════
    {
        "id": "tienda",
        "name": "Tienda / E-commerce",
        "icon": "🛍️",
        "description": "Tiendas físicas, online, moda, decoración, regalos",
        "business_description": "Tienda con productos seleccionados cuidadosamente. Atención personalizada, envíos rápidos y política de devoluciones flexible.",
        "extra_info": "- **Envíos** a toda España en 24-48h (gratis a partir de 50€)\n- **Devoluciones** gratuitas durante 30 días\n- Pago: **tarjeta, Bizum, Apple Pay, Google Pay, transferencia**\n- **Regalo** envuelto sin coste si lo pides en el pedido\n- **Atención al cliente** por WhatsApp y email\n- Tienda física con horario de visita para recoger pedidos",
        "welcome": "¡Hola! ¿Te ayudo a encontrar algo? Puedo resolver dudas sobre productos, envíos, devoluciones o formas de pago.",
        "intents": [
            {"name": "horarios", "keywords": ["horario", "hora", "abierto", "tienda física", "tienda fisica"], "priority": 10,
             "response": "La tienda física abre de lunes a sábado, de 10:00 a 14:00 y de 17:00 a 20:30. La tienda online funciona 24/7 — puedes hacer tu pedido a cualquier hora."},
            {"name": "envios", "keywords": ["envío", "envio", "envíos", "envios", "entrega", "llega", "cuándo llega", "cuanto tarda", "tardanza", "plazo"], "priority": 10,
             "response": "Enviamos a toda España en 24-48h laborables. Envíos **gratis a partir de 50€**, por debajo el coste es 4,95€. Recibirás el tracking por email en cuanto salga el paquete."},
            {"name": "devoluciones", "keywords": ["devolución", "devolucion", "devolver", "cambiar", "no me queda", "no me gusta", "reembolso", "reintegro"], "priority": 10,
             "response": "Tienes **30 días** para devolver cualquier producto sin dar explicaciones. La devolución es **gratuita**: te mandamos una etiqueta para que reenvíes el paquete y reembolsamos el importe en 3-5 días laborables tras recibirlo."},
            {"name": "pago", "keywords": ["pago", "pagar", "tarjeta", "bizum", "transferencia", "paypal", "apple pay", "google pay", "visa", "mastercard"], "priority": 9,
             "response": "Aceptamos tarjeta (Visa, Mastercard, American Express), Bizum, Apple Pay, Google Pay, PayPal y transferencia bancaria. Todos los pagos online son seguros y encriptados."},
            {"name": "stock_disponibilidad", "keywords": ["stock", "disponible", "hay", "queda", "tenéis", "talla", "color", "modelo"], "priority": 8,
             "response": "El stock se actualiza en tiempo real en la web. Si un producto aparece, está disponible. Si quieres algo concreto que no ves, escríbenos con la referencia y miramos en almacén."},
            {"name": "regalo", "keywords": ["regalo", "envolver", "envoltorio", "para regalar"], "priority": 7,
             "response": "Podemos envolver tu pedido como regalo sin coste adicional. Solo tienes que marcar la casilla \"envolver para regalo\" en el checkout y, si quieres, añadir un mensaje personalizado."},
            {"name": "tallas_medidas", "keywords": ["talla", "tallas", "medida", "medidas", "tamaño", "size"], "priority": 8,
             "response": "Cada producto tiene su guía de tallas con medidas exactas en la ficha. Si dudas entre dos tallas, pídenos consejo con tu altura y peso y te orientamos."},
        ],
    },
    # ══════════════════════════════════════════════════════════════════
    {
        "id": "inmobiliaria",
        "name": "Inmobiliaria",
        "icon": "🏠",
        "description": "Agencias inmobiliarias, compra-venta, alquiler, zonas residenciales",
        "business_description": "Agencia inmobiliaria con años de experiencia en la zona. Asesoramiento personalizado en compra, venta y alquiler. Gestión completa incluyendo documentación y financiación.",
        "extra_info": "- **Visitas** con cita previa (presenciales o por videollamada)\n- Asesoramiento en **financiación hipotecaria** sin coste\n- **Honorarios** claros al cierre de operación\n- Gestión completa de **documentación y notaría**\n- **Valoración gratuita** de tu inmueble\n- Trabajamos con compradores nacionales e internacionales",
        "welcome": "¡Hola! Soy el asistente de la inmobiliaria. Puedo ayudarte con información sobre nuestras propiedades, visitas, precios o el proceso de compra/alquiler.",
        "intents": [
            {"name": "horarios_visitas", "keywords": ["horario", "hora", "visitar", "visita", "ver", "cita"], "priority": 10,
             "response": "Atendemos de lunes a viernes de 10:00-14:00 y 16:30-20:00, y sábados de 10:00-14:00. Las visitas a los inmuebles son siempre con cita previa — llámanos o escríbenos para coordinar."},
            {"name": "alquiler_vs_venta", "keywords": ["alquilar", "alquiler", "comprar", "venta", "vender", "rent", "buy"], "priority": 10,
             "response": "Trabajamos tanto compra-venta como alquiler. Dinos qué buscas (comprar / vender / alquilar / traspasar), zona y presupuesto aproximado y te orientamos con las opciones disponibles."},
            {"name": "precios_zona", "keywords": ["precio", "precios", "cuánto", "cuanto", "cuesta", "valor", "mercado", "zona"], "priority": 9,
             "response": "Los precios varían según zona, metros y estado. Podemos hacerte una valoración gratuita de tu inmueble o indicarte precios orientativos de la zona que te interesa. Cuéntanos tu caso."},
            {"name": "financiacion", "keywords": ["hipoteca", "financiación", "financiacion", "préstamo", "prestamo", "banco", "financiar"], "priority": 9,
             "response": "Tenemos acuerdos con varias entidades bancarias y podemos ayudarte a encontrar la **mejor hipoteca** según tu perfil. El asesoramiento financiero no tiene coste adicional."},
            {"name": "documentacion", "keywords": ["papeles", "documentos", "documentación", "contrato", "notaría", "notaria", "escritura", "gestiones"], "priority": 9,
             "response": "Gestionamos toda la documentación de la operación: contrato de arras, escritura, inscripción en el registro, cambio de titular de suministros... Te explicamos cada paso para que no te pierdas."},
            {"name": "valoracion", "keywords": ["valorar", "valoración", "valoracion", "tasar", "tasación", "tasacion", "cuánto vale"], "priority": 9,
             "response": "Hacemos **valoración gratuita** de tu inmueble. Visitamos la vivienda, analizamos el mercado de la zona y te damos un precio realista para que pongas en venta con éxito."},
            {"name": "honorarios", "keywords": ["comisión", "comision", "honorarios", "cuánto cobráis", "cuanto cobrais", "coste del servicio"], "priority": 8,
             "response": "Nuestros honorarios son claros y se pactan al inicio. Solo cobramos al cerrar la operación con éxito — si no hay venta o alquiler, no hay coste. Dinos tu caso y te damos el detalle."},
        ],
    },
    # ══════════════════════════════════════════════════════════════════
    {
        "id": "servicios",
        "name": "Servicios profesionales",
        "icon": "💼",
        "description": "Abogados, contables, consultores, gestorías, arquitectos, diseñadores",
        "business_description": "Profesionales especializados con trato cercano y atención personalizada. Asesoramiento claro, sin letra pequeña, con experiencia contrastada.",
        "extra_info": "- **Primera consulta** orientativa gratuita (30 min)\n- **Presupuestos** cerrados sin sorpresas\n- Atención **presencial y online** (videollamada)\n- Trabajamos con **particulares y empresas**\n- Documentación y seguimiento por **cliente privado**\n- Facturación **mensual o por proyecto**",
        "welcome": "¡Hola! Soy el asistente. Puedo ayudarte a entender nuestros servicios, agendar una primera consulta o darte una idea de precios.",
        "intents": [
            {"name": "horarios", "keywords": ["horario", "hora", "abierto", "atención", "despacho"], "priority": 10,
             "response": "Atendemos de lunes a jueves de 9:30 a 18:30 y viernes de 9:30 a 15:00. Atendemos tanto presencialmente como por videollamada según lo que te venga mejor."},
            {"name": "primera_consulta", "keywords": ["primera consulta", "gratis", "gratuita", "asesorar", "dudas", "informarme"], "priority": 10,
             "response": "Ofrecemos una **primera consulta gratuita de 30 minutos** para entender tu caso y decidir si podemos ayudarte. Agenda un hueco llamando o por email y te confirmamos la cita en el día."},
            {"name": "servicios", "keywords": ["servicio", "servicios", "qué hacéis", "ofrecéis", "ayudarme", "trabajáis"], "priority": 9,
             "response": "Ofrecemos asesoramiento y gestión en distintas áreas de nuestra especialidad. Cuéntanos brevemente tu necesidad y te orientamos al profesional y servicio adecuado."},
            {"name": "presupuesto", "keywords": ["presupuesto", "precio", "precios", "cuánto", "cuesta", "cobráis", "tarifa", "honorarios"], "priority": 10,
             "response": "Damos **presupuestos cerrados sin sorpresas**, después de entender tu caso en la primera consulta. Trabajamos por proyecto, iguala mensual o hora según lo que te convenga. Pídenos cita sin compromiso."},
            {"name": "contratar", "keywords": ["contratar", "empezar", "cómo funciono", "proceso", "siguientes pasos"], "priority": 9,
             "response": "El proceso es simple: **1)** Agendas la consulta inicial gratuita. **2)** Te enviamos presupuesto cerrado. **3)** Si aceptas, firmamos el encargo y empezamos a trabajar. Te mantenemos informado en cada hito."},
            {"name": "empresas_vs_particulares", "keywords": ["empresa", "empresas", "autónomo", "autonomo", "pyme", "particular", "individual"], "priority": 8,
             "response": "Trabajamos tanto con **particulares** como con **empresas y autónomos**. El tipo de cliente nos permite ofrecer servicios adaptados a cada caso. Cuéntanos qué eres y qué buscas."},
            {"name": "documentacion_seguimiento", "keywords": ["documentación", "documentos", "expediente", "seguimiento", "avance", "estado"], "priority": 7,
             "response": "Te damos acceso a un **cliente privado** donde puedes consultar tu expediente, documentos y el estado de cada gestión en tiempo real. Así siempre sabes en qué punto está tu asunto."},
        ],
    },
]
