# Copyright The IETF Trust 2007, All Rights Reserved

from django.db import models
from django.conf import settings
from ietf.idtracker.models import PersonOrOrgInfo, ChairsHistory
#from django.contrib.auth.models import Permission

# I don't know why the IETF database mostly stores times
# as char(N) instead of TIME.  Until it's important, let's
# keep them as char here too.

# email is not used; the announced_from text is Foo Bar <foo@bar.com>
class AnnouncedFrom(models.Model):
    announced_from_id = models.AutoField(primary_key=True)
    announced_from = models.CharField(blank=True, max_length=255, db_column='announced_from_value')
    email = models.CharField(blank=True, max_length=255, db_column='announced_from_email', editable=False)
    #permission = models.ManyToManyField(Permission, limit_choices_to={'codename__endswith':'announcedfromperm'}, verbose_name='Permission Required', blank=True)
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

class AnnouncedTo(models.Model):
    announced_to_id = models.AutoField(primary_key=True)
    announced_to = models.CharField(blank=True, max_length=255, db_column='announced_to_value')
    email = models.CharField(blank=True, max_length=255, db_column='announced_to_email')
    def __str__(self):
	return self.announced_to
    class Meta:
        db_table = 'announced_to'

class Announcement(models.Model):
    announcement_id = models.AutoField(primary_key=True)
    announced_by = models.ForeignKey(PersonOrOrgInfo, db_column='announced_by')
    announced_date = models.DateField(null=True, blank=True)
    announced_time = models.CharField(blank=True, max_length=20)
    text = models.TextField(blank=True, db_column='announcement_text')
    announced_from = models.ForeignKey(AnnouncedFrom)
    cc = models.CharField(blank=True, null=True, max_length=255)
    subject = models.CharField(blank=True, max_length=255)
    extra = models.TextField(blank=True,null=True)
    announced_to = models.ForeignKey(AnnouncedTo)
    nomcom = models.NullBooleanField()
    nomcom_chair = models.ForeignKey(ChairsHistory, null=True, blank=True)
    manually_added = models.BooleanField(db_column='manualy_added')
    other_val = models.CharField(blank=True, null=True, max_length=255)
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

class ScheduledAnnouncement(models.Model):
    mail_sent = models.BooleanField()
    to_be_sent_date = models.DateField(null=True, blank=True)
    to_be_sent_time = models.CharField(blank=True, null=True, max_length=50)
    scheduled_by = models.CharField(blank=True, max_length=100)
    scheduled_date = models.DateField(null=True, blank=True)
    scheduled_time = models.CharField(blank=True, max_length=50)
    subject = models.CharField(blank=True, max_length=255)
    to_val = models.CharField(blank=True, max_length=255)
    from_val = models.CharField(blank=True, max_length=255)
    cc_val = models.TextField(blank=True,null=True)
    body = models.TextField(blank=True)
    actual_sent_date = models.DateField(null=True, blank=True)
    actual_sent_time = models.CharField(blank=True, max_length=50) # should be time, but database contains oddities
    first_q = models.IntegerField(null=True, blank=True)
    second_q = models.IntegerField(null=True, blank=True)
    note = models.TextField(blank=True,null=True)
    content_type = models.CharField(blank=True, max_length=255)
    replyto = models.CharField(blank=True, null=True, max_length=255)
    bcc_val = models.CharField(blank=True, null=True, max_length=255)
    def __str__(self):
	return "Scheduled Announcement from %s to %s on %s %s" % (self.from_val, self.to_val, self.to_be_sent_date, self.to_be_sent_time)
    class Meta:
        db_table = 'scheduled_announcements'


if settings.USE_DB_REDESIGN_PROXY_CLASSES or hasattr(settings, "IMPORTING_FROM_OLD_SCHEMA"):
    import datetime

    from person.models import Email, Person
    from group.models import Group

    class Message(models.Model):
        time = models.DateTimeField(default=datetime.datetime.now)
        by = models.ForeignKey(Person)

        subject = models.CharField(max_length=255)
        frm = models.CharField(max_length=255)
        to = models.CharField(max_length=1024)
        cc = models.CharField(max_length=1024, blank=True)
        bcc = models.CharField(max_length=255, blank=True)
        reply_to = models.CharField(max_length=255, blank=True)
        body = models.TextField()
        content_type = models.CharField(max_length=255, blank=True)

        related_groups = models.ManyToManyField(Group, blank=True)

        class Meta:
            ordering = ['time']

        def __unicode__(self):
            return "'%s' %s -> %s" % (self.subject, self.frm, self.to)

    class SendQueue(models.Model):
        time = models.DateTimeField(default=datetime.datetime.now)
        by = models.ForeignKey(Person)
        
        message = models.ForeignKey(Message)
        
        send_at = models.DateTimeField(blank=True, null=True)
        sent_at = models.DateTimeField(blank=True, null=True)

        note = models.TextField(blank=True)
        
        class Meta:
            ordering = ['time']
