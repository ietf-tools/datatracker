import os
import sys
import time

from optparse import make_option
from pathlib import Path
from StringIO import StringIO
from textwrap import dedent
from xym import xym

from django.conf import settings
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    """
    Populate the yang models repositories from drafts and RFCs.

    Extracts yang models from RFCs (found in settings.RFC_PATH and places
    them in settings.YANG_RFC_MODEL_DIR, and from active drafts, placed in
    settings.YANG_DRAFT_MODEL_DIR if valid and settings.YANG_INVAL_MODEL_DIR
    if not.

    """

    help = dedent(__doc__).strip()
            
    option_list = BaseCommand.option_list + (
        make_option('--clean',
            action='store_true', dest='clean', default=False,
            help='Remove the current directory content before writing new models.'),
        )

    def handle(self, *filenames, **options):
        """

         * All yang modules from published RFCs should be extracted and be
           available in an rfc-yang repository.

         * All valid yang modules from active, not replaced, internet drafts
           should be extracted and be available in a draft-valid-yang repository.

         * All, valid and invalid, yang modules from active, not replaced,
           internet drafts should be available in a draft-all-yang repository.
           (Actually, given precedence ordering, it would be enough to place
           non-validating modules in a draft-invalid-yang repository instead).

         * In all cases, example modules should be excluded.

         * Precedence is established by the search order of the repository as
           provided to pyang.

         * As drafts expire, models should be removed in order to catch cases
           where a module being worked on depends on one which has slipped out
           of the work queue.

        """

        verbosity = int(options.get('verbosity'))

        def extract_from(file, dir, strict=True):
            saved_stderr = sys.stderr
            sys.stderr = StringIO()
            model_list = []
            try:
                model_list = xym.xym(str(item), str(item.parent), str(dir), strict=strict, debug_level=(verbosity>1))
                for name in model_list:
                    modfile = moddir / name
                    mtime = item.stat().st_mtime
                    os.utime(str(modfile), (mtime, mtime))
                    if '"' in name:
                        name = name.replace('"', '')
                        modfile.rename(str(moddir/name))
                        model_list = [ n.replace('"','') for n in model_list ]
            except Exception as e:
                print("** Error when extracting from %s: %s" % (item, str(e)))
            sys.stderr = saved_stderr
            return model_list

        # Extract from new RFCs

        rfcdir = Path(settings.RFC_PATH)

        moddir = Path(settings.YANG_RFC_MODEL_DIR)
        if not moddir.exists():
            moddir.mkdir(parents=True)

        latest = 0
        for item in moddir.iterdir():
            if item.stat().st_mtime > latest:
                latest = item.stat().st_mtime
        
        print("Extracting to %s ..." % moddir)
        for item in rfcdir.iterdir():
            if item.is_file() and item.name.startswith('rfc') and item.name.endswith('.txt'):
                if item.stat().st_mtime > latest:
                    model_list = extract_from(item, moddir)
                    for name in model_list:
                        if name.startswith('ietf') or name.startswith('iana'):
                            if verbosity > 1:
                                print("  Extracted from %s: %s" % (item, name))
                            else:
                                sys.stdout.write('.')
                                sys.stdout.flush()
                        else:
                            modfile = moddir / name
                            modfile.unlink()
                            if verbosity > 1:
                                print("  Skipped module from %s: %s" % (item, name))
        print("")

        # Extract valid modules from drafts

        six_months_ago = time.time() - 6*31*24*60*60
        def active(item):
            return item.stat().st_mtime > six_months_ago

        draftdir = Path(settings.INTERNET_DRAFT_PATH)

        moddir = Path(settings.YANG_DRAFT_MODEL_DIR)
        if not moddir.exists():
            moddir.mkdir(parents=True)
        print("Emptying %s ..." % moddir)
        for item in moddir.iterdir():
            item.unlink()

        print("Extracting to %s ..." % moddir)
        for item in draftdir.iterdir():
            if item.is_file() and item.name.startswith('draft') and item.name.endswith('.txt') and active(item):
                model_list = extract_from(item, moddir)
                for name in model_list:
                    if not name.startswith('example'):
                        if verbosity > 1:
                            print("  Extracted valid module from %s: %s" % (item, name))
                        else:
                                sys.stdout.write('.')
                                sys.stdout.flush()
                    else:
                        modfile = moddir / name
                        modfile.unlink()
                        if verbosity > 1:
                            print("  Skipped module from %s: %s" % (item, name))
        print("")

        # Extract invalid modules from drafts
        valdir = moddir
        moddir = Path(settings.YANG_INVAL_MODEL_DIR)
        if not moddir.exists():
            moddir.mkdir(parents=True)
        print("Emptying %s ..." % moddir)
        for item in moddir.iterdir():
            item.unlink()

        print("Extracting to %s ..." % moddir)
        for item in draftdir.iterdir():
            if item.is_file() and item.name.startswith('draft') and item.name.endswith('.txt') and active(item):
                model_list = extract_from(item, moddir, strict=False)
                for name in model_list:
                    modfile = moddir / name                    
                    if (valdir/name).exists():
                        modfile.unlink()
                        if verbosity > 1:
                            print("  Skipped valid module from %s: %s" % (item, name))
                    elif not name.startswith('example'):
                        if verbosity > 1:
                            print("  Extracted invalid module from %s: %s" % (item, name))
                        else:
                                sys.stdout.write('.')
                                sys.stdout.flush()
                    else:
                        modfile.unlink()
                        if verbosity > 1:
                            print("  Skipped module from %s: %s" % (item, name))
        print("")
