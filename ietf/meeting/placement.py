#  FILE: ietf/meeting/placement.py
#
# Copyright (c) 2013, The IETF Trust. See ../../../LICENSE.
#
# This file contains a model that encapsulates the progress of the automatic placer.
# Each step of placement is stored as a row in a table, not because this is necessary,
# but because it helps to debug things.
#
# A production run of the placer would do the same work, but simply not save anything.
#

import sys

from random              import Random
from datetime            import datetime

from django.db           import models
#from settings import BADNESS_UNPLACED, BADNESS_TOOSMALL_50, BADNESS_TOOSMALL_100, BADNESS_TOOBIG, BADNESS_MUCHTOOBIG
#from ietf.meeting.models import Schedule, SchedTimeSessAssignment,TimeSlot,Room
from ietf.meeting.models import SchedTimeSessAssignment
from django.template.defaultfilters import slugify, date as date_format, time as time_format

def do_prompt():
    print "waiting:"
    sys.stdin.readline()

class PlacementException(Exception):
    pass

# ScheduleSlot really represents a single column of time.
# The TimeSlot object would work here, but it associates a room.
# There is a special Schedule slot (subclass) which corresponds to unscheduled items.
class ScheduleSlot(object):
    def __init__(self, daytime):
        self.daytime = daytime
        self.badness = None
        self.slotgroups = {}

    # this is a partial copy of SchedTimeSessAssignment's methods. Prune later.
    #def __unicode__(self):
    #    return u"%s [%s<->%s]" % (self.schedule, self.session, self.timeslot)
    #
    #def __str__(self):
    #    return self.__unicode__()

    def add_assignment(self,fs):
        self.slotgroups[fs] = fs

    def scheduled_session_pk(self, assignments):
        things = []
        slot1 = assignments.slot1
        slot2 = assignments.slot2
        for fs in self.slotgroups.iterkeys():
            session = fs.session
            if slot1 is not None and fs == slot1:
                session = slot2.session
            if slot2 is not None and fs == slot2:
                session = slot1.session
            if session is not None:
                things.append((session.pk,fs))
        return things

    def recalc_badness1(self, assignments):
        badness = 0
        for fs,fs2 in self.slotgroups.iteritems():
            if fs.session is not None:
                num = fs.session.badness2(self)
                #print "rc,,,,%s,%s,%u,recalc1" % (self.daytime, fs.session.short_name, num)
                badness += num
        self.badness = badness

    def recalc_badness(self, assignments):
        badness = 0
        session_pk_list = self.scheduled_session_pk(assignments)
        #print "rc,,,%u,slot_recalc" % (len(session_pk_list))
        for pk,fs in session_pk_list:
            #print "rc,,,,%u,%s,list" % (pk,fs.session)
            if fs.session is not None:
                num = fs.session.badness_fast(fs.timeslot, self, session_pk_list)
                #print "rc,,,,%s,%s,%u,recalc0" % (self.daytime, fs.session.short_name, num)
                badness += num
        self.badness = badness

    def calc_badness(self, assignments):
        if self.badness is None:
            self.recalc_badness(assignments)
        return self.badness

#
# this subclass does everything a ScheduleSlot does, in particular it knows how to
# maintain and recalculate badness, but it also maintains a list of slots which
# are unplaced so as to accelerate finding things to place at the beginning of automatic placement.
#
# XXX perhaps this should be in the form an iterator?
#
class UnplacedScheduleSlot(ScheduleSlot):
    def __init__(self):
        super(UnplacedScheduleSlot, self).__init__(None)
        self.unplaced_slot_numbers = []
        self.unplaced_slots_finishcount = 0

    def shuffle(self, generator):
        generator.shuffle(self.unplaced_slot_numbers)
        self.unplaced_slots_finishcount = self.count / 10

    def finished(self):
        if len(self.unplaced_slot_numbers) <= self.unplaced_slots_finishcount:
            return True
        else:
            return False

    @property
    def count(self):
        return len(self.unplaced_slot_numbers)

    def add_assignment(self,fs):
        super(UnplacedScheduleSlot, self).add_assignment(fs)
        #print "unplaced add: %s" % (fs.available_slot)
        self.unplaced_slot_numbers.append(fs.available_slot)

    def get_unplaced_slot_number(self):
        #print "unplaced slots: %s" % (self.unplaced_slot_numbers)
        return self.unplaced_slot_numbers[0]

    def delete_first(self):
        del self.unplaced_slot_numbers[0]


