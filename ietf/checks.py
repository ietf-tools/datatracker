import os

from django.conf import settings
from django.core import checks

@checks.register('directories')
def check_cdn_directory_exists(app_configs, **kwargs):
    """This checks that the path from which the CDN will serve static files for
       this version of the datatracker actually exists.  In development and test
       mode STATIC_ROOT will normally be just static/, but in production it will be
       set to a different part of the file system which is served via CDN, and the
       path will contain the datatracker release version.
    """
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
    from ietf.group.info import check_group_email_aliases
    errors = []
    try:
        ok = check_group_email_aliases()
        if not ok:
            errors.append(checks.Error(
                "Found no aliases in the group email aliases file",
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
    errors = []
    try:
        ok = check_doc_email_aliases()
        if not ok:
            errors.append(checks.Critical(
                "Found no aliases in the document email aliases file.",
                hint="Please run ietf/bin/generate-draft-aliases to generate them.",
                obj=None,
                id="datatracker.E0004",
            ))
    except IOError as e:
        errors.append(checks.Critical(
            "Could not read document email aliases:\n   %s" % e,
            hint="Please run ietf/bin/generate-draft-aliases to generate them.",
            obj=None,
            id="datatracker.E0005",
        ))

    return errors
    
@checks.register('directories')
def check_id_submission_directories(app_configs, **kwargs):
    errors = []
    for s in ("IDSUBMIT_STAGING_PATH", "IDSUBMIT_REPOSITORY_PATH", "INTERNET_DRAFT_ARCHIVE_DIR"):
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
