# Copyright The IETF Trust 2007-2020, All Rights Reserved
# -*- coding: utf-8 -*-


# old meeting models can be found in ../proceedings/models.py

import datetime
import io
import os
import pytz
import random
import re
import string

from collections import namedtuple
from pathlib import Path
from urllib.parse import urljoin

import debug                            # pyflakes:ignore

from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Max, Subquery, OuterRef, TextField, Value, Q
from django.db.models.functions import Coalesce
from django.conf import settings
# mostly used by json_dict()
#from django.template.defaultfilters import slugify, date as date_format, time as time_format
from django.template.defaultfilters import date as date_format
from django.utils.text import slugify
from django.utils.safestring import mark_safe

from ietf.dbtemplate.models import DBTemplate
from ietf.doc.models import Document
from ietf.group.models import Group
from ietf.group.utils import can_manage_materials
from ietf.name.models import (
    MeetingTypeName, TimeSlotTypeName, SessionStatusName, ConstraintName, RoomResourceName,
    ImportantDateName, TimerangeName, SlideSubmissionStatusName, ProceedingsMaterialTypeName,
)
from ietf.person.models import Person
from ietf.utils.decorators import memoize
from ietf.utils.storage import NoLocationMigrationFileSystemStorage
from ietf.utils.text import xslugify
from ietf.utils.timezone import date2datetime
from ietf.utils.models import ForeignKey
from ietf.utils.validators import (
    MaxImageSizeValidator, WrappedValidator, validate_file_size, validate_mime_type,
    validate_file_extension,
)
from ietf.utils.fields import MissingOkImageField
from ietf.utils.log import unreachable

countries = list(pytz.country_names.items())
countries.sort(key=lambda x: x[1])

timezones = []
for name in pytz.common_timezones:
    tzfn = os.path.join(settings.TZDATA_ICS_PATH, name + ".ics")
    if not os.path.islink(tzfn):
        timezones.append((name, name))
timezones.sort()


# this is used in models to format dates, as the built-in json serializer
# can not deal with them, and the django provided serializer is inaccessible.
from django.utils import datetime_safe
DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M:%S"

def fmt_date(o):
    d = datetime_safe.new_date(o)
    return d.strftime(DATE_FORMAT)

