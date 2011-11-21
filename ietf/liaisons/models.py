# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.template.loader import render_to_string
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse as urlreverse
from ietf.idtracker.models import Acronym, PersonOrOrgInfo, Area, IESGLogin
from ietf.liaisons.mail import IETFEmailMessage
from ietf.ietfauth.models import LegacyLiaisonUser
from ietf.utils.admin import admin_link

class LiaisonPurpose(models.Model):
    purpose_id = models.AutoField(primary_key=True)
    purpose_text = models.CharField(blank=True, max_length=50)
    def __str__(self):
	return self.purpose_text
    class Meta:
        db_table = 'liaison_purpose'

class FromBodies(models.Model):
    from_id = models.AutoField(primary_key=True)
    body_name = models.CharField(blank=True, max_length=35)
    poc = models.ForeignKey(PersonOrOrgInfo, db_column='poc', null=True)
    is_liaison_manager = models.BooleanField()
    other_sdo = models.BooleanField()
    email_priority = models.IntegerField(null=True, blank=True)
    def __str__(self):
	return self.body_name
    class Meta:
        db_table = 'from_bodies'
        verbose_name = "From body"
        verbose_name_plural = "From bodies"
    contact_link = admin_link('poc', label='Contact')
    


class OutgoingLiaisonApproval(models.Model):
    approved = models.BooleanField(default=True)
    approval_date = models.DateField(null=True, blank=True)


