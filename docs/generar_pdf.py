"""Genera docs/Documentacion_Tor_IP_API.pdf.

Cada captura se describe en un recuadro. Si la imagen correspondiente existe en
docs/capturas/ (con el nombre indicado en el recuadro), se inserta en su lugar.
Para actualizar el PDF después de tomar capturas, basta con volver a ejecutar:

    python3 docs/generar_pdf.py

Requiere reportlab y Pillow (en Kali: sudo apt install python3-reportlab python3-pil).
"""

from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

DOCS = Path(__file__).resolve().parent
CAPTURAS = DOCS / "capturas"
SALIDA = DOCS / "Documentacion_Tor_IP_API.pdf"
REPO = "github.com/AnaLauraRG/tor-ip-api"

ACENTO = colors.HexColor("#1F4E79")
GRIS_TEXTO = colors.HexColor("#444444")
GRIS_FONDO = colors.HexColor("#F3F4F6")
GRIS_BORDE = colors.HexColor("#C9CDD2")
FONDO_CAPTURA = colors.HexColor("#FFF8E6")
BORDE_CAPTURA = colors.HexColor("#E0B04A")

ANCHO_UTIL = letter[0] - 2 * inch

# --- Estilos ---------------------------------------------------------------

base = getSampleStyleSheet()
S = {
    "titulo": ParagraphStyle("titulo", parent=base["Title"], fontName="Helvetica-Bold",
                             fontSize=26, leading=32, textColor=ACENTO, spaceAfter=10),
    "subtitulo": ParagraphStyle("subtitulo", parent=base["Normal"], fontName="Helvetica",
                                fontSize=14, leading=19, textColor=GRIS_TEXTO, alignment=TA_CENTER),
    "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName="Helvetica-Bold",
                         fontSize=17, leading=22, textColor=ACENTO, spaceBefore=6, spaceAfter=10,
                         keepWithNext=True),
    "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="Helvetica-Bold",
                         fontSize=13, leading=17, textColor=ACENTO, spaceBefore=12, spaceAfter=6,
                         keepWithNext=True),
    "body": ParagraphStyle("body", parent=base["Normal"], fontName="Helvetica",
                           fontSize=11, leading=15.5, spaceAfter=7),
    "bullet": ParagraphStyle("bullet", parent=base["Normal"], fontName="Helvetica",
                             fontSize=11, leading=15.5, leftIndent=16, bulletIndent=4, spaceAfter=3),
    "celda": ParagraphStyle("celda", parent=base["Normal"], fontName="Helvetica",
                            fontSize=9.5, leading=12.5),
    "celda_b": ParagraphStyle("celda_b", parent=base["Normal"], fontName="Helvetica-Bold",
                              fontSize=9.5, leading=12.5, textColor=colors.white),
    "code": ParagraphStyle("code", parent=base["Code"], fontName="Courier",
                           fontSize=9, leading=12),
    "cap_titulo": ParagraphStyle("cap_titulo", parent=base["Normal"], fontName="Helvetica-Bold",
                                 fontSize=10.5, leading=14, textColor=colors.HexColor("#7A5200")),
    "cap": ParagraphStyle("cap", parent=base["Normal"], fontName="Helvetica",
                          fontSize=9.5, leading=13),
    "pie_img": ParagraphStyle("pie_img", parent=base["Normal"], fontName="Helvetica-Oblique",
                              fontSize=9, leading=12, textColor=GRIS_TEXTO, alignment=TA_CENTER,
                              spaceBefore=3, spaceAfter=12),
}


def p(texto, estilo="body"):
    return Paragraph(texto, S[estilo])


def vinetas(items):
    return [Paragraph(t, S["bullet"], bulletText="•") for t in items]


