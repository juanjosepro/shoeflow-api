from django.core.management import call_command

def load_catalog_defaults(sender, **kwargs):
    # This will load the JSON automatically every time a schema is migrated
    try:
        call_command('loaddata', 'initial_catalog.json')
        print("✅ Initial catalog data loaded successfully.")
    except Exception as e:
        print(f"⚠️ Note: Failed to load initial_catalog (this is normal in the first public migration): {e}")