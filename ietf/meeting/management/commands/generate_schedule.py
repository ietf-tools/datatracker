# Copyright The IETF Trust 2021, All Rights Reserved
# For an overview of this process and context, see:
# https://trac.ietf.org/trac/ietfdb/wiki/MeetingConstraints
from __future__ import absolute_import, print_function, unicode_literals

import calendar
import datetime
import math
import random
import string
import sys
import time

from collections import defaultdict
from functools import lru_cache
from typing import NamedTuple, Optional

from django.contrib.humanize.templatetags.humanize import intcomma
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

import debug                            # pyflakes:ignore

from ietf.person.models import Person
from ietf.meeting import models
from ietf.meeting.helpers import get_person_by_email

# 40 runs of the optimiser for IETF 106 with cycles=160 resulted in 16
# zero-violation invocations, with a mean number of runs of 91 and 
# std-dev 41.  On the machine used, 160 cycles had a runtime of about
# 30 minutes.  Setting default to 160, as 80 or 100 seems too low to have
# a reasonable rate of success in generating zero-cost schedules.

OPTIMISER_MAX_CYCLES = 160


class ScheduleId(NamedTuple):
    """Represents a schedule id as name and owner"""
    name: str
    owner: Optional[str] = None

    @classmethod
    def from_str(cls, s):
        """Parse id of the form [owner/]name"""
        return cls(*reversed(s.split('/', 1)))

    @classmethod
    def from_schedule(cls, sched):
        return cls(sched.name, str(sched.owner.email()))

    def __str__(self):
        return '/'.join(tok for tok in reversed(self) if tok is not None)


class Command(BaseCommand):
    help = 'Create a meeting schedule'

    def add_arguments(self, parser):
        parser.add_argument('-m', '--meeting', default=None,
                            help='the number of the meeting to generate a schedule for')
        parser.add_argument('-n', '--name', default=None,
                            help='a name for the generated schedule')
        parser.add_argument('-r', '--max-runs', type=int, dest='max_cycles',
                            default=OPTIMISER_MAX_CYCLES,
                            help='maximum optimiser runs')
        parser.add_argument('-b', '--base-schedule',
                            type=ScheduleId.from_str,
                            dest='base_id',
                            default=None,
                            help=(
                                'Base schedule for generated schedule, specified as "[owner/]name"'
                                ' (default is no base schedule; owner not required if name is unique)'
                            ))

    def handle(self, meeting, name, max_cycles, verbosity, base_id, *args, **kwargs):
        ScheduleHandler(self.stdout, meeting, name, max_cycles, verbosity, base_id).run()