def codigo(texto):
    pre = Preformatted(texto.strip("\n"), S["code"])
    t = Table([[pre]], colWidths=[ANCHO_UTIL])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GRIS_FONDO),
        ("BOX", (0, 0), (-1, -1), 0.5, GRIS_BORDE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return [t, Spacer(1, 8)]


def tabla(filas, anchos, encabezado=True):
    datos = []
    for i, fila in enumerate(filas):
        estilo = "celda_b" if encabezado and i == 0 else "celda"
        datos.append([Paragraph(str(c), S[estilo]) for c in fila])
    t = Table(datos, colWidths=[ANCHO_UTIL * a for a in anchos], repeatRows=1 if encabezado else 0)
    estilo = [
        ("GRID", (0, 0), (-1, -1), 0.5, GRIS_BORDE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if encabezado:
        estilo.append(("BACKGROUND", (0, 0), (-1, 0), ACENTO))
        for i in range(1, len(filas)):
            if i % 2 == 0:
                estilo.append(("BACKGROUND", (0, i), (-1, i), GRIS_FONDO))
    t.setStyle(TableStyle(estilo))
    return [t, Spacer(1, 10)]


# --- Capturas --------------------------------------------------------------

contador = {"n": 0}


def captura(archivo, titulo, peticion, como, esperado):
    """Recuadro descriptivo, o la imagen si ya existe en docs/capturas/.

    El número de la captura es el prefijo del nombre de archivo (00a, 01, 02...),
    para que el texto, el PDF y la carpeta usen la misma referencia.
    """
    contador["n"] += 1
    n = archivo.split("-", 1)[0]
    ruta = CAPTURAS / archivo
    if ruta.exists():
        img = Image(str(ruta))
        escala = min(ANCHO_UTIL / img.imageWidth, (6.3 * inch) / img.imageHeight, 1.0)
        img.drawWidth = img.imageWidth * escala
        img.drawHeight = img.imageHeight * escala
        img.hAlign = "CENTER"
        pie = Paragraph(f"Captura {n}. {titulo}. Esperado: {esperado}", S["pie_img"])
        return [KeepTogether([img, pie])]

    filas = [
        [Paragraph(f"Captura {n} · {titulo}", S["cap_titulo"])],
        [Paragraph(f"<b>Archivo:</b> <font face='Courier'>docs/capturas/{archivo}</font>", S["cap"])],
        [Paragraph(f"<b>Petición:</b> {peticion}", S["cap"])],
        [Paragraph(f"<b>Cómo:</b> {como}", S["cap"])],
        [Paragraph(f"<b>Debe mostrar:</b> {esperado}", S["cap"])],
    ]
    t = Table(filas, colWidths=[ANCHO_UTIL])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), FONDO_CAPTURA),
        ("BOX", (0, 0), (-1, -1), 1, BORDE_CAPTURA),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, BORDE_CAPTURA),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 7),
    ]))
    return [KeepTogether([t, Spacer(1, 10)])]


# --- Contenido -------------------------------------------------------------

def portada():
    return [
        Spacer(1, 2.1 * inch),
        Paragraph("Tor IP API", S["titulo"]),
        Paragraph("Documentación técnica y evidencias", S["subtitulo"]),
        Spacer(1, 0.25 * inch),
        Paragraph("Reto 1 · Challenge Cybersecurity Engineer (BISO)", S["subtitulo"]),
        Spacer(1, 2.6 * inch),
        Paragraph(f"Repositorio: {REPO}", S["subtitulo"]),
        Paragraph(date.today().strftime("%d/%m/%Y"), S["subtitulo"]),
        PageBreak(),
    ]


def descripcion():
    h = [p("1. Descripción general", "h1")]
    h.append(p(
        "Tor IP API es una API REST que obtiene las direcciones IP de los nodos de salida de la red "
        "Tor desde tres fuentes públicas, las unifica sin duplicados y permite mantener una lista de "
        "IPs excluidas. Su objetivo es alimentar controles de seguridad, como un firewall o un WAF, "
        "que necesitan identificar tráfico proveniente de Tor."))
    h.append(p("Endpoints que pide el reto", "h2"))
    h += tabla([
        ["Método", "Ruta", "Descripción"],
        ["GET", "/ips", "Devuelve todas las IPs de Tor obtenidas de las fuentes externas."],
        ["POST", "/exclusions", "Recibe una IP y la guarda en la base de datos de exclusiones."],
        ["GET", "/ips/filtered", "Devuelve las IPs de Tor exceptuando las excluidas."],
    ], [0.12, 0.22, 0.66])
    h.append(p("Funcionalidades adicionales", "h2"))
    h += vinetas([
        "Autenticación con tokens JWT y contraseñas protegidas con bcrypt.",
        "Dos roles: <b>reader</b> (solo consulta) y <b>admin</b> (gestión completa).",
        "Auditoría de todas las peticiones, incluidas las rechazadas.",
        "Límite de intentos de login para frenar ataques de fuerza bruta.",
        "Endpoints extra: listar y borrar exclusiones, gestión de usuarios, actualización manual "
        "de las fuentes, consulta de auditoría y estado del servicio.",
        "Informe de análisis de seguridad (SAST) e integración continua con GitHub Actions.",
    ])
    h.append(Spacer(1, 6))
    h.append(p("Fuentes de IPs de Tor", "h2"))
    h += tabla([
        ["Fuente", "Formato", "Consideración"],
        ["check.torproject.org", "Texto plano", "Lista oficial del proyecto Tor."],
        ["dan.me.uk", "Texto plano", "Solo permite una descarga cada 30 minutos."],
        ["bigdatacloud.com", "API JSON paginada", "Requiere una API key gratuita."],
    ], [0.3, 0.22, 0.48])
    h.append(p(
        "Debido al límite de dan.me.uk, la API nunca consulta las fuentes en el momento de cada "
        "petición. Un planificador interno las descarga periódicamente y guarda el resultado en "
        "PostgreSQL; los endpoints leen siempre de la base de datos."))
    return h