class Meeting(models.Model):
    # number is either the number for IETF meetings, or some other
    # identifier for interim meetings/IESG retreats/liaison summits/...
    number = models.CharField(unique=True, max_length=64)
    type = ForeignKey(MeetingTypeName)
    # Date is useful when generating a set of timeslot for this meeting, but
    # is not used to determine date for timeslot instances thereafter, as
    # they have their own datetime field.
    date = models.DateField()
    days = models.IntegerField(default=7, null=False, validators=[MinValueValidator(1)],
        help_text="The number of days the meeting lasts")
    city = models.CharField(blank=True, max_length=255)
    country = models.CharField(blank=True, max_length=2, choices=countries)
    # We can't derive time-zone from country, as there are some that have
    # more than one timezone, and the pytz module doesn't provide timezone
    # lookup information for all relevant city/country combinations.
    time_zone = models.CharField(blank=True, max_length=255, choices=timezones)
    idsubmit_cutoff_day_offset_00 = models.IntegerField(blank=True,
        default=settings.IDSUBMIT_DEFAULT_CUTOFF_DAY_OFFSET_00,
        help_text = "The number of days before the meeting start date when the submission of -00 drafts will be closed.")
    idsubmit_cutoff_day_offset_01 = models.IntegerField(blank=True,
        default=settings.IDSUBMIT_DEFAULT_CUTOFF_DAY_OFFSET_01,
        help_text = "The number of days before the meeting start date when the submission of -01 drafts etc. will be closed.")        
    idsubmit_cutoff_time_utc  = models.DurationField(blank=True,
        default=settings.IDSUBMIT_DEFAULT_CUTOFF_TIME_UTC,
        help_text = "The time of day (UTC) after which submission will be closed.  Use for example 23:59:59.")
    idsubmit_cutoff_warning_days  = models.DurationField(blank=True,
        default=settings.IDSUBMIT_DEFAULT_CUTOFF_WARNING_DAYS,
        help_text = "How long before the 00 cutoff to start showing cutoff warnings.  Use for example '21' or '21 days'.")
    submission_start_day_offset = models.IntegerField(blank=True,
        default=settings.MEETING_MATERIALS_DEFAULT_SUBMISSION_START_DAYS,
        help_text = "The number of days before the meeting start date after which meeting materials will be accepted.")
    submission_cutoff_day_offset = models.IntegerField(blank=True,
        default=settings.MEETING_MATERIALS_DEFAULT_SUBMISSION_CUTOFF_DAYS,
        help_text = "The number of days after the meeting start date in which new meeting materials will be accepted.")
    submission_correction_day_offset = models.IntegerField(blank=True,
        default=settings.MEETING_MATERIALS_DEFAULT_SUBMISSION_CORRECTION_DAYS,
        help_text = "The number of days after the meeting start date in which updates to existing meeting materials will be accepted.")
    venue_name = models.CharField(blank=True, max_length=255)
    venue_addr = models.TextField(blank=True)
    break_area = models.CharField(blank=True, max_length=255)
    reg_area = models.CharField(blank=True, max_length=255)
    agenda_info_note = models.TextField(blank=True, help_text="Text in this field will be placed at the top of the html agenda page for the meeting.  HTML can be used, but will not be validated.")
    agenda_warning_note = models.TextField(blank=True, help_text="Text in this field will be placed more prominently at the top of the html agenda page for the meeting.  HTML can be used, but will not be validated.")
    schedule   = ForeignKey('Schedule',null=True,blank=True, related_name='+')
    session_request_lock_message = models.CharField(blank=True,max_length=255) # locked if not empty
    proceedings_final = models.BooleanField(default=False, help_text="Are the proceedings for this meeting complete?")
    acknowledgements = models.TextField(blank=True, help_text="Acknowledgements for use in meeting proceedings.  Use ReStructuredText markup.")
    overview = ForeignKey(DBTemplate, related_name='overview', null=True, editable=False)
    show_important_dates = models.BooleanField(default=False)
    attendees = models.IntegerField(blank=True, null=True, default=None,
                                    help_text="Number of Attendees for backfilled meetings, leave it blank for new meetings, and then it is calculated from the registrations")
    group_conflict_types = models.ManyToManyField(
        ConstraintName, blank=True, limit_choices_to=dict(is_group_conflict=True),
        help_text='Types of scheduling conflict between groups to consider')

    def __str__(self):
        if self.type_id == "ietf":
            return u"IETF-%s" % (self.number)
        else:
            return self.number

    def get_meeting_date (self,offset):
        return self.date + datetime.timedelta(days=offset)

    def end_date(self):
        return self.get_meeting_date(self.days-1)

    def get_00_cutoff(self):
        start_date = datetime.datetime(year=self.date.year, month=self.date.month, day=self.date.day, tzinfo=pytz.utc)
        importantdate = self.importantdate_set.filter(name_id='idcutoff').first()
        if not importantdate:
            importantdate = self.importantdate_set.filter(name_id='00cutoff').first()
        if importantdate:
            cutoff_date = importantdate.date
        else:
            cutoff_date = start_date + datetime.timedelta(days=ImportantDateName.objects.get(slug='idcutoff').default_offset_days)
        cutoff_time = date2datetime(cutoff_date) + self.idsubmit_cutoff_time_utc
        return cutoff_time

    def get_01_cutoff(self):
        start_date = datetime.datetime(year=self.date.year, month=self.date.month, day=self.date.day, tzinfo=pytz.utc)
        importantdate = self.importantdate_set.filter(name_id='idcutoff').first()
        if not importantdate:
            importantdate = self.importantdate_set.filter(name_id='01cutoff').first()
        if importantdate:
            cutoff_date = importantdate.date
        else:
            cutoff_date = start_date + datetime.timedelta(days=ImportantDateName.objects.get(slug='idcutoff').default_offset_days)
        cutoff_time = date2datetime(cutoff_date) + self.idsubmit_cutoff_time_utc
        return cutoff_time

    def get_reopen_time(self):
        start_date = datetime.datetime(year=self.date.year, month=self.date.month, day=self.date.day)
        local_tz = pytz.timezone(self.time_zone)
        local_date = local_tz.localize(start_date)
        cutoff = self.get_00_cutoff()
        if cutoff.date() == start_date:
            # no cutoff, so no local-time re-open
            reopen_time = cutoff
        else:
            # reopen time is in local timezone.  May need policy change??  XXX
            reopen_time = local_date + self.idsubmit_cutoff_time_utc
        return reopen_time

    @classmethod
    def get_current_meeting(cls, type="ietf"):
        return cls.objects.filter(type=type, date__gte=datetime.datetime.today()-datetime.timedelta(days=7) ).order_by('date').first()

    def get_first_cut_off(self):
        return self.get_00_cutoff()

    def get_second_cut_off(self):
        return self.get_01_cutoff()

    def get_ietf_monday(self):
        for offset in range(self.days):
            date = self.date+datetime.timedelta(days=offset)
            if date.weekday() == 0:     # Monday is 0
                return date

    def get_materials_path(self):
        return os.path.join(settings.AGENDA_PATH,self.number)
    
    # the various dates are currently computed
    def get_submission_start_date(self):
        return self.date - datetime.timedelta(days=self.submission_start_day_offset)
    def get_submission_cut_off_date(self):
        importantdate = self.importantdate_set.filter(name_id='procsub').first()
        if importantdate:
            return importantdate.date
        else:
            return self.date + datetime.timedelta(days=self.submission_cutoff_day_offset)

    def get_submission_correction_date(self):
        importantdate = self.importantdate_set.filter(name_id='revsub').first()
        if importantdate:
            return importantdate.date
        else:
            return self.date + datetime.timedelta(days=self.submission_correction_day_offset)

    def enabled_constraint_names(self):
        return ConstraintName.objects.filter(
            Q(is_group_conflict=False)  # any non-group-conflict constraints
            | Q(is_group_conflict=True, meeting=self)  # or specifically enabled for this meeting
        )

    def enabled_constraints(self):
        return self.constraint_set.filter(name__in=self.enabled_constraint_names())

    def get_schedule_by_name(self, name):
        return self.schedule_set.filter(name=name).first()

    def get_number(self):
        "Return integer meeting number for ietf meetings, rather than strings."
        if self.number.isdigit():
            return int(self.number)
        else:
            return None

    def get_proceedings_materials(self):
        """Get proceedings materials"""
        return self.proceedings_materials.filter(
            document__states__slug='active', document__states__type_id='procmaterials'
        ).order_by('type__order')

    def get_attendance(self):
        """Get the meeting attendance from the MeetingRegistrations

        Returns a NamedTuple with onsite and online attributes. Returns None if the record is unavailable
        for this meeting.
        """
        number = self.get_number()
        if number is None or number < 110:
            return None
        Attendance = namedtuple('Attendance', 'onsite online')
        return Attendance(
            onsite=Person.objects.filter(
                meetingregistration__meeting=self,
                meetingregistration__attended=True,
                meetingregistration__reg_type__contains='in_person',
            ).distinct().count(),
            online=Person.objects.filter(
                meetingregistration__meeting=self,
                meetingregistration__attended=True,
                meetingregistration__reg_type__contains='remote',
            ).distinct().count(),
        )

    @property
    def proceedings_format_version(self):
        """Indicate version of proceedings that should be used for this meeting

        Only makes sense for IETF meeting. Returns None for any meeting without a purely numeric number.

        Uses settings.PROCEEDINGS_VERSION_CHANGES. Versions start at 1. Entries
        in the array are the first meeting number using each version.
        """
        if not hasattr(self, '_proceedings_format_version'):
            if not self.number.isdigit():
                version = None  # no version for non-IETF meeting
            else:
                version = len(settings.PROCEEDINGS_VERSION_CHANGES)  # start assuming latest version
                mtg_number = self.get_number()
                if mtg_number is None:
                    unreachable('2021-08-10')
                else:
                    # Find the index of the first entry in the version change array that
                    # is >= this meeting's number. The first entry in the array is 0, so the
                    # version is always >= 1 for positive meeting numbers.
                    for vers, threshold in enumerate(settings.PROCEEDINGS_VERSION_CHANGES):
                        if mtg_number < threshold:
                            version = vers
                            break
            self._proceedings_format_version = version  # save this for later
        return self._proceedings_format_version

    @property
    def session_constraintnames(self):
        """Gets a list of the constraint names that should be used for this meeting

        Anticipated that this will soon become a many-to-many relationship with ConstraintName
        (see issue #2770). Making this a @property allows use of the .all(), .filter(), etc,
        so that other code should not need changes when this is replaced.
        """
        try:
            mtg_num = int(self.number)
        except ValueError:
            mtg_num = None  # should not come up, but this method should not fail
        if mtg_num is None or mtg_num >= 106:
            # These meetings used the old 'conflic?' constraint types labeled as though
            # they were the new types.
            slugs = ('chair_conflict', 'tech_overlap', 'key_participant')
        else:
            slugs = ('conflict', 'conflic2', 'conflic3')
        return ConstraintName.objects.filter(slug__in=slugs)

    def json_url(self):
        return "/meeting/%s/json" % (self.number, )

    def base_url(self):
        return "/meeting/%s" % (self.number, )

    def json_dict(self, host_scheme):
        # unfortunately, using the datetime aware json encoder seems impossible,
        # so the dates are formatted as strings here.
        agenda_url = ""
        if self.schedule:
            agenda_url = urljoin(host_scheme, self.schedule.base_url())
        return {
            'href':                 urljoin(host_scheme, self.json_url()),
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
            'venue_addr':              self.venue_addr,
            'break_area':              self.break_area,
            'reg_area':                self.reg_area
            }

    def build_timeslices(self):
        days = []          # the days of the meetings
        time_slices = {}   # the times on each day
        slots = {}

        for ts in self.timeslot_set.all():
            if ts.location_id is None:
                continue
            ymd = ts.time.date()
            if ymd not in time_slices:
                time_slices[ymd] = []
                slots[ymd] = []
                days.append(ymd)

            if ymd in time_slices:
                # only keep unique entries
                if [ts.time, ts.time + ts.duration, ts.duration.seconds] not in time_slices[ymd]:
                    time_slices[ymd].append([ts.time, ts.time + ts.duration, ts.duration.seconds])
                    slots[ymd].append(ts)

        days.sort()
        for ymd in time_slices:
            time_slices[ymd].sort()
            slots[ymd].sort(key=lambda x: x.time)
        return days,time_slices,slots

    # this functions makes a list of timeslices and rooms, and
    # makes sure that all schedules have all of them.
