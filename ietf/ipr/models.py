import re
from django.db import models
from django.template.defaultfilters import capfirst
from django import oldforms
from django import newforms as forms
from ietf.idtracker.views import InternetDraft
from ietf.idtracker.models import Rfc

# ------------------------------------------------------------------------
# New field classes

phone_re = re.compile(r'^\+?[0-9 ]*(\([0-9]+\))?[0-9 -]+$')
class InternationalPhoneNumberField(models.PhoneNumberField):
    error_message = 'Phone numbers may have a leading "+", and otherwise only contain numbers [0-9], dash, space, and parentheses. '
    def validate(self, field_data, all_data):
        if not phone_re.search(field_data):
            raise ValidationError, self.error_message + ' "%s" is invalid.' % field_data

    def clean(self, value):
        if value in EMPTY_VALUES:
            return u''
        self.validate(value, {})
        return smart_unicode(value)

    def formfield(self, **kwargs):
        defaults = {'required': not self.blank, 'label': capfirst(self.verbose_name),
                    'help_text': self.help_text,
                    'error_message': self.error_message + "Enter a valid phone number."}
        defaults.update(kwargs)
        return forms.RegexField(phone_re, **defaults)


# ------------------------------------------------------------------------
# Models

LICENSE_CHOICES = (
    (1, 'No License Required for Implementers.'),
    (2, 'Royalty-Free, Reasonable and Non-Discriminatory License to All Implementers.'),
    (3, 'Reasonable and Non-Discriminatory License to All Implementers with Possible Royalty/Fee.'),
    (4, 'Licensing Declaration to be Provided Later.'),
    (5, 'Unwilling to Commit to the Provisions.'),
    (6, 'See Text Below for Licensing Declaration.'),
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

# not clear why this has both an ID and selecttype
# Also not clear why a table for "YES" and "NO".
class IprSelecttype(models.Model):
    type_id = models.AutoField(primary_key=True)
    selecttype = models.IntegerField(unique=True)
    type_display = models.CharField(blank=True, maxlength=15)
    def __str__(self):
	return self.type_display
    class Meta:
        db_table = 'ipr_selecttype'
    class Admin:
	pass

class IprLicensing(models.Model):
    licensing_option = models.AutoField(primary_key=True)
    value = models.CharField(maxlength=255, db_column='licensing_option_value')
    def __str__(self):
	return self.value;
    class Meta:
        db_table = 'ipr_licensing'
    class Admin:
	pass


class IprDetail(models.Model):
    ipr_id = models.AutoField(primary_key=True)
    p_h_legal_name = models.CharField("Legal Name", maxlength=255)
    document_title = models.CharField(blank=True, maxlength=255)
    rfc_number = models.IntegerField(null=True, editable=False, blank=True)	# always NULL
    id_document_tag = models.IntegerField(null=True, editable=False, blank=True)	# always NULL
    other_designations = models.CharField(blank=True, maxlength=255)
    p_applications = models.TextField(blank=True, maxlength=255)
    date_applied = models.CharField(blank=True, maxlength=255)
    #selecttype = models.ForeignKey(IprSelecttype, to_field='selecttype', db_column='selecttype')
    selecttype = models.IntegerField(null=True, choices=SELECT_CHOICES)
    discloser_identify = models.TextField(blank=True, maxlength=255, db_column='disclouser_identify')
    #licensing_option = models.ForeignKey(IprLicensing, db_column='licensing_option')
    licensing_option = models.IntegerField(null=True, blank=True, choices=LICENSE_CHOICES)
    other_notes = models.TextField(blank=True)
    submitted_date = models.DateField(null=True, blank=True)
    status = models.IntegerField(null=True, blank=True)
    comments = models.TextField(blank=True)
    old_ipr_url = models.CharField(blank=True, maxlength=255)
    additional_old_title1 = models.CharField(blank=True, maxlength=255)
    additional_old_url1 = models.CharField(blank=True, maxlength=255)
    additional_old_title2 = models.CharField(blank=True, maxlength=255)
    additional_old_url2 = models.CharField(blank=True, maxlength=255)
    country = models.CharField(blank=True, maxlength=100)
    p_notes = models.TextField(blank=True)
    third_party = models.BooleanField(editable=False)
    lic_opt_a_sub = models.IntegerField(editable=False, choices=STDONLY_CHOICES)
    lic_opt_b_sub = models.IntegerField(editable=False, choices=STDONLY_CHOICES)
    lic_opt_c_sub = models.IntegerField(editable=False, choices=STDONLY_CHOICES)
    generic = models.BooleanField(editable=False)
    selectowned = models.IntegerField(null=True, blank=True, choices=SELECT_CHOICES)
    comply = models.BooleanField(editable=False)
    lic_checkbox = models.BooleanField()
    update_notified_date = models.DateField(null=True, blank=True)
    def __str__(self):
	return self.document_title
    def selecttypetext(self):
        if self.selecttype == "1":
            return "YES"
        else:
            return "NO"
    def selectownedtext(self):
        if self.selectowned == "1":
            return "YES"
        else:
            return "NO"
    def get_patent_holder_contact(self):
        try:
            return self.contact.filter(contact_type=1)[0]
        except:
            return None
    def get_ietf_contact(self):
        try:
            return self.contact.filter(contact_type=2)[0]
        except:
            return None
    def get_submitter(self):
        try:
            return self.contact.filter(contact_type=3)[0]
        except:
            return None
    def get_absolute_url(self, item):
        return "http://merlot.tools.ietf.org:31415/ipr/ipr-%s" % ipr_id
    class Meta:
        db_table = 'ipr_detail'
    class Admin:
	pass

class IprContact(models.Model):
    TYPE_CHOICES = (
	('1', 'Patent Holder Contact'),
	('2', 'IETF Participant Contact'),
	('3', 'Submitter Contact'),
    )
    contact_id = models.AutoField(primary_key=True)
    ipr = models.ForeignKey(IprDetail, raw_id_admin=True, editable=False, related_name="contact")
    contact_type = models.IntegerField(editable=False, choices=TYPE_CHOICES)
    name = models.CharField(maxlength=255)
    title = models.CharField(blank=True, maxlength=255)
    department = models.CharField(blank=True, maxlength=255)
    address1 = models.CharField(blank=True, maxlength=255)
    address2 = models.CharField(blank=True, maxlength=255)
    telephone = InternationalPhoneNumberField(maxlength=25)
    fax = InternationalPhoneNumberField(blank=True, maxlength=25)
    email = models.EmailField(maxlength=255)
    def __str__(self):
	return self.name
    class Meta:
        db_table = 'ipr_contacts'
    class Admin:
	pass
    


class IprDraft(models.Model):
    document = models.ForeignKey(InternetDraft, db_column='id_document_tag', raw_id_admin=True)
    ipr = models.ForeignKey(IprDetail, raw_id_admin=True, related_name='drafts')
    revision = models.CharField(maxlength=2)
    def __str__(self):
	return "%s applies to %s-%s" % ( self.ipr, self.document, self.revision )
    class Meta:
        db_table = 'ipr_ids'
    class Admin:
	pass

class IprNotification(models.Model):
    ipr = models.ForeignKey(IprDetail, raw_id_admin=True)
    notification = models.TextField(blank=True)
    date_sent = models.DateField(null=True, blank=True)
    time_sent = models.CharField(blank=True, maxlength=25)
    def __str__(self):
	return "IPR notification for %s sent %s %s" % (self.ipr, self.date_sent, self.time_sent)
    class Meta:
        db_table = 'ipr_notifications'
    class Admin:
	pass

class IprRfc(models.Model):
    ipr = models.ForeignKey(IprDetail, raw_id_admin=True, related_name='rfcs')
    rfc_number = models.ForeignKey(Rfc, db_column='rfc_number', raw_id_admin=True)
    def __str__(self):
	return "%s applies to RFC%04d" % ( self.ipr, self.rfc_number )
    class Meta:
        db_table = 'ipr_rfcs'
    class Admin:
	pass

class IprUpdate(models.Model):
    id = models.IntegerField(primary_key=True)
    ipr = models.ForeignKey(IprDetail, raw_id_admin=True, related_name='updates')
    updated = models.ForeignKey(IprDetail, db_column='updated', raw_id_admin=True, related_name='updated_by')
    status_to_be = models.IntegerField(null=True, blank=True)
    processed = models.IntegerField(null=True, blank=True)
    class Meta:
        db_table = 'ipr_updates'
    class Admin:
	pass
