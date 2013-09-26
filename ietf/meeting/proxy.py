import datetime

from django.conf import settings

from ietf.utils.proxy import TranslatingManager
from models import *

class MeetingProxy(Meeting):
    objects = TranslatingManager(dict(meeting_num="number"), always_filter=dict(type="ietf"))
                                      
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
        return self.number

    @property
    def meeting_venue(self):
        return MeetingVenueProxy().from_object(self)
    
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

    class Meta:
        proxy = True

class ProceedingProxy(Meeting):
    objects = TranslatingManager(dict(meeting_num="number"))
                                      
    #meeting_num = models.ForeignKey(Meeting, db_column='meeting_num', unique=True, primary_key=True)
    @property
    def meeting_num(self):
        return MeetingProxy().from_object(self)
    @property
    def meeting_num_id(self):
        return self.number
    #dir_name = models.CharField(blank=True, max_length=25)
    @property
    def dir_name(self):
        return self.number
    #sub_begin_date = models.DateField(null=True, blank=True)
    @property
    def sub_begin_date(self):
        return self.get_submission_start_date()
    #sub_cut_off_date = models.DateField(null=True, blank=True)
    @property
    def sub_cut_off_date(self):
        return self.get_submission_cut_off_date()
    #frozen = models.IntegerField(null=True, blank=True)
    #c_sub_cut_off_date = models.DateField(null=True, blank=True)
    @property
    def c_sub_cut_off_date(self):
        return self.get_submission_correction_date()
    #pr_from_date = models.DateField(null=True, blank=True)
    #pr_to_date = models.DateField(null=True, blank=True)
    def __str__(self):
	return "IETF %s" % (self.meeting_num_id)
    class Meta:
        proxy = True
    
class SwitchesProxy(Meeting):
    def from_object(self, base):
        for f in base._meta.fields:
            setattr(self, f.name, getattr(base, f.name))
        return self
    
    #name = models.CharField(max_length=100)
    #val = models.IntegerField(null=True, blank=True)
    #updated_date = models.DateField(null=True, blank=True)
    #updated_time = models.TimeField(null=True, blank=True)
    def updated(self):
        from django.db.models import Max
	return max(self.timeslot_set.aggregate(Max('modified'))["modified__max"],
                   self.session_set.aggregate(Max('modified'))["modified__max"])
    class Meta:
        proxy = True

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

