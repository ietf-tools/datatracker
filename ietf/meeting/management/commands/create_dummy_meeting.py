# Copyright The IETF Trust 2020, All Rights Reserved
# -*- coding: utf-8 -*-

# This command generates a Meeting (IETF 999) with Rooms, TimeSlots, Sessions and Constraints.
# It is mainly meant to support the development of the Automatic Schedule Builder, by
# providing one meeting with a full set of constraints, on which the schedule
# builder can be run to test it with a realistic dataset.
# The data is based on IETF 106, modified to translate many previously manually
# processed comments into Constraint objects, using recently added options.

# This command was built by:
# - Running script-generator.py, which generates new objects based on IETF 106 data.
# - Going through all manually entered comments, and seeing whether they should and
#   can be translated to the newly expanded Constraint objects.
#
# This work was done in the context of the new meeting constraints modelling:
# https://trac.tools.ietf.org/tools/ietfdb/wiki/MeetingConstraints
# Note that aside from Constraint objects, as created below, there is also
# business logic that applies to all sessions, which is to be implemented
# in the automatic schedule builder.
# 
# Important notes:
# - Free text comments can contain a lot of nuance and flexibility. These were
#   translated to explicit Constraints as well as possible. 
# - Some constraints, like "Please also avoid collision with IoT-related BOFs.", were
#   too vague to define.
# - Two WGs requested two sessions, but actually meant to have a single 2.5 hour session,
#   which currently can not be entered in the session request UI. These were manually
#   modified to have a single 2.5 hour session.
# - Some constraints are implicit by business logic. For example, pce requested not
#   to schedule against any routing area BOF. However, pce is in the routing area,
#   and therefore should never be scheduled against any routing area BOF.
#   Similarly, rtgwg asked for "no overlap with other routing area WGs". However,
#   rtgwg has meeting_seen_as_area set (it is a WG, but should be considered an area meeting),
#   meaning this behaviour is already implied. The same occurs for dispatch, which requested
#   not to be scheduled against other area meetings.
# - In general, the purpose of this dataset is not to recreate the set exactly as if it
#   would be entered by session requesters, but to provide a realistic dataset of a
#   realistic complexity.
# - The joint second idr session was added from IETF 105, to have another case of
#   a joint session in the dataset.

from __future__ import absolute_import, print_function, unicode_literals

import debug                            # pyflakes:ignore

import socket
import datetime

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from ietf.group.models import Group
from ietf.name.models import TimerangeName, TimeSlotTypeName
from ietf.meeting.models import Meeting, Room, Constraint, Session, ResourceAssociation, TimeSlot, SchedulingEvent, Schedule


