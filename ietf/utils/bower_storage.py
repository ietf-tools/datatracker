from django.core.files.storage import FileSystemStorage
from django.contrib.staticfiles.finders import BaseStorageFinder
from django.conf import settings

if settings.SERVER_MODE != 'production':
    # We need this during test and development in order to find the external
    # static files which are managed with bower (using manage.py bower_install)
    class BowerStorageFinder(BaseStorageFinder):
        storage = FileSystemStorage(location=settings.STATIC_ROOT, base_url=settings.STATIC_URL)
