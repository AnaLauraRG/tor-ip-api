# Tor IP API

API REST que unifica las IPs de nodos de salida de Tor de varias fuentes externas y permite excluir IPs del listado. Incluye autenticación con JWT, control de acceso por roles y auditoría de todas las peticiones.

> Estado: núcleo, autenticación, roles y auditoría completos. El informe SAST, las capturas y el documento de despliegue en la nube se agregan en fases posteriores.

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

## Ejecutar con Docker

```bash
cp .env.example .env
openssl rand -base64 48    # copia el resultado en JWT_SECRET
nano .env                  # completa JWT_SECRET, ADMIN_PASSWORD, POSTGRES_PASSWORD y BIGDATACLOUD_API_KEY
docker compose up --build
```

La API queda en `http://localhost:8000`. Al arrancar se crea el administrador inicial y corre el primer ciclo de ingesta.

Con Podman en lugar de Docker, activa antes su socket: `systemctl --user enable --now podman.socket`.

## Ejecutar localmente (sin Docker)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env       # completa al menos JWT_SECRET y ADMIN_PASSWORD
uvicorn app.main:app --reload
```

Sin `DATABASE_URL` definida se usa un archivo SQLite local (`tor.db`), suficiente para desarrollo. Para usar PostgreSQL:

```bash
export DATABASE_URL=postgresql+psycopg://usuario:clave@localhost:5432/tor
```

## Ejemplos

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

- La IP de origen se toma de la conexión directa. Detrás de un balanceador habría que confiar en `X-Forwarded-For` solo desde ese balanceador. Con Podman sin privilegios, según la configuración de red, todas las peticiones pueden aparecer con la IP de la puerta de enlace del contenedor, y en ese caso el límite de login sería global en lugar de por cliente.
- Las tablas se crean con `create_all`, que agrega tablas nuevas pero no modifica las existentes. Para cambios de esquema en producción se usaría una herramienta de migraciones como Alembic.
