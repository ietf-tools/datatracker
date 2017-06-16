# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('person', '0004_auto_20150308_0440'),
        ('doc', '0010_auto_20150930_0251'),
        ('group', '0006_auto_20150718_0509'),
        ('community', '0002_auto_20141222_1749'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Rule',
            new_name='SearchRule',
        ),
        migrations.RemoveField(
            model_name='displayconfiguration',
            name='community_list',
        ),
        migrations.DeleteModel(
            name='DisplayConfiguration',
        ),
        migrations.RemoveField(
            model_name='documentchangedates',
            name='document',
        ),
        migrations.DeleteModel(
            name='DocumentChangeDates',
        ),
        migrations.RemoveField(
            model_name='expectedchange',
            name='community_list',
        ),
        migrations.RemoveField(
            model_name='expectedchange',
            name='document',
        ),
        migrations.DeleteModel(
            name='ExpectedChange',
        ),
        migrations.RemoveField(
            model_name='listnotification',
            name='event',
        ),
        migrations.DeleteModel(
            name='ListNotification',
        ),
        migrations.RemoveField(
            model_name='searchrule',
            name='cached_ids',
        ),
        migrations.RenameField(
            model_name='communitylist',
            old_name='added_ids',
            new_name='added_docs',
        ),
        migrations.RemoveField(
            model_name='communitylist',
            name='cached',
        ),
        migrations.RemoveField(
            model_name='communitylist',
            name='secret',
        ),
        migrations.AddField(
            model_name='searchrule',
            name='group',
            field=models.ForeignKey(blank=True, to='group.Group', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='searchrule',
            name='person',
            field=models.ForeignKey(blank=True, to='person.Person', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='searchrule',
            name='state',
            field=models.ForeignKey(blank=True, to='doc.State', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='searchrule',
            name='text',
            field=models.CharField(default=b'', max_length=255, verbose_name=b'Text/RegExp', blank=True),
            preserve_default=True,
        ),
        migrations.RemoveField(
            model_name='searchrule',
            name='last_updated',
        ),
        migrations.AlterField(
            model_name='searchrule',
            name='rule_type',
            field=models.CharField(max_length=30, choices=[(b'group', b'All I-Ds associated with a particular group'), (b'area', b'All I-Ds associated with all groups in a particular Area'), (b'group_rfc', b'All RFCs associated with a particular group'), (b'area_rfc', b'All RFCs associated with all groups in a particular Area'), (b'state_iab', b'All I-Ds that are in a particular IAB state'), (b'state_iana', b'All I-Ds that are in a particular IANA state'), (b'state_iesg', b'All I-Ds that are in a particular IESG state'), (b'state_irtf', b'All I-Ds that are in a particular IRTF state'), (b'state_ise', b'All I-Ds that are in a particular ISE state'), (b'state_rfceditor', b'All I-Ds that are in a particular RFC Editor state'), (b'state_ietf', b'All I-Ds that are in a particular Working Group state'), (b'author', b'All I-Ds with a particular author'), (b'author_rfc', b'All RFCs with a particular author'), (b'ad', b'All I-Ds with a particular responsible AD'), (b'shepherd', b'All I-Ds with a particular document shepherd'), (b'name_contains', b'All I-Ds with particular text/regular expression in the name')]),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='searchrule',
            unique_together=set([]),
        ),
        migrations.AddField(
            model_name='emailsubscription',
            name='notify_on',
            field=models.CharField(default=b'all', max_length=30, choices=[(b'all', b'All changes'), (b'significant', b'Only significant state changes')]),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='searchrule',
            name='name_contains_index',
            field=models.ManyToManyField(to='doc.Document'),
            preserve_default=True,
        ),
    ]
