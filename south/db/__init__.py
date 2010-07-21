
# Establish the common DatabaseOperations instance, which we call 'db'.
# This code somewhat lifted from django evolution
from django.conf import settings
import sys
if hasattr(settings, "SOUTH_DATABASE_ADAPTER"):
    module_name = settings.SOUTH_DATABASE_ADAPTER
else:
    module_name = '.'.join(['south.db', settings.DATABASE_ENGINE])

try:
    module = __import__(module_name,{},{},[''])
except ImportError:
    sys.stderr.write("There is no South database module for the engine '%s' (tried with %s). Please either choose a supported one, or check for SOUTH_DATABASE_ADAPTER settings, or remove South from INSTALLED_APPS.\n" 
                     % (settings.DATABASE_ENGINE, module_name))
    sys.exit(1)
db = module.DatabaseOperations()
