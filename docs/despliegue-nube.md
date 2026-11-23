# Despliegue en la nube (AWS)

Este documento explica cómo ejecutaría Tor IP API en AWS. Es una propuesta de diseño: la solución no está desplegada en la nube (ese punto es un extra del reto y no se implementó).

Se eligió AWS porque cubre con servicios administrados todo lo que la aplicación ya usa en Docker Compose (contenedor, PostgreSQL, secretos y logs) sin cambiar el código. Al final hay una tabla con los equivalentes en GCP y Azure.

![Arquitectura de despliegue en AWS](diagramas/aws.png)

## 1. Componentes

| Necesidad | En Docker Compose | En AWS |
|---|---|---|
| Imagen de la API | Se construye localmente | **Amazon ECR**, con escaneo al subir y etiquetas inmutables |
| Ejecución del contenedor | Servicio `api` | **ECS sobre Fargate** (contenedores sin administrar servidores) |
| Base de datos | Contenedor `postgres:16-alpine` | **RDS for PostgreSQL 16**, Multi-AZ, cifrada con KMS |
| Secretos | Archivo `.env` | **AWS Secrets Manager**, inyectados en la tarea al arrancar |
| Entrada HTTP | Puerto 8000 publicado | **Application Load Balancer** con HTTPS (certificado de ACM) |
| Protección perimetral | — | **AWS WAF** delante del balanceador |
| Logs y auditoría | Salida del contenedor y tabla `audit_log` | **CloudWatch Logs** y la misma tabla `audit_log` en RDS |
| Salida a internet (fuentes) | Red de Docker | **NAT Gateway** desde las subredes privadas |

## 2. Red

- Una **VPC** con dos zonas de disponibilidad. En cada zona, una subred pública y una privada.
- En las **subredes públicas** solo están el balanceador y el NAT Gateway.
- Las tareas de ECS y la base de datos viven en las **subredes privadas**: no tienen IP pública y nadie puede llegar a ellas desde internet.
- Las tareas salen a internet por el NAT Gateway, únicamente para descargar las listas de Tor.
- **Grupos de seguridad** (cada uno solo acepta tráfico del anterior):

| Grupo | Acepta | Desde |
|---|---|---|
| `sg-alb` | 443 (y 80 solo para redirigir a HTTPS) | Internet, filtrado por WAF |
| `sg-api` | 8000 | Solo `sg-alb` |
| `sg-rds` | 5432 | Solo `sg-api` |

## 3. Cómputo: dos servicios de ECS con la misma imagen

La aplicación ejecuta el planificador de ingesta dentro del mismo proceso que la API, y su bloqueo de ingesta vive en memoria. Si se escalara a varias tareas sin más, cada una descargaría las fuentes por su cuenta y `dan.me.uk` podría bloquear la IP de salida. Por eso se usan **dos servicios de ECS con la misma imagen**, que solo se distinguen por una variable de entorno que la aplicación ya soporta:

| Servicio | Tareas | `SCHEDULER_ENABLED` | Detrás del balanceador | Función |
|---|---|---|---|---|
| `api` | 2 o más (escalado automático por CPU) | `false` | Sí | Atiende las peticiones |
| `ingesta` | Exactamente 1 | `true` | No | Descarga las fuentes y actualiza la base |

- Cada tarea: 0.5 vCPU y 1 GB de memoria es suficiente para el volumen de esta API.
- El servicio `api` se reparte entre las dos zonas; si una tarea falla su verificación (`GET /health`), ECS la reemplaza.
- El `HEALTHCHECK` del Dockerfile sigue funcionando y el balanceador usa la misma ruta `/health`, que solo responde 503 si la base de datos no está disponible.
- Las tareas corren con el usuario sin privilegios de la imagen y con el sistema de archivos raíz en solo lectura (`readonlyRootFilesystem`).

## 4. Base de datos

