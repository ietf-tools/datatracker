# Copyright The IETF Trust 2007, All Rights Reserved

########################################################################
########################################################################
########################################################################
#####                                                              #####
#####   WARNING WARNING WARNING WARNING WARNING WARNING WARNING    #####
#####                                                              #####
#####   These models are old, deprecated, and should not be        #####
#####   used. Use the models in the meetings directory             #####
#####   instead.                                                   #####
#####                                                              #####
#####   WARNING WARNING WARNING WARNING WARNING WARNING WARNING    #####
#####                                                              #####
########################################################################
########################################################################
########################################################################

from django.db import models
from django.conf import settings
from ietf.idtracker.models import Acronym, PersonOrOrgInfo, IRTF, AreaGroup, Area, IETFWG
from ietf.utils.broken_foreign_key import BrokenForeignKey
import datetime
#from ietf.utils import log

# group_acronym is either an IETF Acronym
#  or an IRTF one, depending on the value of irtf.
#  Multiple inheritance to the rescue.
#
# interim = i prefix (complicated because you have to check if self has
#    an interim attribute first)
class ResolveAcronym(object):
    def acronym(self):
        if hasattr(self, '_acronym_acronym'):
            return self._acronym_acronym
	try:
	    interim = self.interim
	except AttributeError:
	    interim = False
	if self.irtf:
	    o = IRTF.objects.get(pk=self.group_acronym_id)
	else:
            o = Acronym.objects.get(pk=self.group_acronym_id)
        self._acronym_acronym = o.acronym
        self._acronym_name = o.name
        acronym = self._acronym_acronym
	if interim:
	    return "i" + acronym
        else:
            return acronym
    def acronym_lower(self):
        return self.acronym().lower()
    def acronym_name(self):
        if not hasattr(self, '_acronym_name'):
            self.acronym()
        try:
            interim = self.interim
        except AttributeError:
            interim = False
        acronym_name = self._acronym_name
        if interim:
            return acronym_name + " (interim)"
        else:
            return acronym_name
    def area(self):
        if hasattr(self, '_area'):
            return self._area
        if self.irtf:
            area = "irtf"
        elif self.group_acronym_id < 0  and self.group_acronym_id > -3:
            area = "1plenary"
        elif self.group_acronym_id < -2:
            area = ""
        else:
            try:
                area = AreaGroup.objects.select_related().get(group=self.group_acronym_id).area.area_acronym.acronym
            except AreaGroup.DoesNotExist:
                area = ""
        self._area = area
        return area
    def area_name(self):
        if self.irtf:
            area_name = "IRTF"
        elif self.group_acronym_id < 0  and self.group_acronym_id > -3:
            area_name = "Plenary Sessions"
        elif self.group_acronym_id < -2:
            area_name = "Training"
        else:
            try:
                area_name = AreaGroup.objects.get(group=self.group_acronym_id).area.area_acronym.name
            except AreaGroup.DoesNotExist:
                area_name = ""
        return area_name
    def isWG(self):
        if self.irtf:
              return False
        if not hasattr(self,'_ietfwg'):
            try:
                self._ietfwg = IETFWG.objects.get(pk=self.group_acronym_id)
            except IETFWG.DoesNotExist:
                self._ietfwg = None
        if self._ietfwg and self._ietfwg.group_type_id == 1:
            return True
        else:
            return False
    def group_type_str(self):
        if self.irtf:
            return ""
        else:
            self.isWG()
            if not self._ietfwg:
                return ""
            elif self._ietfwg.group_type_id == 1:
                return "WG"
            elif self._ietfwg.group_type_id == 3:
                return "BOF"
            else:
                return ""

TIME_ZONE_CHOICES = (
    (0, 'UTC'),
    (-1, 'UTC -1'),
    (-2, 'UTC -2'),
    (-3, 'UTC -3'),
    (-4, 'UTC -4 (Eastern Summer)'),
    (-5, 'UTC -5 (Eastern Winter)'),
    (-6, 'UTC -6'),
    (-7, 'UTC -7'),
    (-8, 'UTC -8 (Pacific Winter)'),
    (-9, 'UTC -9'),
    (-10, 'UTC -10 (Hawaii Winter)'),
    (-11, 'UTC -11'),
    (+12, 'UTC +12'),
    (+11, 'UTC +11'),
    (+10, 'UTC +10 (Brisbane)'),
    (+9, 'UTC +9'),
    (+8, 'UTC +8 (Perth Winter)'),
    (+7, 'UTC +7'),
    (+6, 'UTC +6'),
    (+5, 'UTC +5'),
    (+4, 'UTC +4'),
    (+3, 'UTC +3 (Moscow Winter)'),
    (+2, 'UTC +2 (Western Europe Summer'),
    (+1, 'UTC +1 (Western Europe Winter)'),
)

