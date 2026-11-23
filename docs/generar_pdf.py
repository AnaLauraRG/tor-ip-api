"""Genera docs/Documentacion_Tor_IP_API.pdf.

Cada captura se describe en un recuadro. Si la imagen correspondiente existe en
docs/capturas/ (con el nombre indicado en el recuadro), se inserta en su lugar.
Para actualizar el PDF después de tomar capturas, basta con volver a ejecutar:

    python3 docs/generar_pdf.py

Requiere reportlab y Pillow (en Kali: sudo apt install python3-reportlab python3-pil).
"""

import hashlib
import re
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
from reportlab.platypus.tableofcontents import TableOfContents

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
    "h3": ParagraphStyle("h3", parent=base["Heading3"], fontName="Helvetica-Bold",
                         fontSize=11.5, leading=15, textColor=GRIS_TEXTO, spaceBefore=8, spaceAfter=4,
                         keepWithNext=True),
    "indice": ParagraphStyle("indice", parent=base["Heading1"], fontName="Helvetica-Bold",
                             fontSize=17, leading=22, textColor=ACENTO, spaceAfter=6),
    "toc0": ParagraphStyle("toc0", parent=base["Normal"], fontName="Helvetica-Bold",
                           fontSize=10.5, leading=13, leftIndent=0, firstLineIndent=0, spaceBefore=4,
                           textColor=ACENTO),
    "toc1": ParagraphStyle("toc1", parent=base["Normal"], fontName="Helvetica",
                           fontSize=9.5, leading=12, leftIndent=16, firstLineIndent=0),
    "body": ParagraphStyle("body", parent=base["Normal"], fontName="Helvetica",
                           fontSize=11, leading=15.5, spaceAfter=7),
    "bullet": ParagraphStyle("bullet", parent=base["Normal"], fontName="Helvetica",
                             fontSize=11, leading=15.5, leftIndent=16, bulletIndent=4, spaceAfter=3),
    "celda": ParagraphStyle("celda", parent=base["Normal"], fontName="Helvetica",
                            fontSize=9.5, leading=12.5),
    "celda_b": ParagraphStyle("celda_b", parent=base["Normal"], fontName="Helvetica-Bold",
                              fontSize=9.5, leading=12.5, textColor=colors.white),
    "code": ParagraphStyle("code", parent=base["Code"], fontName="Courier",
                           fontSize=8.5, leading=11.5, leftIndent=0),
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
    pre = Preformatted(texto.strip("\n"), S["code"], maxLineLength=86, newLineChars="      ")
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
    h.append(p("La aplicación corre en dos contenedores dentro de una red interna de Docker Compose. "
               "El diagrama sigue el camino de una petición de arriba hacia abajo y, a la derecha, "
               "la descarga de las fuentes."))
    h += diagrama(DOCS / "diagramas" / "arquitectura.png",
                  "Arquitectura de Tor IP API con Docker Compose.", alto=6.7 * inch)
    h.append(PageBreak())
    h += tabla([
        ["Componente", "Tecnología", "Función"],
        ["Middleware HTTP", "FastAPI", "Registra cada petición en la auditoría y agrega cabeceras de seguridad."],
        ["Endpoints", "FastAPI, Pydantic", "Validan los datos y exigen el rol que corresponde a cada ruta."],
        ["Seguridad", "bcrypt, PyJWT", "Verifica contraseñas y tokens; lee el rol y el estado del usuario en la base."],
        ["Planificador de ingesta", "APScheduler", "Cada 5 minutos revisa qué fuentes toca descargar."],
        ["Servicio de ingesta", "httpx", "Descarga las fuentes respetando su intervalo, valida las IPs y actualiza la base."],
        ["Base de datos", "PostgreSQL 16", "IPs de Tor, exclusiones, usuarios, auditoría y estado de las fuentes."],
        ["Contenedores", "Docker Compose", "API y base en una red interna; solo el puerto 8000 queda publicado."],
    ], [0.24, 0.2, 0.56])
    h.append(p("<b>Dos caminos independientes.</b> Los clientes leen de PostgreSQL a través de la API, y la "
               "ingesta escribe en PostgreSQL desde las fuentes. Solo se encuentran en la base de datos: "
               "una petición nunca espera a que se descargue una fuente y dan.me.uk nunca se consulta "
               "más de lo que permite."))
    h.append(p("<b>Flujo de una petición.</b> El middleware la registra; el endpoint pide al módulo de "
               "seguridad que valide el token y el rol; si pasa, consulta PostgreSQL y responde en JSON. "
               "Las peticiones sin token o sin permiso se rechazan con 401 o 403 y también quedan en la "
               "auditoría."))
    return h


