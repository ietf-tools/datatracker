# Copyright The IETF Trust 2024, All Rights Reserved
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ipr", "0003_alter_iprdisclosurebase_docs"),
    ]

    operations = [
        migrations.AddField(
            model_name="holderiprdisclosure",
            name="is_blanket_disclosure",
            field=models.BooleanField(default=False),
        ),
    ]
