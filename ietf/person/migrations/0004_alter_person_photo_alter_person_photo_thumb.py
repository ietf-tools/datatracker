# Copyright The IETF Trust 2025, All Rights Reserved

from django.db import migrations, models
import ietf.utils.storage


class Migration(migrations.Migration):

    dependencies = [
        ("person", "0003_alter_personalapikey_endpoint"),
    ]

    operations = [
        migrations.AlterField(
            model_name="person",
            name="photo",
            field=models.ImageField(
                blank=True,
                default=None,
                storage=ietf.utils.storage.BlobShadowFileSystemStorage(
                    kind="", location=None
                ),
                upload_to="photo",
            ),
        ),
        migrations.AlterField(
            model_name="person",
            name="photo_thumb",
            field=models.ImageField(
                blank=True,
                default=None,
                storage=ietf.utils.storage.BlobShadowFileSystemStorage(
                    kind="", location=None
                ),
                upload_to="photo",
            ),
        ),
    ]
