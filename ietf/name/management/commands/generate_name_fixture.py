# Copyright The IETF Trust 2019-2026, All Rights Reserved
"""Management command for exporting name related base data for the tests"""

import json

from django.core.management.base import BaseCommand
from django.core.serializers import serialize
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from ietf.dbtemplate.models import DBTemplate
from ietf.doc.models import BallotType, State, StateType
from ietf.group.models import GroupFeatures
from ietf.mailtrigger.models import MailTrigger, Recipient
from ietf.meeting.models import BusinessConstraint
from ietf.name.models import NameModel
from ietf.stats.models import CountryAlias


class Command(BaseCommand):
    help = """
    Generate a custom fixture for all objects needed by the datatracker test suite.

    The fixture is written to stdout:

      "ietf/manage.py generate_name_fixture > ietf/name/fixtures/names.json"
    """

    def handle(self, *args, **options):
        objects: list[models.Model] = []  # type: ignore[annotation-unchecked]

        # Grab all ietf.name.models
        for name_model in NameModel.__subclasses__():
            if not name_model._meta.abstract:
                objects.extend(name_model.objects.all())

        # Grab some name-like models, too
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
            objects.extend(m.objects.all())

        # This specific DBTemplate was needed as of 2019
        for m in (DBTemplate,):
            objects.append(m.objects.get(pk=354))

        # Sort the serialized dicts rather than the querysets: "model" is the lowercased
        # "app_label.modelname", which does not order the same way as the model class
        # names, and string pks must compare by code point, not by DB collation.
        data = sorted(serialize("python", objects), key=lambda d: (d["model"], d["pk"]))

        # ensure_ascii=False keeps non-ASCII characters (e.g., "Åland Islands") as UTF-8,
        # so the stream has to be able to encode them whatever the environment's locale.
        reconfigure = getattr(self.stdout, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")

        # These options reproduce the formatting of "jq --sort-keys", which historically
        # post-processed this command's output. OutputWrapper adds the trailing newline.
        self.stdout.write(
            json.dumps(
                data,
                cls=DjangoJSONEncoder,
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
        )