def arquitectura():
    h = [p("2. Arquitectura", "h1")]
    h += tabla([
        ["Componente", "Tecnología", "Función"],
        ["API", "Python 3.13, FastAPI", "Expone los endpoints, valida datos, autentica y audita."],
        ["Planificador de ingesta", "APScheduler", "Descarga las fuentes respetando el intervalo de cada una."],
        ["Base de datos", "PostgreSQL 16", "Guarda IPs de Tor, exclusiones, usuarios, auditoría y estado de las fuentes."],
        ["Contenedores", "Docker Compose", "Levanta la API y la base de datos en una red interna."],
    ], [0.24, 0.24, 0.52])
    h = [KeepTogether(h)]
    h.append(p("Flujo de una petición: el cliente envía la petición con su token; la API verifica el "
               "token y el rol del usuario, ejecuta la consulta en PostgreSQL, responde en JSON y "
               "registra la petición en la auditoría. Las peticiones sin token o sin permiso se "
               "rechazan con 401 o 403 y también quedan registradas."))
    return h


def requisitos_y_config():
    h = [p("3. Requisitos", "h1")]
    h += vinetas([
        "<b>Con Docker:</b> Docker con Docker Compose, o Podman con su socket activo.",
        "<b>Sin Docker:</b> Python 3.13 y, opcionalmente, PostgreSQL 16.",
        "Una API key gratuita de bigdatacloud.com (opcional: sin ella, esa fuente se omite).",
    ])
    h.append(Spacer(1, 6))
    h.append(p("4. Configuración", "h1"))
    h.append(p("La configuración se lee del archivo <font face='Courier'>.env</font>, que nunca se sube "
               "al repositorio. Se crea a partir de la plantilla:"))
    h += codigo("cp .env.example .env\nopenssl rand -base64 48     # genera el valor de JWT_SECRET\nnano .env")
    h += tabla([
        ["Variable", "Obligatoria", "Descripción"],
        ["POSTGRES_USER / _PASSWORD / _DB", "Sí", "Credenciales de PostgreSQL (contraseña solo con letras y números)."],
        ["JWT_SECRET", "Sí", "Clave para firmar los tokens; mínimo 32 caracteres. Sin ella la API no arranca."],
        ["ADMIN_USERNAME / ADMIN_PASSWORD", "Sí", "Administrador que se crea en el primer arranque (contraseña de 12+ caracteres)."],
        ["BIGDATACLOUD_API_KEY", "No", "Clave de bigdatacloud; vacía, la fuente se omite."],
        ["JWT_EXPIRE_MIN", "No", "Validez de cada token en minutos (30 por defecto)."],
        ["LOGIN_MAX_ATTEMPTS / LOGIN_WINDOW_MIN", "No", "Intentos de login fallidos permitidos y ventana en minutos (5 en 15)."],
        ["*_INTERVAL_MIN", "No", "Minutos entre descargas de cada fuente (60; dan.me.uk no admite menos de 30)."],
    ], [0.38, 0.14, 0.48])
    return h


def ejecucion_docker():
    h = [p("5. Ejecución con Docker", "h1")]
    h.append(p("Desde la carpeta del proyecto, con el archivo <font face='Courier'>.env</font> ya configurado:"))
    h += codigo("docker compose up --build")
    h.append(p("Compose construye la imagen de la API, levanta PostgreSQL, espera a que la base esté "
               "lista y arranca la API en <font face='Courier'>http://localhost:8000</font>. Al iniciar se "
               "crea el administrador y corre el primer ciclo de descarga de las fuentes."))
    h.append(p("Si se usa Podman en lugar de Docker, antes hay que activar su socket:"))
    h += codigo("systemctl --user enable --now podman.socket")
    h.append(p("Para comprobar que todo está funcionando:"))
    h += codigo("docker compose ps\ncurl http://localhost:8000/health")
    h += captura("00a-docker-compose-up.png", "Arranque con Docker Compose",
                 "<font face='Courier'>docker compose up --build</font> (o <font face='Courier'>docker compose logs api</font> si ya está corriendo)",
                 "Captura de la terminal con los logs del arranque.",
                 "el arranque sin errores: <i>Planificador de ingesta iniciado</i>, <i>Application startup complete</i>, "
                 "<i>Uvicorn running on http://0.0.0.0:8000</i> y los ciclos de ingesta ejecutados correctamente.")
    h += captura("00b-docker-ps.png", "Contenedores en ejecución",
                 "<font face='Courier'>docker compose ps</font> y <font face='Courier'>curl http://localhost:8000/health</font>",
                 "Captura de la terminal con ambos comandos.",
                 "los contenedores <i>db</i> y <i>api</i> en estado <i>Up</i> (healthy), y el JSON de /health "
                 "con las tres fuentes en <i>\"last_status\": \"ok\"</i>.")
    return h


