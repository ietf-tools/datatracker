# Copyright The IETF Trust 2025, All Rights Reserved

from django.db import migrations, models
import ietf.meeting.models
import ietf.utils.storage


class Migration(migrations.Migration):
    dependencies = [
        ("meeting", "0013_correct_reg_checkedin"),
    ]

    operations = [
        migrations.AlterField(
            model_name="floorplan",
            name="image",
            field=models.ImageField(
                default=None,
                storage=ietf.utils.storage.BlobShadowFileSystemStorage(
                    kind="", location=None
                ),
                upload_to=ietf.meeting.models.floorplan_path,
            ),
        ),
    ]
