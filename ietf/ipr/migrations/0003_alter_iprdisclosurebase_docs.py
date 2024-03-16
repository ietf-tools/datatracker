# Copyright The IETF Trust 2023, All Rights Reserved

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("doc", "0017_delete_docalias"),
        ("ipr", "0002_iprdocrel_no_aliases"),
    ]

    operations = [
        migrations.AlterField(
            model_name="iprdisclosurebase",
            name="docs",
            field=models.ManyToManyField(through="ipr.IprDocRel", to="doc.document"),
        ),
    ]
