# Informe de análisis de seguridad (SAST)

**Proyecto:** Tor IP API
**Fecha del análisis:** 18 de noviembre de 2026
**Alcance:** código de la aplicación (`app/`), pruebas (`tests/`), dependencias de Python (`requirements.txt`), `Dockerfile`, `docker-compose.yml` y archivos de configuración.

## 1. Resumen

| Herramienta | Qué analiza | Resultado inicial | Resultado final |
|---|---|---|---|
| Bandit 1.9.4 | Patrones inseguros en código Python | 0 hallazgos en `app/` | 0 hallazgos |
| Semgrep 1.186.0 | Código, Dockerfile, Compose y secretos (638 reglas) | 4 hallazgos (2 WARNING, 2 INFO) | 1 hallazgo INFO aceptado con mitigación |
| pip-audit 2.10.1 | Vulnerabilidades conocidas (CVE) en 32 paquetes, incluidos los transitivos | 0 vulnerabilidades | 0 vulnerabilidades |
| Gitleaks 8.30.1 | Secretos en los archivos del proyecto | 0 hallazgos | 0 hallazgos |
| Trivy | Imagen Docker: sistema operativo y librerías | Se ejecuta en CI y en el entorno local (sección 6) | — |

No se encontraron vulnerabilidades explotables. De los cuatro hallazgos de Semgrep, uno era una mejora válida que se corrigió, dos eran falsos positivos y uno es una recomendación que se acepta con mitigación.

Además, los análisis se ejecutan automáticamente en cada `push` mediante GitHub Actions (sección 7), de modo que el análisis es continuo y no puntual.

## 2. Bandit

**Comando:**

```bash
bandit -r app
```

**Resultado:** 904 líneas analizadas, sin hallazgos de ninguna severidad.

Bandit busca, entre otros: contraseñas o claves escritas en el código, consultas SQL armadas con cadenas, uso de `eval`/`exec`, deserialización insegura (`pickle`), llamadas a la shell, criptografía débil y peticiones HTTP sin timeout. El resultado es coherente con el diseño:

- Las consultas usan SQLAlchemy con parámetros, nunca SQL concatenado.
- Los secretos (`JWT_SECRET`, `ADMIN_PASSWORD`, `BIGDATACLOUD_API_KEY`) se leen de variables de entorno.
- Las contraseñas usan bcrypt y los tokens JWT, HS256 con algoritmo fijado.
- Todas las peticiones HTTP a las fuentes tienen timeout.

**Carpeta `tests/`:** se analizó por separado y produce 122 hallazgos de severidad baja, todos esperados en código de pruebas:

| Regla | Cantidad | Motivo por el que no aplica |
|---|---|---|
| B101 `assert_used` | 112 | `assert` es la forma estándar de verificar resultados en pytest. El riesgo de Bandit (que `python -O` elimine los `assert`) solo importa en código de producción. |
| B105 / B106 `hardcoded_password` | 10 | Son contraseñas ficticias de las pruebas, que solo existen en una base de datos temporal. |

Por eso el análisis de Bandit y el de CI se limitan a `app/`.

## 3. Semgrep

**Reglas:** conjuntos públicos de Semgrep para Python (incluye FastAPI, JWT, SQLAlchemy, requests y criptografía), Dockerfile, Docker Compose y detección de secretos. En total, 638 reglas sobre 52 archivos.

**Comando:**

```bash
semgrep scan --config p/python --config p/dockerfile --config p/secrets --metrics=off
```

### Hallazgos y decisiones

| # | Regla | Severidad | Ubicación | Decisión |
|---|---|---|---|---|
| S1 | `prefer-json-notation` | INFO | `Dockerfile`, `HEALTHCHECK` | **Corregido** |
| S2 | `is-function-without-parentheses` | WARNING | `app/security.py`, login | **Falso positivo**, suprimido con justificación |
| S3 | `is-function-without-parentheses` | WARNING | `app/security.py`, validación de token | **Falso positivo**, suprimido con justificación |
| S4 | `dockerfile-source-not-pinned` | INFO | `Dockerfile`, `FROM` | **Aceptado con mitigación** |

