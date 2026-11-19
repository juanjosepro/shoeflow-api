"""
Configuración de PRODUCCIÓN (VPS).
Se activa con DJANGO_SETTINGS_MODULE=core.settings.prod
Todos los secretos vienen de variables de entorno (archivo .env.prod en el servidor).
"""
import os

from .base import *  # noqa: F401,F403

ENVIRONMENT = 'prod'
DEBUG = False

# Sin valor por defecto: si falta SECRET_KEY el contenedor NO arranca (a propósito).
SECRET_KEY = os.environ['SECRET_KEY']

# Solo el dominio de la API. El tenant se decide por X-Tenant, no por este host.
ALLOWED_HOSTS = ['sf.juanjosepau.dev']

# Frontends (Vercel) autorizados a llamar a la API
CORS_ALLOWED_ORIGINS = [
    'https://nikfort.juanjosepau.dev',
    'https://demo.juanjosepau.dev',
]
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS + ['https://sf.juanjosepau.dev']

# Estamos detrás de un proxy inverso con HTTPS: confiamos en su header
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Estáticos servidos por WhiteNoise (comprimidos)
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}

# Con DEBUG=False Django NO imprime errores en consola por defecto.
# Esto los manda a la salida estándar para verlos con `docker compose logs`.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': 'WARNING'},
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}