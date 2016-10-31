import os
import sys
import time
from textwrap import dedent

import debug                            # pyflakes:ignore
debug.debug = True

from django.conf import settings
from django.core import checks
from django.utils.module_loading import import_string

checks_run = []

def already_ran():
    import inspect
    outerframe = inspect.currentframe().f_back
    name = outerframe.f_code.co_name
    if name in checks_run:
        return True
    else:
        checks_run.append(name)
        return False

@checks.register('directories')
def check_cdn_directory_exists(app_configs, **kwargs):
    """This checks that the path from which the CDN will serve static files for
       this version of the datatracker actually exists.  In development and test
       mode STATIC_ROOT will normally be just static/, but in production it will be
       set to a different part of the file system which is served via CDN, and the
       path will contain the datatracker release version.
    """
    if already_ran():
        return []
    #
    errors = []
    if settings.SERVER_MODE == 'production' and not os.path.exists(settings.STATIC_ROOT):
        errors.append(checks.Error(
            "The static files directory has not been set up.",
            hint="Please run 'ietf/manage.py collectstatic'.",
            obj=None,
            id='datatracker.E001',
        ))
    return errors

@checks.register('files')
def check_group_email_aliases_exists(app_configs, **kwargs):
    from ietf.group.views import check_group_email_aliases
    #
    if already_ran():
        return []
    #
    errors = []
    try:
        ok = check_group_email_aliases()
        if not ok:
            errors.append(checks.Error(
                "Found no aliases in the group email aliases file\n'%s'."%settings.GROUP_ALIASES_PATH,
                hint="Please run ietf/bin/generate-wg-aliases to generate them.",
                obj=None,
                id="datatracker.E0002",
            ))
    except IOError as e:
        errors.append(checks.Error(
            "Could not read group email aliases:\n   %s" % e,
            hint="Please run ietf/bin/generate-wg-aliases to generate them.",
            obj=None,
            id="datatracker.E0003",
        ))
        
    return errors

@checks.register('files')
def check_doc_email_aliases_exists(app_configs, **kwargs):
    from ietf.doc.views_doc import check_doc_email_aliases
    #
    if already_ran():
        return []
    #
    errors = []
    try:
        ok = check_doc_email_aliases()
        if not ok:
            errors.append(checks.Error(
                "Found no aliases in the document email aliases file\n'%s'."%settings.DRAFT_ALIASES_PATH,
                hint="Please run ietf/bin/generate-draft-aliases to generate them.",
                obj=None,
                id="datatracker.E0004",
            ))
    except IOError as e:
        errors.append(checks.Error(
            "Could not read document email aliases:\n   %s" % e,
            hint="Please run ietf/bin/generate-draft-aliases to generate them.",
            obj=None,
            id="datatracker.E0005",
        ))

    return errors
    
@checks.register('directories')
def check_id_submission_directories(app_configs, **kwargs):
    #
    if already_ran():
        return []
    #
    errors = []
    for s in ("IDSUBMIT_STAGING_PATH", "IDSUBMIT_REPOSITORY_PATH", "INTERNET_DRAFT_ARCHIVE_DIR", ):
        p = getattr(settings, s)
        if not os.path.exists(p):
            errors.append(checks.Critical(
                "A directory used by the ID submission tool does not exist at the path given\n"
                "in the settings file.  The setting is:\n"
                "    %s = %s" % (s, p),
                hint = ("Please either update the local settings to point at the correct directory,"
                    "or if the setting is correct, create the directory."),
                id = "datatracker.E0006",
            ))
    return errors

@checks.register('files')
def check_id_submission_files(app_configs, **kwargs):
    #
    if already_ran():
        return []
    #
    errors = []
    for s in ("IDSUBMIT_IDNITS_BINARY", ):
        p = getattr(settings, s)
        if not os.path.exists(p):
            errors.append(checks.Critical(
                "A file used by the ID submission tool does not exist at the path given\n"
                "in the settings file.  The setting is:\n"
                "    %s = %s" % (s, p),
                hint = ("Please either update the local settings to point at the correct file,"
                    "or if the setting is correct, make sure the file is in place and has the right permissions."),
                id = "datatracker.E0007",
            ))
    return errors

@checks.register('submission-checkers')
def check_id_submission_checkers(app_configs, **kwargs):
    #
    if already_ran():
        return []
    #
    errors = []
    for checker_path in settings.IDSUBMIT_CHECKER_CLASSES:
        try:
            checker_class = import_string(checker_path)
        except Exception as e:
            errors.append(checks.Critical(
                "An exception was raised when trying to import the draft submission"
                "checker class '%s':\n %s" % (checker_path, e),
                hint = "Please check that the class exists and can be imported.",
                id = "datatracker.E0008",
            ))
        try:
            checker = checker_class()
        except Exception as e:
            errors.append(checks.Critical(
                "An exception was raised when trying to instantiate the draft submission"
                "checker class '%s': %s" % (checker_path, e),
                hint = "Please check that the class can be instantiated.",
                id = "datatracker.E0009",
            ))
            continue
        for attr in ('name',):
            if not hasattr(checker, attr):
                errors.append(checks.Critical(
                    "The draft submission checker '%s' has no attribute '%s', which is required" % (checker_path, attr),
                    hint = "Please update the class.",
                    id = "datatracker.E0010",
                ))
        checker_methods = ("check_file_txt", "check_file_xml", "check_fragment_txt", "check_fragment_xml", )
        for method in checker_methods:
            if hasattr(checker, method):
                break
        else:
            errors.append(checks.Critical(
                "The draft submission checker '%s' has no recognised checker method;  "
                "should be one or more of %s." % (checker_path, checker_methods),
                hint = "Please update the class.",
                id = "datatracker.E0011",
            ))
    return errors

