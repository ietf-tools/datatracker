import logging

from django.conf import settings

# Python 2.7 has an importlib with import_module.
# For older Pythons, Django's bundled copy provides it.
# For older Django's dajaxice reduced_import_module.
try:
    from importlib import import_module
except:
    try:
        from django.utils.importlib import import_module
    except:
        from dajaxice.utils import simple_import_module as import_module

log = logging.getLogger('dajaxice.DajaxiceRequest')


class DajaxiceFunction(object):

    def __init__(self, name, path, doc=None):
        self.name = name
        self.path = path
        self.doc = doc

    def get_callable_path(self):
        return '%s.%s' % (self.path.replace('.ajax', ''), self.name)

    def __cmp__(self, other):
        return (self.name == other.name and self.path == other.path)


class DajaxiceModule(object):
    def __init__(self, module):
        self.functions = []
        self.sub_modules = []
        self.name = module[0]

        sub_module = module[1:]
        if len(sub_module) != 0:
            self.add_submodule(sub_module)

    def get_module(self, module):
        """
        Recursively get_module util we found it.
        """
        if len(module) == 0:
            return self

        for dajaxice_module in self.sub_modules:
            if dajaxice_module.name == module[0]:
                return dajaxice_module.get_module(module[1:])
        return None

    def add_function(self, function):
        self.functions.append(function)

    def has_sub_modules(self):
        return len(self.sub_modules) > 0

    def add_submodule(self, module):
        """
        Recursively add_submodule, if it's not registered, create it.
        """
        if len(module) == 0:
            return
        else:
            sub_module = self.exist_submodule(module[0])

            if type(sub_module) == int:
                self.sub_modules[sub_module].add_submodule(module[1:])
            else:
                self.sub_modules.append(DajaxiceModule(module))

    def exist_submodule(self, name):
        """
        Check if submodule name was already registered.
        """
        for module in self.sub_modules:
            if module.name == name:
                return self.sub_modules.index(module)
        return False


class Dajaxice(object):
    def __init__(self):
        self._registry = []
        self._callable = []

        for function in getattr(settings, 'DAJAXICE_FUNCTIONS', ()):
            function = function.rsplit('.', 1)
            self.register_function(function[0], function[1])

    def register(self, function):
        self.register_function(function.__module__, function.__name__, function.__doc__)

    def register_function(self, module, name, doc=None):
        """
        Register function at 'module' depth
        """
        #Create the dajaxice function.
        function = DajaxiceFunction(name=name, path=module, doc=doc)

        #Check for already registered functions.
        full_path = '%s.%s' % (module, name)
        if full_path in self._callable:
            log.warning('%s already registered as dajaxice function.' % full_path)
            return

        self._callable.append(full_path)

        #Dajaxice path without ajax.
        module_without_ajax = module.replace('.ajax', '').split('.')

        #Register module if necessary.
        exist_module = self._exist_module(module_without_ajax[0])

        if type(exist_module) == int:
            self._registry[exist_module].add_submodule(module_without_ajax[1:])
        else:
            self._registry.append(DajaxiceModule(module_without_ajax))

        #Register Function
        module = self.get_module(module_without_ajax)
        if module:
            module.add_function(function)

    def get_module(self, module):
        """
        Recursively get module from registry
        """
        for dajaxice_module in self._registry:
            if dajaxice_module.name == module[0]:
                return dajaxice_module.get_module(module[1:])
        return None

    def is_callable(self, name):
        return name in self._callable

    def _exist_module(self, module_name):
        for module in self._registry:
            if module.name == module_name:
                return self._registry.index(module)
        return False

    def get_functions(self):
        return self._registry


LOADING_DAJAXICE = False


def dajaxice_autodiscover():
    """
    Auto-discover INSTALLED_APPS ajax.py modules and fail silently when
    not present.
    NOTE: dajaxice_autodiscover was inspired/copied from django.contrib.admin autodiscover
    """
    global LOADING_DAJAXICE
    if LOADING_DAJAXICE:
        return
    LOADING_DAJAXICE = True

    import imp
    from django.conf import settings

    for app in settings.INSTALLED_APPS:

        try:
            app_path = import_module(app).__path__
        except AttributeError:
            continue

        try:
            imp.find_module('ajax', app_path)
        except ImportError:
            continue

        import_module("%s.ajax" % app)

    LOADING_DAJAXICE = False
