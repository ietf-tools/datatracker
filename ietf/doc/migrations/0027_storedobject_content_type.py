# Copyright The IETF Trust 2025, All Rights Reserved

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("doc", "0026_storedobject_committed"),
    ]

    operations = [
        migrations.AddField(
            model_name="storedobject",
            name="content_type",
            field=models.CharField(
                blank=True,
                help_text="content-type header value for the stored object",
                max_length=1024,
            ),
        ),
    ]
