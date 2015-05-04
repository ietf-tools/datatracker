# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import datetime
from django.db import migrations


def backfill_91_other_meetings(apps, schema_editor):

        Meeting          = apps.get_model('meeting', 'Meeting')
        Schedule         = apps.get_model('meeting', 'Schedule')
        ScheduledSession = apps.get_model('meeting', 'ScheduledSession')
        Room             = apps.get_model('meeting', 'Room')
        Group            = apps.get_model('group',   'Group')
        Person           = apps.get_model('person',  'Person')

        ietf91 = Meeting.objects.filter(number=91).first()

        if not ietf91:
            print "IETF91 not found, no data changed"
        else:
            agenda91 = Schedule.objects.get(meeting=ietf91,pk=ietf91.agenda.pk)
    
            south_pacific_1 = Room.objects.get(meeting=ietf91,name="South Pacific 1")
            south_pacific_2 = Room.objects.get(meeting=ietf91,name="South Pacific 2")
            rainbow_12      = Room.objects.get(meeting=ietf91,name="Rainbow Suite 1/2")        
            lehua_suite     = Room.objects.get(meeting=ietf91,name="Lehua Suite")        
            kahili          = Room.objects.get(meeting=ietf91,name="Kahili")        
            coral_2         = Room.objects.get(meeting=ietf91,name="Coral 2")        
    
            south_pacific_3  = Room.objects.create(meeting=ietf91,name="South Pacific 3",capacity=20)
            rainbow_suite_3  = Room.objects.create(meeting=ietf91,name="Rainbow Suite 3",capacity=20)
            rainbow_23       = Room.objects.create(meeting=ietf91,name="Rainbow Suite 2/3",capacity=210)
            south_pacific_34 = Room.objects.create(meeting=ietf91,name="South Pacific 3/4",capacity=210)
            iolani_67        = Room.objects.create(meeting=ietf91,name="Iolani 6/7",capacity=40)
            sea_pearl_12     = Room.objects.create(meeting=ietf91,name="Sea Pearl 1/2",capacity=40)
            sea_pearl_2      = Room.objects.create(meeting=ietf91,name="Sea Pearl 2",capacity=20)
            coral_lounge     = Room.objects.create(meeting=ietf91,name="Coral Lounge", capacity=1200)
            hibiscus         = Room.objects.create(meeting=ietf91,name="Hibiscus", capacity=20)
            tiare            = Room.objects.create(meeting=ietf91,name="Tiare Suite", capacity=20)
    
            iesg = Group.objects.get(acronym='iesg')
            iab = Group.objects.get(acronym='iab')
            rsoc = Group.objects.get(acronym='rsoc')
            iaoc = Group.objects.get(acronym='iaoc')
            nomcom = Group.objects.get(acronym='nomcom2014')
            isoc = Group.objects.get(acronym='isoc')
            secr = Group.objects.get(acronym='secretariat')
            isocbot = Group.objects.create(acronym='isocbot',name="Internet Society Board of Trustees",state_id='active',type_id='isoc',parent=isoc)
            isocfell = Group.objects.create(acronym='isocfell',name="Internet Society Fellows",state_id='active',type_id='isoc',parent=isoc)
    
            system = Person.objects.get(name='(System)')
    
            for d, h, m, duration, type_id,  groups, room, slotname, label in [
                    (  9,  8,  0,  120, 'offagenda', [secr],     rainbow_suite_3, 'WEIRDS Interop', 'WEIRDS Interop'),
                    (  9,  8, 30,   90, 'lead',      [iesg],     south_pacific_2, 'Breakfast', None),
                    (  9,  9,  0,  240, 'offagenda', [secr],     lehua_suite,     'RMCAT Interim', 'RMCAT Interim Meeting'),
                    (  9,  9,  0,   60, 'lead',      [nomcom],   iolani_67,       'Breakfast', 'Nomcom Breakfast'),
                    (  9,  9,  0,  150, 'lead',      [iesg],     south_pacific_2, 'Meeting', None), 
                    (  9,  9,  0,  360, 'offagenda', [secr],     hibiscus,        'Meeting', 'RootOPS'),
                    (  9,  9, 30,  360, 'offagenda', [secr],     kahili,          'TLS Interim', 'TLS WG Interim'),
                    (  9, 11,  0,  480, 'offagenda', [secr],     coral_lounge,    'T-Shirt Distribution', 'T-shirt Distribution'),
                    (  9, 11, 30,  150, 'lead',      [iesg],     south_pacific_2, 'Lunch', 'IESG Lunch with the IAB'),
                    (  9, 11, 30,  150, 'lead',      [iab],      south_pacific_2, 'Lunch', 'IAB Lunch with the IESG'),
                    (  9, 12,  0,  360, 'offagenda', [secr],     south_pacific_1, 'Terminal Room', 'Terminal Room Open to Attendees'),
                    (  9, 14,  0,  180, 'lead',      [iab],      south_pacific_2, 'Meeting', None),
                    (  9, 16,  0,  120, 'offagenda', [secr],     coral_2,         'Meeting', 'Web Object Encryption'),
                    (  9, 17,  0,  120, 'offagenda', [secr],     sea_pearl_12,    'Reception', "Companion's Reception"), # Should this appear on agenda?
                    (  9, 19,  0,  180, 'offagenda', [isocfell], rainbow_23,      'Dinner', 'ISOC Fellows Reception/Dinner'),
                    (  9, 19,  0,  180, 'offagenda', [secr],     lehua_suite,     'Meeting', 'Huawei'),
                    (  9, 21,  0,  180, 'lead',      [secr],     sea_pearl_12,    'Gathering', 'AMS/IESG/IAB/IAOC Gathering'),
                    ( 10,  0,  0, 1440, 'offagenda', [secr],     south_pacific_1, 'Terminal Room', 'Terminal Room Open to Attendees'),
                    ( 10,  7,  0,  120, 'lead',      [iesg],     south_pacific_2, 'Breakfast', 'IESG Breakfast with the IAB'),
                    ( 10,  7,  0,  120, 'lead',      [iab],      south_pacific_2, 'Breakfast', 'IAB Breakfast with the IESG'),
                    ( 10,  7,  0,  120, 'lead',      [nomcom],   iolani_67,       'Breakfast', 'Nomcom Breakfast'),
                    ( 10,  8,  0,  600, 'offagenda', [secr],     coral_lounge,    'T-shirt Distribution', 'T-shirt Distribution'),
                    ( 10, 11, 30,   90, 'offagenda', [secr],     south_pacific_2, 'Meeting', 'OPS Directorate Meeting'),
                    ( 10, 11, 30,   90, 'offagenda', [secr],     rainbow_suite_3, 'Meeting', 'IETF/3GPP Meeting'),
                    ( 10, 11, 30,   90, 'offagenda', [secr],     lehua_suite,     'Meeting', 'RTG Area Meeting'),
                    ( 10, 19,  0,  240, 'offagenda', [secr],     south_pacific_2, 'Meeting', 'Huawei'),
                    ( 11,  0,  0, 1440, 'offagenda', [secr],     south_pacific_1, 'Terminal Room', 'Terminal Room Open to Attendees'),
                    ( 11,  7,  0,  120, 'lead',      [iesg],     south_pacific_2, 'Breakfast', None),
                    ( 11,  7,  0,  120, 'lead',      [nomcom],   iolani_67,       'Breakfast', 'Nomcom Breakfast'),
                    ( 11,  7,  0,  120, 'lead',      [iab],      rainbow_suite_3, 'Breakfast', None),
                    ( 11,  7,  0,   60, 'lead',      [iab],      tiare,           'Meeting', 'Vendor Selection Committee Meeting'),
                    ( 11,  8,  0,  600, 'offagenda', [secr],     coral_lounge,    'T-shirt Distribution', 'T-shirt Distribution'),
                    ( 11,  9,  0,   90, 'offagenda', [secr],     south_pacific_2, 'Meeting', 'DHCPv6bis Team Meeting'),
                    ( 11, 11, 30,   90, 'offagenda', [secr],     south_pacific_2, 'Meeting', 'SECdir Meeting'),
                    ( 11, 11, 30,   90, 'offagenda', [secr],     rainbow_suite_3, 'Lunch', 'RSAG/ISEB Lunch'),
                    ( 11, 16,  0,  240, 'offagenda', [secr],     south_pacific_2, 'Meeting', 'Verisign Corporate Meeting'),
                    ( 12,  0,  0, 1440, 'offagenda', [secr],     south_pacific_1, 'Terminal Room', 'Terminal Room Open to Attendees'),
                    ( 12,  7, 30,   90, 'lead',      [iaoc],     south_pacific_3, 'Breakfast', None),
                    ( 12,  7,  0,  120, 'lead',      [nomcom],   iolani_67,       'Breakfast', 'Nomcom Breakfast'),
                    ( 12,  8,  0,  540, 'offagenda', [secr],     coral_lounge,    'T-shirt Distribution', 'T-shirt Distribution'),
                    ( 12,  8,  0,  240, 'offagenda', [secr],     south_pacific_2, 'Meeting', 'DIME WG'),
                    ( 12, 11, 30,   90, 'offagenda', [secr],     rainbow_suite_3, 'Lunch', 'RFC Editor Lunch'),
                    ( 12, 15,  0,  120, 'offagenda', [secr],     south_pacific_2, 'Meeting', 'YANG Advice'),
                    ( 12, 17,  0,  240, 'offagenda', [secr],     rainbow_suite_3, 'Meeting', 'Huawei (POC Wil Liu)'),
                    ( 12, 20,  0,  150, 'offagenda', [secr],     south_pacific_2, 'Meeting', 'ICANN SSAC'),
                    ( 13,  0,  0, 1440, 'offagenda', [secr],     south_pacific_1, 'Terminal Room', 'Terminal Room Open to Attendees'),
                    ( 13,  7,  0,  120, 'lead',      [iab],      rainbow_suite_3, 'Breakfast', None),
                    ( 13,  7,  0,  120, 'lead',      [nomcom],   iolani_67,       'Breakfast', 'Nomcom Breakfast'),
                    ( 13, 11, 30,   90, 'lead',      [iab],      sea_pearl_2,     'Meeting', 'IAB Liaison Oversight'),
                    ( 13, 11, 30,   90, 'lead',      [rsoc],     rainbow_suite_3, 'Lunch', None),
                    ( 14,  0,  0,  900, 'offagenda', [secr],     south_pacific_1, 'Terminal Room', 'Terminal Room Open to Attendees'),
                    ( 14,  7,  0,  120, 'lead',      [nomcom],   iolani_67,       'Breakfast', 'Nomcom Breakfast'),
                    ( 14, 11,  0,  360, 'offagenda', [isoc],     south_pacific_34,'Meeeting', 'ISOC AC Meeting'),
                    ( 14, 13, 30,   90, 'lead',      [iesg],     south_pacific_2, 'Lunch', 'IESG Lunch with the IAB'),
                    ( 14, 13, 30,   90, 'lead',      [iab],      south_pacific_2, 'Lunch', 'IAB Lunch with the IESG'),
                    ( 14, 18,  0,   60, 'offagenda', [isocbot],  rainbow_23,      'Reception', 'ISOC Board Reception for IETF Leadership'),
                    ( 14, 19,  0,  180, 'offagenda', [isocbot],  rainbow_23,      'Dinner', 'ISOC Board Dinner for IETF Leadership'),
                    ( 15,  8,  0,   60, 'offagenda', [isocbot],  rainbow_12,      'Breakfast', 'ISOC Board of Trustees Breakfast'),
                    ( 15,  8,  0,  540, 'offagenda', [isocbot],  south_pacific_34,'Meeting', 'ISOC Board of Trustees Meeting'),
                    ( 15, 12,  0,   60, 'offagenda', [isocbot],  rainbow_12,      'Lunch', 'ISOC Board of Trustees Lunch'),
                    ( 16,  8,  0,   60, 'offagenda', [isocbot],  rainbow_12,      'Breakfast', 'ISOC Board of Trustees Breakfast'), 
                    ( 16,  8,  0,  540, 'offagenda', [isocbot],  south_pacific_34,'Meeting', 'ISOC Board of Trustees Meeting'),
                    ( 16, 12,  0,   60, 'offagenda', [isocbot],  rainbow_12,      'Lunch', 'ISOC Board of Trustees Lunch'),
                    ]:
                ts = ietf91.timeslot_set.create(type_id=type_id, name=slotname, 
                                                time=datetime.datetime(2014,11,d,h,m,0),
                                                duration=datetime.timedelta(minutes=duration), 
                                                location=room,show_location=(type_id not in ['lead','offagenda']))
                for group in groups:
                    session = ietf91.session_set.create(name= label or "%s %s"%(group.acronym.upper(),slotname),
                                                        group=group, attendees=25,
                                                        requested=datetime.datetime(2014,11,1,0,0,0),
                                                        requested_by=system, status_id='sched')
                    ScheduledSession.objects.create(schedule=agenda91, timeslot=ts, session=session)




class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0005_auto_20150430_0847'),
        ('name',    '0004_auto_20150318_1140'),
        ('group',   '0004_auto_20150430_0847'),
        ('person',  '0004_auto_20150308_0440'),
    ]

    operations = [
        migrations.RunPython(backfill_91_other_meetings)
    ]