class WgMeetingSessionProxy(TimeSlot):
    # we model WgMeetingSession as a TimeSlot, to make the illusion
    # complete we thus have to forward all the session stuff to the
    # real session
    objects = TranslatingManager(dict(group_acronym_id="session__group",
                                      status__id=lambda v: ("state", {4: "sched"}[v])))

    def from_object(self, base):
        for f in base._meta.fields:
            setattr(self, f.name, getattr(base, f.name))
        return self

    #session_id = models.AutoField(primary_key=True) # same name
    #meeting = models.ForeignKey(Meeting, db_column='meeting_num') # same name
    #group_acronym_id = models.IntegerField()
    @property
    def group_acronym_id(self):
        return self.session.group_id if self.session else -1
    #irtf = models.NullBooleanField()
    @property
    def irtf(self):
        return 1 if self.session and self.session.group and self.session.group.type == "rg" else 0
    #num_session = models.IntegerField()
    @property
    def num_session(self):
        return 1 if self.session else 0
    #length_session1 = models.CharField(blank=True, max_length=100)
    @property
    def length_session1(self):
        if not self.session:
            return "0"
        
        secs = self.session.requested_duration.seconds
        if secs == 0:
            return "0"
        return str((secs / 60 - 30) / 30)
    #length_session2 = models.CharField(blank=True, max_length=100)
    @property
    def length_session2(self):
        return "0"
    #length_session3 = models.CharField(blank=True, max_length=100)
    @property
    def length_session3(self):
        return "0"

    def conflicting_group_acronyms(self, level):
        if not self.session:
            return ""
        
        conflicts = Constraint.objects.filter(meeting=self.meeting_id,
                                              target=self.session.group,
                                              name=level)
        return " ".join(c.source.acronym for c in conflicts)
        
    #conflict1 = models.CharField(blank=True, max_length=255)
    @property
    def conflict1(self):
        return self.conflicting_group_acronyms("conflict")
    #conflict2 = models.CharField(blank=True, max_length=255)
    @property
    def conflict2(self):
        return self.conflicting_group_acronyms("conflic2")
    #conflict3 = models.CharField(blank=True, max_length=255)
    @property
    def conflict3(self):
        return self.conflicting_group_acronyms("conflic3")
    #conflict_other = models.TextField(blank=True)
    @property
    def conflict_other(self):
        return ""
    #special_req = models.TextField(blank=True)
    @property
    def special_req(self):
        return self.session.comments if self.session else ""
    #number_attendee = models.IntegerField(null=True, blank=True)
    @property
    def number_attendee(self):
        return self.session.attendees if self.session else 0
    #approval_ad = models.IntegerField(null=True, blank=True)
    #status = models.ForeignKey(SessionStatus, null=True, blank=True) # same name
    #ts_status_id = models.IntegerField(null=True, blank=True)
    #requested_date = models.DateField(null=True, blank=True)
    @property
    def requested_date(self):
        return self.session.requested.date() if self.session else None
    #approved_date = models.DateField(null=True, blank=True)
    #requested_by = BrokenForeignKey(PersonOrOrgInfo, db_column='requested_by', null=True, null_values=(0, 888888))
    @property
    def requested_by(self):
        return self.session.requested_by if self.session else None
    #scheduled_date = models.DateField(null=True, blank=True)
    @property
    def scheduled_date(self):
        return self.session.scheduled.date() if self.session else ""
    #last_modified_date = models.DateField(null=True, blank=True)
    @property
    def last_modified_date(self):
        return self.session.modified.date() if self.session else ""
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
    @property
    def special_agenda_note(self):
        return self.session.agenda_note if self.session else ""
    #combined_room_id1 = models.ForeignKey(MeetingRoom, db_column='combined_room_id1', null=True, blank=True, related_name='here4')
    #combined_time_id1 = models.ForeignKey(MeetingTime, db_column='combined_time_id1', null=True, blank=True, related_name='now4')
    #combined_room_id2 = models.ForeignKey(MeetingRoom, db_column='combined_room_id2', null=True, blank=True, related_name='here5')
    #combined_time_id2 = models.ForeignKey(MeetingTime, db_column='combined_time_id2', null=True, blank=True, related_name='now5')
    def __str__(self):
	return "%s at %s" % (self.acronym(), self.meeting)
    def agenda_file(self,interimvar=0):
        if not hasattr(self, '_agenda_file'):
            self._agenda_file = ""

            if not self.session:
                return ""

            docs = self.session.materials.filter(type="agenda", states__type="agenda", states__slug="active")
            if not docs:
                return ""

            # we use external_url at the moment, should probably regularize
            # the filenames to match the document name instead
            filename = docs[0].external_url
            self._agenda_file = "%s/agenda/%s" % (self.meeting.number, filename)
            
        return self._agenda_file
    def minute_file(self,interimvar=0):
        if not self.session:
            return ""

        docs = self.session.materials.filter(type="minutes", states__type="minutes", states__slug="active")
        if not docs:
            return ""

        # we use external_url at the moment, should probably regularize
        # the filenames to match the document name instead
        filename = docs[0].external_url
        return "%s/minutes/%s" % (self.meeting.number, filename)
    def slides(self,interimvar=0):
        return SlideProxy.objects.filter(session__timeslot=self).order_by("order")
    def interim_meeting(self):
        return False
    def length_session1_desc(self):
        l = self.length_session1
        return { "0": "", "1": "1 hour", "2": "1.5 hours", "3": "2 hours", "4": "2.5 hours"}[l]
    def length_session2_desc(self):
        return ""
    def length_session3_desc(self):
        return ""

    @property
    def ordinality(self):
        return 1
    
    @property
    def room_id(self):
        class Dummy: pass
        d = Dummy()
        d.room_name = self.location.name
        return d
    
    # from ResolveAcronym:
    def acronym(self):
        if self.type_id == "plenary":
            if "Operations and Administration" in self.name:
                return "plenaryw"
            if "Technical" in self.name:
                return "plenaryt"
            for m in self.materials.filter(type="agenda", states__type="agenda", states__slug="active"):
                if "plenaryw" in m.name:
                    return "plenaryw"
                if "plenaryt" in m.name:
                    return "plenaryt"
        if not self.session:
            return "%s" % self.pk
        if hasattr(self, "interim"):
            return "i" + self.session.group.acronym
        else:
            return self.session.group.acronym
    def acronym_lower(self):
        return self.acronym().lower()
    def acronym_name(self):
        if not self.session:
            return self.name
        if hasattr(self, "interim"):
            return self.session.group.name + " (interim)"
        elif self.session.name:
            return self.session.name
        else:
            return self.session.group.name
    def area(self):
        if not self.session or not self.session.group:
            return ""
        if self.session.group.type_id == "irtf":
            return "irtf"
        if self.type_id == "plenary":
            return "1plenary"
        if not self.session.group.parent or not self.session.group.parent.type_id in ["area","irtf","ietf"]:
            return ""
        return self.session.group.parent.acronym
    def area_name(self):
        if self.type_id == "plenary":
            return "Plenary Sessions"
        elif self.session and self.session.group and self.session.group.acronym == "edu":
            return "Training"
        elif not self.session or not self.session.group or not self.session.group.parent or not self.session.group.parent.type_id == "area":
            return ""
        return self.session.group.parent.name
    def isWG(self):
        if not self.session or not self.session.group:
            return False
        if self.session.group.type_id == "wg" and self.session.group.state_id != "bof":
            return True
    def group_type_str(self):
        if not self.session or not self.session.group:
            return ""
        if self.session.group and self.session.group.type_id == "wg":
            if self.session.group.state_id == "bof":
                return "BOF"
            else:
                return "WG"

        return ""
    
    class Meta:
        proxy = True
        