class Meeting(models.Model):
    meeting_num = models.IntegerField(primary_key=True)
    start_date = models.DateField()
    end_date = models.DateField()
    city = models.CharField(blank=True, max_length=255)
    state = models.CharField(blank=True, max_length=255)
    country = models.CharField(blank=True, max_length=255)
    time_zone = models.IntegerField(null=True, blank=True, choices=TIME_ZONE_CHOICES)
    ack = models.TextField(blank=True)
    agenda_html = models.TextField(blank=True)
    agenda_text = models.TextField(blank=True)
    future_meeting = models.TextField(blank=True)
    overview1 = models.TextField(blank=True)
    overview2 = models.TextField(blank=True)
    def __str__(self):
	return "IETF-%s" % (self.meeting_num)
    def get_meeting_date (self,offset):
        return self.start_date + datetime.timedelta(days=offset) 
    def num(self):
        return self.meeting_num
    class Meta:
        db_table = 'meetings'

    @classmethod
    def get_first_cut_off(cls):
        start_date = cls.objects.all().order_by('-start_date')[0].start_date
        offset = datetime.timedelta(days=settings.FIRST_CUTOFF_DAYS)
        return start_date - offset

    @classmethod
    def get_second_cut_off(cls):
        start_date = cls.objects.all().order_by('-start_date')[0].start_date
        offset = datetime.timedelta(days=settings.SECOND_CUTOFF_DAYS)
        return start_date - offset

    @classmethod
    def get_ietf_monday(cls):
        start_date = cls.objects.all().order_by('-start_date')[0].start_date
        return start_date + datetime.timedelta(days=-start_date.weekday(), weeks=1)

class MeetingVenue(models.Model):
    meeting_num = models.ForeignKey(Meeting, db_column='meeting_num', unique=True)
    break_area_name = models.CharField(max_length=255)
    reg_area_name = models.CharField(max_length=255)
    def __str__(self):
	return "IETF %s" % (self.meeting_num_id)
    class Meta:
        db_table = 'meeting_venues'
        verbose_name = "Meeting public areas"
        verbose_name_plural = "Meeting public areas"

class NonSessionRef(models.Model):
    name = models.CharField(max_length=255)
    def __str__(self):
	return self.name
    class Meta:
        db_table = 'non_session_ref'
        verbose_name = "Non-session slot name"

class NonSession(models.Model):
    non_session_id = models.AutoField(primary_key=True)
    day_id = models.IntegerField(blank=True, null=True) # NULL means all days
    non_session_ref = models.ForeignKey(NonSessionRef)
    meeting = models.ForeignKey(Meeting, db_column='meeting_num')
    time_desc = models.CharField(blank=True, max_length=75)
    show_break_location = models.BooleanField()
    def __str__(self):
	if self.day_id:
	    return "%s %s %s @%s" % ((self.meeting.start_date + datetime.timedelta(self.day_id)).strftime('%A'), self.time_desc, self.non_session_ref, self.meeting_id)
	else:
	    return "** %s %s @%s" % (self.time_desc, self.non_session_ref, self.meeting_id)
    def day(self):
        if self.day_id:
            return (self.meeting.start_date + datetime.timedelta(self.day_id)).strftime('%A')
        else:
            return "All"
    class Meta:
	db_table = 'non_session'
        verbose_name = "Meeting non-session slot"

class Proceeding(models.Model):
    meeting_num = models.ForeignKey(Meeting, db_column='meeting_num', unique=True, primary_key=True)
    dir_name = models.CharField(blank=True, max_length=25)
    sub_begin_date = models.DateField(null=True, blank=True)
    sub_cut_off_date = models.DateField(null=True, blank=True)
    frozen = models.IntegerField(null=True, blank=True)
    c_sub_cut_off_date = models.DateField(null=True, blank=True)
    pr_from_date = models.DateField(null=True, blank=True)
    pr_to_date = models.DateField(null=True, blank=True)
    def __str__(self):
	return "IETF %s" % (self.meeting_num_id)
    class Meta:
        db_table = 'proceedings'
	ordering = ['?']	# workaround for FK primary key

