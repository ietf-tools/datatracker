# old meeting models can be found in ../proceedings/models.py

import pytz, datetime

from django.db import models
from django.conf import settings
from timedeltafield import TimedeltaField

from ietf.group.models import Group
from ietf.person.models import Person
from ietf.doc.models import Document
from ietf.name.models import MeetingTypeName, TimeSlotTypeName, SessionStatusName, ConstraintName

countries = pytz.country_names.items()
countries.sort(lambda x,y: cmp(x[1], y[1]))

timezones = [(name, name) for name in pytz.common_timezones]
timezones.sort()

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

    def __unicode__(self):
        if self.type_id == "ietf":
            return "IETF-%s" % (self.number)
        else:
            return self.number

    def time_zone_offset(self):
        # Look at the time of 8 o'clock sunday, rather than 0h sunday, to get
        # the right time after a possible summer/winter time change.
        return pytz.timezone(self.time_zone).localize(datetime.datetime.combine(self.date, datetime.time(8, 0))).strftime("%z")

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

class Room(models.Model):
    meeting = models.ForeignKey(Meeting)
    name = models.CharField(max_length=255)

    def __unicode__(self):
        return self.name

class TimeSlot(models.Model):
    """
    Everything that would appear on the meeting agenda of a meeting is
    mapped to a time slot, including breaks. Sessions are connected to
    TimeSlots during scheduling. A template function to populate a
    meeting with an appropriate set of TimeSlots is probably also
    needed.
    """
    meeting = models.ForeignKey(Meeting)
    type = models.ForeignKey(TimeSlotTypeName)
    name = models.CharField(max_length=255)
    time = models.DateTimeField()
    duration = TimedeltaField()
    location = models.ForeignKey(Room, blank=True, null=True)
    show_location = models.BooleanField(default=True, help_text="Show location in agenda")
    session = models.ForeignKey('Session', null=True, blank=True, help_text=u"Scheduled session, if any")
    modified = models.DateTimeField(default=datetime.datetime.now)

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

        
    
class Constraint(models.Model):
    """Specifies a constraint on the scheduling between source and
    target, e.g. some kind of conflict."""
    meeting = models.ForeignKey(Meeting)
    source = models.ForeignKey(Group, related_name="constraint_source_set")
    target = models.ForeignKey(Group, related_name="constraint_target_set")
    name = models.ForeignKey(ConstraintName)

    def __unicode__(self):
        return u"%s %s %s" % (self.source, self.name.name.lower(), self.target)

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
        try:
            return self.materials.get(type="agenda",states__type="agenda",states__slug="active")
        except Exception:
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

        timeslots = self.timeslot_set.order_by('time')
        return u"%s: %s %s" % (self.meeting, self.group.acronym, timeslots[0].time.strftime("%H%M") if timeslots else "(unscheduled)")

    def constraints(self):
        return Constraint.objects.filter(target=self.group, meeting=self.meeting).order_by('name__name')
