# Tor IP API

API REST que unifica las IPs de nodos de salida de Tor de varias fuentes externas y permite excluir IPs del listado. Incluye autenticación con JWT, control de acceso por roles y auditoría de todas las peticiones.

## Arquitectura

![Arquitectura de Tor IP API](docs/diagramas/arquitectura.png)

La API y PostgreSQL corren en dos contenedores dentro de una red interna de Docker Compose; solo el puerto 8000 queda publicado. Cada petición pasa por el middleware de auditoría, el endpoint exige el rol que le corresponde y el módulo de seguridad valida el token. En paralelo, el planificador descarga las tres fuentes y guarda las IPs en la base: los clientes leen de PostgreSQL y la ingesta escribe en PostgreSQL, así que una petición nunca espera a que se descargue una fuente.

## Endpoints

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| POST | `/auth/login` | Obtiene un token JWT | Público |
| GET | `/ips` | Todas las IPs de Tor obtenidas de las fuentes | reader, admin |
| GET | `/ips/filtered` | IPs de Tor exceptuando las excluidas | reader, admin |
| GET | `/exclusions` | Lista las IPs excluidas | reader, admin |
| POST | `/exclusions` | Agrega una IP a la base de exclusiones | admin |
| DELETE | `/exclusions/{ip}` | Quita una IP de las exclusiones | admin |
| POST | `/sources/refresh` | Descarga las fuentes sin esperar su intervalo | admin |
| GET | `/users` | Lista los usuarios | admin |
| POST | `/users` | Crea un usuario (reader o admin) | admin |
| GET | `/audit` | Consulta el registro de auditoría | admin |
| GET | `/health` | Estado del servicio y de cada fuente | Público |

Los tres endpoints obligatorios del reto son `GET /ips`, `POST /exclusions` y `GET /ips/filtered`; el resto son extras.

Documentación interactiva (Swagger): `http://localhost:8000/docs`. Pulsa **Authorize**, ingresa usuario y contraseña, y todos los endpoints usarán tu token.

## Paso a paso: descargar y ejecutar

### 1. Requisitos

| Herramienta | Para qué | Cómo comprobarlo |
|---|---|---|
| Git | Descargar el repositorio | `git --version` |
| Docker con Compose (o Podman) | Ejecutar la API y PostgreSQL | `docker compose version` |
| Acceso al repositorio | Es privado: hay que aceptar la invitación de GitHub | Abrir `https://github.com/AnaLauraRG/tor-ip-api` con tu cuenta |
| API key de bigdatacloud (opcional) | Usar la tercera fuente; sin ella se omite | Cuenta gratuita en bigdatacloud.com |

Con Podman en lugar de Docker, activa antes su socket: `systemctl --user enable --now podman.socket`.

### 2. Descargar el proyecto

Como el repositorio es privado, GitHub pide autenticarte al clonar. Usa **una** de estas opciones:

```bash
# Opción A: HTTPS. Como contraseña se usa un token personal de GitHub
# (Settings → Developer settings → Personal access tokens), no la contraseña de la cuenta.
git clone https://github.com/AnaLauraRG/tor-ip-api.git

# Opción B: SSH, si ya tienes una llave SSH registrada en GitHub
git clone git@github.com:AnaLauraRG/tor-ip-api.git

# Opción C: GitHub CLI, después de `gh auth login`
gh repo clone AnaLauraRG/tor-ip-api
```

Después entra a la carpeta; todos los comandos siguientes se ejecutan desde ahí:

```bash
cd tor-ip-api
```

### 3. Configurar el archivo `.env`

La configuración y los secretos van en un archivo `.env` que **no** se sube al repositorio. Se crea a partir de la plantilla:

```bash
cp .env.example .env
openssl rand -base64 48    # genera una clave; cópiala para JWT_SECRET
nano .env
```

Completa al menos estos valores:

| Variable | Qué poner |
|---|---|
| `POSTGRES_PASSWORD` | Una contraseña para PostgreSQL, solo con letras y números (va dentro de una URL) |
| `JWT_SECRET` | La clave que generó `openssl` (mínimo 32 caracteres; sin ella la API no arranca) |
| `ADMIN_PASSWORD` | La contraseña del administrador inicial, de 12 caracteres o más |
| `BIGDATACLOUD_API_KEY` | Tu API key de bigdatacloud, o vacía para omitir esa fuente |

