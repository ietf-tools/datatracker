# old meeting models can be found in ../proceedings/models.py

import pytz, datetime

from django.db import models
from django.conf import settings
from timedeltafield import TimedeltaField

# mostly used by json_dict()
from django.template.defaultfilters import slugify, date as date_format, time as time_format
from django.utils import formats

from ietf.group.models import Group
from ietf.person.models import Person
from ietf.doc.models import Document
from ietf.name.models import MeetingTypeName, TimeSlotTypeName, SessionStatusName, ConstraintName

countries = pytz.country_names.items()
countries.sort(lambda x,y: cmp(x[1], y[1]))

timezones = [(name, name) for name in pytz.common_timezones]
timezones.sort()


# this is used in models to format dates, as the simplejson serializer
# can not deal with them, and the django provided serializer is inaccessible.
from django.utils import datetime_safe
DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M:%S"

def fmt_date(o):
    d = datetime_safe.new_date(o)
    return d.strftime(DATE_FORMAT)

def fmt_datetime(o):
    d = datetime_safe.new_date(o)
    return d.strftime("%s %s" % (DATE_FORMAT, TIME_FORMAT))


class Meeting(models.Model):
    # number is either the number for IETF meetings, or some other
    # identifier for interim meetings/IESG retreats/liaison summits/...
    number = models.CharField(unique=True, max_length=64)
    type = models.ForeignKey(MeetingTypeName)
    # Date is useful when generating a set of timeslot for this meeting, but
    # is not used to determine date for timeslot instances thereafter, as
    # they have their own datetime field.
    date = models.DateField()
    city = models.CharField(blank=True, max_length=255)
    country = models.CharField(blank=True, max_length=2, choices=countries)
    # We can't derive time-zone from country, as there are some that have
    # more than one timezone, and the pytz module doesn't provide timezone
    # lookup information for all relevant city/country combinations.
    time_zone = models.CharField(blank=True, max_length=255, choices=timezones)
    venue_name = models.CharField(blank=True, max_length=255)
    venue_addr = models.TextField(blank=True)
    break_area = models.CharField(blank=True, max_length=255)
    reg_area = models.CharField(blank=True, max_length=255)
    agenda_note = models.TextField(blank=True, help_text="Text in this field will be placed at the top of the html agenda page for the meeting.  HTML can be used, but will not validated.")
    agenda     = models.ForeignKey('Schedule',null=True,blank=True, related_name='+')

    def __unicode__(self):
        if self.type_id == "ietf":
            return "IETF-%s" % (self.number)
        else:
            return self.number

    def time_zone_offset(self):
        # Look at the time of 8 o'clock sunday, rather than 0h sunday, to get
        # the right time after a possible summer/winter time change.
        if self.time_zone:
            return pytz.timezone(self.time_zone).localize(datetime.datetime.combine(self.date, datetime.time(8, 0))).strftime("%z")
        else:
            return ""

    def get_meeting_date (self,offset):
        return self.date + datetime.timedelta(days=offset)

    def end_date(self):
        return self.get_meeting_date(5)

    @classmethod
    def get_first_cut_off(cls):
        date = cls.objects.all().filter(type="ietf").order_by('-date')[0].date
        offset = datetime.timedelta(days=settings.FIRST_CUTOFF_DAYS)
        return date - offset

    @classmethod
    def get_second_cut_off(cls):
        date = cls.objects.all().filter(type="ietf").order_by('-date')[0].date
        offset = datetime.timedelta(days=settings.SECOND_CUTOFF_DAYS)
        return date - offset

    @classmethod
    def get_ietf_monday(cls):
        date = cls.objects.all().filter(type="ietf").order_by('-date')[0].date
        return date + datetime.timedelta(days=-date.weekday(), weeks=1)

    # the various dates are currently computed
    def get_submission_start_date(self):
        return self.date + datetime.timedelta(days=settings.SUBMISSION_START_DAYS)
    def get_submission_cut_off_date(self):
        return self.date + datetime.timedelta(days=settings.SUBMISSION_CUTOFF_DAYS)
    def get_submission_correction_date(self):
        return self.date + datetime.timedelta(days=settings.SUBMISSION_CORRECTION_DAYS)

    def get_schedule_by_name(self, name):
        qs = self.schedule_set.filter(name=name)
        if qs:
            return qs[0]
        return None

    def url(self, sitefqdn, exten=".json"):
        return "%s/meeting/%s%s" % (sitefqdn, self.number, exten)

    @property
    def relurl(self):
        return self.url("")

    def json_dict(self, sitefqdn):
        # unfortunately, using the datetime aware json encoder seems impossible,
        # so the dates are formatted as strings here.
        agenda_url = ""
        if self.agenda:
            agenda_url = self.agenda.url(sitefqdn)
        return {
            'href':                 self.url(sitefqdn),
            'name':                 self.number,
            'submission_start_date':   fmt_date(self.get_submission_start_date()),
            'submission_cut_off_date': fmt_date(self.get_submission_cut_off_date()),
            'submission_correction_date': fmt_date(self.get_submission_correction_date()),
            'date':                    fmt_date(self.date),
            'agenda_href':             agenda_url,
            'city':                    self.city,
            'country':                 self.country,
            'time_zone':               self.time_zone,
            'venue_name':              self.venue_name,
            'venus_addr':              self.venue_addr,
            'break_area':              self.break_area,
            'reg_area':                self.reg_area
            }

    def build_timeslices(self):
        days = []          # the days of the meetings
        time_slices = {}   # the times on each day
        slots = {}

        ids = []
        for ts in self.timeslot_set.all():
            if ts.location is None:
                continue
            ymd = ts.time.date()
            if ymd not in time_slices:
                time_slices[ymd] = []
                slots[ymd] = []
                days.append(ymd)

            if ymd in time_slices:
                # only keep unique entries
                if [ts.time, ts.time + ts.duration] not in time_slices[ymd]:
                    time_slices[ymd].append([ts.time, ts.time + ts.duration])
                    slots[ymd].append(ts)

        days.sort()
        for ymd in time_slices:
            time_slices[ymd].sort()
            slots[ymd].sort(lambda x,y: cmp(x.time, y.time))
        return days,time_slices,slots

    # this functions makes a list of timeslices and rooms, and
    # makes sure that all schedules have all of them.
    def create_all_timeslots(self):
        alltimeslots = self.timeslot_set.all()
        for sched in self.schedule_set.all():
            ts_hash = {}
            for ss in sched.scheduledsession_set.all():
                ts_hash[ss.timeslot] = ss
            for ts in alltimeslots:
                if not (ts in ts_hash):
                    ScheduledSession.objects.create(schedule = sched,
                                                    timeslot = ts)