def ejecucion_local():
    h = [p("6. Ejecución local (sin Docker)", "h1")]
    h.append(p("Útil para desarrollo. Sin la variable <font face='Courier'>DATABASE_URL</font>, la API usa un "
               "archivo SQLite local (<font face='Courier'>tor.db</font>)."))
    h += codigo(
        "python3 -m venv .venv\n"
        "source .venv/bin/activate\n"
        "pip install -r requirements-dev.txt\n"
        "cp .env.example .env          # completar al menos JWT_SECRET y ADMIN_PASSWORD\n"
        "uvicorn app.main:app --reload --port 8001")
    h.append(p("Se usa el puerto 8001 para no chocar con la versión en Docker, si está corriendo. "
               "Para usar PostgreSQL en lugar de SQLite:"))
    h += codigo("export DATABASE_URL=postgresql+psycopg://usuario:clave@localhost:5432/tor")
    h.append(p("Pruebas automáticas (68 pruebas; simulan las fuentes, no requieren internet):"))
    h += codigo("pytest")
    return h


def acceso():
    h = [p("7. Autenticación y roles", "h1")]
    h.append(p("Todos los endpoints, excepto <font face='Courier'>/auth/login</font> y "
               "<font face='Courier'>/health</font>, requieren un token. El token se obtiene con usuario y "
               "contraseña y se envía en la cabecera <font face='Courier'>Authorization: Bearer &lt;token&gt;</font>. "
               "Expira a los 30 minutos."))
    h += codigo(
        'curl -X POST http://localhost:8000/auth/login \\\n'
        '     -d "username=admin&password=TU_CLAVE"')
    h += tabla([
        ["Acción", "reader", "admin"],
        ["Consultar IPs y exclusiones", "Sí", "Sí"],
        ["Crear y borrar exclusiones", "No (403)", "Sí"],
        ["Actualizar las fuentes manualmente", "No (403)", "Sí"],
        ["Crear y listar usuarios", "No (403)", "Sí"],
        ["Consultar la auditoría", "No (403)", "Sí"],
    ], [0.56, 0.22, 0.22])
    h.append(p("El administrador inicial se crea desde el <font face='Courier'>.env</font>; los demás usuarios "
               "los crea un administrador con <font face='Courier'>POST /users</font>. El rol se consulta en la "
               "base de datos en cada petición, por lo que desactivar a un usuario o cambiar su rol tiene "
               "efecto inmediato aunque su token siga vigente."))
    return h


def endpoints():
    h = [p("8. Referencia de endpoints", "h1")]
    h += tabla([
        ["Método", "Ruta", "Acceso", "Respuestas"],
        ["POST", "/auth/login", "Público", "200, 401, 429"],
        ["GET", "/ips", "reader, admin", "200, 401"],
        ["GET", "/ips/filtered", "reader, admin", "200, 401"],
        ["GET", "/exclusions", "reader, admin", "200, 401"],
        ["POST", "/exclusions", "admin", "201, 401, 403, 409, 422"],
        ["DELETE", "/exclusions/{ip}", "admin", "204, 401, 403, 404, 422"],
        ["POST", "/sources/refresh", "admin", "200, 401, 403, 409"],
        ["GET", "/users", "admin", "200, 401, 403"],
        ["POST", "/users", "admin", "201, 401, 403, 409, 422"],
        ["GET", "/audit", "admin", "200, 401, 403, 422"],
        ["GET", "/health", "Público", "200, 503"],
    ], [0.13, 0.27, 0.25, 0.35])
    h += tabla([
        ["Código", "Significado"],
        ["200 / 201 / 204", "Éxito: consulta, creación o eliminación."],
        ["401", "Sin token, token inválido o expirado, o credenciales incorrectas."],
        ["403", "El rol del usuario no permite la operación."],
        ["404", "La exclusión a eliminar no existe."],
        ["409", "La IP ya está excluida, el usuario ya existe o hay una actualización en curso."],
        ["422", "Datos inválidos, por ejemplo una IP mal formada."],
        ["429", "Demasiados intentos de login fallidos; la cabecera Retry-After indica cuándo reintentar."],
    ], [0.22, 0.78])
    h.append(p("La documentación interactiva de todos los endpoints está disponible en "
               "<font face='Courier'>http://localhost:8000/docs</font> (Swagger UI)."))
    h += captura("00d-swagger.png", "Documentación interactiva (Swagger UI)",
                 "<font face='Courier'>http://localhost:8000/docs</font> en el navegador",
                 "Abrir la página sin desplegar ningún endpoint.",
                 "la lista completa de endpoints agrupados por sección (auth, ips, exclusions, sources, "
                 "users, audit, health) y el botón <i>Authorize</i>.")
    return h