- **RDS for PostgreSQL 16** en las subredes privadas, sin acceso público.
- **Multi-AZ** para que una caída de zona no detenga el servicio.
- Cifrado en reposo con **KMS** y conexiones con **TLS obligatorio** (`rds.force_ssl = 1` y `sslmode=require` en la URL de conexión).
- Copias de seguridad automáticas con 7 días de retención y protección contra borrado activada.
- Las tablas se crean igual que en local, al arrancar la aplicación.

## 5. Secretos

Los valores que hoy van en `.env` pasan a **Secrets Manager** y la definición de la tarea de ECS los inyecta como variables de entorno al arrancar. No quedan en la imagen, en el repositorio ni en la definición de la tarea.

| Secreto | Variable |
|---|---|
| `tor-ip-api/jwt-secret` | `JWT_SECRET` |
| `tor-ip-api/admin-password` | `ADMIN_PASSWORD` |
| `tor-ip-api/database-url` | `DATABASE_URL` (incluye usuario y contraseña de RDS) |
| `tor-ip-api/bigdatacloud-api-key` | `BIGDATACLOUD_API_KEY` |

- El **rol de ejecución** de la tarea solo puede leer esos cuatro secretos y descargar la imagen de ECR.
- El **rol de la tarea** (el que usa la aplicación) no necesita ningún permiso de AWS, porque la aplicación no llama a servicios de AWS.
- Rotar `JWT_SECRET` invalida todos los tokens vigentes. Es la forma de cerrar todas las sesiones si se sospecha que la clave se filtró.

## 6. Entrada, HTTPS y WAF

- El **balanceador** termina HTTPS con un certificado de **ACM**, redirige HTTP a HTTPS y reenvía a las tareas por el puerto 8000.
- **AWS WAF** delante del balanceador, con:
  - Las reglas administradas de AWS (conjunto básico y entradas maliciosas conocidas).
  - Una **regla de límite de tasa sobre `/auth/login`**. Reemplaza al límite de intentos de la aplicación, que vive en memoria y con varias tareas se contaría por separado en cada una.
  - Una **lista de IPs permitidas** con las salidas de la red corporativa y de los sistemas que consumen la API. Es una herramienta interna del equipo de seguridad y no necesita estar abierta a todo internet.
- **IP real del cliente.** Detrás del balanceador, la aplicación vería la IP del balanceador en la auditoría. Uvicorn ya lee la cabecera `X-Forwarded-For`; basta con indicarle que solo confíe en direcciones de la VPC, sin cambiar el código:

  ```
  FORWARDED_ALLOW_IPS=10.0.0.0/16
  ```

  Así toma como origen la última IP que agrega el balanceador, y un cliente no puede falsificar su IP enviando su propia cabecera `X-Forwarded-For`.

## 7. Logs, auditoría y alertas

- Los logs de las tareas van a **CloudWatch Logs** (controlador `awslogs`), con 90 días de retención.
- La auditoría de la aplicación sigue en la tabla `audit_log` de RDS y se consulta con `GET /audit`. También aparece en los logs, porque la aplicación escribe cada petición en su salida.
- **Filtros de métricas y alarmas** en CloudWatch:
  - Picos de respuestas 401, 403 y 429 (intentos de fuerza bruta o de acceso no autorizado).
  - Una fuente con error en `/health` por más de dos ciclos.
  - Tareas del servicio `api` por debajo del mínimo.
- **CloudTrail** registra los cambios en la infraestructura (quién modificó un secreto, una regla de WAF o la definición de una tarea).

## 8. Integración y despliegue continuo

El pipeline de GitHub Actions que ya existe (pruebas, Bandit, Semgrep, pip-audit, Trivy y Gitleaks) se amplía con un trabajo de despliegue que corre solo en la rama `main` y solo si todo lo anterior pasa:

1. GitHub Actions se autentica en AWS con **OIDC**. No hay claves de acceso guardadas en GitHub, y el rol que asume solo puede subir imágenes a este repositorio de ECR y actualizar estos dos servicios.
2. Construye la imagen, la vuelve a escanear con Trivy y la sube a ECR con el hash del commit como etiqueta.
3. Registra una nueva revisión de la definición de tarea con esa imagen y actualiza los servicios `api` e `ingesta`.
4. ECS hace un despliegue gradual: levanta las tareas nuevas, espera a que pasen la verificación de salud y luego detiene las viejas. Si las nuevas fallan, el *circuit breaker* de ECS vuelve a la versión anterior.

