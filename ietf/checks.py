import os

from django.conf import settings
from django.core import checks

@checks.register('directories')
def check_cdn_directory_exists(app_configs, **kwargs):
    """This checks that the path from which the CDN will serve static files for
       this version of the datatracker actually exists.  In development and test
       mode this will normally be just STATIC_ROOT, but in production it will be
       a symlink to STATIC_ROOT, with a path containing the datatracker release
       version.
    """
    errors = []
    if not os.path.exists(settings.STATIC_CDN_PATH):
        errors.append(checks.Error(
            'The CDN static files path has not been set up',
            hint='Set up this symlink:\n\t%s -> %s' % (settings.STATIC_CDN_PATH, settings.STATIC_ROOT),
            obj=None,
            id='datatracker.E001',
        ))
    return errors