class Room(models.Model):
    meeting = models.ForeignKey(Meeting)
    name = models.CharField(max_length=255)
    capacity = models.IntegerField(null=True, blank=True)

    def __unicode__(self):
        return self.name

    def delete_timeslots(self):
        for ts in self.timeslot_set.all():
            ts.scheduledsession_set.all().delete()
            ts.delete()

    def create_timeslots(self):
        days, time_slices, slots  = self.meeting.build_timeslices()
        for day in days:
            for ts in slots[day]:
                ts0 = TimeSlot.objects.create(type_id=ts.type_id,
                                    meeting=self.meeting,
                                    name=ts.name,
                                    time=ts.time,
                                    location=self,
                                    duration=ts.duration)
        self.meeting.create_all_timeslots()

    def url(self, sitefqdn):
        return "%s/meeting/%s/room/%s.json" % (sitefqdn, self.meeting.number, self.id)

    @property
    def relurl(self):
        return self.url("")

    def json_dict(self, sitefqdn):
        return {
            'href':                 self.url(sitefqdn),
            'name':                 self.name,
            'capacity':             self.capacity,
            }


class TimeSlot(models.Model):
    """
    Everything that would appear on the meeting agenda of a meeting is
    mapped to a time slot, including breaks. Sessions are connected to
    TimeSlots during scheduling.
    """
    meeting = models.ForeignKey(Meeting)
    type = models.ForeignKey(TimeSlotTypeName)
    name = models.CharField(max_length=255)
    time = models.DateTimeField()
    duration = TimedeltaField()
    location = models.ForeignKey(Room, blank=True, null=True)
    show_location = models.BooleanField(default=True, help_text="Show location in agenda")
    sessions = models.ManyToManyField('Session', related_name='slots', through='ScheduledSession', null=True, blank=True, help_text=u"Scheduled session, if any")
    modified = models.DateTimeField(default=datetime.datetime.now)
    #

    @property
    def time_desc(self):
        return u"%s-%s" % (self.time.strftime("%H%M"), (self.time + self.duration).strftime("%H%M"))

    def meeting_date(self):
        return self.time.date()

    def registration(self):
        # below implements a object local cache
        # it tries to find a timeslot of type registration which starts at the same time as this slot
        # so that it can be shown at the top of the agenda.
        if not hasattr(self, '_reg_info'):
            try:
                self._reg_info = TimeSlot.objects.get(meeting=self.meeting, time__month=self.time.month, time__day=self.time.day, type="reg")
            except TimeSlot.DoesNotExist:
                self._reg_info = None
        return self._reg_info

    def reg_info(self):
        return (self.registration() is not None)

    def __unicode__(self):
        location = self.get_location()
        if not location:
            location = "(no location)"

        return u"%s: %s-%s %s, %s" % (self.meeting.number, self.time.strftime("%m-%d %H:%M"), (self.time + self.duration).strftime("%H:%M"), self.name, location)
    def end_time(self):
        return self.time + self.duration
    def get_location(self):
        location = self.location
        if location:
            location = location.name
        elif self.type_id == "reg":
            location = self.meeting.reg_area
        elif self.type_id == "break":
            location = self.meeting.break_area
        if not self.show_location:
            location = ""
        return location
    @property
    def tz(self):
        if self.meeting.time_zone:
            return pytz.timezone(self.meeting.time_zone)
        else:
            return None
    def tzname(self):
        if self.tz:
            return self.tz.tzname(self.time)
        else:
            return ""
    def utc_start_time(self):
        if self.tz:
            local_start_time = self.tz.localize(self.time)
            return local_start_time.astimezone(pytz.utc)
        else:
            return None
    def utc_end_time(self):
        if self.tz:
            local_end_time = self.tz.localize(self.end_time())
            return local_end_time.astimezone(pytz.utc)
        else:
            return None

    def session_name(self):
        if self.type_id not in ("session", "plenary"):
            return None

        class Dummy(object):
            def __unicode__(self):
                return self.session_name
        d = Dummy()
        d.session_name = self.name
        return d

    def session_for_schedule(self, schedule):
        ss = scheduledsession_set.filter(schedule=schedule).all()[0]
        if ss:
            return ss.session
        else:
            return None

    def scheduledsessions_at_same_time(self, agenda=None):
        if agenda is None:
            agenda = self.meeting.agenda

        return agenda.scheduledsession_set.filter(timeslot__time=self.time, timeslot__type__in=("session", "plenary", "other"))

    @property
    def js_identifier(self):
        # this returns a unique identifier that is js happy.
        #  {{s.timeslot.time|date:'Y-m-d'}}_{{ s.timeslot.time|date:'Hi' }}"
        # also must match:
        #  {{r|slugify}}_{{day}}_{{slot.0|date:'Hi'}}
        return "%s_%s_%s" % (slugify(self.get_location()), self.time.strftime('%Y-%m-%d'), self.time.strftime('%H%M'))


    @property
    def is_plenary(self):
        return self.type_id == "plenary"

    @property
    def is_plenary_type(self, name, agenda=None):
        return self.scheduledsessions_at_same_time(agenda)[0].acronym == name

    @property
    def slot_decor(self):
        if self.type_id == "plenary":
            return "plenary";
        elif self.type_id == "session":
            return "session";
        elif self.type_id == "non-session":
            return "non-session";
        else:
            return "reserved";

    def json_dict(self, selfurl):
        ts = dict()
        ts['timeslot_id'] = self.id
        ts['room']        = slugify(self.location)
        ts['roomtype'] = self.type.slug
        ts["time"]     = date_format(self.time, 'Hi')
        ts["date"]     = time_format(self.time, 'Y-m-d')
        ts["domid"]    = self.js_identifier
        return ts

    def url(self, sitefqdn):
        return "%s/meeting/%s/timeslot/%s.json" % (sitefqdn, self.meeting.number, self.id)

    @property
    def relurl(self):
        return self.url("")


    """
    This routine takes the current timeslot, which is assumed to have no location,
    and assigns a room, and then creates an identical timeslot for all of the other
    rooms.
    """
    def create_concurrent_timeslots(self):
        ts = self
        for room in self.meeting.room_set.all():
            ts.location = room
            ts.save()
            # this is simplest way to "clone" an object...
            ts.id = None
        self.meeting.create_all_timeslots()

    """
    This routine deletes all timeslots which are in the same time as this slot.
    """
    def delete_concurrent_timeslots(self):
        # can not include duration in filter, because there is no support
        # for having it a WHERE clause.
        # below will delete self as well.
        for ts in self.meeting.timeslot_set.filter(time=self.time).all():
            if ts.duration!=self.duration:
                continue

            # now remove any schedule that might have been made to this
            # timeslot.
            ts.scheduledsession_set.all().delete()
            ts.delete()

    """
    Find a timeslot that comes next, in the same room.   It must be on the same day,
    and it must have a gap of 11 minutes or less. (10 is the spec)
    """
    @property
    def slot_to_the_right(self):
        things = self.meeting.timeslot_set.filter(location = self.location,       # same room!
                                 type     = self.type,           # must be same type (usually session)
                                 time__gt = self.time + self.duration,  # must be after this session.
                                 time__lt = self.time + self.duration + datetime.timedelta(0,11*60))
        if things:
            return things[0]
        else:
            return None

