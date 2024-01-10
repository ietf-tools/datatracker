# Copyright The IETF Trust 2023, All Rights Reserved

from django.conf import settings
from django.db import migrations
from django.db.models import Value
from django.db.models.functions import Replace


def forward(apps, schema_editor):
    Group = apps.get_model("group", "Group")
    old_pattern = f"{settings.MAILING_LIST_ARCHIVE_URL}/arch/search/?email_list="
    new_pattern = f"{settings.MAILING_LIST_ARCHIVE_URL}/arch/browse/"

    Group.objects.filter(list_archive__startswith=old_pattern).update(
        list_archive=Replace("list_archive", Value(old_pattern), Value(new_pattern))
    )


class Migration(migrations.Migration):
    dependencies = [
        ("group", "0003_iabworkshops"),
    ]

    operations = [migrations.RunPython(forward)]