**S1. Healthcheck en formato shell.** El `HEALTHCHECK` usaba la forma de texto (`CMD python -c ...`), que ejecuta el comando a través de `/bin/sh`. Se cambió a la forma JSON (`CMD ["python", "-c", ...]`), que ejecuta el proceso directamente: no depende de la shell, no interpreta caracteres especiales y recibe las señales del sistema de forma correcta.

**S2 y S3. `user.is_active` sin paréntesis.** La regla advierte que, si `is_active` fuera un método, `not user.is_active` siempre sería falso y la verificación de usuario desactivado nunca se cumpliría. En este proyecto `is_active` es una columna booleana del modelo `User`, no un método, así que la condición es correcta. Las pruebas `test_inactive_user_cannot_login_and_loses_access` lo confirman: un usuario desactivado no puede iniciar sesión y su token deja de funcionar. Se suprimió la alerta en esas dos líneas con un comentario `nosemgrep` que explica el motivo, en lugar de desactivar la regla para todo el proyecto.

**S4. Imagen base sin digest.** El `Dockerfile` usa `python:3.13-slim` por etiqueta. Una etiqueta puede apuntar a una imagen distinta con el tiempo, así que dos construcciones del mismo código podrían dar resultados diferentes. Fijar la imagen por su digest (`python:3.13-slim@sha256:...`) garantiza reproducibilidad, pero también congela la imagen y deja de recibir parches de seguridad si nadie la actualiza.

Se acepta el uso por etiqueta con estas mitigaciones:

- Trivy analiza la imagen en cada `push` y bloquea el CI si encuentra vulnerabilidades CRITICAL o HIGH con corrección disponible.
- Dependabot revisa la imagen base cada semana y abre un pull request cuando hay una nueva versión.
- Se usa una etiqueta de versión concreta (`3.13-slim`), no `latest`.

Para un despliegue productivo se recomienda fijar el digest, ya que Dependabot también actualiza digests automáticamente. Para obtenerlo:

```bash
skopeo inspect --raw docker://docker.io/library/python:3.13-slim | sha256sum
```

y escribir `FROM docker.io/library/python:3.13-slim@sha256:<resultado>`.

## 4. pip-audit

**Comando:**

```bash
pip-audit -r requirements.txt
```

**Resultado:** sin vulnerabilidades conocidas en los 32 paquetes, contando las dependencias directas y las transitivas.

Todas las dependencias están fijadas a una versión exacta en `requirements.txt`, lo que hace que el análisis sea reproducible: la imagen instala exactamente lo que se auditó. Dependabot propone actualizaciones semanales y cada una pasa por este mismo análisis en CI.

## 5. Gitleaks

**Comando:**

```bash
gitleaks dir . -v
```

**Resultado:** sin secretos en los archivos del proyecto.

El archivo `.env`, que contiene las credenciales reales, está en `.gitignore` y en `.dockerignore`, así que no llega ni al repositorio ni a la imagen. Solo se sube `.env.example`, con los valores vacíos.

En CI, Gitleaks analiza **todo el historial de Git**, no solo la versión actual. Esto importa porque un secreto que se subió en un commit y se borró en el siguiente sigue siendo recuperable del historial.

## 6. Trivy (imagen Docker)

Trivy analiza la imagen completa: los paquetes del sistema operativo de la imagen base (Debian) y las librerías de Python instaladas.

**En CI** se ejecuta en cada `push` con estos criterios:

- Severidad CRITICAL o HIGH.
- Solo vulnerabilidades que ya tienen corrección disponible (`ignore-unfixed`). Las que no tienen parche publicado no se pueden resolver actualizando y bloquearían el CI sin una acción posible.

**En el entorno local** (Kali con Podman):

