# Tor IP API

API REST que unifica las IPs de nodos de salida de Tor de varias fuentes externas y permite excluir IPs del listado.

> Estado: núcleo funcional (Fases 1 y 2). Autenticación, permisos, auditoría, informe SAST y la documentación completa se agregan en fases posteriores.

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/ips` | Todas las IPs de Tor obtenidas de las fuentes |
| POST | `/exclusions` | Agrega una IP a la base de exclusiones |
| GET | `/ips/filtered` | IPs de Tor exceptuando las excluidas |
| GET | `/health` | Estado del servicio y de cada fuente |

Documentación interactiva (Swagger): `http://localhost:8000/docs`

## Ejecutar con Docker

```bash
cp .env.example .env      # edita la contraseña y la API key de bigdatacloud
docker compose up --build
```

La API queda en `http://localhost:8000`. El primer ciclo de ingesta corre al arrancar.

## Ejecutar localmente (sin Docker)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Sin `DATABASE_URL` definida se usa un archivo SQLite local (`tor.db`), suficiente para desarrollo. Para usar PostgreSQL:

```bash
export DATABASE_URL=postgresql+psycopg://usuario:clave@localhost:5432/tor
```

## Ejemplos

```bash
curl http://localhost:8000/ips
curl -X POST http://localhost:8000/exclusions \
     -H "Content-Type: application/json" \
     -d '{"ip": "185.220.101.1", "reason": "falso positivo"}'
curl http://localhost:8000/ips/filtered
curl http://localhost:8000/health
```

## Pruebas

```bash
pytest
```

Las pruebas simulan las fuentes externas; no hacen peticiones a internet.

## Decisiones de diseño

- **Fuentes.** Se usan las tres sugeridas: `check.torproject.org` (texto plano, oficial), `dan.me.uk` (texto plano, lista de salida) y `bigdatacloud` (API JSON paginada con clave).
- **Caché en base de datos.** `dan.me.uk` solo permite una descarga cada 30 minutos, así que los endpoints nunca consultan las fuentes en vivo: un planificador las descarga periódicamente y los GET leen de PostgreSQL.
- **El límite sobrevive a los reinicios.** La fecha del último intento de cada fuente se guarda en la tabla `source_status` antes de descargar.
- **Fallar sin vaciar.** Si una fuente falla o no devuelve IPs válidas, se conservan sus datos anteriores y el error queda visible en `/health`.
- **IPs obsoletas.** Una IP que ninguna fuente reporta en 48 horas se elimina.
- **Validación.** Toda IP (de las fuentes o del POST) se valida y se guarda en forma canónica, para IPv4 e IPv6.
- **Secretos.** La API key va en `.env` (fuera del repo) y nunca se escribe en logs ni en mensajes de error.
