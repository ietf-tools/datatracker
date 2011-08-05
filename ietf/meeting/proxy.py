import datetime

from redesign.proxy_utils import TranslatingManager
from models import *

class MeetingProxy(Meeting):
    objects = TranslatingManager(dict(meeting_num="number"))
                                      
    def from_object(self, base):
        for f in base._meta.fields:
            setattr(self, f.name, getattr(base, f.name))
        return self
                
    #meeting_num = models.IntegerField(primary_key=True)
    @property
    def meeting_num(self):
        return self.number
    #start_date = models.DateField()
    @property
    def start_date(self):
        return self.date
    #end_date = models.DateField()
    @property
    def end_date(self):
        return self.date + datetime.timedelta(days=5)
    
    #city = models.CharField(blank=True, max_length=255)
    #state = models.CharField(blank=True, max_length=255)
    #country = models.CharField(blank=True, max_length=255)
    #time_zone = models.IntegerField(null=True, blank=True, choices=TIME_ZONE_CHOICES)
    #ack = models.TextField(blank=True)
    #agenda_html = models.TextField(blank=True)
    #agenda_text = models.TextField(blank=True)
    #future_meeting = models.TextField(blank=True)
    #overview1 = models.TextField(blank=True)
    #overview2 = models.TextField(blank=True)
    def __str__(self):
	return "IETF-%s" % (self.meeting_num)
    def get_meeting_date (self,offset):
        return self.start_date + datetime.timedelta(days=offset) 
    def num(self):
        return self.meeting_num

    @property
    def meeting_venue(self):
        return MeetingVenueProxy().from_object(self)
    
    class Meta:
        proxy = True

    @classmethod
    def get_first_cut_off(cls):
        start_date = cls.objects.all().order_by('-date')[0].start_date
        offset = datetime.timedelta(days=settings.FIRST_CUTOFF_DAYS)
        return start_date - offset

    @classmethod
    def get_second_cut_off(cls):
        start_date = cls.objects.all().order_by('-date')[0].start_date
        offset = datetime.timedelta(days=settings.SECOND_CUTOFF_DAYS)
        return start_date - offset

    @classmethod
    def get_ietf_monday(cls):
        start_date = cls.objects.all().order_by('-date')[0].start_date
        return start_date + datetime.timedelta(days=-start_date.weekday(), weeks=1)

class MeetingVenueProxy(Meeting):
    objects = TranslatingManager(dict(meeting_num="number"))
                                      
    def from_object(self, base):
        for f in base._meta.fields:
            setattr(self, f.name, getattr(base, f.name))
        return self
    
    #meeting_num = models.ForeignKey(Meeting, db_column='meeting_num', unique=True)
    @property
    def meeting_num(self):
        return self.number
    #break_area_name = models.CharField(max_length=255)
    @property
    def break_area_name(self):
        return self.break_area
    #reg_area_name = models.CharField(max_length=255)
    @property
    def reg_area_name(self):
        return self.reg_area
    
    def __str__(self):
	return "IETF %s" % (self.meeting_num)

    class Meta:
        proxy = True

