from redesign.proxy_utils import TranslatingManager
from ietf.liaisons.models import LiaisonStatement

class LiaisonDetailProxy(LiaisonStatement):
    objects = TranslatingManager(dict(meeting_num="number"))
                                      
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
        return self.submitted_by
    #submitted_date = models.DateField(null=True, blank=True)
    @property
    def submitted_date(self):
        return self.submitted.date()
    #last_modified_date = models.DateField(null=True, blank=True)
    @property
    def last_modified_date(self):
        return self.modified.date()
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
        return self.deadline.date()
    #cc1 = models.TextField(blank=True, null=True)
    @property
    def cc1(self):
        return self.cc
    #cc2 = models.CharField(blank=True, null=True, max_length=50) # unused
    #submitter_name = models.CharField(blank=True, null=True, max_length=255)
    #submitter_email = models.CharField(blank=True, null=True, max_length=255)
    #by_secretariat = models.IntegerField(null=True, blank=True)
    @property
    def by_secretariat(self):
        return False
    #to_poc = models.CharField(blank=True, null=True, max_length=255)
    @property
    def to_poc(self):
        return self.to_contact
    #to_email = models.CharField(blank=True, null=True, max_length=255) # unused
    #purpose = models.ForeignKey(LiaisonPurpose,null=True)
    #replyto = models.CharField(blank=True, null=True, max_length=255)
    @property
    def replyto(self):
        return self.reply_to
    #from_raw_body = models.CharField(blank=True, null=True, max_length=255)
    @property
    def from_raw_body(self):
        return self.from_name
    #from_raw_code = models.CharField(blank=True, null=True, max_length=255)
    @property
    def from_raw_code(self):
        return self.from_group_id
    #to_raw_code = models.CharField(blank=True, null=True, max_length=255)
    @property
    def to_raw_code(self):
        return self.to_body_id
    #approval = models.ForeignKey(OutgoingLiaisonApproval, blank=True, null=True)
    @property
    def approval(self):
        return bool(self.approved)
    #action_taken = models.BooleanField(default=False, db_column='taken_care') # same name
    #related_to = models.ForeignKey('LiaisonDetail', blank=True, null=True) # same name
    def __str__(self):
	return unicode(self)
    def __unicode__(self):
	return self.title or "<no title>"
    def from_body(self):
        return self.from_name
    def from_sdo(self):
        return self.from_group if self.from_group and self.from_group.type_id == "sdo" else None
    def from_email(self):
        self.from_contact
    def get_absolute_url(self):
	return '/liaison/%d/' % self.detail_id
    class Meta:
        proxy = True

    def notify_pending_by_email(self, fake):
        raise NotImplemented
        from ietf.liaisons.utils import IETFHM

        from_entity = IETFHM.get_entity_by_key(self.from_raw_code)
        if not from_entity:
            return None
        to_email = []
        for person in from_entity.can_approve():
            to_email.append('%s <%s>' % person.email())
        subject = 'New Liaison Statement, "%s" needs your approval' % (self.title)
        from_email = settings.LIAISON_UNIVERSAL_FROM
        body = render_to_string('liaisons/pending_liaison_mail.txt',
                                {'liaison': self,
                                })
        mail = IETFEmailMessage(subject=subject,
                                to=to_email,
                                from_email=from_email,
                                body = body)
        if not fake:
            mail.send()         
        return mail                                                     

    def send_by_email(self, fake=False):
        raise NotImplemented
        if self.is_pending():
            return self.notify_pending_by_email(fake)
        subject = 'New Liaison Statement, "%s"' % (self.title)
        from_email = settings.LIAISON_UNIVERSAL_FROM
        to_email = self.to_poc.split(',')
        cc = self.cc1.split(',')
        if self.technical_contact:
            cc += self.technical_contact.split(',')
        if self.response_contact:
            cc += self.response_contact.split(',')
        bcc = ['statements@ietf.org']
        body = render_to_string('liaisons/liaison_mail.txt',
                                {'liaison': self,
                                })
        mail = IETFEmailMessage(subject=subject,
                                to=to_email,
                                from_email=from_email,
                                cc = cc,
                                bcc = bcc,
                                body = body)
        if not fake:
            mail.send()         
        return mail                                                     

    def is_pending(self):
        return not self.approved