# end of TimeSlot

class Schedule(models.Model):
    """
    Each person may have multiple agendas saved.
    An Agenda may be made visible, which means that it will show up in
    public drop down menus, etc.  It may also be made public, which means
    that someone who knows about it by name/id would be able to reference
    it.  A non-visible, public agenda might be passed around by the
    Secretariat to IESG members for review.  Only the owner may edit the
    agenda, others may copy it
    """
    meeting  = models.ForeignKey(Meeting, null=True)
    name     = models.CharField(max_length=16, blank=False)
    owner    = models.ForeignKey(Person)
    visible  = models.BooleanField(default=True, help_text=u"Make this agenda available to those who know about it")
    public   = models.BooleanField(default=True, help_text=u"Make this agenda publically available")
    # considering copiedFrom = models.ForeignKey('Schedule', blank=True, null=True)

    def __unicode__(self):
        return u"%s:%s(%s)" % (self.meeting, self.name, self.owner)

    def url(self, sitefqdn):
        return "%s/meeting/%s/agenda/%s" % (sitefqdn, self.meeting.number, self.name)

    @property
    def relurl(self):
        return self.url("")

    def url_edit(self, sitefqdn):
        return "%s/meeting/%s/agenda/%s/edit" % (sitefqdn, self.meeting.number, self.name)

    @property
    def relurl_edit(self):
        return self.url_edit("")

    @property
    def visible_token(self):
        if self.visible:
            return "visible"
        else:
            return "hidden"

    @property
    def public_token(self):
        if self.public:
            return "public"
        else:
            return "private"

    @property
    def is_official(self):
        return (self.meeting.agenda == self)

    @property
    def official_class(self):
        if self.is_official:
            return "agenda_official"
        else:
            return "agenda_unofficial"

    @property
    def official_token(self):
        if self.is_official:
            return "official"
        else:
            return "unofficial"

    def delete_scheduledsessions(self):
        self.scheduledsession_set.all().delete()

    # I'm loath to put calls to reverse() in there.
    # is there a better way?
    def url(self, sitefqdn):
        # XXX need to include owner.
        return "%s/meeting/%s/agendas/%s.json" % (sitefqdn, self.meeting.number, self.name)

    def json_dict(self, sitefqdn):
        sch = dict()
        sch['schedule_id'] = self.id
        sch['href']        = self.url(sitefqdn)
        if self.visible:
            sch['visible']  = "visible"
        else:
            sch['visible']  = "hidden"
        if self.public:
            sch['public']   = "public"
        else:
            sch['public']   = "private"
        sch['owner']       = self.owner.url(sitefqdn)
        # should include href to list of scheduledsessions, but they have no direct API yet.
        return sch

