# Copyright The IETF Trust 2025, All Rights Reserved

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("doc", "0025_storedobject_storedobject_unique_name_per_store"),
    ]

    operations = [
        migrations.AddField(
            model_name="storedobject",
            name="committed",
            field=models.DateTimeField(null=True),
        ),
    ]