class Command(BaseCommand):
    help = "Create (or delete) a dummy meeting for test and development purposes."

    def add_arguments(self, parser):
        parser.add_argument('--delete', dest='delete', action='store_true', help='Delete the test and development dummy meeting')

    def handle(self, *args, **options):
        if socket.gethostname().split('.')[0] in ['core3', 'ietfa', 'ietfb', 'ietfc', ]:
            raise EnvironmentError("Refusing to create a dummy meetng on a production server")

        opt_delete = options.get('delete', False)
        if opt_delete:
            if Meeting.objects.filter(number='999').exists():
                Meeting.objects.filter(number='999').delete()
                self.stdout.write("Deleted dummy meeting IETF 999 and its related objects.")
            else:
                self.stderr.write("Dummy meeting IETF 999 does not exist; nothing to do.\n")
        else:
            if Meeting.objects.filter(number='999').exists():
                self.stderr.write("Dummy meeting IETF 999 already exists; nothing to do.\n")
            else:
                transaction.set_autocommit(False)
                
                m = Meeting.objects.create(
                    number='999',
                    type_id='IETF',
                    date=datetime.date(2019, 11, 16),
                    days=7,
                )
                schedule = Schedule.objects.create(meeting=m, name='Empty-Schedule', owner_id=1, 
                                                   visible=True, public=True)
                m.schedule = schedule
                m.save()
                
                ##### ROOMS #####
                
                r = Room.objects.create(meeting=m, name='Skai Suite 4 (Swissotel)', capacity=None, functional_name='Newcomers dinner')
                r = Room.objects.create(meeting=m, name='Ord', capacity=None, functional_name='Code Sprint')
                r = Room.objects.create(meeting=m, name='Skai Suite 1 (Swissotel)', capacity=None, functional_name='Systers Networking')
                r = Room.objects.create(meeting=m, name='Butterworth', capacity=None, functional_name='Attendee Sign-Up 2')
                r = Room.objects.create(meeting=m, name='Bras Basah', capacity=None, functional_name='Attendee Sign-Up 1')
                r = Room.objects.create(meeting=m, name='Indiana', capacity=None, functional_name='NOC')
                r = Room.objects.create(meeting=m, name='Ord/Blundell', capacity=None, functional_name='Terminal Room')
                r = Room.objects.create(meeting=m, name='Bailey', capacity=None, functional_name='Secretariat')
                r = Room.objects.create(meeting=m, name='Bonham', capacity=None, functional_name='NomCom Interviews')
                r = Room.objects.create(meeting=m, name='Fullerton', capacity=None, functional_name='NomCom')
                r = Room.objects.create(meeting=m, name='Minto', capacity=None, functional_name='LLC')
                r = Room.objects.create(meeting=m, name='Mercury/Enterprise', capacity=None, functional_name='ISOC')
                r = Room.objects.create(meeting=m, name='Clark', capacity=None, functional_name='IESG')
                r = Room.objects.create(meeting=m, name='VIP B', capacity=None, functional_name='IAB')
                r = Room.objects.create(meeting=m, name='Moor/Morrison', capacity=None, functional_name='Code Lounge')
                r = Room.objects.create(meeting=m, name='Fairmont Ballroom Foyer', capacity=None, functional_name='Welcome Reception')
                r = Room.objects.create(meeting=m, name='Convention Foyer', capacity=None, functional_name='IETF Registration')
                r.session_types.set(TimeSlotTypeName.objects.filter(slug__in=['reg']))
                r = Room.objects.create(meeting=m, name='Stamford & Fairmont Ballroom Foyers', capacity=None, functional_name='Breaks')
                r.session_types.set(TimeSlotTypeName.objects.filter(slug__in=['break']))
                r = Room.objects.create(meeting=m, name='Canning/Padang', capacity=None, functional_name='Plenary')
                r.session_types.set(TimeSlotTypeName.objects.filter(slug__in=['plenary']))
                r = Room.objects.create(meeting=m, name='Canning', capacity=250, functional_name='Breakout 8')
                r.session_types.set(TimeSlotTypeName.objects.filter(slug__in=['regular']))
                r = Room.objects.create(meeting=m, name='Padang', capacity=300, functional_name='Breakout 7')
                r.session_types.set(TimeSlotTypeName.objects.filter(slug__in=['regular']))
                r = Room.objects.create(meeting=m, name='Collyer', capacity=250, functional_name='Breakout 6')
                r.session_types.set(TimeSlotTypeName.objects.filter(slug__in=['regular']))
                r = Room.objects.create(meeting=m, name='Sophia', capacity=200, functional_name='Breakout 5')
                r.session_types.set(TimeSlotTypeName.objects.filter(slug__in=['regular']))
                r = Room.objects.create(meeting=m, name='Olivia', capacity=150, functional_name='Breakout 4')
                r.session_types.set(TimeSlotTypeName.objects.filter(slug__in=['regular']))
                r = Room.objects.create(meeting=m, name='Hullet', capacity=100, functional_name='Breakout 3')
                r.session_types.set(TimeSlotTypeName.objects.filter(slug__in=['regular']))
                r = Room.objects.create(meeting=m, name='VIP A', capacity=100, functional_name='Breakout 2')
                r.session_types.set(TimeSlotTypeName.objects.filter(slug__in=['regular']))
                r = Room.objects.create(meeting=m, name='Orchard', capacity=50, functional_name='Breakout 1')
                r.session_types.set(TimeSlotTypeName.objects.filter(slug__in=['regular']))
                
                ##### SESSIONS AND CONSTRAINTS #####
                
                ## session for grow ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1584,  # grow
                    attendees=75,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1041, )  # idr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2166, )  # sidrops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1619, )  # rtgwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1578, )  # v6ops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1751, )  # lisp
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=111656, )  # Warren Kumari
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=111303, )  # Job Snijders
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=111246, )  # Chris Morrow
                
                ## session for sidrops ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2166,  # sidrops
                    attendees=62,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1041, )  # idr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1397, )  # pim
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1140, )  # mpls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2215, )  # lsr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1619, )  # rtgwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2216, )  # lsvr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1723, )  # 6man
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1584, )  # grow
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1905, )  # spring
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=111656, )  # Warren Kumari
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=111246, )  # Chris Morrow
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=104971, )  # Keyur Patel
                
                ## session for dnsop ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1452,  # dnsop
                    attendees=160,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                ## session for dnsop ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1452,  # dnsop
                    attendees=160,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=3600),  # 1:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=988, )  # dhc
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2145, )  # maprg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2208, )  # doh
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1958, )  # dprive
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1895, )  # dnssd
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1803, )  # homenet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1995, )  # acme
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1920, )  # trans
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1665, )  # intarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2146, )  # regext
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2164, )  # lamps
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1892, )  # dmarc
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=18009, )  # Suzanne Woolf
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=123662, )  # Benno Overeinder
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=115244, )  # Tim Wicinski
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=111656, )  # Warren Kumari
                
                ## session for lsvr ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2216,  # lsvr
                    attendees=100,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1041, )  # idr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1584, )  # grow
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1960, )  # bess
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2166, )  # sidrops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1404, )  # rtgarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1619, )  # rtgwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2215, )  # lsr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2214, )  # rift
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1905, )  # spring
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1840, )  # nvo3
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1964, )  # bier
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=109802, )  # Alvaro Retana
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=108304, )  # Gunter Van de Velde
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=111493, )  # Victor Kuarsingh
                
                ## session for quic ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2161,  # quic
                    attendees=200,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                s.resources.set(ResourceAssociation.objects.filter(pk__in=[6]))  # [<ResourceAssociation: Experimental Room Setup (U-Shape and classroom, subject to availability)>]
                ## session for quic ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2161,  # quic
                    attendees=200,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                s.resources.set(ResourceAssociation.objects.filter(pk__in=[6]))  # [<ResourceAssociation: Experimental Room Setup (U-Shape and classroom, subject to availability)>]
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1718, )  # httpbis
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1764, )  # mptcp
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=42, )  # iccrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1620, )  # tcpm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1463, )  # tsvwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1679, )  # tsvarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2015, )  # capport
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2246, )  # add
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2208, )  # doh
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=19483, )  # Sean Turner
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=112330, )  # Mirja Kühlewind
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=109354, )  # Brian Trammell
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=107131, )  # Martin Thomson
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=124381, )  # Alan Frindell
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105721, )  # Jana Iyengar
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=119702, )  # Ian Swett
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=104294, )  # Magnus Westerlund
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=116439, )  # Mike Bishop
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=103881, )  # Mark Nottingham
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=112773, )  # Lars Eggert
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='time_relation', time_relation='subsequent-days')
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='timerange')
                c.timeranges.set(TimerangeName.objects.exclude(slug__startswith='monday').exclude(slug__startswith='tuesday').exclude(slug__startswith='wednesday-morning'))
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2253, )  # abcd
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2256, )  # raw
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2254, )  # wpack
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2258, )  # mathmesh
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2257, )  # txauth
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2255, )  # tmrid
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2260, )  # webtrans
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1399, )  # opsarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1404, )  # rtgarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1619, )  # rtgwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1625, )  # genarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1665, )  # intarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1763, )  # dispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1853, )  # irtfopen
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2017, )  # artarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2219, )  # secdispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2252, )  # gendispatch
                
                
                ## session for tsvwg ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1463,  # tsvwg
                    attendees=100,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""Must not conflict with Transport Area BoFs. """,  # this is implicit
                    remote_instructions="",
                )
                ## session for tsvwg ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1463,  # tsvwg
                    attendees=100,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""Must not conflict with Transport Area BoFs. """,  # this is implicit
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1665, )  # intarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1679, )  # tsvarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=42, )  # iccrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2145, )  # maprg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1620, )  # tcpm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1152, )  # nfsv4
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1924, )  # taps
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1723, )  # 6man
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1962, )  # detnet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1926, )  # tram
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1578, )  # v6ops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1966, )  # dtn
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1764, )  # mptcp
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1089, )  # ippm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1838, )  # rmcat
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2202, )  # panrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1524, )  # ccamp
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2017, )  # artarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=23177, )  # Bob Briscoe
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=112330, )  # Mirja Kühlewind
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=110856, )  # Wesley Eddy
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=104695, )  # Michael Tüxen
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=104331, )  # Gorry Fairhurst
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=104294, )  # Magnus Westerlund
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=103156, )  # David Black
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='time_relation', time_relation='one-day-seperation')
                
                ## session for ccamp ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1524,  # ccamp
                    attendees=50,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1140, )  # mpls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1575, )  # netconf
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1638, )  # netmod
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1985, )  # teas
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1630, )  # pce
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1960, )  # bess
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1962, )  # detnet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1875, )  # i2rs
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2215, )  # lsr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=109703, )  # Daniele Ceccarelli
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=108894, )  # Fatai Zhang
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=106471, )  # Deborah Brungard
                
                ## session for dispatch ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1763,  # dispatch
                    attendees=80,
                    agenda_note="Joint with ARTAREA",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments=""" and avoid the same kind of conflicts with other area meetings and any Bofs and potential new ART WGs.""",  # this is implicit
                    remote_instructions="",
                )
                s.joint_with_groups.set(Group.objects.filter(acronym='artarea'))
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2219, )  # secdispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1812, )  # avtcore
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1899, )  # stir
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1789, )  # core
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1762, )  # sipcore
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2208, )  # doh
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1838, )  # rmcat
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2176, )  # jmap
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2205, )  # extra
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1814, )  # payload
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1918, )  # uta
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=31, )  # cfrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1138, )  # mmusic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1892, )  # dmarc
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1995, )  # acme
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1643, )  # ecrit
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1815, )  # xrblock
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1679, )  # tsvarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1463, )  # tsvwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1926, )  # tram
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1399, )  # opsarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=104140, )  # Ben Campbell
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=103769, )  # Adam Roach
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=102830, )  # Mary Barnes
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=102154, )  # Alexey Melnikov
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=21684, )  # Barry Leiba
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='timerange')
                c.timeranges.set(TimerangeName.objects.exclude(slug='monday-morning'))
                
                ## session for tram ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1926,  # tram
                    attendees=None,
                    agenda_note="",
                    requested_duration=datetime.timedelta(0),  # 0:00:00
                    comments="""""",
                    remote_instructions="",
                )
                
                ## session for v6ops ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1578,  # v6ops
                    attendees=100,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1905, )  # spring
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1041, )  # idr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1665, )  # intarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1723, )  # 6man
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2215, )  # lsr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1679, )  # tsvarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1619, )  # rtgwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1463, )  # tsvwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1584, )  # grow
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2202, )  # panrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=111656, )  # Warren Kumari
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=101568, )  # Ron Bonica
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=2853, )  # Fred Baker
                
                ## session for stir ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1899,  # stir
                    attendees=60,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2167, )  # ipwave
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2211, )  # suit
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2164, )  # lamps
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1643, )  # ecrit
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1994, )  # modern
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1762, )  # sipcore
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1763, )  # dispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2194, )  # teep
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1812, )  # avtcore
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2220, )  # mls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1138, )  # mmusic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=31, )  # cfrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2156, )  # sipbrandy
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2013, )  # perc
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1995, )  # acme
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2219, )  # secdispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1748, )  # oauth
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=5376, )  # Russ Housley
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=120587, )  # Chris Wendt
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=104557, )  # Jon Peterson
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=103961, )  # Robert Sparks
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=103769, )  # Adam Roach
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=19483, )  # Sean Turner
                
                ## session for pim ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1397,  # pim
                    attendees=30,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1118, )  # mboned
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1964, )  # bier
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1638, )  # netmod
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1575, )  # netconf
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1404, )  # rtgarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1875, )  # i2rs
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1619, )  # rtgwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1960, )  # bess
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1905, )  # spring
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1803, )  # homenet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1840, )  # nvo3
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1041, )  # idr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1132, )  # manet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1678, )  # softwire
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1956, )  # anima
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1962, )  # detnet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1751, )  # lisp
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=109802, )  # Alvaro Retana
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=106173, )  # Stig Venaas
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105708, )  # Mike McBride
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='wg_adjacent', target_id=1118, )  # mboned
                
                ## session for suit ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2211,  # suit
                    attendees=80,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2167, )  # ipwave
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2231, )  # rats
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1831, )  # mile
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1740, )  # ipsecme
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2194, )  # teep
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1899, )  # stir
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2164, )  # lamps
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2220, )  # mls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2156, )  # sipbrandy
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1869, )  # sacm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2219, )  # secdispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=31, )  # cfrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1748, )  # oauth
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1995, )  # acme
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105857, )  # Hannes Tschofenig
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105815, )  # Roman Danyliw
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=124893, )  # David Brown
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=15927, )  # Dave Thaler
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=123482, )  # Milosch Meriac
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=5376, )  # Russ Housley
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=123481, )  # Brendan Moran
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=117723, )  # Henk Birkholz
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=111953, )  # David Waltermire
                
                ## session for coinrg ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2234,  # coinrg
                    attendees=100,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1883, )  # nwcrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1853, )  # irtfopen
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2228, )  # qirg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2209, )  # dinrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1849, )  # icnrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1991, )  # t2trg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2250, )  # loops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=125277, )  # Jianfei He
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=123468, )  # Eve Schooler
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=103930, )  # Marie-Jose Montpetit
                
                ## session for nwcrg ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1883,  # nwcrg
                    attendees=35,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1463, )  # tsvwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1853, )  # irtfopen
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2234, )  # coinrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2250, )  # loops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2227, )  # pearg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1924, )  # taps
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2202, )  # panrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=42, )  # iccrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1849, )  # icnrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2209, )  # dinrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=107132, )  # Vincent Roca
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=103930, )  # Marie-Jose Montpetit
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='timerange')
                c.timeranges.set(TimerangeName.objects.exclude(slug__startswith='friday').exclude(slug__startswith='thursday'))
                
                ## session for mtgvenue ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2147,  # mtgvenue
                    attendees=None,
                    agenda_note="",
                    requested_duration=datetime.timedelta(0),  # 0:00:00
                    comments="""""",
                    remote_instructions="",
                )
                
                ## session for tcpm ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1620,  # tcpm
                    attendees=60,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1764, )  # mptcp
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2202, )  # panrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=42, )  # iccrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1679, )  # tsvarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1924, )  # taps
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1463, )  # tsvwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=112330, )  # Mirja Kühlewind
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=110636, )  # Michael Scharf
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=104695, )  # Michael Tüxen
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=15951, )  # Yoshifumi Nishida
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='timerange')
                c.timeranges.set(TimerangeName.objects.filter(slug='thursday-afternoon-late'))
                
                ## session for ippm ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1089,  # ippm
                    attendees=60,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1718, )  # httpbis
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1679, )  # tsvarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2202, )  # panrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2145, )  # maprg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1665, )  # intarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2015, )  # capport
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1924, )  # taps
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1463, )  # tsvwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1578, )  # v6ops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=945, )  # bmwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1628, )  # bfd
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1723, )  # 6man
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1905, )  # spring
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1599, )  # opsec
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1140, )  # mpls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=112330, )  # Mirja Kühlewind
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=109354, )  # Brian Trammell
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=106879, )  # Frank Brockners
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=122654, )  # Greg <gregimirsky@gmail.com>>
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=102900, )  # Al Morton
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=119325, )  # Tommy Pauly
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=118908, )  # Giuseppe Fioccola
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=113573, )  # Bill Cerveny
                
                ## session for lamps ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2164,  # lamps
                    attendees=45,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=3600),  # 1:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2167, )  # ipwave
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2211, )  # suit
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2164, )  # lamps
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1921, )  # ace
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=31, )  # cfrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1995, )  # acme
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1748, )  # oauth
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2194, )  # teep
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2220, )  # mls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2156, )  # sipbrandy
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2219, )  # secdispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=109505, )  # Bernie Hoeneisen
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=108049, )  # Richard Barnes
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105815, )  # Roman Danyliw
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=102154, )  # Alexey Melnikov
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=125563, )  # Hendrik Brockhaus
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=19483, )  # Sean Turner
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=124538, )  # Tim Hollebeek
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=18427, )  # Rich Salz
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=110910, )  # Jim Schaad
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=5376, )  # Russ Housley
                
                ## session for httpbis ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1718,  # httpbis
                    attendees=150,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                ## session for httpbis ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1718,  # httpbis
                    attendees=150,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1089, )  # ippm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1924, )  # taps
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1763, )  # dispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2017, )  # artarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2015, )  # capport
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=119325, )  # Tommy Pauly
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=116593, )  # Patrick McManus
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=103881, )  # Mark Nottingham
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=21684, )  # Barry Leiba
                
                ## session for taps ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1924,  # taps
                    attendees=50,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""The IRTF Chair is a contributor to TAPS so please avoid IRTF RGs if possible.""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2145, )  # maprg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1718, )  # httpbis
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2202, )  # panrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1463, )  # tsvwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1679, )  # tsvarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2234, )  # coinrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=42, )  # iccrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1620, )  # tcpm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1089, )  # ippm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1812, )  # avtcore
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1463, )  # tsvwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1838, )  # rmcat
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2248, )  # mops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1853, )  # irtfopen
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2219, )  # secdispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1118, )  # mboned
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2250, )  # loops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2248, )  # mops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=122540, )  # Jake Holland
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=109354, )  # Brian Trammell
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=121595, )  # Christopher Wood
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=104331, )  # Gorry Fairhurst
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=119463, )  # Kyle Rose
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=104294, )  # Magnus Westerlund
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=119325, )  # Tommy Pauly
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=103877, )  # Michael Welzl
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=114993, )  # Anna Brunstrom
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=123344, )  # Theresa Enghardt
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=21226, )  # Aaron Falk
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=112330, )  # Mirja Kühlewind
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=123343, )  # Philipp Tiesel
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=20209, )  # Colin Perkins
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=109753, )  # Zaheduzzaman Sarker
                
                ## session for dprive ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1958,  # dprive
                    attendees=120,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1895, )  # dnssd
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2164, )  # lamps
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1452, )  # dnsop
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2208, )  # doh
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1803, )  # homenet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1995, )  # acme
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=115244, )  # Tim Wicinski
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105099, )  # Éric Vyncke
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=100664, )  # Brian Haberman
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='timerange')
                c.timeranges.set(TimerangeName.objects.exclude(slug__startswith='friday'))
                
                ## session for teep ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2194,  # teep
                    attendees=50,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                ## session for teep ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2194,  # teep
                    attendees=50,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2211, )  # suit
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1723, )  # 6man
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1578, )  # v6ops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1665, )  # intarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1831, )  # mile
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2231, )  # rats
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2002, )  # cose
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1748, )  # oauth
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=107773, )  # Mingliang Pei
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105857, )  # Hannes Tschofenig
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105785, )  # Nancy Cam-Winget
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=15927, )  # Dave Thaler
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=124970, )  # Dave Wheeler
                
                ## session for iccrg ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=42,  # iccrg
                    attendees=100,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2208, )  # doh
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1718, )  # httpbis
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1764, )  # mptcp
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1924, )  # taps
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1853, )  # irtfopen
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1838, )  # rmcat
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2145, )  # maprg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1679, )  # tsvarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1620, )  # tcpm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1463, )  # tsvwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105721, )  # Jana Iyengar
                
                ## session for rats ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2231,  # rats
                    attendees=40,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                ## session for rats ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2231,  # rats
                    attendees=40,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2219, )  # secdispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2194, )  # teep
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1869, )  # sacm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1995, )  # acme
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1831, )  # mile
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1575, )  # netconf
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2211, )  # suit
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1958, )  # dprive
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1956, )  # anima
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2002, )  # cose
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105815, )  # Roman Danyliw
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105785, )  # Nancy Cam-Winget
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=104851, )  # Kathleen Moriarty
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=21144, )  # Ned Smith
                
                ## session for secdispatch ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2219,  # secdispatch
                    attendees=200,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1996, )  # dots
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2231, )  # rats
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1990, )  # tokbind
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2143, )  # curdle
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1748, )  # oauth
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2002, )  # cose
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1831, )  # mile
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2194, )  # teep
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1995, )  # acme
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2164, )  # lamps
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2211, )  # suit
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1921, )  # ace
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1740, )  # ipsecme
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2169, )  # secevent
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1763, )  # dispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1965, )  # i2nsf
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1869, )  # sacm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1718, )  # httpbis
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=108049, )  # Richard Barnes
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105815, )  # Roman Danyliw
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=104851, )  # Kathleen Moriarty
                
                ## session for mboned ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1118,  # mboned
                    attendees=30,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1397, )  # pim
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2248, )  # mops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1960, )  # bess
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1964, )  # bier
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1138, )  # mmusic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1619, )  # rtgwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1404, )  # rtgarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1578, )  # v6ops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1723, )  # 6man
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2214, )  # rift
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=106173, )  # Stig Venaas
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105708, )  # Mike McBride
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=104329, )  # Leonard Giuliano
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=111656, )  # Warren Kumari
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=106315, )  # Greg Shepherd
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='wg_adjacent', target_id=1397, )  # mboned
                
                ## session for bess ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1960,  # bess
                    attendees=90,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""""",
                    remote_instructions="",
                )
                ## session for bess ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1960,  # bess
                    attendees=90,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1041, )  # idr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1840, )  # nvo3
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1964, )  # bier
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1397, )  # pim
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1140, )  # mpls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1910, )  # sfc
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1905, )  # spring
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1969, )  # pals
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=123321, )  # mankamana mishra
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=113838, )  # Stephane Litkowski
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=108279, )  # Martin Vigoureux
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105786, )  # Matthew Bocci
                
                ## session for cellar ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2022,  # cellar
                    attendees=None,
                    agenda_note="",
                    requested_duration=datetime.timedelta(0),  # 0:00:00
                    comments="""""",
                    remote_instructions="",
                )
                
                ## session for homenet and dnssd ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1803,  # homenet
                    attendees=60,
                    agenda_note="Joint with DNSSD",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                s.joint_with_groups.set(Group.objects.filter(acronym='dnssd'))
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1452, )  # dnsop
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2150, )  # babel
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1578, )  # v6ops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1803, )  # homenet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1723, )  # 6man
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1958, )  # dprive
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1718, )  # httpbis
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2208, )  # doh
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1665, )  # intarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1789, )  # core
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2220, )  # mls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1956, )  # anima
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2231, )  # rats
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1903, )  # 6tisch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2249, )  # lake
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1730, )  # roll
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=119562, )  # David Schinazi
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=114464, )  # Barbara Stark
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105099, )  # Éric Vyncke
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=19177, )  # Stephen Farrell
                
                ## session for curdle ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2143,  # curdle
                    attendees=None,
                    agenda_note="",
                    requested_duration=datetime.timedelta(0),  # 0:00:00
                    comments="""""",
                    remote_instructions="",
                )
                
                ## session for acme ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1995,  # acme
                    attendees=70,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1748, )  # oauth
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1740, )  # ipsecme
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1965, )  # i2nsf
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2219, )  # secdispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=31, )  # cfrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=106745, )  # Yoav Nir
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105815, )  # Roman Danyliw
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=102154, )  # Alexey Melnikov
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=18427, )  # Rich Salz
                
                ## session for babel ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2150,  # babel
                    attendees=21,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=3600),  # 1:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1960, )  # bess
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1840, )  # nvo3
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1619, )  # rtgwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1041, )  # idr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1404, )  # rtgarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1132, )  # manet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1803, )  # homenet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1638, )  # netmod
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1575, )  # netconf
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=108279, )  # Martin Vigoureux
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=104645, )  # Russ White
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=102391, )  # Donald Eastlake
                
                ## session for lsr ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2215,  # lsr
                    attendees=100,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                ## session for lsr ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2215,  # lsr
                    attendees=100,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=3600),  # 1:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1740, )  # ipsecme
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2216, )  # lsvr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1619, )  # rtgwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1041, )  # idr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1905, )  # spring
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2214, )  # rift
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1628, )  # bfd
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1960, )  # bess
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=109802, )  # Alvaro Retana
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=22933, )  # Christian Hopps
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=10784, )  # Acee Lindem
                
                ## session for netconf ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1575,  # netconf
                    attendees=65,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1638, )  # netmod
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1714, )  # opsawg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1399, )  # opsarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1956, )  # anima
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1628, )  # bfd
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1620, )  # tcpm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2150, )  # babel
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2231, )  # rats
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1041, )  # idr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=118100, )  # Ignas Bagdonas
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=112548, )  # Kent Watsen
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=107859, )  # Mahesh Jethanandani
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='timerange')
                c.timeranges.set(TimerangeName.objects.exclude(slug__startswith='monday').exclude(slug__startswith='tuesday'))
                
                ## session for maprg ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2145,  # maprg
                    attendees=200,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1764, )  # mptcp
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1089, )  # ippm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1679, )  # tsvarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1744, )  # alto
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1838, )  # rmcat
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1924, )  # taps
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1620, )  # tcpm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1665, )  # intarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2017, )  # artarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1404, )  # rtgarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1718, )  # httpbis
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1578, )  # v6ops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2202, )  # panrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2219, )  # secdispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1452, )  # dnsop
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=42, )  # iccrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1763, )  # dispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1714, )  # opsawg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=945, )  # bmwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1463, )  # tsvwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1723, )  # 6man
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1853, )  # irtfopen
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=112330, )  # Mirja Kühlewind
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=121213, )  # Dave Plonka
                
                ## session for 6lo ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1897,  # 6lo
                    attendees=55,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""Please also avoid collision with IoT-related BOFs.
                Eric Vyncke's presence is a strong wish as he may take responsibility of this WG.""",  # BOFs are already avoided if in the internet area
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1817, )  # lwig
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2231, )  # rats
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1089, )  # ippm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1620, )  # tcpm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2148, )  # lpwan
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1578, )  # v6ops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1730, )  # roll
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1962, )  # detnet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1803, )  # homenet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1665, )  # intarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1921, )  # ace
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2175, )  # cbor
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2167, )  # ipwave
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1132, )  # manet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1723, )  # 6man
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=42, )  # iccrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1903, )  # 6tisch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1991, )  # t2trg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2249, )  # lake
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1789, )  # core
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1849, )  # icnrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=116512, )  # Shwetha Bhandari
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=108961, )  # Carles Gomez
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=106412, )  # Suresh Krishnan
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105099, )  # Éric Vyncke
                
                ## session for 6man ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1723,  # 6man
                    attendees=120,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""We would prefer to have session #1 early in the week to allow for side meetings to follow up on open items.""",
                    remote_instructions="",
                )
                ## session for 6man ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1723,  # 6man
                    attendees=120,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=3600),  # 1:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1665, )  # intarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2250, )  # loops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2147, )  # mtgvenue
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1905, )  # spring
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1578, )  # v6ops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1895, )  # dnssd
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1803, )  # homenet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1679, )  # tsvarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1463, )  # tsvwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=106412, )  # Suresh Krishnan
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105691, )  # Ole Trøan
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=2793, )  # Bob Hinden
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='time_relation', time_relation='one-day-seperation')
                
                ## session for irtfopen ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1853,  # irtfopen
                    attendees=150,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""MUST NOT be in parallel with any other IRTF sessions. """,  # should be implicit
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=31, )  # cfrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1849, )  # icnrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2228, )  # qirg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=42, )  # iccrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2227, )  # pearg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1988, )  # hrpc
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2202, )  # panrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1968, )  # gaia
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1883, )  # nwcrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2209, )  # dinrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=38, )  # nmrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2234, )  # coinrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2145, )  # maprg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1991, )  # t2trg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1463, )  # tsvwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1679, )  # tsvarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1620, )  # tcpm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1838, )  # rmcat
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1812, )  # avtcore
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2248, )  # mops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2250, )  # loops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1924, )  # taps
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=109986, )  # Mat Ford
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=20209, )  # Colin Perkins
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='timerange')
                c.timeranges.set(TimerangeName.objects.exclude(slug__startswith='monday'))
                
                ## session for lpwan ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2148,  # lpwan
                    attendees=75,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""Eric Vyncke's presence is a strong wish (not a strong requirement) as he may take responsibility of this WG.""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2256, )  # raw
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1897, )  # 6lo
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1789, )  # core
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1723, )  # 6man
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1962, )  # detnet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1903, )  # 6tisch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2214, )  # rift
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1730, )  # roll
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2211, )  # suit
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1817, )  # lwig
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1575, )  # netconf
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2175, )  # cbor
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2249, )  # lake
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1665, )  # intarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=119881, )  # Alexander Pelov
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=115824, )  # Pascal Thubert
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=106412, )  # Suresh Krishnan
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105099, )  # Éric Vyncke
                
                ## session for 6tisch ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1903,  # 6tisch
                    attendees=60,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2256, )  # raw
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1897, )  # 6lo
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1789, )  # core
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1723, )  # 6man
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1962, )  # detnet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2148, )  # lpwan
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2214, )  # rift
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1730, )  # roll
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2211, )  # suit
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1817, )  # lwig
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1575, )  # netconf
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2175, )  # cbor
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1956, )  # anima
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2249, )  # lake
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1921, )  # ace
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=115824, )  # Pascal Thubert
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=108628, )  # Thomas Watteyne
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=106412, )  # Suresh Krishnan
                
                ## session for lisp ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1751,  # lisp
                    attendees=45,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1619, )  # rtgwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1665, )  # intarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1397, )  # pim
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1910, )  # sfc
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2145, )  # maprg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1584, )  # grow
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1962, )  # detnet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1875, )  # i2rs
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2216, )  # lsvr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1840, )  # nvo3
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2215, )  # lsr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1849, )  # icnrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1118, )  # mboned
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1463, )  # tsvwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1964, )  # bier
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1905, )  # spring
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1041, )  # idr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1853, )  # irtfopen
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1960, )  # bess
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=3862, )  # Joel Halpern
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=121160, )  # Padma Pillay-Esnault
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=108833, )  # Luigi Iannone
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=106471, )  # Deborah Brungard
                
                ## session for mptcp ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1764,  # mptcp
                    attendees=50,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=3600),  # 1:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1620, )  # tcpm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2145, )  # maprg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1463, )  # tsvwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1679, )  # tsvarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1924, )  # taps
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=42, )  # iccrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1853, )  # irtfopen
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2234, )  # coinrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=112330, )  # Mirja Kühlewind
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=107998, )  # Philip Eardley
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=15951, )  # Yoshifumi Nishida
                
                ## session for roll ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1730,  # roll
                    attendees=50,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                ## session for roll ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1730,  # roll
                    attendees=50,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1956, )  # anima
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1921, )  # ace
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1789, )  # core
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1903, )  # 6tisch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1132, )  # manet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1897, )  # 6lo
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1404, )  # rtgarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1991, )  # t2trg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2175, )  # cbor
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1817, )  # lwig
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1723, )  # 6man
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1665, )  # intarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1619, )  # rtgwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2148, )  # lpwan
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=115213, )  # Ines Robles
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=109802, )  # Alvaro Retana
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105620, )  # Peter Van der Stok
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=102254, )  # Michael Richardson
                
                ## session for bfcpbis ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1832,  # bfcpbis
                    attendees=None,
                    agenda_note="",
                    requested_duration=datetime.timedelta(0),  # 0:00:00
                    comments="""""",
                    remote_instructions="",
                )
                
                ## session for saag ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1187,  # saag
                    attendees=150,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1921, )  # ace
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2194, )  # teep
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1674, )  # emu
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2220, )  # mls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2211, )  # suit
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1996, )  # dots
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1831, )  # mile
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2169, )  # secevent
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2143, )  # curdle
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2164, )  # lamps
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2219, )  # secdispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2002, )  # cose
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1920, )  # trans
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1634, )  # kitten
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1869, )  # sacm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=31, )  # cfrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1990, )  # tokbind
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1740, )  # ipsecme
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2231, )  # rats
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1995, )  # acme
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1965, )  # i2nsf
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1748, )  # oauth
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2166, )  # sidrops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1958, )  # dprive
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1892, )  # dmarc
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2227, )  # pearg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1918, )  # uta
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1853, )  # irtfopen
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=115214, )  # Benjamin Kaduk
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105815, )  # Roman Danyliw
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='timerange')
                c.timeranges.set(TimerangeName.objects.exclude(slug__startswith='thursday-early-afternoon'))
                
                ## session for mpls ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1140,  # mpls
                    attendees=100,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1962, )  # detnet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1905, )  # spring
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1960, )  # bess
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1628, )  # bfd
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1910, )  # sfc
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1041, )  # idr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1985, )  # teas
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1969, )  # pals
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1524, )  # ccamp
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1964, )  # bier
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1630, )  # pce
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2216, )  # lsvr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2215, )  # lsr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1840, )  # nvo3
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1875, )  # i2rs
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1404, )  # rtgarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1619, )  # rtgwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=108187, )  # Nicolai Leymann
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=106471, )  # Deborah Brungard
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=20682, )  # Loa Andersson
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=125952, )  # Mach(Guoyi) Chen
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=116516, )  # Tarek Saad
                
                ## session for pce ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1630,  # pce
                    attendees=75,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""Do not schedule against RTG area BOF (if any)""",  # this is implicit
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1905, )  # spring
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1524, )  # ccamp
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1985, )  # teas
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2202, )  # panrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1964, )  # bier
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2214, )  # rift
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1969, )  # pals
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1140, )  # mpls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1910, )  # sfc
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1723, )  # 6man
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2215, )  # lsr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1638, )  # netmod
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1041, )  # idr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1575, )  # netconf
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1962, )  # detnet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1960, )  # bess
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1619, )  # rtgwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1714, )  # opsawg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=108213, )  # Julien Meuric
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=106471, )  # Deborah Brungard
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=115798, )  # Hariharan Ananthakrishnan
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=111477, )  # Dhruv Dhody
                
                ## session for detnet ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1962,  # detnet
                    attendees=100,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=9000),  # 2:30:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1630, )  # pce
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1140, )  # mpls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1638, )  # netmod
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1985, )  # teas
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2215, )  # lsr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1463, )  # tsvwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1524, )  # ccamp
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1910, )  # sfc
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1619, )  # rtgwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1969, )  # pals
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1960, )  # bess
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1628, )  # bfd
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1840, )  # nvo3
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=124759, )  # Ethan Grossman
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=118295, )  # Janos Farkas
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=106471, )  # Deborah Brungard
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=103156, )  # David Black
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=10064, )  # Lou Berger
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='timerange')
                c.timeranges.set(TimerangeName.objects.filter(slug__startswith='monday'))
                
                ## session for alto ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1744,  # alto
                    attendees=25,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1849, )  # icnrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2145, )  # maprg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2202, )  # panrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1679, )  # tsvarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=38, )  # nmrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=112330, )  # Mirja Kühlewind
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=108807, )  # Jan Seedorf
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=106812, )  # Vijay Gurbani
                
                ## session for gaia ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1968,  # gaia
                    attendees=60,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=117577, )  # Leandro Navarro
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=123022, )  # Jane Coffin
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='timerange')
                c.timeranges.set(TimerangeName.objects.filter(slug__startswith='friday'))
                
                ## session for git ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2233,  # git
                    attendees=65,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=3600),  # 1:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1452, )  # dnsop
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2227, )  # pearg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1958, )  # dprive
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1905, )  # spring
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1956, )  # anima
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1803, )  # homenet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1895, )  # dnssd
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2220, )  # mls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2150, )  # babel
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1995, )  # acme
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1718, )  # httpbis
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=121595, )  # Christopher Wood
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=110077, )  # Alissa Cooper
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=10083, )  # Paul Hoffman
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2253, )  # abcd
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2256, )  # raw
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2254, )  # wpack
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2258, )  # mathmesh
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2257, )  # txauth
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2255, )  # tmrid
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2260, )  # webtrans
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1399, )  # opsarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1404, )  # rtgarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1619, )  # rtgwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1625, )  # genarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1665, )  # intarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1679, )  # tsvarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1763, )  # dispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1853, )  # irtfopen
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2017, )  # artarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2219, )  # secdispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2252, )  # gendispatch
                
                ## session for pearg ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2227,  # pearg
                    attendees=120,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1988, )  # hrpc
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2233, )  # git
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2228, )  # qirg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1853, )  # irtfopen
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=31, )  # cfrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1958, )  # dprive
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1452, )  # dnsop
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1895, )  # dnssd
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1718, )  # httpbis
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2220, )  # mls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=123472, )  # Shivan Sahib
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=121595, )  # Christopher Wood
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=112423, )  # Sara Dickinson
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='timerange')
                c.timeranges.set(TimerangeName.objects.exclude(slug__startswith='monday').exclude(slug__startswith='tuesday'))
                
                ## session for tls ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1326,  # tls
                    attendees=120,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                ## session for tls ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1326,  # tls
                    attendees=120,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=3600),  # 1:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2227, )  # pearg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2239, )  # cacao
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1674, )  # emu
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2220, )  # mls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2233, )  # git
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1958, )  # dprive
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=31, )  # cfrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2249, )  # lake
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1452, )  # dnsop
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2219, )  # secdispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1924, )  # taps
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1718, )  # httpbis
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=115214, )  # Benjamin Kaduk
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=106745, )  # Yoav Nir
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=101208, )  # Joseph Salowey
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=19483, )  # Sean Turner
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=18427, )  # Rich Salz
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=122298, )  # Nick Sullivan
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=12695, )  # Eric Rescorla
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=121595, )  # Christopher Wood
                
                ## session for tsvarea ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1679,  # tsvarea
                    attendees=120,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=3600),  # 1:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1744, )  # alto
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1924, )  # taps
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1838, )  # rmcat
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1152, )  # nfsv4
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1966, )  # dtn
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1764, )  # mptcp
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1463, )  # tsvwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1089, )  # ippm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1926, )  # tram
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2145, )  # maprg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1620, )  # tcpm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=42, )  # iccrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1763, )  # dispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2202, )  # panrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1853, )  # irtfopen
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2017, )  # artarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2219, )  # secdispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1665, )  # intarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=112330, )  # Mirja Kühlewind
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=104294, )  # Magnus Westerlund
                
                ## session for secevent ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2169,  # secevent
                    attendees=None,
                    agenda_note="",
                    requested_duration=datetime.timedelta(0),  # 0:00:00
                    comments="""""",
                    remote_instructions="",
                )
                
                ## session for dinrg ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2209,  # dinrg
                    attendees=90,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1853, )  # irtfopen
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1988, )  # hrpc
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1883, )  # nwcrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2234, )  # coinrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1991, )  # t2trg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=31, )  # cfrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=20209, )  # Colin Perkins
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=102174, )  # Dirk Kutscher
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=101104, )  # Melinda Shore
                
                ## session for opsawg ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1714,  # opsawg
                    attendees=70,
                    agenda_note="Combined OpsAWG / OpsAREA",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""PLEASE NOTE: Combined OpsAWG / OpsAREA""",
                    remote_instructions="",
                )
                s.joint_with_groups.set(Group.objects.filter(acronym='opsarea'))
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1089, )  # ippm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1905, )  # spring
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1723, )  # 6man
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1638, )  # netmod
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1575, )  # netconf
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1619, )  # rtgwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1041, )  # idr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1584, )  # grow
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=118100, )  # Ignas Bagdonas
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=117721, )  # Tianran Zhou
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=113086, )  # Joe Clarke
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=111656, )  # Warren Kumari
                
                ## session for avtcore ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1812,  # avtcore
                    attendees=30,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=3600),  # 1:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2017, )  # artarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2248, )  # mops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1679, )  # tsvarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1463, )  # tsvwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=42, )  # iccrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1763, )  # dispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1816, )  # clue
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1815, )  # xrblock
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1762, )  # sipcore
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2013, )  # perc
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1814, )  # payload
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1138, )  # mmusic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2250, )  # loops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1924, )  # taps
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1838, )  # rmcat
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=111749, )  # Rachel Huang
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105873, )  # Roni Even
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=101923, )  # Jonathan Lennox
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=21684, )  # Barry Leiba
                
                ## session for kitten ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1634,  # kitten
                    attendees=None,
                    agenda_note="",
                    requested_duration=datetime.timedelta(0),  # 0:00:00
                    comments="""""",
                    remote_instructions="",
                )
                
                ## session for clue ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1816,  # clue
                    attendees=None,
                    agenda_note="",
                    requested_duration=datetime.timedelta(0),  # 0:00:00
                    comments="""""",
                    remote_instructions="",
                )
                
                ## session for payload ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1814,  # payload
                    attendees=None,
                    agenda_note="",
                    requested_duration=datetime.timedelta(0),  # 0:00:00
                    comments="""""",
                    remote_instructions="",
                )
                
                ## session for bfd ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1628,  # bfd
                    attendees=50,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=3600),  # 1:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1041, )  # idr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1575, )  # netconf
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1638, )  # netmod
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1751, )  # lisp
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1960, )  # bess
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1619, )  # rtgwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1584, )  # grow
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1910, )  # sfc
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1969, )  # pals
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1985, )  # teas
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1140, )  # mpls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1905, )  # spring
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1964, )  # bier
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1524, )  # ccamp
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=108279, )  # Martin Vigoureux
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=106444, )  # Reshad Rahman
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105046, )  # Jeffrey Haas
                
                ## session for emu ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1674,  # emu
                    attendees=50,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1817, )  # lwig
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=31, )  # cfrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2219, )  # secdispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1918, )  # uta
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2249, )  # lake
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2143, )  # curdle
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2227, )  # pearg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1991, )  # t2trg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2220, )  # mls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1748, )  # oauth
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1869, )  # sacm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1897, )  # 6lo
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1995, )  # acme
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1964, )  # bier
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1634, )  # kitten
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=101208, )  # Joseph Salowey
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=21072, )  # Jari Arkko
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=113142, )  # Mohit Sethi
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=109330, )  # John Mattsson
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=108624, )  # Alan DeKok
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105815, )  # Roman Danyliw
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='timerange')
                c.timeranges.set(TimerangeName.objects.exclude(slug__startswith='monday').exclude(slug__startswith='tuesday').exclude(slug='wednesday-morning'))
                
                ## session for hrpc ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1988,  # hrpc
                    attendees=100,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1958, )  # dprive
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2227, )  # pearg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1853, )  # irtfopen
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1968, )  # gaia
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2146, )  # regext
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2208, )  # doh
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2220, )  # mls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1452, )  # dnsop
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2015, )  # capport
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=124328, )  # Mallory Knodel
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=3747, )  # Avri Doria
                
                ## session for cose ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2002,  # cose
                    attendees=60,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1789, )  # core
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1991, )  # t2trg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2219, )  # secdispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2148, )  # lpwan
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2164, )  # lamps
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1763, )  # dispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2194, )  # teep
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2231, )  # rats
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=31, )  # cfrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2175, )  # cbor
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1921, )  # ace
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=111178, )  # Matthew Miller
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=123715, )  # Ivaylo Petrov
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=115214, )  # Benjamin Kaduk
                
                ## session for dots ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1996,  # dots
                    attendees=50,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1956, )  # anima
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2211, )  # suit
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2231, )  # rats
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2164, )  # lamps
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1740, )  # ipsecme
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1965, )  # i2nsf
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1918, )  # uta
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=31, )  # cfrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=115214, )  # Benjamin Kaduk
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=111620, )  # Liang Xia
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=103686, )  # Valery Smyslov
                
                ## session for idr ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1041,  # idr
                    attendees=75,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=3600),  # 1:00:00
                    comments="""""",
                    remote_instructions="",
                )
                ## session for idr ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1041,  # idr
                    attendees=75,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=3600),  # 1:00:00
                    comments="""""",
                    remote_instructions="",
                )
                s.joint_with_groups.set(Group.objects.filter(acronym__in=['i2nsf', 'ipsecme', 'bess']))
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2215, )  # lsr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1584, )  # grow
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2166, )  # sidrops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1960, )  # bess
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1619, )  # rtgwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1905, )  # spring
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2216, )  # lsvr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1628, )  # bfd
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1638, )  # netmod
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1575, )  # netconf
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=109802, )  # Alvaro Retana
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=4836, )  # John Scudder
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=3056, )  # Susan Hares
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='timerange')
                c.timeranges.set(TimerangeName.objects.filter(slug__startswith='friday'))
                
                ## session for bmwg ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=945,  # bmwg
                    attendees=30,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                s.resources.set(ResourceAssociation.objects.filter(pk__in=[6]))  # [<ResourceAssociation: Experimental Room Setup (U-Shape and classroom, subject to availability)>]
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1089, )  # ippm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1463, )  # tsvwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1853, )  # irtfopen
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1958, )  # dprive
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1964, )  # bier
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1960, )  # bess
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1679, )  # tsvarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2145, )  # maprg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=111656, )  # Warren Kumari
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=110785, )  # Sarah Banks
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=102900, )  # Al Morton
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='timerange')
                c.timeranges.set(TimerangeName.objects.filter(slug__startswith='friday'))
                
                ## session for panrg ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2202,  # panrg
                    attendees=75,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2166, )  # sidrops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1905, )  # spring
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1723, )  # 6man
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1578, )  # v6ops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2145, )  # maprg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1924, )  # taps
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1679, )  # tsvarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1089, )  # ippm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1665, )  # intarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1630, )  # pce
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1620, )  # tcpm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1463, )  # tsvwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1404, )  # rtgarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1619, )  # rtgwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1744, )  # alto
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1853, )  # irtfopen
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=122661, )  # Jen Linkova
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=109354, )  # Brian Trammell
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=107190, )  # Spencer Dawkins
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=123344, )  # Theresa Enghardt
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2250, )  # loops
                
                ## session for nmrg ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=38,  # nmrg
                    attendees=80,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                ## session for nmrg ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=38,  # nmrg
                    attendees=80,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1956, )  # anima
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1714, )  # opsawg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1399, )  # opsarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1853, )  # irtfopen
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1638, )  # netmod
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1575, )  # netconf
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1619, )  # rtgwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2234, )  # coinrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=121666, )  # Jérôme François
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=108591, )  # Laurent Ciavaglia
                
                ## session for softwire ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1678,  # softwire
                    attendees=None,
                    agenda_note="",
                    requested_duration=datetime.timedelta(0),  # 0:00:00
                    comments="""""",
                    remote_instructions="",
                )
                
                ## session for intarea ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1665,  # intarea
                    attendees=60,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2148, )  # lpwan
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=988, )  # dhc
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1897, )  # 6lo
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1578, )  # v6ops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1723, )  # 6man
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1847, )  # dmm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1903, )  # 6tisch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1991, )  # t2trg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1463, )  # tsvwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1452, )  # dnsop
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1575, )  # netconf
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=106199, )  # Wassim Haddad
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=108573, )  # Juan-Carlos Zúñiga
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=106412, )  # Suresh Krishnan
                
                ## session for lwig ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1817,  # lwig
                    attendees=50,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=3600),  # 1:00:00
                    comments="""Eric Vyncke's presence is a strong wish only (not a strict requirement) as he may take responsibility of this WG.""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1674, )  # emu
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1730, )  # roll
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1764, )  # mptcp
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2148, )  # lpwan
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1897, )  # 6lo
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1620, )  # tcpm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1903, )  # 6tisch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1991, )  # t2trg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1921, )  # ace
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1789, )  # core
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2249, )  # lake
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2219, )  # secdispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=113142, )  # Mohit Sethi
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=110531, )  # Zhen Cao
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=108990, )  # Ari Keränen
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=106412, )  # Suresh Krishnan
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105099, )  # Éric Vyncke
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=11843, )  # Carsten Bormann
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='timerange')
                c.timeranges.set(TimerangeName.objects.exclude(slug__startswith='monday').exclude(slug__startswith='tuesday'))
                
                ## session for rtgwg ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1619,  # rtgwg
                    attendees=150,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""No overlap with other Routing Area workings groups.""",  # implicit, rtgwg meeting_seen_as_area set
                    remote_instructions="",
                )
                ## session for rtgwg ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1619,  # rtgwg
                    attendees=150,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""No overlap with other Routing Area workings groups.""",  # implicit, rtgwg meeting_seen_as_area set
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2214, )  # rift
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2166, )  # sidrops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1575, )  # netconf
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1584, )  # grow
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=38, )  # nmrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1723, )  # 6man
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=108279, )  # Martin Vigoureux
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=114478, )  # Chris Bowers
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=112405, )  # Jeff Tantsura
                
                ## session for rift ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2214,  # rift
                    attendees=70,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1619, )  # rtgwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2216, )  # lsvr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1964, )  # bier
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1905, )  # spring
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1041, )  # idr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2215, )  # lsr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1960, )  # bess
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1630, )  # pce
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1140, )  # mpls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1628, )  # bfd
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1985, )  # teas
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=110966, )  # Zhaohui Zhang
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=109802, )  # Alvaro Retana
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=112405, )  # Jeff Tantsura
                
                ## session for uta ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1918,  # uta
                    attendees=None,
                    agenda_note="",
                    requested_duration=datetime.timedelta(0),  # 0:00:00
                    comments="""""",
                    remote_instructions="",
                )
                
                ## session for spring ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1905,  # spring
                    attendees=140,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""If it's not possible to address all conflicts, chairs will try to schedule 6MAN related content in the first session and MPLS related content during the second session.""",
                    remote_instructions="",
                )
                ## session for spring ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1905,  # spring
                    attendees=140,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=3600),  # 1:00:00
                    comments="""If it's not possible to address all conflicts, chairs will try to schedule 6MAN related content in the first session and MPLS related content during the second session.""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1723, )  # 6man
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1630, )  # pce
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1041, )  # idr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2215, )  # lsr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1140, )  # mpls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=108279, )  # Martin Vigoureux
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=107172, )  # Bruno Decraene
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=116387, )  # Rob Shakir
                
                ## session for nfsv4 ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1152,  # nfsv4
                    attendees=None,
                    agenda_note="",
                    requested_duration=datetime.timedelta(0),  # 0:00:00
                    comments="""""",
                    remote_instructions="",
                )
                
                ## session for dhc ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=988,  # dhc
                    attendees=25,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""Eric Vyncke's presence is a strong wish as he may take responsibility of this WG.""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1452, )  # dnsop
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1723, )  # 6man
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1578, )  # v6ops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2208, )  # doh
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1958, )  # dprive
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1803, )  # homenet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1966, )  # dtn
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1678, )  # softwire
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1575, )  # netconf
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1665, )  # intarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=106618, )  # Bernie Volz
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=106412, )  # Suresh Krishnan
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105099, )  # Éric Vyncke
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=110805, )  # Tomek Mrugalski
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='timerange')
                c.timeranges.set(TimerangeName.objects.filter(slug__startswith='friday'))
                
                ## session for ipsecme ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1740,  # ipsecme
                    attendees=50,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2211, )  # suit
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1620, )  # tcpm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=31, )  # cfrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2143, )  # curdle
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1965, )  # i2nsf
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1921, )  # ace
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1817, )  # lwig
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1903, )  # 6tisch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1897, )  # 6lo
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1918, )  # uta
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=110121, )  # Tero Kivinen
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=115214, )  # Benjamin Kaduk
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=111953, )  # David Waltermire
                
                ## session for regext ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2146,  # regext
                    attendees=50,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2239, )  # cacao
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2208, )  # doh
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1869, )  # sacm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2246, )  # add
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1958, )  # dprive
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1452, )  # dnsop
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1988, )  # hrpc
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1895, )  # dnssd
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=114834, )  # Antoin Verschuren
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=21684, )  # Barry Leiba
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=2783, )  # James Galvin
                
                ## session for cfrg ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=31,  # cfrg
                    attendees=150,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""Please also avoid conflicts with Security Area WG.""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1831, )  # mile
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2176, )  # jmap
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2220, )  # mls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1918, )  # uta
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2227, )  # pearg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2164, )  # lamps
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2211, )  # suit
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2205, )  # extra
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2219, )  # secdispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1763, )  # dispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=122298, )  # Nick Sullivan
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=113609, )  # Kenny Paterson
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=102154, )  # Alexey Melnikov
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2258, )  # mathmesh
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2257, )  # txauth
                # All security WGs not already listed as conflicts:
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1634)  # kitten
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1674)  # emu
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1740)  # ipsecme
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1748)  # oauth
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1869)  # sacm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1920)  # trans
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1921)  # ace
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1965)  # i2nsf
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1990)  # tokbind
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1995)  # acme
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1996)  # dots
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2002)  # cose
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2143)  # curdle
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2169)  # secevent
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2194)  # teep
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2231)  # rats
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2249)  # lake
                
                ## session for icnrg ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1849,  # icnrg
                    attendees=80,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2209, )  # dinrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1744, )  # alto
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1883, )  # nwcrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2234, )  # coinrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1853, )  # irtfopen
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1463, )  # tsvwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2202, )  # panrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1665, )  # intarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=102174, )  # Dirk Kutscher
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=18250, )  # Börje Ohlman
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=773, )  # David Oran
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='timerange')
                c.timeranges.set(TimerangeName.objects.exclude(slug__startswith='monday').exclude(slug__startswith='tuesday'))
                
                ## session for dmm ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1847,  # dmm
                    attendees=45,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2167, )  # ipwave
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=114978, )  # Satoru Matsushima
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=109589, )  # Dapeng Liu
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=106412, )  # Suresh Krishnan
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=101641, )  # Sri Gundavelli
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='timerange')
                c.timeranges.set(TimerangeName.objects.exclude(slug__startswith='monday').exclude(slug__startswith='tuesday'))
                
                ## session for jmap ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2176,  # jmap
                    attendees=20,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=3600),  # 1:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2208, )  # doh
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1918, )  # uta
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2017, )  # artarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1892, )  # dmarc
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2221, )  # iasa2
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1953, )  # calext
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2205, )  # extra
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1748, )  # oauth
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1763, )  # dispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1921, )  # ace
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1718, )  # httpbis
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1991, )  # t2trg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1789, )  # core
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2164, )  # lamps
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=122671, )  # Bron Gondwana
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=122525, )  # Neil Jenkins
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=121191, )  # Jim Fenton
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=102154, )  # Alexey Melnikov
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='timerange')
                c.timeranges.set(TimerangeName.objects.filter(slug__startswith='friday'))
                
                ## session for calext ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1953,  # calext
                    attendees=15,
                    agenda_note="1330 - 1430",
                    requested_duration=datetime.timedelta(seconds=3600),  # 1:00:00
                    comments="""We will need to make possible remote participation""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1740, )  # ipsecme
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2176, )  # jmap
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1452, )  # dnsop
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1817, )  # lwig
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1921, )  # ace
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2205, )  # extra
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=122671, )  # Bron Gondwana
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=109969, )  # Daniel Migault
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=21684, )  # Barry Leiba
                
                ## session for cbor ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2175,  # cbor
                    attendees=50,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""Please avoid collision with any Sec and IoT-related BoFs.""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2249, )  # lake
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2002, )  # cose
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2164, )  # lamps
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1789, )  # core
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1921, )  # ace
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2231, )  # rats
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1956, )  # anima
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1897, )  # 6lo
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1903, )  # 6tisch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1817, )  # lwig
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2194, )  # teep
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2148, )  # lpwan
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2211, )  # suit
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1991, )  # t2trg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1748, )  # oauth
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1452, )  # dnsop
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2219, )  # secdispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1996, )  # dots
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1869, )  # sacm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1674, )  # emu
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1730, )  # roll
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=31, )  # cfrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2250, )  # loops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2017, )  # artarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=119822, )  # Francesca Palombini
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=110910, )  # Jim Schaad
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=102154, )  # Alexey Melnikov
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=11843, )  # Carsten Bormann
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2254, )  # wpack
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2252, )  # gendispatch
                
                ## session for rum ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2242,  # rum
                    attendees=20,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=3600),  # 1:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1812, )  # avtcore
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1138, )  # mmusic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1643, )  # ecrit
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1762, )  # sipcore
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1994, )  # modern
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1763, )  # dispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=108554, )  # Paul Kyzivat
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=106987, )  # Brian Rosen
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=103769, )  # Adam Roach
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='timerange')
                c.timeranges.set(TimerangeName.objects.filter(Q(slug__startswith='friday') | Q(slug='tuesday-morning')))
                
                ## session for mls ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2220,  # mls
                    attendees=125,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=31, )  # cfrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2219, )  # secdispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1718, )  # httpbis
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2221, )  # iasa2
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2227, )  # pearg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2013, )  # perc
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1763, )  # dispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2017, )  # artarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1995, )  # acme
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=12695, )  # Eric Rescorla
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=122298, )  # Nick Sullivan
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=115214, )  # Benjamin Kaduk
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=108049, )  # Richard Barnes
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=19483, )  # Sean Turner
                
                ## session for extra ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2205,  # extra
                    attendees=15,
                    agenda_note="1430 - 1530",
                    requested_duration=datetime.timedelta(seconds=3600),  # 1:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2176, )  # jmap
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1763, )  # dispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1953, )  # calext
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=122671, )  # Bron Gondwana
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=107279, )  # Jiankang Yao
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=102154, )  # Alexey Melnikov
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=21684, )  # Barry Leiba
                
                ## session for sipcore ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1762,  # sipcore
                    attendees=None,
                    agenda_note="",
                    requested_duration=datetime.timedelta(0),  # 0:00:00
                    comments="""""",
                    remote_instructions="",
                )
                
                ## session for manet ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1132,  # manet
                    attendees=20,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1966, )  # dtn
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2215, )  # lsr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1985, )  # teas
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1404, )  # rtgarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1730, )  # roll
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=109802, )  # Alvaro Retana
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=19150, )  # Stan Ratliff
                
                ## session for rmcat ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1838,  # rmcat
                    attendees=30,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=3600),  # 1:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1853, )  # irtfopen
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1463, )  # tsvwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1679, )  # tsvarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1763, )  # dispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1924, )  # taps
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2017, )  # artarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1138, )  # mmusic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2145, )  # maprg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=42, )  # iccrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1812, )  # avtcore
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1620, )  # tcpm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=20209, )  # Colin Perkins
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=114993, )  # Anna Brunstrom
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=112330, )  # Mirja Kühlewind
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105519, )  # Martin Stiemerling
                
                ## session for anima ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1956,  # anima
                    attendees=80,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""It would be nice to have the 1.5 hour meeting first.""",  # this is default
                    remote_instructions="",
                )
                ## session for anima ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1956,  # anima
                    attendees=80,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=3600),  # 1:00:00
                    comments="""It would be nice to have the 1.5 hour meeting first.""",  # this is default
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1964, )  # bier
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1921, )  # ace
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1903, )  # 6tisch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1897, )  # 6lo
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1723, )  # 6man
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1118, )  # mboned
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1397, )  # pim
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1575, )  # netconf
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1803, )  # homenet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1730, )  # roll
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1674, )  # emu
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2202, )  # panrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2209, )  # dinrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1399, )  # opsarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1665, )  # intarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1962, )  # detnet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=31, )  # cfrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=38, )  # nmrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=118100, )  # Ignas Bagdonas
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=108054, )  # Sheng Jiang
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=11834, )  # Toerless Eckert
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='timerange')
                c.timeranges.set(TimerangeName.objects.filter(slug__startswith='friday'))
                
                ## session for mmusic ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1138,  # mmusic
                    attendees=None,
                    agenda_note="",
                    requested_duration=datetime.timedelta(0),  # 0:00:00
                    comments="""""",
                    remote_instructions="",
                )
                
                ## session for ntp ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1642,  # ntp
                    attendees=30,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1869, )  # sacm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1853, )  # irtfopen
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1962, )  # detnet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=945, )  # bmwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1089, )  # ippm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=31, )  # cfrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2220, )  # mls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1748, )  # oauth
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=113902, )  # Dieter Sibold
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=106412, )  # Suresh Krishnan
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=4857, )  # Karen O'Donoghue
                
                ## session for tictoc ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1709,  # tictoc
                    attendees=None,
                    agenda_note="",
                    requested_duration=datetime.timedelta(0),  # 0:00:00
                    comments="""""",
                    remote_instructions="",
                )
                
                ## session for oauth ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1748,  # oauth
                    attendees=50,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""""",
                    remote_instructions="",
                )
                ## session for oauth ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1748,  # oauth
                    attendees=50,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1995, )  # acme
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1956, )  # anima
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1762, )  # sipcore
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2231, )  # rats
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2169, )  # secevent
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1921, )  # ace
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1990, )  # tokbind
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1789, )  # core
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2211, )  # suit
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2194, )  # teep
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105815, )  # Roman Danyliw
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=111355, )  # Rifaat Shekh-Yusef
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105857, )  # Hannes Tschofenig
                
                ## session for sacm ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1869,  # sacm
                    attendees=30,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=31, )  # cfrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1642, )  # ntp
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1831, )  # mile
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1575, )  # netconf
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1965, )  # i2nsf
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2211, )  # suit
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1996, )  # dots
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2239, )  # cacao
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1789, )  # core
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2169, )  # secevent
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1748, )  # oauth
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1740, )  # ipsecme
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1956, )  # anima
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=113536, )  # Christopher Inacio
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=111953, )  # David Waltermire
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105815, )  # Roman Danyliw
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=4857, )  # Karen O'Donoghue
                
                ## session for bier ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1964,  # bier
                    attendees=30,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1140, )  # mpls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1905, )  # spring
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1730, )  # roll
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1118, )  # mboned
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2215, )  # lsr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1397, )  # pim
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=104151, )  # Tony Przygienda
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=109802, )  # Alvaro Retana
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=106315, )  # Greg Shepherd
                
                ## session for teas ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1985,  # teas
                    attendees=100,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=9000),  # 2:30:00
                    comments="""Other Conflicts: IRTF RRG, RTG BOFs""",  # RTG BOF constraint is implicit
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1524, )  # ccamp
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1962, )  # detnet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1638, )  # netmod
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1630, )  # pce
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1140, )  # mpls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1875, )  # i2rs
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1041, )  # idr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2215, )  # lsr
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1905, )  # spring
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1840, )  # nvo3
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1960, )  # bess
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1969, )  # pals
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=10064, )  # Lou Berger
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=114351, )  # Vishnu Beeram
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=106471, )  # Deborah Brungard
                
                ## session for netmod ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1638,  # netmod
                    attendees=100,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                ## session for netmod ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1638,  # netmod
                    attendees=100,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=3600),  # 1:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1575, )  # netconf
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1985, )  # teas
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1875, )  # i2rs
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1619, )  # rtgwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=20959, )  # Joel Jaeggli
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=10064, )  # Lou Berger
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=118100, )  # Ignas Bagdonas
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=112548, )  # Kent Watsen
                
                ## session for core ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1789,  # core
                    attendees=60,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""Plse also avd any potntlly IoT reltd BOFs&PRGs tht mght cme up.
                Second meeting often is 40 people.""",
                    remote_instructions="",
                )
                ## session for core ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1789,  # core
                    attendees=60,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""Plse also avd any potntlly IoT reltd BOFs&PRGs tht mght cme up.
                Second meeting often is 40 people.""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2175, )  # cbor
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2250, )  # loops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2249, )  # lake
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2231, )  # rats
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2017, )  # artarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2002, )  # cose
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1991, )  # t2trg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2148, )  # lpwan
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1869, )  # sacm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1718, )  # httpbis
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2219, )  # secdispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1730, )  # roll
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1897, )  # 6lo
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1817, )  # lwig
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1903, )  # 6tisch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2211, )  # suit
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1853, )  # irtfopen
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1921, )  # ace
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2194, )  # teep
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1895, )  # dnssd
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1962, )  # detnet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1956, )  # anima
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1849, )  # icnrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1996, )  # dots
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=31, )  # cfrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1674, )  # emu
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2209, )  # dinrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1638, )  # netmod
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2234, )  # coinrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1575, )  # netconf
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=102154, )  # Alexey Melnikov
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=11843, )  # Carsten Bormann
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=113152, )  # Jaime Jimenez
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='time_relation', time_relation='one-day-seperation')
                
                ## session for t2trg ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1991,  # t2trg
                    attendees=90,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""Please also avoid any potentially IoT related BOFs that might come up
                """,
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2175, )  # cbor
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2250, )  # loops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2249, )  # lake
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2017, )  # artarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2021, )  # ice
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2231, )  # rats
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1789, )  # core
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1817, )  # lwig
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1869, )  # sacm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1730, )  # roll
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1903, )  # 6tisch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1897, )  # 6lo
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2234, )  # coinrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2148, )  # lpwan
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2209, )  # dinrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1718, )  # httpbis
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1853, )  # irtfopen
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2219, )  # secdispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1956, )  # anima
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2194, )  # teep
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1578, )  # v6ops
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1674, )  # emu
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1638, )  # netmod
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1895, )  # dnssd
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1575, )  # netconf
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1849, )  # icnrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1965, )  # i2nsf
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=31, )  # cfrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1665, )  # intarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1399, )  # opsarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=11843, )  # Carsten Bormann
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=108990, )  # Ari Keränen
                
                ## session for i2nsf ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1965,  # i2nsf
                    attendees=None,
                    agenda_note="",
                    requested_duration=datetime.timedelta(0),  # 0:00:00
                    comments="""""",
                    remote_instructions="",
                )
                
                ## session for ace ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1921,  # ace
                    attendees=50,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1740, )  # ipsecme
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2164, )  # lamps
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1789, )  # core
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2175, )  # cbor
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2219, )  # secdispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=2002, )  # cose
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1674, )  # emu
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1817, )  # lwig
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=31, )  # cfrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1803, )  # homenet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1748, )  # oauth
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2194, )  # teep
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2211, )  # suit
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1991, )  # t2trg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=2252, )  # gendispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1903, )  # 6tisch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic3', target_id=1956, )  # anima
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=109969, )  # Daniel Migault
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=115214, )  # Benjamin Kaduk
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=110910, )  # Jim Schaad
                
                ## session for wpack ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2254,  # wpack
                    attendees=150,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1718, )  # httpbis
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1995, )  # acme
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2219, )  # secdispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1763, )  # dispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=102154, )  # Alexey Melnikov
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='timerange')
                c.timeranges.set(TimerangeName.objects.filter(slug='monday-morning'))
                
                ## session for webtrans ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2260,  # webtrans
                    attendees=100,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1924, )  # taps
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1679, )  # tsvarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1895, )  # dnssd
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1789, )  # core
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1718, )  # httpbis
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2021, )  # ice
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=21684, )  # Barry Leiba
                
                ## session for abcd ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2253,  # abcd
                    attendees=200,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1958, )  # dprive
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2017, )  # artarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1452, )  # dnsop
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=21684, )  # Barry Leiba
                
                ## session for tmrid ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2255,  # tmrid
                    attendees=30,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=31, )  # cfrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2002, )  # cose
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1991, )  # t2trg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2231, )  # rats
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1956, )  # anima
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1740, )  # ipsecme
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105099, )  # Éric Vyncke
                
                ## session for mops ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2248,  # mops
                    attendees=100,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2208, )  # doh
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1958, )  # dprive
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1718, )  # httpbis
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1678, )  # softwire
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1138, )  # mmusic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1803, )  # homenet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1397, )  # pim
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1626, )  # hip
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1118, )  # mboned
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1895, )  # dnssd
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1822, )  # cdni
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1924, )  # taps
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=109223, )  # Leslie Daigle
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105099, )  # Éric Vyncke
                
                ## session for raw ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2256,  # raw
                    attendees=100,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1903, )  # 6tisch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1524, )  # ccamp
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1964, )  # bier
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1905, )  # spring
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1132, )  # manet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2148, )  # lpwan
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1962, )  # detnet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=106471, )  # Deborah Brungard
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='timerange')
                c.timeranges.set(TimerangeName.objects.filter(slug__startswith='monday'))
                
                ## session for txauth ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2257,  # txauth
                    attendees=150,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1718, )  # httpbis
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2169, )  # secevent
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2143, )  # curdle
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2164, )  # lamps
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2219, )  # secdispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2002, )  # cose
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1920, )  # trans
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1634, )  # kitten
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1869, )  # sacm
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1995, )  # acme
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1990, )  # tokbind
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1740, )  # ipsecme
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2231, )  # rats
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1921, )  # ace
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1965, )  # i2nsf
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1748, )  # oauth
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2194, )  # teep
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1674, )  # emu
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2220, )  # mls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2211, )  # suit
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1996, )  # dots
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1831, )  # mile
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105815, )  # Roman Danyliw
                
                ## session for rseme ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2259,  # rseme
                    attendees=150,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""Please avoid other BoFs, and minimize conflicts for attendees.""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2233, )  # git
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2147, )  # mtgvenue
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2221, )  # iasa2
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2252, )  # gendispatch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=113431, )  # Heather Flanagan
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2253, )  # abcd
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2256, )  # raw
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2254, )  # wpack
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2258, )  # mathmesh
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2257, )  # txauth
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2255, )  # tmrid
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2260, )  # webtrans
                
                ## session for gendispatch ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2252,  # gendispatch
                    attendees=75,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=3600),  # 1:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2017, )  # artarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2161, )  # quic
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2253, )  # abcd
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2258, )  # mathmesh
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2249, )  # lake
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1326, )  # tls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2256, )  # raw
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1789, )  # core
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1905, )  # spring
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2255, )  # tmrid
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1921, )  # ace
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1714, )  # opsawg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2257, )  # txauth
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2175, )  # cbor
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1956, )  # anima
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2260, )  # webtrans
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1625, )  # genarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1958, )  # dprive
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2254, )  # wpack
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=18321, )  # Pete Resnick
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=119822, )  # Francesca Palombini
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=110077, )  # Alissa Cooper
                
                ## session for dtn ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1966,  # dtn
                    attendees=30,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2256, )  # raw
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1132, )  # manet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=38, )  # nmrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1679, )  # tsvarea
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1463, )  # tsvwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=104294, )  # Magnus Westerlund
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=19869, )  # Marc Blanchet
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=117656, )  # Rick Taylor
                
                ## session for lake ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2249,  # lake
                    attendees=100,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=5400),  # 1:30:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1730, )  # roll
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1817, )  # lwig
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2175, )  # cbor
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1789, )  # core
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2148, )  # lpwan
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1903, )  # 6tisch
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=115214, )  # Benjamin Kaduk
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=19177, )  # Stephen Farrell
                
                ## session for mathmesh ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2258,  # mathmesh
                    attendees=100,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=2254, )  # wpack
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=115214, )  # Benjamin Kaduk
                
                ## session for qirg ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2228,  # qirg
                    attendees=50,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=3600),  # 1:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1853, )  # irtfopen
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1187, )  # saag
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=31, )  # cfrg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=125147, )  # Stephanie Wehner
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=110694, )  # Rodney Van Meter
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='timerange')
                c.timeranges.set(TimerangeName.objects.filter(slug__in=[
                    'tuesday-afternoon-early', 'tuesday-afternoon-late', 'wednesday-morning',
                    'wednesday-afternoon-early', 'wednesday-afternoon-late', 'thursday-morning']))
                
                ## session for hotrfc ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=2225,  # hotrfc
                    attendees=200,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=7200),  # 2:00:00
                    comments="""""",
                    remote_instructions="",
                )
                
                ## session for nvo3 ##
                s = Session.objects.create(
                    meeting=m,
                    type_id="regular",
                    group_id=1840,  # nvo3
                    attendees=50,
                    agenda_note="",
                    requested_duration=datetime.timedelta(seconds=3600),  # 1:00:00
                    comments="""""",
                    remote_instructions="",
                )
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1905, )  # spring
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1960, )  # bess
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1619, )  # rtgwg
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflict', target_id=1910, )  # sfc
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='conflic2', target_id=1140, )  # mpls
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=108279, )  # Martin Vigoureux
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=105786, )  # Matthew Bocci
                c = Constraint.objects.create(meeting=m, source=s.group, name_id='bethere', person_id=112237, )  # Sam Aldrin
                
                ##### TIMESLOTS #####
                
                ## timeslot 2019-11-22 12:20:00 length 1:30:00 in Orchard size: 50 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session II", time=datetime.datetime(2019, 11, 22, 12, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Orchard"), show_location=True)
                ## timeslot 2019-11-22 12:20:00 length 1:30:00 in VIP A size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session II", time=datetime.datetime(2019, 11, 22, 12, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="VIP A"), show_location=True)
                ## timeslot 2019-11-22 12:20:00 length 1:30:00 in Hullet size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session II", time=datetime.datetime(2019, 11, 22, 12, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Hullet"), show_location=True)
                ## timeslot 2019-11-22 12:20:00 length 1:30:00 in Olivia size: 150 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session II", time=datetime.datetime(2019, 11, 22, 12, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Olivia"), show_location=True)
                ## timeslot 2019-11-22 12:20:00 length 1:30:00 in Sophia size: 200 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session II", time=datetime.datetime(2019, 11, 22, 12, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Sophia"), show_location=True)
                ## timeslot 2019-11-22 12:20:00 length 1:30:00 in Collyer size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session II", time=datetime.datetime(2019, 11, 22, 12, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Collyer"), show_location=True)
                ## timeslot 2019-11-22 12:20:00 length 1:30:00 in Padang size: 300 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session II", time=datetime.datetime(2019, 11, 22, 12, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Padang"), show_location=True)
                ## timeslot 2019-11-22 12:20:00 length 1:30:00 in Canning size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session II", time=datetime.datetime(2019, 11, 22, 12, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Canning"), show_location=True)
                ## timeslot 2019-11-22 12:20:00 length 1:30:00 in Canning/Padang size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session II", time=datetime.datetime(2019, 11, 22, 12, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Canning/Padang"), show_location=True)
                ## timeslot 2019-11-22 12:20:00 length 1:30:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session II", time=datetime.datetime(2019, 11, 22, 12, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-22 12:20:00 length 1:30:00 in Convention Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session II", time=datetime.datetime(2019, 11, 22, 12, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Convention Foyer"), show_location=True)
                ## timeslot 2019-11-22 12:20:00 length 1:30:00 in Fairmont Ballroom Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session II", time=datetime.datetime(2019, 11, 22, 12, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Fairmont Ballroom Foyer"), show_location=True)
                ## timeslot 2019-11-22 12:20:00 length 1:30:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session II", time=datetime.datetime(2019, 11, 22, 12, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-22 12:20:00 length 1:30:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session II", time=datetime.datetime(2019, 11, 22, 12, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-22 12:20:00 length 1:30:00 in VIP B size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session II", time=datetime.datetime(2019, 11, 22, 12, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="VIP B"), show_location=True)
                ## timeslot 2019-11-22 12:20:00 length 1:30:00 in Clark size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session II", time=datetime.datetime(2019, 11, 22, 12, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Clark"), show_location=True)
                ## timeslot 2019-11-22 12:20:00 length 1:30:00 in Mercury/Enterprise size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session II", time=datetime.datetime(2019, 11, 22, 12, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Mercury/Enterprise"), show_location=True)
                ## timeslot 2019-11-22 12:20:00 length 1:30:00 in Minto size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session II", time=datetime.datetime(2019, 11, 22, 12, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Minto"), show_location=True)
                ## timeslot 2019-11-22 12:20:00 length 1:30:00 in Fullerton size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session II", time=datetime.datetime(2019, 11, 22, 12, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Fullerton"), show_location=True)
                ## timeslot 2019-11-22 12:20:00 length 1:30:00 in Bonham size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session II", time=datetime.datetime(2019, 11, 22, 12, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Bonham"), show_location=True)
                ## timeslot 2019-11-22 12:20:00 length 1:30:00 in Bailey size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session II", time=datetime.datetime(2019, 11, 22, 12, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Bailey"), show_location=True)
                ## timeslot 2019-11-22 12:20:00 length 1:30:00 in Ord/Blundell size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session II", time=datetime.datetime(2019, 11, 22, 12, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Ord/Blundell"), show_location=True)
                ## timeslot 2019-11-22 12:20:00 length 1:30:00 in Indiana size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session II", time=datetime.datetime(2019, 11, 22, 12, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Indiana"), show_location=True)
                ## timeslot 2019-11-22 12:20:00 length 1:30:00 in Bras Basah size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session II", time=datetime.datetime(2019, 11, 22, 12, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Bras Basah"), show_location=True)
                ## timeslot 2019-11-22 12:20:00 length 1:30:00 in Butterworth size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session II", time=datetime.datetime(2019, 11, 22, 12, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Butterworth"), show_location=True)
                ## timeslot 2019-11-22 12:00:00 length 0:20:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="break", name="Beverage and Snack Break", time=datetime.datetime(2019, 11, 22, 12, 0), duration=datetime.timedelta(seconds=1200), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-22 10:00:00 length 2:00:00 in Orchard size: 50 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 22, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Orchard"), show_location=True)
                ## timeslot 2019-11-22 10:00:00 length 2:00:00 in VIP A size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 22, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="VIP A"), show_location=True)
                ## timeslot 2019-11-22 10:00:00 length 2:00:00 in Hullet size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 22, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Hullet"), show_location=True)
                ## timeslot 2019-11-22 10:00:00 length 2:00:00 in Olivia size: 150 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 22, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Olivia"), show_location=True)
                ## timeslot 2019-11-22 10:00:00 length 2:00:00 in Sophia size: 200 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 22, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Sophia"), show_location=True)
                ## timeslot 2019-11-22 10:00:00 length 2:00:00 in Collyer size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 22, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Collyer"), show_location=True)
                ## timeslot 2019-11-22 10:00:00 length 2:00:00 in Padang size: 300 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 22, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Padang"), show_location=True)
                ## timeslot 2019-11-22 10:00:00 length 2:00:00 in Canning size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 22, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Canning"), show_location=True)
                ## timeslot 2019-11-22 10:00:00 length 2:00:00 in Canning/Padang size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 22, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Canning/Padang"), show_location=True)
                ## timeslot 2019-11-22 10:00:00 length 2:00:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 22, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-22 10:00:00 length 2:00:00 in Convention Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 22, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Convention Foyer"), show_location=True)
                ## timeslot 2019-11-22 10:00:00 length 2:00:00 in Fairmont Ballroom Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 22, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Fairmont Ballroom Foyer"), show_location=True)
                ## timeslot 2019-11-22 10:00:00 length 2:00:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 22, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-22 10:00:00 length 2:00:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 22, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-22 10:00:00 length 2:00:00 in VIP B size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 22, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="VIP B"), show_location=True)
                ## timeslot 2019-11-22 10:00:00 length 2:00:00 in Clark size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 22, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Clark"), show_location=True)
                ## timeslot 2019-11-22 10:00:00 length 2:00:00 in Mercury/Enterprise size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 22, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Mercury/Enterprise"), show_location=True)
                ## timeslot 2019-11-22 10:00:00 length 2:00:00 in Minto size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 22, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Minto"), show_location=True)
                ## timeslot 2019-11-22 10:00:00 length 2:00:00 in Fullerton size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 22, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Fullerton"), show_location=True)
                ## timeslot 2019-11-22 10:00:00 length 2:00:00 in Bonham size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 22, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Bonham"), show_location=True)
                ## timeslot 2019-11-22 10:00:00 length 2:00:00 in Bailey size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 22, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Bailey"), show_location=True)
                ## timeslot 2019-11-22 10:00:00 length 2:00:00 in Ord/Blundell size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 22, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Ord/Blundell"), show_location=True)
                ## timeslot 2019-11-22 10:00:00 length 2:00:00 in Indiana size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 22, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Indiana"), show_location=True)
                ## timeslot 2019-11-22 10:00:00 length 2:00:00 in Bras Basah size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 22, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Bras Basah"), show_location=True)
                ## timeslot 2019-11-22 10:00:00 length 2:00:00 in Butterworth size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 22, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Butterworth"), show_location=True)
                ## timeslot 2019-11-22 08:30:00 length 1:15:00 in None ##
                TimeSlot.objects.create(meeting=m, type_id="other", name="Side Meetings / Open Time", time=datetime.datetime(2019, 11, 22, 8, 30), duration=datetime.timedelta(seconds=4500), location=None, show_location=False)
                ## timeslot 2019-11-22 08:30:00 length 4:00:00 in Convention Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="reg", name="IETF Registration", time=datetime.datetime(2019, 11, 22, 8, 30), duration=datetime.timedelta(seconds=14400), location=Room.objects.get(meeting=m, name="Convention Foyer"), show_location=True)
                ## timeslot 2019-11-22 08:00:00 length 1:00:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="break", name="Beverage Break", time=datetime.datetime(2019, 11, 22, 8, 0), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-21 17:40:00 length 1:00:00 in Orchard size: 50 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 21, 17, 40), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Orchard"), show_location=True)
                ## timeslot 2019-11-21 17:40:00 length 1:00:00 in VIP A size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 21, 17, 40), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="VIP A"), show_location=True)
                ## timeslot 2019-11-21 17:40:00 length 1:00:00 in Hullet size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 21, 17, 40), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Hullet"), show_location=True)
                ## timeslot 2019-11-21 17:40:00 length 1:00:00 in Olivia size: 150 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 21, 17, 40), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Olivia"), show_location=True)
                ## timeslot 2019-11-21 17:40:00 length 1:00:00 in Sophia size: 200 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 21, 17, 40), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Sophia"), show_location=True)
                ## timeslot 2019-11-21 17:40:00 length 1:00:00 in Collyer size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 21, 17, 40), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Collyer"), show_location=True)
                ## timeslot 2019-11-21 17:40:00 length 1:00:00 in Padang size: 300 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 21, 17, 40), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Padang"), show_location=True)
                ## timeslot 2019-11-21 17:40:00 length 1:00:00 in Canning size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 21, 17, 40), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Canning"), show_location=True)
                ## timeslot 2019-11-21 17:40:00 length 1:00:00 in Canning/Padang size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 21, 17, 40), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Canning/Padang"), show_location=True)
                ## timeslot 2019-11-21 17:40:00 length 1:00:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 21, 17, 40), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-21 17:40:00 length 1:00:00 in Convention Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 21, 17, 40), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Convention Foyer"), show_location=True)
                ## timeslot 2019-11-21 17:40:00 length 1:00:00 in Fairmont Ballroom Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 21, 17, 40), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Fairmont Ballroom Foyer"), show_location=True)
                ## timeslot 2019-11-21 17:40:00 length 1:00:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 21, 17, 40), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-21 17:40:00 length 1:00:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 21, 17, 40), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-21 17:40:00 length 1:00:00 in VIP B size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 21, 17, 40), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="VIP B"), show_location=True)
                ## timeslot 2019-11-21 17:40:00 length 1:00:00 in Clark size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 21, 17, 40), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Clark"), show_location=True)
                ## timeslot 2019-11-21 17:40:00 length 1:00:00 in Mercury/Enterprise size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 21, 17, 40), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Mercury/Enterprise"), show_location=True)
                ## timeslot 2019-11-21 17:40:00 length 1:00:00 in Minto size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 21, 17, 40), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Minto"), show_location=True)
                ## timeslot 2019-11-21 17:40:00 length 1:00:00 in Fullerton size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 21, 17, 40), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Fullerton"), show_location=True)
                ## timeslot 2019-11-21 17:40:00 length 1:00:00 in Bonham size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 21, 17, 40), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Bonham"), show_location=True)
                ## timeslot 2019-11-21 17:40:00 length 1:00:00 in Bailey size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 21, 17, 40), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Bailey"), show_location=True)
                ## timeslot 2019-11-21 17:40:00 length 1:00:00 in Ord/Blundell size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 21, 17, 40), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Ord/Blundell"), show_location=True)
                ## timeslot 2019-11-21 17:40:00 length 1:00:00 in Indiana size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 21, 17, 40), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Indiana"), show_location=True)
                ## timeslot 2019-11-21 17:40:00 length 1:00:00 in Bras Basah size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 21, 17, 40), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Bras Basah"), show_location=True)
                ## timeslot 2019-11-21 17:40:00 length 1:00:00 in Butterworth size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 21, 17, 40), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Butterworth"), show_location=True)
                ## timeslot 2019-11-21 17:20:00 length 0:20:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="break", name="Beverage Break", time=datetime.datetime(2019, 11, 21, 17, 20), duration=datetime.timedelta(seconds=1200), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-21 15:50:00 length 1:30:00 in Orchard size: 50 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 21, 15, 50), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Orchard"), show_location=True)
                ## timeslot 2019-11-21 15:50:00 length 1:30:00 in VIP A size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 21, 15, 50), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="VIP A"), show_location=True)
                ## timeslot 2019-11-21 15:50:00 length 1:30:00 in Hullet size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 21, 15, 50), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Hullet"), show_location=True)
                ## timeslot 2019-11-21 15:50:00 length 1:30:00 in Olivia size: 150 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 21, 15, 50), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Olivia"), show_location=True)
                ## timeslot 2019-11-21 15:50:00 length 1:30:00 in Sophia size: 200 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 21, 15, 50), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Sophia"), show_location=True)
                ## timeslot 2019-11-21 15:50:00 length 1:30:00 in Collyer size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 21, 15, 50), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Collyer"), show_location=True)
                ## timeslot 2019-11-21 15:50:00 length 1:30:00 in Padang size: 300 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 21, 15, 50), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Padang"), show_location=True)
                ## timeslot 2019-11-21 15:50:00 length 1:30:00 in Canning size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 21, 15, 50), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Canning"), show_location=True)
                ## timeslot 2019-11-21 15:50:00 length 1:30:00 in Canning/Padang size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 21, 15, 50), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Canning/Padang"), show_location=True)
                ## timeslot 2019-11-21 15:50:00 length 1:30:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 21, 15, 50), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-21 15:50:00 length 1:30:00 in Convention Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 21, 15, 50), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Convention Foyer"), show_location=True)
                ## timeslot 2019-11-21 15:50:00 length 1:30:00 in Fairmont Ballroom Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 21, 15, 50), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Fairmont Ballroom Foyer"), show_location=True)
                ## timeslot 2019-11-21 15:50:00 length 1:30:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 21, 15, 50), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-21 15:50:00 length 1:30:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 21, 15, 50), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-21 15:50:00 length 1:30:00 in VIP B size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 21, 15, 50), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="VIP B"), show_location=True)
                ## timeslot 2019-11-21 15:50:00 length 1:30:00 in Clark size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 21, 15, 50), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Clark"), show_location=True)
                ## timeslot 2019-11-21 15:50:00 length 1:30:00 in Mercury/Enterprise size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 21, 15, 50), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Mercury/Enterprise"), show_location=True)
                ## timeslot 2019-11-21 15:50:00 length 1:30:00 in Minto size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 21, 15, 50), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Minto"), show_location=True)
                ## timeslot 2019-11-21 15:50:00 length 1:30:00 in Fullerton size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 21, 15, 50), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Fullerton"), show_location=True)
                ## timeslot 2019-11-21 15:50:00 length 1:30:00 in Bonham size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 21, 15, 50), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Bonham"), show_location=True)
                ## timeslot 2019-11-21 15:50:00 length 1:30:00 in Bailey size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 21, 15, 50), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Bailey"), show_location=True)
                ## timeslot 2019-11-21 15:50:00 length 1:30:00 in Ord/Blundell size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 21, 15, 50), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Ord/Blundell"), show_location=True)
                ## timeslot 2019-11-21 15:50:00 length 1:30:00 in Indiana size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 21, 15, 50), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Indiana"), show_location=True)
                ## timeslot 2019-11-21 15:50:00 length 1:30:00 in Bras Basah size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 21, 15, 50), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Bras Basah"), show_location=True)
                ## timeslot 2019-11-21 15:50:00 length 1:30:00 in Butterworth size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 21, 15, 50), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Butterworth"), show_location=True)
                ## timeslot 2019-11-21 15:30:00 length 0:20:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="break", name="Beverage and Snack Break", time=datetime.datetime(2019, 11, 21, 15, 30), duration=datetime.timedelta(seconds=1200), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-21 13:30:00 length 2:00:00 in Orchard size: 50 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 21, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Orchard"), show_location=True)
                ## timeslot 2019-11-21 13:30:00 length 2:00:00 in VIP A size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 21, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="VIP A"), show_location=True)
                ## timeslot 2019-11-21 13:30:00 length 2:00:00 in Hullet size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 21, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Hullet"), show_location=True)
                ## timeslot 2019-11-21 13:30:00 length 2:00:00 in Olivia size: 150 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 21, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Olivia"), show_location=True)
                ## timeslot 2019-11-21 13:30:00 length 2:00:00 in Sophia size: 200 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 21, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Sophia"), show_location=True)
                ## timeslot 2019-11-21 13:30:00 length 2:00:00 in Collyer size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 21, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Collyer"), show_location=True)
                ## timeslot 2019-11-21 13:30:00 length 2:00:00 in Padang size: 300 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 21, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Padang"), show_location=True)
                ## timeslot 2019-11-21 13:30:00 length 2:00:00 in Canning size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 21, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Canning"), show_location=True)
                ## timeslot 2019-11-21 13:30:00 length 2:00:00 in Canning/Padang size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 21, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Canning/Padang"), show_location=True)
                ## timeslot 2019-11-21 13:30:00 length 2:00:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 21, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-21 13:30:00 length 2:00:00 in Convention Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 21, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Convention Foyer"), show_location=True)
                ## timeslot 2019-11-21 13:30:00 length 2:00:00 in Fairmont Ballroom Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 21, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Fairmont Ballroom Foyer"), show_location=True)
                ## timeslot 2019-11-21 13:30:00 length 2:00:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 21, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-21 13:30:00 length 2:00:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 21, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-21 13:30:00 length 2:00:00 in VIP B size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 21, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="VIP B"), show_location=True)
                ## timeslot 2019-11-21 13:30:00 length 2:00:00 in Clark size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 21, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Clark"), show_location=True)
                ## timeslot 2019-11-21 13:30:00 length 2:00:00 in Mercury/Enterprise size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 21, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Mercury/Enterprise"), show_location=True)
                ## timeslot 2019-11-21 13:30:00 length 2:00:00 in Minto size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 21, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Minto"), show_location=True)
                ## timeslot 2019-11-21 13:30:00 length 2:00:00 in Fullerton size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 21, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Fullerton"), show_location=True)
                ## timeslot 2019-11-21 13:30:00 length 2:00:00 in Bonham size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 21, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Bonham"), show_location=True)
                ## timeslot 2019-11-21 13:30:00 length 2:00:00 in Bailey size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 21, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Bailey"), show_location=True)
                ## timeslot 2019-11-21 13:30:00 length 2:00:00 in Ord/Blundell size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 21, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Ord/Blundell"), show_location=True)
                ## timeslot 2019-11-21 13:30:00 length 2:00:00 in Indiana size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 21, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Indiana"), show_location=True)
                ## timeslot 2019-11-21 13:30:00 length 2:00:00 in Bras Basah size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 21, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Bras Basah"), show_location=True)
                ## timeslot 2019-11-21 13:30:00 length 2:00:00 in Butterworth size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 21, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Butterworth"), show_location=True)
                ## timeslot 2019-11-21 12:30:00 length 0:45:00 in Collyer size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="other", name="Host Speaker Series", time=datetime.datetime(2019, 11, 21, 12, 30), duration=datetime.timedelta(seconds=2700), location=Room.objects.get(meeting=m, name="Collyer"), show_location=True)
                ## timeslot 2019-11-21 12:15:00 length 1:00:00 in Skai Suite 1 (Swissotel) size: None ##
                TimeSlot.objects.create(meeting=m, type_id="other", name="Systers Lunch", time=datetime.datetime(2019, 11, 21, 12, 15), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Skai Suite 1 (Swissotel)"), show_location=True)
                ## timeslot 2019-11-21 12:00:00 length 1:30:00 in None ##
                TimeSlot.objects.create(meeting=m, type_id="break", name="Break", time=datetime.datetime(2019, 11, 21, 12, 0), duration=datetime.timedelta(seconds=5400), location=None, show_location=False)
                ## timeslot 2019-11-21 10:00:00 length 2:00:00 in Orchard size: 50 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 21, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Orchard"), show_location=True)
                ## timeslot 2019-11-21 10:00:00 length 2:00:00 in VIP A size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 21, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="VIP A"), show_location=True)
                ## timeslot 2019-11-21 10:00:00 length 2:00:00 in Hullet size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 21, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Hullet"), show_location=True)
                ## timeslot 2019-11-21 10:00:00 length 2:00:00 in Olivia size: 150 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 21, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Olivia"), show_location=True)
                ## timeslot 2019-11-21 10:00:00 length 2:00:00 in Sophia size: 200 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 21, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Sophia"), show_location=True)
                ## timeslot 2019-11-21 10:00:00 length 2:00:00 in Collyer size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 21, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Collyer"), show_location=True)
                ## timeslot 2019-11-21 10:00:00 length 2:00:00 in Padang size: 300 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 21, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Padang"), show_location=True)
                ## timeslot 2019-11-21 10:00:00 length 2:00:00 in Canning size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 21, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Canning"), show_location=True)
                ## timeslot 2019-11-21 10:00:00 length 2:00:00 in Canning/Padang size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 21, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Canning/Padang"), show_location=True)
                ## timeslot 2019-11-21 10:00:00 length 2:00:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 21, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-21 10:00:00 length 2:00:00 in Convention Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 21, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Convention Foyer"), show_location=True)
                ## timeslot 2019-11-21 10:00:00 length 2:00:00 in Fairmont Ballroom Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 21, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Fairmont Ballroom Foyer"), show_location=True)
                ## timeslot 2019-11-21 10:00:00 length 2:00:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 21, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-21 10:00:00 length 2:00:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 21, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-21 10:00:00 length 2:00:00 in VIP B size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 21, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="VIP B"), show_location=True)
                ## timeslot 2019-11-21 10:00:00 length 2:00:00 in Clark size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 21, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Clark"), show_location=True)
                ## timeslot 2019-11-21 10:00:00 length 2:00:00 in Mercury/Enterprise size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 21, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Mercury/Enterprise"), show_location=True)
                ## timeslot 2019-11-21 10:00:00 length 2:00:00 in Minto size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 21, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Minto"), show_location=True)
                ## timeslot 2019-11-21 10:00:00 length 2:00:00 in Fullerton size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 21, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Fullerton"), show_location=True)
                ## timeslot 2019-11-21 10:00:00 length 2:00:00 in Bonham size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 21, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Bonham"), show_location=True)
                ## timeslot 2019-11-21 10:00:00 length 2:00:00 in Bailey size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 21, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Bailey"), show_location=True)
                ## timeslot 2019-11-21 10:00:00 length 2:00:00 in Ord/Blundell size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 21, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Ord/Blundell"), show_location=True)
                ## timeslot 2019-11-21 10:00:00 length 2:00:00 in Indiana size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 21, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Indiana"), show_location=True)
                ## timeslot 2019-11-21 10:00:00 length 2:00:00 in Bras Basah size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 21, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Bras Basah"), show_location=True)
                ## timeslot 2019-11-21 10:00:00 length 2:00:00 in Butterworth size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 21, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Butterworth"), show_location=True)
                ## timeslot 2019-11-21 09:00:00 length 1:00:00 in Fullerton size: None ##
                TimeSlot.objects.create(meeting=m, type_id="other", name="NomCom Office Hours", time=datetime.datetime(2019, 11, 21, 9, 0), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Fullerton"), show_location=True)
                ## timeslot 2019-11-21 08:30:00 length 1:15:00 in None ##
                TimeSlot.objects.create(meeting=m, type_id="other", name="Side Meetings / Open Time", time=datetime.datetime(2019, 11, 21, 8, 30), duration=datetime.timedelta(seconds=4500), location=None, show_location=False)
                ## timeslot 2019-11-21 08:30:00 length 9:30:00 in Convention Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="reg", name="IETF Registration", time=datetime.datetime(2019, 11, 21, 8, 30), duration=datetime.timedelta(seconds=34200), location=Room.objects.get(meeting=m, name="Convention Foyer"), show_location=True)
                ## timeslot 2019-11-21 08:00:00 length 1:00:00 in Bras Basah size: None ##
                TimeSlot.objects.create(meeting=m, type_id="other", name="Newcomers' Feedback Session", time=datetime.datetime(2019, 11, 21, 8, 0), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Bras Basah"), show_location=True)
                ## timeslot 2019-11-21 08:00:00 length 1:00:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="break", name="Beverage Break", time=datetime.datetime(2019, 11, 21, 8, 0), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-20 17:10:00 length 2:30:00 in Canning/Padang size: None ##
                TimeSlot.objects.create(meeting=m, type_id="plenary", name="IETF Plenary", time=datetime.datetime(2019, 11, 20, 17, 10), duration=datetime.timedelta(seconds=9000), location=Room.objects.get(meeting=m, name="Canning/Padang"), show_location=True)
                ## timeslot 2019-11-20 16:50:00 length 0:20:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="break", name="Beverage and Snack Break", time=datetime.datetime(2019, 11, 20, 16, 50), duration=datetime.timedelta(seconds=1200), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-20 15:20:00 length 1:30:00 in Orchard size: 50 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 20, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Orchard"), show_location=True)
                ## timeslot 2019-11-20 15:20:00 length 1:30:00 in VIP A size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 20, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="VIP A"), show_location=True)
                ## timeslot 2019-11-20 15:20:00 length 1:30:00 in Hullet size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 20, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Hullet"), show_location=True)
                ## timeslot 2019-11-20 15:20:00 length 1:30:00 in Olivia size: 150 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 20, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Olivia"), show_location=True)
                ## timeslot 2019-11-20 15:20:00 length 1:30:00 in Sophia size: 200 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 20, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Sophia"), show_location=True)
                ## timeslot 2019-11-20 15:20:00 length 1:30:00 in Collyer size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 20, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Collyer"), show_location=True)
                ## timeslot 2019-11-20 15:20:00 length 1:30:00 in Padang size: 300 ##
                TimeSlot.objects.create(meeting=m, type_id="unavail", name="Afternoon Session II", time=datetime.datetime(2019, 11, 20, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Padang"), show_location=True)
                ## timeslot 2019-11-20 15:20:00 length 1:30:00 in Canning size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="unavail", name="Afternoon Session II", time=datetime.datetime(2019, 11, 20, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Canning"), show_location=True)
                ## timeslot 2019-11-20 15:20:00 length 1:30:00 in Canning/Padang size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 20, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Canning/Padang"), show_location=True)
                ## timeslot 2019-11-20 15:20:00 length 1:30:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 20, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-20 15:20:00 length 1:30:00 in Convention Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 20, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Convention Foyer"), show_location=True)
                ## timeslot 2019-11-20 15:20:00 length 1:30:00 in Fairmont Ballroom Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 20, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Fairmont Ballroom Foyer"), show_location=True)
                ## timeslot 2019-11-20 15:20:00 length 1:30:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 20, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-20 15:20:00 length 1:30:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 20, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-20 15:20:00 length 1:30:00 in VIP B size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 20, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="VIP B"), show_location=True)
                ## timeslot 2019-11-20 15:20:00 length 1:30:00 in Clark size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 20, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Clark"), show_location=True)
                ## timeslot 2019-11-20 15:20:00 length 1:30:00 in Mercury/Enterprise size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 20, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Mercury/Enterprise"), show_location=True)
                ## timeslot 2019-11-20 15:20:00 length 1:30:00 in Minto size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 20, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Minto"), show_location=True)
                ## timeslot 2019-11-20 15:20:00 length 1:30:00 in Fullerton size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 20, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Fullerton"), show_location=True)
                ## timeslot 2019-11-20 15:20:00 length 1:30:00 in Bonham size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 20, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Bonham"), show_location=True)
                ## timeslot 2019-11-20 15:20:00 length 1:30:00 in Bailey size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 20, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Bailey"), show_location=True)
                ## timeslot 2019-11-20 15:20:00 length 1:30:00 in Ord/Blundell size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 20, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Ord/Blundell"), show_location=True)
                ## timeslot 2019-11-20 15:20:00 length 1:30:00 in Indiana size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 20, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Indiana"), show_location=True)
                ## timeslot 2019-11-20 15:20:00 length 1:30:00 in Bras Basah size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 20, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Bras Basah"), show_location=True)
                ## timeslot 2019-11-20 15:20:00 length 1:30:00 in Butterworth size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 20, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Butterworth"), show_location=True)
                ## timeslot 2019-11-20 15:00:00 length 0:20:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="break", name="Beverage Break", time=datetime.datetime(2019, 11, 20, 15, 0), duration=datetime.timedelta(seconds=1200), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-20 13:30:00 length 1:30:00 in Orchard size: 50 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 20, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Orchard"), show_location=True)
                ## timeslot 2019-11-20 13:30:00 length 1:30:00 in VIP A size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 20, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="VIP A"), show_location=True)
                ## timeslot 2019-11-20 13:30:00 length 1:30:00 in Hullet size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 20, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Hullet"), show_location=True)
                ## timeslot 2019-11-20 13:30:00 length 1:30:00 in Olivia size: 150 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 20, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Olivia"), show_location=True)
                ## timeslot 2019-11-20 13:30:00 length 1:30:00 in Sophia size: 200 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 20, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Sophia"), show_location=True)
                ## timeslot 2019-11-20 13:30:00 length 1:30:00 in Collyer size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 20, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Collyer"), show_location=True)
                ## timeslot 2019-11-20 13:30:00 length 1:30:00 in Padang size: 300 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 20, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Padang"), show_location=True)
                ## timeslot 2019-11-20 13:30:00 length 1:30:00 in Canning size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 20, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Canning"), show_location=True)
                ## timeslot 2019-11-20 13:30:00 length 1:30:00 in Canning/Padang size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 20, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Canning/Padang"), show_location=True)
                ## timeslot 2019-11-20 13:30:00 length 1:30:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 20, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-20 13:30:00 length 1:30:00 in Convention Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 20, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Convention Foyer"), show_location=True)
                ## timeslot 2019-11-20 13:30:00 length 1:30:00 in Fairmont Ballroom Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 20, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Fairmont Ballroom Foyer"), show_location=True)
                ## timeslot 2019-11-20 13:30:00 length 1:30:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 20, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-20 13:30:00 length 1:30:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 20, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-20 13:30:00 length 1:30:00 in VIP B size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 20, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="VIP B"), show_location=True)
                ## timeslot 2019-11-20 13:30:00 length 1:30:00 in Clark size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 20, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Clark"), show_location=True)
                ## timeslot 2019-11-20 13:30:00 length 1:30:00 in Mercury/Enterprise size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 20, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Mercury/Enterprise"), show_location=True)
                ## timeslot 2019-11-20 13:30:00 length 1:30:00 in Minto size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 20, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Minto"), show_location=True)
                ## timeslot 2019-11-20 13:30:00 length 1:30:00 in Fullerton size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 20, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Fullerton"), show_location=True)
                ## timeslot 2019-11-20 13:30:00 length 1:30:00 in Bonham size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 20, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Bonham"), show_location=True)
                ## timeslot 2019-11-20 13:30:00 length 1:30:00 in Bailey size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 20, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Bailey"), show_location=True)
                ## timeslot 2019-11-20 13:30:00 length 1:30:00 in Ord/Blundell size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 20, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Ord/Blundell"), show_location=True)
                ## timeslot 2019-11-20 13:30:00 length 1:30:00 in Indiana size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 20, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Indiana"), show_location=True)
                ## timeslot 2019-11-20 13:30:00 length 1:30:00 in Bras Basah size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 20, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Bras Basah"), show_location=True)
                ## timeslot 2019-11-20 13:30:00 length 1:30:00 in Butterworth size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 20, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Butterworth"), show_location=True)
                ## timeslot 2019-11-20 12:15:00 length 1:00:00 in Sophia size: 200 ##
                TimeSlot.objects.create(meeting=m, type_id="other", name="WG Chairs Forum (For WG Chairs Only)", time=datetime.datetime(2019, 11, 20, 12, 15), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Sophia"), show_location=True)
                ## timeslot 2019-11-20 12:00:00 length 1:30:00 in None ##
                TimeSlot.objects.create(meeting=m, type_id="break", name="Break", time=datetime.datetime(2019, 11, 20, 12, 0), duration=datetime.timedelta(seconds=5400), location=None, show_location=False)
                ## timeslot 2019-11-20 10:00:00 length 2:00:00 in Orchard size: 50 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 20, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Orchard"), show_location=True)
                ## timeslot 2019-11-20 10:00:00 length 2:00:00 in VIP A size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 20, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="VIP A"), show_location=True)
                ## timeslot 2019-11-20 10:00:00 length 2:00:00 in Hullet size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 20, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Hullet"), show_location=True)
                ## timeslot 2019-11-20 10:00:00 length 2:00:00 in Olivia size: 150 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 20, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Olivia"), show_location=True)
                ## timeslot 2019-11-20 10:00:00 length 2:00:00 in Sophia size: 200 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 20, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Sophia"), show_location=True)
                ## timeslot 2019-11-20 10:00:00 length 2:00:00 in Collyer size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 20, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Collyer"), show_location=True)
                ## timeslot 2019-11-20 10:00:00 length 2:00:00 in Padang size: 300 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 20, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Padang"), show_location=True)
                ## timeslot 2019-11-20 10:00:00 length 2:00:00 in Canning size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 20, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Canning"), show_location=True)
                ## timeslot 2019-11-20 10:00:00 length 2:00:00 in Canning/Padang size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 20, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Canning/Padang"), show_location=True)
                ## timeslot 2019-11-20 10:00:00 length 2:00:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 20, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-20 10:00:00 length 2:00:00 in Convention Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 20, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Convention Foyer"), show_location=True)
                ## timeslot 2019-11-20 10:00:00 length 2:00:00 in Fairmont Ballroom Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 20, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Fairmont Ballroom Foyer"), show_location=True)
                ## timeslot 2019-11-20 10:00:00 length 2:00:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 20, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-20 10:00:00 length 2:00:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 20, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-20 10:00:00 length 2:00:00 in VIP B size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 20, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="VIP B"), show_location=True)
                ## timeslot 2019-11-20 10:00:00 length 2:00:00 in Clark size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 20, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Clark"), show_location=True)
                ## timeslot 2019-11-20 10:00:00 length 2:00:00 in Mercury/Enterprise size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 20, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Mercury/Enterprise"), show_location=True)
                ## timeslot 2019-11-20 10:00:00 length 2:00:00 in Minto size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 20, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Minto"), show_location=True)
                ## timeslot 2019-11-20 10:00:00 length 2:00:00 in Fullerton size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 20, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Fullerton"), show_location=True)
                ## timeslot 2019-11-20 10:00:00 length 2:00:00 in Bonham size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 20, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Bonham"), show_location=True)
                ## timeslot 2019-11-20 10:00:00 length 2:00:00 in Bailey size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 20, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Bailey"), show_location=True)
                ## timeslot 2019-11-20 10:00:00 length 2:00:00 in Ord/Blundell size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 20, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Ord/Blundell"), show_location=True)
                ## timeslot 2019-11-20 10:00:00 length 2:00:00 in Indiana size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 20, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Indiana"), show_location=True)
                ## timeslot 2019-11-20 10:00:00 length 2:00:00 in Bras Basah size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 20, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Bras Basah"), show_location=True)
                ## timeslot 2019-11-20 10:00:00 length 2:00:00 in Butterworth size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 20, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Butterworth"), show_location=True)
                ## timeslot 2019-11-20 09:00:00 length 1:00:00 in Fullerton size: None ##
                TimeSlot.objects.create(meeting=m, type_id="other", name="NomCom Office Hours", time=datetime.datetime(2019, 11, 20, 9, 0), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Fullerton"), show_location=True)
                ## timeslot 2019-11-20 09:00:00 length 0:45:00 in Clark size: None ##
                TimeSlot.objects.create(meeting=m, type_id="other", name="Routing AD Office Hours", time=datetime.datetime(2019, 11, 20, 9, 0), duration=datetime.timedelta(seconds=2700), location=Room.objects.get(meeting=m, name="Clark"), show_location=True)
                ## timeslot 2019-11-20 08:30:00 length 1:15:00 in None ##
                TimeSlot.objects.create(meeting=m, type_id="other", name="Side Meetings / Open Time", time=datetime.datetime(2019, 11, 20, 8, 30), duration=datetime.timedelta(seconds=4500), location=None, show_location=False)
                ## timeslot 2019-11-20 08:30:00 length 8:40:00 in Convention Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="reg", name="IETF Registration", time=datetime.datetime(2019, 11, 20, 8, 30), duration=datetime.timedelta(seconds=31200), location=Room.objects.get(meeting=m, name="Convention Foyer"), show_location=True)
                ## timeslot 2019-11-20 08:00:00 length 1:00:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="break", name="Beverage Break", time=datetime.datetime(2019, 11, 20, 8, 0), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-20 07:30:00 length 2:00:00 in None ##
                TimeSlot.objects.create(meeting=m, type_id="lead", name="IAB Breakfast", time=datetime.datetime(2019, 11, 20, 7, 30), duration=datetime.timedelta(seconds=7200), location=None, show_location=True)
                ## timeslot 2019-11-19 19:00:00 length 4:00:00 in None ##
                TimeSlot.objects.create(meeting=m, type_id="other", name="IETF 106 Social Event at the ArtScience Museum Marina Bay Sands - Hosted by Nokia", time=datetime.datetime(2019, 11, 19, 19, 0), duration=datetime.timedelta(seconds=14400), location=None, show_location=False)
                ## timeslot 2019-11-19 17:10:00 length 1:30:00 in Clark size: None ##
                TimeSlot.objects.create(meeting=m, type_id="other", name="Internet Area AD Office Hours", time=datetime.datetime(2019, 11, 19, 17, 10), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Clark"), show_location=True)
                ## timeslot 2019-11-19 17:10:00 length 1:30:00 in Orchard size: 50 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 19, 17, 10), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Orchard"), show_location=True)
                ## timeslot 2019-11-19 17:10:00 length 1:30:00 in VIP A size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 19, 17, 10), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="VIP A"), show_location=True)
                ## timeslot 2019-11-19 17:10:00 length 1:30:00 in Hullet size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 19, 17, 10), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Hullet"), show_location=True)
                ## timeslot 2019-11-19 17:10:00 length 1:30:00 in Olivia size: 150 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 19, 17, 10), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Olivia"), show_location=True)
                ## timeslot 2019-11-19 17:10:00 length 1:30:00 in Sophia size: 200 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 19, 17, 10), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Sophia"), show_location=True)
                ## timeslot 2019-11-19 17:10:00 length 1:30:00 in Collyer size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 19, 17, 10), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Collyer"), show_location=True)
                ## timeslot 2019-11-19 17:10:00 length 1:30:00 in Padang size: 300 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 19, 17, 10), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Padang"), show_location=True)
                ## timeslot 2019-11-19 17:10:00 length 1:30:00 in Canning size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 19, 17, 10), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Canning"), show_location=True)
                ## timeslot 2019-11-19 17:10:00 length 1:30:00 in Canning/Padang size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 19, 17, 10), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Canning/Padang"), show_location=True)
                ## timeslot 2019-11-19 17:10:00 length 1:30:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 19, 17, 10), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-19 17:10:00 length 1:30:00 in Convention Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 19, 17, 10), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Convention Foyer"), show_location=True)
                ## timeslot 2019-11-19 17:10:00 length 1:30:00 in Fairmont Ballroom Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 19, 17, 10), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Fairmont Ballroom Foyer"), show_location=True)
                ## timeslot 2019-11-19 17:10:00 length 1:30:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 19, 17, 10), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-19 17:10:00 length 1:30:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 19, 17, 10), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-19 17:10:00 length 1:30:00 in VIP B size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 19, 17, 10), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="VIP B"), show_location=True)
                ## timeslot 2019-11-19 17:10:00 length 1:30:00 in Clark size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 19, 17, 10), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Clark"), show_location=True)
                ## timeslot 2019-11-19 17:10:00 length 1:30:00 in Mercury/Enterprise size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 19, 17, 10), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Mercury/Enterprise"), show_location=True)
                ## timeslot 2019-11-19 17:10:00 length 1:30:00 in Minto size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 19, 17, 10), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Minto"), show_location=True)
                ## timeslot 2019-11-19 17:10:00 length 1:30:00 in Fullerton size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 19, 17, 10), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Fullerton"), show_location=True)
                ## timeslot 2019-11-19 17:10:00 length 1:30:00 in Bonham size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 19, 17, 10), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Bonham"), show_location=True)
                ## timeslot 2019-11-19 17:10:00 length 1:30:00 in Bailey size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 19, 17, 10), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Bailey"), show_location=True)
                ## timeslot 2019-11-19 17:10:00 length 1:30:00 in Ord/Blundell size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 19, 17, 10), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Ord/Blundell"), show_location=True)
                ## timeslot 2019-11-19 17:10:00 length 1:30:00 in Indiana size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 19, 17, 10), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Indiana"), show_location=True)
                ## timeslot 2019-11-19 17:10:00 length 1:30:00 in Bras Basah size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 19, 17, 10), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Bras Basah"), show_location=True)
                ## timeslot 2019-11-19 17:10:00 length 1:30:00 in Butterworth size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 19, 17, 10), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Butterworth"), show_location=True)
                ## timeslot 2019-11-19 16:50:00 length 0:20:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="break", name="Beverage Break", time=datetime.datetime(2019, 11, 19, 16, 50), duration=datetime.timedelta(seconds=1200), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-19 15:20:00 length 1:30:00 in Orchard size: 50 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 19, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Orchard"), show_location=True)
                ## timeslot 2019-11-19 15:20:00 length 1:30:00 in VIP A size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 19, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="VIP A"), show_location=True)
                ## timeslot 2019-11-19 15:20:00 length 1:30:00 in Hullet size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 19, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Hullet"), show_location=True)
                ## timeslot 2019-11-19 15:20:00 length 1:30:00 in Olivia size: 150 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 19, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Olivia"), show_location=True)
                ## timeslot 2019-11-19 15:20:00 length 1:30:00 in Sophia size: 200 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 19, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Sophia"), show_location=True)
                ## timeslot 2019-11-19 15:20:00 length 1:30:00 in Collyer size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 19, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Collyer"), show_location=True)
                ## timeslot 2019-11-19 15:20:00 length 1:30:00 in Padang size: 300 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 19, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Padang"), show_location=True)
                ## timeslot 2019-11-19 15:20:00 length 1:30:00 in Canning size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 19, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Canning"), show_location=True)
                ## timeslot 2019-11-19 15:20:00 length 1:30:00 in Canning/Padang size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 19, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Canning/Padang"), show_location=True)
                ## timeslot 2019-11-19 15:20:00 length 1:30:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 19, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-19 15:20:00 length 1:30:00 in Convention Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 19, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Convention Foyer"), show_location=True)
                ## timeslot 2019-11-19 15:20:00 length 1:30:00 in Fairmont Ballroom Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 19, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Fairmont Ballroom Foyer"), show_location=True)
                ## timeslot 2019-11-19 15:20:00 length 1:30:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 19, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-19 15:20:00 length 1:30:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 19, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-19 15:20:00 length 1:30:00 in VIP B size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 19, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="VIP B"), show_location=True)
                ## timeslot 2019-11-19 15:20:00 length 1:30:00 in Clark size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 19, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Clark"), show_location=True)
                ## timeslot 2019-11-19 15:20:00 length 1:30:00 in Mercury/Enterprise size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 19, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Mercury/Enterprise"), show_location=True)
                ## timeslot 2019-11-19 15:20:00 length 1:30:00 in Minto size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 19, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Minto"), show_location=True)
                ## timeslot 2019-11-19 15:20:00 length 1:30:00 in Fullerton size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 19, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Fullerton"), show_location=True)
                ## timeslot 2019-11-19 15:20:00 length 1:30:00 in Bonham size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 19, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Bonham"), show_location=True)
                ## timeslot 2019-11-19 15:20:00 length 1:30:00 in Bailey size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 19, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Bailey"), show_location=True)
                ## timeslot 2019-11-19 15:20:00 length 1:30:00 in Ord/Blundell size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 19, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Ord/Blundell"), show_location=True)
                ## timeslot 2019-11-19 15:20:00 length 1:30:00 in Indiana size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 19, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Indiana"), show_location=True)
                ## timeslot 2019-11-19 15:20:00 length 1:30:00 in Bras Basah size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 19, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Bras Basah"), show_location=True)
                ## timeslot 2019-11-19 15:20:00 length 1:30:00 in Butterworth size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 19, 15, 20), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Butterworth"), show_location=True)
                ## timeslot 2019-11-19 15:00:00 length 0:20:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="break", name="Beverage and Snack Break", time=datetime.datetime(2019, 11, 19, 15, 0), duration=datetime.timedelta(seconds=1200), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-19 13:30:00 length 1:30:00 in Orchard size: 50 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 19, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Orchard"), show_location=True)
                ## timeslot 2019-11-19 13:30:00 length 1:30:00 in VIP A size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 19, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="VIP A"), show_location=True)
                ## timeslot 2019-11-19 13:30:00 length 1:30:00 in Hullet size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 19, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Hullet"), show_location=True)
                ## timeslot 2019-11-19 13:30:00 length 1:30:00 in Olivia size: 150 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 19, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Olivia"), show_location=True)
                ## timeslot 2019-11-19 13:30:00 length 1:30:00 in Sophia size: 200 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 19, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Sophia"), show_location=True)
                ## timeslot 2019-11-19 13:30:00 length 1:30:00 in Collyer size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 19, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Collyer"), show_location=True)
                ## timeslot 2019-11-19 13:30:00 length 1:30:00 in Padang size: 300 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 19, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Padang"), show_location=True)
                ## timeslot 2019-11-19 13:30:00 length 1:30:00 in Canning size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 19, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Canning"), show_location=True)
                ## timeslot 2019-11-19 13:30:00 length 1:30:00 in Canning/Padang size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 19, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Canning/Padang"), show_location=True)
                ## timeslot 2019-11-19 13:30:00 length 1:30:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 19, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-19 13:30:00 length 1:30:00 in Convention Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 19, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Convention Foyer"), show_location=True)
                ## timeslot 2019-11-19 13:30:00 length 1:30:00 in Fairmont Ballroom Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 19, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Fairmont Ballroom Foyer"), show_location=True)
                ## timeslot 2019-11-19 13:30:00 length 1:30:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 19, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-19 13:30:00 length 1:30:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 19, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-19 13:30:00 length 1:30:00 in VIP B size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 19, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="VIP B"), show_location=True)
                ## timeslot 2019-11-19 13:30:00 length 1:30:00 in Clark size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 19, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Clark"), show_location=True)
                ## timeslot 2019-11-19 13:30:00 length 1:30:00 in Mercury/Enterprise size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 19, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Mercury/Enterprise"), show_location=True)
                ## timeslot 2019-11-19 13:30:00 length 1:30:00 in Minto size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 19, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Minto"), show_location=True)
                ## timeslot 2019-11-19 13:30:00 length 1:30:00 in Fullerton size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 19, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Fullerton"), show_location=True)
                ## timeslot 2019-11-19 13:30:00 length 1:30:00 in Bonham size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 19, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Bonham"), show_location=True)
                ## timeslot 2019-11-19 13:30:00 length 1:30:00 in Bailey size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 19, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Bailey"), show_location=True)
                ## timeslot 2019-11-19 13:30:00 length 1:30:00 in Ord/Blundell size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 19, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Ord/Blundell"), show_location=True)
                ## timeslot 2019-11-19 13:30:00 length 1:30:00 in Indiana size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 19, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Indiana"), show_location=True)
                ## timeslot 2019-11-19 13:30:00 length 1:30:00 in Bras Basah size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 19, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Bras Basah"), show_location=True)
                ## timeslot 2019-11-19 13:30:00 length 1:30:00 in Butterworth size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 19, 13, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Butterworth"), show_location=True)
                ## timeslot 2019-11-19 12:00:00 length 1:30:00 in None ##
                TimeSlot.objects.create(meeting=m, type_id="break", name="Break", time=datetime.datetime(2019, 11, 19, 12, 0), duration=datetime.timedelta(seconds=5400), location=None, show_location=False)
                ## timeslot 2019-11-19 10:00:00 length 2:00:00 in Orchard size: 50 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 19, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Orchard"), show_location=True)
                ## timeslot 2019-11-19 10:00:00 length 2:00:00 in VIP A size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 19, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="VIP A"), show_location=True)
                ## timeslot 2019-11-19 10:00:00 length 2:00:00 in Hullet size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 19, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Hullet"), show_location=True)
                ## timeslot 2019-11-19 10:00:00 length 2:00:00 in Olivia size: 150 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 19, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Olivia"), show_location=True)
                ## timeslot 2019-11-19 10:00:00 length 2:00:00 in Sophia size: 200 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 19, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Sophia"), show_location=True)
                ## timeslot 2019-11-19 10:00:00 length 2:00:00 in Collyer size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 19, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Collyer"), show_location=True)
                ## timeslot 2019-11-19 10:00:00 length 2:00:00 in Padang size: 300 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 19, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Padang"), show_location=True)
                ## timeslot 2019-11-19 10:00:00 length 2:00:00 in Canning size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 19, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Canning"), show_location=True)
                ## timeslot 2019-11-19 10:00:00 length 2:00:00 in Canning/Padang size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 19, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Canning/Padang"), show_location=True)
                ## timeslot 2019-11-19 10:00:00 length 2:00:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 19, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-19 10:00:00 length 2:00:00 in Convention Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 19, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Convention Foyer"), show_location=True)
                ## timeslot 2019-11-19 10:00:00 length 2:00:00 in Fairmont Ballroom Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 19, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Fairmont Ballroom Foyer"), show_location=True)
                ## timeslot 2019-11-19 10:00:00 length 2:00:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 19, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-19 10:00:00 length 2:00:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 19, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-19 10:00:00 length 2:00:00 in VIP B size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 19, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="VIP B"), show_location=True)
                ## timeslot 2019-11-19 10:00:00 length 2:00:00 in Clark size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 19, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Clark"), show_location=True)
                ## timeslot 2019-11-19 10:00:00 length 2:00:00 in Mercury/Enterprise size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 19, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Mercury/Enterprise"), show_location=True)
                ## timeslot 2019-11-19 10:00:00 length 2:00:00 in Minto size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 19, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Minto"), show_location=True)
                ## timeslot 2019-11-19 10:00:00 length 2:00:00 in Fullerton size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 19, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Fullerton"), show_location=True)
                ## timeslot 2019-11-19 10:00:00 length 2:00:00 in Bonham size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 19, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Bonham"), show_location=True)
                ## timeslot 2019-11-19 10:00:00 length 2:00:00 in Bailey size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 19, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Bailey"), show_location=True)
                ## timeslot 2019-11-19 10:00:00 length 2:00:00 in Ord/Blundell size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 19, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Ord/Blundell"), show_location=True)
                ## timeslot 2019-11-19 10:00:00 length 2:00:00 in Indiana size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 19, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Indiana"), show_location=True)
                ## timeslot 2019-11-19 10:00:00 length 2:00:00 in Bras Basah size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 19, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Bras Basah"), show_location=True)
                ## timeslot 2019-11-19 10:00:00 length 2:00:00 in Butterworth size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 19, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Butterworth"), show_location=True)
                ## timeslot 2019-11-19 09:00:00 length 1:00:00 in Fullerton size: None ##
                TimeSlot.objects.create(meeting=m, type_id="other", name="NomCom Office Hours", time=datetime.datetime(2019, 11, 19, 9, 0), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Fullerton"), show_location=True)
                ## timeslot 2019-11-19 08:30:00 length 1:15:00 in None ##
                TimeSlot.objects.create(meeting=m, type_id="other", name="Side Meetings / Open Time", time=datetime.datetime(2019, 11, 19, 8, 30), duration=datetime.timedelta(seconds=4500), location=None, show_location=False)
                ## timeslot 2019-11-19 08:30:00 length 1:15:00 in Orchard size: 50 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Side Meetings / Open Time", time=datetime.datetime(2019, 11, 19, 8, 30), duration=datetime.timedelta(seconds=4500), location=Room.objects.get(meeting=m, name="Orchard"), show_location=True)
                ## timeslot 2019-11-19 08:30:00 length 1:15:00 in VIP A size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Side Meetings / Open Time", time=datetime.datetime(2019, 11, 19, 8, 30), duration=datetime.timedelta(seconds=4500), location=Room.objects.get(meeting=m, name="VIP A"), show_location=True)
                ## timeslot 2019-11-19 08:30:00 length 1:15:00 in Hullet size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Side Meetings / Open Time", time=datetime.datetime(2019, 11, 19, 8, 30), duration=datetime.timedelta(seconds=4500), location=Room.objects.get(meeting=m, name="Hullet"), show_location=True)
                ## timeslot 2019-11-19 08:30:00 length 1:15:00 in Olivia size: 150 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Side Meetings / Open Time", time=datetime.datetime(2019, 11, 19, 8, 30), duration=datetime.timedelta(seconds=4500), location=Room.objects.get(meeting=m, name="Olivia"), show_location=True)
                ## timeslot 2019-11-19 08:30:00 length 1:15:00 in Sophia size: 200 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Side Meetings / Open Time", time=datetime.datetime(2019, 11, 19, 8, 30), duration=datetime.timedelta(seconds=4500), location=Room.objects.get(meeting=m, name="Sophia"), show_location=True)
                ## timeslot 2019-11-19 08:30:00 length 1:15:00 in Collyer size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Side Meetings / Open Time", time=datetime.datetime(2019, 11, 19, 8, 30), duration=datetime.timedelta(seconds=4500), location=Room.objects.get(meeting=m, name="Collyer"), show_location=True)
                ## timeslot 2019-11-19 08:30:00 length 1:15:00 in Padang size: 300 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Side Meetings / Open Time", time=datetime.datetime(2019, 11, 19, 8, 30), duration=datetime.timedelta(seconds=4500), location=Room.objects.get(meeting=m, name="Padang"), show_location=True)
                ## timeslot 2019-11-19 08:30:00 length 1:15:00 in Canning size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Side Meetings / Open Time", time=datetime.datetime(2019, 11, 19, 8, 30), duration=datetime.timedelta(seconds=4500), location=Room.objects.get(meeting=m, name="Canning"), show_location=True)
                ## timeslot 2019-11-19 08:30:00 length 1:15:00 in Canning/Padang size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Side Meetings / Open Time", time=datetime.datetime(2019, 11, 19, 8, 30), duration=datetime.timedelta(seconds=4500), location=Room.objects.get(meeting=m, name="Canning/Padang"), show_location=True)
                ## timeslot 2019-11-19 08:30:00 length 1:15:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Side Meetings / Open Time", time=datetime.datetime(2019, 11, 19, 8, 30), duration=datetime.timedelta(seconds=4500), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-19 08:30:00 length 1:15:00 in Convention Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Side Meetings / Open Time", time=datetime.datetime(2019, 11, 19, 8, 30), duration=datetime.timedelta(seconds=4500), location=Room.objects.get(meeting=m, name="Convention Foyer"), show_location=True)
                ## timeslot 2019-11-19 08:30:00 length 1:15:00 in Fairmont Ballroom Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Side Meetings / Open Time", time=datetime.datetime(2019, 11, 19, 8, 30), duration=datetime.timedelta(seconds=4500), location=Room.objects.get(meeting=m, name="Fairmont Ballroom Foyer"), show_location=True)
                ## timeslot 2019-11-19 08:30:00 length 1:15:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Side Meetings / Open Time", time=datetime.datetime(2019, 11, 19, 8, 30), duration=datetime.timedelta(seconds=4500), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-19 08:30:00 length 1:15:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Side Meetings / Open Time", time=datetime.datetime(2019, 11, 19, 8, 30), duration=datetime.timedelta(seconds=4500), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-19 08:30:00 length 1:15:00 in VIP B size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Side Meetings / Open Time", time=datetime.datetime(2019, 11, 19, 8, 30), duration=datetime.timedelta(seconds=4500), location=Room.objects.get(meeting=m, name="VIP B"), show_location=True)
                ## timeslot 2019-11-19 08:30:00 length 1:15:00 in Clark size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Side Meetings / Open Time", time=datetime.datetime(2019, 11, 19, 8, 30), duration=datetime.timedelta(seconds=4500), location=Room.objects.get(meeting=m, name="Clark"), show_location=True)
                ## timeslot 2019-11-19 08:30:00 length 1:15:00 in Mercury/Enterprise size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Side Meetings / Open Time", time=datetime.datetime(2019, 11, 19, 8, 30), duration=datetime.timedelta(seconds=4500), location=Room.objects.get(meeting=m, name="Mercury/Enterprise"), show_location=True)
                ## timeslot 2019-11-19 08:30:00 length 1:15:00 in Minto size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Side Meetings / Open Time", time=datetime.datetime(2019, 11, 19, 8, 30), duration=datetime.timedelta(seconds=4500), location=Room.objects.get(meeting=m, name="Minto"), show_location=True)
                ## timeslot 2019-11-19 08:30:00 length 1:15:00 in Fullerton size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Side Meetings / Open Time", time=datetime.datetime(2019, 11, 19, 8, 30), duration=datetime.timedelta(seconds=4500), location=Room.objects.get(meeting=m, name="Fullerton"), show_location=True)
                ## timeslot 2019-11-19 08:30:00 length 1:15:00 in Bonham size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Side Meetings / Open Time", time=datetime.datetime(2019, 11, 19, 8, 30), duration=datetime.timedelta(seconds=4500), location=Room.objects.get(meeting=m, name="Bonham"), show_location=True)
                ## timeslot 2019-11-19 08:30:00 length 1:15:00 in Bailey size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Side Meetings / Open Time", time=datetime.datetime(2019, 11, 19, 8, 30), duration=datetime.timedelta(seconds=4500), location=Room.objects.get(meeting=m, name="Bailey"), show_location=True)
                ## timeslot 2019-11-19 08:30:00 length 1:15:00 in Ord/Blundell size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Side Meetings / Open Time", time=datetime.datetime(2019, 11, 19, 8, 30), duration=datetime.timedelta(seconds=4500), location=Room.objects.get(meeting=m, name="Ord/Blundell"), show_location=True)
                ## timeslot 2019-11-19 08:30:00 length 1:15:00 in Indiana size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Side Meetings / Open Time", time=datetime.datetime(2019, 11, 19, 8, 30), duration=datetime.timedelta(seconds=4500), location=Room.objects.get(meeting=m, name="Indiana"), show_location=True)
                ## timeslot 2019-11-19 08:30:00 length 1:15:00 in Bras Basah size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Side Meetings / Open Time", time=datetime.datetime(2019, 11, 19, 8, 30), duration=datetime.timedelta(seconds=4500), location=Room.objects.get(meeting=m, name="Bras Basah"), show_location=True)
                ## timeslot 2019-11-19 08:30:00 length 1:15:00 in Butterworth size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Side Meetings / Open Time", time=datetime.datetime(2019, 11, 19, 8, 30), duration=datetime.timedelta(seconds=4500), location=Room.objects.get(meeting=m, name="Butterworth"), show_location=True)
                ## timeslot 2019-11-19 08:30:00 length 10:00:00 in Convention Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="reg", name="IETF Registration", time=datetime.datetime(2019, 11, 19, 8, 30), duration=datetime.timedelta(seconds=36000), location=Room.objects.get(meeting=m, name="Convention Foyer"), show_location=True)
                ## timeslot 2019-11-19 08:00:00 length 1:00:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="break", name="Beverage Break", time=datetime.datetime(2019, 11, 19, 8, 0), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-19 07:30:00 length 2:00:00 in None ##
                TimeSlot.objects.create(meeting=m, type_id="lead", name="IAB Breakfast", time=datetime.datetime(2019, 11, 19, 7, 30), duration=datetime.timedelta(seconds=7200), location=None, show_location=True)
                ## timeslot 2019-11-18 19:30:00 length 1:30:00 in Skai Suite 4 (Swissotel) size: None ##
                TimeSlot.objects.create(meeting=m, type_id="other", name="Newcomers' Dinner (Open to Newcomers. Note that pre-registration is required and a $25USD fee will be charged.)", time=datetime.datetime(2019, 11, 18, 19, 30), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Skai Suite 4 (Swissotel)"), show_location=True)
                ## timeslot 2019-11-18 18:10:00 length 1:30:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="other", name="Hackdemo Happy Hour", time=datetime.datetime(2019, 11, 18, 18, 10), duration=datetime.timedelta(seconds=5400), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-18 18:10:00 length 1:00:00 in Orchard size: 50 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 18, 18, 10), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Orchard"), show_location=True)
                ## timeslot 2019-11-18 18:10:00 length 1:00:00 in VIP A size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 18, 18, 10), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="VIP A"), show_location=True)
                ## timeslot 2019-11-18 18:10:00 length 1:00:00 in Hullet size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 18, 18, 10), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Hullet"), show_location=True)
                ## timeslot 2019-11-18 18:10:00 length 1:00:00 in Olivia size: 150 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 18, 18, 10), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Olivia"), show_location=True)
                ## timeslot 2019-11-18 18:10:00 length 1:00:00 in Sophia size: 200 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 18, 18, 10), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Sophia"), show_location=True)
                ## timeslot 2019-11-18 18:10:00 length 1:00:00 in Collyer size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 18, 18, 10), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Collyer"), show_location=True)
                ## timeslot 2019-11-18 18:10:00 length 1:00:00 in Padang size: 300 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 18, 18, 10), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Padang"), show_location=True)
                ## timeslot 2019-11-18 18:10:00 length 1:00:00 in Canning size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 18, 18, 10), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Canning"), show_location=True)
                ## timeslot 2019-11-18 18:10:00 length 1:00:00 in Canning/Padang size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 18, 18, 10), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Canning/Padang"), show_location=True)
                ## timeslot 2019-11-18 18:10:00 length 1:00:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 18, 18, 10), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-18 18:10:00 length 1:00:00 in Convention Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 18, 18, 10), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Convention Foyer"), show_location=True)
                ## timeslot 2019-11-18 18:10:00 length 1:00:00 in Fairmont Ballroom Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 18, 18, 10), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Fairmont Ballroom Foyer"), show_location=True)
                ## timeslot 2019-11-18 18:10:00 length 1:00:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 18, 18, 10), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-18 18:10:00 length 1:00:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 18, 18, 10), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-18 18:10:00 length 1:00:00 in VIP B size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 18, 18, 10), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="VIP B"), show_location=True)
                ## timeslot 2019-11-18 18:10:00 length 1:00:00 in Clark size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 18, 18, 10), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Clark"), show_location=True)
                ## timeslot 2019-11-18 18:10:00 length 1:00:00 in Mercury/Enterprise size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 18, 18, 10), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Mercury/Enterprise"), show_location=True)
                ## timeslot 2019-11-18 18:10:00 length 1:00:00 in Minto size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 18, 18, 10), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Minto"), show_location=True)
                ## timeslot 2019-11-18 18:10:00 length 1:00:00 in Fullerton size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 18, 18, 10), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Fullerton"), show_location=True)
                ## timeslot 2019-11-18 18:10:00 length 1:00:00 in Bonham size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 18, 18, 10), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Bonham"), show_location=True)
                ## timeslot 2019-11-18 18:10:00 length 1:00:00 in Bailey size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 18, 18, 10), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Bailey"), show_location=True)
                ## timeslot 2019-11-18 18:10:00 length 1:00:00 in Ord/Blundell size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 18, 18, 10), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Ord/Blundell"), show_location=True)
                ## timeslot 2019-11-18 18:10:00 length 1:00:00 in Indiana size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 18, 18, 10), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Indiana"), show_location=True)
                ## timeslot 2019-11-18 18:10:00 length 1:00:00 in Bras Basah size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 18, 18, 10), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Bras Basah"), show_location=True)
                ## timeslot 2019-11-18 18:10:00 length 1:00:00 in Butterworth size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session III", time=datetime.datetime(2019, 11, 18, 18, 10), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Butterworth"), show_location=True)
                ## timeslot 2019-11-18 17:50:00 length 0:20:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="break", name="Beverage Break", time=datetime.datetime(2019, 11, 18, 17, 50), duration=datetime.timedelta(seconds=1200), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-18 16:50:00 length 1:00:00 in Clark size: None ##
                TimeSlot.objects.create(meeting=m, type_id="other", name="TSV AD Office Hours", time=datetime.datetime(2019, 11, 18, 16, 50), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Clark"), show_location=True)
                ## timeslot 2019-11-18 15:50:00 length 2:00:00 in Orchard size: 50 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 18, 15, 50), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Orchard"), show_location=True)
                ## timeslot 2019-11-18 15:50:00 length 2:00:00 in VIP A size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 18, 15, 50), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="VIP A"), show_location=True)
                ## timeslot 2019-11-18 15:50:00 length 2:00:00 in Hullet size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 18, 15, 50), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Hullet"), show_location=True)
                ## timeslot 2019-11-18 15:50:00 length 2:00:00 in Olivia size: 150 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 18, 15, 50), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Olivia"), show_location=True)
                ## timeslot 2019-11-18 15:50:00 length 2:00:00 in Sophia size: 200 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 18, 15, 50), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Sophia"), show_location=True)
                ## timeslot 2019-11-18 15:50:00 length 2:00:00 in Collyer size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 18, 15, 50), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Collyer"), show_location=True)
                ## timeslot 2019-11-18 15:50:00 length 2:00:00 in Padang size: 300 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 18, 15, 50), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Padang"), show_location=True)
                ## timeslot 2019-11-18 15:50:00 length 2:00:00 in Canning size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 18, 15, 50), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Canning"), show_location=True)
                ## timeslot 2019-11-18 15:50:00 length 2:00:00 in Canning/Padang size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 18, 15, 50), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Canning/Padang"), show_location=True)
                ## timeslot 2019-11-18 15:50:00 length 2:00:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 18, 15, 50), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-18 15:50:00 length 2:00:00 in Convention Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 18, 15, 50), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Convention Foyer"), show_location=True)
                ## timeslot 2019-11-18 15:50:00 length 2:00:00 in Fairmont Ballroom Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 18, 15, 50), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Fairmont Ballroom Foyer"), show_location=True)
                ## timeslot 2019-11-18 15:50:00 length 2:00:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 18, 15, 50), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-18 15:50:00 length 2:00:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 18, 15, 50), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-18 15:50:00 length 2:00:00 in VIP B size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 18, 15, 50), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="VIP B"), show_location=True)
                ## timeslot 2019-11-18 15:50:00 length 2:00:00 in Clark size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 18, 15, 50), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Clark"), show_location=True)
                ## timeslot 2019-11-18 15:50:00 length 2:00:00 in Mercury/Enterprise size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 18, 15, 50), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Mercury/Enterprise"), show_location=True)
                ## timeslot 2019-11-18 15:50:00 length 2:00:00 in Minto size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 18, 15, 50), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Minto"), show_location=True)
                ## timeslot 2019-11-18 15:50:00 length 2:00:00 in Fullerton size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 18, 15, 50), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Fullerton"), show_location=True)
                ## timeslot 2019-11-18 15:50:00 length 2:00:00 in Bonham size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 18, 15, 50), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Bonham"), show_location=True)
                ## timeslot 2019-11-18 15:50:00 length 2:00:00 in Bailey size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 18, 15, 50), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Bailey"), show_location=True)
                ## timeslot 2019-11-18 15:50:00 length 2:00:00 in Ord/Blundell size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 18, 15, 50), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Ord/Blundell"), show_location=True)
                ## timeslot 2019-11-18 15:50:00 length 2:00:00 in Indiana size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 18, 15, 50), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Indiana"), show_location=True)
                ## timeslot 2019-11-18 15:50:00 length 2:00:00 in Bras Basah size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 18, 15, 50), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Bras Basah"), show_location=True)
                ## timeslot 2019-11-18 15:50:00 length 2:00:00 in Butterworth size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session II", time=datetime.datetime(2019, 11, 18, 15, 50), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Butterworth"), show_location=True)
                ## timeslot 2019-11-18 15:30:00 length 0:20:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="break", name="Beverage and Snack Break", time=datetime.datetime(2019, 11, 18, 15, 30), duration=datetime.timedelta(seconds=1200), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-18 13:30:00 length 2:00:00 in Orchard size: 50 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 18, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Orchard"), show_location=True)
                ## timeslot 2019-11-18 13:30:00 length 2:00:00 in VIP A size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 18, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="VIP A"), show_location=True)
                ## timeslot 2019-11-18 13:30:00 length 2:00:00 in Hullet size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 18, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Hullet"), show_location=True)
                ## timeslot 2019-11-18 13:30:00 length 2:00:00 in Olivia size: 150 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 18, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Olivia"), show_location=True)
                ## timeslot 2019-11-18 13:30:00 length 2:00:00 in Sophia size: 200 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 18, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Sophia"), show_location=True)
                ## timeslot 2019-11-18 13:30:00 length 2:00:00 in Collyer size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 18, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Collyer"), show_location=True)
                ## timeslot 2019-11-18 13:30:00 length 2:00:00 in Padang size: 300 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 18, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Padang"), show_location=True)
                ## timeslot 2019-11-18 13:30:00 length 2:00:00 in Canning size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 18, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Canning"), show_location=True)
                ## timeslot 2019-11-18 13:30:00 length 2:00:00 in Canning/Padang size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 18, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Canning/Padang"), show_location=True)
                ## timeslot 2019-11-18 13:30:00 length 2:00:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 18, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-18 13:30:00 length 2:00:00 in Convention Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 18, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Convention Foyer"), show_location=True)
                ## timeslot 2019-11-18 13:30:00 length 2:00:00 in Fairmont Ballroom Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 18, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Fairmont Ballroom Foyer"), show_location=True)
                ## timeslot 2019-11-18 13:30:00 length 2:00:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 18, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-18 13:30:00 length 2:00:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 18, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-18 13:30:00 length 2:00:00 in VIP B size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 18, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="VIP B"), show_location=True)
                ## timeslot 2019-11-18 13:30:00 length 2:00:00 in Clark size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 18, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Clark"), show_location=True)
                ## timeslot 2019-11-18 13:30:00 length 2:00:00 in Mercury/Enterprise size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 18, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Mercury/Enterprise"), show_location=True)
                ## timeslot 2019-11-18 13:30:00 length 2:00:00 in Minto size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 18, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Minto"), show_location=True)
                ## timeslot 2019-11-18 13:30:00 length 2:00:00 in Fullerton size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 18, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Fullerton"), show_location=True)
                ## timeslot 2019-11-18 13:30:00 length 2:00:00 in Bonham size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 18, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Bonham"), show_location=True)
                ## timeslot 2019-11-18 13:30:00 length 2:00:00 in Bailey size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 18, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Bailey"), show_location=True)
                ## timeslot 2019-11-18 13:30:00 length 2:00:00 in Ord/Blundell size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 18, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Ord/Blundell"), show_location=True)
                ## timeslot 2019-11-18 13:30:00 length 2:00:00 in Indiana size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 18, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Indiana"), show_location=True)
                ## timeslot 2019-11-18 13:30:00 length 2:00:00 in Bras Basah size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 18, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Bras Basah"), show_location=True)
                ## timeslot 2019-11-18 13:30:00 length 2:00:00 in Butterworth size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Afternoon Session I", time=datetime.datetime(2019, 11, 18, 13, 30), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Butterworth"), show_location=True)
                ## timeslot 2019-11-18 12:00:00 length 1:30:00 in None ##
                TimeSlot.objects.create(meeting=m, type_id="break", name="Break", time=datetime.datetime(2019, 11, 18, 12, 0), duration=datetime.timedelta(seconds=5400), location=None, show_location=False)
                ## timeslot 2019-11-18 10:00:00 length 2:00:00 in Orchard size: 50 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 18, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Orchard"), show_location=True)
                ## timeslot 2019-11-18 10:00:00 length 2:00:00 in VIP A size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 18, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="VIP A"), show_location=True)
                ## timeslot 2019-11-18 10:00:00 length 2:00:00 in Hullet size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 18, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Hullet"), show_location=True)
                ## timeslot 2019-11-18 10:00:00 length 2:00:00 in Olivia size: 150 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 18, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Olivia"), show_location=True)
                ## timeslot 2019-11-18 10:00:00 length 2:00:00 in Sophia size: 200 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 18, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Sophia"), show_location=True)
                ## timeslot 2019-11-18 10:00:00 length 2:00:00 in Collyer size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 18, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Collyer"), show_location=True)
                ## timeslot 2019-11-18 10:00:00 length 2:00:00 in Padang size: 300 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 18, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Padang"), show_location=True)
                ## timeslot 2019-11-18 10:00:00 length 2:00:00 in Canning size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 18, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Canning"), show_location=True)
                ## timeslot 2019-11-18 10:00:00 length 2:00:00 in Canning/Padang size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 18, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Canning/Padang"), show_location=True)
                ## timeslot 2019-11-18 10:00:00 length 2:00:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 18, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-18 10:00:00 length 2:00:00 in Convention Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 18, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Convention Foyer"), show_location=True)
                ## timeslot 2019-11-18 10:00:00 length 2:00:00 in Fairmont Ballroom Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 18, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Fairmont Ballroom Foyer"), show_location=True)
                ## timeslot 2019-11-18 10:00:00 length 2:00:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 18, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-18 10:00:00 length 2:00:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 18, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-18 10:00:00 length 2:00:00 in VIP B size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 18, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="VIP B"), show_location=True)
                ## timeslot 2019-11-18 10:00:00 length 2:00:00 in Clark size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 18, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Clark"), show_location=True)
                ## timeslot 2019-11-18 10:00:00 length 2:00:00 in Mercury/Enterprise size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 18, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Mercury/Enterprise"), show_location=True)
                ## timeslot 2019-11-18 10:00:00 length 2:00:00 in Minto size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 18, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Minto"), show_location=True)
                ## timeslot 2019-11-18 10:00:00 length 2:00:00 in Fullerton size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 18, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Fullerton"), show_location=True)
                ## timeslot 2019-11-18 10:00:00 length 2:00:00 in Bonham size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 18, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Bonham"), show_location=True)
                ## timeslot 2019-11-18 10:00:00 length 2:00:00 in Bailey size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 18, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Bailey"), show_location=True)
                ## timeslot 2019-11-18 10:00:00 length 2:00:00 in Ord/Blundell size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 18, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Ord/Blundell"), show_location=True)
                ## timeslot 2019-11-18 10:00:00 length 2:00:00 in Indiana size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 18, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Indiana"), show_location=True)
                ## timeslot 2019-11-18 10:00:00 length 2:00:00 in Bras Basah size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 18, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Bras Basah"), show_location=True)
                ## timeslot 2019-11-18 10:00:00 length 2:00:00 in Butterworth size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Morning Session I", time=datetime.datetime(2019, 11, 18, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Butterworth"), show_location=True)
                ## timeslot 2019-11-18 09:00:00 length 1:00:00 in Fullerton size: None ##
                TimeSlot.objects.create(meeting=m, type_id="other", name="NomCom Office Hours", time=datetime.datetime(2019, 11, 18, 9, 0), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Fullerton"), show_location=True)
                ## timeslot 2019-11-18 08:30:00 length 1:15:00 in None ##
                TimeSlot.objects.create(meeting=m, type_id="other", name="Side Meetings / Open Time", time=datetime.datetime(2019, 11, 18, 8, 30), duration=datetime.timedelta(seconds=4500), location=None, show_location=False)
                ## timeslot 2019-11-18 08:30:00 length 10:00:00 in Convention Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="reg", name="IETF Registration", time=datetime.datetime(2019, 11, 18, 8, 30), duration=datetime.timedelta(seconds=36000), location=Room.objects.get(meeting=m, name="Convention Foyer"), show_location=True)
                ## timeslot 2019-11-18 08:00:00 length 1:00:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="break", name="Beverage Break", time=datetime.datetime(2019, 11, 18, 8, 0), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-18 08:00:00 length 1:00:00 in Skai Suite 1 (Swissotel) size: None ##
                TimeSlot.objects.create(meeting=m, type_id="other", name="Systers Networking Event", time=datetime.datetime(2019, 11, 18, 8, 0), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Skai Suite 1 (Swissotel)"), show_location=True)
                ## timeslot 2019-11-17 18:00:00 length 2:00:00 in Orchard size: 50 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Hot RFC Lightning Talks", time=datetime.datetime(2019, 11, 17, 18, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Orchard"), show_location=True)
                ## timeslot 2019-11-17 18:00:00 length 2:00:00 in VIP A size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Hot RFC Lightning Talks", time=datetime.datetime(2019, 11, 17, 18, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="VIP A"), show_location=True)
                ## timeslot 2019-11-17 18:00:00 length 2:00:00 in Hullet size: 100 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Hot RFC Lightning Talks", time=datetime.datetime(2019, 11, 17, 18, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Hullet"), show_location=True)
                ## timeslot 2019-11-17 18:00:00 length 2:00:00 in Olivia size: 150 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Hot RFC Lightning Talks", time=datetime.datetime(2019, 11, 17, 18, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Olivia"), show_location=True)
                ## timeslot 2019-11-17 18:00:00 length 2:00:00 in Sophia size: 200 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Hot RFC Lightning Talks", time=datetime.datetime(2019, 11, 17, 18, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Sophia"), show_location=True)
                ## timeslot 2019-11-17 18:00:00 length 2:00:00 in Collyer size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Hot RFC Lightning Talks", time=datetime.datetime(2019, 11, 17, 18, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Collyer"), show_location=True)
                ## timeslot 2019-11-17 18:00:00 length 2:00:00 in Padang size: 300 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Hot RFC Lightning Talks", time=datetime.datetime(2019, 11, 17, 18, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Padang"), show_location=True)
                ## timeslot 2019-11-17 18:00:00 length 2:00:00 in Canning size: 250 ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Hot RFC Lightning Talks", time=datetime.datetime(2019, 11, 17, 18, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Canning"), show_location=True)
                ## timeslot 2019-11-17 18:00:00 length 2:00:00 in Canning/Padang size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Hot RFC Lightning Talks", time=datetime.datetime(2019, 11, 17, 18, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Canning/Padang"), show_location=True)
                ## timeslot 2019-11-17 18:00:00 length 2:00:00 in Stamford & Fairmont Ballroom Foyers size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Hot RFC Lightning Talks", time=datetime.datetime(2019, 11, 17, 18, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Stamford & Fairmont Ballroom Foyers"), show_location=True)
                ## timeslot 2019-11-17 18:00:00 length 2:00:00 in Convention Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Hot RFC Lightning Talks", time=datetime.datetime(2019, 11, 17, 18, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Convention Foyer"), show_location=True)
                ## timeslot 2019-11-17 18:00:00 length 2:00:00 in Fairmont Ballroom Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Hot RFC Lightning Talks", time=datetime.datetime(2019, 11, 17, 18, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Fairmont Ballroom Foyer"), show_location=True)
                ## timeslot 2019-11-17 18:00:00 length 2:00:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Hot RFC Lightning Talks", time=datetime.datetime(2019, 11, 17, 18, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-17 18:00:00 length 2:00:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Hot RFC Lightning Talks", time=datetime.datetime(2019, 11, 17, 18, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-17 18:00:00 length 2:00:00 in VIP B size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Hot RFC Lightning Talks", time=datetime.datetime(2019, 11, 17, 18, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="VIP B"), show_location=True)
                ## timeslot 2019-11-17 18:00:00 length 2:00:00 in Clark size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Hot RFC Lightning Talks", time=datetime.datetime(2019, 11, 17, 18, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Clark"), show_location=True)
                ## timeslot 2019-11-17 18:00:00 length 2:00:00 in Mercury/Enterprise size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Hot RFC Lightning Talks", time=datetime.datetime(2019, 11, 17, 18, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Mercury/Enterprise"), show_location=True)
                ## timeslot 2019-11-17 18:00:00 length 2:00:00 in Minto size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Hot RFC Lightning Talks", time=datetime.datetime(2019, 11, 17, 18, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Minto"), show_location=True)
                ## timeslot 2019-11-17 18:00:00 length 2:00:00 in Fullerton size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Hot RFC Lightning Talks", time=datetime.datetime(2019, 11, 17, 18, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Fullerton"), show_location=True)
                ## timeslot 2019-11-17 18:00:00 length 2:00:00 in Bonham size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Hot RFC Lightning Talks", time=datetime.datetime(2019, 11, 17, 18, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Bonham"), show_location=True)
                ## timeslot 2019-11-17 18:00:00 length 2:00:00 in Bailey size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Hot RFC Lightning Talks", time=datetime.datetime(2019, 11, 17, 18, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Bailey"), show_location=True)
                ## timeslot 2019-11-17 18:00:00 length 2:00:00 in Ord/Blundell size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Hot RFC Lightning Talks", time=datetime.datetime(2019, 11, 17, 18, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Ord/Blundell"), show_location=True)
                ## timeslot 2019-11-17 18:00:00 length 2:00:00 in Indiana size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Hot RFC Lightning Talks", time=datetime.datetime(2019, 11, 17, 18, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Indiana"), show_location=True)
                ## timeslot 2019-11-17 18:00:00 length 2:00:00 in Bras Basah size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Hot RFC Lightning Talks", time=datetime.datetime(2019, 11, 17, 18, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Bras Basah"), show_location=True)
                ## timeslot 2019-11-17 18:00:00 length 2:00:00 in Butterworth size: None ##
                TimeSlot.objects.create(meeting=m, type_id="regular", name="Hot RFC Lightning Talks", time=datetime.datetime(2019, 11, 17, 18, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Butterworth"), show_location=True)
                ## timeslot 2019-11-17 17:00:00 length 2:00:00 in Fairmont Ballroom Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="other", name="Welcome Reception", time=datetime.datetime(2019, 11, 17, 17, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Fairmont Ballroom Foyer"), show_location=True)
                ## timeslot 2019-11-17 16:00:00 length 1:00:00 in Fairmont Ballroom Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="other", name="Newcomers' Quick Connections (Open to Newcomers. Note that pre-registration is required)", time=datetime.datetime(2019, 11, 17, 16, 0), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Fairmont Ballroom Foyer"), show_location=True)
                ## timeslot 2019-11-17 13:45:00 length 1:00:00 in Sophia size: 200 ##
                TimeSlot.objects.create(meeting=m, type_id="other", name="Tutorial: Service Discovery for IP Applications", time=datetime.datetime(2019, 11, 17, 13, 45), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Sophia"), show_location=True)
                ## timeslot 2019-11-17 12:30:00 length 1:00:00 in Olivia size: 150 ##
                TimeSlot.objects.create(meeting=m, type_id="other", name="Tutorial: Newcomers' Overview", time=datetime.datetime(2019, 11, 17, 12, 30), duration=datetime.timedelta(seconds=3600), location=Room.objects.get(meeting=m, name="Olivia"), show_location=True)
                ## timeslot 2019-11-17 10:00:00 length 2:00:00 in Olivia size: 150 ##
                TimeSlot.objects.create(meeting=m, type_id="other", name="IEPG Meeting", time=datetime.datetime(2019, 11, 17, 10, 0), duration=datetime.timedelta(seconds=7200), location=Room.objects.get(meeting=m, name="Olivia"), show_location=True)
                ## timeslot 2019-11-17 10:00:00 length 8:00:00 in Convention Foyer size: None ##
                TimeSlot.objects.create(meeting=m, type_id="reg", name="IETF Registration", time=datetime.datetime(2019, 11, 17, 10, 0), duration=datetime.timedelta(seconds=28800), location=Room.objects.get(meeting=m, name="Convention Foyer"), show_location=True)
                ## timeslot 2019-11-17 08:30:00 length 7:30:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="other", name="IETF Hackathon", time=datetime.datetime(2019, 11, 17, 8, 30), duration=datetime.timedelta(seconds=27000), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                ## timeslot 2019-11-16 09:30:00 length 8:30:00 in Ord size: None ##
                TimeSlot.objects.create(meeting=m, type_id="other", name="Code Sprint", time=datetime.datetime(2019, 11, 16, 9, 30), duration=datetime.timedelta(seconds=30600), location=Room.objects.get(meeting=m, name="Ord"), show_location=True)
                ## timeslot 2019-11-16 08:30:00 length 13:30:00 in Moor/Morrison size: None ##
                TimeSlot.objects.create(meeting=m, type_id="other", name="IETF Hackathon", time=datetime.datetime(2019, 11, 16, 8, 30), duration=datetime.timedelta(seconds=48600), location=Room.objects.get(meeting=m, name="Moor/Morrison"), show_location=True)
                
                for s in m.session_set.all():
                    SchedulingEvent.objects.create(session=s, status_id='schedw', by_id=1)
                
                transaction.commit()
                self.stdout.write("IETF 999 created.\n")