class FakeSchedTimeSessAssignment(object):
    """
    This model provides a fake (not-backed by database) N:M relationship between
    Session and TimeSlot, but in this case TimeSlot is always None, because the
    Session is not scheduled.
    """
    faked          = "fake"

    def __init__(self, schedule):
        self.extendedfrom = None
        self.modified = None
        self.notes    = None
        self.badness  = None
        self.available_slot = None
        self.origss         = None
        self.timeslot = None
        self.session  = None
        self.schedule = schedule
        self.pinned   = False
        self.scheduleslot = None

    def fromSchedTimeSessAssignment(self, ss):  # or from another FakeSchedTimeSessAssignment
        self.session   = ss.session
        self.schedule  = ss.schedule
        self.timeslot  = ss.timeslot
        self.modified  = ss.modified
        self.pinned    = ss.pinned
        self.origss    = ss

    def save(self):
        pass

    # this is a partial copy of SchedTimeSessAssignment's methods. Prune later.
    def __unicode__(self):
        return u"%s [%s<->%s]" % (self.schedule, self.session, self.timeslot)

    def __str__(self):
        return self.__unicode__()

    @property
    def room_name(self):
        return "noroom"

    @property
    def special_agenda_note(self):
        return self.session.agenda_note if self.session else ""

    @property
    def acronym(self):
        if self.session and self.session.group:
            return self.session.group.acronym

    @property
    def slot_to_the_right(self):
        return None

    @property
    def acronym_name(self):
        if not self.session:
            return self.notes
        if hasattr(self, "interim"):
            return self.session.group.name + " (interim)"
        elif self.session.name:
            return self.session.name
        else:
            return self.session.group.name

    @property
    def session_name(self):
        return self.session.name

    @property
    def area(self):
        if not self.session or not self.session.group:
            return ""
        if self.session.group.type_id == "irtf":
            return "irtf"
        if self.timeslot.type_id == "plenary":
            return "1plenary"
        if not self.session.group.parent or not self.session.group.parent.type_id in ["area","irtf"]:
            return ""
        return self.session.group.parent.acronym

    @property
    def break_info(self):
        return None

    @property
    def area_name(self):
        if self.session and self.session.group and self.session.group.acronym == "edu":
            return "Training"
        elif not self.session or not self.session.group or not self.session.group.parent or not self.session.group.parent.type_id == "area":
            return ""
        return self.session.group.parent.name

    @property
    def isWG(self):
        if not self.session or not self.session.group:
            return False
        if self.session.group.type_id == "wg" and self.session.group.state_id != "bof":
            return True

    @property
    def group_type_str(self):
        if not self.session or not self.session.group:
            return ""
        if self.session.group and self.session.group.type_id == "wg":
            if self.session.group.state_id == "bof":
                return "BOF"
            else:
                return "WG"

        return ""

    @property
    def slottype(self):
        return ""

    @property
    def empty_str(self):
        # return JS happy value
        if self.session:
            return "False"
        else:
            return "True"

    def json_dict(self, selfurl):
        ss = dict()
        ss['assignment_id'] = self.id
        #ss['href']          = self.url(sitefqdn)
        ss['empty'] =  self.empty_str
        ss['timeslot_id'] = self.timeslot.id
        if self.session:
            ss['session_id']  = self.session.id
        ss['room'] = slugify(self.timeslot.location)
        ss['roomtype'] = self.timeslot.type.slug
        ss["time"]     = date_format(self.timeslot.time, 'Hi')
        ss["date"]     = time_format(self.timeslot.time, 'Y-m-d')
        ss["domid"]    = self.timeslot.js_identifier
        return ss

