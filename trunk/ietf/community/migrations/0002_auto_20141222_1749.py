# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('community', '0001_initial'),
        ('doc', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='rule',
            name='cached_ids',
            field=models.ManyToManyField(to='doc.Document'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='rule',
            name='community_list',
            field=models.ForeignKey(to='community.CommunityList'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='rule',
            unique_together=set([('community_list', 'rule_type', 'value')]),
        ),
        migrations.AddField(
            model_name='listnotification',
            name='event',
            field=models.ForeignKey(to='doc.DocEvent'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='expectedchange',
            name='community_list',
            field=models.ForeignKey(to='community.CommunityList'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='expectedchange',
            name='document',
            field=models.ForeignKey(to='doc.Document'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='emailsubscription',
            name='community_list',
            field=models.ForeignKey(to='community.CommunityList'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='documentchangedates',
            name='document',
            field=models.ForeignKey(to='doc.Document'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='displayconfiguration',
            name='community_list',
            field=models.ForeignKey(to='community.CommunityList'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='communitylist',
            name='added_ids',
            field=models.ManyToManyField(to='doc.Document'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='communitylist',
            name='group',
            field=models.ForeignKey(blank=True, to='group.Group', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='communitylist',
            name='user',
            field=models.ForeignKey(blank=True, to=settings.AUTH_USER_MODEL, null=True),
            preserve_default=True,
        ),
    ]
