import os
import sys

#sys.path.append('/a/www/ietfsec/current:/a/www/ietf-datatracker/web')
#sys.path.append('/a/home/rcross/devx/current:/a/home/rcross/devx/ietf')
sys.path.insert(0, '/a/home/rcross/devx/ietf')
sys.path.insert(0, '/a/home/rcross/devx/current')

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sec.settings")

# This application object is used by the development server
# as well as any WSGI server configured to use this file.
# NOTE may need this config if we upgrade django
#from django.core.wsgi import get_wsgi_application
#application = get_wsgi_application()

import django.core.handlers.wsgi
application = django.core.handlers.wsgi.WSGIHandler()
