# Copyright The IETF Trust 2019-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('name', '0006_adjust_statenames'),
    ]

    operations = [
        migrations.RunSQL("ALTER TABLE doc_ballottype_positions MODIFY ballotpositionname_id varchar(32);", ""),
        migrations.RunSQL("ALTER TABLE doc_dochistory_tags MODIFY doctagname_id varchar(32);", ""),
        migrations.RunSQL("ALTER TABLE group_group_unused_tags MODIFY doctagname_id varchar(32);", ""),
        migrations.RunSQL("ALTER TABLE group_grouphistory_unused_tags MODIFY doctagname_id varchar(32);", ""),
    ]
