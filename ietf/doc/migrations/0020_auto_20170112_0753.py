# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('name', '0017_formallanguagename'),
        ('doc', '0019_auto_20161207_1036'),
    ]

    operations = [
        migrations.AddField(
            model_name='dochistory',
            name='words',
            field=models.IntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='document',
            name='words',
            field=models.IntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='dochistory',
            name='formal_languages',
            field=models.ManyToManyField(help_text=b'Formal languages used in document', to='name.FormalLanguageName', blank=True),
        ),
        migrations.AddField(
            model_name='document',
            name='formal_languages',
            field=models.ManyToManyField(help_text=b'Formal languages used in document', to='name.FormalLanguageName', blank=True),
        ),
        migrations.RemoveField(
            model_name='dochistory',
            name='authors',
        ),
        migrations.RemoveField(
            model_name='document',
            name='authors',
        ),
        migrations.AddField(
            model_name='dochistoryauthor',
            name='affiliation',
            field=models.CharField(help_text=b'Organization/company used by author for submission', max_length=100, blank=True),
        ),
        migrations.AddField(
            model_name='dochistoryauthor',
            name='country',
            field=models.CharField(blank=True, help_text=b'Country used by author for submission', max_length=255),
        ),
        migrations.RenameField(
            model_name='dochistoryauthor',
            old_name='author',
            new_name='email',
        ),
        migrations.AlterField(
            model_name='dochistoryauthor',
            name='email',
            field=models.ForeignKey(blank=True, to='person.Email', help_text=b'Email address used by author for submission', null=True),
        ),
        migrations.AddField(
            model_name='dochistoryauthor',
            name='person',
            field=models.ForeignKey(blank=True, to='person.Person', null=True),
        ),
        migrations.AddField(
            model_name='documentauthor',
            name='affiliation',
            field=models.CharField(help_text=b'Organization/company used by author for submission', max_length=100, blank=True),
        ),
        migrations.AddField(
            model_name='documentauthor',
            name='country',
            field=models.CharField(blank=True, help_text=b'Country used by author for submission', max_length=255),
        ),
        migrations.RenameField(
            model_name='documentauthor',
            old_name='author',
            new_name='email',
        ),
        migrations.AlterField(
            model_name='documentauthor',
            name='email',
            field=models.ForeignKey(blank=True, to='person.Email', help_text=b'Email address used by author for submission', null=True),
        ),
        migrations.AddField(
            model_name='documentauthor',
            name='person',
            field=models.ForeignKey(blank=True, to='person.Person', null=True),
        ),
        migrations.AlterField(
            model_name='dochistoryauthor',
            name='document',
            field=models.ForeignKey(related_name='documentauthor_set', to='doc.DocHistory'),
        ),
        migrations.AlterField(
            model_name='dochistoryauthor',
            name='order',
            field=models.IntegerField(default=1),
        ),
        migrations.RunSQL("update doc_documentauthor a inner join person_email e on a.email_id = e.address set a.person_id = e.person_id;", migrations.RunSQL.noop),
        migrations.RunSQL("update doc_dochistoryauthor a inner join person_email e on a.email_id = e.address set a.person_id = e.person_id;", migrations.RunSQL.noop),
        migrations.AlterField(
            model_name='documentauthor',
            name='person',
            field=models.ForeignKey(to='person.Person'),
        ),
        migrations.AlterField(
            model_name='dochistoryauthor',
            name='person',
            field=models.ForeignKey(to='person.Person'),
        ),
    ]