def evidencias():
    h = [p("9. Evidencias de requests y responses", "h1")]
    h.append(p("Las capturas siguientes muestran cada endpoint con su petición y su respuesta, tanto en "
               "los casos exitosos como en los de error. Se pueden tomar desde Swagger UI "
               "(<font face='Courier'>/docs</font>) o desde la colección de Postman incluida en "
               "<font face='Courier'>postman/</font>. Cada captura debe mostrar el método, la URL, el cuerpo "
               "enviado (si lo hay), el código de respuesta y el cuerpo de la respuesta."))
    h.append(p("Las capturas deben tomarse en el orden indicado, porque varias usan datos de las anteriores "
               "(el token, la IP excluida o el usuario lector)."))

    h.append(p("9.1 Autenticación", "h2"))
    h += captura("01-health.png", "Estado del servicio", "<b>GET</b> /health", "Sin token.",
                 "<b>200 OK</b> con las tres fuentes, su estado y el número de IPs de cada una.")
    h += captura("02-login-admin.png", "Login del administrador", "<b>POST</b> /auth/login",
                 "Formulario con <i>username</i> = admin y <i>password</i> = la contraseña del admin. "
                 "En Swagger: botón <i>Authorize</i>, o el endpoint POST /auth/login. No mostrar la contraseña.",
                 "<b>200 OK</b> con <i>access_token</i>, <i>token_type: bearer</i> y <i>expires_in: 1800</i>. "
                 "La petición no se muestra porque su cuerpo contiene la contraseña del administrador.")
    h += captura("03-login-password-incorrecta.png", "Login con contraseña incorrecta", "<b>POST</b> /auth/login",
                 "Usuario admin con una contraseña equivocada.",
                 "<b>401 Unauthorized</b> con <i>\"Usuario o contraseña incorrectos\"</i>.")
    h += captura("04-login-usuario-inexistente.png", "Login con usuario inexistente", "<b>POST</b> /auth/login",
                 "Un usuario que no existe, con cualquier contraseña.",
                 "<b>401</b> con exactamente el mismo mensaje que la captura anterior: la API no revela qué usuarios existen.")

    h.append(p("9.2 Endpoints obligatorios", "h2"))
    h += captura("05-get-ips.png", "Todas las IPs de Tor", "<b>GET</b> /ips", "Con el token de admin.",
                 "<b>200 OK</b> con <i>count</i> (total de IPs) y la lista <i>ips</i>. Anotar el valor de "
                 "<i>count</i> y copiar la primera IP de la lista para los pasos siguientes.")
    h += captura("06-post-exclusion.png", "Excluir una IP", "<b>POST</b> /exclusions",
                 "Con el token de admin. Cuerpo: <font face='Courier'>{\"ip\": \"&lt;IP copiada&gt;\", "
                 "\"reason\": \"Falso positivo: servidor propio\"}</font>.",
                 "<b>201 Created</b> con la IP, el motivo y la fecha <i>created_at</i>.")
    h += captura("07-post-exclusion-duplicada.png", "Excluir una IP ya excluida", "<b>POST</b> /exclusions",
                 "La misma IP de la captura anterior.",
                 "<b>409 Conflict</b> con <i>\"La IP ya está excluida\"</i>.")
    h += captura("08-post-exclusion-invalida.png", "Excluir una IP inválida", "<b>POST</b> /exclusions",
                 "Cuerpo: <font face='Courier'>{\"ip\": \"999.1.1.1\"}</font>.",
                 "<b>422 Unprocessable Content</b> indicando que no es una dirección IP válida.")
    h += captura("09-post-exclusion-inyeccion.png", "Intento de inyección", "<b>POST</b> /exclusions",
                 "Cuerpo: <font face='Courier'>{\"ip\": \"1.1.1.1; DROP TABLE excluded_ips\"}</font>.",
                 "<b>422</b>: la entrada se rechaza en la validación, antes de llegar a la base de datos.")
    h += captura("10-get-ips-filtered.png", "IPs sin las excluidas", "<b>GET</b> /ips/filtered",
                 "Con el token de admin.",
                 "<b>200 OK</b> con <i>count</i> menor que en la captura 05: una unidad por cada IP de Tor excluida "
                 "(la de la captura 06 y dos de pruebas anteriores, ver captura 18). Las IPs excluidas ya no aparecen en la lista.")

    h.append(p("9.3 Control de acceso", "h2"))
    h += captura("11-sin-token.png", "Petición sin token", "<b>GET</b> /ips",
                 "Sin token (en Swagger: <i>Authorize</i> y luego <i>Logout</i>).",
                 "<b>401 Unauthorized</b> con <i>\"Credenciales inválidas o token expirado\"</i>.")
    h += captura("12-token-manipulado.png", "Token manipulado", "<b>GET</b> /ips",
                 "Con un token alterado (por ejemplo, cambiando algunos caracteres del token real). "
                 "Más fácil en Postman o con curl: <font face='Courier'>-H \"Authorization: Bearer abc.def.ghi\"</font>.",
                 "<b>401 Unauthorized</b>: la firma del token no es válida.")
    h += captura("13-crear-lector.png", "Crear un usuario de solo lectura", "<b>POST</b> /users",
                 "Con el token de admin. Cuerpo: <font face='Courier'>{\"username\": \"analista\", "
                 "\"password\": \"&lt;clave de 12+ caracteres&gt;\", \"role\": \"reader\"}</font>.",
                 "<b>201 Created</b> con el usuario y su rol <i>reader</i>, sin la contraseña ni su hash. "
                 "La petición no se muestra porque su cuerpo contiene la contraseña del usuario.")
    h += captura("14-login-lector.png", "Login del usuario lector", "<b>POST</b> /auth/login",
                 "Con el usuario y la contraseña recién creados.",
                 "<b>200 OK</b> con el token del lector. La petición no se muestra porque contiene su contraseña.")
    h += captura("15-lector-consulta.png", "El lector consulta IPs (permitido)", "<b>GET</b> /ips/filtered",
                 "Con el token del lector.", "<b>200 OK</b> con la lista de IPs.")
    h += captura("16-lector-excluir-prohibido.png", "El lector intenta excluir una IP (prohibido)",
                 "<b>POST</b> /exclusions", "Con el token del lector y cualquier IP válida.",
                 "<b>403 Forbidden</b> con <i>\"No tienes permiso para esta operación\"</i>.")
    h += captura("17-lector-auditoria-prohibido.png", "El lector intenta ver la auditoría (prohibido)",
                 "<b>GET</b> /audit", "Con el token del lector.", "<b>403 Forbidden</b>.")

    h.append(p("9.4 Endpoints adicionales", "h2"))
    h.append(p("Para estas capturas se vuelve a usar el token de admin."))
    h += captura("18-get-exclusions.png", "Listar exclusiones", "<b>GET</b> /exclusions", "Con el token de admin.",
                 "<b>200 OK</b> con la IP excluida en la captura 06, su motivo y su fecha, junto con las "
                 "exclusiones de pruebas anteriores.")
    h += captura("19-get-users.png", "Listar usuarios", "<b>GET</b> /users", "Con el token de admin.",
                 "<b>200 OK</b> con los usuarios <i>admin</i> y <i>analista</i>, sus roles y su estado.")
    h += captura("20-refresh.png", "Actualizar las fuentes manualmente", "<b>POST</b> /sources/refresh",
                 "Con el token de admin.",
                 "<b>200 OK</b> con el resultado por fuente. dan.me.uk aparece como <i>skipped</i> si se "
                 "consultó hace menos de 30 minutos: la actualización manual respeta su límite.")
    h += captura("21-audit.png", "Registro de auditoría", "<b>GET</b> /audit?limit=20", "Con el token de admin.",
                 "<b>200 OK</b> con las peticiones recientes: usuario, método, ruta, código e IP de origen. "
                 "Deben verse los 401 y los 403 de las capturas anteriores.")
    h += captura("22-delete-exclusion.png", "Quitar una exclusión", "<b>DELETE</b> /exclusions/{ip}",
                 "Con el token de admin y la IP excluida en la captura 06.", "<b>204 No Content</b>.")
    h += captura("23-delete-inexistente.png", "Quitar una exclusión inexistente", "<b>DELETE</b> /exclusions/{ip}",
                 "La misma IP otra vez.", "<b>404 Not Found</b> con <i>\"La IP no está excluida\"</i>.")
    h += captura("24-ips-filtered-restaurada.png", "La IP vuelve al listado filtrado", "<b>GET</b> /ips/filtered",
                 "Con el token de admin.",
                 "<b>200 OK</b>: la IP de la captura 06 vuelve a aparecer en la lista y <i>count</i> aumenta en uno "
                 "respecto a la captura 10.")

    h.append(p("9.5 Límite de intentos de login", "h2"))
    h.append(p("Esta captura debe tomarse al final, porque bloquea el login desde la IP de origen durante 15 minutos."))
    h += captura("25-login-bloqueado-429.png", "Bloqueo por intentos fallidos", "<b>POST</b> /auth/login",
                 "Enviar una contraseña incorrecta repetidamente (5 veces por defecto).",
                 "<b>429 Too Many Requests</b> con <i>\"Demasiados intentos fallidos\"</i> y la cabecera "
                 "<i>Retry-After</i> con los segundos de espera.")
    return h


