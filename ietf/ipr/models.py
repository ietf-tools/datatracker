# Copyright The IETF Trust 2007, All Rights Reserved

from django.db import models
#from django import newforms as forms
from ietf.idtracker.views import InternetDraft
from ietf.idtracker.models import Rfc

# ------------------------------------------------------------------------
# Models

LICENSE_CHOICES = (
    (1, 'a) No License Required for Implementers.'),
    (2, 'b) Royalty-Free, Reasonable and Non-Discriminatory License to All Implementers.'),
    (3, 'c) Reasonable and Non-Discriminatory License to All Implementers with Possible Royalty/Fee.'),
    (4, 'd) Licensing Declaration to be Provided Later (implies a willingness'
        ' to commit to the provisions of a), b), or c) above to all implementers;'
        ' otherwise, the next option "Unwilling to Commit to the Provisions of'
        ' a), b), or c) Above". - must be selected).'),
    (5, 'e) Unwilling to Commit to the Provisions of a), b), or c) Above.'),
    (6, 'f) See Text Below for Licensing Declaration.'),
)
STDONLY_CHOICES = (
    (0, ""),
    (1,  "The licensing declaration is limited solely to standards-track IETF documents."),
)
SELECT_CHOICES = (
    ("0", 'NO'),
    ("1", 'YES'),
    ("2", 'NO'),
)
STATUS_CHOICES = (
    ( 0, "Waiting for approval" ), 
    ( 1, "Approved and Posted" ), 
    ( 2, "Rejected by Administrator" ), 
    ( 3, "Removed by Request" ), 
)
# not clear why this has both an ID and selecttype
# Also not clear why a table for "YES" and "NO".
class IprSelecttype(models.Model):
    type_id = models.AutoField(primary_key=True)
    is_pending = models.IntegerField(unique=True, db_column="selecttype")
    type_display = models.CharField(blank=True, max_length=15)
    def __str__(self):
	return self.type_display
    class Meta:
        db_table = 'ipr_selecttype'

class IprLicensing(models.Model):
    licensing_option = models.AutoField(primary_key=True)
    value = models.CharField(max_length=255, db_column='licensing_option_value')
    def __str__(self):
	return self.value;
    class Meta:
        db_table = 'ipr_licensing'


class IprDetail(models.Model):
    ipr_id = models.AutoField(primary_key=True)
    title = models.CharField(blank=True, db_column="document_title", max_length=255)

    # Legacy information fieldset
    legacy_url_0 = models.CharField(blank=True, null=True, db_column="old_ipr_url", max_length=255)
    legacy_url_1 = models.CharField(blank=True, null=True, db_column="additional_old_url1", max_length=255)
    legacy_title_1 = models.CharField(blank=True, null=True, db_column="additional_old_title1", max_length=255)
    legacy_url_2 = models.CharField(blank=True, null=True, db_column="additional_old_url2", max_length=255)
    legacy_title_2 = models.CharField(blank=True, null=True, db_column="additional_old_title2", max_length=255)

    # Patent holder fieldset
    legal_name = models.CharField("Legal Name", db_column="p_h_legal_name", max_length=255)

    # Patent Holder Contact fieldset
    # self.contact.filter(contact_type=1)

    # IETF Contact fieldset
    # self.contact.filter(contact_type=3)
    
    # Related IETF Documents fieldset
    rfc_number = models.IntegerField(null=True, editable=False, blank=True)	# always NULL
    id_document_tag = models.IntegerField(null=True, editable=False, blank=True)	# always NULL
    other_designations = models.CharField(blank=True, max_length=255)
    document_sections = models.TextField("Specific document sections covered", blank=True, max_length=255, db_column='disclouser_identify')

    # Patent Information fieldset
    patents = models.TextField("Patent Applications", db_column="p_applications", max_length=255)
    date_applied = models.CharField(max_length=255)
    country = models.CharField(max_length=100)
    notes = models.TextField("Additional notes", db_column="p_notes", blank=True)
    is_pending = models.IntegerField("Unpublished Pending Patent Application", blank=True, choices=SELECT_CHOICES, db_column="selecttype")
    applies_to_all = models.IntegerField("Applies to all IPR owned by Submitter", blank=True, choices=SELECT_CHOICES, db_column="selectowned")

    # Licensing Declaration fieldset
    #licensing_option = models.ForeignKey(IprLicensing, db_column='licensing_option')
    licensing_option = models.IntegerField(null=True, blank=True, choices=LICENSE_CHOICES)
    lic_opt_a_sub = models.IntegerField(editable=False, choices=STDONLY_CHOICES)
    lic_opt_b_sub = models.IntegerField(editable=False, choices=STDONLY_CHOICES)
    lic_opt_c_sub = models.IntegerField(editable=False, choices=STDONLY_CHOICES)
    comments = models.TextField("Licensing Comments", blank=True)
    lic_checkbox = models.BooleanField("All terms and conditions has been disclosed")


    # Other notes fieldset
    other_notes = models.TextField(blank=True)

    # Generated fields, not part of the submission form
    # Hidden fields
    third_party = models.BooleanField()
    generic = models.BooleanField()
    comply = models.BooleanField()

    status = models.IntegerField(null=True, blank=True, choices=STATUS_CHOICES)
    submitted_date = models.DateField(blank=True)
    update_notified_date = models.DateField(null=True, blank=True)

    def __str__(self):
	return self.title
    def docs(self):
        return list(self.drafts.all()) + list(self.rfcs.all())
    def get_absolute_url(self):
        return "/ipr/%d/" % self.ipr_id
    def get_submitter(self):
	try:
	    return self.contact.get(contact_type=3)
	except IprContact.DoesNotExist:
	    return None
    class Meta:
        db_table = 'ipr_detail'

