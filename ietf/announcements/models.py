from django.db import models
from ietf.idtracker.models import PersonOrOrgInfo, ChairsHistory

# I don't know why the IETF database mostly stores times
# as char(N) instead of TIME.  Until it's important, let's
# keep them as char here too.

class AnnouncedFrom(models.Model):
    announced_from_id = models.AutoField(primary_key=True)
    announced_from_value = models.CharField(blank=True, maxlength=255)
    announced_from_email = models.CharField(blank=True, maxlength=255)
    def __str__(self):
	return self.announced_from_value
    class Meta:
        db_table = 'announced_from'
    class Admin:
	pass

class AnnouncedTo(models.Model):
    announced_to_id = models.AutoField(primary_key=True)
    announced_to_value = models.CharField(blank=True, maxlength=255)
    announced_to_email = models.CharField(blank=True, maxlength=255)
    def __str__(self):
	return self.announced_to_value
    class Meta:
        db_table = 'announced_to'
    class Admin:
	pass

class Announcement(models.Model):
    announcement_id = models.AutoField(primary_key=True)
    announced_by = models.ForeignKey(PersonOrOrgInfo, raw_id_admin=True, db_column='announced_by')
    announced_date = models.DateField(null=True, blank=True)
    announced_time = models.CharField(blank=True, maxlength=20)
    text = models.TextField(blank=True, db_column='announcement_text')
    announced_from = models.ForeignKey(AnnouncedFrom)
    cc = models.CharField(blank=True, maxlength=255)
    subject = models.CharField(blank=True, maxlength=255)
    extra = models.TextField(blank=True)
    announced_to = models.ForeignKey(AnnouncedTo)
    nomcom = models.BooleanField()
    nomcom_chair_id = models.IntegerField(null=True, blank=True) # ForeignKey to nomcom chairs
    manually_added = models.BooleanField(db_column='manualy_added')
    other_val = models.CharField(blank=True, maxlength=255)
    def __str__(self):
	return "Announcement from %s to %s on %s %s" % (self.announced_from, self.announced_to, self.announced_date, self.announced_time)
    def from_name(self):
	if self.announced_from_id == 99:
	    return self.other_val
	if self.announced_from_id == 14:	# sigh hardcoding
	    return ChairsHistory.objects.all().get(id=self.nomcom_chair_id).person
	return self.announced_from
    class Meta:
        db_table = 'announcements'
    class Admin:
	pass

class ScheduledAnnouncement(models.Model):
    mail_sent = models.BooleanField()
    to_be_sent_date = models.DateField(null=True, blank=True)
    to_be_sent_time = models.CharField(blank=True, maxlength=50)
    scheduled_by = models.CharField(blank=True, maxlength=100)
    scheduled_date = models.DateField(null=True, blank=True)
    scheduled_time = models.CharField(blank=True, maxlength=50)
    subject = models.CharField(blank=True, maxlength=255)
    to_val = models.CharField(blank=True, maxlength=255)
    from_val = models.CharField(blank=True, maxlength=255)
    cc_val = models.TextField(blank=True)
    body = models.TextField(blank=True)
    actual_sent_date = models.DateField(null=True, blank=True)
    actual_sent_time = models.CharField(blank=True, maxlength=50)
    first_q = models.IntegerField(null=True, blank=True)
    second_q = models.IntegerField(null=True, blank=True)
    note = models.TextField(blank=True)
    content_type = models.CharField(blank=True, maxlength=255)
    replyto = models.CharField(blank=True, maxlength=255)
    bcc_val = models.CharField(blank=True, maxlength=255)
    def __str__(self):
	return "Scheduled Announcement from %s to %s on %s %s" % (self.from_val, self.to_val, self.to_be_sent_date, self.to_be_sent_time)
    class Meta:
        db_table = 'scheduled_announcements'
    class Admin:
	pass
