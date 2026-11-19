"""
Configuración de DESARROLLO (tu máquina local con Docker Desktop).
Se activa con DJANGO_SETTINGS_MODULE=core.settings.dev
"""
from pathlib import Path

from dotenv import load_dotenv

# Carga el archivo .env ANTES de importar base (base lee variables DB_*).
# Si ya vienen del contenedor (env_file), load_dotenv no las pisa.
load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')

from .base import *  # noqa: E402,F401,F403

ENVIRONMENT = 'dev'
DEBUG = True

# Clave inofensiva, solo para local. NUNCA se usa en producción.
SECRET_KEY = 'dev-only-insecure-key'

ALLOWED_HOSTS = ['localhost', '.localhost', '127.0.0.1']

# django-extensions solo existe en desarrollo (shell_plus, etc.)
INSTALLED_APPS += ['django_extensions']  # noqa: F405

CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'http://127.0.0.1:5173',
    'http://localhost:3000',
    'http://127.0.0.1:3000',
]
CORS_ALLOWED_ORIGIN_REGEXES = [
    r'^http://.*\.localhost:5173$',
    r'^http://.*\.localhost:3000$',
]

USE_X_FORWARDED_HOST = True