class ScheduledSession(models.Model):
    """
    This model provides an N:M relationship between Session and TimeSlot.
    Each relationship is attached to the named agenda, which is owned by
    a specific person/user.
    """
    timeslot = models.ForeignKey('TimeSlot', null=False, blank=False, help_text=u"")
    session  = models.ForeignKey('Session', null=True, default=None, help_text=u"Scheduled session")
    schedule = models.ForeignKey('Schedule', null=False, blank=False, help_text=u"Who made this agenda")
    extendedfrom = models.ForeignKey('ScheduledSession', null=True, default=None, help_text=u"Timeslot this session is an extension of")
    modified = models.DateTimeField(default=datetime.datetime.now)
    notes    = models.TextField(blank=True)

    def __unicode__(self):
        return u"%s [%s<->%s]" % (self.schedule, self.session, self.timeslot)

    @property
    def room_name(self):
        return self.timeslot.location.name

    @property
    def special_agenda_note(self):
        return self.session.agenda_note if self.session else ""

    @property
    def acronym(self):
        if self.session and self.session.group:
            return self.session.group.acronym

    @property
    def slot_to_the_right(self):
        ss1 = self.schedule.scheduledsession_set.filter(timeslot = self.timeslot.slot_to_the_right)
        if ss1:
            return ss1[0]
        else:
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
        if self.timeslot.type_id not in ("session", "plenary"):
            return None
        return self.timeslot.name

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
        breaks = self.schedule.scheduledsessions_set.filter(timeslot__time__month=self.timeslot.time.month, timeslot__time__day=self.timeslot.time.day, timeslot__type="break").order_by("timeslot__time")
        now = self.timeslot.time_desc[:4]
        for brk in breaks:
            if brk.time_desc[-4:] == now:
                return brk
        return None

    @property
    def area_name(self):
        if self.timeslot.type_id == "plenary":
            return "Plenary Sessions"
        elif self.session and self.session.group and self.session.group.acronym == "edu":
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
        if self.timeslot and self.timeslot.type:
            return self.timeslot.type.slug
        else:
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
        ss['scheduledsession_id'] = self.id
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


