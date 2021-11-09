import datetime
import random

from django.core.management.base import BaseCommand, CommandError

from ietf.group.models import Group
from ietf.meeting.factories import RoomFactory, TimeSlotFactory, SessionFactory
from ietf.meeting.helpers import get_meeting
from ietf.meeting.models import Room, Session
from ietf.name.models import SessionPurposeName


class Command(BaseCommand):
    help = 'Set up a demo of the session purpose updates'

    DEMO_PREFIX='PDemo'  # used to identify things added by this command

    def add_arguments(self, parser):
        parser.add_argument('--remove', action='store_true')

    def handle(self, *args, **options):
        if options['remove']:
            self.remove_demo()
        else:
            self.install_demo()

    def remove_demo(self):
        self.stdout.write(f'Removing rooms with "{self.DEMO_PREFIX}" name prefix...\n')
        Room.objects.filter(name__startswith=self.DEMO_PREFIX).delete()
        self.stdout.write(f'Removing sessions with "{self.DEMO_PREFIX}" name prefix...\n')
        Session.objects.filter(name__startswith=self.DEMO_PREFIX).delete()

    def install_demo(self):
        # get meeting
        try:
            meeting = get_meeting(days=14)  # matches how secr app finds meetings
        except:
            raise CommandError('No upcoming meeting to modify')

        # create rooms
        self.stdout.write('Creating rooms...\n')
        rooms = [
            RoomFactory(meeting=meeting, name=f'{self.DEMO_PREFIX} 1'),
            RoomFactory(meeting=meeting, name=f'{self.DEMO_PREFIX} 2'),
            RoomFactory(meeting=meeting, name=f'{self.DEMO_PREFIX} 3'),
        ]

        # get all the timeslot types used by a session purpose
        type_ids = set()
        for purpose in SessionPurposeName.objects.filter(used=True):
            type_ids.update(purpose.timeslot_types)

        # set up timeslots
        self.stdout.write('Creating timeslots...\n')
        for room in rooms:
            for day in range(meeting.days):
                date = meeting.get_meeting_date(day)
                for n, type_id in enumerate(type_ids):
                    TimeSlotFactory(
                        type_id=type_id,
                        meeting=meeting,
                        location=room,
                        time=datetime.datetime.combine(date, datetime.time(10, 0, 0)) + datetime.timedelta(hours=n),
                        duration=datetime.timedelta(hours=1),
                    )

        # set up sessions
        self.stdout.write('Creating sessions...')
        groups_for_session_purpose = {
            purpose.slug: list(
                Group.objects.filter(
                    type__features__session_purposes__contains=f'"{purpose.slug}"',
                    state_id='active',
                )
            )
            for purpose in SessionPurposeName.objects.filter(used=True)
        }
        for purpose in SessionPurposeName.objects.filter(used=True):
            for type_id in purpose.timeslot_types:
                group=random.choice(groups_for_session_purpose[purpose.slug])
                SessionFactory(
                    meeting=meeting,
                    purpose=purpose,
                    type_id=type_id,
                    group=group,
                    name=f'{self.DEMO_PREFIX} for {group.acronym}',
                    status_id='schedw',
                    add_to_schedule=False,
                )

        self.stdout.write(f'\nRooms and sessions created with "{self.DEMO_PREFIX}" as name prefix\n')