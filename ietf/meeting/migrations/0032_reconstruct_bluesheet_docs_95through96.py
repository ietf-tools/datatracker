# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os

import debug         # pyflakes:ignore

from django.db import migrations
from django.conf import settings


def official_time(session):
    return session.timeslotassignments.filter(schedule=session.meeting.agenda).first()

def forward(apps, schema_editor):
    Document = apps.get_model('doc','Document')
    NewRevisionDocEvent = apps.get_model('doc','NewRevisionDocEvent')
    State = apps.get_model('doc','State')
    Group = apps.get_model('group','Group')
    Meeting = apps.get_model('meeting', 'Meeting')

    active = State.objects.get(type_id='bluesheets',slug='active')

    print
    print "Attention: The following anomalies are expected:"
    print "There are no bluesheets for nmlrg at IETF95 or for cellar at IETF96."
    print "At IETF95, netmod and opsec have a different number of bluesheets than sessions."
    print "Please report any other warnings issued during the production migration to RjS."

    for num in [95, 96]:
        mtg = Meeting.objects.get(number=num)
        bs_path = '%s/bluesheets/'% os.path.join(settings.AGENDA_PATH,mtg.number)
        if not os.path.exists(bs_path):
            os.makedirs(bs_path)
        bs_files = os.listdir(bs_path)
        bs_acronyms = set([x[14:].split('-')[0] for x in bs_files])
        group_acronyms = set([x.group.acronym for x in mtg.session_set.filter(status_id='sched') if official_time(x) and x.group.type_id in ['wg','rg','ag'] and not x.agenda_note.lower().startswith('cancel')])

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
                          title='Bluesheets IETF%d : %s : %s' % (num,acronym,official_time(sess[n]).timeslot.time.strftime('%a %H:%M')),
                          group=group,
                          rev='00',
                          external_url=bs[n],
                      )
                doc.states.add(active)
                doc.docalias_set.create(name=doc.name)
                NewRevisionDocEvent.objects.create(doc=doc,time=doc.time,by_id=1,type='new_revision',desc='New revision available: %s'%doc.rev,rev=doc.rev)
                sess[n].sessionpresentation_set.create(document=doc,rev='00')

def reverse(apps, schema_editor):
    Document = apps.get_model('doc','Document')
    Document.objects.filter(type_id='bluesheets',sessionpresentation__session__meeting__number__in=[95,96]).exclude(group__acronym='openpgp').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0031_add_proceedings_final'),
        ('doc', '0012_auto_20160207_0537'),
        ('group','0008_auto_20160505_0523'),
    ]

    operations = [
        migrations.RunPython(forward,reverse)
    ]