class Constraint(models.Model):
    """
    Specifies a constraint on the scheduling.
    One type (name=conflic?) of constraint is between source WG and target WG,
           e.g. some kind of conflict.
    Another type (name=adpresent) of constraing is between source WG and
           availability of a particular Person, usually an AD.
    A third type (name=avoidday) of constraing is between source WG and
           a particular day of the week, specified in day.
    """
    meeting = models.ForeignKey(Meeting)
    source = models.ForeignKey(Group, related_name="constraint_source_set")
    target = models.ForeignKey(Group, related_name="constraint_target_set", null=True)
    person = models.ForeignKey(Person, null=True, blank=True)
    day    = models.DateTimeField(null=True, blank=True)
    name   = models.ForeignKey(ConstraintName)

    def __unicode__(self):
        return u"%s %s %s" % (self.source, self.name.name.lower(), self.target)

    def url(self, sitefqdn):
        return "%s/meeting/%s/constraint/%s.json" % (sitefqdn, self.meeting.number, self.id)

    def json_dict(self, sitefqdn):
        ct1 = dict()
        ct1['constraint_id'] = self.id
        ct1['href']          = self.url(sitefqdn)
        ct1['name']          = self.name.slug
        if self.person is not None:
            ct1['person_href'] = self.person.url(sitefqdn)
        if self.source is not None:
            ct1['source_href'] = self.source.url(sitefqdn)
        if self.target is not None:
            ct1['target_href'] = self.target.url(sitefqdn)
        ct1['meeting_href'] = self.meeting.url(sitefqdn)
        return ct1