La infraestructura se describiría como código (Terraform o AWS CDK), para que la red, los grupos de seguridad y los permisos se revisen en un pull request igual que el código.

## 9. Pasos del primer despliegue

Una vez creadas la VPC, la base RDS y el clúster de ECS (idealmente con Terraform), los pasos que dependen de la aplicación son:

```bash
REGION=us-east-1
CUENTA=$(aws sts get-caller-identity --query Account --output text)
REPO=$CUENTA.dkr.ecr.$REGION.amazonaws.com/tor-ip-api

# 1. Repositorio de imágenes con escaneo y etiquetas inmutables
aws ecr create-repository --repository-name tor-ip-api --region $REGION \
    --image-scanning-configuration scanOnPush=true --image-tag-mutability IMMUTABLE

# 2. Construir y subir la imagen
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $CUENTA.dkr.ecr.$REGION.amazonaws.com
docker build -t $REPO:$(git rev-parse --short HEAD) .
docker push $REPO:$(git rev-parse --short HEAD)

# 3. Secretos (los valores se generan o se leen sin escribirlos en la terminal)
aws secretsmanager create-secret --name tor-ip-api/jwt-secret --secret-string "$(openssl rand -base64 48)"
read -rs ADMIN_PASS && aws secretsmanager create-secret --name tor-ip-api/admin-password --secret-string "$ADMIN_PASS"
# ...igual para database-url y bigdatacloud-api-key

# 4. Registrar la definición de tarea y crear los dos servicios
aws ecs register-task-definition --cli-input-json file://task-api.json   # imagen, secretos, variables y logs
aws ecs create-service --cluster tor-ip-api --service-name api --task-definition tor-ip-api \
    --desired-count 2 --launch-type FARGATE ...   # subredes privadas, sg-api y el target group del ALB
```

Al arrancar por primera vez, la aplicación crea las tablas y el administrador inicial, igual que en Docker Compose.

## 10. Costo

Los componentes que más pesan en la factura mensual son, en este orden aproximado: el **NAT Gateway** (cobra por hora y por GB), **RDS Multi-AZ**, el **balanceador** y las tareas de **Fargate**. WAF y Secrets Manager suman poco. Para estimar el costo de la región elegida se usa la [AWS Pricing Calculator](https://calculator.aws/).

Si se quisiera reducir el costo en un entorno de pruebas: RDS en una sola zona, una sola tarea del servicio `api` y VPC endpoints para ECR, Secrets Manager y CloudWatch (así solo la descarga de las fuentes pasa por el NAT Gateway).

## 11. Equivalentes en GCP y Azure

| Necesidad | AWS | GCP | Azure |
|---|---|---|---|
| Registro de imágenes | ECR | Artifact Registry | Azure Container Registry |
| Contenedores | ECS Fargate | Cloud Run | Azure Container Apps |
| PostgreSQL administrado | RDS for PostgreSQL | Cloud SQL for PostgreSQL | Azure Database for PostgreSQL (Flexible Server) |
| Secretos | Secrets Manager | Secret Manager | Key Vault |
| Balanceador y HTTPS | ALB + ACM | Cloud Load Balancing | Application Gateway |
| WAF | AWS WAF | Cloud Armor | Azure WAF |
| Logs y alertas | CloudWatch | Cloud Logging y Monitoring | Azure Monitor |
| Salida a internet | NAT Gateway | Cloud NAT | NAT Gateway |

En GCP y Azure el diseño es el mismo: un servicio para la API con varias instancias, otro con una sola instancia para la ingesta (en Cloud Run, con instancias mínimas en 1 y la CPU siempre asignada, para que el planificador siga corriendo entre peticiones), la base en una red privada y los secretos en el gestor de cada nube.
