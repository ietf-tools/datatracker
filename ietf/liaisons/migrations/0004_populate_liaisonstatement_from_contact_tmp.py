# Copyright The IETF Trust 2025, All Rights Reserved
from itertools import islice

from django.db import migrations

from ietf.person.name import plain_name
from ietf.utils.mail import formataddr
from ietf.utils.validators import validate_mailbox_address


def forward(apps, schema_editor):
    def _formatted_email(email):
        """Format an email address to match Email.formatted_email()"""
        person = email.person
        if person:
            return formataddr(
                (
                    # inlined Person.plain_name(), minus the caching
                    person.plain if person.plain else plain_name(person.name),
                    email.address,
                )
            )
        return email.address

    def _batched(iterable, n):
        """Split an iterable into lists of length <= n

        (based on itertools example code for batched(), which is added in py312)
        """
        iterator = iter(iterable)
        batch = list(islice(iterator, n))  # consumes first n iterations
        while batch:
            yield batch
            batch = list(islice(iterator, n))  # consumes next n iterations

    LiaisonStatement = apps.get_model("liaisons", "LiaisonStatement")
    LiaisonStatement.objects.update(from_contact_tmp="")  # ensure they're all blank
    for batch in _batched(
        LiaisonStatement.objects.exclude(from_contact=None).select_related(
            "from_contact"
        ),
        100,
    ):
        for ls in batch:
            ls.from_contact_tmp = _formatted_email(ls.from_contact)
            validate_mailbox_address(
                ls.from_contact_tmp
            )  # be sure it's permitted before we accept it

        LiaisonStatement.objects.bulk_update(batch, fields=["from_contact_tmp"])


class Migration(migrations.Migration):
    dependencies = [
        ("liaisons", "0003_liaisonstatement_from_contact_tmp"),
    ]

    operations = [
        migrations.RunPython(forward),
    ]