#    def create_all_timeslots(self):
#        alltimeslots = self.timeslot_set.all()
#        for sched in self.schedule_set.all():
#            ts_hash = {}
#            for ss in sched.assignments.all():
#                ts_hash[ss.timeslot] = ss
#            for ts in alltimeslots:
#                if not (ts in ts_hash):
#                    SchedTimeSessAssignment.objects.create(schedule = sched,
#                                                    timeslot = ts)

    def vtimezone(self):
        if self.time_zone:
            try:
                tzfn = os.path.join(settings.TZDATA_ICS_PATH, self.time_zone + ".ics")
                if os.path.exists(tzfn):
                    with io.open(tzfn) as tzf:
                        icstext = tzf.read()
                    vtimezone = re.search("(?sm)(\nBEGIN:VTIMEZONE.*\nEND:VTIMEZONE\n)", icstext).group(1).strip()
                    if vtimezone:
                        vtimezone += "\n"
                    return vtimezone
            except IOError:
                pass
        return ''

    def set_official_schedule(self, schedule):
        if self.schedule != schedule:
            self.schedule = schedule
            self.save()

    def updated(self):
        min_time = datetime.datetime(1970, 1, 1, 0, 0, 0) # should be Meeting.modified, but we don't have that
        timeslots_updated = self.timeslot_set.aggregate(Max('modified'))["modified__max"] or min_time
        sessions_updated = self.session_set.aggregate(Max('modified'))["modified__max"] or min_time
        assignments_updated = min_time
        if self.schedule:
            assignments_updated = SchedTimeSessAssignment.objects.filter(schedule__in=[self.schedule, self.schedule.base if self.schedule else None]).aggregate(Max('modified'))["modified__max"] or min_time
        ts = max(timeslots_updated, sessions_updated, assignments_updated)
        tz = pytz.timezone(settings.PRODUCTION_TIMEZONE)
        ts = tz.localize(ts)
        return ts

    @memoize
    def previous_meeting(self):
        return Meeting.objects.filter(type_id=self.type_id,date__lt=self.date).order_by('-date').first()

    class Meta:
        ordering = ["-date", "-id"]
        indexes = [
            models.Index(fields=['-date', '-id']),
        ]

# === Rooms, Resources, Floorplans =============================================

class ResourceAssociation(models.Model):
    name = ForeignKey(RoomResourceName)
    icon = models.CharField(max_length=64)       # icon to be found in /static/img
    desc = models.CharField(max_length=256)

    def __str__(self):
        return self.desc

    def json_dict(self, host_scheme):
        res1 = dict()
        res1['name'] = self.name.slug
        res1['icon'] = "/images/%s" % (self.icon)
        res1['desc'] = self.desc
        res1['resource_id'] = self.pk
        return res1

class Room(models.Model):
    meeting = ForeignKey(Meeting)
    modified = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=255)
    functional_name = models.CharField(max_length=255, blank = True)
    capacity = models.IntegerField(null=True, blank=True)
    resources = models.ManyToManyField(ResourceAssociation, blank = True)
    session_types = models.ManyToManyField(TimeSlotTypeName, blank = True)
    # floorplan-related properties
    floorplan = ForeignKey('FloorPlan', null=True, blank=True, default=None)
    # floorplan: room pixel position : (0,0) is top left of image, (xd, yd)
    # is room width, height.
    x1 = models.SmallIntegerField(null=True, blank=True, default=None)
    y1 = models.SmallIntegerField(null=True, blank=True, default=None)
    x2 = models.SmallIntegerField(null=True, blank=True, default=None)
    y2 = models.SmallIntegerField(null=True, blank=True, default=None)
    # end floorplan-related stuff

    def __str__(self):
        return u"%s size: %s" % (self.name, self.capacity)

    def delete_timeslots(self):
        for ts in self.timeslot_set.all():
            ts.sessionassignments.all().delete()
            ts.delete()

    def create_timeslots(self):
        days, time_slices, slots  = self.meeting.build_timeslices()
        for day in days:
            for ts in slots[day]:
                TimeSlot.objects.create(type_id=ts.type_id,
                                    meeting=self.meeting,
                                    name=ts.name,
                                    time=ts.time,
                                    location=self,
                                    duration=ts.duration)
        #self.meeting.create_all_timeslots()

    def dom_id(self):
        return "room%u" % (self.pk)

    def json_url(self):
        return "/meeting/%s/room/%s.json" % (self.meeting.number, self.id)

    def json_dict(self, host_scheme):
        return {
            'href':                 urljoin(host_scheme, self.json_url()),
            'name':                 self.name,
            'capacity':             self.capacity,
            }
    # floorplan support
    def left(self):
        return min(self.x1, self.x2) if (self.x1 and self.x2) else 0
    def top(self):
        return min(self.y1, self.y2) if (self.y1 and self.y2) else 0
    def right(self):
        return max(self.x1, self.x2) if (self.x1 and self.x2) else 0
    def bottom(self):
        return max(self.y1, self.y2) if (self.y1 and self.y2) else 0
    def functional_display_name(self):
        if not self.functional_name:
            return ""
        if 'breakout' in self.functional_name.lower():
            return ""
        if self.functional_name[0].isdigit():
            return ""
        return self.functional_name
    # audio stream support
    def audio_stream_url(self):
        urlresources = [ur for ur in self.urlresource_set.all() if ur.name_id == 'audiostream']
        return urlresources[0].url if urlresources else None
    def video_stream_url(self):
        urlresources = [ur for ur in self.urlresource_set.all() if ur.name_id in ['meetecho']]
        return urlresources[0].url if urlresources else None
    def webex_url(self):
        urlresources = [ur for ur in self.urlresource_set.all() if ur.name_id in ['webex']]
        return urlresources[0].url if urlresources else None
    #
    class Meta:
        ordering = ["-id"]


class UrlResource(models.Model):
    "For things like audio stream urls, meetecho stream urls"
    name    = ForeignKey(RoomResourceName)
    room    = ForeignKey(Room)
    url     = models.URLField(null=True, blank=True)

def floorplan_path(instance, filename):
    root, ext = os.path.splitext(filename)
    return "%s/floorplan-%s-%s%s" % (settings.FLOORPLAN_MEDIA_DIR, instance.meeting.number, xslugify(instance.name), ext)