@checks.register('directories')
def check_media_directories(app_configs, **kwargs):
    #
    if already_ran():
        return []
    #
    errors = []
    for s in ("PHOTOS_DIR", ):
        p = getattr(settings, s)
        if not os.path.exists(p):
            errors.append(checks.Critical(
                "A directory used for media uploads and serves does not exist at the path given\n"
                "in the settings file.  The setting is:\n"
                "    %s = %s" % (s, p),
                hint = ("Please either update the local settings to point at the correct directory,"
                    "or if the setting is correct, create the directory."),
                id = "datatracker.E0012",
            ))
    return errors

    
@checks.register('directories')
def check_proceedings_directories(app_configs, **kwargs):
    #
    if already_ran():
        return []
    #
    errors = []
    for s in ("AGENDA_PATH", ):
        p = getattr(settings, s)
        if not os.path.exists(p):
            errors.append(checks.Critical(
                "A directory used for meeting materials does not exist at the path given\n"
                "in the settings file.  The setting is:\n"
                "    %s = %s" % (s, p),
                hint = ("Please either update the local settings to point at the correct directory,"
                    "or if the setting is correct, create the directory."),
                id = "datatracker.E0013",
            ))
    return errors

@checks.register('cache')
def check_cache(app_configs, **kwargs):
    #
    if already_ran():
        return []
    #
    errors = []
    if settings.SERVER_MODE == 'production':
        from django.core.cache import cache
        def cache_error(msg, errnum):
            return checks.Warning(
                ( "A cache test failed with the message:\n    '%s'.\n"
                "This indicates that the cache is unavailable or not working as expected.\n"
                "It will impact performance, but isn't fatal.  The default cache is:\n"
                "    CACHES['default']['BACKEND'] = %s\n") % (
                    msg,
                    settings.CACHES["default"]["BACKEND"],
                ),
                hint = "Please check that the configured cache backend is available.\n",
                id = "datatracker.%s" % errnum,
            )
        key = "ietf:checks:check_cache"
        val = os.urandom(32)
        wait = 1
        cache.set(key, val, wait)
        if not cache.get(key) == val:
            errors.append(cache_error("Could not get value from cache", "E0014"))
        time.sleep(wait+1)
        # should have timed out
        if cache.get(key) == val:
            errors.append(cache_error("Cache value didn't time out", "E0015"))
        cache.set(key, val, settings.SESSION_COOKIE_AGE)
        if not cache.get(key) == val:
            errors.append(cache_error("Cache didn't accept session cookie age", "E0016"))
    return errors
    
@checks.register('cache')
def check_svn_import(app_configs, **kwargs):
    #
    if already_ran():
        return []
    #
    errors = []
    # 
    site_packages_dir = None
    for p in sys.path:
        if ('/env/' in p or '/venv/' in p) and '/site-packages' in p:
            site_packages_dir = p
            break
    if site_packages_dir:
        for path in settings.SVN_PACKAGES:
            if os.path.exists(path):
                dir, name = os.path.split(path)
                package_link = os.path.join(site_packages_dir, name)
                if not os.path.lexists(package_link):
                    os.symlink(path, package_link)
            else:
                errors.append(checks.Critical(
                    "The setting SVN_PACKAGES specify a library path which\n"
                    "does not exist:\n"
                    "   %s\n" % path,
                    hint = "Please provide the correct python system site-package paths for\n"
                    "svn and libsvn in SVN_PACKAGES.",
                    id = "datatracker.E0015",))
    #
    if settings.SERVER_MODE == 'production':
        try:
            import svn                  # pyflakes:ignore
        except ImportError as e:
            errors.append(checks.Critical(
                "Could not import the python svn module:\n   %s\n" % e,
                hint = dedent("""
                    You are running in production mode, and the subversion bindings for python
                    are necessary in order to run the Trac wiki glue scripts.

                    However, the subversion bindings seem to be unavailable.  The subversion
                    bindings are not available for install using pip, but must be supplied by
                    the system package manager.  In order to be available within the python
                    virtualenv, ietf.checks.check_svn_import() tries to create a symlink from
                    the configured location of the system-provided svn package to the
                    site-packages directory of the virtualenv. If you get this message, that has
                    failed to provide the svn package.

                    Please install 'python-subversion' (Debian), 'subversion-python' (RedHat,
                    CentOS, Fedora), 'subversion-python27bindings' (BSD); and provide the
                    correct path to the svn package in settings.SVN_PACKAGE.  Further tips are
                    available at https://trac.edgewall.org/wiki/TracSubversion.

                    """).replace('\n', '\n   ').rstrip(),
                id = "datatracker.E0014",
            ))
    return errors
