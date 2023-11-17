# Copyright The IETF Trust 2023, All Rights Reserved

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("ipr", "0002_iprdocrel_no_aliases"),
        ("doc", "0016_relate_hist_no_aliases"),
    ]

    operations = [
        migrations.DeleteModel(
            name="DocAlias",
        ),
    ]
