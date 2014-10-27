# Copyright The IETF Trust 2007, All Rights Reserved

from django.db import models

from ietf.doc.models import DocAlias


LICENSE_CHOICES = (
    (0, ''),
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
    (0, 'NO'),
    (1, 'YES'),
    (2, 'NO'),
)
STATUS_CHOICES = (
    ( 0, "Waiting for approval" ), 
    ( 1, "Approved and Posted" ), 
    ( 2, "Rejected by Administrator" ), 
    ( 3, "Removed by Request" ), 
)

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
    country = models.CharField(max_length=255)
    notes = models.TextField("Additional notes", db_column="p_notes", blank=True)
    is_pending = models.IntegerField("Unpublished Pending Patent Application", blank=True, null=True, choices=SELECT_CHOICES, db_column="selecttype")
    applies_to_all = models.IntegerField("Applies to all IPR owned by Submitter", blank=True, null=True, choices=SELECT_CHOICES, db_column="selectowned")

    # Licensing Declaration fieldset
    licensing_option = models.IntegerField(null=True, blank=True, choices=LICENSE_CHOICES)
    lic_opt_a_sub = models.IntegerField(null=True, editable=False, choices=STDONLY_CHOICES)
    lic_opt_b_sub = models.IntegerField(null=True, editable=False, choices=STDONLY_CHOICES)
    lic_opt_c_sub = models.IntegerField(null=True, editable=False, choices=STDONLY_CHOICES)
    comments = models.TextField("Licensing Comments", blank=True)
    lic_checkbox = models.BooleanField("All terms and conditions has been disclosed", default=False)


    # Other notes fieldset
    other_notes = models.TextField(blank=True)

    # Generated fields, not part of the submission form
    # Hidden fields
    third_party = models.BooleanField(default=False)
    generic = models.BooleanField(default=False)
    comply = models.BooleanField(default=False)

    status = models.IntegerField(null=True, blank=True, choices=STATUS_CHOICES)
    submitted_date = models.DateField(blank=True)
    update_notified_date = models.DateField(null=True, blank=True)

    def __unicode__(self):
        return self.title

    @models.permalink
    def get_absolute_url(self):
        return ('ietf.ipr.views.show', [str(self.ipr_id)])

    def get_submitter(self):
	try:
	    return self.contact.get(contact_type=3)
	except IprContact.DoesNotExist:
	    return None
        except IprContact.MultipleObjectsReturned:
            return self.contact.filter(contact_type=3)[0]

    def docs(self):
        return self.iprdocalias_set.select_related("doc_alias", "doc_alias__document").order_by("id")

class IprContact(models.Model):
    TYPE_CHOICES = (
	(1, 'Patent Holder Contact'),
	(2, 'IETF Participant Contact'),
	(3, 'Submitter Contact'),
    )
    contact_id = models.AutoField(primary_key=True)
    ipr = models.ForeignKey(IprDetail, related_name="contact")
    contact_type = models.IntegerField(choices=TYPE_CHOICES)
    name = models.CharField(max_length=255)
    title = models.CharField(blank=True, max_length=255)
    department = models.CharField(blank=True, max_length=255)
    address1 = models.CharField(blank=True, max_length=255)
    address2 = models.CharField(blank=True, max_length=255)
    telephone = models.CharField(blank=True, max_length=25)
    fax = models.CharField(blank=True, max_length=25)
    email = models.EmailField(max_length=255)
    def __str__(self):
	return self.name or '<no name>'


class IprNotification(models.Model):
    ipr = models.ForeignKey(IprDetail)
    notification = models.TextField(blank=True)
    date_sent = models.DateField(null=True, blank=True)
    time_sent = models.CharField(blank=True, max_length=25)
    def __str__(self):
	return "IPR notification for %s sent %s %s" % (self.ipr, self.date_sent, self.time_sent)

class IprUpdate(models.Model):
    ipr = models.ForeignKey(IprDetail, related_name='updates')
    updated = models.ForeignKey(IprDetail, db_column='updated', related_name='updated_by')
    status_to_be = models.IntegerField(null=True, blank=True)
    processed = models.IntegerField(null=True, blank=True)


class IprDocAlias(models.Model):
    ipr = models.ForeignKey(IprDetail)
    doc_alias = models.ForeignKey(DocAlias)
    rev = models.CharField(max_length=2, blank=True)

    def formatted_name(self):
        name = self.doc_alias.name
        if name.startswith("rfc"):
            return name.upper()
        elif self.rev:
            return "%s-%s" % (name, self.rev)
        else:
            return name

    def __unicode__(self):
        if self.rev:
            return u"%s which applies to %s-%s" % (self.ipr, self.doc_alias.name, self.rev)
        else:
            return u"%s which applies to %s" % (self.ipr, self.doc_alias.name)

    class Meta:
        verbose_name = "IPR document alias"
        verbose_name_plural = "IPR document aliases"