# this object maintains the current state of the placement tool.
# the assignments hash says where the sessions would go.
class CurrentScheduleState:
    def __getitem__(self, key):
        if key in self.tempdict:
            return self.tempdict[key]
        return self.current_assignments[key]

    def __iter__(self):
        return self.current_assignments.__iter__()
    def iterkeys(self):
        return self.current_assignments.__iter__()

    def add_to_available_slot(self, fs):
        size = len(self.available_slots)
        if fs.session is not None:
            fs.session.setup_conflicts()

        time_column = None
        needs_to_be_added = True
        #print "adding fs for slot: %s" % (fs.timeslot)
        if fs.timeslot is not None:
            if fs.timeslot in self.fs_by_timeslot:
                ofs = self.fs_by_timeslot[fs.timeslot]
                #print "  duplicate timeslot[%s], updating old one: %s" % (ofs.available_slot, fs.timeslot)
                if ofs.session is None:
                    # keep the one with the assignment.
                    self.fs_by_timeslot[fs.timeslot] = fs
                    # get rid of old item
                    fs.available_slot = ofs.available_slot
                    self.available_slots[ofs.available_slot] = fs
                needs_to_be_added = False
            else:
                self.fs_by_timeslot[fs.timeslot] = fs

            # add the slot to the list of vertical slices.
            time_column = self.timeslots[fs.timeslot.time]
            #group_name = "empty"
            #if fs.session is not None:
            #    group_name = fs.session.group.acronym
            #print "  inserting fs %s / %s to slot: %s" % (fs.timeslot.location.name,
            #                                            group_name,
            #                                            time_column.daytime)
            fs.scheduleslot = time_column
            if fs.session is None:
                self.placed_scheduleslots.append(fs)
        else:
            time_column = self.unplaced_scheduledslots
            fs.scheduleslot = self.unplaced_scheduledslots

        if needs_to_be_added:
            self.total_slots  = size
            self.available_slots.append(fs)
            fs.available_slot = size

        if time_column is not None:
            # needs available_slot to be filled in
            time_column.add_assignment(fs)
        #print "adding item: %u to unplaced slots (pinned: %s)" % (fs.available_slot, fs.pinned)

    def __init__(self, schedule, seed=None):
        # initialize available_slots with the places that a session can go based upon the
        # schedtimesessassignment objects of the provided schedule.
        # for each session which is not initially scheduled, also create a schedtimesessassignment
        # that has a session, but no timeslot.

        self.recordsteps         = True
        self.debug_badness       = False
        self.lastSaveTime        = datetime.now()
        self.lastSaveStep        = 0
        self.verbose             = False

        # this maps a *group* to a list of (session,location) pairs, using FakeSchedTimeSessAssignment
        self.current_assignments = {}
        self.tempdict            = {}   # used when calculating badness.

        # this contains an entry for each location, and each un-location in the form of
        # (session,location) with the appropriate part None.
        self.fs_by_timeslot  = {}
        self.available_slots = []
        self.unplaced_scheduledslots  = UnplacedScheduleSlot()
        self.placed_scheduleslots     = []
        self.sessions        = {}
        self.total_slots     = 0

        self.schedule        = schedule
        self.meeting         = schedule.meeting
        self.seed            = seed
        self.badness         = schedule.badness
        self.random_generator=Random()
        self.random_generator.seed(seed)
        self.temperature     = 10000000
        self.stepnum         = 1
        self.timeslots       = {}
        self.slot1           = None
        self.slot2           = None

        # setup up array of timeslots objects
        for timeslot in schedule.meeting.timeslot_set.filter(type = "session").all():
            if not timeslot.time in self.timeslots:
                self.timeslots[timeslot.time] = ScheduleSlot(timeslot.time)
            fs = FakeSchedTimeSessAssignment(self.schedule)
            fs.timeslot = timeslot
            self.add_to_available_slot(fs)
        self.timeslots[None] = self.unplaced_scheduledslots

        # make list of things that need placement.
        for sess in self.meeting.sessions_that_can_be_placed().all():
            fs = FakeSchedTimeSessAssignment(self.schedule)
            fs.session     = sess
            self.sessions[sess] = fs
            self.current_assignments[sess.group] = []

        #print "Then had %u" % (self.total_slots)
        # now find slots that are not empty.
        # loop here and the one for useableslots could be merged into one loop
        allschedsessions = self.schedule.qs_assignments_with_sessions.filter(timeslot__type = "session").all()
        for ss in allschedsessions:
            # do not need to check for ss.session is not none, because filter above only returns those ones.
            sess = ss.session
            if not (sess in self.sessions):
                #print "Had to create sess for %s" % (sess)
                self.sessions[sess] = FakeSchedTimeSessAssignment(self.schedule)
            fs = self.sessions[sess]
            #print "Updating %s from %s(%s)" % (fs.session.group.acronym, ss.timeslot.location.name, ss.timeslot.time)
            fs.fromSchedTimeSessAssignment(ss)

            # if pinned, then do not consider it when selecting, but it needs to be in
            # current_assignments so that conflicts are calculated.
            if not ss.pinned:
                self.add_to_available_slot(fs)
            else:
                del self.sessions[sess]
            self.current_assignments[ss.session.group].append(fs)

            # XXX can not deal with a session in two slots yet?!

        # need to remove any sessions that might have gotten through above, but are in non-session
        # places, otherwise these could otherwise appear to be unplaced.
        allspecialsessions = self.schedule.qs_assignments_with_sessions.exclude(timeslot__type = "session").all()
        for ss in allspecialsessions:
            sess = ss.session
            if sess is None:
                continue
            if (sess in self.sessions):
                del self.sessions[sess]

        # now need to add entries for those sessions which are currently unscheduled (and yet not pinned)
        for sess,fs in self.sessions.iteritems():
            if fs.timeslot is None:
                #print "Considering sess: %s, and loc: %s" % (sess, str(fs.timeslot))
                self.add_to_available_slot(fs)

        #import pdb; pdb.set_trace()
        # do initial badness calculation for placement that has been done
        for daytime,scheduleslot in self.timeslots.iteritems():
            scheduleslot.recalc_badness(self)

    def dump_available_slot_state(self):
        for fs in self.available_slots:
           shortname="unplaced"
           sessid = 0
           if fs.session is not None:
              shortname=fs.session.short_name
              sessid = fs.session.id
           pinned = "unplaced"
           ssid=0
           if fs.origss is not None:
              pinned = fs.origss.pinned
              ssid = fs.origss.id
           print "%s: %s[%u] pinned: %s ssid=%u" % (fs.available_slot, shortname, sessid, pinned, ssid)

    def pick_initial_slot(self):
        if self.unplaced_scheduledslots.finished():
            self.initial_stage = False
        if self.initial_stage:
            item  = self.unplaced_scheduledslots.get_unplaced_slot_number()
            slot1 = self.available_slots[item]
            #print "item: %u points to %s" % (item, slot1)
        else:
            slot1 = self.random_generator.choice(self.available_slots)
        return slot1

    def pick_second_slot(self):
        if self.initial_stage and len(self.placed_scheduleslots)>0:
            self.random_generator.shuffle(self.placed_scheduleslots)
            slot2 = self.placed_scheduleslots[0]
            del self.placed_scheduleslots[0]
        else:
            slot2 = self.random_generator.choice(self.available_slots)
        return slot2

    def pick_two_slots(self):
        slot1 = self.pick_initial_slot()
        slot2 = self.pick_second_slot()
        tries = 100
        self.repicking = 0
        # 1) no point in picking two slots which are the same.
        # 2) no point in picking two slots which have no session (already empty)
        # 3) no point in picking two slots which are both unscheduled sessions
        # 4) limit outselves to ten tries.
        while (slot1 == slot2 or slot1 is None or slot2 is None or
               (slot1.session is None and slot2.session is None) or
               (slot1.timeslot is None and slot2.timeslot is None)
               ) and tries > 0:
            self.repicking += 1
            #print "%u: .. repicking slots, had: %s and %s" % (self.stepnum, slot1, slot2)
            slot1 = self.pick_initial_slot()
            slot2 = self.pick_second_slot()
            tries -= 1
        if tries == 0:
            raise PlacementException("How can it pick the same slot ten times in a row")

        if slot1.pinned:
            raise PlacementException("Should never attempt to move pinned slot1")

        if slot2.pinned:
            raise PlacementException("Should never attempt to move pinned slot2")

        return slot1, slot2

    # this assigns a session to a particular slot.
    def assign_session(self, session, fslot, doubleup=False):
        import copy
        if session is None:
            # we need to unschedule the session
            session = fslot.session
            self.tempdict[session.group] = []
            return

        if not session in self.sessions:
            raise PlacementException("Is there a legit case where session is not in sessions here?")

        oldfs = self.sessions[session]
        # find the group mapping.
        pairs = copy.copy(self.current_assignments[session.group])
        #print "pairs is: %s" % (pairs)
        if oldfs in pairs:
            which = pairs.index(oldfs)
            del pairs[which]
            #print "new pairs is: %s" % (pairs)

        self.sessions[session] = fslot
        # now fix up the other things.
        pairs.append(fslot)
        self.tempdict[session.group] = pairs

    def commit_tempdict(self):
        for key,value in self.tempdict.iteritems():
            self.current_assignments[key] = value
        self.tempdict = dict()

    # calculate badness of the columns which have changed
    def calc_badness(self, slot1, slot2):
        badness = 0
        for daytime,scheduleslot in self.timeslots.iteritems():
            oldbadness = scheduleslot.badness
            if oldbadness is None:
                oldbadness = 0
            recalc=""
            if slot1 is not None and slot1.scheduleslot == scheduleslot:
                recalc="recalc slot1"
                scheduleslot.recalc_badness(self)
            if slot2 is not None and slot2.scheduleslot == scheduleslot:
                recalc="recalc slot2"
                scheduleslot.recalc_badness(self)

            newbadness = scheduleslot.calc_badness(self)
            if self.debug_badness:
                print "  calc: %s %u %u %s" % (scheduleslot.daytime, oldbadness, newbadness, recalc)
            badness += newbadness
        return badness

    def try_swap(self):
        badness     = self.badness
        slot1,slot2 = self.pick_two_slots()
        if self.debug_badness:
            print "start\n slot1: %s.\n slot2: %s.\n badness: %s" % (slot1, slot2,badness)
        self.slot1 = slot1
        self.slot2 = slot2
        #import pdb; pdb.set_trace()
        #self.assign_session(slot2.session, slot1, False)
        #self.assign_session(slot1.session, slot2, False)
        # self can substitute for current_assignments thanks to getitem() above.
        newbadness  = self.calc_badness(slot1, slot2)
        if self.debug_badness:
            print "end\n slot1: %s.\n slot2: %s.\n badness: %s" % (slot1, slot2, newbadness)
        return newbadness

    def log_step(self, accepted_str, change, dice, prob):
        acronym1 = "empty"
        if self.slot1.session is not None:
            acronym1 = self.slot1.session.group.acronym
        place1   = "nowhere"
        if self.slot1.timeslot is not None:
            place1 = str(self.slot1.timeslot.location.name)

        acronym2= "empty"
        if self.slot2.session is not None:
            acronym2 = self.slot2.session.group.acronym
        place2   = "nowhere"
        if self.slot2.timeslot is not None:
            place2 = str(self.slot2.timeslot.location.name)
        initial = "    "
        if self.initial_stage:
            initial = "init"

        # note in logging: the swap has already occured, but the values were set before
        if self.verbose:
            print "% 5u:%s %s temp=%9u delta=%+9d badness=%10d dice=%.4f <=> prob=%.4f (repicking=%u)  %9s:[%8s->%8s], %9s:[%8s->%8s]" % (self.stepnum, initial,
                accepted_str, self.temperature,
                change, self.badness, dice, prob,
                self.repicking, acronym1, place2, place1, acronym2, place1, place2)

    def do_step(self):
        self.stepnum += 1
        newbadness = self.try_swap()
        if self.badness is None:
            self.commit_tempdict
            self.badness = newbadness
            return True, 0

        change = newbadness - self.badness
        prob   = self.calc_probability(change)
        dice   = self.random_generator.random()

        #self.log_step("consider", change, dice, prob)

        if dice < prob:
            accepted_str = "accepted"
            accepted = True
            # swap things as planned
            self.commit_tempdict

            # actually do the swap in the FS
            tmp = self.slot1.session
            self.slot1.session = self.slot2.session
            self.slot2.session = tmp
            self.badness = newbadness
            # save state object
        else:
            accepted_str = "rejected"
            accepted = False
            self.tempdict = dict()

        self.log_step(accepted_str, change, dice, prob)

        if accepted and not self.initial_stage:
            self.temperature = self.temperature * 0.9995

        return accepted, change

    def calc_probability(self, change):
        import math
        return 1/(1 + math.exp(float(change)/self.temperature))

    def delete_available_slot(self, number):
        # because the numbers matter, we just None things out, and let repicking
        # work on things.
        #last = len(self.available_slots)-1
        #if number < last:
        #    self.available_slots[number] = self.available_slots[last]
        #    self.available_slots[last].available_slot = number
        #
        #del self.available_slots[last]
        self.available_slots[number] = None

    def do_steps(self, limit=None, monitorSchedule=None):
        print "do_steps(%s,%s)" % (limit, monitorSchedule)
        if self.badness is None or self.badness == 0:
            self.badness = self.schedule.calc_badness1(self)
        self.oldbadness = self.badness
        while (limit is None or self.stepnum < limit) and self.temperature > 1000:
            accepted,change = self.do_step()
            #set_prompt_wait(True)
            if not accepted and self.initial_stage:
                # randomize again!
                self.unplaced_scheduledslots.shuffle(self.random_generator)

            if accepted and self.initial_stage and self.unplaced_scheduledslots.count>0:
                # delete it from available slots, so as not to leave unplaced slots
                self.delete_available_slot(self.slot1.available_slot)
                # remove initial slot from list.
                self.unplaced_scheduledslots.delete_first()

            if False and accepted and self.recordsteps:
                ass1 = AutomaticScheduleStep()
                ass1.schedule = self.schedule
                if self.slot1.session is not None:
                    ass1.session  = self.slot1.session
                if self.slot1.origss is not None:
                    ass1.moved_to = self.slot1.origss
                ass1.stepnum  = self.stepnum
                ass1.save()
                ass2 = AutomaticScheduleStep()
                ass2.schedule = self.schedule
                if self.slot2.session is not None:
                    ass2.session  = self.slot2.session
                if self.slot2.origss is not None:
                    ass2.moved_to = self.slot2.origss
                ass2.stepnum  = self.stepnum
                ass2.save()
            #print "%u: accepted: %s change %d temp: %d" % (self.stepnum, accepted, change, self.temperature)
            if (self.stepnum % 1000) == 0 and monitorSchedule is not None:
                self.saveToSchedule(monitorSchedule)
        print "Finished after %u steps, badness = %u->%u" % (self.stepnum, self.oldbadness, self.badness)

    def saveToSchedule(self, targetSchedule):
        when = datetime.now()
        since = 0
        rate  = 0
        if targetSchedule is None:
            targetSchedule = self.schedule
        else:
            # XXX more stuff to do here, setup mapping, copy pinned items
            pass

        if self.lastSaveTime is not None:
            since = when - self.lastSaveTime
            if since.microseconds > 0:
                rate  = 1000 * float(self.stepnum - self.lastSaveStep) / (1000*since.seconds + since.microseconds / 1000)
        print "%u: saved to schedule: %s %s elapsed=%s rate=%.2f" % (self.stepnum, targetSchedule.name, when, since, rate)
        self.lastSaveTime = datetime.now()
        self.lastSaveStep = self.stepnum

        # first, remove all assignments in the schedule.
        for ss in targetSchedule.assignments.all():
            if ss.pinned:
                continue
            ss.delete()

        # then, add new items for new placements.
        for fs in self.available_slots:
            if fs is None:
                continue
            ss = SchedTimeSessAssignment(timeslot = fs.timeslot,
                                  schedule = targetSchedule,
                                  session = fs.session)
            ss.save()

    def do_placement(self, limit=None, targetSchedule=None):
        self.badness  = self.schedule.calc_badness1(self)
        if limit is None:
            limitstr = "unlimited "
        else:
            limitstr = "%u" % (limit)
        print "Initial stage (limit=%s) starting with: %u items to place" % (limitstr, self.unplaced_scheduledslots.count)

        # permute the unplaced sessions
        self.unplaced_scheduledslots.shuffle(self.random_generator)

        self.initial_stage = True
        monitorSchedule = targetSchedule
        if monitorSchedule is None:
            monitorSchedule = self.schedule
        self.do_steps(limit, monitorSchedule)
        self.saveToSchedule(targetSchedule)

#
# this does not clearly have value at this point.
# Not worth a migration/table yet.
#
if False:
    class AutomaticScheduleStep(models.Model):
        schedule   = models.ForeignKey('Schedule', null=False, blank=False, help_text=u"Who made this agenda.")
        session    = models.ForeignKey('Session', null=True, default=None, help_text=u"Scheduled session involved.")
        moved_from = models.ForeignKey('SchedTimeSessAssignment', related_name="+", null=True, default=None, help_text=u"Where session was.")
        moved_to   = models.ForeignKey('SchedTimeSessAssignment', related_name="+", null=True, default=None, help_text=u"Where session went.")
        stepnum    = models.IntegerField(default=0, blank=True, null=True)

