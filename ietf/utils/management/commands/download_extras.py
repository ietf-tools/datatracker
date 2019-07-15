# Copyright The IETF Trust 2019, All Rights Reserved
# -*- coding: utf-8 -*-


from __future__ import absolute_import, print_function, unicode_literals

import os
import subprocess

from textwrap import dedent

from django.core.management.base import BaseCommand
from django.conf import settings

import debug                            # pyflakes:ignore

class Command(BaseCommand):
    """
    Download extra files (photos, floorplans, ...)
    """

    help = dedent(__doc__).strip()
            
    def handle(self, *filenames, **options):
        for src, dst in (
                ('rsync.ietf.org::dev.media/', settings.MEDIA_ROOT), ):
            if src and dst:
                if not dst.endswith(os.pathsep):
                    dst += os.pathsep
                subprocess.call(('rsync', '-auz', '--info=progress2', src, dst))
                