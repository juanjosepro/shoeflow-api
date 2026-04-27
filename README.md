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