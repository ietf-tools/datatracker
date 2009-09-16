# Copyright The IETF Trust 2007, All Rights Reserved

from django.db import models
from ietf.idtracker.models import PersonOrOrgInfo, ChairsHistory
#from django.contrib.auth.models import Permission

# I don't know why the IETF database mostly stores times
# as char(N) instead of TIME.  Until it's important, let's
# keep them as char here too.

# email is not used; the announced_from text is Foo Bar <foo@bar.com>
class AnnouncedFrom(models.Model):
    announced_from_id = models.AutoField(primary_key=True)
    announced_from = models.CharField(blank=True, maxlength=255, db_column='announced_from_value')
    email = models.CharField(blank=True, maxlength=255, db_column='announced_from_email', editable=False)
    #permission = models.ManyToManyField(Permission, limit_choices_to={'codename__endswith':'announcedfromperm'}, filter_interface=models.VERTICAL, verbose_name='Permission Required', blank=True)
    def __str__(self):
	return self.announced_from
    class Meta:
        db_table = 'announced_from'
	#permissions = (
	#    ("ietf_chair_announcedfromperm", "Can send messages from IETF Chair"),
	#    ("iab_chair_announcedfromperm", "Can send messages from IAB Chair"),
	#    ("iad_announcedfromperm", "Can send messages from IAD"),
	#    ("ietf_execdir_announcedfromperm", "Can send messages from IETF Executive Director"),
	#    ("other_announcedfromperm", "Can send announcements from others"),
	#)
    class Admin:
	pass

class AnnouncedTo(models.Model):
    announced_to_id = models.AutoField(primary_key=True)
    announced_to = models.CharField(blank=True, maxlength=255, db_column='announced_to_value')
    email = models.CharField(blank=True, maxlength=255, db_column='announced_to_email')
    def __str__(self):
	return self.announced_to
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
    nomcom_chair = models.ForeignKey(ChairsHistory, null=True, blank=True)
    manually_added = models.BooleanField(db_column='manualy_added')
    other_val = models.CharField(blank=True, maxlength=255)
    def __str__(self):
	return "Announcement from %s to %s on %s %s" % (self.announced_from, self.announced_to, self.announced_date, self.announced_time)
    def from_name(self):
	if self.announced_from_id == 99:
	    return self.other_val
	if self.announced_from_id == 18:	# sigh hardcoding
	    return self.nomcom_chair.person
	return self.announced_from
    class Meta:
        db_table = 'announcements'
    class Admin:
	list_display = ('announced_from', 'announced_to', 'announced_date', 'subject')
	date_hierarchy = 'announced_date'
	list_filter = ['nomcom', 'manually_added']
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
