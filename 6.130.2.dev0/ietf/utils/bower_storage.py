from django.core.files.storage import FileSystemStorage
from django.contrib.staticfiles.finders import BaseStorageFinder
from django.conf import settings

import debug                            # pyflakes:ignore

class BowerStorageFinder(BaseStorageFinder):
    storage = FileSystemStorage(location=settings.COMPONENT_ROOT, base_url=settings.COMPONENT_URL)

    def find(self, path, all=False):
        files = super(BowerStorageFinder, self).find(path, all)
        return files