class FloorPlan(models.Model):
    name    = models.CharField(max_length=255)
    short   = models.CharField(max_length=3, default='')
    modified= models.DateTimeField(auto_now=True)
    meeting = ForeignKey(Meeting)
    order   = models.SmallIntegerField()
    image   = models.ImageField(storage=NoLocationMigrationFileSystemStorage(), upload_to=floorplan_path, blank=True, default=None)
    #
    class Meta:
        ordering = ['-id',]
    #
    def __str__(self):
        return u'floorplan-%s-%s' % (self.meeting.number, xslugify(self.name))

# === Schedules, Sessions, Timeslots and Assignments ===========================

class TimeSlot(models.Model):
    """
    Everything that would appear on the meeting agenda of a meeting is
    mapped to a time slot, including breaks. Sessions are connected to
    TimeSlots during scheduling.
    """
    meeting = ForeignKey(Meeting)
    type = ForeignKey(TimeSlotTypeName)
    name = models.CharField(max_length=255)
    time = models.DateTimeField()
    duration = models.DurationField(default=datetime.timedelta(0))
    location = ForeignKey(Room, blank=True, null=True)
    show_location = models.BooleanField(default=True, help_text="Show location in agenda.")
    sessions = models.ManyToManyField('Session', related_name='slots', through='SchedTimeSessAssignment', blank=True, help_text="Scheduled session, if any.")
    modified = models.DateTimeField(auto_now=True)
    #

    @property
    def session(self):
        if not hasattr(self, "_session_cache"):
            self._session_cache = self.sessions.filter(timeslotassignments__schedule__in=[self.meeting.schedule, self.meeting.schedule.base if self.meeting else None]).first()
        return self._session_cache

    @property
    def time_desc(self):
        return "%s-%s" % (self.time.strftime("%H%M"), (self.time + self.duration).strftime("%H%M"))

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

    def __str__(self):
        location = self.get_location()
        if not location:
            location = u"(no location)"

        return u"%s: %s-%s %s, %s" % (self.meeting.number, self.time.strftime("%m-%d %H:%M"), (self.time + self.duration).strftime("%H:%M"), self.name, location)

    def end_time(self):
        return self.time + self.duration

    def get_hidden_location(self):
        if not hasattr(self, '_cached_hidden_location'):
            location = self.location
            if location:
                location = location.name
            elif self.type_id == "reg":
                location = self.meeting.reg_area
            elif self.type_id == "break":
                location = self.meeting.break_area
            self._cached_hidden_location = location
        return self._cached_hidden_location

    def get_location(self):
        return self.get_hidden_location() if self.show_location else ""

    def get_functional_location(self):
        name_parts = []
        room = self.location
        if room and room.functional_name:
            name_parts.append(room.functional_name)
        location = self.get_hidden_location()
        if location:
            name_parts.append(location)
        return ' - '.join(name_parts)

    def get_html_location(self):
        if not hasattr(self, '_cached_html_location'):
            self._cached_html_location = self.get_location()
            if len(self._cached_html_location) > 8:
                self._cached_html_location = mark_safe(self._cached_html_location.replace('/', '/<wbr>'))
            else:
                self._cached_html_location = mark_safe(self._cached_html_location.replace(' ', '&nbsp;'))
        return self._cached_html_location

    def tz(self):
        if not hasattr(self, '_cached_tz'):
            if self.meeting.time_zone:
                self._cached_tz = pytz.timezone(self.meeting.time_zone)
            else:
                self._cached_tz = None
        return self._cached_tz

    def tzname(self):
        if self.tz():
            return self.tz().tzname(self.time)
        else:
            return ""
    def utc_start_time(self):
        if self.tz():
            local_start_time = self.tz().localize(self.time)
            return local_start_time.astimezone(pytz.utc)
        else:
            return None
    def utc_end_time(self):
        if self.tz():
            local_end_time = self.tz().localize(self.end_time())
            return local_end_time.astimezone(pytz.utc)
        else:
            return None
    def local_start_time(self):
        if self.tz():
            local_start_time = self.tz().localize(self.time)
            return local_start_time
        else:
            return None
    def local_end_time(self):
        if self.tz():
            local_end_time = self.tz().localize(self.end_time())
            return local_end_time
        else:
            return None

    @property
    def js_identifier(self):
        # this returns a unique identifier that is js happy.
        #  {{s.timeslot.time|date:'Y-m-d'}}_{{ s.timeslot.time|date:'Hi' }}"
        # also must match:
        #  {{r|slugify}}_{{day}}_{{slot.0|date:'Hi'}}
        dom_id="ts%u" % (self.pk)
        if self.location is not None:
            dom_id = self.location.dom_id()
        return "%s_%s_%s" % (dom_id, self.time.strftime('%Y-%m-%d'), self.time.strftime('%H%M'))

    def json_dict(self, host_scheme):
        ts = dict()
        ts['timeslot_id'] = self.id
        ts['href']        = urljoin(host_scheme, self.json_url())
        ts['room']        = self.get_location()
        ts['roomtype'] = self.type.slug
        if self.location is not None:
            ts['capacity'] = self.location.capacity
        ts["time"]     = date_format(self.time, 'Hi')
        ts["date"]     = fmt_date(self.time)
        ts["domid"]    = self.js_identifier
        following = self.slot_to_the_right
        if following is not None:
            ts["following_timeslot_id"] = following.id
        return ts

    def json_url(self):
        return "/meeting/%s/timeslot/%s.json" % (self.meeting.number, self.id)

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
            ts.sessionassignments.all().delete()
            ts.delete()

    """
    Find a timeslot that comes next, in the same room.   It must be on the same day,
    and it must have a gap of less than 11 minutes. (10 is the spec)
    """
    @property
    def slot_to_the_right(self):
        return self.meeting.timeslot_set.filter(
            location = self.location,       # same room!
            type     = self.type,           # must be same type (usually session)
            time__gt = self.time + self.duration,  # must be after this session
            time__lt = self.time + self.duration + datetime.timedelta(seconds=11*60)).first()

    class Meta:
        ordering = ["-time", "-id"]
        indexes = [
            models.Index(fields=['-time', '-id']),
        ]


# end of TimeSlot

class Schedule(models.Model):
    """
    Each person may have multiple schedules saved.
    A Schedule may be made visible, which means that it will show up in
    public drop down menus, etc.  It may also be made public, which means
    that someone who knows about it by name/id would be able to reference
    it.  A non-visible, public schedule might be passed around by the
    Secretariat to IESG members for review.  Only the owner may edit the
    schedule, others may copy it
    """
    meeting  = ForeignKey(Meeting, null=True, related_name='schedule_set')
    name     = models.CharField(max_length=64, blank=False, help_text="Letters, numbers and -:_ allowed.", validators=[RegexValidator(r'^[A-Za-z0-9-:_]*$')])
    owner    = ForeignKey(Person)
    visible  = models.BooleanField("Show in agenda list", default=True, help_text="Show in the list of possible agendas for the meeting.")
    public   = models.BooleanField(default=True, help_text="Allow others to see this agenda.")
    badness  = models.IntegerField(null=True, blank=True)
    notes    = models.TextField(blank=True)
    origin   = ForeignKey('Schedule', blank=True, null=True, on_delete=models.SET_NULL, related_name="+")
    base     = ForeignKey('Schedule', blank=True, null=True, on_delete=models.SET_NULL,
                          help_text="Sessions scheduled in the base schedule show up in this schedule too.", related_name="derivedschedule_set",
                          limit_choices_to={'base': None}) # prevent the inheritance from being more than one layer deep (no recursion)

    def __str__(self):
        return u"%s:%s(%s)" % (self.meeting, self.name, self.owner)

    def base_url(self):
        return "/meeting/%s/agenda/%s/%s" % (self.meeting.number, self.owner_email(), self.name)

    # temporary property to pacify the places where Schedule.assignments is used
