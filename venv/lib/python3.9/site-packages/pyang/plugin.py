"""pyang plugin handling"""

import os
import sys
import pkg_resources

plugins = []
"""List of registered PyangPlugin instances"""

def init(plugindirs=None):
    """Initialize the plugin framework"""
    if plugindirs is None:
        plugindirs = []

    # initialize the builtin plugins
    from .translators import yang,yin,dsdl
    yang.pyang_plugin_init()
    yin.pyang_plugin_init()
    dsdl.pyang_plugin_init()

    # initialize installed plugins
    for ep in pkg_resources.iter_entry_points(group='pyang.plugin'):
        plugin_init = ep.load()
        plugin_init()

    # search for plugins in std directories (plugins directory first)
    basedir = os.path.split(sys.modules['pyang'].__file__)[0]
    plugindirs.insert(0, basedir + "/transforms")
    plugindirs.insert(0, basedir + "/plugins")

    # add paths from env
    pluginpath = os.getenv('PYANG_PLUGINPATH')
    if pluginpath is not None:
        plugindirs.extend(pluginpath.split(os.pathsep))

    syspath = sys.path
    for plugindir in plugindirs:
        sys.path = [plugindir] + syspath
        try:
            fnames = os.listdir(plugindir)
        except OSError:
            continue
        modnames = []
        for fname in fnames:
            if (fname.startswith(".#") or
                fname.startswith("__init__.py") or
                fname.endswith("_flymake.py") or
                fname.endswith("_flymake.pyc")):
                pass
            elif fname.endswith(".py"):
                modname = fname[:-3]
                if modname not in modnames:
                    modnames.append(modname)
            elif fname.endswith(".pyc"):
                modname = fname[:-4]
                if modname not in modnames:
                    modnames.append(modname)
        for modname in modnames:
            pluginmod = __import__(modname)
            try:
                pluginmod.pyang_plugin_init()
            except AttributeError as s:
                print(pluginmod.__dict__)
                raise AttributeError(pluginmod.__file__ + ': ' + str(s))
        sys.path = syspath

def register_plugin(plugin):
    """Call this to register a pyang plugin. See class PyangPlugin
    for more info.
    """
    plugins.append(plugin)

def is_plugin_registered(name):
    for plugin in plugins:
        if plugin.name == name:
            return True
    return False

class PyangPlugin(object):
    """Abstract base class for pyang plugins

    A pyang plugin is a module found in the plugins directory of the
    pyang installation, or in the dynamic pluginpath.

    Such a module must export a function 'pyang_plugin_init()', which
    may call pyang.plugin.register_plugin() with an instance of a class
    derived from this class as argument.

    A plugin can extend the base pyang library functions, or the pyang
    front-end program, or both.
    """

    def __init__(self, name=None):
        self.name = name
        self.multiple_modules = False
        self.handle_comments = False

    ## pyang front-end program methods

    def add_output_format(self, fmts):
        """Add an output format to the pyang program.

        `fmts` is a dict which maps the format name string to a plugin
        instance.

        Override this method and update `fmts` with the output format
        name.
        """
        return

    def add_transform(self, xforms):
        """Add a transform to the pyang program.

        `xforms` is a dict which maps the transform name string to a plugin
        instance.

        Override this method and update `xforms` with the transform name.
        """
        return

    def add_opts(self, optparser):
        """Add command line options to the pyang program.

        Override this method and add the plugin related options as an
        option group.
        """
        return

    ## library methods

    def setup_ctx(self, ctx):
        """Modify the Context at setup time.  Called for all plugins.

        Override this method to modify the Context before the module
        repository is accessed.
        """
        return

    def setup_fmt(self, ctx):
        """Modify the Context at setup time.  Called for the selected
        output format plugin.

        Override this method to modify the Context before the module
        repository is accessed.
        """
        return

    def setup_xform(self, ctx):
        """Modify the Context at setup time.  Called for the selected
        transform plugin.

        Override this method to modify the Context before the module
        repository is accessed.
        """
        return

    def pre_load_modules(self, ctx):
        """Called for the selected plugin, before any modules are loaded"""
        return

    def pre_validate_ctx(self, ctx, modules):
        """Called for all plugins, before the modules are validated"""
        return

    def pre_validate(self, ctx, modules):
        """Called for the selected plugin, before the modules are validated"""
        return

    def post_validate(self, ctx, modules):
        """Called for the selected plugin, after the modules
        have been validated"""
        return

    def post_validate_ctx(self, ctx, modules):
        """Called for all plugins, after the modules
        have been validated"""
        return

    def emit(self, ctx, modules, fd):
        """Produce the plugin output.

        Override this method to perform the output conversion.
        `fd` is a file-like object open for writing.

        Raise error.EmitError on failure.
        """
        return

    def transform(self, ctx, modules):
        """Transform the modules (called after modules have been validated).

        Override this method to modify the modules.
        Return `True` to indicate either that none of the modifications
        require modules to be re-validated or that the modules have already
        been re-validated.

        Raise error.TransformError on failure."""
