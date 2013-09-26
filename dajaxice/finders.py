import os
import tempfile

from django.contrib.staticfiles import finders
from django.template import Context
from django.template.loader import get_template
from django.core.exceptions import SuspiciousOperation


class VirtualStorage(finders.FileSystemStorage):
    """" Mock a FileSystemStorage to build tmp files on demand."""

    def __init__(self, *args, **kwargs):
        self._files_cache = {}
        super(VirtualStorage, self).__init__(*args, **kwargs)

    def get_or_create_file(self, path):
        if path not in self.files:
            return ''

        data = getattr(self, self.files[path])()

        try:
            current_file = open(self._files_cache[path])
            current_data = current_file.read()
            current_file.close()
            if current_data != data:
                os.remove(path)
                raise Exception("Invalid data")
        except Exception:
            handle, tmp_path = tempfile.mkstemp()
            tmp_file = open(tmp_path, 'w')
            tmp_file.write(data)
            tmp_file.close()
            self._files_cache[path] = tmp_path

        return self._files_cache[path]

    def exists(self, name):
        return name in self.files

    def listdir(self, path):
        folders, files = [], []
        for f in self.files:
            if f.startswith(path):
                f = f.replace(path, '', 1)
                if os.sep in f: 
                    folders.append(f.split(os.sep, 1)[0])
                else:
                    files.append(f)
        return folders, files

    def path(self, name):
        try:
            path = self.get_or_create_file(name)
        except ValueError:
            raise SuspiciousOperation("Attempted access to '%s' denied." % name)
        return os.path.normpath(path)


class DajaxiceStorage(VirtualStorage):

    files = {'dajaxice/dajaxice.core.js': 'dajaxice_core_js'}

    def dajaxice_core_js(self):
        from dajaxice.core import dajaxice_autodiscover, dajaxice_config

        dajaxice_autodiscover()

        c = Context({'dajaxice_config': dajaxice_config})
        return get_template('dajaxice/dajaxice.core.js').render(c)


class DajaxiceFinder(finders.BaseStorageFinder):
    storage = DajaxiceStorage()
