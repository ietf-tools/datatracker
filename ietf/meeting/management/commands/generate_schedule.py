# Copyright The IETF Trust 2020, All Rights Reserved
# For an overview of this process and context, see:
# https://trac.tools.ietf.org/tools/ietfdb/wiki/MeetingConstraints
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

from django.contrib.humanize.templatetags.humanize import intcomma
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

import debug                            # pyflakes:ignore

from ietf.person.models import Person
from ietf.meeting import models

# 40 runs of the optimiser for IETF 106 with cycles=160 resulted in 16
# zero-violation invocations, with a mean number of runs of 91 and 
# std-dev 41.  On the machine used, 160 cycles had a runtime of about
# 30 minutes.  Setting default to 160, as 80 or 100 seems too low to have
# a reasonable rate of success in generating zero-cost schedules.

OPTIMISER_MAX_CYCLES = 160


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

    def handle(self, meeting, name, max_cycles, verbosity, *args, **kwargs):
        ScheduleHandler(self.stdout, meeting, name, max_cycles, verbosity).run()


class ScheduleHandler(object):
    def __init__(self, stdout, meeting_number, name=None, max_cycles=OPTIMISER_MAX_CYCLES, verbosity=1):
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
        if self.verbosity >= 1:
            self.stdout.write("\nRunning automatic schedule layout for meeting IETF %s\n\n" % self.meeting.number)
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
            owner=Person.objects.get(name='(System)'),
            public=False,
            visible=True,
            badness=cost,
        )
        self.schedule.save_assignments(schedule_db)
        self.stdout.write('Schedule saved as {}'.format(self.name))
        
    def _load_meeting(self):
        """Load all timeslots and sessions into in-memory objects."""
        business_constraint_costs = {
            bc.slug: bc.penalty
            for bc in models.BusinessConstraint.objects.all()
        }
        
        timeslots_db = models.TimeSlot.objects.filter(
            meeting=self.meeting,
            type_id='regular',
        ).exclude(location__capacity=None).select_related('location')
        
        timeslots = {TimeSlot(t, self.verbosity) for t in timeslots_db}
        timeslots = {t for t in timeslots if t.day != 'sunday'}
        for timeslot in timeslots:
            timeslot.store_relations(timeslots)

        sessions_db = models.Session.objects.filter(
            meeting=self.meeting,
            type_id='regular',
            schedulingevent__status_id='schedw',
        ).select_related('group')
        
        sessions = {Session(self.stdout, self.meeting, s, business_constraint_costs, self.verbosity)
                    for s in sessions_db}
        for session in sessions:
            # The complexity of a session also depends on how many
            # sessions have declared a conflict towards this session.
            session.update_complexity(sessions)

        self.schedule = Schedule(
            self.stdout, timeslots, sessions, business_constraint_costs, self.max_cycles, self.verbosity)
        self.schedule.adjust_for_timeslot_availability()


