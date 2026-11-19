# Imagen base
FROM python:3.12-slim

# No generar .pyc y mostrar logs al instante
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencias del sistema (necesarias para psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Qué archivo de requirements instalar. Por defecto PRODUCCIÓN;
# el compose de desarrollo lo cambia a requirements-dev.txt.
ARG REQUIREMENTS=requirements.txt
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r ${REQUIREMENTS}

# Copiar el código (.dockerignore evita copiar .env y basura)
COPY . .

# Usuario sin privilegios (uid 1000 = tu usuario de WSL, evita problemas de permisos)
RUN useradd -m -u 1000 app && chown -R app:app /app
USER app

EXPOSE 8000