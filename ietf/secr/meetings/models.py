from django.db import models
#from sec.core.models import Meeting
"""
import datetime

class GeneralInfo(models.Model):
    id = models.IntegerField(primary_key=True)
    info_name = models.CharField(max_length=150, blank=True)
    info_text = models.TextField(blank=True)
    info_header = models.CharField(max_length=765, blank=True)
    class Meta:
        db_table = u'general_info'

class MeetingVenue(models.Model):
    meeting_num = models.ForeignKey(Meeting, db_column='meeting_num', unique=True, editable=False)
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
    non_session_id = models.AutoField(primary_key=True, editable=False)
    day_id = models.IntegerField(blank=True, null=True, editable=False)
    non_session_ref = models.ForeignKey(NonSessionRef, editable=False)
    meeting = models.ForeignKey(Meeting, db_column='meeting_num', editable=False)
    time_desc = models.CharField(blank=True, max_length=75, default='0')
    show_break_location = models.BooleanField(editable=False, default=True)
    def __str__(self):
        if self.day_id != None:
            return "%s %s %s @%s" % ((self.meeting.start_date + datetime.timedelta(self.day_id)).strftime('%A'), self.time_desc, self.non_session_ref, self.meeting_id)
        else:
            return "** %s %s @%s" % (self.time_desc, self.non_session_ref, self.meeting_id)
    def day(self):
        if self.day_id != None:
            return (self.meeting.start_date + datetime.timedelta(self.day_id)).strftime('%A')
        else:
            return ""
    class Meta:
        db_table = 'non_session'
        verbose_name = "Meeting non-session slot"

"""