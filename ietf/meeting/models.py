# Copyright The IETF Trust 2007-2024, All Rights Reserved
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
from django.urls import reverse as urlreverse
from django.utils import timezone
from django.utils.text import slugify

from ietf.dbtemplate.models import DBTemplate
from ietf.doc.models import Document
from ietf.group.models import Group
from ietf.group.utils import can_manage_materials
from ietf.name.models import (
    MeetingTypeName, TimeSlotTypeName, SessionStatusName, ConstraintName, RoomResourceName,
    ImportantDateName, TimerangeName, SlideSubmissionStatusName, ProceedingsMaterialTypeName,
    SessionPurposeName,
)
from ietf.person.models import Person
from ietf.utils.decorators import memoize
from ietf.utils.history import find_history_replacements_active_at, find_history_active_at
from ietf.utils.storage import NoLocationMigrationFileSystemStorage
from ietf.utils.text import xslugify
from ietf.utils.timezone import datetime_from_date, date_today
from ietf.utils.models import ForeignKey
from ietf.utils.validators import (
    MaxImageSizeValidator, WrappedValidator, validate_file_size, validate_mime_type,
    validate_file_extension,
)
from ietf.utils.fields import MissingOkImageField

countries = list(pytz.country_names.items())
countries.sort(key=lambda x: x[1])

timezones = []
for name in pytz.common_timezones:
    tzfn = os.path.join(settings.TZDATA_ICS_PATH, name + ".ics")
    if not os.path.islink(tzfn):
        timezones.append((name, name))