class SessionConflict(models.Model):
    group_acronym = models.ForeignKey(Acronym, related_name='conflicts_set')
    conflict_gid = models.ForeignKey(Acronym, related_name='conflicts_with_set', db_column='conflict_gid')
    meeting_num = models.ForeignKey(Meeting, db_column='meeting_num')
    def __str__(self):
        try:
            return "At IETF %s, %s conflicts with %s" % ( self.meeting_num_id, self.group_acronym.acronym, self.conflict_gid.acronym)
        except BaseException:
	    return "At IETF %s, something conflicts with something" % ( self.meeting_num_id )

    class Meta:
        db_table = 'session_conflicts'

class SessionName(models.Model):
    session_name_id = models.AutoField(primary_key=True)
    session_name = models.CharField(blank=True, max_length=255)
    def __str__(self):
	return self.session_name
    class Meta:
        db_table = 'session_names'
        verbose_name = "Slot name"


class IESGHistory(models.Model):
    meeting = models.ForeignKey(Meeting, db_column='meeting_num')
    area = models.ForeignKey(Area, db_column='area_acronym_id')
    person = models.ForeignKey(PersonOrOrgInfo, db_column='person_or_org_tag')
    def __str__(self):
        return "IESG%s: %s (%s)" % (self.meeting_id, self.person,self.area)
    class Meta:
        db_table = 'iesg_history'
        verbose_name = "Meeting AD info"
        verbose_name_plural = "Meeting AD info"
    
class MeetingTime(models.Model):
    time_id = models.AutoField(primary_key=True)
    time_desc = models.CharField(max_length=100)
    meeting = models.ForeignKey(Meeting, db_column='meeting_num')
    day_id = models.IntegerField()
    session_name = models.ForeignKey(SessionName,null=True)
    def __str__(self):
	return "[%d] |%s| %s" % (self.meeting_id, (self.meeting.start_date + datetime.timedelta(self.day_id)).strftime('%A'), self.time_desc)
    def sessions(self):
	"""
	Get all sessions that are scheduled at this time.
	"""
	sessions = WgMeetingSession.objects.filter(
	    models.Q(sched_time_id1=self.time_id) |
	    models.Q(sched_time_id2=self.time_id) |
	    models.Q(sched_time_id3=self.time_id) |
            models.Q(combined_time_id1=self.time_id) |
            models.Q(combined_time_id2=self.time_id))
	for s in sessions:
	    if s.sched_time_id1_id == self.time_id:
		s.room_id = s.sched_room_id1
                s.ordinality = 1
	    elif s.sched_time_id2_id == self.time_id:
		s.room_id = s.sched_room_id2
                s.ordinality = 2
	    elif s.sched_time_id3_id == self.time_id:
		s.room_id = s.sched_room_id3
                s.ordinality = 3
            elif s.combined_time_id1_id == self.time_id:
                s.room_id = s.combined_room_id1
                s.ordinality = 4
            elif s.combined_time_id2_id == self.time_id:
                s.room_id = s.combined_room_id2
                s.ordinality = 5
	    else:
		s.room_id = 0
                s.ordinality = 0
	return sessions
    def sessions_by_area(self):
        return [ {"area":session.area()+session.acronym(), "info":session} for session in self.sessions() ]
    def meeting_date(self):
        return self.meeting.get_meeting_date(self.day_id)
    def registration(self):
        if hasattr(self, '_reg_info'):
            return self._reg_info
        reg = NonSession.objects.get(meeting=self.meeting, day_id=self.day_id, non_session_ref=1)
        reg.name = reg.non_session_ref.name
        self._reg_info = reg
	return reg
    def reg_info(self):
	reg_info = self.registration()
        if reg_info.time_desc:
            return "%s %s" % (reg_info.time_desc, reg_info.name)
        else:
            return ""
    def break_info(self):
        breaks = NonSession.objects.filter(meeting=self.meeting).exclude(non_session_ref=1).filter(models.Q(day_id=self.day_id) | models.Q(day_id__isnull=True)).order_by('time_desc')
        for brk in breaks:
            if brk.time_desc[-4:] == self.time_desc[:4]:
                brk.name = brk.non_session_ref.name
                return brk
        return None
    def is_plenary(self):
        return self.session_name_id in [9, 10]
    class Meta:
        db_table = 'meeting_times'
        verbose_name = "Meeting slot time"

