from django.core.management import call_command

def load_staff_defaults(sender, **kwargs):
    # Esto cargará el JSON automáticamente cada vez que se migre un esquema
    try:
        call_command('loaddata', 'initial_staff.json')
        print("✅ Initial staff data loaded successfully.")
    except Exception as e:
        print(f"⚠️ Note: Failed to load initial_staff (this is normal during the first public migration). {e}")