# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import ietf.person.models


def forward(apps, schema_editor):
    Person = apps.get_model("person", "Person")
    PersonUUID = apps.get_model("person", "PersonUUID")
    # uuid and time come from the field defaults
    PersonUUID.objects.bulk_create(
        [PersonUUID(person=person, primary=True) for person in Person.objects.all()],
        batch_size=1000,
    )


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
                ("primary", models.BooleanField(default=False)),
                (
                    "time",
                    models.DateTimeField(
                        default=django.utils.timezone.now, editable=False
                    ),
                ),
                (
                    "person",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="uuids",
                        to="person.person",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="personuuid",
            constraint=models.UniqueConstraint(
                condition=models.Q(("primary", True)),
                fields=("person",),
                name="unique_primary_uuid_per_person",
            ),
        ),
        migrations.RunPython(forward, reverse),
    ]
