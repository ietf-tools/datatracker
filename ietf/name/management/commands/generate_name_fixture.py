# Copyright The IETF Trust 2019-2026, All Rights Reserved
"""Management command for exporting name related base data for the tests"""

import inspect
import io
import os
import sys
from pprint import pprint
from typing import List  # pyflakes:ignore

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.serializers import serialize
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection

from ietf.dbtemplate.models import DBTemplate
from ietf.doc.models import BallotType, State, StateType
from ietf.group.models import GroupFeatures
from ietf.mailtrigger.models import MailTrigger, Recipient
from ietf.meeting.models import BusinessConstraint
from ietf.name import models as name_models
from ietf.stats.models import CountryAlias


class SortedJsonEncoder(DjangoJSONEncoder):
    def __init__(self, *args, **kwargs):
        kwargs["sort_keys"] = True
        super().__init__(*args, **kwargs)


class Command(BaseCommand):
    help = """
    Generate a custom fixture for all objects needed by the datatracker test suite.

    The recommended way to use this is unfortunately not the default, as the ordering
    of the resulting fixture isn't quite stable.  Instead use:

      "ietf/manage.py generate_name_fixture --stdout | jq --sort-keys 'sort_by(.model, .pk)' > ietf/name/fixtures/names.json"
    """
    output = None

    def add_arguments(self, parser):
        parser.add_argument(
            "--stdout",
            action="store_true",
            default=False,
            help="Send fixture to stdout instead of ietf/name/fixtures/names.json",
        )

    def handle(self, *args, **options):
        self.output = (
            sys.stdout
            if options.get("stdout")
            else io.open(
                os.path.join(settings.BASE_DIR, "name/fixtures/names.json"), "w"
            )
        )

        def model_name(model_):
            return "%s.%s" % (model_._meta.app_label, model_.__name__)

        def output(seq):
            try:
                f = self.output
                f.write(serialize("json", seq, cls=SortedJsonEncoder, indent=2))
                f.close()
            except:

                pprint(connection.queries)
                raise

        objects: List[object] = []  # type: ignore[annotation-unchecked]
        model_objects = {}

        # Grab all ietf.name.models
        for n in dir(name_models):
            item = getattr(name_models, n)
            if inspect.isclass(item) and issubclass(item, name_models.NameModel):
                if not item._meta.abstract:
                    model_objects[model_name(item)] = list(
                        item.objects.all().order_by("pk")
                    )

        for m in (
            BallotType,
            State,
            StateType,
            GroupFeatures,
            MailTrigger,
            Recipient,
            CountryAlias,
            BusinessConstraint,
        ):
            model_objects[model_name(m)] = list(m.objects.all().order_by("pk"))

        for m in (DBTemplate,):
            model_objects[model_name(m)] = [m.objects.get(pk=354)]

        for model_name in sorted(model_objects.keys()):
            objects += model_objects[model_name]

        output(objects)
