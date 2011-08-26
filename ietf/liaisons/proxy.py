from redesign.proxy_utils import TranslatingManager
from ietf.liaisons.models import LiaisonStatement
from redesign.doc.models import Document

class LiaisonDetailProxy(LiaisonStatement):
    objects = TranslatingManager(dict(submitted_date="submitted",
                                      deadline_date="deadline",
                                      to_body="to_name",
                                      from_raw_body="from_name"))
                                      
    def from_object(self, base):
        for f in base._meta.fields:
            setattr(self, f.name, getattr(base, f.name))
        return self
                
    #detail_id = models.AutoField(primary_key=True)
    @property
    def detail_id(self):
        return self.id
    #person = models.ForeignKey(PersonOrOrgInfo, null=True, db_column='person_or_org_tag')
    @property
    def person(self):
        return self.from_contact.person if self.from_contact else ""
    #submitted_date = models.DateField(null=True, blank=True)
    @property
    def submitted_date(self):
        return self.submitted.date() if self.submitted else None
    #last_modified_date = models.DateField(null=True, blank=True)
    @property
    def last_modified_date(self):
        return self.modified.date() if self.modified else None
    #from_id = models.IntegerField(null=True, blank=True)
    @property
    def from_id(self):
        return self.from_group_id
    #to_body = models.CharField(blank=True, null=True, max_length=255)
    @property
    def to_body(self):
        return self.to_name
    #title = models.CharField(blank=True, null=True, max_length=255) # same name
    #response_contact = models.CharField(blank=True, null=True, max_length=255) # same name
    #technical_contact = models.CharField(blank=True, null=True, max_length=255) # same name
    #purpose_text = models.TextField(blank=True, null=True, db_column='purpose')
    @property
    def purpose_text(self):
        return ""
    #body = models.TextField(blank=True,null=True) # same name
    #deadline_date = models.DateField(null=True, blank=True)
    @property
    def deadline_date(self):
        return self.deadline
    #cc1 = models.TextField(blank=True, null=True)
    @property
    def cc1(self):
        return self.cc
    #cc2 = models.CharField(blank=True, null=True, max_length=50) # unused
    @property
    def cc2(self):
        return ""
    #submitter_name = models.CharField(blank=True, null=True, max_length=255)
    @property
    def submitter_name(self):
        i = self.to_name.find('<')
        if i > 0:
            return self.to_name[:i - 1]
        else:
            return self.to_name
    #submitter_email = models.CharField(blank=True, null=True, max_length=255)
    @property
    def submitter_email(self):
        import re
        re_email = re.compile("<(.*)>")
        match = re_email.search(self.to_name)
        if match:
            return match.group(1)
        else:
            return ""
    #by_secretariat = models.IntegerField(null=True, blank=True)
    @property
    def by_secretariat(self):
        return not self.from_contact
    #to_poc = models.CharField(blank=True, null=True, max_length=255)
    @property
    def to_poc(self):
        return self.to_contact
    #to_email = models.CharField(blank=True, null=True, max_length=255)
    @property
    def to_email(self):
        return ""
    #purpose = models.ForeignKey(LiaisonPurpose,null=True)
    #replyto = models.CharField(blank=True, null=True, max_length=255)
    @property
    def replyto(self):
        return self.reply_to
    #from_raw_body = models.CharField(blank=True, null=True, max_length=255)
    @property
    def from_raw_body(self):
        return self.from_name
    
    def raw_codify(self, group):
        if not group:
            return ""
        if group.type_id in ("sdo", "wg", "area"):
            return "%s_%s" % (group.type_id, group.id)
        return group.acronym
    
    #from_raw_code = models.CharField(blank=True, null=True, max_length=255)
    @property
    def from_raw_code(self):
        return self.raw_codify(self.from_group)
    #to_raw_code = models.CharField(blank=True, null=True, max_length=255)
    @property
    def to_raw_code(self):
        return self.raw_codify(self.to_group)
    #approval = models.ForeignKey(OutgoingLiaisonApproval, blank=True, null=True)
    @property
    def approval(self):
        return bool(self.approved)
    #action_taken = models.BooleanField(default=False, db_column='taken_care') # same name
    #related_to = models.ForeignKey('LiaisonDetail', blank=True, null=True) # same name

    @property
    def uploads_set(self):
        return UploadsProxy.objects.filter(liaisonstatement=self).order_by('name')
    
    @property
    def liaisondetail_set(self):
        return self.liaisonstatement_set
    
    def __str__(self):
	return unicode(self)
    def __unicode__(self):
	return self.title or "<no title>"
    def from_body(self):
        return self.from_name
    def from_sdo(self):
        return self.from_group if self.from_group and self.from_group.type_id == "sdo" else None
    def from_email(self):
        self.from_contact.address
    def get_absolute_url(self):
	return '/liaison/%d/' % self.detail_id
    class Meta:
        proxy = True

    def send_by_email(self, fake=False):
        # grab this from module instead of stuffing in on the model
        from ietf.liaisons.mails import send_liaison_by_email
        # we don't have a request so just pass None for the time being
        return send_liaison_by_email(None, self, fake)

    def is_pending(self):
        return not self.approved

class UploadsProxy(Document):
    #file_id = models.AutoField(primary_key=True)
    @property
    def file_id(self):
        if self.external_url.startswith(self.name):
            return self.name # new data
        else:
            return int(self.external_url.split(".")[0][len(file):]) # old data
    #file_title = models.CharField(blank=True, max_length=255)
    @property
    def file_title(self):
        return self.title
    #person = models.ForeignKey(PersonOrOrgInfo, db_column='person_or_org_tag')
    #file_extension = models.CharField(blank=True, max_length=10)
    @property
    def file_extension(self):
        t = self.external_url.split(".")
        if len(t) > 1:
            return "." + t[1]
        else:
            return ""
    #detail = models.ForeignKey(LiaisonDetail)
    @property
    def detail(self):
        return self.liaisonstatement_set.all()[0]
    def filename(self):
        return self.external_url
    class Meta:
        proxy = True
