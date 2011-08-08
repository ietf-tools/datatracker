# old meeting models can be found in ../proceedings/models.py

import pytz

from django.db import models
from timedeltafield import TimedeltaField

from redesign.group.models import Group
from redesign.person.models import Person
from redesign.doc.models import Document
from redesign.name.models import TimeSlotTypeName, SessionStatusName, ConstraintName

countries = pytz.country_names.items()
countries.sort(lambda x,y: cmp(x[1], y[1]))

timezones = [(name, name) for name in pytz.common_timezones]
timezones.sort()

class Meeting(models.Model):
    # Number is not an integer any more, in order to be able to accomodate
    # interim meetings (and other variations?)
    number = models.CharField(max_length=64)
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
    
    def __str__(self):
	return "IETF-%s" % (self.number)
    def get_meeting_date (self,offset):
        return self.date + datetime.timedelta(days=offset)
    # cut-off dates (draft submission cut-of, wg agenda cut-off, minutes
    # submission cut-off), and more, are probably methods of this class,
    # rather than fields on a Proceedings class.

    @classmethod
    def get_first_cut_off(cls):
        date = cls.objects.all().order_by('-date')[0].date
        offset = datetime.timedelta(days=settings.FIRST_CUTOFF_DAYS)
        return date - offset

    @classmethod
    def get_second_cut_off(cls):
        date = cls.objects.all().order_by('-date')[0].date
        offset = datetime.timedelta(days=settings.SECOND_CUTOFF_DAYS)
        return date - offset

    @classmethod
    def get_ietf_monday(cls):
        date = cls.objects.all().order_by('-date')[0].date
        return date + datetime.timedelta(days=-date.weekday(), weeks=1)


class Room(models.Model):
    meeting = models.ForeignKey(Meeting)
    name = models.CharField(max_length=255)

    def __unicode__(self):
        return self.name

class TimeSlot(models.Model):
    """
    Everything that would appear on the meeting agenda of a meeting is mapped
    to a time slot, including breaks (i.e., also NonSession+NonSessionRef.
    Sessions are connected to TimeSlots during scheduling.
    A template function to populate a meeting with an appropriate set of TimeSlots
    is probably also needed.
    """
    meeting = models.ForeignKey(Meeting)
    type = models.ForeignKey(TimeSlotTypeName)
    name = models.CharField(max_length=255)
    time = models.DateTimeField()
    duration = TimedeltaField()
    location = models.ForeignKey(Room, blank=True, null=True)
    show_location = models.BooleanField(default=True)
    materials = models.ManyToManyField(Document, blank=True)

    def __unicode__(self):
        location = self.get_location()
        if not location:
            location = "(no location)"
            
        return u"%s: %s-%s %s, %s" % (self.meeting.number, self.time.strftime("%m-%d %H:%M"), (self.time + self.duration).strftime("%H:%M"), self.name, location)

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
        return u"%s %s %s" % (self.source, self.name.lower(), self.target)

class Session(models.Model):
    meeting = models.ForeignKey(Meeting)
    timeslot = models.ForeignKey(TimeSlot, null=True, blank=True) # Null until session has been scheduled
    group = models.ForeignKey(Group)    # The group type determines the session type.  BOFs also need to be added as a group.
    attendees = models.IntegerField(null=True, blank=True)
    agenda_note = models.CharField(blank=True, max_length=255)
    #
    requested = models.DateTimeField()
    requested_by = models.ForeignKey(Person)
    requested_duration = TimedeltaField()
    comments = models.TextField()
    #
    status = models.ForeignKey(SessionStatusName)
    scheduled = models.DateTimeField(null=True, blank=True)
    modified = models.DateTimeField(null=True, blank=True)

    # contains the materials while the session is being requested,
    # when it is scheduled, timeslot.materials should be used (FIXME: ask Henrik)
    materials = models.ManyToManyField(Document, blank=True)

    def __unicode__(self):
        return u"%s: %s %s" % (self.meeting, self.group.acronym, self.timeslot.time.strftime("%H%M") if self.timeslot else "(unscheduled)")

# Agendas, Minutes and Slides are all mapped to Document.

# IESG history is extracted from GroupHistory, rather than hand coded in a
# separate table.