class ScheduleHandler(object):
    def __init__(self, stdout, meeting_number, name=None, max_cycles=OPTIMISER_MAX_CYCLES,
                 verbosity=1, base_id=None):
        self.stdout = stdout
        self.verbosity = verbosity
        self.name = name
        self.max_cycles = max_cycles
        if meeting_number:
            try:
                self.meeting = models.Meeting.objects.get(type="ietf", number=meeting_number)
            except models.Meeting.DoesNotExist:
                raise CommandError('Unknown meeting number {}'.format(meeting_number))
        else:
            self.meeting = models.Meeting.get_current_meeting()

        if base_id is None:
            self.base_schedule = None
        else:
            base_candidates = models.Schedule.objects.filter(meeting=self.meeting, name=base_id.name)
            if base_id.owner is not None:
                base_candidates = base_candidates.filter(owner=get_person_by_email(base_id.owner))
            if base_candidates.count() == 0:
                raise CommandError('Base schedule "{}" not found'.format(base_id))
            elif base_candidates.count() >= 2:
                raise CommandError('Base schedule "{}" not unique (candidates are {})'.format(
                    base_id,
                    ', '.join(str(ScheduleId.from_schedule(sched)) for sched in base_candidates)
                ))
            else:
                self.base_schedule = base_candidates.first()  # only have one

        if self.verbosity >= 1:
            msgs = ['Running automatic schedule layout for meeting IETF {}'.format(self.meeting.number)]
            if self.base_schedule is not None:
                msgs.append('Applying schedule {} as base schedule'.format(ScheduleId.from_schedule(self.base_schedule)))
            self.stdout.write('\n{}\n\n'.format('\n'.join(msgs)))
        self._load_meeting()

    def run(self):
        """Schedule all sessions"""
        beg_time = time.time()
        self.schedule.fill_initial_schedule()
        violations, cost = self.schedule.total_schedule_cost()
        end_time = time.time()
        tot_time = end_time - beg_time
        if self.verbosity >= 1:
            self.stdout.write('Initial schedule completed with %s violations, total cost %s, in %dm %.2fs'
                               % (len(violations), intcomma(cost), tot_time//60, tot_time%60))

        beg_time = time.time()
        runs = self.schedule.optimise_schedule()
        violations, cost = self.schedule.total_schedule_cost()
        end_time = time.time()
        tot_time = end_time - beg_time
        if self.verbosity >= 1:
            vc = len(violations)
            self.stdout.write('Optimisation completed with %s violation%s, cost %s, %s runs in %dm %.2fs'
                               % (vc, '' if vc==1 else 's', intcomma(cost), runs, tot_time//60, tot_time%60))
        if self.verbosity >= 1 and violations:
            self.stdout.write('Remaining violations:')
            for v in violations:
                self.stdout.write(v)
                
        self.schedule.optimise_timeslot_capacity()

        self._save_schedule(cost)
        return violations, cost
    
    def _save_schedule(self, cost):
        if not self.name:
            count = models.Schedule.objects.filter(name__startswith='auto-%s-'%self.meeting.number).count()
            self.name = 'auto-%s-%02d' % (self.meeting.number, count)
        if models.Schedule.objects.filter(name=self.name).exists():
            self.stdout.write("WARNING: A schedule with the name '%s' already exists.  Picking another random one." % self.name)
            self.name = 'auto-%s-%s' % (self.meeting.number, ''.join(random.choice(string.ascii_lowercase) for i in range(10)))
        schedule_db = models.Schedule.objects.create(
            meeting=self.meeting,
            name=self.name,
            base=self.base_schedule,
            owner=Person.objects.get(name='(System)'),
            public=False,
            visible=True,
            badness=cost,
        )
        self.schedule.save_assignments(schedule_db)
        self.stdout.write('Schedule saved as {}'.format(self.name))

    def _available_timeslots(self):
        """Find timeslots available for schedule generation

        Excludes:
          * sunday timeslots
          *  timeslots used by the base schedule, if any
        """
        # n.b., models.TimeSlot is not the same as TimeSlot!
        timeslots_db = models.TimeSlot.objects.filter(
            meeting=self.meeting,
            type_id='regular',
        ).exclude(
            location__capacity=None,
        )

        if self.base_schedule is None:
            fixed_timeslots = models.TimeSlot.objects.none()
        else:
            fixed_timeslots = timeslots_db.filter(pk__in=self.base_schedule.qs_timeslots_in_use())
        free_timeslots = timeslots_db.exclude(pk__in=fixed_timeslots)

        timeslots = {TimeSlot(t, self.verbosity) for t in free_timeslots.select_related('location')}
        timeslots.update(
            TimeSlot(t, self.verbosity, is_fixed=True) for t in fixed_timeslots.select_related('location')
        )
        return {t for t in timeslots if t.day != 'sunday'}

    def _sessions_to_schedule(self, *args, **kwargs):
        """Find sessions that need to be scheduled

        Extra arguments are passed to the Session constructor.
        """
        sessions_db = models.Session.objects.filter(
            meeting=self.meeting,
            type_id='regular',
            schedulingevent__status_id='schedw',
        )

        if self.base_schedule is None:
            fixed_sessions = models.Session.objects.none()
        else:
            fixed_sessions = sessions_db.filter(pk__in=self.base_schedule.qs_sessions_scheduled())
        free_sessions = sessions_db.exclude(pk__in=fixed_sessions)

        sessions = {
            Session(self.stdout, self.meeting, s, is_fixed=False, *args, **kwargs)
            for s in free_sessions.select_related('group')
        }

        sessions.update({
            Session(self.stdout, self.meeting, s, is_fixed=True, *args, **kwargs)
            for s in fixed_sessions.select_related('group')
        })
        return sessions

    def _load_meeting(self):
        """Load all timeslots and sessions into in-memory objects."""
        business_constraint_costs = {
            bc.slug: bc.penalty
            for bc in models.BusinessConstraint.objects.all()
        }

        timeslots = self._available_timeslots()
        for timeslot in timeslots:
            timeslot.store_relations(timeslots)

        sessions = self._sessions_to_schedule(business_constraint_costs, self.verbosity)
        for session in sessions:
            # The complexity of a session also depends on how many
            # sessions have declared a conflict towards this session.
            session.update_complexity(sessions)

        self.schedule = Schedule(
            self.stdout,
            timeslots,
            sessions,
            business_constraint_costs,
            self.max_cycles,
            self.verbosity,
            self.base_schedule,
        )
        self.schedule.adjust_for_timeslot_availability()  # calculates some fixed costs


class Schedule(object):
    """
    The Schedule object represents the schedule, and contains code to generate/optimise it.
    The schedule is internally represented as a dict, timeslots being keys, sessions being values.
    Note that "timeslot" means the combination of a timeframe and a location.
    """
    def __init__(self, stdout, timeslots, sessions, business_constraint_costs,
                 max_cycles, verbosity, base_schedule=None):
        self.stdout = stdout
        self.timeslots = timeslots
        self.sessions = sessions or []
        self.business_constraint_costs = business_constraint_costs
        self.verbosity = verbosity
        self.schedule = dict()
        self.best_cost = math.inf
        self.best_schedule = None
        self._fixed_costs = dict()  # key = type of cost
        self._fixed_violations = dict()  # key = type of cost
        self.max_cycles = max_cycles
        self.base_schedule = self._load_base_schedule(base_schedule) if base_schedule else None

    def __str__(self):
        return 'Schedule ({} timeslots, {} sessions, {} scheduled, {} in base schedule)'.format(
            len(self.timeslots),
            len(self.sessions),
            len(self.schedule),
            len(self.base_schedule) if self.base_schedule else 0,
        )

    def pretty_print(self, include_base=True):
        """Pretty print the schedule"""
        last_day = None
        sched = dict(self.schedule)
        if include_base:
            sched.update(self.base_schedule)
        for slot in sorted(sched, key=lambda ts: ts.start):
            if last_day != slot.start.date():
                last_day = slot.start.date()
                print("""
-----------------
 Day: {}
-----------------""".format(slot.start.date()))

            print('{}: {}{}'.format(
                models.TimeSlot.objects.get(pk=slot.timeslot_pk),
                models.Session.objects.get(pk=sched[slot].session_pk),
                ' [BASE]' if slot in self.base_schedule else '',
            ))

    @property
    def fixed_cost(self):
        return sum(self._fixed_costs.values())

    @property
    def fixed_violations(self):
        return sum(self._fixed_violations.values(), [])

    def add_fixed_cost(self, label, violations, cost):
        self._fixed_costs[label] = cost
        self._fixed_violations[label] = violations

    @property
    def free_sessions(self):
        """Sessions that can be moved by the schedule"""
        return (sess for sess in self.sessions if not sess.is_fixed)

    @property
    def free_timeslots(self):
        """Timeslots that can be filled by the schedule"""
        return (t for t in self.timeslots if not t.is_fixed)

    def _load_base_schedule(self, db_base_schedule):
        session_lut = {s.session_pk: s for s in self.sessions}
        timeslot_lut = {t.timeslot_pk: t for t in self.timeslots}
        base_schedule = dict()
        for assignment in db_base_schedule.assignments.filter(session__in=session_lut, timeslot__in=timeslot_lut):
            base_schedule[timeslot_lut[assignment.timeslot.pk]] = session_lut[assignment.session.pk]
        return base_schedule

    def save_assignments(self, schedule_db):
        for timeslot, session in self.schedule.items():
            models.SchedTimeSessAssignment.objects.create(
                timeslot_id=timeslot.timeslot_pk,
                session_id=session.session_pk,
                schedule=schedule_db,
                badness=session.last_cost,
            )
    
    def adjust_for_timeslot_availability(self):
        """
        Check the number of sessions, their required capacity and duration against availability.
        If there are too many sessions, the generator exits.
        If sessions can't fit, they are trimmed, and a fixed cost is applied.
        
        Note that the trim is only applied on the in-memory object. The purpose
        of trimming in advance is to prevent the optimiser from trying to resolve
        a constraint that can never be resolved.
        """
        num_to_schedule = len(list(self.free_sessions))
        num_free_timeslots = len(list(self.free_timeslots))
        if  num_to_schedule > num_free_timeslots:
            raise CommandError('More sessions ({}) than timeslots ({})'
                               .format(num_to_schedule, num_free_timeslots))
    
        def make_capacity_adjustments(t_attr, s_attr):
            availables = [getattr(timeslot, t_attr) for timeslot in self.free_timeslots]
            availables.sort()
            sessions = sorted(self.free_sessions, key=lambda s: getattr(s, s_attr), reverse=True)
            violations, cost = [], 0
            for session in sessions:
                found_fit = False
                for idx, available in enumerate(availables):
                    if getattr(session, s_attr) <= available:
                        availables.pop(idx)
                        found_fit = True
                        break
                if not found_fit:
                    largest_available = availables[-1]
                    f = 'No timeslot with sufficient {} available for {}, requested {}, trimmed to {}'
                    msg = f.format(t_attr, session.group, getattr(session, s_attr), largest_available)
                    setattr(session, s_attr, largest_available)
                    availables.pop(-1)
                    cost += self.business_constraint_costs['session_requires_trim']
                    violations.append(msg)
            return violations, cost

        self.add_fixed_cost(
            'session_requires_duration_trim',
            *make_capacity_adjustments('duration', 'requested_duration'),
        )

        self.add_fixed_cost(
            'session_requires_capacity_trim',
            *make_capacity_adjustments('capacity', 'attendees'),
        )


    def total_schedule_cost(self):
        """
        Calculate the total cost of the current schedule in self.schedule.
        This includes the dynamic cost, which can be affected by scheduling choices,
        and the fixed cost, which can not be improved upon (e.g. sessions that had
        to be trimmed in duration).
        Returns a tuple of violations (list of strings) and the total cost (integer). 
        """
        violations, cost = self.calculate_dynamic_cost()
        if self.base_schedule is not None:
            # Include dynamic costs from the base schedule as a fixed cost for the generated schedule.
            # Fixed costs from the base schedule are included in the costs computed by adjust_for_timeslot_availability.
            self.add_fixed_cost('base_schedule', *self.calculate_dynamic_cost(self.base_schedule, include_fixed=True))
        violations += self.fixed_violations
        cost += self.fixed_cost
        return violations, cost

    def calculate_dynamic_cost(self, schedule=None, include_fixed=False):
        """
        Calculate the dynamic cost of the current schedule in self.schedule,
        or a different provided schedule. "Dynamic" cost means these are costs
        that can be affected by scheduling choices.
        Returns a tuple of violations (list of strings) and the total cost (integer). 
        """
        if not schedule:
            schedule = self.schedule
        if self.base_schedule is not None:
            schedule = dict(schedule)  # make a copy
            schedule.update(self.base_schedule)

        violations, cost = [], 0
        
        # For performance, a few values are pre-calculated in bulk
        group_sessions = defaultdict(set)
        overlapping_sessions = defaultdict(set)
        for timeslot, session in schedule.items():
            group_sessions[session.group].add((timeslot, session))  # (timeslot, session), not just session!
            overlapping_sessions[timeslot].update({schedule[t] for t in timeslot.overlaps if t in schedule})
            
        for timeslot, session in schedule.items():
            session_violations, session_cost = session.calculate_cost(
                schedule, timeslot, overlapping_sessions[timeslot], group_sessions[session.group], include_fixed
            )
            violations += session_violations
            cost += session_cost

        return violations, cost

    def fill_initial_schedule(self):
        """
        Create an initial schedule, which is stored in self.schedule.
        
        The initial schedule is created by going through all sessions in order of highest
        complexity first. Each sessions is placed in a timeslot chosen by:
        - First: lowest cost, taking all sessions into account that have already been scheduled
        - Second: shortest duration that still fits
        - Third: smallest room that still fits
        If there are multiple options with equal value, a random one is picked.
        
        For initial scheduling, it is not a hard requirement that the timeslot is long
        or large enough, though that will be preferred due to the lower cost.
        """
        if self.verbosity >= 2:
            self.stdout.write('== Initial scheduler starting, scheduling {} sessions in {} timeslots =='
                              .format(len(list(self.free_sessions)), len(list(self.free_timeslots))))
        sessions = sorted(self.free_sessions, key=lambda s: s.complexity, reverse=True)

        for session in sessions:
            possible_slots = [t for t in self.free_timeslots if t not in self.schedule.keys()]
            random.shuffle(possible_slots)
            
            def timeslot_preference(t):
                proposed_schedule = self.schedule.copy()
                proposed_schedule[t] = session
                return self.calculate_dynamic_cost(proposed_schedule)[1], t.duration, t.capacity

            possible_slots.sort(key=timeslot_preference)
            self._schedule_session(session, possible_slots[0])
            if self.verbosity >= 3:
                self.stdout.write('Scheduled {} at {} in location {}'
                                  .format(session.group, possible_slots[0].start,
                                          possible_slots[0].location_pk))

    def optimise_schedule(self):
        """
        Optimise the schedule in self.schedule. Expects fill_initial_schedule() to already
        have run - this only moves sessions around that were already scheduled.
        
        The optimising algorithm performs up to OPTIMISER_MAX_CYCLES runs. In each run, each
        scheduled session is considered for a switch with each other scheduled session.
        If the switch reduces the total cost of the schedule, the switch is made.
        
        If the optimiser finishes a whole run without finding any improvements, the schedule
        can not be improved further by switching, and sessions are shuffled with
        _shuffle_conflicted_sessions() and the continues.
         
        If the total schedule cost reaches 0 at any time, the schedule is perfect and the
        optimiser returns. 
        """
        last_run_violations = []
        best_cost = math.inf
        shuffle_next_run = False
        last_run_cost = None
        switched_with = None
        
        for run_count in range(1, self.max_cycles+1):
            items = list(self.schedule.items())
            random.shuffle(items)

            if self.verbosity >= 2:
                self.stdout.write('== Optimiser starting run {}, dynamic cost after last run {} =='
                                  .format(run_count,  last_run_cost))
                self.stdout.write('Dynamic violations in last optimiser run: {}'
                                  .format(last_run_violations))
            if shuffle_next_run:
                shuffle_next_run = False
                last_run_cost = None  # After a shuffle, attempt at least two regular runs
                self._shuffle_conflicted_sessions(items)

            for original_timeslot, session in items:
                if session.is_fixed:
                    continue
                best_cost = self.calculate_dynamic_cost()[1]
                if best_cost == 0:
                    if self.verbosity >= 1 and self.stdout.isatty():
                        sys.stderr.write('\n')
                    if self.verbosity >= 2:
                        self.stdout.write('Optimiser found an optimal schedule')

                    return run_count
                best_timeslot = None

                for possible_new_slot in self.free_timeslots:
                    cost = self._cost_for_switch(original_timeslot, possible_new_slot)
                    if cost < best_cost:
                        best_cost = cost
                        best_timeslot = possible_new_slot

                if best_timeslot:
                    switched_with = self._switch_sessions(original_timeslot, best_timeslot)
                    switched_with = switched_with.group if switched_with else '<empty slot>'
                    if self.verbosity >= 3:
                        self.stdout.write('Run {:2}: found cost reduction to {:,} by switching {} with {}'
                                          .format(run_count, best_cost, session.group, switched_with))

            if last_run_cost == best_cost:
                shuffle_next_run = True
            last_run_violations, last_run_cost = self.calculate_dynamic_cost()
            self._save(last_run_cost)

            if self.verbosity >= 1 and self.stdout.isatty():
                sys.stderr.write('*' if last_run_cost == self.best_cost else '.')
                sys.stderr.flush()

        if self.verbosity >= 1 and self.stdout.isatty():
            sys.stderr.write('\n')
        if self.verbosity >= 2:
            self.stdout.write('Optimiser did not find perfect schedule, using best schedule at dynamic cost {:,}'
                              .format(self.best_cost))
        self.schedule = self.best_schedule

        return run_count

    def _shuffle_conflicted_sessions(self, items):
        """
        Shuffle sessions that currently have conflicts.
        All sessions that had conflicts in their last run, are shuffled to
        an entirely random timeslot, in which they fit.
        Parameter is an iterable of (timeslot, session) tuples.
        """
        self.calculate_dynamic_cost()  # update all costs
        to_reschedule = [(t, s) for t, s in items if s.last_cost]
        random.shuffle(to_reschedule)
        if self.verbosity >= 2:
            self.stdout.write('Optimiser has no more improvements, shuffling sessions {}'
                              .format(', '.join([s.group for t, s in to_reschedule])))
        
        for original_timeslot, rescheduling_session in to_reschedule:
            possible_new_slots = list(t for t in self.free_timeslots if t != original_timeslot)
            random.shuffle(possible_new_slots)
            
            for possible_new_slot in possible_new_slots:
                switched_with = self._switch_sessions(original_timeslot, possible_new_slot)
                if switched_with is not False:
                    switched_group = switched_with.group if switched_with else '<empty slot>'
                    if self.verbosity >= 3:
                        self.stdout.write('Moved {} to random new slot, previously in slot was {}'
                                          .format(rescheduling_session.group, switched_group))
                    break
                    
    def optimise_timeslot_capacity(self):
        """
        Optimise the schedule for room capacity usage.
        
        For each fully overlapping timeslot, the sessions are re-ordered so
        that smaller sessions are in smaller rooms, and larger sessions in
        larger rooms. This does not change which sessions overlap, so it
        has no impact on the schedule cost. 
        """
        optimised_timeslots = set()
        for timeslot in list(self.schedule.keys()):
            if timeslot in optimised_timeslots or timeslot.is_fixed:
                continue
            timeslot_overlaps = sorted(timeslot.full_overlaps, key=lambda t: t.capacity, reverse=True)
            sessions_overlaps = [self.schedule.get(t) for t in timeslot_overlaps]
            sessions_overlaps.sort(key=lambda s: s.attendees if s else 0, reverse=True)
            assert len(timeslot_overlaps) == len(sessions_overlaps)
            
            for new_timeslot in timeslot_overlaps:
                if new_timeslot.is_fixed:
                    continue
                new_session = sessions_overlaps.pop(0)
                if not new_session and new_timeslot in self.schedule:
                    del self.schedule[new_timeslot]
                elif new_session:
                    self.schedule[new_timeslot] = new_session
                
            optimised_timeslots.add(timeslot)
            optimised_timeslots.update(timeslot_overlaps)    

    def _schedule_session(self, session, timeslot):
        self.schedule[timeslot] = session

    def _cost_for_switch(self, timeslot1, timeslot2):
        """
        Calculate the total cost of self.schedule, if the sessions in timeslot1 and timeslot2 
        would be switched. Does not perform the switch, self.schedule remains unchanged.
        """
        proposed_schedule = self.schedule.copy()
        session1 = proposed_schedule.get(timeslot1)
        session2 = proposed_schedule.get(timeslot2)
        if session1 and not session1.fits_in_timeslot(timeslot2):
            return math.inf
        if session2 and not session2.fits_in_timeslot(timeslot1):
            return math.inf
        if session1:
            proposed_schedule[timeslot2] = session1
        elif session2:
            del proposed_schedule[timeslot2]
        if session2:
            proposed_schedule[timeslot1] = session2
        elif session1:
            del proposed_schedule[timeslot1]
        return self.calculate_dynamic_cost(proposed_schedule)[1]

    def _switch_sessions(self, timeslot1, timeslot2):
        """
        Switch the sessions currently in timeslot1 and timeslot2.
        If timeslot2 had a session scheduled, returns that Session instance.
        """
        session1 = self.schedule.get(timeslot1)
        session2 = self.schedule.get(timeslot2)
        if timeslot1 == timeslot2:
            return False
        if session1 and not session1.fits_in_timeslot(timeslot2):
            return False
        if session2 and not session2.fits_in_timeslot(timeslot1):
            return False
        if session1:
            self.schedule[timeslot2] = session1
        elif session2:
            del self.schedule[timeslot2]
        if session2:
            self.schedule[timeslot1] = session2
        elif session1:
            del self.schedule[timeslot1]
        return session2
    
    def _save(self, cost):
        if cost < self.best_cost:
            self.best_cost = cost
            self.best_schedule = self.schedule.copy()


class TimeSlot(object):
    """
    This TimeSlot class is analogous to the TimeSlot class in the models,
    i.e. it represents a timeframe in a particular location.
    """
    def __init__(self, timeslot_db, verbosity, is_fixed=False):
        """Initialise this object from a TimeSlot model instance."""
        self.verbosity = verbosity
        self.is_fixed = is_fixed
        self.timeslot_pk = timeslot_db.pk
        self.location_pk = timeslot_db.location.pk
        self.capacity = timeslot_db.location.capacity
        self.start = timeslot_db.time
        self.duration = timeslot_db.duration
        self.end = self.start + self.duration
        self.day = calendar.day_name[self.start.weekday()].lower()
        if self.start.time() < datetime.time(12, 30):
            self.time_of_day = 'morning'
        elif self.start.time() < datetime.time(15, 30):
            self.time_of_day = 'afternoon-early'
        else:
            self.time_of_day = 'afternoon-late'
        self.time_group = self.day + '-' + self.time_of_day
        self.overlaps = set()
        self.full_overlaps = set()
        self.adjacent = set()

    def store_relations(self, other_timeslots):
        """
        Store relations to all other timeslots. This should be called
        after all TimeSlot objects have been created. This allows fast
        lookups of which TimeSlot objects overlap or are adjacent.
        Note that there is a distinction between an overlap, meaning
        at least part of the timeslots occur during the same time,
        and a full overlap, meaning the start and end time are identical.
        """
        for other in other_timeslots:
            if any([
                self.start < other.start < self.end,
                self.start < other.end < self.end,
                self.start >= other.start and self.end <= other.end,
            ]) and other != self:
                self.overlaps.add(other)
            if self.start == other.start and self.end == other.end and other != self:
                self.full_overlaps.add(other)
            if (
                abs(self.start - other.end) <= datetime.timedelta(minutes=30) or
                abs(other.start - self.end) <= datetime.timedelta(minutes=30)
            ) and self.location_pk == other.location_pk:
                self.adjacent.add(other)


class Session(object):
    """
    This TimeSlot class is analogous to the Session class in the models,
    i.e. it represents a single session to be scheduled. It also pulls
    in data about constraints, group parents, etc.
    """
    def __init__(self, stdout, meeting, session_db, business_constraint_costs, verbosity, is_fixed=False):
        """
        Initialise this object from a Session model instance.
        This includes collecting all constraints from the database,
        and calculating an initial complexity.  
        """
        self.stdout = stdout
        self.verbosity = verbosity
        self.business_constraint_costs = business_constraint_costs
        self.session_pk = session_db.pk
        self.group = session_db.group.acronym
        self.parent = session_db.group.parent.acronym if session_db.group.parent else None
        self.ad = session_db.group.ad_role().person.pk if session_db.group.ad_role() else None
        self.is_area_meeting = any([
            session_db.group.type_id == 'area',
            session_db.group.type_id == 'ag',
            session_db.group.type_id == 'rag',
            session_db.group.meeting_seen_as_area,
        ])
        self.is_bof = session_db.group.state_id == 'bof'
        self.is_prg = session_db.group.type_id == 'rg' and session_db.group.state_id == 'proposed'
        self.is_fixed = is_fixed  # if True, cannot be moved

        self.attendees = session_db.attendees
        if not self.attendees:
            if self.verbosity >= 1:
                self.stdout.write('WARNING: session {} (pk {}) has no attendees set, assuming any room fits'
                                  .format(self.group, self.session_pk))
            self.attendees = 0
        self.requested_duration = session_db.requested_duration

        constraints_db = models.Constraint.objects.filter(
            Q(source=session_db.group) | Q(source__in=session_db.joint_with_groups.all()),
            meeting=meeting,
        )

        self.conflict_groups = defaultdict(int)
        self.conflict_people = set()
        self.conflict_people_penalty = 0
        self.time_relation = None
        self.time_relation_penalty = 0
        self.wg_adjacent = None
        self.wg_adjacent_penalty = 0
        self.wg_adjacent = None
        self.timeranges_unavailable = set()
        self.timeranges_unavailable_penalty = 0

        self.last_cost = None

        for constraint_db in constraints_db:
            if constraint_db.name.is_group_conflict:
                self.conflict_groups[constraint_db.target.acronym] += constraint_db.name.penalty
            elif constraint_db.name.slug == 'bethere':
                self.conflict_people.add(constraint_db.person.pk)
                self.conflict_people_penalty = constraint_db.name.penalty
            elif constraint_db.name.slug == 'time_relation':
                self.time_relation = constraint_db.time_relation
                self.time_relation_penalty = constraint_db.name.penalty
            elif constraint_db.name.slug == 'wg_adjacent':
                self.wg_adjacent = constraint_db.target.acronym
                self.wg_adjacent_penalty = constraint_db.name.penalty
            elif constraint_db.name.slug == 'timerange':
                self.timeranges_unavailable.update({t.slug for t in constraint_db.timeranges.all()})
                self.timeranges_unavailable_penalty = constraint_db.name.penalty
            else:
                f = 'Unknown constraint type {} for {}'
                raise CommandError(f.format(constraint_db.name.slug, self.group))

        self.complexity = sum([
            self.attendees,
            sum(self.conflict_groups.values()),
            (self.conflict_people_penalty * len(self.conflict_people)),
            self.time_relation_penalty,
            self.wg_adjacent_penalty * 1000,
            self.timeranges_unavailable_penalty * len(self.timeranges_unavailable),
            self.requested_duration.seconds * 100,
        ])
        
    def update_complexity(self, other_sessions):
        """
        Update the complexity of this session, based on all other sessions.
        This should be called after all Session objects are created, and
        updates the complexity of this session based on how many conflicts
        other sessions may have with this session 
        """
        for other_session in other_sessions:
            self.complexity += sum([
                sum([cost for group, cost in other_session.conflict_groups.items() if
                     group == self.group]),
                self.conflict_people_penalty * len(
                    self.conflict_people.intersection(other_session.conflict_people))
            ])

    def fits_in_timeslot(self, timeslot):
        return self.attendees <= timeslot.capacity and self.requested_duration <= timeslot.duration

    def calculate_cost(self, schedule, my_timeslot, overlapping_sessions, my_sessions, include_fixed=False):
        """
        Calculate the cost of this session, in the provided schedule, with this session
        being in my_timeslot, and a given set of overlapping sessions and the set of
        all sessions of this group.
        The functionality is split into a few methods, to optimise caching.
        
        overlapping_sessions is a list of Session objects
        my_sessions is an iterable of tuples, each tuple containing a TimeSlot and a Session

        The return value is a tuple of violations (list of strings) and a cost (integer).        
        """
        violations, cost = [], 0
        # Ignore overlap between two fixed sessions when calculating dynamic cost
        overlapping_sessions = tuple(
            o for o in overlapping_sessions
            if include_fixed or not (self.is_fixed and o.is_fixed)
        )

        if include_fixed or (not self.is_fixed):
            if self.attendees > my_timeslot.capacity:
                violations.append('{}: scheduled in too small room'.format(self.group))
                cost += self.business_constraint_costs['session_requires_trim']

            if self.requested_duration > my_timeslot.duration:
                violations.append('{}: scheduled in too short timeslot'.format(self.group))
                cost += self.business_constraint_costs['session_requires_trim']

            if my_timeslot.time_group in self.timeranges_unavailable:
                violations.append('{}: scheduled in unavailable timerange {}'
                                  .format(self.group, my_timeslot.time_group))
                cost += self.timeranges_unavailable_penalty
            
        v, c = self._calculate_cost_overlapping_groups(overlapping_sessions)
        violations += v
        cost += c

        v, c = self._calculate_cost_business_logic(overlapping_sessions)
        violations += v
        cost += c

        v, c = self._calculate_cost_my_other_sessions(tuple(my_sessions))
        violations += v
        cost += c

        if self.wg_adjacent and (include_fixed or not self.is_fixed):
            adjacent_groups = tuple([schedule[t].group for t in my_timeslot.adjacent if t in schedule])
            if self.wg_adjacent not in adjacent_groups:
                violations.append('{}: missing adjacency with {}, adjacents are: {}'
                                  .format(self.group, self.wg_adjacent, ', '.join(adjacent_groups)))
                cost += self.wg_adjacent_penalty

        self.last_cost = cost
        return violations, cost

    @lru_cache(maxsize=10000)
    def _calculate_cost_overlapping_groups(self, overlapping_sessions):
        violations, cost = [], 0
        for other in overlapping_sessions:
            if not other:
                continue
            if self.is_fixed and other.is_fixed:
                continue
            if other.group == self.group:
                violations.append('{}: scheduled twice in overlapping slots'.format(self.group))
                cost += math.inf
            if other.group in self.conflict_groups:
                violations.append('{}: group conflict with {}'.format(self.group, other.group))
                cost += self.conflict_groups[other.group]
    
            conflict_people = self.conflict_people.intersection(other.conflict_people)
            for person in conflict_people:
                violations.append('{}: conflict w/ key person {}, also in {}'
                                  .format(self.group, person, other.group))
            cost += len(conflict_people) * self.conflict_people_penalty
        return violations, cost

    @lru_cache(maxsize=10000)
    def _calculate_cost_business_logic(self, overlapping_sessions):
        violations, cost = [], 0
        for other in overlapping_sessions:
            if not other:
                continue
            if self.is_fixed and other.is_fixed:
                continue
            # BOFs cannot conflict with PRGs
            if self.is_bof and other.is_prg:
                violations.append('{}: BOF overlaps with PRG: {}'
                                  .format(self.group, other.group))
                cost += self.business_constraint_costs['bof_overlapping_prg']
            # BOFs cannot conflict with any other BOFs
            if self.is_bof and other.is_bof:
                violations.append('{}: BOF overlaps with other BOF: {}'
                                  .format(self.group, other.group))
                cost += self.business_constraint_costs['bof_overlapping_bof']
            # BOFs cannot conflict with any other WGs in their area
            if self.is_bof and self.parent == other.parent:
                violations.append('{}: BOF overlaps with other session from same area: {}'
                                  .format(self.group, other.group))
                cost += self.business_constraint_costs['bof_overlapping_area_wg']
            # BOFs cannot conflict with any area-wide meetings (of any area)
            if self.is_bof and other.is_area_meeting:
                violations.append('{}: BOF overlaps with area meeting {}'
                                  .format(self.group, other.group))
                cost += self.business_constraint_costs['bof_overlapping_area_meeting']
            # Area meetings cannot conflict with anything else in their area 
            if self.is_area_meeting and other.parent == self.group:
                violations.append('{}: area meeting overlaps with session from same area: {}'
                                  .format(self.group, other.group))
                cost += self.business_constraint_costs['area_overlapping_in_area']
            # Area meetings cannot conflict with other area meetings 
            if self.is_area_meeting and other.is_area_meeting:
                violations.append('{}: area meeting overlaps with other area meeting: {}'
                                  .format(self.group, other.group))
                cost += self.business_constraint_costs['area_overlapping_other_area']
            # WGs overseen by the same Area Director should not conflict  
            if self.ad and self.ad == other.ad:
                violations.append('{}: has same AD as {}'.format(self.group, other.group))
                cost += self.business_constraint_costs['session_overlap_ad']
        return violations, cost
    
    @lru_cache(maxsize=10000)
    def _calculate_cost_my_other_sessions(self, my_sessions):
        """Calculate cost due to other sessions for same group

        my_sessions is a set of (TimeSlot, Session) tuples.
        """
        def sort_sessions(timeslot_session_pairs):
            return sorted(timeslot_session_pairs, key=lambda item: item[1].session_pk)

        violations, cost = [], 0
        if len(my_sessions) >= 2:
            my_fixed_sessions = [m for m in my_sessions if m[1].is_fixed]
            fixed_sessions_in_order = (my_fixed_sessions == sort_sessions(my_fixed_sessions))
            # Only possible to keep sessions in order if fixed sessions are in order - ignore cost if not.
            if fixed_sessions_in_order and (list(my_sessions) != sort_sessions(my_sessions)):
                session_order = [s.session_pk for t, s in list(my_sessions)]
                violations.append('{}: sessions out of order: {}'.format(self.group, session_order))
                cost += self.business_constraint_costs['sessions_out_of_order']
                
            if self.time_relation:
                group_days = [t.start.date() for t, s in my_sessions]
                # ignore conflict between two fixed sessions
                if not (my_sessions[0][1].is_fixed and my_sessions[1][1].is_fixed):
                    difference_days = abs((group_days[1] - group_days[0]).days)
                    if self.time_relation == 'subsequent-days' and difference_days != 1:
                        violations.append('{}: has time relation subsequent-days but difference is {}'
                                          .format(self.group, difference_days))
                        cost += self.time_relation_penalty
                    elif self.time_relation == 'one-day-seperation' and difference_days == 1:
                        violations.append('{}: has time relation one-day-seperation but difference is {}'
                                          .format(self.group, difference_days))
                        cost += self.time_relation_penalty
        return violations, cost
