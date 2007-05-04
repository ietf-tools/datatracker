from django.db import models
from ietf.idtracker.models import Acronym, PersonOrOrgInfo, IRTF
import datetime

# group_acronym is either an IETF Acronym
#  or an IRTF one, depending on the value of irtf.
#  Multiple inheritance to the rescue.
#
# interim = i prefix (complicated because you have to check if self has
#    an interim attribute first)
class ResolveAcronym(object):
    def acronym(self):
	try:
	    interim = self.interim
	except AttributeError:
	    interim = False
	if self.irtf:
	    acronym = IRTF.objects.get(pk=self.group_acronym_id).acronym
	else:
	    acronym = Acronym.objects.get(pk=self.group_acronym_id).acronym
	if interim:
	    return "i" + acronym
	return acronym

class Meeting(models.Model):
    meeting_num = models.IntegerField(primary_key=True)
    start_date = models.DateField()
    end_date = models.DateField()
    city = models.CharField(blank=True, maxlength=255)
    state = models.CharField(blank=True, maxlength=255)
    country = models.CharField(blank=True, maxlength=255)
    ack = models.TextField(blank=True)
    agenda_html = models.TextField(blank=True)
    agenda_text = models.TextField(blank=True)
    future_meeting = models.TextField(blank=True)
    overview1 = models.TextField(blank=True)
    overview2 = models.TextField(blank=True)
    def __str__(self):
	return "IETF %d" % (self.meeting_num)
    class Meta:
        db_table = 'meetings'
    class Admin:
	pass

class MeetingVenue(models.Model):
    meeting_num = models.ForeignKey(Meeting, db_column='meeting_num', unique=True)
    break_area_name = models.CharField(maxlength=255)
    reg_area_name = models.CharField(maxlength=255)
    def __str__(self):
	return "IETF %d" % (self.meeting_num_id)
    class Meta:
        db_table = 'meeting_venues'
    class Admin:
	pass

class NonSessionRef(models.Model):
    name = models.CharField(maxlength=255)
    class Meta:
        db_table = 'non_session_ref'

class NonSession(models.Model):
    day_id = models.IntegerField()
    non_session_ref = models.ForeignKey(NonSessionRef)
    meeting_num = models.ForeignKey(Meeting, db_column='meeting_num', unique=True)
    time_desc = models.CharField(blank=True, maxlength=75)
    class Meta:
        db_table = 'non_session'

class Proceeding(models.Model):
    meeting_num = models.ForeignKey(Meeting, db_column='meeting_num', unique=True, primary_key=True)
    dir_name = models.CharField(blank=True, maxlength=25)
    sub_begin_date = models.DateField(null=True, blank=True)
    sub_cut_off_date = models.DateField(null=True, blank=True)
    frozen = models.IntegerField(null=True, blank=True)
    c_sub_cut_off_date = models.DateField(null=True, blank=True)
    pr_from_date = models.DateField(null=True, blank=True)
    pr_to_date = models.DateField(null=True, blank=True)
    def __str__(self):
	return "IETF %d" % (self.meeting_num_id)
    class Meta:
        db_table = 'proceedings'
	ordering = ['?']	# workaround for FK primary key
    #class Admin:
    #    pass		# admin site doesn't like something about meeting_num

class SessionConflict(models.Model):
    group_acronym = models.ForeignKey(Acronym, raw_id_admin=True, related_name='conflicts_set')
    conflict_gid = models.ForeignKey(Acronym, raw_id_admin=True, related_name='conflicts_with_set', db_column='conflict_gid')
    meeting_num = models.ForeignKey(Meeting, db_column='meeting_num')
    def __str__(self):
	return "At IETF %d, %s conflicts with %s" % ( self.meeting_num_id, self.group_acronym.acronym, self.conflict_gid.acronym)
    class Meta:
        db_table = 'session_conflicts'
    class Admin:
	pass

class SessionName(models.Model):
    session_name_id = models.AutoField(primary_key=True)
    session_name = models.CharField(blank=True, maxlength=255)
    def __str__(self):
	return self.session_name
    class Meta:
        db_table = 'session_names'
    class Admin:
	pass

class MeetingTime(models.Model):
    time_id = models.AutoField(primary_key=True)
    time_desc = models.CharField(maxlength=100)
    meeting = models.ForeignKey(Meeting, db_column='meeting_num', unique=True)
    day_id = models.IntegerField()
    session_name = models.ForeignKey(SessionName)
    def __str__(self):
	return "[%d] |%s| %s" % (self.meeting_id, (self.meeting.start_date + datetime.timedelta(self.day_id)).strftime('%A'), self.time_desc)
    class Meta:
        db_table = 'meeting_times'
    class Admin:
	pass

class MeetingRoom(models.Model):
    room_id = models.AutoField(primary_key=True)
    meeting = models.ForeignKey(Meeting, db_column='meeting_num')
    room_name = models.CharField(maxlength=255)
    def __str__(self):
	return "[%d] %s" % (self.meeting_id, self.room_name)
    class Meta:
        db_table = 'meeting_rooms'
    class Admin:
	pass