class IprContact(models.Model):
    TYPE_CHOICES = (
	('1', 'Patent Holder Contact'),
	('2', 'IETF Participant Contact'),
	('3', 'Submitter Contact'),
    )
    contact_id = models.AutoField(primary_key=True)
    ipr = models.ForeignKey(IprDetail, related_name="contact")
    contact_type = models.IntegerField(choices=TYPE_CHOICES)
    name = models.CharField(max_length=255)
    title = models.CharField(blank=True, max_length=255)
    department = models.CharField(blank=True, max_length=255)
    address1 = models.CharField(blank=True, max_length=255)
    address2 = models.CharField(blank=True, max_length=255)
    telephone = models.CharField(max_length=25)
    fax = models.CharField(blank=True, max_length=25)
    email = models.EmailField(max_length=255)
    def __str__(self):
	return self.name or '<no name>'
    class Meta:
        db_table = 'ipr_contacts'


class IprDraft(models.Model):
    ipr = models.ForeignKey(IprDetail, related_name='drafts')
    document = models.ForeignKey(InternetDraft, db_column='id_document_tag', related_name="ipr")
    revision = models.CharField(max_length=2)
    def __str__(self):
	return "%s which applies to %s-%s" % ( self.ipr, self.document, self.revision )
    class Meta:
        db_table = 'ipr_ids'

class IprNotification(models.Model):
    ipr = models.ForeignKey(IprDetail)
    notification = models.TextField(blank=True)
    date_sent = models.DateField(null=True, blank=True)
    time_sent = models.CharField(blank=True, max_length=25)
    def __str__(self):
	return "IPR notification for %s sent %s %s" % (self.ipr, self.date_sent, self.time_sent)
    class Meta:
        db_table = 'ipr_notifications'

class IprRfc(models.Model):
    ipr = models.ForeignKey(IprDetail, related_name='rfcs')
    document = models.ForeignKey(Rfc, db_column='rfc_number', related_name="ipr")
    def __str__(self):
	return "%s applies to RFC%04d" % ( self.ipr, self.document_id )
    class Meta:
        db_table = 'ipr_rfcs'

class IprUpdate(models.Model):
    id = models.IntegerField(primary_key=True)
    ipr = models.ForeignKey(IprDetail, related_name='updates')
    updated = models.ForeignKey(IprDetail, db_column='updated', related_name='updated_by')
    status_to_be = models.IntegerField(null=True, blank=True)
    processed = models.IntegerField(null=True, blank=True)
    class Meta:
        db_table = 'ipr_updates'

# changes done by convert-096.py:changed maxlength to max_length
# removed core
# removed edit_inline
# removed raw_id_admin
