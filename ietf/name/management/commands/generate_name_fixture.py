# Copyright The IETF Trust 2019-2020, All Rights Reserved
#!/usr/bin/python

# simple script for exporting name related base data for the tests

import inspect
import io
import os, sys

from typing import Any, List        # pyflakes:ignore


from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.serializers import serialize
from django.core.serializers.json import DjangoJSONEncoder

import debug                            # pyflakes:ignore

class SortedJsonEncoder(DjangoJSONEncoder):
    def __init__(self, *args, **kwargs):
        kwargs['sort_keys'] = True
        return super(SortedJsonEncoder, self).__init__(*args, **kwargs)

class Command(BaseCommand):
    help = """
    Generate a custom fixture for all objects needed by the datatracker test suite.

    The recommended way to use this is unfortunately not the default, as the ordering
    of the resulting fixture isn't quite stable.  Instead use:

      "ietf/manage.py generate_name_fixture --stdout | jq --sort-keys 'sort_by(.model, .pk)' > ietf/name/fixtures/names.json"
    """

    def add_arguments(self, parser):
        parser.add_argument('--stdout', action='store_true', default=False, help="Send fixture to stdout instead of ietf/name/fixtures/names.json")

    def say(self, msg):
        if self.verbosity > 0:
            sys.stdout.write(msg)
            sys.stdout.write('\n')

    def note(self, msg):
        if self.verbosity > 1:
            sys.stdout.write(msg)
            sys.stdout.write('\n')

    def mutter(self, msg):
        if self.verbosity > 2:
            sys.stdout.write(msg)
            sys.stdout.write('\n')

    def handle(self, *args, **options):
        self.output = sys.stdout if options.get('stdout') else io.open(os.path.join(settings.BASE_DIR, "name/fixtures/names.json"), 'w')

        def model_name(m):
            return '%s.%s' % (m._meta.app_label, m.__name__)

        def output(seq):
            try:
                f = self.output
                f.write(serialize("json", seq, cls=SortedJsonEncoder, indent=2))
                f.close()
            except:
                from django.db import connection
                from pprint import pprint
                pprint(connection.queries)
                raise

        objects = []                    # type: List[object]
        model_objects = {}

        import ietf.name.models
        from ietf.dbtemplate.models import DBTemplate
        from ietf.doc.models import BallotType, State, StateType
        from ietf.group.models import GroupFeatures
        from ietf.mailtrigger.models import MailTrigger, Recipient
        from ietf.stats.models import CountryAlias
        from ietf.utils.models import VersionInfo

        # Grab all ietf.name.models
        for n in dir(ietf.name.models):
            item = getattr(ietf.name.models, n)
            if inspect.isclass(item) and issubclass(item, ietf.name.models.NameModel):
                if not item._meta.abstract:
                    model_objects[model_name(item)] = list(item.objects.all().order_by('pk'))


        for m in ( BallotType, State, StateType, GroupFeatures, MailTrigger, Recipient, CountryAlias, VersionInfo ):
            model_objects[model_name(m)] = list(m.objects.all().order_by('pk'))

        for m in ( DBTemplate, ):
            model_objects[model_name(m)] = [ m.objects.get(pk=354) ]

        for model_name in sorted(model_objects.keys()):
            objects += model_objects[model_name]

        output(objects)