def seguridad():
    h = [p("10. Seguridad", "h1")]
    h += vinetas([
        "Contraseñas con hash bcrypt; nunca se guardan ni se registran en claro.",
        "Tokens JWT firmados con HS256 y con expiración; se rechazan los tokens sin firma, alterados o expirados.",
        "El login responde igual si el usuario no existe o si la contraseña es incorrecta.",
        "Validación estricta de IPs (IPv4 e IPv6) y consultas parametrizadas: sin inyección SQL.",
        "Cabeceras de seguridad en todas las respuestas y contenedor con usuario sin privilegios.",
        "Secretos solo en variables de entorno; la API key se envía en una cabecera, nunca en la URL.",
        "Análisis SAST con Bandit, Semgrep, pip-audit, Gitleaks y Trivy, ejecutados en cada push "
        "con GitHub Actions. Resultado final: 0 vulnerabilidades.",
    ])
    h.append(Spacer(1, 4))
    h.append(p("El detalle de cada análisis, sus hallazgos y las decisiones tomadas está en "
               "<font face='Courier'>docs/sast-report.md</font>."))
    return h


def diagrama(ruta, pie):
    img = Image(str(ruta))
    escala = min(ANCHO_UTIL / img.imageWidth, (6.4 * inch) / img.imageHeight)
    img.drawWidth = img.imageWidth * escala
    img.drawHeight = img.imageHeight * escala
    img.hAlign = "CENTER"
    return [KeepTogether([img, Paragraph(pie, S["pie_img"])])]