#    @property
#    def schedtimesessassignment_set(self):
#        return self.assignments
# 
#     def url_edit(self):
#         return "/meeting/%s/agenda/%s/edit" % (self.meeting.number, self.name)
#
#     @property
#     def relurl_edit(self):
#         return self.url_edit("")

    def owner_email(self):
        email = self.owner.email_set.all().order_by('primary').first()
        if email:
            return email.address
        else:
            return "noemail"

    @property
    def is_official(self):
        return (self.meeting.schedule == self)

    @property
    def is_official_record(self):
        return (self.is_official and
                self.meeting.end_date() <= datetime.date.today() )

    # returns a dictionary {group -> [schedtimesessassignment+]}
    # and it has [] if the session is not placed.
    # if there is more than one session for that group,
    # then a list of them is returned (always a list)
    @property
    def official_token(self):
        if self.is_official:
            return "official"
        else:
            return "unofficial"

    def delete_assignments(self):
        self.assignments.all().delete()

    def json_url(self):
        return "%s.json" % self.base_url()

    def json_dict(self, host_scheme):
        sch = dict()
        sch['schedule_id'] = self.id
        sch['href']        = urljoin(host_scheme, self.json_url())
        if self.visible:
            sch['visible']  = "visible"
        else:
            sch['visible']  = "hidden"
        if self.public:
            sch['public']   = "public"
        else:
            sch['public']   = "private"
        sch['owner']       = urljoin(host_scheme, self.owner.json_url())
        # should include href to list of assignments, but they have no direct API yet.
        return sch

    @property
    def qs_assignments_with_sessions(self):
        return self.assignments.filter(session__isnull=False)

    def qs_timeslots_in_use(self):
        """Get QuerySet containing timeslots used by the schedule"""
        return TimeSlot.objects.filter(sessionassignments__schedule=self)

    def qs_sessions_scheduled(self):
        """Get QuerySet containing sessions assigned to timeslots by this schedule"""
        return Session.objects.filter(timeslotassignments__schedule=self)

    def delete_schedule(self):
        self.assignments.all().delete()
        self.delete()

# to be renamed SchedTimeSessAssignments (stsa)
class SchedTimeSessAssignment(models.Model):
    """
    This model provides an N:M relationship between Session and TimeSlot.
    Each relationship is attached to the named schedule, which is owned by
    a specific person/user.
    """
    timeslot = ForeignKey('TimeSlot', null=False, blank=False, related_name='sessionassignments')
    session  = ForeignKey('Session', null=True, default=None, related_name='timeslotassignments', help_text="Scheduled session.")
    schedule = ForeignKey('Schedule', null=False, blank=False, related_name='assignments')
    extendedfrom = ForeignKey('self', null=True, default=None, help_text="Timeslot this session is an extension of.")
    modified = models.DateTimeField(auto_now=True)
    notes    = models.TextField(blank=True)
    badness  = models.IntegerField(default=0, blank=True, null=True)
    pinned   = models.BooleanField(default=False, help_text="Do not move session during automatic placement.")

    class Meta:
        ordering = ["timeslot__time", "timeslot__type__slug", "session__group__parent__name", "session__group__acronym", "session__name", ]

    def __str__(self):
        return u"%s [%s<->%s]" % (self.schedule, self.session, self.timeslot)

    @property
    def room_name(self):
        return self.timeslot.location.name if self.timeslot and self.timeslot.location else None

    @property
    def acronym(self):
        if self.session and self.session.group:
            return self.session.group.acronym

    @property
    def slot_to_the_right(self):
        s = self.timeslot.slot_to_the_right
        if s:
            return self.schedule.assignments.filter(timeslot=s).first()
        else:
            return None

    def json_url(self):
        if not hasattr(self, '_cached_json_url'):
            self._cached_json_url =  "/meeting/%s/agenda/%s/%s/session/%u.json" % (
                                        self.schedule.meeting.number,
                                        self.schedule.owner_email(),
                                        self.schedule.name, self.id )
        return self._cached_json_url

    def json_dict(self, host_scheme):
        if not hasattr(self, '_cached_json_dict'):
            ss = dict()
            ss['assignment_id'] = self.id
            ss['href']          = urljoin(host_scheme, self.json_url())
            ss['timeslot_id'] = self.timeslot.id

            efset = self.session.timeslotassignments.filter(schedule=self.schedule).order_by("timeslot__time")
            if efset.count() > 1:
                # now we know that there is some work to do finding the extendedfrom_id.
                # loop through the list of items
                previous = None
                for efss in efset:
                    if efss.pk == self.pk:
                        extendedfrom = previous
                        break
                    previous = efss
                if extendedfrom is not None:
                    ss['extendedfrom_id']  = extendedfrom.id

            if self.session:
                ss['session_id']  = self.session.id
            ss["pinned"]   = self.pinned
            self._cached_json_dict = ss
        return self._cached_json_dict

    def slug(self):
        """Return sensible id string for session, e.g. suitable for use as HTML anchor."""
        components = []

        components.append(self.schedule.meeting.number)

        if not self.timeslot:
            components.append("unknown")

        if not self.session or not (getattr(self.session, "historic_group", None) or self.session.group):
            components.append("unknown")
        else:
            components.append(self.timeslot.time.strftime("%Y-%m-%d-%a-%H%M"))

            g = getattr(self.session, "historic_group", None) or self.session.group

            if self.timeslot.type_id in ('break', 'reg', 'other'):
                components.append(g.acronym)
                components.append(slugify(self.session.name))

            if self.timeslot.type_id in ('regular', 'plenary'):
                if self.timeslot.type_id == "plenary":
                    components.append("1plenary")
                else:
                    p = getattr(g, "historic_parent", None) or g.parent
                    if p and p.type_id in ("area", "irtf", 'ietf'):
                        components.append(p.acronym)

                components.append(g.acronym)

        return "-".join(components).lower()


class BusinessConstraint(models.Model):
    """
    Constraints on the scheduling that apply across all qualifying
    sessions in all meetings. Used by the ScheduleGenerator.
    """
    slug = models.CharField(max_length=32, primary_key=True)
    name = models.CharField(max_length=255)
    penalty = models.IntegerField(default=0, help_text="The penalty for violating this kind of constraint; for instance 10 (small penalty) or 10000 (large penalty)")

    
