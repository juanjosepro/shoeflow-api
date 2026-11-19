"""
Configuración BASE de ShoeFlow: lo que es IGUAL en desarrollo y producción.
Lo que cambia entre entornos (SECRET_KEY, DEBUG, hosts, CORS) vive en dev.py y prod.py.
Nunca se usa directamente: siempre a través de dev.py o prod.py.
"""
import os
from pathlib import Path

from corsheaders.defaults import default_headers

# Este archivo está en core/settings/base.py -> subimos 3 niveles hasta la raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# Aplicaciones (django-tenants separa apps compartidas y apps por tenant)
# ---------------------------------------------------------------------------
SHARED_APPS = [
    'django_tenants',
    'apps.central.customers',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

TENANT_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'corsheaders',
    'rest_framework',
    'apps.tenants.catalog',
    'apps.tenants.staff',
    'apps.tenants.production',
    'apps.tenants.payroll',
    'apps.tenants.contact',
    'rest_framework.authtoken',
]

INSTALLED_APPS = list(SHARED_APPS) + [app for app in TENANT_APPS if app not in SHARED_APPS]

TENANT_MODEL = 'customers.Client'
TENANT_DOMAIN_MODEL = 'customers.Domain'
TENANT_CREATION_FAILS_CLEANUP = True

# ---------------------------------------------------------------------------
# Middleware (el orden importa)
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # WhiteNoise sirve los archivos estáticos (admin, DRF) sin necesitar nginx.
    # Va antes del tenant para que los estáticos no dependan de resolver un tenant.
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    # Resuelve el tenant por el header X-Tenant (si no viene, usa el Host como antes).
    'core.middleware.HeaderTenantMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# ---------------------------------------------------------------------------
# Base de datos: siempre se lee de variables de entorno (DB_*)
# ---------------------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django_tenants.postgresql_backend',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT'),
    }
}

DATABASE_ROUTERS = (
    'django_tenants.routers.TenantSyncRouter',
)

# ---------------------------------------------------------------------------
# Validación de contraseñas
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ---------------------------------------------------------------------------
# Internacionalización
# ---------------------------------------------------------------------------
LANGUAGE_CODE = 'es-pe'
TIME_ZONE = 'America/Lima'
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Archivos estáticos
# ---------------------------------------------------------------------------
STATIC_URL = '/static/'
# Carpeta donde `collectstatic` junta los estáticos (la usa WhiteNoise en producción)
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 15,
}

# ---------------------------------------------------------------------------
# CORS: permitimos el header X-Tenant (lo envía el frontend para indicar el tenant).
# La lista de orígenes permitidos se define en dev.py y prod.py.
# ---------------------------------------------------------------------------
CORS_ALLOW_HEADERS = (*default_headers, 'x-tenant')