El usuario del administrador es `admin` (variable `ADMIN_USERNAME`). Se crea solo en el primer arranque: si después cambias `ADMIN_PASSWORD`, no se modifica el usuario que ya existe.

### 4. Levantar la API

```bash
docker compose up --build -d
```

La primera vez tarda unos minutos, porque construye la imagen y descarga PostgreSQL. Compose levanta la base, espera a que esté lista y arranca la API; al iniciar, la API crea las tablas, el administrador y descarga las fuentes por primera vez.

### 5. Comprobar que funciona

```bash
docker compose ps                    # db y api en estado "Up" (healthy)
curl http://localhost:8000/health    # las tres fuentes con "last_status": "ok"
docker compose logs -f api           # ver los logs en vivo (Ctrl+C para salir)
```

Si `/health` aún muestra alguna fuente sin datos, espera uno o dos minutos a que termine la primera descarga.

### 6. Probar los endpoints

**Desde el navegador:** abre `http://localhost:8000/docs`, pulsa **Authorize**, escribe `admin` y la contraseña de tu `.env`, y ejecuta cualquier endpoint con **Try it out → Execute**.

**Desde la terminal** (la contraseña se pide sin mostrarse en pantalla; funciona en bash y en zsh):

```bash
printf "Contraseña del admin: "; read -rs PASS; echo
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  --data-urlencode "username=admin" --data-urlencode "password=$PASS" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
AUTH="Authorization: Bearer $TOKEN"

curl -H "$AUTH" http://localhost:8000/ips             # 1. todas las IPs de Tor
curl -H "$AUTH" -X POST http://localhost:8000/exclusions \
     -H "Content-Type: application/json" \
     -d '{"ip": "185.220.101.1", "reason": "falso positivo"}'   # 2. excluir una IP
curl -H "$AUTH" http://localhost:8000/ips/filtered    # 3. IPs sin las excluidas
```

