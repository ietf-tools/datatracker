from django.core.files.storage import FileSystemStorage
from django.contrib.staticfiles.finders import BaseStorageFinder
from django.conf import settings

if settings.SERVER_MODE != 'production':
    class CdnStorageFinder(BaseStorageFinder):
        storage = FileSystemStorage(location=settings.STATIC_ROOT, base_url=settings.STATIC_URL)