class Constraint(models.Model):
    """
    Specifies a constraint on the scheduling.
    These constraints apply to a specific group during a specific meeting.

    Available types are:
    - conflict/conflic2/conflic3: a conflict between source and target WG/session,
      with varying priority. The first is used for a chair conflict, the second for
      technology overlap, third for key person conflict
    - bethere: a constraint between source WG and a particular person
    - timerange: can not meet during these times
    - time_relation: preference for a time difference between sessions
    - wg_adjacent: request for source WG to be adjacent (directly before or after,
      no breaks, same room) the target WG
      
    """
    TIME_RELATION_CHOICES = (
        ('subsequent-days', 'Schedule the sessions on subsequent days'),
        ('one-day-seperation', 'Leave at least one free day in between the two sessions'),
    )
    meeting = ForeignKey(Meeting)
    source = ForeignKey(Group, related_name="constraint_source_set")
    target = ForeignKey(Group, related_name="constraint_target_set", null=True)
    person = ForeignKey(Person, null=True, blank=True)
    name   = ForeignKey(ConstraintName)
    time_relation = models.CharField(max_length=200, choices=TIME_RELATION_CHOICES, blank=True)
    timeranges = models.ManyToManyField(TimerangeName)

    active_status = None

    def __str__(self):
        return u"%s %s target=%s person=%s" % (self.source, self.name.name.lower(), self.target, self.person)

    def brief_display(self):
        if self.name.slug == "wg_adjacent":
            return "Adjacent with %s" % self.target.acronym
        elif self.name.slug == "time_relation":
            return self.get_time_relation_display()
        elif self.name.slug == "timerange":
            timeranges_str = ", ".join([t.desc for t in self.timeranges.all()])
            return "Can't meet %s" % timeranges_str
        elif self.target and self.person:
            return "%s ; %s" % (self.target.acronym, self.person)
        elif self.target and not self.person:
            return "%s " % (self.target.acronym)
        elif not self.target and self.person:
            return "%s " % (self.person)

    def json_url(self):
        return "/meeting/%s/constraint/%s.json" % (self.meeting.number, self.id)

    def json_dict(self, host_scheme):
        ct1 = dict()
        ct1['constraint_id'] = self.id
        ct1['href']          = urljoin(host_scheme, self.json_url())
        ct1['name']          = self.name.slug
        if self.person is not None:
            ct1['person_href'] = urljoin(host_scheme, self.person.json_url())
        if self.source is not None:
            ct1['source_href'] = urljoin(host_scheme, self.source.json_url())
        if self.target is not None:
            ct1['target_href'] = urljoin(host_scheme, self.target.json_url())
        ct1['meeting_href'] = urljoin(host_scheme, self.meeting.json_url())
        if self.time_relation:
            ct1['time_relation'] = self.time_relation
            ct1['time_relation_display'] = self.get_time_relation_display()
        if self.timeranges.count():
            ct1['timeranges_cant_meet'] = [t.slug for t in self.timeranges.all()]
            timeranges_str = ", ".join([t.desc for t in self.timeranges.all()])
            ct1['timeranges_display'] = "Can't meet %s" % timeranges_str
        return ct1