def nube():
    h = [p("11. Despliegue en la nube (AWS)", "h1")]
    h.append(p("Esta sección explica cómo se ejecutaría la solución en AWS. Es una propuesta de diseño: "
               "la API no está desplegada en la nube. Se eligió AWS porque cubre con servicios "
               "administrados todo lo que la aplicación usa en Docker Compose (contenedor, PostgreSQL, "
               "secretos y logs) sin cambiar el código. El detalle completo está en "
               "<font face='Courier'>docs/despliegue-nube.md</font>."))
    h += diagrama(DOCS / "diagramas" / "aws-vertical.png", "Arquitectura de despliegue propuesta en AWS.")
    h.append(p("Componentes", "h2"))
    h += tabla([
        ["Necesidad", "En Docker Compose", "En AWS"],
        ["Imagen", "Se construye localmente", "Amazon ECR, con escaneo al subir y etiquetas inmutables"],
        ["Contenedor", "Servicio api", "ECS sobre Fargate, en subredes privadas"],
        ["Base de datos", "Contenedor postgres:16", "RDS for PostgreSQL 16, Multi-AZ, cifrada con KMS y TLS obligatorio"],
        ["Secretos", "Archivo .env", "AWS Secrets Manager, inyectados en la tarea al arrancar"],
        ["Entrada HTTP", "Puerto 8000", "Application Load Balancer con HTTPS (certificado de ACM)"],
        ["Protección perimetral", "—", "AWS WAF: reglas administradas, límite de tasa en /auth/login y lista de IPs permitidas"],
        ["Logs y auditoría", "Salida del contenedor y tabla audit_log", "CloudWatch Logs y alarmas; la tabla audit_log sigue en RDS"],
        ["Salida a internet", "Red de Docker", "NAT Gateway, solo para descargar las fuentes"],
    ], [0.22, 0.3, 0.48])
    h.append(p("Red", "h2"))
    h += vinetas([
        "VPC con dos zonas de disponibilidad. En las subredes públicas solo están el balanceador y el NAT Gateway.",
        "Las tareas de ECS y la base de datos están en subredes privadas, sin IP pública.",
        "Grupos de seguridad encadenados: el balanceador acepta 443 desde internet (filtrado por WAF); "
        "las tareas aceptan 8000 solo desde el balanceador; RDS acepta 5432 solo desde las tareas.",
    ])
    h.append(p("Dos servicios con la misma imagen", "h2"))
    h.append(p("El planificador de ingesta corre dentro del proceso de la API y su bloqueo vive en memoria. "
               "Con varias tareas, cada una descargaría las fuentes y dan.me.uk podría bloquear la IP de salida. "
               "Por eso se crean dos servicios de ECS que solo se distinguen por una variable que la aplicación ya soporta:"))
    h += tabla([
        ["Servicio", "Tareas", "SCHEDULER_ ENABLED", "Balanceador", "Función"],
        ["api", "2 o más, escalado por CPU", "false", "Sí", "Atiende las peticiones"],
        ["ingesta", "Exactamente 1", "true", "No", "Descarga las fuentes y actualiza la base"],
    ], [0.11, 0.22, 0.27, 0.15, 0.25])
    h.append(p("Seguridad en la nube", "h2"))
    h += vinetas([
        "<b>Secretos:</b> JWT_SECRET, ADMIN_PASSWORD, DATABASE_URL y BIGDATACLOUD_API_KEY en Secrets Manager. "
        "El rol de ejecución solo puede leer esos secretos y descargar la imagen; la aplicación no necesita "
        "permisos de AWS.",
        "<b>Límite de login:</b> el límite de la aplicación vive en memoria; con varias tareas lo reemplaza una "
        "regla de límite de tasa de WAF sobre /auth/login.",
        "<b>IP real del cliente:</b> con <font face='Courier'>FORWARDED_ALLOW_IPS=10.0.0.0/16</font>, Uvicorn toma "
        "la IP que agrega el balanceador y la auditoría registra el origen real, sin que un cliente pueda "
        "falsificarla con su propia cabecera X-Forwarded-For. No requiere cambios en el código.",
        "<b>Contenedor:</b> usuario sin privilegios y sistema de archivos raíz en solo lectura.",
        "<b>Alertas:</b> filtros de métricas en CloudWatch para picos de 401, 403 y 429, fuentes con error y "
        "tareas caídas; CloudTrail registra los cambios de infraestructura.",
    ])
    h.append(p("Despliegue continuo", "h2"))
    h += vinetas([
        "El pipeline de GitHub Actions existente agrega un trabajo de despliegue en la rama main, que solo corre "
        "si pasan las pruebas y los análisis de seguridad.",
        "Se autentica en AWS con OIDC (sin claves guardadas en GitHub), construye la imagen, la escanea con Trivy, "
        "la sube a ECR con el hash del commit y actualiza los dos servicios.",
        "ECS hace un despliegue gradual y vuelve a la versión anterior si las tareas nuevas no pasan /health.",
        "La infraestructura se describe como código (Terraform o AWS CDK) y se revisa en pull requests.",
    ])
    h.append(p("Primer despliegue", "h2"))
    h += codigo(
        "aws ecr create-repository --repository-name tor-ip-api \\\n"
        "    --image-scanning-configuration scanOnPush=true \\\n"
        "    --image-tag-mutability IMMUTABLE\n"
        "TAG=$(git rev-parse --short HEAD)\n"
        "docker build -t $REPO:$TAG . && docker push $REPO:$TAG\n"
        "aws secretsmanager create-secret --name tor-ip-api/jwt-secret \\\n"
        "    --secret-string \"$(openssl rand -base64 48)\"\n"
        "aws ecs register-task-definition \\\n"
        "    --cli-input-json file://task-api.json\n"
        "aws ecs create-service --cluster tor-ip-api --service-name api \\\n"
        "    --desired-count 2 --launch-type FARGATE ...")
    h.append(p("Al arrancar por primera vez, la aplicación crea las tablas y el administrador inicial, igual que "
               "en Docker Compose. Los mayores costos mensuales son el NAT Gateway, RDS Multi-AZ, el balanceador "
               "y Fargate; se estiman con la AWS Pricing Calculator."))
    h.append(p("Equivalentes en GCP y Azure", "h2"))
    h += tabla([
        ["Necesidad", "AWS", "GCP", "Azure"],
        ["Imágenes", "ECR", "Artifact Registry", "Container Registry"],
        ["Contenedores", "ECS Fargate", "Cloud Run", "Container Apps"],
        ["PostgreSQL", "RDS", "Cloud SQL", "Database for PostgreSQL"],
        ["Secretos", "Secrets Manager", "Secret Manager", "Key Vault"],
        ["Balanceador", "ALB + ACM", "Cloud Load Balancing", "Application Gateway"],
        ["WAF", "AWS WAF", "Cloud Armor", "Azure WAF"],
        ["Logs y alertas", "CloudWatch", "Cloud Logging y Monitoring", "Azure Monitor"],
    ], [0.19, 0.23, 0.29, 0.29])
    return h


