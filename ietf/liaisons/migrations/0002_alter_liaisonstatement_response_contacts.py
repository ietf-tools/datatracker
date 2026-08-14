# Copyright The IETF Trust 2025, All Rights Reserved

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("liaisons", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="liaisonstatement",
            name="response_contacts",
            field=models.TextField(
                blank=True, help_text="Where to send a response", max_length=1024
            ),
        ),
    ]
