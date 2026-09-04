# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations, models
import ietf.api.models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="KnownApiEndpoint",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(help_text="API endpoint name", max_length=1000),
                ),
                (
                    "enabled",
                    models.BooleanField(
                        default=True,
                        help_text="Are bearers of tokens for this endpoint allowed access?",
                    ),
                ),
            ],
            options={
                "verbose_name": "API endpoint",
            },
        ),
        migrations.CreateModel(
            name="AppApiToken",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "token",
                    models.CharField(
                        default=ietf.api.models._generate_token,
                        help_text="API token",
                        max_length=128,
                        unique=True,
                    ),
                ),
                (
                    "client",
                    models.CharField(
                        help_text="Brief description of client using the token",
                        max_length=255,
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        help_text="Extended description of the purpose of the token",
                    ),
                ),
                (
                    "enabled",
                    models.BooleanField(
                        default=True,
                        help_text="Is bearer of this token allowed access?",
                    ),
                ),
                (
                    "endpoints",
                    models.ManyToManyField(
                        related_name="tokens", to="api.knownapiendpoint"
                    ),
                ),
            ],
            options={
                "verbose_name": "API token",
            },
        ),
    ]
