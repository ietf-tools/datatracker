# Copyright The IETF Trust 2026, All Rights Reserved

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("meeting", "0019_slidesubmission_resolved"),
    ]

    operations = [
        migrations.AlterField(
            model_name="slidesubmission",
            name="time",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
