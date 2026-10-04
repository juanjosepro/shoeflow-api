## Instalación en Local

```bash
# 1. Crear variables de entorno
cp .env.example .env
```

```bash
# 2. Levantar los servicios en segundo plano
docker compose up -d
```

```bash
# 3. Correr las migraciones
docker compose exec app python manage.py makemigrations
```

```bash
# 5. Aplicar las migraciones a la base de datos
docker compose exec app python manage.py migrate
```

```bash
# 6. Crear usuario administrador
docker compose exec app python manage.py createsuperuser
```

```bash
# 7. Crear el Tenant principal y su Dominio:

# Entrar al shell del contenedor:
docker compose exec app python manage.py shell

# Importar los modelos:
from apps.central.customers.models import Client, Domain

# Crear el esquema principal (OBLIGATORIO que sea schema_name='public')
tenant = Client(
    schema_name='public',
    names='Administrador del Sistema',
    is_active=True
)
tenant.save()

# Vincular el dominio localhost para que Django lo reconozca
domain = Domain(
    domain='localhost',
    tenant=tenant,
    is_primary=True
)
domain.save()

exit()
```

<!-- Detecta cambios en el código y crea los archivos (en Central y Tenants). No toca la DB.-->

docker compose exec app python manage.py makemigrations

<!-- Aplica los cambios solo a la App Central (esquema public). Tablas de clientes y dominios. -->

docker compose exec app python manage.py migrate

<!-- Aplica los cambios solo a los Tenants. Crea las tablas de cada cliente (productos, ventas). -->

docker-compose exec app python manage.py migrate_schemas

<!-- El "todo en uno". Actualiza la Central + todos los Tenants al mismo tiempo. -->

docker compose exec app python manage.py migrate_schemas --shared

<!-- Entrar a la base de datos -->

docker compose exec db psql -U [TU_USUARIO] -d [TU_DB]

<!-- Listar esquemas en PostgreSQL: -->

\dn

<!-- Para eliminar un esquema en PostgreSQL: -->

DROP SCHEMA nombre_del_esquema CASCADE;

<!-- Ver logs en tiempo real -->

docker compose logs -f

sudo chown -R pau:pau common/
