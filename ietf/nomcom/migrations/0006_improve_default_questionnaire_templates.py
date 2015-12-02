# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


def set_new_template_content(apps, schema_editor):
    DBTemplate = apps.get_model('dbtemplate','DBTemplate')

    h = DBTemplate.objects.get(path='/nomcom/defaults/position/header_questionnaire.txt')
    h.content = """Hi $nominee, this is the questionnaire for the position $position.
Please follow the directions in the questionnaire closely - you may see
that some changes have been made from previous years, so please take note.

We look forward to reading your questionnaire response!  If you have any
administrative questions, please send mail to nomcom-chair@ietf.org.

You may have received this questionnaire before accepting the nomination.  A
separate message, sent at the time of nomination, provides instructions for
indicating whether you accept or decline. If you have not completed those
steps, please do so as soon as possible, or contact the nomcom chair.

Thank you!


"""
    h.save()

    h = DBTemplate.objects.get(path='/nomcom/defaults/position/questionnaire.txt')
    h.content = """NomCom Chair: Replace this content with the appropriate questionnaire for the position $position.
"""
    h.save()

def revert_to_old_template_content(apps, schema_editor):
    DBTemplate = apps.get_model('dbtemplate','DBTemplate')

    h = DBTemplate.objects.get(path='/nomcom/defaults/position/header_questionnaire.txt')
    h.content = """Hi $nominee, this is the questionnaire for the position $position.
Please follow the directions in the questionnaire closely - you may see
that some changes have been made from previous years, so please take note.

We look forward to reading your questionnaire response!  If you have any
administrative questions, please send mail to nomcom-chair@ietf.org.

Thank you!


"""
    h.save()

    h = DBTemplate.objects.get(path='/nomcom/defaults/position/questionnaire.txt')
    h.content = """Enter here the questionnaire for the position $position:

Questionnaire

"""
    h.save()

class Migration(migrations.Migration):

    dependencies = [
        ('nomcom', '0005_remove_position_incumbent'),
    ]

    operations = [
        migrations.RunPython(set_new_template_content,revert_to_old_template_content)
    ]