def requisitos_y_config():
    h = [p("3. Requisitos y descarga", "h1")]
    h += vinetas([
        "<b>Git</b>, para descargar el repositorio, y acceso a él: es privado, así que hay que aceptar "
        "antes la invitación de GitHub.",
        "<b>Con Docker:</b> Docker con Docker Compose, o Podman con su socket activo.",
        "<b>Sin Docker:</b> Python 3.13 y, opcionalmente, PostgreSQL 16.",
        "Una API key gratuita de bigdatacloud.com (opcional: sin ella, esa fuente se omite).",
    ])
    h.append(p("Descargar el proyecto", "h2"))
    h.append(p("Como el repositorio es privado, GitHub pide autenticarse al clonar. Basta con una de estas "
               "opciones; en la primera, la contraseña que pide Git es un token personal de GitHub "
               "(<i>Settings → Developer settings → Personal access tokens</i>), no la contraseña de la cuenta."))
    h += codigo(
        "git clone https://github.com/AnaLauraRG/tor-ip-api.git     # HTTPS con token personal\n"
        "git clone git@github.com:AnaLauraRG/tor-ip-api.git         # SSH con llave registrada\n"
        "gh repo clone AnaLauraRG/tor-ip-api                        # GitHub CLI\n"
        "cd tor-ip-api")
    h.append(p("Todos los comandos de las secciones siguientes se ejecutan desde la carpeta "
               "<font face='Courier'>tor-ip-api</font>. Para actualizar más adelante: "
               "<font face='Courier'>git pull &amp;&amp; docker compose up --build -d</font>."))
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


C = "<font face='Courier'>{}</font>".format


def ejecucion():
    h = [p("5. Ejecución", "h1")]
    h.append(p("La aplicación se puede ejecutar de dos formas: con Docker Compose, que levanta la API y "
               "PostgreSQL igual que en producción, o directamente desde el repositorio con Python, útil "
               "para desarrollo. Ambas leen la configuración del archivo " + C(".env") + "."))

    h.append(p("5.1 Con Docker", "h2"))
    h.append(p("Desde la carpeta del proyecto, con el archivo " + C(".env") + " ya configurado:"))
    h += codigo("docker compose up --build")
    h.append(p("Compose construye la imagen de la API, levanta PostgreSQL, espera a que la base esté "
               "lista y arranca la API en " + C("http://localhost:8000") + ". Al iniciar se "
               "crea el administrador y corre el primer ciclo de descarga de las fuentes. "
               "Con Podman en lugar de Docker, antes hay que activar su socket con "
               + C("systemctl --user enable --now podman.socket") + "."))
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

    h.append(p("5.2 Desde el repositorio, sin Docker", "h2"))
    h.append(p("Con Python 3.13, desde la carpeta del repositorio. Sin la variable " + C("DATABASE_URL")
               + " la API usa un archivo SQLite local (" + C("tor.db") + "); el puerto 8001 evita chocar "
               "con la versión en Docker si está corriendo."))
    h += codigo(
        "python3 -m venv .venv && source .venv/bin/activate\n"
        "pip install -r requirements-dev.txt\n"
        "cp .env.example .env     # completar al menos JWT_SECRET y ADMIN_PASSWORD\n"
        "uvicorn app.main:app --reload --port 8001\n"
        "pytest                   # pruebas automáticas; simulan las fuentes, sin internet")
    h.append(p("Para usar PostgreSQL en lugar de SQLite: "
               + C("export DATABASE_URL=postgresql+psycopg://usuario:clave@localhost:5432/tor") + "."))
    return h


