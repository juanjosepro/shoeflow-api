from django.core.management import call_command

def load_payroll_defaults(sender, **kwargs):
    # Esto cargará el JSON automáticamente cada vez que se migre un esquema
    try:
        call_command('loaddata', 'initial_payroll.json')
        print("✅ Datos iniciales cargados correctamente.")
    except Exception as e:
        print(f"⚠️ Nota: No se pudo cargar initial_payroll (esto es normal en la primera migración pública): {e}")