class Session(models.Model):
    """Session records that a group should have a session on the
    meeting (time and location is stored in a TimeSlot) - if multiple
    timeslots are needed, multiple sessions will have to be created.
    Training sessions and similar are modeled by filling in a
    responsible group (e.g. Edu team) and filling in the name."""
    meeting = models.ForeignKey(Meeting)
    name = models.CharField(blank=True, max_length=255, help_text="Name of session, in case the session has a purpose rather than just being a group meeting")
    short = models.CharField(blank=True, max_length=32, help_text="Short version of 'name' above, for use in filenames")
    group = models.ForeignKey(Group)    # The group type determines the session type.  BOFs also need to be added as a group.
    attendees = models.IntegerField(null=True, blank=True)
    agenda_note = models.CharField(blank=True, max_length=255)
    requested = models.DateTimeField(default=datetime.datetime.now)
    requested_by = models.ForeignKey(Person)
    requested_duration = TimedeltaField(default=0)
    comments = models.TextField(blank=True)
    status = models.ForeignKey(SessionStatusName)
    scheduled = models.DateTimeField(null=True, blank=True)
    modified = models.DateTimeField(default=datetime.datetime.now)

    materials = models.ManyToManyField(Document, blank=True)

    def agenda(self):
        items = self.materials.filter(type="agenda",states__type="agenda",states__slug="active")
        if items and items[0] is not None:
            return items[0]
        else:
            return None

    def minutes(self):
        try:
            return self.materials.get(type="minutes",states__type="minutes",states__slug="active")
        except Exception:
            return None

    def slides(self):
        try:
            return self.materials.filter(type="slides",states__type="slides",states__slug="active").order_by("order")
        except Exception:
            return []

    def __unicode__(self):
        if self.meeting.type_id == "interim":
            return self.meeting.number

        ss0name = "(unscheduled)"
        ss = self.scheduledsession_set.order_by('timeslot__time')
        if ss:
            ss0name = ss[0].timeslot.time.strftime("%H%M")
        return u"%s: %s %s" % (self.meeting, self.group.acronym, ss0name)

    @property
    def short_name(self):
        if self.name:
            return self.name
        if self.short:
            return self.short
        if self.group:
            return self.group.acronym
        return u"req#%u" % (id)

    @property
    def special_request_token(self):
        if self.comments is not None and len(self.comments)>0:
            return "*"
        else:
            return ""

    def constraints(self):
        return Constraint.objects.filter(source=self.group, meeting=self.meeting).order_by('name__name')

    def reverse_constraints(self):
        return Constraint.objects.filter(target=self.group, meeting=self.meeting).order_by('name__name')

    def scheduledsession_for_agenda(self, schedule):
        return self.scheduledsession_set.filter(schedule=schedule)[0]

    def official_scheduledsession(self):
        return self.scheduledsession_for_agenda(self.meeting.agenda)

    def constraints_dict(self, sitefqdn):
        constraint_list = []
        for constraint in self.group.constraint_source_set.filter(meeting=self.meeting):
            ct1 = constraint.json_dict(sitefqdn)
            constraint_list.append(ct1)

        for constraint in self.group.constraint_target_set.filter(meeting=self.meeting):
            ct1 = constraint.json_dict(sitefqdn)
            constraint_list.append(ct1)
        return constraint_list

    def url(self, sitefqdn):
        return "%s/meeting/%s/session/%s.json" % (sitefqdn, self.meeting.number, self.id)

    def json_dict(self, sitefqdn):
        sess1 = dict()
        sess1['href']           = self.url(sitefqdn)
        sess1['group_href']     = self.group.url(sitefqdn)
        sess1['group_acronym']  = str(self.group.acronym)
        sess1['name']           = str(self.name)
        sess1['short_name']     = str(self.name)
        sess1['agenda_note']    = str(self.agenda_note)
        sess1['attendees']      = str(self.attendees)
        sess1['status']         = str(self.status)
        if self.comments is not None:
            sess1['comments']       = str(self.comments)
        sess1['requested_time'] = str(self.requested.strftime("%Y-%m-%d"))
        sess1['requested_by']   = str(self.requested_by)
        sess1['requested_duration']= "%.1f h" % (float(self.requested_duration.seconds) / 3600)
        sess1['area']           = str(self.group.parent.acronym)
        sess1['responsible_ad'] = str(self.group.ad)
        sess1['GroupInfo_state']= str(self.group.state)
        return sess1


