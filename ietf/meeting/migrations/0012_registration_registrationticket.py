# Copyright The IETF Trust 2025, All Rights Reserved

from django.db import migrations, models
import django.db.models.deletion
import ietf.utils.models


class Migration(migrations.Migration):

    dependencies = [
        ("name", "0017_populate_new_reg_names"),
        ("person", "0004_alter_person_photo_alter_person_photo_thumb"),
        ("meeting", "0011_alter_slidesubmission_doc"),
    ]

    operations = [
        migrations.CreateModel(
            name="Registration",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("first_name", models.CharField(max_length=255)),
                ("last_name", models.CharField(max_length=255)),
                ("affiliation", models.CharField(blank=True, max_length=255)),
                ("country_code", models.CharField(max_length=2)),
                ("email", models.EmailField(blank=True, max_length=254, null=True)),
                ("attended", models.BooleanField(default=False)),
                ("checkedin", models.BooleanField(default=False)),
                (
                    "meeting",
                    ietf.utils.models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="meeting.meeting",
                    ),
                ),
                (
                    "person",
                    ietf.utils.models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="person.person",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="RegistrationTicket",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "attendance_type",
                    ietf.utils.models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="name.attendancetypename",
                    ),
                ),
                (
                    "registration",
                    ietf.utils.models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tickets",
                        to="meeting.registration",
                    ),
                ),
                (
                    "ticket_type",
                    ietf.utils.models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="name.registrationtickettypename",
                    ),
                ),
            ],
        ),
    ]