class MeetingTimeProxy(TimeSlot):
    # the old MeetingTimes did not include a room, so there we can't
    # do a proper mapping - instead this proxy is one TimeSlot and
    # uses the information in that to emulate a MeetingTime and enable
    # retrieval of the other related TimeSlots
    objects = TranslatingManager(dict(day_id="time", time_desc="time"))

    def from_object(self, base):
        for f in base._meta.fields:
            setattr(self, f.name, getattr(base, f.name))
        return self
    
    #time_id = models.AutoField(primary_key=True)
    @property
    def time_id(self):
        return self.pk
    #time_desc = models.CharField(max_length=100)
    @property
    def time_desc(self):
        return u"%s-%s" % (self.time.strftime("%H%M"), (self.time + self.duration).strftime("%H%M"))
    #meeting = models.ForeignKey(Meeting, db_column='meeting_num') # same name
    #day_id = models.IntegerField()
    @property
    def day_id(self):
        return (self.time.date() - self.meeting.date).days
    #session_name = models.ForeignKey(SessionName,null=True)
    @property
    def session_name(self):
        if self.type_id not in ("session", "plenary"):
            return None
        
        class Dummy(object):
            def __unicode__(self):
                return self.session_name
        d = Dummy()
        d.session_name = self.name
        return d
    def __str__(self):
	return "[%d] |%s| %s" % (self.meeting.number, self.time.strftime('%A'), self.time_desc)
    def sessions(self):
        return WgMeetingSessionProxy.objects.filter(meeting=self.meeting, time=self.time, type__in=("session", "plenary", "other"))
    def sessions_by_area(self):
        return [ {"area":session.area()+session.acronym(), "info":session} for session in self.sessions() ]
    def meeting_date(self):
        return self.time.date()
    def registration(self):
        if not hasattr(self, '_reg_info'):
            try:
                self._reg_info = MeetingTimeProxy.objects.get(meeting=self.meeting, time__month=self.time.month, time__day=self.time.day, type="reg")
            except MeetingTimeProxy.DoesNotExist:
                self._reg_info = None
        return self._reg_info
    def reg_info(self):
	reg_info = self.registration()
        if reg_info and reg_info.time_desc:
            return "%s %s" % (reg_info.time_desc, reg_info.name)
        else:
            return ""
    def break_info(self):
        breaks = MeetingTimeProxy.objects.filter(meeting=self.meeting, time__month=self.time.month, time__day=self.time.day, type="break").order_by("time")
        for brk in breaks:
            if brk.time_desc[-4:] == self.time_desc[:4]:
                return brk
        return None
    def is_plenary(self):
        return self.type_id == "plenary"

    # from NonSession
    #non_session_id = models.AutoField(primary_key=True)
    @property
    def non_session_id(self):
        return self.id
    #day_id = models.IntegerField(blank=True, null=True) # already wrapped
    #non_session_ref = models.ForeignKey(NonSessionRef)
    @property
    def non_session_ref(self):
        return 1 if self.type_id == "reg" else 3
    #meeting = models.ForeignKey(Meeting, db_column='meeting_num') 3 same name
    #time_desc = models.CharField(blank=True, max_length=75) # already wrapped
    #show_break_location = models.BooleanField()
    @property
    def show_break_location(self):
        return self.show_location
    def day(self):
        return self.time.strftime("%A")
    
    class Meta:
        proxy = True
        
NonSessionProxy = MeetingTimeProxy

