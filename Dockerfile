FROM docker.io/library/python:3.15-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Aplica los parches de seguridad de Debian publicados después de que se
# construyó la imagen base (por ejemplo, zlib CVE-2026-85091, detectado por Trivy).
# Semgrep desaconseja "apt-get upgrade" suponiendo que la imagen base siempre
# está al día; Trivy demostró que no es así, por eso se mantiene.
# nosemgrep: avoid-apt-get-upgrade
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# La aplicación corre con un usuario sin privilegios.
RUN useradd --create-home --uid 10001 appuser

COPY requirements.txt .

# pip solo se necesita para instalar las dependencias. Se desinstala después
# porque trae sus propias copias de urllib3, msgpack y setuptools con
# vulnerabilidades conocidas, y porque sin pip un atacante que comprometa el
# contenedor no puede instalar paquetes.
RUN pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y pip

COPY app ./app

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]

# Un solo proceso: el planificador de ingesta vive dentro de la API y no debe duplicarse.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