class LiaisonDetail(models.Model):
    detail_id = models.AutoField(primary_key=True)
    person = models.ForeignKey(PersonOrOrgInfo, null=True, db_column='person_or_org_tag')
    submitted_date = models.DateField(null=True, blank=True)
    last_modified_date = models.DateField(null=True, blank=True)
    from_id = models.IntegerField(null=True, blank=True)
    to_body = models.CharField(blank=True, null=True, max_length=255)
    title = models.CharField(blank=True, null=True, max_length=255)
    response_contact = models.CharField(blank=True, null=True, max_length=255)
    technical_contact = models.CharField(blank=True, null=True, max_length=255)
    purpose_text = models.TextField(blank=True, null=True, db_column='purpose')
    body = models.TextField(blank=True,null=True)
    deadline_date = models.DateField(null=True, blank=True)
    cc1 = models.TextField(blank=True, null=True)
    # unclear why cc2 is a CharField, but it's always
    # either NULL or blank.
    cc2 = models.CharField(blank=True, null=True, max_length=50)
    submitter_name = models.CharField(blank=True, null=True, max_length=255)
    submitter_email = models.CharField(blank=True, null=True, max_length=255)
    by_secretariat = models.IntegerField(null=True, blank=True)
    to_poc = models.CharField(blank=True, null=True, max_length=255)
    to_email = models.CharField(blank=True, null=True, max_length=255)
    purpose = models.ForeignKey(LiaisonPurpose,null=True)
    replyto = models.CharField(blank=True, null=True, max_length=255)
    from_raw_body = models.CharField(blank=True, null=True, max_length=255)
    from_raw_code = models.CharField(blank=True, null=True, max_length=255)
    to_raw_code = models.CharField(blank=True, null=True, max_length=255)
    approval = models.ForeignKey(OutgoingLiaisonApproval, blank=True, null=True)
    action_taken = models.BooleanField(default=False, db_column='taken_care')
    related_to = models.ForeignKey('LiaisonDetail', blank=True, null=True)
    def __str__(self):
	return self.title or "<no title>"
    def __unicode__(self):
	return self.title or "<no title>"
    def from_body(self):
	"""The from_raw_body stores the name of the entity
    sending the liaison.
    For legacy liaisons (the ones with empty from_raw_body)
    the legacy_from_body() is returned."""
        if not self.from_raw_body:
            return self.legacy_from_body()
        return self.from_raw_body
    def from_sdo(self):
	try:
	    name = FromBodies.objects.get(pk=self.from_id).body_name
            sdo = SDOs.objects.get(sdo_name=name)
            return sdo
	except ObjectDoesNotExist:
            return None
    def legacy_from_body(self):
	"""The from_id field is a foreign key for either
	FromBodies or Acronyms, depending on whether it's
	the IETF or not.  There is no flag field saying
	which, so we just try it.  If the index values
	overlap, then this function will be ambiguous
	and will return the value from FromBodies.  Current
	acronym IDs start at 925 so the day of reckoning
	is not nigh."""
	try:
	    from_body = FromBodies.objects.get(pk=self.from_id)
	    return from_body.body_name
	except ObjectDoesNotExist:
	    pass
	try:
	    acronym = Acronym.objects.get(pk=self.from_id)
            try:
                x = acronym.area
		kind = "AREA"
            except Area.DoesNotExist:
                kind = "WG"
	    return "IETF %s %s" % (acronym.acronym.upper(), kind)
	except ObjectDoesNotExist:
	    pass
	return "<unknown body %s>" % self.from_id
    def from_email(self):
	"""If there is an entry in from_bodies, it has
	the desired email priority.  However, if it's from
	an IETF WG, there is no entry in from_bodies, so
	default to 1."""
	try:
	    from_body = FromBodies.objects.get(pk=self.from_id)
	    email_priority = from_body.email_priority
	except FromBodies.DoesNotExist:
	    email_priority = 1
	return self.person.emailaddress_set.all().get(priority=email_priority)
    def get_absolute_url(self):
	return '/liaison/%d/' % self.detail_id
    class Meta:
        db_table = 'liaison_detail'

    def notify_pending_by_email(self, fake):
        from ietf.liaisons.utils import IETFHM

        from_entity = IETFHM.get_entity_by_key(self.from_raw_code)
        if not from_entity:
            return None
        to_email = []
        for person in from_entity.can_approve():
            to_email.append('%s <%s>' % person.email())
        subject = 'New Liaison Statement, "%s" needs your approval' % (self.title)
        from_email = settings.LIAISON_UNIVERSAL_FROM
        body = render_to_string('liaisons/pending_liaison_mail.txt', {
                'liaison': self,
                'url': settings.IDTRACKER_BASE_URL + urlreverse("liaison_approval_detail", kwargs=dict(object_id=self.pk)),
                'referenced_url': settings.IDTRACKER_BASE_URL + urlreverse("liaison_detail", kwargs=dict(object_id=self.related_to.pk)) if self.related_to else None,
                })
        mail = IETFEmailMessage(subject=subject,
                                to=to_email,
                                from_email=from_email,
                                body = body)
        if not fake:
            mail.send()         
        return mail                                                     

    def send_by_email(self, fake=False):
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
        body = render_to_string('liaisons/liaison_mail.txt', {
                'liaison': self,
                'url': settings.IDTRACKER_BASE_URL + urlreverse("liaison_detail", kwargs=dict(object_id=self.pk)),
                'referenced_url': settings.IDTRACKER_BASE_URL + urlreverse("liaison_detail", kwargs=dict(object_id=self.related_to.pk)) if self.related_to else None,
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
        return bool(self.approval and not self.approval.approved)


class SDOs(models.Model):
    sdo_id = models.AutoField(primary_key=True, verbose_name='ID')
    sdo_name = models.CharField(blank=True, max_length=255, verbose_name='SDO Name')
    def __str__(self):
	return self.sdo_name
    def liaisonmanager(self):
	try:
	    return self.liaisonmanagers_set.all()[0]
	except:
	    return None
    def sdo_contact(self):
	try:
	    return self.sdoauthorizedindividual_set.all()[0]
	except:
	    return None
    class Meta:
        verbose_name = 'SDO'
        verbose_name_plural = 'SDOs'
        db_table = 'sdos'
        ordering = ('sdo_name', )
    liaisonmanager_link = admin_link('liaisonmanager', label='Liaison')
    sdo_contact_link = admin_link('sdo_contact')

class LiaisonStatementManager(models.Model):
    person = models.ForeignKey(PersonOrOrgInfo, db_column='person_or_org_tag')
    sdo = models.ForeignKey(SDOs, verbose_name='SDO')
    def __unicode__(self):
        return '%s (%s)' % (self.person, self.sdo)
    class Meta:
        abstract = True
    # Helper functions, for use in the admin interface
    def login_name(self):
        login_name = None
        try:
            login_name = IESGLogin.objects.get(person=self.person).login_name
            if User.objects.filter(username=login_name).count():
                return login_name            
        except IESGLogin.DoesNotExist:
            pass
        try:
            login_name = LegacyLiaisonUser.objects.get(person=self.person).login_name
        except LegacyLiaisonUser.DoesNotExist:
            pass
        return login_name
    def user(self):
        login_name = self.login_name()
        user = None
        if login_name:
            try:
                return User.objects.get(username=login_name), login_name
            except User.DoesNotExist:
                pass
        return None, login_name
    def user_name(self):
        user, login_name = self.user()
        if user:
            return u'<a href="/admin/auth/user/%s/">%s</a>' % (user.id, login_name)
        else:
            if login_name:
                return u'Add login: <a href="/admin/auth/user/add/?username=%s"><span style="color: red">%s</span></a>' % (login_name, login_name)
            else:
                return u'Add liaison user: <a href="/admin/ietfauth/legacyliaisonuser/add/?person=%s&login_name=%s&user_level=3"><span style="color: red">%s</span></a>' % (self.person.pk, self.person.email()[1], self.person, )
                
    user_name.allow_tags = True
    def groups(self):
        user, login_name = self.user()
        return ", ".join([ group.name for group in user.groups.all()])
    person_link = admin_link('person')
    sdo_link = admin_link('sdo', label='SDO')
        
class LiaisonManagers(LiaisonStatementManager):
    email_priority = models.IntegerField(null=True, blank=True)
    def email(self):
	try:
	    return self.person.emailaddress_set.get(priority=self.email_priority)
	except ObjectDoesNotExist:
	    return None
    class Meta:
        verbose_name = 'SDO Liaison Manager'
        verbose_name_plural = 'SDO Liaison Managers'
        db_table = 'liaison_managers'
        ordering = ('sdo__sdo_name', )

class SDOAuthorizedIndividual(LiaisonStatementManager):
    class Meta:
        verbose_name = 'SDO Authorized Individual'
        verbose_name_plural = 'SDO Authorized Individuals'

# This table is not used by any code right now.
#class LiaisonsInterim(models.Model):
#    title = models.CharField(blank=True, max_length=255)
#    submitter_name = models.CharField(blank=True, max_length=255)
#    submitter_email = models.CharField(blank=True, max_length=255)
#    submitted_date = models.DateField(null=True, blank=True)
#    from_id = models.IntegerField(null=True, blank=True)
#    def __str__(self):
#	return self.title
#    class Meta:
#        db_table = 'liaisons_interim'

class Uploads(models.Model):
    file_id = models.AutoField(primary_key=True)
    file_title = models.CharField(blank=True, max_length=255)
    person = models.ForeignKey(PersonOrOrgInfo, db_column='person_or_org_tag')
    file_extension = models.CharField(blank=True, max_length=10)
    detail = models.ForeignKey(LiaisonDetail)
    def __str__(self):
	return self.file_title
    def filename(self):
        return "file%s%s" % (self.file_id, self.file_extension)
    class Meta:
        db_table = 'uploads'

# empty table
#class SdoChairs(models.Model):
#    sdo = models.ForeignKey(SDOs)
#    person = models.ForeignKey(PersonOrOrgInfo, db_column='person_or_org_tag')
#    email_priority = models.IntegerField(null=True, blank=True)
#    class Meta:
#        db_table = 'sdo_chairs'

# changes done by convert-096.py:changed maxlength to max_length
# removed core
# removed edit_inline
# removed num_in_admin
# removed raw_id_admin

if settings.USE_DB_REDESIGN_PROXY_CLASSES or hasattr(settings, "IMPORTING_FROM_OLD_SCHEMA"):
    from redesign.name.models import LiaisonStatementPurposeName
    from redesign.doc.models import Document
    from redesign.person.models import Email
    from redesign.group.models import Group
    
    class LiaisonStatement(models.Model):
        title = models.CharField(blank=True, max_length=255)
        purpose = models.ForeignKey(LiaisonStatementPurposeName)
        body = models.TextField(blank=True)
        deadline = models.DateField(null=True, blank=True)
        
        related_to = models.ForeignKey('LiaisonStatement', blank=True, null=True)
        
        from_group = models.ForeignKey(Group, related_name="liaisonstatement_from_set", null=True, blank=True, help_text="Sender group, if it exists")
        from_name = models.CharField(max_length=255, help_text="Name of the sender body")
        from_contact = models.ForeignKey(Email, blank=True, null=True)
        to_group = models.ForeignKey(Group, related_name="liaisonstatement_to_set", null=True, blank=True, help_text="Recipient group, if it exists")
        to_name = models.CharField(max_length=255, help_text="Name of the recipient body")
        to_contact = models.CharField(blank=True, max_length=255, help_text="Contacts at recipient body")
        
        reply_to = models.CharField(blank=True, max_length=255)
        
        response_contact = models.CharField(blank=True, max_length=255)
        technical_contact = models.CharField(blank=True, max_length=255)
        cc = models.TextField(blank=True)
        
        submitted = models.DateTimeField(null=True, blank=True)
        modified = models.DateTimeField(null=True, blank=True)
        approved = models.DateTimeField(null=True, blank=True)

        action_taken = models.BooleanField(default=False)

        attachments = models.ManyToManyField(Document, blank=True)

        def name(self):
            from django.template.defaultfilters import slugify
            if self.from_group:
                frm = self.from_group.acronym or self.from_group.name
            else:
                frm = self.from_name
            if self.to_group:
                to = self.to_group.acronym or self.to_group.name
            else:
                to = self.to_name
            return slugify("liaison" + " " + self.submitted.strftime("%Y-%m-%d") + " " + frm[:50] + " " + to[:50] + " " + self.title[:115])
        
        def __unicode__(self):
            return self.title or "<no title>"

        LiaisonDetailOld = LiaisonDetail