class WgMeetingSessionProxy(TimeSlot):
    # we model WgMeetingSession as a TimeSlot - we need to do this
    # because some previous sessions are now really time slots, to
    # make the illusion complete we thus have to forward all the
    # session stuff to the real session
    objects = TranslatingManager(dict(group_acronym_id="session__group"))

    def from_object(self, base):
        for f in base._meta.fields:
            setattr(self, f.name, getattr(base, f.name))
        return self

    def get_session(self):
        if not hasattr(self, "_session_cache"):
            s = self.session_set.all()
            self._session_cache = s[0] if s else None

        return self._session_cache
    
    #session_id = models.AutoField(primary_key=True)
    @property
    def session_id(self):
        return self.id
    #meeting = models.ForeignKey(Meeting, db_column='meeting_num') # same name
    #group_acronym_id = models.IntegerField()
    @property
    def group_acronym_id(self):
        s = self.get_session()
        return s.group_id if s else -1
    #irtf = models.NullBooleanField()
    #num_session = models.IntegerField()
    #length_session1 = models.CharField(blank=True, max_length=100)
    #length_session2 = models.CharField(blank=True, max_length=100)
    #length_session3 = models.CharField(blank=True, max_length=100)
    #conflict1 = models.CharField(blank=True, max_length=255)
    #conflict2 = models.CharField(blank=True, max_length=255)
    #conflict3 = models.CharField(blank=True, max_length=255)
    #conflict_other = models.TextField(blank=True)
    #special_req = models.TextField(blank=True)
    #number_attendee = models.IntegerField(null=True, blank=True)
    @property
    def number_attendee(self):
        s = self.get_session()
        return s.attendees if s else 0
    #approval_ad = models.IntegerField(null=True, blank=True)
    #status = models.ForeignKey(SessionStatus, null=True, blank=True) # same name
    #ts_status_id = models.IntegerField(null=True, blank=True)
    #requested_date = models.DateField(null=True, blank=True)
    #approved_date = models.DateField(null=True, blank=True)
    #requested_by = BrokenForeignKey(PersonOrOrgInfo, db_column='requested_by', null=True, null_values=(0, 888888))
    #scheduled_date = models.DateField(null=True, blank=True)
    #last_modified_date = models.DateField(null=True, blank=True)
    #ad_comments = models.TextField(blank=True,null=True)
    #sched_room_id1 = models.ForeignKey(MeetingRoom, db_column='sched_room_id1', null=True, blank=True, related_name='here1')
    #sched_time_id1 = BrokenForeignKey(MeetingTime, db_column='sched_time_id1', null=True, blank=True, related_name='now1')
    #sched_date1 = models.DateField(null=True, blank=True)
    #sched_room_id2 = models.ForeignKey(MeetingRoom, db_column='sched_room_id2', null=True, blank=True, related_name='here2')
    #sched_time_id2 = BrokenForeignKey(MeetingTime, db_column='sched_time_id2', null=True, blank=True, related_name='now2')
    #sched_date2 = models.DateField(null=True, blank=True)
    #sched_room_id3 = models.ForeignKey(MeetingRoom, db_column='sched_room_id3', null=True, blank=True, related_name='here3')
    #sched_time_id3 = BrokenForeignKey(MeetingTime, db_column='sched_time_id3', null=True, blank=True, related_name='now3')
    #sched_date3 = models.DateField(null=True, blank=True)
    #special_agenda_note = models.CharField(blank=True, max_length=255)
    #combined_room_id1 = models.ForeignKey(MeetingRoom, db_column='combined_room_id1', null=True, blank=True, related_name='here4')
    #combined_time_id1 = models.ForeignKey(MeetingTime, db_column='combined_time_id1', null=True, blank=True, related_name='now4')
    #combined_room_id2 = models.ForeignKey(MeetingRoom, db_column='combined_room_id2', null=True, blank=True, related_name='here5')
    #combined_time_id2 = models.ForeignKey(MeetingTime, db_column='combined_time_id2', null=True, blank=True, related_name='now5')
    def __str__(self):
	return "%s at %s" % (self.acronym(), self.meeting)
    def agenda_file(self,interimvar=0):
        if not hasattr(self, '_agenda_file'):
            # FIXME
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
        return self._agenda_file
    def minute_file(self,interimvar=0):
        # FIXME
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
        # FIXME
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
        # FIXME
        if self.minute_file(1):
            return True
        elif self.agenda_file(1):
            return True
        elif self.slides(1):
            return True
        else:
            return False
    def length_session1_desc (self):
        if self.requested_duration.seconds == 60 * 60:
            return "1 hour"
        else:
            return "%.1f hours" % (float(self.requested_duration.seconds) / (60 * 60))
    def length_session2_desc (self):
        return ""
    def length_session3_desc (self):
        return ""

    @property
    def room_id(self):
        class Dummy: pass
        d = Dummy()
        d.room_name = self.location.name
        return d
    
    _dirs = {}

    # from ResolveAcronym:
    def acronym(self):
        s = self.get_session()
        if not s:
            return ""
        if hasattr(self, "interim"):
            return "i" + s.group.acronym
        else:
            return s.group.acronym
    def acronym_lower(self):
        return self.acronym().lower()
    def acronym_name(self):
        s = self.get_session()
        if not s:
            return self.name
        if hasattr(self, "interim"):
            return s.group.name + " (interim)"
        else:
            return s.group.name
    def area(self):
        s = self.get_session()
        if not s:
            return ""
        return s.group.parent.acronym
    def area_name(self):
        s = self.get_session()
        if not s:
            return ""
        return s.group.parent.name
    def isWG(self):
        s = self.get_session()
        if not s or not s.group:
            return False
        if s.group.type_id == "wg" and s.group.state_id != "bof":
            return True
    def group_type_str(self):
        s = self.get_session()
        if not s or not s.group:
            return ""
        if s.group and s.group.type_id == "wg":
            if s.group.state_id == "bof":
                return "BOF"
            else:
                return "WG"

        return ""
    
    class Meta:
        proxy = True
        
