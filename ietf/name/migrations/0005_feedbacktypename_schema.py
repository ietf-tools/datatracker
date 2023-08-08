# Copyright The IETF Trust 2023, All Rights Reserved

from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ("name", "0004_statements"),
    ]

    operations = [
        migrations.AddField(
            model_name="FeedbackTypeName",
            name="legend",
            field=models.CharField(
                default="",
                help_text="One-character legend for feedback classification form",
                max_length=1,
            ),
        ),
    ]
