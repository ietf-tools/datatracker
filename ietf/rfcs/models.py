from django.db import models
from ietf.idtracker.models import PersonOrOrgInfo

class RfcIntendedStatus(models.Model):
    intended_status_id = models.AutoField(primary_key=True)
    status = models.CharField(maxlength=25, db_column='status_value')
    def __str__(self):
        return self.status
    class Meta:
        db_table = 'rfc_intend_status'
	verbose_name = 'RFC Intended Status Field'
    class Admin:
	pass

class RfcStatus(models.Model):
    status_id = models.AutoField(primary_key=True)
    status = models.CharField(maxlength=25, db_column='status_value')
    def __str__(self):
        return self.status
    class Meta:
        db_table = 'rfc_status'
	verbose_name = 'RFC Status'
	verbose_name_plural = 'RFC Statuses'
    class Admin:
	pass

class Rfc(models.Model):
    rfc_number = models.IntegerField(primary_key=True)
    rfc_name = models.CharField(maxlength=200)
    rfc_name_key = models.CharField(maxlength=200, editable=False)
    group_acronym = models.CharField(blank=True, maxlength=8)
    area_acronym = models.CharField(blank=True, maxlength=8)
    status = models.ForeignKey(RfcStatus, db_column="status_id")
    intended_status = models.ForeignKey(RfcIntendedStatus, db_column="intended_status_id")
    fyi_number = models.CharField(blank=True, maxlength=20)
    std_number = models.CharField(blank=True, maxlength=20)
    txt_page_count = models.IntegerField(null=True, blank=True)
    online_version = models.CharField(blank=True, maxlength=3)
    rfc_published_date = models.DateField(null=True, blank=True)
    proposed_date = models.DateField(null=True, blank=True)
    draft_date = models.DateField(null=True, blank=True)
    standard_date = models.DateField(null=True, blank=True)
    historic_date = models.DateField(null=True, blank=True)
    lc_sent_date = models.DateField(null=True, blank=True)
    lc_expiration_date = models.DateField(null=True, blank=True)
    b_sent_date = models.DateField(null=True, blank=True)
    b_approve_date = models.DateField(null=True, blank=True)
    comments = models.TextField(blank=True)
    last_modified_date = models.DateField()
    def __str__(self):
	return "RFC%04d" % ( self.rfc_number )        
    def save(self):
	self.rfc_name_key = self.rfc_name.upper()
	super(Rfc, self).save()
    class Meta:
        db_table = 'rfcs'
	verbose_name = 'RFC'
	verbose_name_plural = 'RFCs'
    class Admin:
	search_fields = ['rfc_name', 'group_acronym', 'area_acronym']
	list_display = ['rfc_number', 'rfc_name']
	pass

class RfcAuthor(models.Model):
    rfc = models.ForeignKey(Rfc, unique=True, db_column='rfc_number', related_name='authors', edit_inline=models.TABULAR)
    person = models.ForeignKey(PersonOrOrgInfo, db_column='person_or_org_tag', raw_id_admin=True, core=True)
    def __str__(self):
        return "%s, %s" % ( self.person.last_name, self.person.first_name)
    class Meta:
        db_table = 'rfc_authors'
	verbose_name = 'RFC Author'

class RfcObsolete(models.Model):
    rfc = models.ForeignKey(Rfc, db_column='rfc_number', raw_id_admin=True, related_name='updates_or_obsoletes')
    action = models.CharField(maxlength=20, core=True)
    rfc_acted_on = models.ForeignKey(Rfc, db_column='rfc_acted_on', raw_id_admin=True, related_name='updated_or_obsoleted_by')
    def __str__(self):
        return "RFC%04d %s RFC%04d" % (self.rfc_id, self.action, self.rfc_acted_on_id)
    class Meta:
        db_table = 'rfcs_obsolete'
	verbose_name = 'RFC updates or obsoletes'
	verbose_name_plural = verbose_name
    class Admin:
	pass

