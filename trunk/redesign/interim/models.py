from django.db import models

class InterimActivities(models.Model):
    id = models.IntegerField(primary_key=True)
    group_acronym_id = models.IntegerField()
    meeting_num = models.IntegerField()
    activity = models.TextField()
    act_date = models.DateField()
    act_time = models.TimeField()
    act_by = models.IntegerField()
    class Meta:
        db_table = u'interim_activities'

class InterimAgenda(models.Model):
    id = models.IntegerField(primary_key=True)
    meeting_num = models.IntegerField()
    group_acronym_id = models.IntegerField()
    filename = models.CharField(max_length=765)
    irtf = models.IntegerField()
    interim = models.IntegerField()
    class Meta:
        db_table = u'interim_agenda'

class InterimInfo(models.Model):
    id = models.IntegerField(primary_key=True)
    group_acronym_id = models.IntegerField(null=True, blank=True)
    meeting_num = models.IntegerField(null=True, blank=True)
    meeting_date = models.CharField(max_length=765, blank=True)
    message_body = models.TextField(blank=True)
    class Meta:
        db_table = u'interim_info'

class InterimMeetings(models.Model):
    meeting_num = models.IntegerField(primary_key=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    city = models.CharField(max_length=765, blank=True)
    state = models.CharField(max_length=765, blank=True)
    country = models.CharField(max_length=765, blank=True)
    time_zone = models.IntegerField(null=True, blank=True)
    ack = models.TextField(blank=True)
    agenda_html = models.TextField(blank=True)
    agenda_text = models.TextField(blank=True)
    future_meeting = models.TextField(blank=True)
    overview1 = models.TextField(blank=True)
    overview2 = models.TextField(blank=True)
    group_acronym_id = models.IntegerField(null=True, blank=True)
    class Meta:
        db_table = u'interim_meetings'

class InterimMinutes(models.Model):
    id = models.IntegerField(primary_key=True)
    meeting_num = models.IntegerField()
    group_acronym_id = models.IntegerField()
    filename = models.CharField(max_length=765)
    irtf = models.IntegerField()
    interim = models.IntegerField()
    class Meta:
        db_table = u'interim_minutes'

class InterimSlides(models.Model):
    id = models.IntegerField(primary_key=True)
    meeting_num = models.IntegerField()
    group_acronym_id = models.IntegerField(null=True, blank=True)
    slide_num = models.IntegerField(null=True, blank=True)
    slide_type_id = models.IntegerField()
    slide_name = models.CharField(max_length=765)
    irtf = models.IntegerField()
    interim = models.IntegerField()
    order_num = models.IntegerField(null=True, blank=True)
    in_q = models.IntegerField(null=True, blank=True)
    class Meta:
        db_table = u'interim_slides'

    def file_loc(self):
        from ietf.idtracker.models import Acronym
        dir = self.meeting_num
        acronym = Acronym.objects.get(pk=self.group_acronym_id).acronym
        if self.slide_type_id==1:
            #return "%s/slides/%s-%s/sld1.htm" % (dir,self.acronym(),self.slide_num)
            return "%s/slides/%s-%s/%s-%s.htm" % (dir,acronym,self.slide_num,self.acronym,self.slide_num)
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
            return "%s/slides/%s-%s%s" % (dir,acronym,self.slide_num,ext)
