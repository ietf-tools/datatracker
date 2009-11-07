# Copyright The IETF Trust 2007, All Rights Reserved

from django.db import models
from ietf.idtracker.models import Acronym, Area

class ImportedMailingList(models.Model):
    group_acronym = models.ForeignKey(Acronym, null=True)
    acronym = models.CharField(maxlength=255, db_column='list_acronym')
    name = models.CharField(blank=True, maxlength=255, db_column='list_name')
    domain = models.CharField(blank=True, maxlength=25, db_column='list_domain')
    def __str__(self):
	return self.acronym or self.group_acronym.acronym
    def choices(dname):
	objects = ImportedMailingList.objects.all().filter(domain__icontains=dname).exclude(acronym__iendswith='announce')
	if dname == "ietf.org":
	    objects = objects.exclude(acronym__istartswith='ietf').exclude(acronym__icontains='iesg')
	return objects
	#return [(list.acronym, list.acronym) for list in objects]
    choices = staticmethod(choices)
    class Meta:
        db_table = 'imported_mailing_list'
    class Admin:
	pass

class NonWgMailingList(models.Model):
    id = models.CharField(primary_key=True, maxlength=35)
    s_name = models.CharField("Submitter's Name", blank=True, maxlength=255)
    s_email = models.EmailField("Submitter's Email Address", blank=True, maxlength=255)
    list_name = models.CharField("Mailing List Name", unique=True, maxlength=255)
    list_url = models.CharField("List URL", maxlength=255)
    admin = models.TextField("Administrator(s)' Email Address(es)", blank=True)
    purpose = models.TextField(blank=True)
    area = models.ForeignKey(Area, db_column='area_acronym_id', null=True)
    subscribe_url = models.CharField("Subscribe URL", blank=True, maxlength=255)
    subscribe_other = models.TextField("Subscribe Other", blank=True)
    # Can be 0, 1, -1, or what looks like a person_or_org_tag, positive or neg.
    # The values less than 1 don't get displayed on the list of lists.
    status = models.IntegerField()
    ds_name = models.CharField(blank=True, maxlength=255)
    ds_email = models.EmailField(blank=True, maxlength=255)
    msg_to_ad = models.TextField(blank=True)
    def __str__(self):
	return self.list_name 
    def choices():
	return [(list.id, list.list_name) for list in NonWgMailingList.objects.all().filter(status__gt=0)]
    choices = staticmethod(choices)
    class Meta:
        db_table = 'none_wg_mailing_list'
	ordering = ['list_name']
    class Admin:
	pass