class WgMeetingSession(models.Model, ResolveAcronym):
    session_id = models.AutoField(primary_key=True)
    meeting = models.ForeignKey(Meeting, db_column='meeting_num')
    group_acronym_id = models.IntegerField()
    irtf = models.BooleanField()
    num_session = models.IntegerField()
    length_session1 = models.CharField(blank=True, maxlength=100)
    length_session2 = models.CharField(blank=True, maxlength=100)
    length_session3 = models.CharField(blank=True, maxlength=100)
    conflict1 = models.CharField(blank=True, maxlength=255)
    conflict2 = models.CharField(blank=True, maxlength=255)
    conflict3 = models.CharField(blank=True, maxlength=255)
    conflict_other = models.TextField(blank=True)
    special_req = models.TextField(blank=True)
    number_attendee = models.IntegerField(null=True, blank=True)
    approval_ad = models.IntegerField(null=True, blank=True)
    status_id = models.IntegerField(null=True, blank=True)
    ts_status_id = models.IntegerField(null=True, blank=True)
    requested_date = models.DateField(null=True, blank=True)
    approved_date = models.DateField(null=True, blank=True)
    requested_by = models.ForeignKey(PersonOrOrgInfo, raw_id_admin=True, db_column='requested_by')
    scheduled_date = models.DateField(null=True, blank=True)
    last_modified_date = models.DateField(null=True, blank=True)
    ad_comments = models.TextField(blank=True)
    sched_room_id1 = models.ForeignKey(MeetingRoom, db_column='sched_room_id1', null=True, blank=True, related_name='here1')
    sched_time_id1 = models.ForeignKey(MeetingTime, db_column='sched_time_id1', null=True, blank=True, related_name='now1')
    sched_date1 = models.DateField(null=True, blank=True)
    sched_room_id2 = models.ForeignKey(MeetingRoom, db_column='sched_room_id2', null=True, blank=True, related_name='here2')
    sched_time_id2 = models.ForeignKey(MeetingTime, db_column='sched_time_id2', null=True, blank=True, related_name='now2')
    sched_date2 = models.DateField(null=True, blank=True)
    sched_room_id3 = models.ForeignKey(MeetingRoom, db_column='sched_room_id3', null=True, blank=True, related_name='here3')
    sched_time_id3 = models.ForeignKey(MeetingTime, db_column='sched_time_id3', null=True, blank=True, related_name='now3')
    sched_date3 = models.DateField(null=True, blank=True)
    special_agenda_note = models.CharField(blank=True, maxlength=255)
    combined_room_id1 = models.ForeignKey(MeetingRoom, db_column='combined_room_id1', null=True, blank=True, related_name='here4')
    combined_time_id1 = models.ForeignKey(MeetingTime, db_column='combined_time_id1', null=True, blank=True, related_name='now4')
    combined_room_id2 = models.ForeignKey(MeetingRoom, db_column='combined_room_id2', null=True, blank=True, related_name='here5')
    combined_time_id2 = models.ForeignKey(MeetingTime, db_column='combined_time_id2', null=True, blank=True, related_name='now5')
    def __str__(self):
	return "%s at %s" % (self.acronym(), self.meeting)
    class Meta:
        db_table = 'wg_meeting_sessions'
    class Admin:
	pass

class WgAgenda(models.Model, ResolveAcronym):
    meeting = models.ForeignKey(Meeting, db_column='meeting_num')
    group_acronym_id = models.IntegerField()
    filename = models.CharField(maxlength=255)
    irtf = models.BooleanField()
    interim = models.BooleanField()
    def __str__(self):
	return "Agenda for %s at IETF %d" % (self.acronym(), self.meeting_id)
    class Meta:
        db_table = 'wg_agenda'
    class Admin:
	pass

class Minute(models.Model, ResolveAcronym):
    meeting = models.ForeignKey(Meeting, db_column='meeting_num')
    group_acronym = models.ForeignKey(Acronym, raw_id_admin=True)
    filename = models.CharField(blank=True, maxlength=255)
    irtf = models.BooleanField()
    interim = models.BooleanField()
    def __str__(self):
	return "Minutes for %s at IETF %d" % (self.acronym(), self.meeting_id)
    class Meta:
        db_table = 'minutes'
    class Admin:
	pass

# It looks like Switches was meant for something bigger, but
# is only used for the agenda generation right now so we'll
# put it here.
class Switches(models.Model):
    name = models.CharField(maxlength=100)
    val = models.IntegerField(null=True, blank=True)
    updated_date = models.DateField(null=True, blank=True)
    updated_time = models.TimeField(null=True, blank=True)
    def __str__(self):
	return self.name
    class Meta:
        db_table = 'switches'
    class Admin:
	pass

# Empty table, don't pretend that it exists.
#class SlideTypes(models.Model):
#    type_id = models.AutoField(primary_key=True)
#    type = models.CharField(maxlength=255, db_column='type_name')
#    def __str__(self):
#	return self.type
#    class Meta:
#        db_table = 'slide_types'
#    class Admin:
#	pass

class Slide(models.Model, ResolveAcronym):
    SLIDE_TYPE_CHOICES=(
	('1', '(converted) HTML'),
	('2', 'PDF'),
	('3', 'Text'),
	('4', 'PowerPoint'),
	('5', 'Microsoft Word'),
    )
    meeting = models.ForeignKey(Meeting, db_column='meeting_num')
    group_acronym_id = models.IntegerField(null=True, blank=True)
    slide_num = models.IntegerField(null=True, blank=True)
    slide_type_id = models.IntegerField(choices=SLIDE_TYPE_CHOICES)
    slide_name = models.CharField(blank=True, maxlength=255)
    irtf = models.BooleanField()
    interim = models.BooleanField()
    order_num = models.IntegerField(null=True, blank=True)
    in_q = models.IntegerField(null=True, blank=True)
    def __str__(self):
	return "IETF%d: %s slides (%s)" % (self.meeting_id, self.acronym(), self.slide_name)
    class Meta:
        db_table = 'slides'
    class Admin:
	pass
