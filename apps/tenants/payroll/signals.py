from django.core.management import call_command

def load_payroll_defaults(sender, **kwargs):
    # Esto cargará el JSON automáticamente cada vez que se migre un esquema
    try:
        call_command('loaddata', 'initial_payroll.json')
        print("✅ Initial payroll data loaded successfully.")
    except Exception as e:
        print(f"⚠️ Note: Failed to load initial_payroll (this is normal during the first public migration). {e}")