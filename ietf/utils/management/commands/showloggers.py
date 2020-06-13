# Copyright The IETF Trust 2020, All Rights Reserved
# -*- coding: utf-8 -*-

import logging_tree
import os

from textwrap import dedent

from django.core.management.base import BaseCommand

import debug                            # pyflakes:ignore

class Command(BaseCommand):
    """
    Display a list or tree representation of python loggers.

    Add a UTILS_LOGGER_LEVELS setting in settings_local.py to configure
    non-default logging levels for any registered logger, for instance:

    UTILS_LOGGER_LEVELS = {
        'oicd_provider': 'DEBUG',
        'urllib3.connection': 'DEBUG',
    }

    """

    help = dedent(__doc__).strip()

    def add_arguments(self, parser):
        parser.add_argument('--tree', action="store_true", default=False,
            help='Only list loggers found, without showing the full tree.')

    def handle(self, *filenames, **options):
        if options.get('tree'):
            self.stdout.write(logging_tree.format.build_description(node=None))
        else:
            self.stdout.write("Registered logging.Logger instances by name:")
            def show(node):
                if len(node) == 3:
                    name, logger, nodes = node
                    self.stdout.write("   %s" % (name or ''))
                    for node in nodes:
                        show(node)
                else:
                    self.stdout.write('Node: %s' % node)
            show(logging_tree.tree())
            self.stdout.write("\nUse '%s --tree' to show the full logger tree" % os.path.splitext(os.path.basename(__file__))[0])