class MeetingRoom(models.Model):
    room_id = models.AutoField(primary_key=True)
    meeting = models.ForeignKey(Meeting, db_column='meeting_num')
    room_name = models.CharField(max_length=255)
    def __str__(self):
	return "[%d] %s" % (self.meeting_id, self.room_name)
    class Meta:
        db_table = 'meeting_rooms'
        verbose_name = "Meeting room name"

class SessionStatus(models.Model):
    id = models.AutoField(primary_key=True, db_column='status_id')
    name = models.CharField(max_length=32, db_column='status')
    def __str__(self):
        return self.name
    class Meta:
        db_table = 'session_status'


class WgMeetingSession(models.Model, ResolveAcronym):
    session_id = models.AutoField(primary_key=True)
    meeting = models.ForeignKey(Meeting, db_column='meeting_num')
    group_acronym_id = models.IntegerField()
    irtf = models.NullBooleanField()
    num_session = models.IntegerField()
    length_session1 = models.CharField(blank=True, max_length=100)
    length_session2 = models.CharField(blank=True, max_length=100)
    length_session3 = models.CharField(blank=True, max_length=100)
    conflict1 = models.CharField(blank=True, max_length=255)
    conflict2 = models.CharField(blank=True, max_length=255)
    conflict3 = models.CharField(blank=True, max_length=255)
    conflict_other = models.TextField(blank=True)
    special_req = models.TextField(blank=True)
    number_attendee = models.IntegerField(null=True, blank=True)
    approval_ad = models.IntegerField(null=True, blank=True)
    status = models.ForeignKey(SessionStatus, null=True, blank=True)
    ts_status_id = models.IntegerField(null=True, blank=True)
    requested_date = models.DateField(null=True, blank=True)
    approved_date = models.DateField(null=True, blank=True)
    requested_by = BrokenForeignKey(PersonOrOrgInfo, db_column='requested_by', null=True, null_values=(0, 888888))
    scheduled_date = models.DateField(null=True, blank=True)
    last_modified_date = models.DateField(null=True, blank=True)
    ad_comments = models.TextField(blank=True,null=True)
    sched_room_id1 = models.ForeignKey(MeetingRoom, db_column='sched_room_id1', null=True, blank=True, related_name='here1')
    sched_time_id1 = BrokenForeignKey(MeetingTime, db_column='sched_time_id1', null=True, blank=True, related_name='now1')
    sched_date1 = models.DateField(null=True, blank=True)
    sched_room_id2 = models.ForeignKey(MeetingRoom, db_column='sched_room_id2', null=True, blank=True, related_name='here2')
    sched_time_id2 = BrokenForeignKey(MeetingTime, db_column='sched_time_id2', null=True, blank=True, related_name='now2')
    sched_date2 = models.DateField(null=True, blank=True)
    sched_room_id3 = models.ForeignKey(MeetingRoom, db_column='sched_room_id3', null=True, blank=True, related_name='here3')
    sched_time_id3 = BrokenForeignKey(MeetingTime, db_column='sched_time_id3', null=True, blank=True, related_name='now3')
    sched_date3 = models.DateField(null=True, blank=True)
    special_agenda_note = models.CharField(blank=True, max_length=255)
    combined_room_id1 = models.ForeignKey(MeetingRoom, db_column='combined_room_id1', null=True, blank=True, related_name='here4')
    combined_time_id1 = BrokenForeignKey(MeetingTime, db_column='combined_time_id1', null=True, blank=True, related_name='now4')
    combined_room_id2 = models.ForeignKey(MeetingRoom, db_column='combined_room_id2', null=True, blank=True, related_name='here5')
    combined_time_id2 = BrokenForeignKey(MeetingTime, db_column='combined_time_id2', null=True, blank=True, related_name='now5')
    def __str__(self):
	return "%s at %s" % (self.acronym(), self.meeting)
    def agenda_file(self,interimvar=0):
        if hasattr(self, '_agenda_file'):
            return self._agenda_file
        irtfvar = 0
        if self.irtf:
            irtfvar = self.group_acronym_id 
        if interimvar == 0:
            try:
                if self.interim:
                    interimvar = 1
            except AttributeError:
                    interimvar = 0
        try:
            filename = WgAgenda.objects.get(meeting=self.meeting, group_acronym_id=self.group_acronym_id,irtf=irtfvar,interim=interimvar).filename
            if self.meeting_id in WgMeetingSession._dirs:
                dir = WgMeetingSession._dirs[self.meeting_id]
            else:
                dir = Proceeding.objects.get(meeting_num=self.meeting).dir_name
                WgMeetingSession._dirs[self.meeting_id]=dir
            retvar = "%s/agenda/%s" % (dir,filename) 
        except WgAgenda.DoesNotExist:
            retvar = ""
        self._agenda_file = retvar
        return retvar
    def minute_file(self,interimvar=0):
        irtfvar = 0
        if self.irtf:
            irtfvar = self.group_acronym_id
        if interimvar == 0:
            try:
                if self.interim:
                    interimvar = 1
            except AttributeError:
                    interimvar = 0
        try:
            filename = Minute.objects.get(meeting=self.meeting, group_acronym_id=self.group_acronym_id,irtf=irtfvar,interim=interimvar).filename
            dir = Proceeding.objects.get(meeting_num=self.meeting).dir_name
            retvar = "%s/minutes/%s" % (dir,filename)
        except Minute.DoesNotExist:
            retvar = ""
        return retvar
    def slides(self,interimvar=0):
        """
        Get all slides of this session.
        """
        irtfvar = 0
        if self.irtf:
            irtfvar = self.group_acronym_id
        if interimvar == 0:
            try:
                if self.interim:
                    interimvar = 1
            except AttributeError:
                    interimvar = 0
        slides = Slide.objects.filter(meeting=self.meeting,group_acronym_id=self.group_acronym_id,irtf=irtfvar,interim=interimvar).order_by("order_num")
        return slides
    def interim_meeting (self):
        if self.minute_file(1):
            return True
        elif self.agenda_file(1):
            return True
        elif self.slides(1):
            return True
        else:
            return False
    def length_session1_desc (self):
        mh = MeetingHour.objects.get(hour_id=self.length_session1)
        return mh.hour_desc
    def length_session2_desc (self):
        mh = MeetingHour.objects.get(hour_id=self.length_session2)
        return mh.hour_desc
    def length_session3_desc (self):
        mh = MeetingHour.objects.get(hour_id=self.length_session3)
        return mh.hour_desc
    class Meta:
        db_table = 'wg_meeting_sessions'
        verbose_name = "WG meeting session"
        
    _dirs = {}

