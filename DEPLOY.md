# Despliegue de ShoeFlow en Oracle Cloud VPS

## 1. Conectarse al VPS

```bash
# Conectarse por SSH
ssh -i ~/.ssh/ssh-key-2026-04-01.key ubuntu@129.151.101.128
```

## 2. Entrar al proyecto

```bash
# Ir a la carpeta del backend
cd ~/projects/shoeflow-api

# Comprobar la ubicación
pwd
```

## 3. Actualizar el código

```bash
# Descargar los últimos cambios de GitHub
git pull origin main
```

## 4. Proteger las variables de entorno

```bash
# Comprobar que existe el archivo de producción
ls -la .env.prod

# Restringir el acceso al archivo
chmod 600 .env.prod
```

## 5. Validar Docker Compose

```bash
# Validar la configuración sin mostrar los secretos
docker compose --env-file .env.prod -f docker-compose.prod.yml config --quiet
```

## 6. Construir y levantar los servicios

```bash
# Construir la imagen del backend
docker compose --env-file .env.prod -f docker-compose.prod.yml build

# Levantar los servicios en segundo plano
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d

# Comprobar el estado de los contenedores
docker compose --env-file .env.prod -f docker-compose.prod.yml ps

# Revisar los últimos registros del backend
docker compose --env-file .env.prod -f docker-compose.prod.yml logs --tail=100 app
```

## 7. Aplicar migraciones

```bash
# Aplicar migraciones de las aplicaciones compartidas
docker compose --env-file .env.prod -f docker-compose.prod.yml exec app python manage.py migrate_schemas --shared

# Aplicar migraciones de los tenants
docker compose --env-file .env.prod -f docker-compose.prod.yml exec app python manage.py migrate_schemas
```

## 8. Crear administrador (solo la primera vez)

```bash
# Crear el superusuario de Django
docker compose --env-file .env.prod -f docker-compose.prod.yml exec app python manage.py createsuperuser
```

## 9. Comprobar seguridad

```bash
# Ejecutar las comprobaciones de seguridad para producción
docker compose --env-file .env.prod -f docker-compose.prod.yml exec app python manage.py check --deploy
```

## 10. Configuración inicial del tenant público (solo una vez)

Después de ejecutar las migraciones compartidas, entrar al shell:

```bash
# Abrir el shell de Django
docker compose --env-file .env.prod -f docker-compose.prod.yml exec app python manage.py shell
```

```python
# Importar los modelos centrales
from apps.central.customers.models import Client, Domain

# Crear el tenant público si todavía no existe
tenant, created = Client.objects.get_or_create(
    schema_name='public',
    defaults={
        'business_name': 'Main',
        'owner_names': 'Administrador del Sistema',
        'is_active': True,
    }
)

# Registrar el dominio de la API si todavía no existe
domain, created = Domain.objects.get_or_create(
    domain='sf.juanjosepau.dev',
    defaults={
        'tenant': tenant,
        'is_primary': True,
    }
)

# Salir del shell
exit()
```

## 11. Dominios de los tenants

Registrar desde Django Admin los dominios correspondientes a cada
tenant:

- `sf.juanjosepau.dev` → tenant público (`public`)
- `demo.juanjosepau.dev` → tenant Demo
- `nikfort.juanjosepau.dev` → tenant Nikfort

## 12. Configuración de Nginx Proxy Manager (una sola vez)

Crear un Proxy Host con estos valores:

- Domain: `sf.juanjosepau.dev`
- Scheme: `http`
- Forward Hostname: `shoeflow-prod-api`
- Forward Port: `8000`
- SSL: Let's Encrypt
- Force SSL: activado

La red compartida con el contenedor de Django es `proxy_default`.

## 13. Configuración de Vercel

En los proyectos Demo y Nikfort, configurar la variable `VITE_API_URL`
como tipo `Config`:

```env
# URL única del backend para todos los tenants
VITE_API_URL=https://sf.juanjosepau.dev/api/v1
```

En la raíz de cada frontend debe existir `vercel.json` para las rutas de
React Router:

```json
{
  "rewrites": [
    {
      "source": "/(.*)",
      "destination": "/"
    }
  ]
}
```

## 14. Generar migraciones en desarrollo

Ejecutar en el entorno local, después de modificar modelos:

```bash
# Crear los archivos de migración
docker compose exec app python manage.py makemigrations

# Guardar y subir el código y las migraciones
git add .
git commit -m "feat: update models"
git push origin main
```

Después, actualizar el VPS y aplicar las migraciones siguiendo los pasos
2, 3, 5, 6 y 7.

## 15. Comandos de mantenimiento

```bash
# Ver el estado de los servicios
docker compose --env-file .env.prod -f docker-compose.prod.yml ps

# Ver los logs del backend en tiempo real
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f app

# Reiniciar únicamente el backend
docker compose --env-file .env.prod -f docker-compose.prod.yml restart app

# Entrar al shell de Django
docker compose --env-file .env.prod -f docker-compose.prod.yml exec app python manage.py shell

# Entrar al contenedor del backend
docker compose --env-file .env.prod -f docker-compose.prod.yml exec app sh

# Detener los servicios de ShoeFlow
docker compose --env-file .env.prod -f docker-compose.prod.yml stop

# Iniciar los servicios de ShoeFlow
docker compose --env-file .env.prod -f docker-compose.prod.yml start
```

## Precauciones

- No ejecutar `makemigrations` en producción.
- Hacer una copia de seguridad de PostgreSQL antes de migraciones
  importantes.
- No ejecutar `docker compose down -v`: puede borrar el volumen de la
  base de datos.
- No ejecutar limpiezas globales de Docker que puedan afectar otros
  proyectos.
- No detener ni modificar los contenedores de SuiteHub o Nginx Proxy
  Manager.
- No subir `.env.prod` ni compartir sus secretos.
- Los pasos de creación del tenant público, superusuario y
  configuración de dominios son de configuración inicial; no se
  repiten en cada despliegue.
