# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('name', '0015_insert_review_name_data'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='ballotpositionname',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AlterModelOptions(
            name='constraintname',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AlterModelOptions(
            name='dbtemplatetypename',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AlterModelOptions(
            name='docrelationshipname',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AlterModelOptions(
            name='docremindertypename',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AlterModelOptions(
            name='doctagname',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AlterModelOptions(
            name='doctypename',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AlterModelOptions(
            name='draftsubmissionstatename',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AlterModelOptions(
            name='feedbacktypename',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AlterModelOptions(
            name='groupmilestonestatename',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AlterModelOptions(
            name='groupstatename',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AlterModelOptions(
            name='grouptypename',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AlterModelOptions(
            name='intendedstdlevelname',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AlterModelOptions(
            name='iprdisclosurestatename',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AlterModelOptions(
            name='ipreventtypename',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AlterModelOptions(
            name='iprlicensetypename',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AlterModelOptions(
            name='liaisonstatementeventtypename',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AlterModelOptions(
            name='liaisonstatementpurposename',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AlterModelOptions(
            name='liaisonstatementstate',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AlterModelOptions(
            name='liaisonstatementtagname',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AlterModelOptions(
            name='meetingtypename',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AlterModelOptions(
            name='nomineepositionstatename',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AlterModelOptions(
            name='reviewrequeststatename',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AlterModelOptions(
            name='reviewresultname',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AlterModelOptions(
            name='reviewtypename',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AlterModelOptions(
            name='rolename',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AlterModelOptions(
            name='roomresourcename',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AlterModelOptions(
            name='sessionstatusname',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AlterModelOptions(
            name='stdlevelname',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AlterModelOptions(
            name='streamname',
            options={'ordering': ['order', 'name']},
        ),
        migrations.AlterModelOptions(
            name='timeslottypename',
            options={'ordering': ['order', 'name']},
        ),
    ]
