# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations, models
from django.db.models import Min

from ietf.person.name import alias_names


def remove_duplicate_aliases(apps, schema_editor):
    """Delete repeated aliases of the same name for a person, keeping the oldest row."""
    Alias = apps.get_model("person", "Alias")
    keep = Alias.objects.values("person", "name").annotate(keep_pk=Min("pk")).values("keep_pk")
    Alias.objects.exclude(pk__in=keep).delete()


def add_missing_aliases(apps, schema_editor):
    """Create the aliases each person's name forms call for but that are missing."""
    Alias = apps.get_model("person", "Alias")
    Person = apps.get_model("person", "Person")
    existing = set(Alias.objects.values_list("person_id", "name"))
    people = Person.objects.values_list("pk", "name", "ascii", "ascii_short", "plain")
    missing = []
    for pk, name, ascii, ascii_short, plain in people.iterator():
        for alias_name in alias_names(name, ascii, ascii_short, plain):
            if (pk, alias_name) not in existing:
                missing.append(Alias(person_id=pk, name=alias_name))
    Alias.objects.bulk_create(missing, batch_size=1000)


class Migration(migrations.Migration):
    dependencies = [
        ("person", "0006_personuuid"),
    ]

    operations = [
        migrations.RunPython(remove_duplicate_aliases, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="alias",
            constraint=models.UniqueConstraint(
                fields=("person", "name"), name="unique_alias_name_per_person"
            ),
        ),
        migrations.RunPython(add_missing_aliases, migrations.RunPython.noop),
    ]
