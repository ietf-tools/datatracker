# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations, models
import django.db.models.deletion
import ietf.person.models


def forward(apps, schema_editor):
    Person = apps.get_model("person", "Person")
    for person in Person.objects.all():
        person.uuids.create(person=person)


def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("person", "0005_alter_historicalperson_pronouns_selectable_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="PersonUUID",
            fields=[
                (
                    "uuid",
                    models.UUIDField(
                        default=ietf.person.models.unused_person_uuid,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "person",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="uuids",
                        to="person.person",
                    ),
                ),
            ],
        ),
        migrations.RunPython(forward, reverse),
    ]