class Schedule(object):
    """
    The Schedule object represents the schedule, and contains code to generate/optimise it.
    The schedule is internally represented as a dict, timeslots being keys, sessions being values.
    Note that "timeslot" means the combination of a timeframe and a location.
    """
    def __init__(self, stdout, timeslots, sessions, business_constraint_costs, max_cycles, verbosity):
        self.stdout = stdout
        self.timeslots = timeslots
        self.sessions = sessions
        self.business_constraint_costs = business_constraint_costs
        self.verbosity = verbosity
        self.schedule = dict()
        self.best_cost = math.inf
        self.best_schedule = None
        self.fixed_cost = 0
        self.fixed_violations = []
        self.max_cycles = max_cycles
        
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
        if len(self.sessions) > len(self.timeslots):
            raise CommandError('More sessions ({}) than timeslots ({})'
                               .format(len(self.sessions), len(self.timeslots)))
    
        def make_capacity_adjustments(t_attr, s_attr):
            availables = [getattr(timeslot, t_attr) for timeslot in self.timeslots]
            availables.sort()
            sessions = sorted(self.sessions, key=lambda s: getattr(s, s_attr), reverse=True)
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
                    self.fixed_cost += self.business_constraint_costs['session_requires_trim']
                    self.fixed_violations.append(msg)
        
        make_capacity_adjustments('duration', 'requested_duration')
        make_capacity_adjustments('capacity', 'attendees')
                
    def total_schedule_cost(self):
        """
        Calculate the total cost of the current schedule in self.schedule.
        This includes the dynamic cost, which can be affected by scheduling choices,
        and the fixed cost, which can not be improved upon (e.g. sessions that had
        to be trimmed in duration).
        Returns a tuple of violations (list of strings) and the total cost (integer). 
        """
        violations, cost = self.calculate_dynamic_cost()
        violations += self.fixed_violations
        cost += self.fixed_cost
        return violations, cost

    def calculate_dynamic_cost(self, schedule=None):
        """
        Calculate the dynamic cost of the current schedule in self.schedule,
        or a different provided schedule. "Dynamic" cost means these are costs
        that can be affected by scheduling choices.
        Returns a tuple of violations (list of strings) and the total cost (integer). 
        """
        if not schedule:
            schedule = self.schedule
        violations, cost = [], 0
        
        # For performance, a few values are pre-calculated in bulk
        group_sessions = defaultdict(set)
        overlapping_sessions = defaultdict(set)
        for timeslot, session in schedule.items():
            group_sessions[session.group].add((timeslot, session))
            overlapping_sessions[timeslot].update({schedule.get(t) for t in timeslot.overlaps})
            
        for timeslot, session in schedule.items():
            session_violations, session_cost = session.calculate_cost(
                schedule, timeslot, overlapping_sessions[timeslot], group_sessions[session.group])
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
                              .format(len(self.sessions), len(self.timeslots)))
        sessions = sorted(self.sessions, key=lambda s: s.complexity, reverse=True)

        for session in sessions:
            possible_slots = [t for t in self.timeslots if t not in self.schedule.keys()]
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
                best_cost = self.calculate_dynamic_cost()[1]
                if best_cost == 0:
                    if self.verbosity >= 1 and self.stdout.isatty():
                        sys.stderr.write('\n')
                    if self.verbosity >= 2:
                        self.stdout.write('Optimiser found an optimal schedule')

                    return run_count
                best_timeslot = None

                for possible_new_slot in self.timeslots:
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
            possible_new_slots = list(self.timeslots)
            possible_new_slots.remove(original_timeslot)
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
            if timeslot in optimised_timeslots:
                continue
            timeslot_overlaps = sorted(timeslot.full_overlaps, key=lambda t: t.capacity, reverse=True)
            sessions_overlaps = [self.schedule.get(t) for t in timeslot_overlaps]
            sessions_overlaps.sort(key=lambda s: s.attendees if s else 0, reverse=True)
            assert len(timeslot_overlaps) == len(sessions_overlaps)
            
            for new_timeslot in timeslot_overlaps:
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
    def __init__(self, timeslot_db, verbosity):
        """Initialise this object from a TimeSlot model instance."""
        self.verbosity = verbosity
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
    def __init__(self, stdout, meeting, session_db, business_constraint_costs, verbosity):
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
        self.ad = session_db.group.ad_role().pk if session_db.group.ad_role() else None
        self.is_area_meeting = any([
            session_db.group.type_id == 'area',
            session_db.group.type_id == 'ag',
            session_db.group.type_id == 'rag',
            session_db.group.meeting_seen_as_area,
        ])
        self.is_bof = session_db.group.state_id == 'bof'
        self.is_prg = session_db.group.type_id == 'rg' and session_db.group.state_id == 'proposed'

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
            if constraint_db.name.slug in ['conflict', 'conflic2', 'conflic3']:
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

    def calculate_cost(self, schedule, my_timeslot, overlapping_sessions, my_sessions):
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
        overlapping_sessions = tuple(overlapping_sessions)
        
        if self.attendees > my_timeslot.capacity:
            violations.append('{}: scheduled scheduled in too small room'.format(self.group))
            cost += self.business_constraint_costs['session_requires_trim']

        if self.requested_duration > my_timeslot.duration:
            violations.append('{}: scheduled scheduled in too short timeslot'.format(self.group))
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

        if self.wg_adjacent:
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
            # BoFs cannot conflict with PRGs
            if self.is_bof and other.is_prg:
                violations.append('{}: BoF overlaps with PRG: {}'
                                  .format(self.group, other.group))
                cost += self.business_constraint_costs['bof_overlapping_prg']
            # BoFs cannot conflict with any other BoFs 
            if self.is_bof and other.is_bof:
                violations.append('{}: BoF overlaps with other BoF: {}'
                                  .format(self.group, other.group))
                cost += self.business_constraint_costs['bof_overlapping_bof']
            # BoFs cannot conflict with any other WGs in their area
            if self.is_bof and self.parent == other.parent:
                violations.append('{}: BoF overlaps with other session from same area: {}'
                                  .format(self.group, other.group))
                cost += self.business_constraint_costs['bof_overlapping_area_wg']
            # BoFs cannot conflict with any area-wide meetings (of any area) 
            if self.is_bof and other.is_area_meeting:
                violations.append('{}: BoF overlaps with area meeting {}'
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
        violations, cost = [], 0
        my_sessions = list(my_sessions)
        if len(my_sessions) >= 2:
            if my_sessions != sorted(my_sessions, key=lambda i: i[1].session_pk):
                session_order = [s.session_pk for t, s in my_sessions]
                violations.append('{}: sessions out of order: {}'.format(self.group, session_order))
                cost += self.business_constraint_costs['sessions_out_of_order']
                
        if self.time_relation and len(my_sessions) >= 2:
            group_days = [t.start.date() for t, s in my_sessions]
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