class WgAgenda(models.Model, ResolveAcronym):
    meeting = models.ForeignKey(Meeting, db_column='meeting_num')
    group_acronym_id = models.IntegerField()
    filename = models.CharField(max_length=255)
    irtf = models.IntegerField()
    interim = models.BooleanField()
    def __str__(self):
	return "Agenda for %s at IETF %s" % (self.acronym(), self.meeting_id)
    class Meta:
        db_table = 'wg_agenda'
        verbose_name = "WG agenda info"
        verbose_name_plural = "WG agenda info"

class Minute(models.Model, ResolveAcronym):
    meeting = models.ForeignKey(Meeting, db_column='meeting_num')
    group_acronym_id = models.IntegerField()
    filename = models.CharField(blank=True, max_length=255)
    irtf = models.IntegerField()
    interim = models.BooleanField()
    def __str__(self):
	return "Minutes for %s at IETF %s" % (self.acronym(), self.meeting_id)
    class Meta:
        db_table = 'minutes'
        verbose_name = "WG minutes info"


# It looks like Switches was meant for something bigger, but
# is only used for the agenda generation right now so we'll
# put it here.
class Switches(models.Model):
    name = models.CharField(max_length=100)
    val = models.IntegerField(null=True, blank=True)
    updated_date = models.DateField(null=True, blank=True)
    updated_time = models.TimeField(null=True, blank=True)
    def updated(self):
	return datetime.datetime.combine( self.updated_date, self.updated_time )
    def __str__(self):
	return self.name
    class Meta:
        db_table = 'switches'
        verbose_name = "Switch"
        verbose_name_plural = "Switches"

