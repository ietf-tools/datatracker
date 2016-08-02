# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os

from django.db import migrations
from django.conf import settings


def official_time(session):
    return session.timeslotassignments.filter(schedule=session.meeting.agenda).first()

def forward(apps, schema_editor):
    Document = apps.get_model('doc','Document')
    State = apps.get_model('doc','State')
    Group = apps.get_model('group','Group')
    Meeting = apps.get_model('meeting', 'Meeting')

    active = State.objects.get(type_id='bluesheets',slug='active')

    for num in [95, 96]:
        mtg = Meeting.objects.get(number=num)
        bs_path = '%s/bluesheets/'% os.path.join(settings.AGENDA_PATH,mtg.number)
        bs_files = os.listdir(bs_path)
        bs_acronyms = set([x[14:-7] for x in bs_files])
        group_acronyms = set([x.group.acronym for x in mtg.session_set.all() if official_time(x) and x.group.type_id in ['wg','rg','ag'] and not x.agenda_note.lower().startswith('cancel')])

        if  bs_acronyms-group_acronyms:
            print "Warning IETF%s : groups that have bluesheets but did not appear to meet: %s"%(num,list(bs_acronyms-group_acronyms))
        if  group_acronyms-bs_acronyms:
            print "Warning IETF%s : groups that appeared to meet but have no bluesheets: %s"%(num,list(group_acronyms-bs_acronyms))

        for acronym in group_acronyms & bs_acronyms:
            group = Group.objects.get(acronym=acronym)
            bs = sorted([x for x in bs_files if '-%s-'%acronym in x])
            bs_count = len(bs)
            sess = sorted([ x for x in mtg.session_set.filter(group__acronym=acronym) if not x.agenda_note.lower().startswith('cancel')],
                          key = lambda x: official_time(x).timeslot.time)
            sess_count = len(sess)
            if bs_count != sess_count:
                print "Warning IETF%s: %s : different number of bluesheets (%d) than sessions (%d)"%(num,acronym,bs_count,sess_count)
            numdocs = min(bs_count,sess_count)
            for n in range(numdocs):
                doc = Document.objects.create(
                          name=bs[n][:-4],
                          type_id='bluesheets',
                          title='Bluesheets IETF%d : %s : %s ' % (num,acronym,official_time(sess[n]).timeslot.time.strftime('%a %H:%M')),
                          group=group,
                          rev='00',
                          external_url=bs[n],
                      )
                doc.states.add(active)
                sess[n].sessionpresentation_set.create(document=doc,rev='00')

def reverse(apps, schema_editor):
    Document = apps.get_model('doc','Document')
    Document.objects.filter(type_id='bluesheets',sessionpresentation__session__meeting__number_in=[95,96]).exclude(group__acronym='openpgp').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0028_add_audio_stream_data'),
        ('doc', '0012_auto_20160207_0537'),
        ('group','0008_auto_20160505_0523'),
    ]

    operations = [
        migrations.RunPython(forward,reverse)
    ]
