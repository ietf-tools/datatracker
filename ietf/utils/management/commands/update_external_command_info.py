from __future__ import print_function, unicode_literals

import sys

from textwrap import dedent

from django.core.management.base import BaseCommand

import debug                            # pyflakes:ignore

from ietf.utils.models import VersionInfo
from ietf.utils.pipe import pipe

class Command(BaseCommand):
    """
    Update the version information for external commands used by the datatracker.

    Iterates through the entries in the VersionInfo table, runs the relevant
    command, and updates the version string with the result.

    """

    help = dedent(__doc__).strip()
            
    def handle(self, *filenames, **options):
        for c in VersionInfo.objects.filter(used=True):
            cmd = "%s %s" % (c.command, c.switch)
            code, out, err = pipe(cmd)
            if code != 0:
                sys.stderr.write("Command '%s' retuned %s: \n%s\n%s\n" % (cmd, code, out, err))
            else:
                c.version = (out.strip()+'\n'+err.strip()).strip()
                if options.get('verbosity', 1) > 1:
                    sys.stdout.write(
                        "Command: %s\n"
                        "  Version: %s\n" % (cmd, c.version))
                c.save()
