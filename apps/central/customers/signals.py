from django.dispatch import receiver
from django.contrib.auth.models import User
from django_tenants.utils import schema_context
from django_tenants.signals import post_schema_sync # Señal específica de django-tenants
from .models import Client

@receiver(post_schema_sync)
def create_tenant_admins(sender, **kwargs):
    # 'tenant' es el objeto Client que se acaba de sincronizar
    instance = kwargs.get('tenant')
    
    # Evitamos que se ejecute para el esquema 'public'
    if instance.schema_name == 'public':
        return

    # Nos aseguramos de estar en el esquema correcto
    with schema_context(instance.schema_name):
        # Verificamos si ya existen para evitar duplicados en migraciones futuras
        if not User.objects.filter(username='superadmin').exists():
            # Crear el primer superusuario en el esquema del tenant
            User.objects.create_superuser(
                username='superadmin',
                first_name='Super',
                last_name='Admin',
                email=f'superadmin@gmail.com',
                password='Supernov@08'
            )
            
            # Crear el segundo superusuario en el esquema del tenant
            User.objects.create_superuser(
                username='admin',
                first_name='Admin',
                last_name='User',
                email=f'admin@gmail.com',
                password='123456'
            )
            print(f"✅ Usuarios creados exitosamente en el esquema: {instance.schema_name}")