# Copyright The IETF Trust 2025, All Rights Reserved

from django.db import migrations, models
import ietf.meeting.models
import ietf.utils.fields
import ietf.utils.storage
import ietf.utils.validators


class Migration(migrations.Migration):

    dependencies = [
        ("meeting", "0009_session_meetecho_recording_name"),
    ]

    operations = [
        migrations.AlterField(
            model_name="floorplan",
            name="image",
            field=models.ImageField(
                blank=True,
                default=None,
                storage=ietf.utils.storage.BlobShadowFileSystemStorage(
                    kind="", location=None
                ),
                upload_to=ietf.meeting.models.floorplan_path,
            ),
        ),
        migrations.AlterField(
            model_name="meetinghost",
            name="logo",
            field=ietf.utils.fields.MissingOkImageField(
                height_field="logo_height",
                storage=ietf.utils.storage.BlobShadowFileSystemStorage(
                    kind="", location=None
                ),
                upload_to=ietf.meeting.models._host_upload_path,
                validators=[
                    ietf.utils.validators.MaxImageSizeValidator(400, 400),
                    ietf.utils.validators.WrappedValidator(
                        ietf.utils.validators.validate_file_size, True
                    ),
                    ietf.utils.validators.WrappedValidator(
                        ietf.utils.validators.validate_file_extension,
                        [".png", ".jpg", ".jpeg"],
                    ),
                    ietf.utils.validators.WrappedValidator(
                        ietf.utils.validators.validate_mime_type,
                        ["image/jpeg", "image/png"],
                        True,
                    ),
                ],
                width_field="logo_width",
            ),
        ),
    ]