```bash
podman save -o /tmp/tor-ip-api.tar tor-ip-api-api
podman run --rm -v /tmp/tor-ip-api.tar:/image.tar:Z docker.io/aquasec/trivy:latest \
    image --input /image.tar --severity CRITICAL,HIGH --ignore-unfixed
```

**Resultado:** _pendiente de agregar la salida de la ejecución._

## 7. Integración continua (GitHub Actions)

El flujo `.github/workflows/ci.yml` ejecuta cuatro trabajos en paralelo en cada `push` y cada pull request:

| Trabajo | Qué hace | Cuándo falla |
|---|---|---|
| Pruebas | Corre las 68 pruebas contra un PostgreSQL 16 real | Si alguna prueba falla |
| SAST y dependencias | Bandit, Semgrep y pip-audit | Bandit con severidad media o alta; Semgrep con WARNING o ERROR; pip-audit con cualquier vulnerabilidad |
| Imagen Docker | Construye la imagen y la analiza con Trivy | Vulnerabilidades CRITICAL o HIGH con corrección |
| Secretos | Gitleaks sobre todo el historial | Cualquier secreto detectado |

Medidas de seguridad del propio flujo:

- **Acciones fijadas por commit (SHA)**, no por etiqueta. Si alguien compromete el repositorio de una acción y mueve la etiqueta a código malicioso, este flujo seguiría ejecutando la versión revisada.
- **Permisos mínimos:** el token de GitHub solo tiene permiso de lectura del repositorio (`contents: read`).
- **`persist-credentials: false`:** las credenciales de Git no quedan guardadas en el entorno de ejecución después del checkout.

Dependabot (`.github/dependabot.yml`) revisa cada semana las dependencias de Python, la imagen base y las propias acciones de CI.

## 8. Revisión manual

Además de las herramientas automáticas, la revisión del código durante el desarrollo produjo estas correcciones:

| Hallazgo | Riesgo | Corrección |
|---|---|---|
| La API key de bigdatacloud se enviaba en la URL | Las URLs quedan registradas en logs de proxies y servidores intermedios | Se envía en la cabecera `x-bdc-key` |
| La librería `httpx` registraba la URL completa de cada petición | Exposición de datos en los logs | Se elevó su nivel de log a `WARNING` |
| Los mensajes de error de red podían incluir la URL | Exposición de la API key en `/health` | Los errores se guardan como texto genérico (`error de red (ConnectError)`); hay una prueba que lo verifica |
| El POST de exclusiones no tenía control de acceso | Cualquiera podía sacar su propia IP de la lista de bloqueo | Restringido al rol `admin` |

Otras medidas verificadas con pruebas automáticas:

- Los tokens con `"alg": "none"`, firmados con otra clave u otro algoritmo, expirados o sin `exp` o `sub` se rechazan.
- El login responde igual si el usuario no existe o si la contraseña es incorrecta, y tarda lo mismo en ambos casos.
- Tras 5 intentos fallidos desde una misma IP, el login se bloquea con 429 durante 15 minutos.
- Las contraseñas nunca se guardan en claro, ni en la base ni en la auditoría.
- Un usuario desactivado pierde el acceso de inmediato, aunque su token siga vigente.

## 9. Riesgos residuales

| Riesgo | Mitigación actual | Recomendación para producción |
|---|---|---|
| El límite de intentos de login vive en memoria | Suficiente para una instancia | Redis o un WAF con limitación de tasa |
| La IP de origen es la de la conexión directa | Documentado en el README | Confiar en `X-Forwarded-For` solo desde el balanceador |
| La imagen base no está fijada por digest | Trivy en CI y Dependabot | Fijar el digest |
| Los tokens no se pueden revocar individualmente | Expiran en 30 minutos; desactivar al usuario corta el acceso | Lista de revocación por `jti` si se requiere |
| El esquema de base de datos se crea con `create_all` | Válido para el alcance del reto | Migraciones con Alembic |