class SessionPresentation(models.Model):
    session = ForeignKey('Session')
    document = ForeignKey(Document)
    rev = models.CharField(verbose_name="revision", max_length=16, null=True, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = 'meeting_session_materials'
        ordering = ('order',)
        unique_together = (('session', 'document'),)

    def __str__(self):
        return u"%s -> %s-%s" % (self.session, self.document.name, self.rev)

constraint_cache_uses = 0
constraint_cache_initials = 0

class SessionQuerySet(models.QuerySet):
    def with_current_status(self):
        """Annotate session with its current status
        
        Adds current_status, containing the text representation of the status.
        """
        return self.annotate(
            # coalesce with '' to avoid nulls which give funny
            # results, e.g. .exclude(current_status='canceled') also
            # skips rows with null in them
            current_status=Coalesce(
                Subquery(
                    SchedulingEvent.objects.filter(
                        session=OuterRef('pk')
                    ).order_by(
                        '-time', '-id'
                    ).values('status')[:1]),
                Value(''), 
                output_field=TextField()),
        )

    def with_requested_by(self):
        """Annotate session with requested_by field
        
        Adds requested_by field - pk of the Person who made the request
        """
        return self.annotate(
            requested_by=Subquery(
                SchedulingEvent.objects.filter(
                    session=OuterRef('pk')
                ).order_by(
                    'time', 'id'
                ).values('by')[:1]),
        )

    def with_requested_time(self):
        """Annotate session with requested_time field"""
        return self.annotate(
            requested_time=Subquery(
                SchedulingEvent.objects.filter(
                    session=OuterRef('pk')
                ).order_by(
                    'time', 'id'
                ).values('time')[:1]),
        )

    def not_canceled(self):
        """Queryset containing all sessions not canceled
                
        Results annotated with current_status
        """
        return self.with_current_status().exclude(current_status__in=Session.CANCELED_STATUSES)

    def that_can_meet(self):
        """Queryset containing sessions that can meet
        
        Results annotated with current_status
        """
        return self.with_current_status().exclude(
            current_status__in=['notmeet', 'disappr', 'deleted', 'apprw']
        ).filter(
            type__slug='regular'
        )


class Session(models.Model):
    """Session records that a group should have a session on the
    meeting (time and location is stored in a TimeSlot) - if multiple
    timeslots are needed, multiple sessions will have to be created.
    Training sessions and similar are modeled by filling in a
    responsible group (e.g. Edu team) and filling in the name."""
    objects = SessionQuerySet.as_manager()  # sets default query manager
    meeting = ForeignKey(Meeting)
    name = models.CharField(blank=True, max_length=255, help_text="Name of session, in case the session has a purpose rather than just being a group meeting.")
    short = models.CharField(blank=True, max_length=32, help_text="Short version of 'name' above, for use in filenames.")
    type = ForeignKey(TimeSlotTypeName)
    group = ForeignKey(Group)    # The group type historically determined the session type.  BOFs also need to be added as a group. Note that not all meeting requests have a natural group to associate with.
    joint_with_groups = models.ManyToManyField(Group, related_name='sessions_joint_in',blank=True)
    attendees = models.IntegerField(null=True, blank=True)
    agenda_note = models.CharField(blank=True, max_length=255)
    requested_duration = models.DurationField(default=datetime.timedelta(0))
    comments = models.TextField(blank=True)
    scheduled = models.DateTimeField(null=True, blank=True)
    modified = models.DateTimeField(auto_now=True)
    remote_instructions = models.CharField(blank=True,max_length=1024)

    tombstone_for = models.ForeignKey('Session', blank=True, null=True, help_text="This session is the tombstone for a session that was rescheduled", on_delete=models.CASCADE)

    materials = models.ManyToManyField(Document, through=SessionPresentation, blank=True)
    resources = models.ManyToManyField(ResourceAssociation, blank=True)

    unique_constraints_dict = None

    CANCELED_STATUSES = ['canceled', 'canceledpa']
    
    # Should work on how materials are captured so that deleted things are no longer associated with the session
    # (We can keep the information about something being added to and removed from a session in the document's history)
    def get_material(self, material_type, only_one):
        if hasattr(self, "prefetched_active_materials"):
            l = [d for d in self.prefetched_active_materials if d.type_id == material_type]
            for d in l:
                d.meeting_related = lambda: True
        else:
            l = self.materials.filter(type=material_type).exclude(states__type=material_type, states__slug='deleted').order_by('sessionpresentation__order')

        if only_one:
            if l:
                return l[0]
            else:
                return None
        else:
            return l

    def agenda(self):
        if not hasattr(self, "_agenda_cache"):
            self._agenda_cache = self.get_material("agenda", only_one=True)
        return self._agenda_cache

    def minutes(self):
        if not hasattr(self, '_cached_minutes'):
            self._cached_minutes = self.get_material("minutes", only_one=True)
        return self._cached_minutes

    def recordings(self):
        return list(self.get_material("recording", only_one=False))

    def bluesheets(self):
        return list(self.get_material("bluesheets", only_one=False))

    def slides(self):
        if not hasattr(self, "_slides_cache"):
            self._slides_cache = list(self.get_material("slides", only_one=False))
        return self._slides_cache

    def drafts(self):
        return list(self.materials.filter(type='draft'))

    # The utilities below are used in the proceedings and materials
    # templates, and should be moved there - then we could also query
    # out the needed information in a few passes and speed up those
    # pages.
    def all_meeting_sessions_for_group(self):
        from ietf.meeting.utils import add_event_info_to_session_qs
        if self.group.features.has_meetings:
            if not hasattr(self, "_all_meeting_sessions_for_group_cache"):
                sessions = [s for s in add_event_info_to_session_qs(self.meeting.session_set.filter(group=self.group,type=self.type)) if s.official_timeslotassignment()]
                self._all_meeting_sessions_for_group_cache = sorted(sessions, key = lambda x: x.official_timeslotassignment().timeslot.time)
            return self._all_meeting_sessions_for_group_cache
        else:
            return [self]

    def order_in_meeting(self):
        if not hasattr(self, '_order_in_meeting'):
            session_list = self.all_meeting_sessions_for_group()
            self._order_in_meeting = session_list.index(self) + 1 if self in session_list else 0
        return self._order_in_meeting

    def all_meeting_sessions_cancelled(self):
        return set(s.current_status for s in self.all_meeting_sessions_for_group()) == {'canceled'}

    def all_meeting_recordings(self):
        recordings = [] # These are not sets because we need to preserve relative ordering or redo the ordering work later
        sessions = self.all_meeting_sessions_for_group()
        for session in sessions:
            recordings.extend([r for r in session.recordings() if r not in recordings])
        return recordings
            
    def all_meeting_bluesheets(self):
        bluesheets = []
        sessions = self.all_meeting_sessions_for_group()
        for session in sessions:
            bluesheets.extend([b for b in session.bluesheets() if b not in bluesheets])
        return bluesheets
            
    def all_meeting_drafts(self):
        drafts = []
        sessions = self.all_meeting_sessions_for_group()
        for session in sessions:
            drafts.extend([d for d in session.drafts() if d not in drafts])
        return drafts

    def all_meeting_agendas(self):
        agendas = []
        sessions = self.all_meeting_sessions_for_group()
        for session in sessions:
            agenda = session.agenda()
            if agenda and agenda not in agendas:
                agendas.append(agenda)
        return agendas
        
    def all_meeting_slides(self):
        slides = []
        sessions = self.all_meeting_sessions_for_group()
        for session in sessions:
            slides.extend([s for s in session.slides() if s not in slides])
        return slides

    def all_meeting_minutes(self):
        minutes = []
        sessions = self.all_meeting_sessions_for_group()
        for session in sessions:
            minutes_doc = session.minutes()
            if minutes_doc and minutes_doc not in minutes:
                minutes.append(minutes_doc)
        return minutes

    def can_manage_materials(self, user):
        return can_manage_materials(user,self.group)

    def is_material_submission_cutoff(self):
        return datetime.date.today() > self.meeting.get_submission_correction_date()
    
    def joint_with_groups_acronyms(self):
        return [group.acronym for group in self.joint_with_groups.all()]

    def __str__(self):
        if self.meeting.type_id == "interim":
            return self.meeting.number

        status_id = None
        if hasattr(self, 'current_status'):
            status_id = self.current_status
        elif self.pk is not None:
            latest_event = SchedulingEvent.objects.filter(session=self.pk).order_by('-time', '-id').first()
            if latest_event:
                status_id = latest_event.status_id

        if status_id in ('canceled','disappr','notmeet','deleted'):
            ss0name = "(%s)" % SessionStatusName.objects.get(slug=status_id).name
        else:
            ss0name = "(unscheduled)"
            ss = self.timeslotassignments.filter(schedule__in=[self.meeting.schedule, self.meeting.schedule.base if self.meeting.schedule else None]).order_by('timeslot__time')
            if ss:
                ss0name = ','.join(x.timeslot.time.strftime("%a-%H%M") for x in ss)
        return "%s: %s %s %s" % (self.meeting, self.group.acronym, self.name, ss0name)

    @property
    def short_name(self):
        if self.name:
            return self.name
        if self.short:
            return self.short
        if self.group:
            return self.group.acronym
        return "req#%u" % (id)

    @property
    def special_request_token(self):
        if self.comments is not None and len(self.comments)>0:
            return "*"
        else:
            return ""

    def docname_token(self):
        sess_mtg = Session.objects.filter(meeting=self.meeting, group=self.group).order_by('pk')
        index = list(sess_mtg).index(self)
        return 'sess%s' % (string.ascii_lowercase[index])

    def docname_token_only_for_multiple(self):
        sess_mtg = Session.objects.filter(meeting=self.meeting, group=self.group).order_by('pk')
        if len(list(sess_mtg)) > 1:
            index = list(sess_mtg).index(self)
            if index < 26:
                token = 'sess%s' % (string.ascii_lowercase[index])
            else:
                token = 'sess%s%s' % (string.ascii_lowercase[index//26],string.ascii_lowercase[index%26])
            return token
        return None
        
    def constraints(self):
        return Constraint.objects.filter(source=self.group, meeting=self.meeting).order_by('name__name', 'target__acronym', 'person__name').prefetch_related("source","target","person")

    def reverse_constraints(self):
        return Constraint.objects.filter(target=self.group, meeting=self.meeting).order_by('name__name')

    def official_timeslotassignment(self):
        return self.timeslotassignments.filter(schedule__in=[self.meeting.schedule, self.meeting.schedule.base if self.meeting.schedule else None]).first()

    def constraints_dict(self, host_scheme):
        constraint_list = []
        for constraint in self.constraints():
            ct1 = constraint.json_dict(host_scheme)
            constraint_list.append(ct1)

        for constraint in self.reverse_constraints():
            ct1 = constraint.json_dict(host_scheme)
            constraint_list.append(ct1)
        return constraint_list

    @property
    def people_constraints(self):
        return self.group.constraint_source_set.filter(meeting=self.meeting, name='bethere')

    def json_url(self):
        return "/meeting/%s/session/%s.json" % (self.meeting.number, self.id)

    def json_dict(self, host_scheme):
        sess1 = dict()
        sess1['href']           = urljoin(host_scheme, self.json_url())
        if self.group is not None:
            sess1['group']          = self.group.json_dict(host_scheme)
            sess1['group_href']     = urljoin(host_scheme, self.group.json_url())
            if self.group.parent is not None:
                sess1['area']           = self.group.parent.acronym.upper()
            sess1['description']    = self.group.name
            sess1['group_id']       = str(self.group.pk)
        reslist = []
        for r in self.resources.all():
            reslist.append(r.json_dict(host_scheme))
        sess1['resources']      = reslist
        sess1['session_id']     = str(self.pk)
        sess1['name']           = self.name
        sess1['title']          = self.short_name
        sess1['short_name']     = self.short_name
        sess1['bof']            = str(self.group.is_bof())
        sess1['agenda_note']    = self.agenda_note
        sess1['attendees']      = str(self.attendees)
        sess1['joint_with_groups'] = self.joint_with_groups_acronyms()

        # fish out scheduling information - eventually, we should pick
        # this out in the caller instead
        latest_event = None
        first_event = None

        if self.pk is not None:
            if not hasattr(self, 'current_status') or not hasattr(self, 'requested_time'):
                events = list(SchedulingEvent.objects.filter(session=self.pk).order_by('time', 'id'))
                if events:
                    first_event = events[0]
                    latest_event = events[-1]

        status_id = None
        if hasattr(self, 'current_status'):
            status_id = self.current_status
        elif latest_event:
            status_id = latest_event.status_id

        sess1['status']         = SessionStatusName.objects.get(slug=status_id).name if status_id else None
        if self.comments is not None:
            sess1['comments']       = self.comments

        requested_time = None
        if hasattr(self, 'requested_time'):
            requested_time = self.requested_time
        elif first_event:
            requested_time = first_event.time
        sess1['requested_time'] = requested_time.strftime("%Y-%m-%d") if requested_time else None


        requested_by = None
        if hasattr(self, 'requested_by'):
            requested_by = self.requested_by
        elif first_event:
            requested_by = first_event.by_id

        if requested_by is not None:
            requested_by_person = Person.objects.filter(pk=requested_by).first()
            if requested_by_person:
                sess1['requested_by']   = str(requested_by_person)

        sess1['requested_duration']= "%.1f" % (float(self.requested_duration.seconds) / 3600)
        sess1['special_request'] = str(self.special_request_token)
        return sess1

    def agenda_text(self):
        doc = self.agenda()
        if doc:
            path = os.path.join(settings.AGENDA_PATH, self.meeting.number, "agenda", doc.uploaded_filename)
            if os.path.exists(path):
                with io.open(path) as f:
                    return f.read()
            else:
                return "No agenda file found"
        else:
            return "The agenda has not been uploaded yet."

    def agenda_file(self):
        if not hasattr(self, '_agenda_file'):
            self._agenda_file = ""

            agenda = self.agenda()
            if not agenda:
                return ""

            # FIXME: uploaded_filename should be replaced with a function that computes filenames when they are of a fixed schema and not uploaded names
            self._agenda_file = "%s/agenda/%s" % (self.meeting.number, agenda.uploaded_filename)
            
        return self._agenda_file

    def jabber_room_name(self):
        if self.type_id=='plenary':
            return 'plenary'
        elif self.historic_group:
            return self.historic_group.acronym
        else:
            return self.group.acronym

class SchedulingEvent(models.Model):
    session = ForeignKey(Session)
    time = models.DateTimeField(default=datetime.datetime.now, help_text="When the event happened")
    status = ForeignKey(SessionStatusName)
    by = ForeignKey(Person)

    def __str__(self):
        return u'%s : %s : %s : %s' % (self.session, self.status, self.time, self.by)

class ImportantDate(models.Model):
    meeting = ForeignKey(Meeting)
    date = models.DateField()
    name = ForeignKey(ImportantDateName)
    class Meta:
        ordering = ["-meeting_id","date", ]

    def __str__(self):
        return u'%s : %s : %s' % ( self.meeting, self.name, self.date )

class SlideSubmission(models.Model):
    time = models.DateTimeField(auto_now=True)
    session = ForeignKey(Session)
    title = models.CharField(max_length=255)
    filename = models.CharField(max_length=255)
    apply_to_all = models.BooleanField(default=False)
    submitter = ForeignKey(Person)
    status      = ForeignKey(SlideSubmissionStatusName, null=True, default='pending', on_delete=models.SET_NULL)
    doc         = ForeignKey(Document, null=True, on_delete=models.SET_NULL)

    def staged_filepath(self):
        return os.path.join(settings.SLIDE_STAGING_PATH , self.filename)

    def staged_url(self):
        return "".join([settings.SLIDE_STAGING_URL, self.filename])


class ProceedingsMaterial(models.Model):
    meeting = ForeignKey(Meeting, related_name='proceedings_materials')
    document = ForeignKey(
        Document,
        limit_choices_to=dict(type_id='procmaterials'),
        unique=True,
    )
    type = ForeignKey(ProceedingsMaterialTypeName)

    class Meta:
        unique_together = (('meeting', 'type'),)

    def __str__(self):
        return self.document.title

    def get_href(self):
        return f'{self.document.get_href(self.meeting)}'

    def active(self):
        return self.document.get_state().slug == 'active'

    def is_url(self):
        return len(self.document.external_url) > 0

def _host_upload_path(instance : 'MeetingHost', filename):
    """Compute filename relative to the storage location

    Must live outside a class to allow migrations to deconstruct fields that use it
    """
    num = instance.meeting.number
    path = (
            Path(num) / 'meetinghosts' / f'logo-{"".join(random.choices(string.ascii_lowercase, k=10))}'
    ).with_suffix(
        Path(filename).suffix
    )
    return str(path)


class MeetingHost(models.Model):
    """Meeting sponsor"""
    meeting = ForeignKey(Meeting, related_name='meetinghosts')
    name = models.CharField(max_length=255, blank=False)
    logo = MissingOkImageField(
        storage=NoLocationMigrationFileSystemStorage(location=settings.MEETINGHOST_LOGO_PATH),
        upload_to=_host_upload_path,
        width_field='logo_width',
        height_field='logo_height',
        blank=False,
        validators=[
            MaxImageSizeValidator(
                settings.MEETINGHOST_LOGO_MAX_UPLOAD_WIDTH,
                settings.MEETINGHOST_LOGO_MAX_UPLOAD_HEIGHT,
            ),
            WrappedValidator(validate_file_size, True),
            WrappedValidator(
                validate_file_extension,
                settings.MEETING_VALID_UPLOAD_EXTENSIONS['meetinghostlogo'],
            ),
            WrappedValidator(
                validate_mime_type,
                settings.MEETING_VALID_UPLOAD_MIME_TYPES['meetinghostlogo'],
                True,
            ),
        ],
    )
    # These are filled in by the ImageField allow retrieval of image dimensions
    # without processing the image each time it's loaded.
    logo_width = models.PositiveIntegerField(null=True)
    logo_height = models.PositiveIntegerField(null=True)

    class Meta:
        unique_together = (('meeting', 'name'),)
        ordering = ('pk',)
