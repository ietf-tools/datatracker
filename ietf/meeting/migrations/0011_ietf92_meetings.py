# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import datetime
from django.db import migrations


def backfill_92_other_meetings(apps, schema_editor):

        Meeting          = apps.get_model('meeting', 'Meeting')
        Schedule         = apps.get_model('meeting', 'Schedule')
        ScheduledSession = apps.get_model('meeting', 'ScheduledSession')
        Room             = apps.get_model('meeting', 'Room')
        Session          = apps.get_model('meeting', 'Session')
        Group            = apps.get_model('group',   'Group')
        Person           = apps.get_model('person',  'Person')

        ietf92 = Meeting.objects.filter(number=92).first()

        if not ietf92:
            print "IETF92 not found, no data changed"
        else:

            # Clear out one orphaned ill-configured Session object
            qs = Session.objects.filter(meeting__number=92,name__icontains='beverage break').exclude(type_id='break') 
            if qs.count()==1:
                qs.delete()

            agenda92 = Schedule.objects.get(meeting=ietf92,pk=ietf92.agenda.pk)

            map_existing = {
                            'Regency Ballroom':     'Lounge',
                            'Garden Terrace Level': 'Meet and Greet',
                            'Royal':                'Breakout 1',
                            'Continental':          'Breakout 2',
                            'Far East':             'Breakout 3',
                            'Oak ':                 'Breakout 4',
                            'Parisian':             'Breakout 5',
                            'Venetian':             'Breakout 6',
                            'Gold':                 'Breakout 7',
                            'International':        'Breakout 8',
                            'Brasserie':            'Terminal Room',
                            'State':                'Office #3 (Secretariat Office)',
                            'French':               'Meeting Room #2 (IESG Meeting Room)',
                           }

            for name,functional_name in map_existing.items():
                Room.objects.filter(meeting__number=92,name=name).update(functional_name=functional_name)

            regency       = Room.objects.get(meeting=ietf92,name='Regency Ballroom')
            garden        = Room.objects.get(meeting=ietf92,name='Garden Terrace Level')
            royal         = Room.objects.get(meeting=ietf92,name='Royal')
            continental   = Room.objects.get(meeting=ietf92,name='Continental')
            far_east      = Room.objects.get(meeting=ietf92,name='Far East')
            oak           = Room.objects.get(meeting=ietf92,name='Oak ')
            #parisian      = Room.objects.get(meeting=ietf92,name='Parisian')
            #venetian      = Room.objects.get(meeting=ietf92,name='Venetian')
            #gold          = Room.objects.get(meeting=ietf92,name='Gold')
            #international = Room.objects.get(meeting=ietf92,name='International')
            brasserie     = Room.objects.get(meeting=ietf92,name='Brasserie')
            state         = Room.objects.get(meeting=ietf92,name='State')
            #french        = Room.objects.get(meeting=ietf92,name='French')

            executive     = Room.objects.create(meeting=ietf92,name='Executive',functional_name='Meeting Room #4 (IAOC/IAD)',capacity=20)
            regency_foyer = Room.objects.create(meeting=ietf92,name='Regency Foyer',functional_name='Registration',capacity=1200)
            florentine    = Room.objects.create(meeting=ietf92,name='Florentine',functional_name='Meeting Room #1 (IAB)', capacity=40)
            pavilion      = Room.objects.create(meeting=ietf92,name='Pavilion',functional_name='Meeting Room #6', capacity=80)
            terrace       = Room.objects.create(meeting=ietf92,name='Terrace',functional_name='Meeting Room #7', capacity=80)
            panorama      = Room.objects.create(meeting=ietf92,name='Panorama',functional_name='Companion Reception', capacity=200)

            regency.session_types.add('offagenda')
            pavilion.session_types.add('offagenda')
            pavilion.session_types.add('lead')
            garden.session_types.add('lead')
            panorama.session_types.add('offagenda')
            executive.session_types.add('lead')
            executive.session_types.add('offagenda')
            regency_foyer.session_types.add('offagenda')
            oak.session_types.add('offagenda')
            continental.session_types.add('offagenda')
            state.session_types.add('offagenda')
            florentine.session_types.add('offagenda')
            terrace.session_types.add('lead')
            terrace.session_types.add('offagenda')
            far_east.session_types.add('offagenda')
            brasserie.session_types.add('offagenda')
            royal.session_types.add('offagenda') 
            
            iesg = Group.objects.get(acronym='iesg')
            iab = Group.objects.get(acronym='iab')
            iaoc = Group.objects.get(acronym='iaoc')
            secr = Group.objects.get(acronym='secretariat')
    
            system = Person.objects.get(name='(System)')
    
            for d, h, m, duration, type_id,  groups, room, slotname, label in [
                    ( 20, 13,  0,  480, 'offagenda', [secr],     brasserie,       'Setup', 'Hackathon: Setup'),
                    ( 20,  8,  0,  540, 'offagenda', [secr],     executive,       'Meeting', 'DNS OARC Meeting'),
                    ( 21,  8,  0,  540, 'offagenda', [secr],     executive,       'Meeting', 'DNS OARC Meeting'),
                    ( 22, 12,  0,  720, 'offagenda', [secr],     brasserie,       'Terminal Room', 'Terminal Room Open to Attendees'),
                    ( 22, 11,  0,  480, 'offagenda', [secr],     regency_foyer,   'T-Shirt Distribution', 'T-shirt Distribution'),
                    ( 22, 19,  0,  120, 'offagenda', [secr],     state,           'Meeting', 'CJK Generation Panel coordination informal meeting'),
                    ( 22, 19,  0,  120, 'offagenda', [iab],      florentine,      'Meeting', 'IAB PrivSec program'),
                    ( 22,  8, 30,   90, 'lead',      [iesg],     pavilion,        'Breakfast', None),
                    ( 22,  9,  0,  150, 'lead',      [iesg],     pavilion,        'Meeting', None),
                    ( 22, 11, 30,  150, 'lead',      [iab],      pavilion,        'Lunch', 'IAB Lunch with the IESG'),
                    ( 22, 11, 30,  150, 'lead',      [iesg],     pavilion,        'Lunch', 'IESG Lunch with the IAB'),
                    ( 22, 14,  0,  180, 'lead',      [iab],      pavilion,        'Meeting', None),
                    ( 22,  9,  0,  480, 'offagenda', [secr],     terrace,         'Meeting', 'RootOPS'),
                    ( 22, 16, 30,   60, 'offagenda', [secr],     panorama,        'Reception', "Companion's Reception"), # Should this appear on agenda?
                    ( 22, 21,  0,  180, 'lead',      [secr],     garden,          'Gathering', 'AMS/IESG/IAB/IAOC Gathering'),
                    ( 22,  9,  0,  480, 'offagenda', [secr],     royal,           'ICNRG', 'ICNRG'),
                    ( 22, 19,  0,  180, 'offagenda', [secr],     royal,           'Meeting', 'Huawei'),
                    ( 22, 12, 30,  240, 'offagenda', [secr],     continental,     'Meeting', 'Verisign ROA Workshop'),
                    ( 22, 15, 15,  165, 'offagenda', [secr],     far_east,        'Meeting', 'RSSAC'),
                    ( 22,  9,  0,  150, 'offagenda', [secr],     oak,             'Meeting', 'Ericsson'),
                    ( 23,  0,  0, 1440, 'offagenda', [secr],     brasserie,       'Terminal Room', 'Terminal Room Open to Attendees'),
                    ( 23,  8,  0,  600, 'offagenda', [secr],     regency_foyer,   'T-Shirt Distribution', 'T-shirt Distribution'),
                    ( 23,  0,  0, 1440, 'offagenda', [secr],     regency,         'Lounge', 'Lounge'),
                    ( 23, 11, 30,  180, 'offagenda', [secr],     executive,       'Lunch', 'ICANN Lunch'),
                    ( 23,  7,  0,  120, 'lead',      [iesg],     pavilion,        'Breakfast', 'IESG Breakfast with the IAB'),
                    ( 23,  7,  0,  120, 'lead',      [iab],      pavilion,        'Breakfast', 'IAB Breakfast with the IESG'),
                    ( 23, 11, 30,   90, 'offagenda', [secr],     pavilion,        'Meeting', 'OPS Directorate Meeting'),
                    ( 23, 19,  0,  120, 'offagenda', [secr],     pavilion,        'Meeting', 'ACE'),
                    ( 23,  7, 30,   90, 'offagenda', [secr],     terrace,         'Meeting', 'NRO ECG'),
                    ( 23, 11, 30,   90, 'offagenda', [secr],     terrace,         'Meeting', 'IETF/3GPP Meeting'),
                    ( 23, 19,  0,  120, 'offagenda', [secr],     terrace,         'Meeting', 'I2NSF'),
                    ( 23, 18, 50,   60, 'offagenda', [secr],     royal,           'Meeting', 'Captive Portal Bar BOF'),
                    ( 24,  0,  0, 1440, 'offagenda', [secr],     brasserie,       'Terminal Room', 'Terminal Room Open to Attendees'),
                    ( 24,  8,  0,  600, 'offagenda', [secr],     regency_foyer,   'T-Shirt Distribution', 'T-shirt Distribution'),
                    ( 24,  0,  0, 1440, 'offagenda', [secr],     regency,         'Lounge', 'Lounge'),
                    ( 24, 11, 30,   90, 'offagenda', [secr],     state,           'Meeting', 'HIAPS'),
                    ( 24, 16, 30,  120, 'offagenda', [secr],     state,           'Meeting', 'PDF Draft Review'),
                    ( 24,  7,  0,  120, 'lead',      [iesg],     pavilion,        'Breakfast', None),
                    ( 24, 11, 30,   90, 'offagenda', [secr],     pavilion,        'Meeting', 'SECdir Meeting'),
                    ( 24,  7,  0,  120, 'lead',      [iab],      terrace,         'Breakfast', None),
                    ( 24,  9,  0,  120, 'offagenda', [secr],     terrace,         'Meeting', 'ICNN DRZK Design Team'),
                    ( 24, 11, 30,   90, 'offagenda', [secr],     terrace,         'Lunch', 'RSAG/ISEB Lunch'),
                    ( 24, 13,  0,  120, 'offagenda', [secr],     terrace,         'Meeting', 'SACM'),
                    ( 24, 15,  0,   90, 'offagenda', [secr],     terrace,         'Meeting', 'RSOC Meeting'),
                    ( 24, 17, 30,   60, 'offagenda', [secr],     terrace,         'Meeting', 'SACM'),
                    ( 24, 11, 30,   90, 'offagenda', [secr],     royal,           'Meeting', 'IoT Directorate'),
                    ( 25,  0,  0, 1440, 'offagenda', [secr],     brasserie,       'Terminal Room', 'Terminal Room Open to Attendees'),
                    ( 25,  8,  0,  600, 'offagenda', [secr],     regency_foyer,   'T-Shirt Distribution', 'T-shirt Distribution'),
                    ( 25,  0,  0, 1440, 'offagenda', [secr],     regency,         'Lounge', 'Lounge'),
                    ( 25,  8,  0,   60, 'offagenda', [secr],     state,           'Meeting', 'SFC Control Plane Offline Discussion'),
                    ( 25, 19,  0,  240, 'offagenda', [secr],     state,           'Meeting', 'WWG'),
                    ( 25,  8,  0,   60, 'offagenda', [secr],     florentine,      'Meeting', 'IAB Name Resolution'),
                    ( 25,  6, 45,  135, 'lead',      [iaoc],     executive,       'Breakfast', None),
                    ( 25, 11, 30,   90, 'offagenda', [secr],     pavilion,        'Meeting', 'RMCAT'),
                    ( 25, 19,  0,  120, 'offagenda', [secr],     pavilion,        'Meeting', 'I2NSF'),
                    ( 25,  8,  0,   60, 'offagenda', [secr],     terrace,         'Meeting', 'IETF/IEEE 802 Coordination'),
                    ( 25, 11, 30,   90, 'offagenda', [secr],     terrace,         'Lunch',   'RFC Editor Lunch'),
                    ( 25, 19, 30,  120, 'offagenda', [secr],     terrace,         'Dinner',  'SSAC Dinner'),
                    ( 26,  0,  0, 1440, 'offagenda', [secr],     brasserie,       'Terminal Room', 'Terminal Room Open to Attendees'),
                    ( 26,  8,  0,  600, 'offagenda', [secr],     regency_foyer,   'T-Shirt Distribution', 'T-shirt Distribution'),
                    ( 26,  0,  0, 1440, 'offagenda', [secr],     regency,         'Lounge', 'Lounge'),
                    ( 26,  7, 30,   90, 'offagenda', [secr],     state,           'Breakfast', 'EDU Team Breakfast'),
                    ( 26, 14,  0,  120, 'offagenda', [secr],     state,           'Meeting',   'JJB'),
                    ( 26, 11, 30,   90, 'offagenda', [secr],     florentine,      'Meeting',   'IAB Liaison Oversight'),
                    ( 26, 18,  0,  150, 'offagenda', [secr],     pavilion,        'Meeting',   '6LO Security Discussion'),
                    ( 26,  7,  0,  120, 'lead',      [iab],      terrace,         'Breakfast', None),
                    ( 26, 17, 40,   60, 'offagenda', [secr],     terrace,         'Meeting', 'SACM'),
                    ( 26, 19, 30,  150, 'offagenda', [secr],     royal,           'Meeting', 'Lavabit'),
                    ( 27,  0,  0,  900, 'offagenda', [secr],     brasserie,       'Terminal Room', 'Terminal Room Open to Attendees'),
                    ( 27,  7, 30,   90, 'offagenda', [secr],     executive,       'Meeting', 'Post-Con with Ray'),
                    ( 27,  7, 30,   75, 'offagenda', [secr],     state,           'Breakfast', 'Gen-art'),
                    ( 27, 13, 30,   90, 'lead',      [iab],      pavilion,        'Lunch', 'IAB Lunch with the IESG'),
                    ( 27, 13, 30,   90, 'lead',      [iesg],     pavilion,        'Lunch', 'IESG Lunch with the IAB'),
                   ]:

                ts = ietf92.timeslot_set.create(type_id=type_id, name=slotname, 
                                                time=datetime.datetime(2015,3,d,h,m,0),
                                                duration=datetime.timedelta(minutes=duration), 
                                                location=room,show_location=(type_id not in ['lead','offagenda']))
                for group in groups:
                    session = ietf92.session_set.create(name= label or "%s %s"%(group.acronym.upper(),slotname),
                                                        group=group, attendees=25,
                                                        requested=datetime.datetime(2014,11,1,0,0,0),
                                                        requested_by=system, status_id='sched',type_id=type_id)
                    ScheduledSession.objects.create(schedule=agenda92, timeslot=ts, session=session)


class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0010_auto_20150501_0732'),
        ('name',    '0004_auto_20150318_1140'),
        ('group',   '0004_auto_20150430_0847'),
        ('person',  '0004_auto_20150308_0440'),
    ]

    operations = [
        migrations.RunPython(backfill_92_other_meetings)
    ]