# Empty table, don't pretend that it exists.
#class SlideTypes(models.Model):
#    type_id = models.AutoField(primary_key=True)
#    type = models.CharField(max_length=255, db_column='type_name')
#    def __str__(self):
#	return self.type
#    class Meta:
#        db_table = 'slide_types'

class Slide(models.Model, ResolveAcronym):
    SLIDE_TYPE_CHOICES=(
	('1', '(converted) HTML'),
	('2', 'PDF'),
	('3', 'Text'),
	('4', 'PowerPoint -2003 (PPT)'),
	('5', 'Microsoft Word'),
	('6', 'PowerPoint 2007- (PPTX)'),
    )
    meeting = models.ForeignKey(Meeting, db_column='meeting_num')
    group_acronym_id = models.IntegerField(null=True, blank=True)
    slide_num = models.IntegerField(null=True, blank=True)
    slide_type_id = models.IntegerField(choices=SLIDE_TYPE_CHOICES)
    slide_name = models.CharField(blank=True, max_length=255)
    irtf = models.IntegerField()
    interim = models.BooleanField()
    order_num = models.IntegerField(null=True, blank=True)
    in_q = models.IntegerField(null=True, blank=True)
    def __str__(self):
	return "IETF%d: %s slides (%s)" % (self.meeting_id, self.acronym(), self.slide_name)
    def file_loc(self):
        dir = Proceeding.objects.get(meeting_num=self.meeting).dir_name
        if self.slide_type_id==1:
            #return "%s/slides/%s-%s/sld1.htm" % (dir,self.acronym(),self.slide_num)
            return "%s/slides/%s-%s/%s-%s.htm" % (dir,self.acronym(),self.slide_num,self.acronym(),self.slide_num)
        else:
            if self.slide_type_id == 2:
                ext = ".pdf"
            elif self.slide_type_id == 3:
                ext = ".txt"
            elif self.slide_type_id == 4:
                ext = ".ppt"
            elif self.slide_type_id == 5:
                ext = ".doc"
            elif self.slide_type_id == 6:
                ext = ".pptx"
            else:
                ext = ""
            return "%s/slides/%s-%s%s" % (dir,self.acronym(),self.slide_num,ext)
    class Meta:
        db_table = 'slides'

class WgProceedingsActivities(models.Model, ResolveAcronym):
    id = models.AutoField(primary_key=True)
    #group_acronym_id = models.IntegerField(null=True, blank=True)
    group_acronym = models.ForeignKey(Acronym)

    meeting = models.ForeignKey(Meeting, db_column='meeting_num')
    activity = models.CharField(blank=True, max_length=255)
    act_date =  models.DateField(null=True, blank=True)
    act_time = models.CharField(blank=True, max_length=100)
    act_by = models.ForeignKey(PersonOrOrgInfo, db_column='act_by')
    irtf = None

    def __str__(self):
        return "IETF%d: %s %s" % (self.meeting_id, self.acronym(), self.activity)
    class Meta:
        db_table = 'wg_proceedings_activities'
        verbose_name = "WG material upload"

class MeetingHour(models.Model):
    hour_id = models.IntegerField(primary_key=True)
    hour_desc = models.CharField(max_length=60, blank=True)
    def __unicode__(self):
        return self.hour_desc
    class Meta:
        db_table = u'meeting_hours'

class NotMeetingGroup(models.Model):
    # note: phony key, there's no primary key in db
    group_acronym = models.ForeignKey(Acronym, primary_key=True, null=True, blank=True)
    meeting = models.ForeignKey(Meeting, db_column='meeting_num', null=True, blank=True)
    class Meta:
        db_table = u'not_meeting_groups'

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    MeetingOld = Meeting
    ProceedingOld = Proceeding
    MeetingVenueOld = MeetingVenue
    MeetingTimeOld = MeetingTime
    WgMeetingSessionOld = WgMeetingSession
    SlideOld = Slide
    SwitchesOld = Switches
    IESGHistoryOld = IESGHistory
    from ietf.meeting.proxy import MeetingProxy as Meeting, ProceedingProxy as Proceeding, MeetingVenueProxy as MeetingVenue, MeetingTimeProxy as MeetingTime, WgMeetingSessionProxy as WgMeetingSession, SlideProxy as Slide, SwitchesProxy as Switches, IESGHistoryProxy as IESGHistory

# changes done by convert-096.py:changed maxlength to max_length
# removed core
# removed raw_id_admin
