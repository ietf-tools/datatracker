# Copyright The IETF Trust 2020, All Rights Reserved
import calendar
import datetime
from io import StringIO

from django.core.management.base import CommandError

from ietf.utils.test_utils import TestCase
from ietf.group.factories import GroupFactory, RoleFactory
from ietf.person.factories import PersonFactory
from ietf.meeting.models import Constraint, TimerangeName, BusinessConstraint, SchedTimeSessAssignment, Schedule
from ietf.meeting.factories import MeetingFactory, RoomFactory, TimeSlotFactory, SessionFactory, ScheduleFactory
from ietf.meeting.management.commands import generate_schedule
from ietf.name.models import ConstraintName

import debug                            # pyflakes:ignore


class ScheduleGeneratorTest(TestCase):
    def setUp(self):
        # Create a meeting of 2 days, 5 sessions per day, in 2 rooms. There are 3 days
        # actually created, but sundays are ignored.
        # Two rooms is a fairly low level of simultaneous schedules, this is needed
        # because the schedule in these tests is much more complex than a real schedule.
        self.meeting = MeetingFactory(type_id='ietf', days=2, date=datetime.date(2020, 5, 31))
        self.rooms = [
            RoomFactory(meeting=self.meeting, capacity=100),
            RoomFactory(meeting=self.meeting, capacity=10)
        ]
        
        self.timeslots = []
        for room in self.rooms:
            for day in range(0, 3):
                for hour in range(12, 17): 
                    t = TimeSlotFactory(
                        meeting=self.meeting,
                        location=room,
                        time=datetime.datetime.combine(
                            self.meeting.date + datetime.timedelta(days=day),
                            datetime.time(hour, 0),
                        ),
                        duration=datetime.timedelta(minutes=60),
                    )
                    self.timeslots.append(t)
                            
        self.first_meeting_day = calendar.day_name[self.meeting.date.weekday()].lower()
        
        self.area1 = GroupFactory(acronym='area1', type_id='area')
        self.area2 = GroupFactory(acronym='area2', type_id='area')
        self.wg1 = GroupFactory(acronym='wg1', parent=self.area1)
        self.wg2 = GroupFactory(acronym='wg2', )
        self.wg3 = GroupFactory(acronym='wg3', )
        self.bof1 = GroupFactory(acronym='bof1', parent=self.area1, state_id='bof')
        self.bof2 = GroupFactory(acronym='bof2', parent=self.area2, state_id='bof')
        self.prg1 = GroupFactory(acronym='prg1', parent=self.area2, type_id='rg', state_id='proposed')
        self.all_groups = [self.area1, self.area2, self.wg1, self.wg2, self.wg3, self.bof1,
                           self.bof2, self.prg1]

        self.ad_role = RoleFactory(group=self.wg1, name_id='ad')
        RoleFactory(group=self.bof1, name_id='ad', person=self.ad_role.person)

        self.person1 = PersonFactory()

        self.stdout = StringIO()

    def test_normal_schedule(self):
        self._create_basic_sessions()
        generator = generate_schedule.ScheduleHandler(self.stdout, self.meeting.number, verbosity=3)
        violations, cost = generator.run()
        self.assertEqual(violations, self.fixed_violations)
        self.assertEqual(cost, self.fixed_cost)

        self.stdout.seek(0)
        output = self.stdout.read()
        self.assertIn('WARNING: session wg2 (pk 13) has no attendees set', output)
        self.assertIn('scheduling 13 sessions in 20 timeslots', output)
        self.assertIn('Optimiser starting run 1', output)
        self.assertIn('Optimiser found an optimal schedule', output)
        
        schedule = self.meeting.schedule_set.get(name__startswith='Auto-')
        self.assertEqual(schedule.assignments.count(), 13)

    def test_unresolvable_schedule(self):
        self._create_basic_sessions()
        for group in self.all_groups:
            group.parent = self.area1
            group.ad = self.ad_role
            group.save()
            c = Constraint.objects.create(meeting=self.meeting, source=group, name_id='timerange')
            c.timeranges.set(TimerangeName.objects.filter(slug__startswith=self.first_meeting_day))
            Constraint.objects.create(meeting=self.meeting, source=group,
                                      name_id='bethere', person=self.person1)

        generator = generate_schedule.ScheduleHandler(self.stdout, self.meeting.number, verbosity=2)
        violations, cost = generator.run()
        self.assertNotEqual(violations, [])
        self.assertGreater(cost, self.fixed_cost)

        self.stdout.seek(0)
        output = self.stdout.read()
        self.assertIn('Optimiser did not find perfect schedule', output)

    def test_too_many_sessions(self):
        self._create_basic_sessions()
        self._create_basic_sessions()
        with self.assertRaises(CommandError):
            generator = generate_schedule.ScheduleHandler(self.stdout, self.meeting.number, verbosity=0)
            generator.run()

    def test_invalid_meeting_number(self):
        with self.assertRaises(CommandError):
            generator = generate_schedule.ScheduleHandler(self.stdout, 'not-valid-meeting-number-aaaa', verbosity=0)
            generator.run()

    def test_base_schedule(self):
        self._create_basic_sessions()
        base_schedule = self._create_base_schedule()
        assignment = base_schedule.assignments.first()
        base_session = assignment.session
        base_timeslot = assignment.timeslot

        generator = generate_schedule.ScheduleHandler(
            self.stdout,
            self.meeting.number,
            verbosity=3,
            base_id=generate_schedule.ScheduleId.from_schedule(base_schedule),
        )
        violations, cost = generator.run()

        expected_violations = self.fixed_violations + [
            '{}: scheduled in too small room'.format(base_session.group.acronym),
        ]
        expected_cost = sum([
            self.fixed_cost,
            BusinessConstraint.objects.get(slug='session_requires_trim').penalty,
        ])

        self.assertEqual(violations, expected_violations)
        self.assertEqual(cost, expected_cost)

        generated_schedule = Schedule.objects.get(name=generator.name)
        self.assertEqual(generated_schedule.base, base_schedule,
                         'Base schedule should be attached to generated schedule')
        self.assertCountEqual(
            [a.session for a in base_timeslot.sessionassignments.all()],
            [base_session],
            'A session must not be scheduled on top of a base schedule assignment',
        )

        self.stdout.seek(0)
        output = self.stdout.read()
        self.assertIn('Applying schedule {} as base schedule'.format(
            generate_schedule.ScheduleId.from_schedule(base_schedule)
        ), output)
        self.assertIn('WARNING: session wg2 (pk 13) has no attendees set', output)
        self.assertIn('scheduling 13 sessions in 19 timeslots', output)  # 19 because base is using one
        self.assertIn('Optimiser starting run 1', output)
        self.assertIn('Optimiser found an optimal schedule', output)

    def test_base_schedule_dynamic_cost(self):
        """Conflicts with the base schedule should contribute to dynamic cost"""
        # create the base schedule
        base_schedule = self._create_base_schedule()
        assignment = base_schedule.assignments.first()
        base_session = assignment.session
        base_timeslot = assignment.timeslot

        # create another base session that conflicts with the first
        SessionFactory(
            meeting=self.meeting,
            group=self.wg2,
            attendees=10,
            add_to_schedule=False,
        )
        SchedTimeSessAssignment.objects.create(
            schedule=base_schedule,
            session=SessionFactory(meeting=self.meeting, group=self.wg2, attendees=10, add_to_schedule=False),
            timeslot=self.meeting.timeslot_set.filter(
                time=base_timeslot.time + datetime.timedelta(days=1)
            ).exclude(
                sessionassignments__schedule=base_schedule
            ).first(),
        )
        # make the base session group conflict with wg1 and wg2
        Constraint.objects.create(
            meeting=self.meeting,
            source=base_session.group,
            name_id='tech_overlap',
            target=self.wg1,
        )
        Constraint.objects.create(
            meeting=self.meeting,
            source=base_session.group,
            name_id='wg_adjacent',
            target=self.wg2,
        )

        # create the session to schedule that will conflict
        conflict_session = SessionFactory(meeting=self.meeting, group=self.wg1, add_to_schedule=False,
                                          attendees=10, requested_duration=datetime.timedelta(hours=1))
        conflict_timeslot = self.meeting.timeslot_set.filter(
            time=base_timeslot.time,  # same time as base session
            location__capacity__gte=conflict_session.attendees,  # no capacity violation
        ).exclude(
            sessionassignments__schedule=base_schedule  # do not use the same timeslot
        ).first()

        # Create the ScheduleHandler with the base schedule
        handler = generate_schedule.ScheduleHandler(
            self.stdout,
            self.meeting.number,
            max_cycles=1,
            base_id=generate_schedule.ScheduleId.from_schedule(base_schedule),
        )

        # run once to be sure everything is primed, we'll ignore the outcome
        handler.run()

        timeslot_lut = {ts.timeslot_pk: ts for ts in handler.schedule.timeslots}
        session_lut = {sess.session_pk: sess for sess in handler.schedule.sessions}
        # now create schedule with a conflict
        handler.schedule.schedule = {
            timeslot_lut[conflict_timeslot.pk]: session_lut[conflict_session.pk],
        }

        # check that we get the expected dynamic cost - should NOT include conflict with wg2
        # because that is in the base schedule
        violations, cost = handler.schedule.calculate_dynamic_cost()
        self.assertCountEqual(
            violations,
            ['{}: group conflict with {}'.format(base_session.group.acronym, self.wg1.acronym)]
        )
        self.assertEqual(
            cost,
            ConstraintName.objects.get(pk='tech_overlap').penalty,
        )

        # check the total cost - now should see wg2 and capacity conflicts
        violations, cost = handler.schedule.total_schedule_cost()
        self.assertCountEqual(
            violations,
            [
                '{}: group conflict with {}'.format(base_session.group.acronym, self.wg1.acronym),
                '{}: missing adjacency with {}, adjacents are: '.format(base_session.group.acronym, self.wg2.acronym),
                '{}: scheduled in too small room'.format(base_session.group.acronym),
            ]
        )
        self.assertEqual(
            cost,
            sum([
                BusinessConstraint.objects.get(pk='session_requires_trim').penalty,
                ConstraintName.objects.get(pk='wg_adjacent').penalty,
                ConstraintName.objects.get(pk='tech_overlap').penalty,
            ]),
        )


    def _create_basic_sessions(self):
        for group in self.all_groups:
            SessionFactory(meeting=self.meeting, group=group, add_to_schedule=False, attendees=5,
                           requested_duration=datetime.timedelta(hours=1))
        for group in self.bof1, self.bof2, self.wg2:
            SessionFactory(meeting=self.meeting, group=group, add_to_schedule=False, attendees=55,
                           requested_duration=datetime.timedelta(hours=1))
        SessionFactory(meeting=self.meeting, group=self.wg2, add_to_schedule=False, attendees=500,
                       requested_duration=datetime.timedelta(hours=2))

        joint_session = SessionFactory(meeting=self.meeting, group=self.wg2, add_to_schedule=False)
        joint_session.joint_with_groups.add(self.wg3)

        Constraint.objects.create(meeting=self.meeting, source=self.wg1,
                                  name_id='wg_adjacent', target=self.area1)
        Constraint.objects.create(meeting=self.meeting, source=self.wg2,
                                  name_id='conflict', target=self.bof1)
        Constraint.objects.create(meeting=self.meeting, source=self.bof1,
                                  name_id='bethere', person=self.person1)
        Constraint.objects.create(meeting=self.meeting, source=self.wg2,
                                  name_id='bethere', person=self.person1)
        Constraint.objects.create(meeting=self.meeting, source=self.bof1,
                                  name_id='time_relation', time_relation='subsequent-days')
        Constraint.objects.create(meeting=self.meeting, source=self.bof2,
                                  name_id='time_relation', time_relation='one-day-separation')

        timerange_c1 = Constraint.objects.create(meeting=self.meeting, source=self.wg2,
                                                 name_id='timerange')
        timerange_c1.timeranges.set(TimerangeName.objects.filter(slug__startswith=self.first_meeting_day))

        self.fixed_violations = ['No timeslot with sufficient duration available for wg2, '
                                 'requested 2:00:00, trimmed to 1:00:00', 
                                 'No timeslot with sufficient capacity available for wg2, '
                                 'requested 500, trimmed to 100']
        self.fixed_cost = BusinessConstraint.objects.get(slug='session_requires_trim').penalty * 2

    def _create_base_schedule(self):
        """Create a base schedule

        Generates a base schedule using the first Monday timeslot with a location
        with capacity smaller than 200.
        """
        base_schedule = ScheduleFactory(meeting=self.meeting)
        base_reg_session = SessionFactory(
            meeting=self.meeting,
            requested_duration=datetime.timedelta(minutes=60),
            attendees=200,
           add_to_schedule=False
        )
        # use a timeslot not on Sunday
        ts = self.meeting.timeslot_set.filter(
            time__gt=self.meeting.date + datetime.timedelta(days=1),
            location__capacity__lt=base_reg_session.attendees,
        ).order_by(
            'time'
        ).first()
        SchedTimeSessAssignment.objects.create(
            schedule=base_schedule,
            session=base_reg_session,
            timeslot=ts,
        )
        return base_schedule

