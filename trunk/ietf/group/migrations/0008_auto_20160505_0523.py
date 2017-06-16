# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0007_concluded_group_cleanup'),
    ]

    operations = [
        migrations.AlterField(
            model_name='groupevent',
            name='type',
            field=models.CharField(max_length=50, choices=[(b'changed_state', b'Changed state'), (b'added_comment', b'Added comment'), (b'info_changed', b'Changed metadata'), (b'requested_close', b'Requested closing group'), (b'changed_milestone', b'Changed milestone'), (b'sent_notification', b'Sent notification'), (b'status_update', b'Status update')]),
            preserve_default=True,
        ),
    ]