class SlideProxy(Document):
    objects = TranslatingManager(dict(), always_filter=dict(type="slides"))

    SLIDE_TYPE_CHOICES=(
	('1', '(converted) HTML'),
	('2', 'PDF'),
	('3', 'Text'),
	('4', 'PowerPoint -2003 (PPT)'),
	('5', 'Microsoft Word'),
	('6', 'PowerPoint 2007- (PPTX)'),
    )
    #meeting = models.ForeignKey(Meeting, db_column='meeting_num')
    @property
    def meeting_id(self):
        return self.name.split("-")[1]
    #group_acronym_id = models.IntegerField(null=True, blank=True)
    #slide_num = models.IntegerField(null=True, blank=True)
    @property
    def slide_name(self):
        return int(self.name.split("-")[3])
    #slide_type_id = models.IntegerField(choices=SLIDE_TYPE_CHOICES)
    #slide_name = models.CharField(blank=True, max_length=255)
    @property
    def slide_name(self):
        return self.title
    #irtf = models.IntegerField()
    #interim = models.BooleanField()
    #order_num = models.IntegerField(null=True, blank=True)
    @property
    def order_num(self):
        return self.order
    #in_q = models.IntegerField(null=True, blank=True)
    def acronym():
        return self.name.split("-")[2]
    def __str__(self):
	return "IETF%d: %s slides (%s)" % (self.meeting_id, self.acronym(), self.slide_name)
    def file_loc(self):
        return "%s/slides/%s" % (self.meeting_id, self.external_url)
    class Meta:
        proxy = True

class IESGHistoryProxy(Person):
    def from_object(self, base):
        for f in self._meta.fields: # self here to enable us to copy a history object
            setattr(self, f.name, getattr(base, f.name))
        return self

    #meeting = models.ForeignKey(Meeting, db_column='meeting_num')
    def from_role(self, role, time):
        from ietf.utils.history import find_history_active_at
        personhistory = find_history_active_at(role.person, time)
        self.from_object(personhistory or role.person)
        from ietf.group.proxy import Area
        self.area = Area().from_object(role.group)
        return self
    #area = models.ForeignKey(Area, db_column='area_acronym_id')
    #person = models.ForeignKey(PersonOrOrgInfo, db_column='person_or_org_tag')
    @property
    def person(self):
        return self
    #def __str__(self):
    #    return "IESG%s: %s (%s)" % (self.meeting_id, self.person,self.area)
    class Meta:
        proxy = True