También puedes importar la [colección de Postman](#colección-de-postman), que ejecuta 25 peticiones con sus verificaciones.

### 7. Detener, actualizar o empezar de cero

```bash
docker compose down                       # detiene la API y la base; los datos se conservan
git pull && docker compose up --build -d  # descarga los últimos cambios y vuelve a levantar
docker compose down -v                    # detiene y BORRA la base (usuarios, exclusiones y auditoría)
```

### Alternativa: ejecutar sin Docker

Útil para desarrollo. Requiere Python 3.13:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env       # completa al menos JWT_SECRET y ADMIN_PASSWORD
uvicorn app.main:app --reload --port 8001
```

La API queda en `http://localhost:8001` (el puerto 8001 evita chocar con la versión en Docker). Sin `DATABASE_URL` definida se usa un archivo SQLite local (`tor.db`), suficiente para desarrollo. Para usar PostgreSQL:

```bash
export DATABASE_URL=postgresql+psycopg://usuario:clave@localhost:5432/tor
```

## Más ejemplos

```bash
# Obtener un token (el login recibe un formulario, no JSON)
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
     -d "username=admin&password=TU_CLAVE" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
AUTH="Authorization: Bearer $TOKEN"

curl -H "$AUTH" http://localhost:8000/ips
curl -H "$AUTH" -X POST http://localhost:8000/exclusions \
     -H "Content-Type: application/json" \
     -d '{"ip": "185.220.101.1", "reason": "falso positivo"}'
curl -H "$AUTH" http://localhost:8000/ips/filtered
curl -H "$AUTH" http://localhost:8000/exclusions
curl -H "$AUTH" -X DELETE http://localhost:8000/exclusions/185.220.101.1

# Crear un usuario de solo lectura
curl -H "$AUTH" -X POST http://localhost:8000/users \
     -H "Content-Type: application/json" \
     -d '{"username": "analista", "password": "una-clave-de-12+"}'

curl -H "$AUTH" "http://localhost:8000/audit?limit=20"
curl http://localhost:8000/health
```

## Colección de Postman

[`postman/tor-ip-api.postman_collection.json`](postman/tor-ip-api.postman_collection.json) contiene 25 peticiones, organizadas en el orden en que deben ejecutarse:

| Carpeta | Contenido |
|---|---|
| 00 · Salud | Estado del servicio y de las fuentes |
| 01 · Autenticación | Login correcto y fallidos |
| 02 · Endpoints obligatorios | Los tres endpoints del reto y sus errores (409, 422) |
| 03 · Control de acceso | Sin token, token manipulado, usuario lector permitido y prohibido |
| 04 · Endpoints adicionales | Exclusiones, usuarios, actualización de fuentes y auditoría |
| 05 · Límite de login | Bloqueo con 429 tras varios intentos fallidos (ejecutar al final) |

Para usarla: en Postman, **Import** → selecciona el archivo → en la pestaña **Variables** de la colección escribe la contraseña del admin en `adminPass` (columna *Current value*) → **Run collection**. Cada petición incluye pruebas que verifican su respuesta; los tokens se guardan solos y el usuario lector se crea con credenciales aleatorias.

También se puede ejecutar desde la terminal con [Newman](https://www.npmjs.com/package/newman):

```bash
newman run postman/tor-ip-api.postman_collection.json --env-var "adminPass=TU_CLAVE"
```

La carpeta 05 bloquea el login desde tu IP durante 15 minutos.

## Códigos de respuesta

| Código | Significado |
|---|---|
| 200 / 201 / 204 | Éxito (consulta, creación, eliminación) |
| 401 | Sin token, token inválido o expirado, o credenciales incorrectas |
| 403 | El rol del usuario no permite la operación |
| 404 | La exclusión a eliminar no existe |
| 409 | La IP ya está excluida, el usuario ya existe o hay una actualización en curso |
| 422 | Datos inválidos (por ejemplo, una IP mal formada) |
| 429 | Demasiados intentos de login fallidos; ver la cabecera `Retry-After` |

## Pruebas

```bash
pytest
```

Las pruebas simulan las fuentes externas; no hacen peticiones a internet. Para correrlas contra PostgreSQL: `TEST_DATABASE_URL=postgresql+psycopg://... pytest`.

## Documentación en PDF

[`docs/Documentacion_Tor_IP_API.pdf`](docs/Documentacion_Tor_IP_API.pdf) reúne la arquitectura, la ejecución local y con Docker, la configuración, los endpoints, las capturas de cada request y response, el informe de seguridad (SAST) y el despliegue en la nube. Tiene un índice con enlaces a cada sección y marcadores para navegarlo desde el panel lateral del lector de PDF.

El PDF se genera con `docs/generar_pdf.py`. Cada evidencia tiene un nombre de archivo asignado; al guardar la captura con ese nombre en `docs/capturas/` y volver a generar el PDF, la imagen se inserta en su lugar:

```bash
sudo apt install python3-reportlab python3-pil   # solo la primera vez
python3 docs/generar_pdf.py
```

## Despliegue en la nube

[`docs/despliegue-nube.md`](docs/despliegue-nube.md) explica a fondo cómo se ejecutaría la solución en **AWS** (no está desplegada; es una propuesta de diseño). Incluye:

- **Arquitectura y red:** VPC en dos zonas con subredes públicas, de aplicación y de datos; grupos de seguridad encadenados y endpoints de VPC.
- **Cómputo:** ECS Fargate con dos servicios de la misma imagen, `api` (2 a 4 tareas, sin planificador) e `ingesta` (una sola tarea), y un extracto de la definición de tarea.
- **Datos y secretos:** RDS for PostgreSQL 16 Multi-AZ, cifrada y con TLS obligatorio; secretos en Secrets Manager y su rotación.
- **Permisos:** roles de IAM con mínimo privilegio y despliegue desde GitHub Actions con OIDC limitado a la rama `main`.
- **Entrada:** balanceador con HTTPS y AWS WAF (lista de IPs permitidas, reglas administradas y límite de tasa en `/auth/login`).
- **Operación:** alarmas de CloudWatch, CloudTrail, GuardDuty, escalado, objetivos de recuperación (RPO y RTO) y tabla de amenazas y controles.
- **Uso del resultado:** cómo alimentar un *IP set* de WAF con `/ips/filtered` para bloquear el tráfico de Tor.
- Pasos del primer despliegue, costos y equivalentes en GCP y Azure.

## Análisis de seguridad y CI

- **Informe SAST:** [`docs/sast-report.md`](docs/sast-report.md), con los resultados de Bandit, Semgrep, pip-audit, Gitleaks y Trivy, y la decisión tomada sobre cada hallazgo.
- **GitHub Actions** (`.github/workflows/ci.yml`): en cada `push` corre las pruebas contra PostgreSQL, Bandit, Semgrep, pip-audit, Trivy sobre la imagen y Gitleaks sobre todo el historial.
- **Dependabot** (`.github/dependabot.yml`): propone cada semana actualizaciones de dependencias, imagen base y acciones de CI.

## Decisiones de diseño

### Ingesta

- **Fuentes.** Se usan las tres sugeridas: `check.torproject.org` (texto plano, oficial), `dan.me.uk` (texto plano, lista de salida) y `bigdatacloud` (API JSON paginada con clave).
- **Caché en base de datos.** `dan.me.uk` solo permite una descarga cada 30 minutos, así que los endpoints nunca consultan las fuentes en vivo: un planificador las descarga periódicamente y los GET leen de PostgreSQL.
- **El límite sobrevive a los reinicios.** La fecha del último intento de cada fuente se guarda en la tabla `source_status` antes de descargar.
- **Actualización manual segura.** `POST /sources/refresh` se salta el intervalo normal, pero respeta un mínimo absoluto por fuente: `dan.me.uk` nunca se consulta más de una vez cada 30 minutos.
- **Fallar sin vaciar.** Si una fuente falla o no devuelve IPs válidas, se conservan sus datos anteriores y el error queda visible en `/health`.
- **IPs obsoletas.** Una IP que ninguna fuente reporta en 48 horas se elimina.
- **Validación.** Toda IP (de las fuentes o de los endpoints) se valida y se guarda en forma canónica, para IPv4 e IPv6.

### Seguridad

- **Contraseñas** con hash bcrypt; nunca se guardan ni se registran en claro.
- **Tokens JWT** firmados con HS256 y con expiración. Al validarlos se fija el algoritmo, lo que bloquea los tokens sin firma (`"alg": "none"`). El token solo lleva el nombre de usuario: **el rol y el estado se consultan en la base en cada petición**, así que desactivar un usuario o cambiar su rol tiene efecto inmediato.
- **Sin enumeración de usuarios.** El login responde igual y tarda lo mismo si el usuario no existe o si la contraseña es incorrecta.
- **Límite de intentos de login** por IP (5 en 15 minutos por defecto). Vive en memoria, lo que basta para una instancia; con varias instancias se movería a Redis o a un WAF.
- **Administrador inicial** desde `.env`, solo en el primer arranque. Ninguna credencial está en el código.
- **La aplicación no arranca** sin un `JWT_SECRET` de al menos 32 caracteres.
- **Auditoría.** Cada petición (excepto `/health`) se registra en la tabla `audit_log` y en el log de la aplicación: usuario, método, ruta, código de respuesta, IP de origen, user agent y duración. Incluye los rechazos (401, 403, 429) y el usuario intentado en los logins fallidos.
- **Cabeceras de seguridad** en todas las respuestas: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` y `Cache-Control: no-store`.
- **Secretos.** La API key de bigdatacloud se envía en la cabecera `x-bdc-key`, no en la URL, y nunca se escribe en logs ni en mensajes de error.
- **Contenedor** con usuario sin privilegios; la base de datos no expone puertos fuera de la red interna de Compose.

### Limitaciones conocidas

- La IP de origen se toma de la conexión directa. Detrás de un balanceador habría que confiar en `X-Forwarded-For` solo desde ese balanceador (ver la sección 8 de [`docs/despliegue-nube.md`](docs/despliegue-nube.md)). Con Podman sin privilegios, según la configuración de red, todas las peticiones pueden aparecer con la IP de la puerta de enlace del contenedor, y en ese caso el límite de login sería global en lugar de por cliente.
- Las tablas se crean con `create_all`, que agrega tablas nuevas pero no modifica las existentes. Para cambios de esquema en producción se usaría una herramienta de migraciones como Alembic.
