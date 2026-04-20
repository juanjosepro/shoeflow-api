from django.core.management import call_command

def load_staff_defaults(sender, **kwargs):
    # Esto cargará el JSON automáticamente cada vez que se migre un esquema
    try:
        call_command('loaddata', 'initial_staff.json')
        print("✅ Datos iniciales cargados correctamente.")
    except Exception as e:
        print(f"⚠️ Nota: No se pudo cargar initial_staff (esto es normal en la primera migración pública): {e}")