# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0003_auto_20150304_0743'),
    ]

    operations = [
        migrations.AlterField(
            model_name='group',
            name='unused_states',
            field=models.ManyToManyField(help_text=b'Document states that have been disabled for the group.', to='doc.State', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='group',
            name='unused_tags',
            field=models.ManyToManyField(help_text=b'Document tags that have been disabled for the group.', to='name.DocTagName', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='grouphistory',
            name='unused_states',
            field=models.ManyToManyField(help_text=b'Document states that have been disabled for the group.', to='doc.State', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='grouphistory',
            name='unused_tags',
            field=models.ManyToManyField(help_text=b'Document tags that have been disabled for the group.', to='name.DocTagName', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='groupmilestone',
            name='resolved',
            field=models.CharField(help_text=b'Explanation of why milestone is resolved (usually "Done"), or empty if still due.', max_length=50, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='groupmilestonehistory',
            name='resolved',
            field=models.CharField(help_text=b'Explanation of why milestone is resolved (usually "Done"), or empty if still due.', max_length=50, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='role',
            name='email',
            field=models.ForeignKey(help_text=b'Email address used by person for this role.', to='person.Email'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='rolehistory',
            name='email',
            field=models.ForeignKey(help_text=b'Email address used by person for this role.', to='person.Email'),
            preserve_default=True,
        ),
    ]