def numerar(canvas, doc):
    if doc.page == 1:
        return
    canvas.saveState()
    canvas.setFont("Helvetica", 8.5)
    canvas.setFillColor(GRIS_TEXTO)
    canvas.drawString(inch, 0.6 * inch, "Tor IP API · Documentación técnica")
    canvas.drawRightString(letter[0] - inch, 0.6 * inch, f"Página {doc.page}")
    canvas.restoreState()


def main():
    doc = SimpleDocTemplate(
        str(SALIDA), pagesize=letter,
        leftMargin=inch, rightMargin=inch, topMargin=0.9 * inch, bottomMargin=0.9 * inch,
        title="Tor IP API · Documentación técnica", author="AnaLauraRG",
        subject="Reto 1 · Challenge Cybersecurity Engineer (BISO)",
    )
    historia = []
    historia += portada()
    historia += descripcion()
    historia += arquitectura()
    historia.append(PageBreak())
    historia += requisitos_y_config()
    historia.append(PageBreak())
    historia += ejecucion_docker()
    historia += ejecucion_local()
    historia.append(PageBreak())
    historia += acceso()
    historia += endpoints()
    historia.append(PageBreak())
    historia += evidencias()
    historia.append(PageBreak())
    historia += seguridad()
    historia.append(PageBreak())
    historia += nube()
    doc.build(historia, onFirstPage=numerar, onLaterPages=numerar)

    total = contador["n"]
    con_imagen = sum(1 for f in CAPTURAS.glob("*.png")) if CAPTURAS.exists() else 0
    print(f"PDF generado: {SALIDA}")
    print(f"Capturas descritas: {total}; imágenes encontradas en docs/capturas/: {con_imagen}")


if __name__ == "__main__":
    main()