timezones.sort()


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
    time_zone = models.CharField(max_length=255, choices=timezones, default='UTC')
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

    def start_datetime(self):
        """Start-of-day on meeting.date in meeting time zone"""
        return datetime_from_date(self.date, self.tz())

    def end_datetime(self):
        """Datetime of the first instant _after_ the meeting's last day in meeting time zone"""
        return datetime_from_date(self.get_meeting_date(self.days), self.tz())

    def get_00_cutoff(self):
        """Get the I-D submission 00 cutoff in UTC"""
        importantdate = self.importantdate_set.filter(name_id='idcutoff').first()
        if not importantdate:
            importantdate = self.importantdate_set.filter(name_id='00cutoff').first()
        if importantdate:
            cutoff_date = importantdate.date
        else:
            cutoff_date = self.date + datetime.timedelta(days=ImportantDateName.objects.get(slug='idcutoff').default_offset_days)
        cutoff_time = datetime_from_date(cutoff_date, datetime.timezone.utc) + self.idsubmit_cutoff_time_utc
        return cutoff_time

    def get_01_cutoff(self):
        """Get the I-D submission 01 cutoff in UTC"""
        importantdate = self.importantdate_set.filter(name_id='idcutoff').first()
        if not importantdate:
            importantdate = self.importantdate_set.filter(name_id='01cutoff').first()
        if importantdate:
            cutoff_date = importantdate.date
        else:
            cutoff_date = self.date + datetime.timedelta(days=ImportantDateName.objects.get(slug='idcutoff').default_offset_days)
        cutoff_time = datetime_from_date(cutoff_date, datetime.timezone.utc) + self.idsubmit_cutoff_time_utc
        return cutoff_time

    def get_reopen_time(self):
        """Get the I-D submission reopening time in meeting-local time"""
        cutoff = self.get_00_cutoff()
        if cutoff.date() == self.date:
            # no cutoff, so no local-time re-open
            reopen_time = cutoff
        else:
            # reopen time is in local timezone.  May need policy change??  XXX
            reopen_time = datetime_from_date(self.date, self.tz()) + self.idsubmit_cutoff_time_utc
        return reopen_time

    @classmethod
    def get_current_meeting(cls, type="ietf"):
        return cls.objects.filter(type=type, date__gte=timezone.now()-datetime.timedelta(days=7) ).order_by('date').first()

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
        Attendance = namedtuple('Attendance', 'onsite remote')

        # MeetingRegistration.attended started conflating badge-pickup and session attendance before IETF 114.
        # We've separated session attendance off to ietf.meeting.Attended, but need to report attendance at older
        # meetings correctly.

        attended_per_meetingregistration = (
            Q(meetingregistration__meeting=self) & (
                Q(meetingregistration__attended=True) |
                Q(meetingregistration__checkedin=True)
            )
        )
        attended_per_meeting_attended = (
            Q(attended__session__meeting=self)
            # Note that we are not filtering to plenary, wg, or rg sessions
            # as we do for nomcom eligibility - if picking up a badge (see above)
            # is good enough, just attending e.g. a training session is also good enough
        )
        attended = Person.objects.filter(
            attended_per_meetingregistration | attended_per_meeting_attended
        ).distinct()

        onsite=set(attended.filter(meetingregistration__meeting=self, meetingregistration__reg_type='onsite'))
        remote=set(attended.filter(meetingregistration__meeting=self, meetingregistration__reg_type='remote'))
        remote.difference_update(onsite)

        return Attendance(
            onsite=len(onsite),
            remote=len(remote)
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
                # Find the index of the first entry in the version change array that
                # is >= this meeting's number. The first entry in the array is 0, so the
                # version is always >= 1 for positive meeting numbers.
                for vers, threshold in enumerate(settings.PROCEEDINGS_VERSION_CHANGES):
                    if mtg_number < threshold:
                        version = vers
                        break
            self._proceedings_format_version = version  # save this for later
        return self._proceedings_format_version

    def base_url(self):
        return "/meeting/%s" % (self.number, )

    def build_timeslices(self):
        """Get unique day/time/timeslot data for meeting
        
        Returns a list of days, time intervals for each day, and timeslots for each day,
        with repeated days/time intervals removed. Ignores timeslots that do not have a
        location. The slots return value contains only one TimeSlot for each distinct
        time interval.
        """
        days = []          # the days of the meetings
        time_slices = {}   # the times on each day
        slots = {}

        for ts in self.timeslot_set.all():
            if ts.location_id is None:
                continue
            ymd = ts.local_start_time().date()
            if ymd not in time_slices:
                time_slices[ymd] = []
                slots[ymd] = []
                days.append(ymd)

            if ymd in time_slices:
                # only keep unique entries
                if [ts.local_start_time(), ts.local_end_time(), ts.duration.seconds] not in time_slices[ymd]:
                    time_slices[ymd].append([ts.local_start_time(), ts.local_end_time(), ts.duration.seconds])
                    slots[ymd].append(ts)

        days.sort()
        for ymd in time_slices:
            # Make sure these sort the same way
            time_slices[ymd].sort()
            slots[ymd].sort(key=lambda x: (x.local_start_time(), x.duration))
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

    def tz(self):
        if not hasattr(self, '_cached_tz'):
            self._cached_tz = pytz.timezone(self.time_zone)
        return self._cached_tz

    def vtimezone(self):
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
        return None


    def updated(self):
        # should be Meeting.modified, but we don't have that
        timeslots_updated = self.timeslot_set.aggregate(Max('modified'))["modified__max"]
        sessions_updated = self.session_set.aggregate(Max('modified'))["modified__max"]
        assignments_updated = None
        if self.schedule:
            assignments_updated = SchedTimeSessAssignment.objects.filter(schedule__in=[self.schedule, self.schedule.base if self.schedule else None]).aggregate(Max('modified'))["modified__max"]
        dts = [timeslots_updated, sessions_updated, assignments_updated]
        valid_only = [dt for dt in dts if dt is not None]
        return max(valid_only) if valid_only else None

    @memoize
    def previous_meeting(self):
        return Meeting.objects.filter(type_id=self.type_id,date__lt=self.date).order_by('-date').first()

    def uses_notes(self):
        if self.type_id != 'ietf':
            return True
        num = self.get_number()
        return num is not None and num >= 108

    def has_recordings(self):
        if self.type_id != 'ietf':
            return True
        num = self.get_number()
        return num is not None and num >= 80

    def has_chat_logs(self):
        if self.type_id != 'ietf':
            return True;
        num = self.get_number()
        return num is not None and num >= 60

    def meeting_start(self):
        """Meeting-local midnight at the start of the meeting date"""
        return self.tz().localize(datetime.datetime.combine(self.date, datetime.time()))

    def _groups_at_the_time(self):
        """Get dict mapping Group PK to appropriate Group or GroupHistory at meeting time

        Known issue: only looks up Groups and their *current* parents when called. If a Group's
        parent was different at meeting time, that parent will not be in the cache. Use
        group_at_the_time() to look up values - that will fill in missing groups for you.
        """
        if not hasattr(self,'cached_groups_at_the_time'):
            all_group_pks = set(self.session_set.values_list('group__pk', flat=True))
            all_group_pks.update(self.session_set.values_list('group__parent__pk', flat=True))
            all_group_pks.discard(None)
            self.cached_groups_at_the_time = find_history_replacements_active_at(
                Group.objects.filter(pk__in=all_group_pks),
                self.meeting_start(),
            )
        return self.cached_groups_at_the_time

    def group_at_the_time(self, group):
        # MUST call self._groups_at_the_time() before assuming cached_groups_at_the_time exists
        gatt = self._groups_at_the_time()
        if group.pk in gatt:
            return gatt[group.pk]
        # Cache miss - look up the missing historical group and add it to the cache.
        new_item = find_history_active_at(group, self.meeting_start()) or group  # fall back to original if no history
        self.cached_groups_at_the_time[group.pk] = new_item
        return new_item

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
        if len(self.functional_name) > 0 and self.functional_name != self.name:
            return f"{self.name} [{self.functional_name}] (size: {self.capacity})"    
        return f"{self.name} (size: {self.capacity})"    

    def dom_id(self):
        return "room%u" % (self.pk)

    # floorplan support
    def floorplan_url(self):
        mtg_num = self.meeting.get_number()
        if not mtg_num:
            return None
        elif self.floorplan:
            base_url = urlreverse('floor-plan', kwargs=dict(num=mtg_num))
        else:
            return None
        return f'{base_url}?room={xslugify(self.name)}'

    def left(self):
        return min(self.x1, self.x2) if (self.x1 and self.x2) else 0
    def top(self):
        return min(self.y1, self.y2) if (self.y1 and self.y2) else 0
    def right(self):
        return max(self.x1, self.x2) if (self.x1 and self.x2) else 0
    def bottom(self):
        return max(self.y1, self.y2) if (self.y1 and self.y2) else 0
    # audio stream support
    def audio_stream_url(self):
        urlresources = [ur for ur in self.urlresource_set.all() if ur.name_id == 'audiostream']
        return urlresources[0].url if urlresources else None
    def video_stream_url(self):
        urlresources = [ur for ur in self.urlresource_set.all() if ur.name_id in ['meetecho']]
        return urlresources[0].url if urlresources else None
    def onsite_tool_url(self):
        urlresources = [ur for ur in self.urlresource_set.all() if ur.name_id in ['meetecho_onsite']]
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

class TimeSlotQuerySet(models.QuerySet):
    def that_can_be_scheduled(self):
        return self.exclude(type__in=TimeSlot.TYPES_NOT_SCHEDULABLE)


class TimeSlot(models.Model):
    """
    Everything that would appear on the meeting agenda of a meeting is
    mapped to a timeslot, including breaks. Sessions are connected to
    TimeSlots during scheduling.
    """
    objects = TimeSlotQuerySet.as_manager()

    meeting = ForeignKey(Meeting)
    type = ForeignKey(TimeSlotTypeName)
    name = models.CharField(max_length=255)
    time = models.DateTimeField()
    duration = models.DurationField(default=datetime.timedelta(0))
    location = ForeignKey(Room, blank=True, null=True)
    show_location = models.BooleanField(default=True, help_text="Show location in agenda.")
    sessions = models.ManyToManyField('meeting.Session', related_name='slots', through='meeting.SchedTimeSessAssignment', blank=True, help_text="Scheduled session, if any.")
    modified = models.DateTimeField(auto_now=True)
    #

    TYPES_NOT_SCHEDULABLE = ('offagenda', 'reserved', 'unavail')

    @property
    def session(self):
        if not hasattr(self, "_session_cache"):
            self._session_cache = self.sessions.filter(timeslotassignments__schedule__in=[self.meeting.schedule, self.meeting.schedule.base if self.meeting else None]).first()
        return self._session_cache

    # Unused
    #
    # def meeting_date(self):
    #     return self.time.date()

    # Unused
    #
    # def registration(self):
    #     # below implements a object local cache
    #     # it tries to find a timeslot of type registration which starts at the same time as this slot
    #     # so that it can be shown at the top of the agenda.
    #     if not hasattr(self, '_reg_info'):
    #         try:
    #             self._reg_info = TimeSlot.objects.get(meeting=self.meeting, time__month=self.time.month, time__day=self.time.day, type="reg")
    #         except TimeSlot.DoesNotExist:
    #             self._reg_info = None
    #     return self._reg_info

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

    # Unused
    #
    # def get_functional_location(self):
    #     name_parts = []
    #     room = self.location
    #     if room and room.functional_name:
    #         name_parts.append(room.functional_name)
    #     location = self.get_hidden_location()
    #     if location:
    #         name_parts.append(location)
    #     return ' - '.join(name_parts)

    # def get_html_location(self):
    #     if not hasattr(self, '_cached_html_location'):
    #         self._cached_html_location = self.get_location()
    #         if len(self._cached_html_location) > 8:
    #             self._cached_html_location = mark_safe(self._cached_html_location.replace('/', '/<wbr>'))
    #         else:
    #             self._cached_html_location = mark_safe(self._cached_html_location.replace(' ', '&nbsp;'))
    #     return self._cached_html_location

    def tz(self):
        return self.meeting.tz()

    # Unused
    # def tzname(self):
    #     return self.tz().tzname(self.time)

    def utc_start_time(self):
        return self.time.astimezone(pytz.utc)  # USE_TZ is True, so time is aware

    def utc_end_time(self):
        return self.time.astimezone(pytz.utc) + self.duration  # USE_TZ is True, so time is aware

    def local_start_time(self):
        return self.time.astimezone(self.tz())

    def local_end_time(self):
        return (self.time.astimezone(pytz.utc) + self.duration).astimezone(self.tz())

    # Unused
    #
    # @property
    # def js_identifier(self):
    #     # this returns a unique identifier that is js happy.
    #     #  {{s.timeslot.time|date:'Y-m-d'}}_{{ s.timeslot.time|date:'Hi' }}"
    #     # also must match:
    #     #  {{r|slugify}}_{{day}}_{{slot.0|date:'Hi'}}
    #     dom_id="ts%u" % (self.pk)
    #     if self.location is not None:
    #         dom_id = self.location.dom_id()
    #     return "%s_%s_%s" % (dom_id, self.time.strftime('%Y-%m-%d'), self.time.strftime('%H%M'))

    # def delete_concurrent_timeslots(self):
    #     """Delete all timeslots which are in the same time as this slot"""
    #     # can not include duration in filter, because there is no support
    #     # for having it a WHERE clause.
    #     # below will delete self as well.
    #     for ts in self.meeting.timeslot_set.filter(time=self.time).all():
    #         if ts.duration!=self.duration:
    #             continue

    #         # now remove any schedule that might have been made to this
    #         # timeslot.
    #         ts.sessionassignments.all().delete()
    #         ts.delete()

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
        return self.owner.email_address() or "noemail"

    @property
    def is_official(self):
        return (self.meeting.schedule == self)

    @property
    def is_official_record(self):
        return (self.is_official and
                self.meeting.end_date() <= date_today() )

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

    @property
    def qs_assignments_with_sessions(self):
        return self.assignments.filter(session__isnull=False)

    def qs_timeslots_in_use(self):
        """Get QuerySet containing timeslots used by the schedule"""
        return TimeSlot.objects.filter(sessionassignments__schedule=self)

    def qs_sessions_scheduled(self):
        """Get QuerySet containing sessions assigned to timeslots by this schedule"""
        return Session.objects.filter(timeslotassignments__schedule=self)

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

    def meeting(self):
        """Get the meeting to which this assignment belongs"""
        return self.session.meeting

    def slot_type(self):
        """Get the TimeSlotTypeName that applies to this assignment"""
        return self.timeslot.type

    def slug(self):
        """Return sensible id string for session, e.g. suitable for use as HTML anchor."""
        components = []

        components.append(self.schedule.meeting.number)

        if not self.timeslot:
            components.append("unknown")

        if not self.session or not self.session.group_at_the_time():
            components.append("unknown")
        else:
            components.append(self.timeslot.time.strftime("%Y-%m-%d-%a-%H%M"))

            g = self.session.group_at_the_time()

            if self.timeslot.type.slug in ('break', 'reg', 'other'):
                components.append(g.acronym)
                components.append(slugify(self.session.name))

            if self.timeslot.type.slug in ('regular', 'plenary'):
                if self.timeslot.type.slug == "plenary":
                    components.append("1plenary")
                else:
                    p = self.session.group_parent_at_the_time()
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

    In the schedule editor, run-time, a couple non-persistent ConstraintName instances
    are created for rendering purposes. This is done in
    meeting.utils.preprocess_constraints_for_meeting_schedule_editor(). This adds:
    - joint_with_groups
    - responsible_ad
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


class SessionPresentation(models.Model):
    session = ForeignKey('Session', related_name="presentations")
    document = ForeignKey(Document, related_name="presentations")
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

    def not_deleted(self):
        """Queryset containing all sessions not deleted

        Results annotated with current_status
        """
        return self.with_current_status().exclude(current_status='deleted')

    def that_can_meet(self):
        """Queryset containing sessions that can meet
        
        Results annotated with current_status
        """
        return self.with_current_status().exclude(
            current_status__in=['notmeet', 'disappr', 'deleted', 'apprw']
        ).filter(
            type__slug='regular'
        )

    def that_can_be_scheduled(self):
        """Queryset containing sessions that should be scheduled for a meeting"""
        return self.requests().with_current_status().filter(
            current_status__in=['appr', 'schedw', 'scheda', 'sched']
        )

    def requests(self):
        """Queryset containing sessions that may be handled as requests"""
        return self.exclude(type__in=TimeSlot.TYPES_NOT_SCHEDULABLE)


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
    purpose = ForeignKey(SessionPurposeName, null=False, help_text='Purpose of the session')
    type = ForeignKey(TimeSlotTypeName)
    group = ForeignKey(Group)    # The group type historically determined the session type.  BOFs also need to be added as a group. Note that not all meeting requests have a natural group to associate with.
    joint_with_groups = models.ManyToManyField(Group, related_name='sessions_joint_in',blank=True)
    attendees = models.IntegerField(null=True, blank=True)
    agenda_note = models.CharField(blank=True, max_length=512)
    requested_duration = models.DurationField(default=datetime.timedelta(0))
    comments = models.TextField(blank=True)
    scheduled = models.DateTimeField(null=True, blank=True)
    modified = models.DateTimeField(auto_now=True)
    remote_instructions = models.CharField(blank=True,max_length=1024)
    on_agenda = models.BooleanField(default=True, help_text='Is this session visible on the meeting agenda?')
    has_onsite_tool = models.BooleanField(default=False, help_text="Does this session use the officially supported onsite and remote tooling?")
    chat_room = models.CharField(blank=True, max_length=32, help_text='Name of Zulip stream, if different from group acronym')
    meetecho_recording_name = models.CharField(blank=True, max_length=64, help_text="Name of the meetecho recording")

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
            l = self.materials.filter(type=material_type).exclude(states__type=material_type, states__slug='deleted').order_by('presentations__order')

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

    def narrative_minutes(self):
        if not hasattr(self, '_cached_narrative_minutes'):
            self._cached_minutes = self.get_material("narrativeminutes", only_one=True)
        return self._cached_minutes

    def recordings(self):
        return list(self.get_material("recording", only_one=False))

    def bluesheets(self):
        return list(self.get_material("bluesheets", only_one=False))

    def chatlogs(self):
        return list(self.get_material("chatlog", only_one=False))

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
                sessions = [s for s in add_event_info_to_session_qs(self.meeting.session_set.filter(group=self.group)) if s.official_timeslotassignment()]
                for s in sessions:
                    s.ota = s.official_timeslotassignment()
                # Align this sort with SchedTimeSessAssignment default sort order since many views base their order on that
                self._all_meeting_sessions_for_group_cache = sorted(
                    sessions, key = lambda x: (
                        x.ota.timeslot.time,
                        x.ota.timeslot.type.slug,
                        x.ota.session.group.parent.name if x.ota.session.group.parent else None,
                        x.ota.session.name
                    )
                )
            return self._all_meeting_sessions_for_group_cache
        else:
            return [self]

    def order_in_meeting(self):
        if not hasattr(self, '_order_in_meeting'):
            session_list = self.all_meeting_sessions_for_group()
            self._order_in_meeting = session_list.index(self) + 1 if self in session_list else 0
        return self._order_in_meeting

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
        return date_today(datetime.timezone.utc) > self.meeting.get_submission_correction_date()
    
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

    @staticmethod
    def _alpha_str(n: int):
        """Convert integer to string of a-z characters (a, b, c, ..., aa, ab, ...)"""
        chars = []
        while True:
            chars.append(string.ascii_lowercase[n % 26])
            n //= 26
            # for 2nd letter and beyond, 0 means end the string
            if n == 0:
                break
            # beyond the first letter, no need to represent a 0, so decrement
            n -= 1
        return "".join(chars[::-1])

    def docname_token(self):
        sess_mtg = Session.objects.filter(meeting=self.meeting, group=self.group).order_by('pk')
        index = list(sess_mtg).index(self)
        return f"sess{self._alpha_str(index)}"

    def docname_token_only_for_multiple(self):
        sess_mtg = Session.objects.filter(meeting=self.meeting, group=self.group).order_by('pk')
        if len(list(sess_mtg)) > 1:
            index = list(sess_mtg).index(self)
            token = f"sess{self._alpha_str(index)}"
            return token
        return None
        
    def constraints(self):
        return Constraint.objects.filter(source=self.group, meeting=self.meeting).order_by('name__name', 'target__acronym', 'person__name').prefetch_related("source","target","person")

    def reverse_constraints(self):
        return Constraint.objects.filter(target=self.group, meeting=self.meeting).order_by('name__name')

    def official_timeslotassignment(self):
        # cache only non-None values
        if getattr(self, "_cache_official_timeslotassignment", None) is None:
            self._cache_official_timeslotassignment = self.timeslotassignments.filter(schedule__in=[self.meeting.schedule, self.meeting.schedule.base if self.meeting.schedule else None]).first()
        return self._cache_official_timeslotassignment

    @property
    def people_constraints(self):
        return self.group.constraint_source_set.filter(meeting=self.meeting, name='bethere')

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

    def chat_room_name(self):
        if self.chat_room:
            return self.chat_room
        # At some point, add a migration to add "plenary" chat room name to existing sessions in the database.
        elif self.type_id=='plenary':
            return 'plenary'
        else:
            return self.group_at_the_time().acronym

    def chat_room_url(self):
        return settings.CHAT_URL_PATTERN.format(chat_room_name=self.chat_room_name())

    def chat_archive_url(self):

        if hasattr(self,"prefetched_active_materials"):
            chatlog_doc = None
            for doc in self.prefetched_active_materials:
                if doc.type_id=="chatlog":
                    chatlog_doc = doc
                    break
            if chatlog_doc is not None:
                return chatlog_doc.get_href()
        else:
            chatlog = self.presentations.filter(document__type__slug='chatlog').first()
            if chatlog is not None:
                return chatlog.document.get_href()
            
        if self.meeting.date <= datetime.date(2022, 7, 15):
            # datatracker 8.8.0 released on 2022 July 15; before that, fall back to old log URL
            return f'https://www.ietf.org/jabber/logs/{ self.chat_room_name() }?C=M;O=D'
        elif hasattr(settings,'CHAT_ARCHIVE_URL_PATTERN'):
            return settings.CHAT_ARCHIVE_URL_PATTERN.format(chat_room_name=self.chat_room_name())
        else:
            # Zulip has no separate archive
            return self.chat_room_url()

    def notes_id(self):
        note_id_fragment = 'plenary' if self.type.slug == 'plenary' else self.group.acronym
        return f'notes-ietf-{self.meeting.number}-{note_id_fragment}'

    def notes_url(self):
        return urljoin(settings.IETF_NOTES_URL, self.notes_id())


    def group_at_the_time(self):
        if not hasattr(self,"_cached_group_at_the_time"):
            self._cached_group_at_the_time = self.meeting.group_at_the_time(self.group)
        return self._cached_group_at_the_time

    def group_parent_at_the_time(self):
        if self.group_at_the_time().parent:
            return self.meeting.group_at_the_time(self.group_at_the_time().parent)

    def audio_stream_url(self):
        url = getattr(settings, "MEETECHO_AUDIO_STREAM_URL", "")
        if self.meeting.type.slug == "ietf" and self.has_onsite_tool and url:
            return url.format(session=self)
        return None

    def video_stream_url(self):
        url = getattr(settings, "MEETECHO_VIDEO_STREAM_URL", "")
        if self.meeting.type.slug == "ietf" and self.has_onsite_tool and url:
            return url.format(session=self)
        return None

    def onsite_tool_url(self):
        url = getattr(settings, "MEETECHO_ONSITE_TOOL_URL", "")
        if self.meeting.type.slug == "ietf" and self.has_onsite_tool and url:
            return url.format(session=self)
        return None

    def _session_recording_url_label(self):
        otsa = self.official_timeslotassignment()
        if otsa is None:
            return None
        if self.meeting.type.slug == "ietf" and self.has_onsite_tool:
            session_label = f"IETF{self.meeting.number}-{self.group.acronym.upper()}-{otsa.timeslot.time.strftime('%Y%m%d-%H%M')}"
        else:
            session_label = f"IETF-{self.group.acronym.upper()}-{otsa.timeslot.time.strftime('%Y%m%d-%H%M')}"
        return session_label

    def session_recording_url(self):
        url_formatter = getattr(settings, "MEETECHO_SESSION_RECORDING_URL", "")
        url = None
        name = self.meetecho_recording_name
        if name is None or name.strip() == "":
            name = self._session_recording_url_label()
        if url_formatter.strip() != "" and name is not None:
            url = url_formatter.format(session_label=name)
        return url


class SchedulingEvent(models.Model):
    session = ForeignKey(Session)
    time = models.DateTimeField(default=timezone.now, help_text="When the event happened")
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

class Attended(models.Model):
    person = ForeignKey(Person)
    session = ForeignKey(Session)
    time = models.DateTimeField(default=timezone.now, null=True, blank=True)
    origin = models.CharField(max_length=32, default='datatracker')

    class Meta:
        unique_together = (('person', 'session'),)

    def __str__(self):
        return f'{self.person} at {self.session}'