def autenticacion():
    h = [p("6. Autenticación", "h1")]
    h.append(p("Todos los métodos, excepto " + C("POST /auth/login") + " y " + C("GET /health") + ", "
               "requieren un token. El token se obtiene con usuario y contraseña y se envía en la cabecera "
               + C("Authorization: Bearer &lt;token&gt;") + "."))
    h += codigo(
        'curl -X POST http://localhost:8000/auth/login \\\n'
        '     -d "username=admin&password=TU_CLAVE"')
    h += vinetas([
        "El token es un JWT firmado con HS256 que expira a los 30 minutos. Solo contiene el nombre de "
        "usuario; el rol se consulta en la base en cada petición.",
        "Las contraseñas se guardan con bcrypt. Si el usuario no existe o la contraseña es incorrecta, la "
        "respuesta y el tiempo de respuesta son los mismos, para no revelar qué usuarios existen.",
        "Tras 5 intentos fallidos en 15 minutos desde la misma IP, el login responde 429 hasta que pase la ventana.",
        "En Swagger UI (" + C("http://localhost:8000/docs") + ") se usa el botón <b>Authorize</b>; "
        "desde ese momento todas las peticiones llevan el token.",
    ])
    return h


def _metodo(metodo, ruta, quien, que_hace, entrada, respuestas):
    filas = [
        [Paragraph(f"<b>{metodo}</b>  <font face='Courier'>{ruta}</font>", S["celda_b"]), ""],
        [Paragraph("<b>Qué hace</b>", S["celda"]), Paragraph(que_hace, S["celda"])],
        [Paragraph("<b>Quién puede ejecutarlo</b>", S["celda"]), Paragraph(quien, S["celda"])],
        [Paragraph("<b>Entrada</b>", S["celda"]), Paragraph(entrada, S["celda"])],
        [Paragraph("<b>Respuestas</b>", S["celda"]), Paragraph(respuestas, S["celda"])],
    ]
    t = Table(filas, colWidths=[ANCHO_UTIL * 0.24, ANCHO_UTIL * 0.76])
    t.setStyle(TableStyle([
        ("SPAN", (0, 0), (-1, 0)),
        ("BACKGROUND", (0, 0), (-1, 0), ACENTO),
        ("BACKGROUND", (0, 1), (0, -1), GRIS_FONDO),
        ("GRID", (0, 0), (-1, -1), 0.5, GRIS_BORDE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return [KeepTogether([t, Spacer(1, 10)])]


def unir_titulos(h):
    """Pega cada subtítulo h3 al bloque que le sigue, para que nunca quede solo al pie de una página."""
    salida = []
    for elem in h:
        if (isinstance(elem, KeepTogether) and salida and isinstance(salida[-1], Paragraph)
                and salida[-1].style.name == "h3"):
            elem = KeepTogether([salida.pop()] + list(elem._content))
        salida.append(elem)
    return salida


def metodos():
    publico = "<b>Cualquiera</b>, sin token."
    lectura = "<b>reader</b> y <b>admin</b>. Sin token: 401."
    admin = "<b>Solo admin</b>. Un reader recibe 403; sin token: 401."
    h = [p("7. Métodos de la API", "h1")]
    h.append(p("La API tiene 11 métodos. Los tres que pide el reto son " + C("GET /ips") + ", "
               + C("POST /exclusions") + " y " + C("GET /ips/filtered") + "; los demás son extras. "
               "La tabla resume qué hace cada uno y quién lo puede ejecutar; después se detalla cada método."))
    h.append(p("7.1 Resumen", "h2"))
    h += tabla([
        ["Método", "Ruta", "Qué hace", "Quién puede"],
        ["POST", "/auth/login", "Entrega un token a cambio de usuario y contraseña.", "Cualquiera"],
        ["GET", "/ips", "Lista todas las IPs de Tor de las fuentes. <b>(Reto)</b>", "reader, admin"],
        ["GET", "/ips/filtered", "Lista las IPs de Tor menos las excluidas. <b>(Reto)</b>", "reader, admin"],
        ["GET", "/exclusions", "Lista las IPs excluidas con su motivo y fecha.", "reader, admin"],
        ["POST", "/exclusions", "Agrega una IP a las exclusiones. <b>(Reto)</b>", "admin"],
        ["DELETE", "/exclusions/{ip}", "Quita una IP de las exclusiones.", "admin"],
        ["POST", "/sources/refresh", "Descarga las fuentes sin esperar su intervalo.", "admin"],
        ["GET", "/users", "Lista los usuarios, su rol y su estado.", "admin"],
        ["POST", "/users", "Crea un usuario reader o admin.", "admin"],
        ["GET", "/audit", "Consulta el registro de auditoría.", "admin"],
        ["GET", "/health", "Estado del servicio y de cada fuente.", "Cualquiera"],
    ], [0.11, 0.21, 0.5, 0.18])

    h.append(p("7.2 Detalle por método", "h2"))
    h.append(p("Autenticación", "h3"))
    h += _metodo("POST", "/auth/login", publico,
                 "Verifica usuario y contraseña y devuelve un token JWT válido por 30 minutos.",
                 "Formulario " + C("application/x-www-form-urlencoded") + " con " + C("username") + " y "
                 + C("password") + ".",
                 "<b>200</b> con " + C("access_token") + ", " + C("token_type") + " y " + C("expires_in")
                 + ". <b>401</b> si las credenciales son incorrectas o el usuario está desactivado. "
                 "<b>429</b> tras 5 intentos fallidos en 15 minutos, con la cabecera " + C("Retry-After") + ".")
    h.append(p("IPs de Tor", "h3"))
    h += _metodo("GET", "/ips", lectura,
                 "Devuelve todas las IPs de Tor obtenidas de las tres fuentes, sin duplicados y ordenadas. "
                 "Lee de la base; nunca consulta las fuentes en el momento.",
                 "Ninguna.",
                 "<b>200</b> con " + C("count") + " (total) e " + C("ips") + " (lista). <b>401</b> sin token válido.")
    h += _metodo("GET", "/ips/filtered", lectura,
                 "Devuelve las mismas IPs que " + C("/ips") + " exceptuando las que están en la base de "
                 "exclusiones. Es el listado que consumiría un firewall o un WAF.",
                 "Ninguna.",
                 "<b>200</b> con " + C("count") + " e " + C("ips") + ". <b>401</b> sin token válido.")
    h.append(p("Exclusiones", "h3"))
    h += _metodo("GET", "/exclusions", lectura,
                 "Lista las IPs excluidas con su motivo y la fecha en que se agregaron, de la más reciente a la más antigua.",
                 "Ninguna.",
                 "<b>200</b> con la lista. <b>401</b> sin token válido.")
    h += _metodo("POST", "/exclusions", admin,
                 "Agrega una IP a la base de exclusiones para que deje de aparecer en " + C("/ips/filtered")
                 + ". La IP se valida y se guarda en forma canónica (IPv4 o IPv6).",
                 "JSON con " + C("ip") + " (obligatoria) y " + C("reason") + " (opcional, hasta 255 caracteres).",
                 "<b>201</b> con la IP, el motivo y la fecha. <b>409</b> si ya estaba excluida. "
                 "<b>422</b> si no es una IP válida. <b>401</b> / <b>403</b> según el acceso.")
    h += _metodo("DELETE", "/exclusions/{ip}", admin,
                 "Quita una IP de las exclusiones; vuelve a aparecer en " + C("/ips/filtered")
                 + " si alguna fuente la reporta.",
                 "La IP en la ruta.",
                 "<b>204</b> sin contenido. <b>404</b> si no estaba excluida. <b>422</b> si no es una IP "
                 "válida. <b>401</b> / <b>403</b> según el acceso.")
    h.append(p("Fuentes", "h3"))
    h += _metodo("POST", "/sources/refresh", admin,
                 "Descarga las fuentes en ese momento, sin esperar su intervalo normal. Aun así respeta el "
                 "mínimo de cada fuente: dan.me.uk nunca se consulta más de una vez cada 30 minutos y aparece "
                 "como " + C("skipped") + " si es muy pronto.",
                 "Ninguna.",
                 "<b>200</b> con el resultado por fuente y su estado. <b>409</b> si ya hay una actualización "
                 "en curso. <b>401</b> / <b>403</b> según el acceso.")
    h.append(p("Usuarios", "h3"))
    h += _metodo("GET", "/users", admin,
                 "Lista los usuarios con su rol, si están activos y su fecha de creación. Nunca devuelve "
                 "contraseñas ni hashes.",
                 "Ninguna.",
                 "<b>200</b> con la lista. <b>401</b> / <b>403</b> según el acceso.")
    h += _metodo("POST", "/users", admin,
                 "Crea un usuario. Si no se indica el rol, se crea como " + C("reader") + ".",
                 "JSON con " + C("username") + " (3 a 50 caracteres: letras, números, " + C("_ . -")
                 + "), " + C("password") + " (12 caracteres o más) y " + C("role") + " (" + C("reader")
                 + " o " + C("admin") + ", opcional).",
                 "<b>201</b> con el usuario creado, sin la contraseña. <b>409</b> si ya existe. "
                 "<b>422</b> si los datos no cumplen las reglas. <b>401</b> / <b>403</b> según el acceso.")
    h.append(p("Auditoría y estado", "h3"))
    h += _metodo("GET", "/audit", admin,
                 "Consulta el registro de auditoría: cada petición con fecha, usuario, método, ruta, código "
                 "de respuesta, IP de origen, user agent y duración, de la más reciente a la más antigua.",
                 "Parámetros opcionales " + C("limit") + " (1 a 500, por defecto 100), " + C("offset")
                 + " y " + C("username") + " para filtrar por usuario.",
                 "<b>200</b> con la lista. <b>422</b> si los parámetros no son válidos. "
                 "<b>401</b> / <b>403</b> según el acceso.")
    h += _metodo("GET", "/health", publico,
                 "Indica si el servicio y la base funcionan y muestra, por fuente, su último intento, "
                 "su último éxito, el último error y cuántas IPs aporta. Lo usan Docker y el balanceador "
                 "para saber si el contenedor está sano.",
                 "Ninguna.",
                 "<b>200</b> con el estado. <b>503</b> si la base de datos no está disponible.")
    h.append(p("Códigos de respuesta", "h3"))
    h += tabla([
        ["Código", "Significado"],
        ["200 / 201 / 204", "Éxito: consulta, creación o eliminación."],
        ["401", "Sin token, token inválido o expirado, usuario desactivado o credenciales incorrectas."],
        ["403", "El rol del usuario no permite la operación."],
        ["404", "La exclusión a eliminar no existe."],
        ["409", "La IP ya está excluida, el usuario ya existe o hay una actualización en curso."],
        ["422", "Datos inválidos, por ejemplo una IP mal formada."],
        ["429", "Demasiados intentos de login fallidos; la cabecera Retry-After indica cuándo reintentar."],
        ["503", "La base de datos no está disponible (solo /health)."],
    ], [0.22, 0.78])
    h.append(p("La documentación interactiva de todos los métodos está en " + C("http://localhost:8000/docs")
               + " (Swagger UI)."))
    h += captura("00d-swagger.png", "Documentación interactiva (Swagger UI)",
                 "<font face='Courier'>http://localhost:8000/docs</font> en el navegador",
                 "Abrir la página sin desplegar ningún endpoint.",
                 "la lista completa de endpoints agrupados por sección (auth, ips, exclusions, sources, "
                 "users, audit, health) y el botón <i>Authorize</i>.")
    return unir_titulos(h)


def permisos():
    si, no403, no401 = "Sí", "No (403)", "No (401)"
    h = [p("8. Esquema de permisos", "h1")]
    h.append(p("El acceso se controla con roles (RBAC). Cada usuario tiene exactamente un rol, y cada método "
               "declara qué roles lo pueden ejecutar. Lo que no está permitido de forma explícita se rechaza."))
    h.append(p("8.1 Roles", "h2"))
    h += tabla([
        ["Rol", "Para quién", "Qué puede hacer"],
        ["Público (sin token)", "Cualquier cliente", "Iniciar sesión y consultar el estado del servicio."],
        ["reader", "Analistas y sistemas que consumen la lista (firewall, WAF)",
         "Consultar las IPs de Tor, el listado filtrado y las exclusiones. No modifica nada."],
        ["admin", "Responsables de la herramienta",
         "Todo lo del reader, más gestionar exclusiones, usuarios, actualizar las fuentes y ver la auditoría."],
    ], [0.2, 0.33, 0.47])
    h.append(p("8.2 Matriz de permisos", "h2"))
    h += tabla([
        ["Método", "Sin token", "reader", "admin"],
        ["POST /auth/login", si, si, si],
        ["GET /health", si, si, si],
        ["GET /ips", no401, si, si],
        ["GET /ips/filtered", no401, si, si],
        ["GET /exclusions", no401, si, si],
        ["POST /exclusions", no401, no403, si],
        ["DELETE /exclusions/{ip}", no401, no403, si],
        ["POST /sources/refresh", no401, no403, si],
        ["GET /users", no401, no403, si],
        ["POST /users", no401, no403, si],
        ["GET /audit", no401, no403, si],
    ], [0.4, 0.2, 0.2, 0.2])
    h.append(p("Las capturas 11 a 17 de la sección 9 demuestran esta matriz: peticiones sin token y con token "
               "manipulado (401), el reader consultando (200) y el reader intentando excluir una IP y ver la "
               "auditoría (403)."))
    h.append(p("8.3 Cómo se aplica", "h2"))
    h += vinetas([
        "<b>En cada petición:</b> se valida la firma y la expiración del token, se busca al usuario en la base "
        "y se comprueba que siga activo, y por último se compara su rol con los roles que acepta el método. "
        "Si falla la identidad responde 401; si falla el rol, 403.",
        "<b>El rol no viaja en el token.</b> Se lee de la base en cada petición, así que desactivar a un usuario "
        "o cambiar su rol tiene efecto inmediato, aunque su token siga vigente.",
        "<b>Declarado en el código, no en cada función:</b> los routers de " + C("/users") + ", "
        + C("/audit") + ", " + C("/sources") + " e " + C("/ips") + " exigen el rol a nivel de router, de modo "
        "que un método nuevo en ellos queda protegido por defecto. En " + C("/exclusions") + " cada método "
        "declara el suyo, porque mezcla lectura (reader) y escritura (admin).",
        "<b>Todo queda auditado:</b> los accesos permitidos y los rechazados (401, 403 y 429) se registran con "
        "usuario, ruta, código e IP de origen.",
    ])
    h.append(p("8.4 Gestión de usuarios", "h2"))
    h += vinetas([
        "<b>Administrador inicial:</b> se crea en el primer arranque con " + C("ADMIN_USERNAME") + " y "
        + C("ADMIN_PASSWORD") + " del " + C(".env") + ". Después, cambiar esos valores no lo modifica.",
        "<b>Nuevos usuarios:</b> solo un admin los crea, con " + C("POST /users") + ". Por defecto son "
        + C("reader") + ", siguiendo el principio de mínimo privilegio. No hay registro público.",
        "<b>Contraseñas:</b> mínimo 12 caracteres, guardadas con bcrypt; ningún método las devuelve.",
        "<b>Desactivar o cambiar el rol:</b> no hay un método para hacerlo; se hace en la base con "
        + C("UPDATE users SET is_active = false WHERE username = '...'") + " (o cambiando " + C("role")
        + "). El cambio aplica de inmediato. Agregar estos métodos sería una extensión natural.",
    ])
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
    h = desde_markdown(DOCS / "sast-report.md", 10)
    h.insert(1, p("Esta sección reproduce el informe " + C("docs/sast-report.md") + " del repositorio. Los "
                  "controles de autenticación y permisos de la aplicación están en las secciones 6 y 8, y los "
                  "de la nube en la sección 11."))
    return h


def diagrama(ruta, pie, alto=6.4 * inch):
    img = Image(str(ruta))
    escala = min(ANCHO_UTIL / img.imageWidth, alto / img.imageHeight)
    img.drawWidth = img.imageWidth * escala
    img.drawHeight = img.imageHeight * escala
    img.hAlign = "CENTER"
    return [KeepTogether([img, Paragraph(pie, S["pie_img"])])]


def _inline(texto):
    """Markdown en línea (negrita, cursiva, código, enlaces) a las etiquetas de reportlab."""
    texto = texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    codigos = []

    def guardar(m):
        codigos.append(m.group(1))
        return f"\x00{len(codigos) - 1}\x00"

    texto = re.sub(r"`([^`]+)`", guardar, texto)
    texto = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<link href='\2' color='#1F4E79'>\1</link>", texto)
    texto = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", texto)
    texto = re.sub(r"(?<![\w*])\*([^*]+)\*(?![\w*])", r"<i>\1</i>", texto)
    return re.sub(r"\x00(\d+)\x00", lambda m: f"<font face='Courier'>{codigos[int(m.group(1))]}</font>", texto)


def anchos_columnas(filas):
    """Reparte el ancho: cada columna recibe al menos su palabra más larga y el resto
    se reparte según cuánto texto tiene."""
    def visible(celda):
        return re.sub(r"<[^>]+>", "", celda).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")

    columnas = range(len(filas[0]))
    # Una palabra muy larga (una versión, un hash) se parte; no debe acaparar la tabla.
    minimo = [min(max(max((len(w) for w in visible(f[k]).split()), default=1) for f in filas) * 5.3 + 12, 105)
              for k in columnas]
    deseado = [max(min(len(visible(f[k])), 70) for f in filas) * 5.0 + 12 for k in columnas]
    deseado = [max(d, m) for d, m in zip(deseado, minimo)]
    if sum(deseado) <= ANCHO_UTIL:
        return [d / sum(deseado) for d in deseado]
    extra = ANCHO_UTIL - sum(minimo)
    if extra <= 0:
        return [m / sum(minimo) for m in minimo]
    holgura = [d - m for d, m in zip(deseado, minimo)]
    return [(m + extra * hgl / sum(holgura)) / ANCHO_UTIL for m, hgl in zip(minimo, holgura)]


def desde_markdown(ruta, numero):
    """Convierte docs/despliegue-nube.md en elementos del PDF.

    Así el documento del repositorio y la sección del PDF no se desincronizan.
    Las secciones "## N. Título" pasan a "numero.N Título".
    """
    h = []
    lineas = _renumerar(ruta.read_text(encoding="utf-8"), numero).splitlines()
    i = 0
    while i < len(lineas):
        linea = lineas[i]
        if linea.startswith("# "):
            h.append(p(f"{numero}. {_inline(linea[2:])}", "h1"))
        elif linea.startswith("## "):
            titulo = re.sub(r"^(\d+)\.\s*", rf"{numero}.\1 ", linea[3:])
            h.append(p(_inline(titulo), "h2"))
        elif linea.startswith("### "):
            h.append(p(_inline(linea[4:]), "h3"))
        elif linea.startswith("```"):
            bloque = []
            i += 1
            while not lineas[i].startswith("```"):
                bloque.append(lineas[i])
                i += 1
            h += codigo("\n".join(bloque))
        elif linea.startswith("!["):
            m = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", linea)
            ruta_img = DOCS / m.group(2)
            vertical = ruta_img.with_name(ruta_img.stem + "-vertical.png")
            figura = diagrama(vertical if vertical.exists() else ruta_img, m.group(1) + ".", alto=6.2 * inch)
            if h and isinstance(h[-1], Paragraph) and h[-1].style.name in ("h2", "h3"):
                figura = [KeepTogether([h.pop()] + figura)]
            h += figura
        elif linea.startswith("|"):
            filas = []
            while i < len(lineas) and lineas[i].startswith("|"):
                celdas = [c.strip() for c in lineas[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", c) for c in celdas):
                    filas.append([_inline(c) for c in celdas])
                i += 1
            h += tabla(filas, anchos_columnas(filas))
            continue
        elif re.match(r"^\s*(-|\d+\.)\s", linea):
            items = []
            while i < len(lineas) and re.match(r"^\s*(-|\d+\.)\s", lineas[i]):
                m = re.match(r"^\s*(-|\d+\.)\s+(.*)", lineas[i])
                marca = "•" if m.group(1) == "-" else m.group(1)
                items.append(Paragraph(_inline(m.group(2)), S["bullet"], bulletText=marca))
                i += 1
            h += items + [Spacer(1, 4)]
            continue
        elif linea.strip():
            h.append(p(_inline(linea)))
        i += 1
    return h


def _renumerar(texto, numero):
    """Las referencias internas del Markdown ("sección 3") pasan a la numeración del PDF ("sección 10.3")."""
    return re.sub(r"\b(secci[oó]n) (\d+)\b", rf"\1 {numero}.\2", texto)


def nube():
    h = desde_markdown(DOCS / "despliegue-nube.md", 11)
    h.insert(1, p("Esta sección reproduce <font face='Courier'>docs/despliegue-nube.md</font> del repositorio."))
    return h


def indice():
    toc = TableOfContents()
    toc.levelStyles = [S["toc0"], S["toc1"]]
    toc.dotsMinLevel = 0
    toc.tableStyle = TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ])
    return [Paragraph("Índice", S["indice"]),
            p("Haz clic en un título para ir a su sección; el enlace <i>Índice</i> del pie de página regresa aquí."),
            toc, PageBreak()]


class Documento(SimpleDocTemplate):
    """Agrega cada título al índice clicable y a los marcadores del PDF."""

    def afterFlowable(self, flowable):
        if not isinstance(flowable, Paragraph):
            return
        nombre = flowable.style.name
        if nombre == "indice":
            self.canv.bookmarkPage("indice")
            return
        if nombre not in ("h1", "h2"):
            return
        nivel = 0 if nombre == "h1" else 1
        texto = flowable.getPlainText()
        clave = "s" + hashlib.md5(texto.encode()).hexdigest()[:10]
        self.canv.bookmarkPage(clave)
        self.canv.addOutlineEntry(texto, clave, level=nivel, closed=nivel == 0)
        self.notify("TOCEntry", (nivel, texto, self.page, clave))


def numerar(canvas, doc):
    if doc.page == 1:
        return
    canvas.saveState()
    canvas.setFont("Helvetica", 8.5)
    canvas.setFillColor(GRIS_TEXTO)
    canvas.drawString(inch, 0.6 * inch, "Tor IP API · Documentación técnica")
    centro = letter[0] / 2
    canvas.setFillColor(ACENTO)
    canvas.drawCentredString(centro, 0.6 * inch, "Índice")
    ancho = canvas.stringWidth("Índice", "Helvetica", 8.5)
    canvas.linkRect("", "indice", (centro - ancho / 2 - 2, 0.55 * inch, centro + ancho / 2 + 2, 0.75 * inch),
                    relative=0, thickness=0)
    canvas.setFillColor(GRIS_TEXTO)
    canvas.drawRightString(letter[0] - inch, 0.6 * inch, f"Página {doc.page}")
    canvas.restoreState()


def main():
    doc = Documento(
        str(SALIDA), pagesize=letter,
        leftMargin=inch, rightMargin=inch, topMargin=0.9 * inch, bottomMargin=0.9 * inch,
        title="Tor IP API · Documentación técnica", author="AnaLauraRG",
        subject="Reto 1 · Challenge Cybersecurity Engineer (BISO)",
    )
    historia = []
    historia += portada()
    historia += indice()
    historia += descripcion()
    historia.append(PageBreak())
    historia += arquitectura()
    historia.append(PageBreak())
    historia += requisitos_y_config()
    historia.append(PageBreak())
    historia += ejecucion()
    historia.append(PageBreak())
    historia += autenticacion()
    historia.append(PageBreak())
    historia += metodos()
    historia.append(PageBreak())
    historia += permisos()
    historia.append(PageBreak())
    historia += evidencias()
    historia.append(PageBreak())
    historia += seguridad()
    historia.append(PageBreak())
    historia += nube()
    doc.multiBuild(historia, onFirstPage=numerar, onLaterPages=numerar)

    total = contador["n"]
    con_imagen = sum(1 for f in CAPTURAS.glob("*.png")) if CAPTURAS.exists() else 0
    print(f"PDF generado: {SALIDA}")
    print(f"Capturas descritas: {total}; imágenes encontradas en docs/capturas/: {con_imagen}")


if __name__ == "__main__":
    main()
