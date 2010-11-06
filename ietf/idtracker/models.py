# Copyright The IETF Trust 2007, All Rights Reserved

import os.path
import datetime
import re

from django.conf import settings
from django.db import models
from ietf.utils import FKAsOneToOne
from ietf.utils.broken_foreign_key import BrokenForeignKey
from ietf.utils.cached_lookup_field import CachedLookupField

class Acronym(models.Model):
    INDIVIDUAL_SUBMITTER = 1027
    
    acronym_id = models.AutoField(primary_key=True)
    acronym = models.CharField(max_length=12)
    name = models.CharField(max_length=100)
    name_key = models.CharField(max_length=50, editable=False)
    def save(self):
        self.name_key = self.name.upper()
	super(Acronym, self).save()
    def __str__(self):
        return self.acronym
    class Meta:
        db_table = "acronym"

class AreaStatus(models.Model):
    status_id = models.AutoField(primary_key=True)
    status = models.CharField(max_length=25, db_column='status_value')
    def __str__(self):
	return self.status
    class Meta:
        verbose_name = "Area Status"
        verbose_name_plural = "Area Statuses"
        db_table = 'area_status'

# I think equiv_group_flag is historical.
class IDState(models.Model):
    PUBLICATION_REQUESTED = 10
    LAST_CALL_REQUESTED = 15
    IN_LAST_CALL = 16
    WAITING_FOR_WRITEUP = 18
    WAITING_FOR_AD_GO_AHEAD = 19
    IESG_EVALUATION = 20
    IESG_EVALUATION_DEFER = 21
    APPROVED_ANNOUNCEMENT_SENT = 30
    AD_WATCHING = 42
    DEAD = 99
    DO_NOT_PUBLISH_STATES = (33, 34)
    
    document_state_id = models.AutoField(primary_key=True)
    state = models.CharField(max_length=50, db_column='document_state_val')
    equiv_group_flag = models.IntegerField(null=True, blank=True)
    description = models.TextField(blank=True, db_column='document_desc')
    def __str__(self):
        return self.state
    def choices():
	return [(state.document_state_id, state.state) for state in IDState.objects.all()]
    choices = staticmethod(choices)
    class Meta:
        db_table = 'ref_doc_states_new'
	ordering = ['document_state_id']

class IDNextState(models.Model):
    cur_state = models.ForeignKey(IDState, related_name='nextstate')
    next_state = models.ForeignKey(IDState, related_name='prevstate')
    condition = models.CharField(blank=True, max_length=255)
    def __str__(self):
	return "%s -> %s" % (self.cur_state.state, self.next_state.state )
    class Meta:
        db_table = 'ref_next_states_new'

class IDSubState(models.Model):
    sub_state_id = models.AutoField(primary_key=True)
    sub_state = models.CharField(max_length=55, db_column='sub_state_val')
    description = models.TextField(blank=True, db_column='sub_state_desc')
    def __str__(self):
        return self.sub_state
    class Meta:
        db_table = 'sub_state'
	ordering = ['sub_state_id']

class Area(models.Model):
    ACTIVE=1
    area_acronym = models.OneToOneField(Acronym, primary_key=True)
    start_date = models.DateField(auto_now_add=True)
    concluded_date = models.DateField(null=True, blank=True)
    status = models.ForeignKey(AreaStatus)
    comments = models.TextField(blank=True)
    last_modified_date = models.DateField(auto_now=True)
    extra_email_addresses = models.TextField(blank=True,null=True)
    def __str__(self):
	return self.area_acronym.acronym
    def additional_urls(self):
        return AreaWGURL.objects.filter(name=self.area_acronym.name)
    def active_wgs(self):
        return IETFWG.objects.filter(group_type=1,status=IETFWG.ACTIVE,areagroup__area=self).order_by('group_acronym__acronym')
    def active_areas():
        return Area.objects.filter(status=Area.ACTIVE).order_by('area_acronym__acronym')
    active_areas = staticmethod(active_areas)
    class Meta:
        db_table = 'areas'
	verbose_name="area"

class AreaWGURL(models.Model):
    id = models.AutoField(primary_key=True, db_column='area_ID')
    # For WGs, this is the WG acronym; for areas, it's the area name.
    name = models.CharField(max_length=50, db_column='area_Name')
    url = models.CharField(max_length=50)
    description = models.CharField(max_length=50)
    def __unicode__(self):
        return u'%s (%s)' % (self.name, self.description)
    class Meta:
        ordering = ['name']
        verbose_name = "Area/WG URL"
        db_table = "wg_www_pages"

class IDStatus(models.Model):
    status_id = models.AutoField(primary_key=True)
    status = models.CharField(max_length=25, db_column='status_value')
    def __str__(self):
        return self.status
    class Meta:
        db_table = "id_status"
	verbose_name="I-D Status"
	verbose_name_plural="I-D Statuses"

class IDIntendedStatus(models.Model):
    intended_status_id = models.AutoField(primary_key=True)
    intended_status = models.CharField(max_length=25, db_column='status_value')
    def __str__(self):
        return self.intended_status
    class Meta:
        db_table = "id_intended_status"
	verbose_name="I-D Intended Publication Status"
	verbose_name_plural="I-D Intended Publication Statuses"

class InternetDraft(models.Model):
    DAYS_TO_EXPIRE=185
    id_document_tag = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255, db_column='id_document_name')
    id_document_key = models.CharField(max_length=255, editable=False)
    group = models.ForeignKey(Acronym, db_column='group_acronym_id')
    filename = models.CharField(max_length=255, unique=True)
    revision = models.CharField(max_length=2)
    revision_date = models.DateField()
    file_type = models.CharField(max_length=20)
    txt_page_count = models.IntegerField()
    local_path = models.CharField(max_length=255, blank=True, null=True)
    start_date = models.DateField()
    expiration_date = models.DateField(null=True)
    abstract = models.TextField()
    dunn_sent_date = models.DateField(null=True, blank=True)
    extension_date = models.DateField(null=True, blank=True)
    status = models.ForeignKey(IDStatus)
    intended_status = models.ForeignKey(IDIntendedStatus)
    lc_sent_date = models.DateField(null=True, blank=True)
    lc_changes = models.CharField(max_length=3,null=True)
    lc_expiration_date = models.DateField(null=True, blank=True)
    b_sent_date = models.DateField(null=True, blank=True)
    b_discussion_date = models.DateField(null=True, blank=True)
    b_approve_date = models.DateField(null=True, blank=True)
    wgreturn_date = models.DateField(null=True, blank=True)
    rfc_number = models.IntegerField(null=True, blank=True, db_index=True)
    comments = models.TextField(blank=True,null=True)
    last_modified_date = models.DateField()
    replaced_by = BrokenForeignKey('self', db_column='replaced_by', blank=True, null=True, related_name='replaces_set')
    replaces = FKAsOneToOne('replaces', reverse=True)
    review_by_rfc_editor = models.BooleanField()
    expired_tombstone = models.BooleanField()
    idinternal = FKAsOneToOne('idinternal', reverse=True, query=models.Q(rfc_flag = 0))
    def __str__(self):
        return self.filename
    def save(self):
        self.id_document_key = self.title.upper()
        super(InternetDraft, self).save()
    def displayname(self):
        return self.filename
    def file_tag(self):
        return "<%s>" % (self.filename_with_rev())
    def filename_with_rev(self):
        return "%s-%s.txt" % (self.filename, self.revision_display())
    def group_acronym(self):
	return self.group.acronym
    def group_ml_archive(self):
	return self.group.ietfwg.clean_email_archive()
    def idstate(self):
	idinternal = self.idinternal
	if idinternal:
	    return idinternal.docstate()
	else:
	    return "I-D Exists"
    def revision_display(self):
	r = int(self.revision)
	if self.status.status != 'Active' and not self.expired_tombstone:
	   r = max(r - 1, 0)
	return "%02d" % r
    def expiration(self):
        return self.revision_date + datetime.timedelta(self.DAYS_TO_EXPIRE)
    def can_expire(self):
        # Copying the logic from expire-ids-1 without thinking
        # much about it.
        if self.review_by_rfc_editor:
            return False
        idinternal = self.idinternal
        if idinternal:
            cur_state_id = idinternal.cur_state_id
            # 42 is "AD is Watching"; this matches what's in the
            # expire-ids-1 perl script.
            # A better way might be to add a column to the table
            # saying whether or not a document is prevented from
            # expiring.
            if cur_state_id < 42:
                return False
        return True

    def clean_abstract(self):
        # Cleaning based on what "id-abstracts-text" script does
        a = self.abstract
        a = re.sub(" *\r\n *", "\n", a)  # get rid of DOS line endings
        a = re.sub(" *\r *", "\n", a)  # get rid of MAC line endings
        a = re.sub("(\n *){3,}", "\n\n", a)  # get rid of excessive vertical whitespace
        a = re.sub("\f[\n ]*[^\n]*\n", "", a)  # get rid of page headers
        # Get rid of 'key words' boilerplate and anything which follows it:
        # (No way that is part of the abstract...)
        a = re.sub("(?s)(Conventions [Uu]sed in this [Dd]ocument|Requirements [Ll]anguage)?[\n ]*The key words \"MUST\", \"MUST NOT\",.*$", "", a)
        # Get rid of status/copyright boilerplate
        a = re.sub("(?s)\nStatus of [tT]his Memo\n.*$", "", a)
        # wrap long lines without messing up formatting of Ok paragraphs:
        while re.match("([^\n]{72,}?) +", a):
            a = re.sub("([^\n]{72,}?) +([^\n ]*)(\n|$)", "\\1\n\\2 ", a)
        # Remove leading and trailing whitespace
        a = a.strip()
        return a 

    class Meta:
        db_table = "internet_drafts"
        
class PersonOrOrgInfo(models.Model):
    person_or_org_tag = models.AutoField(primary_key=True)
    record_type = models.CharField(blank=True, null=True, max_length=8)
    name_prefix = models.CharField(blank=True, null=True, max_length=10)
    first_name = models.CharField(blank=True, max_length=20)
    first_name_key = models.CharField(blank=True, max_length=20, editable=False)
    middle_initial = models.CharField(blank=True, null=True, max_length=4)
    middle_initial_key = models.CharField(blank=True, null=True, max_length=4, editable=False)
    last_name = models.CharField(blank=True, max_length=50)
    last_name_key = models.CharField(blank=True, max_length=50, editable=False)
    name_suffix = models.CharField(blank=True, null=True, max_length=10)
    date_modified = models.DateField(null=True, blank=True, auto_now=True)
    modified_by = models.CharField(blank=True, null=True, max_length=8)
    date_created = models.DateField(auto_now_add=True, null=True)
    created_by = models.CharField(blank=True, null=True, max_length=8)
    address_type = models.CharField(blank=True, null=True, max_length=4)
    def save(self):
        self.first_name_key = self.first_name.upper()
        self.middle_initial_key = self.middle_initial.upper()
        self.last_name_key = self.last_name.upper()
        super(PersonOrOrgInfo, self).save()
    def __str__(self):
        # For django.VERSION 0.96
	if self.first_name == '' and self.last_name == '':
	    return "(Person #%s)" % self.person_or_org_tag
        return "%s %s" % ( self.first_name or "<nofirst>", self.last_name or "<nolast>")
    def __unicode__(self):
        # For django.VERSION 1.x
	if self.first_name == '' and self.last_name == '':
	    return u"(Person #%s)" % self.person_or_org_tag
        return u"%s %s" % ( self.first_name or u"<nofirst>", self.last_name or u"<nolast>")
    def email(self, priority=1, type=None):
	name = str(self)
        email = ''
        types = type and [ type ] or [ "INET", "Prim", None ]
        for type in types:
            try:
                if type:
                    email = self.emailaddress_set.get(priority=priority, type=type).address
                else:
                    email = self.emailaddress_set.get(priority=priority).address
                break
            except (EmailAddress.DoesNotExist, AssertionError):
                pass
	return (name, email)
    # Added by Sunny Lee to display person's affiliation - 5/26/2007
    def affiliation(self, priority=1):
        try:
            postal = self.postaladdress_set.get(address_priority=priority)
        except PostalAddress.DoesNotExist:
            return "PersonOrOrgInfo with no postal address!"
        except AssertionError:
            return "PersonOrOrgInfo with multiple priority-%d addresses!" % priority
        return "%s" % ( postal.affiliated_company or postal.department or "???" )
    def full_name_as_key(self):
        return self.first_name.lower() + "." + self.last_name.lower()
    class Meta:
        db_table = 'person_or_org_info'
        ordering = ['last_name']
	verbose_name="Rolodex Entry"
	verbose_name_plural="Rolodex"

# could use a mapping for user_level
class IESGLogin(models.Model):
    SECRETARIAT_LEVEL = 0
    AD_LEVEL = 1
    INACTIVE_AD_LEVEL = 2
    
    USER_LEVEL_CHOICES = (
	(SECRETARIAT_LEVEL, 'Secretariat'),
	(AD_LEVEL, 'IESG'),
	(INACTIVE_AD_LEVEL, 'ex-IESG'),
	(3, 'Level 3'),
	(4, 'Comment Only(?)'),
    )
    id = models.AutoField(primary_key=True)
    login_name = models.CharField(blank=True, max_length=255)
    password = models.CharField(max_length=25)
    user_level = models.IntegerField(choices=USER_LEVEL_CHOICES)
    first_name = models.CharField(blank=True, max_length=25)
    last_name = models.CharField(blank=True, max_length=25)
    # this could be a OneToOneField but the unique constraint is violated in the data (for person_or_org_tag=188)
    person = BrokenForeignKey(PersonOrOrgInfo, db_column='person_or_org_tag', unique=True, null_values=(0, 888888), null=True)
    pgp_id = models.CharField(blank=True, null=True, max_length=20)
    default_search = models.NullBooleanField()
    def __str__(self):
        #return "%s, %s" % ( self.last_name, self.first_name)
        return "%s %s" % ( self.first_name, self.last_name)
    def is_current_ad(self):
	return self.user_level == 1
    def active_iesg():
	return IESGLogin.objects.filter(user_level=1,id__gt=1).order_by('last_name')	#XXX hardcoded
    active_iesg = staticmethod(active_iesg)
    class Meta:
        db_table = 'iesg_login'

class AreaDirector(models.Model):
    area = models.ForeignKey(Area, db_column='area_acronym_id', null=True)
    person = models.ForeignKey(PersonOrOrgInfo, db_column='person_or_org_tag')
    def __str__(self):
        return "%s (%s)" % ( self.person, self.role() )
    def role(self):
	try:
	    return "%s AD" % self.area
	except Area.DoesNotExist:
	    return "?%d? AD" % self.area_id
    class Meta:
        db_table = 'area_directors'


###
# RFC tables

class RfcIntendedStatus(models.Model):
    NONE=5
    intended_status_id = models.AutoField(primary_key=True)
    status = models.CharField(max_length=25, db_column='status_value')
    def __str__(self):
        return self.status
    class Meta:
        db_table = 'rfc_intend_status'
	verbose_name = 'RFC Intended Status Field'

class RfcStatus(models.Model):
    status_id = models.AutoField(primary_key=True)
    status = models.CharField(max_length=25, db_column='status_value')
    def __str__(self):
        return self.status
    class Meta:
        db_table = 'rfc_status'
	verbose_name = 'RFC Status'
	verbose_name_plural = 'RFC Statuses'

class Rfc(models.Model):
    ONLINE_CHOICES=(('YES', 'Yes'), ('NO', 'No'))
    rfc_number = models.IntegerField(primary_key=True)
    title = models.CharField(max_length=200, db_column='rfc_name')
    rfc_name_key = models.CharField(max_length=200, editable=False)
    group_acronym = models.CharField(blank=True, max_length=8)
    area_acronym = models.CharField(blank=True, max_length=8)
    status = models.ForeignKey(RfcStatus, db_column="status_id")
    intended_status = models.ForeignKey(RfcIntendedStatus, db_column="intended_status_id", default=RfcIntendedStatus.NONE)
    fyi_number = models.CharField(blank=True, max_length=20)
    std_number = models.CharField(blank=True, max_length=20)
    txt_page_count = models.IntegerField(null=True, blank=True)
    online_version = models.CharField(choices=ONLINE_CHOICES, max_length=3, default='YES')
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
    
    idinternal = CachedLookupField(lookup=lambda self: IDInternal.objects.get(draft=self.rfc_number, rfc_flag=1))
    group = CachedLookupField(lookup=lambda self: Acronym.objects.get(acronym=self.group_acronym))
    
    def __str__(self):
	return "RFC%04d" % ( self.rfc_number )        
    def save(self):
	self.rfc_name_key = self.title.upper()
	self.last_modified_date = datetime.date.today()
	super(Rfc, self).save()
    def displayname(self):
        return "%s.txt" % ( self.filename() )
    def filename(self):
	return "rfc%d" % ( self.rfc_number )
    def revision(self):
	return "RFC"
    def revision_display(self):
	return "RFC"
    def file_tag(self):
        return "RFC %s" % self.rfc_number

    # return set of RfcObsolete objects obsoleted or updated by this RFC
    def obsoletes(self): 
        return RfcObsolete.objects.filter(rfc=self.rfc_number)

    # return set of RfcObsolete objects obsoleting or updating this RFC
    def obsoleted_by(self): 
        return RfcObsolete.objects.filter(rfc_acted_on=self.rfc_number)

    class Meta:
        db_table = 'rfcs'
	verbose_name = 'RFC'
	verbose_name_plural = 'RFCs'

class RfcAuthor(models.Model):
    rfc = models.ForeignKey(Rfc, db_column='rfc_number', related_name='authors')
    person = models.ForeignKey(PersonOrOrgInfo, db_column='person_or_org_tag')
    def __str__(self):
        return "%s, %s" % ( self.person.last_name, self.person.first_name)
    class Meta:
        db_table = 'rfc_authors'
	verbose_name = 'RFC Author'

class RfcObsolete(models.Model):
    ACTION_CHOICES=(('Obsoletes', 'Obsoletes'), ('Updates', 'Updates'))
    rfc = models.ForeignKey(Rfc, db_column='rfc_number', related_name='updates_or_obsoletes')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    rfc_acted_on = models.ForeignKey(Rfc, db_column='rfc_acted_on', related_name='updated_or_obsoleted_by')
    def __str__(self):
        return "RFC%04d %s RFC%04d" % (self.rfc_id, self.action, self.rfc_acted_on_id)
    class Meta:
        db_table = 'rfcs_obsolete'
	verbose_name = 'RFC updates or obsoletes'
	verbose_name_plural = verbose_name

## End RFC Tables

class BallotInfo(models.Model):   # Added by Michael Lee
    ballot = models.AutoField(primary_key=True, db_column='ballot_id')
    active = models.BooleanField()
    an_sent = models.BooleanField()
    an_sent_date = models.DateField(null=True, blank=True)
    an_sent_by = models.ForeignKey(IESGLogin, db_column='an_sent_by', related_name='ansent', null=True)
    defer = models.BooleanField(blank=True)
    defer_by = models.ForeignKey(IESGLogin, db_column='defer_by', related_name='deferred', null=True)
    defer_date = models.DateField(null=True, blank=True)
    approval_text = models.TextField(blank=True)
    last_call_text = models.TextField(blank=True)
    ballot_writeup = models.TextField(blank=True)
    ballot_issued = models.IntegerField(null=True, blank=True)
    def __str__(self):
	try:
	    return "Ballot for %s" % self.drafts.get(primary_flag=1)
	except IDInternal.DoesNotExist:
	    return "Ballot ID %d (no I-D?)" % (self.ballot)
    def remarks(self):
        remarks = list(self.discusses.all()) + list(self.comments.all())
        return remarks
    def active_positions(self):
        '''Returns a list of dicts, with AD and Position tuples'''
	active_iesg = IESGLogin.active_iesg()
	ads = [ad.id for ad in active_iesg]
	positions = {}
	for position in self.positions.filter(ad__in=ads):
	    positions[position.ad_id] = position
	ret = []
	for ad in active_iesg:
	    ret.append({'ad': ad, 'pos': positions.get(ad.id, None)})
	return ret 
    def needed(self, standardsTrack=True):
	'''Returns text answering the question "what does this document
	need to pass?".  The return value is only useful if the document
	is currently in IESG evaluation.'''
	active_iesg = IESGLogin.active_iesg()
	ads = [ad.id for ad in active_iesg]
	yes = 0
	noobj = 0
	discuss = 0
	recuse = 0
	for position in self.positions.filter(ad__in=ads):
	    yes += 1 if position.yes > 0 else 0
	    noobj += 1 if position.noobj > 0 else 0
	    discuss += 1 if position.discuss > 0 else 0
	    recuse += 1 if position.recuse > 0 else 0
	answer = ''
	if yes < 1:
	    answer += "Needs a YES. "
	if discuss > 0:
	    if discuss == 1:
		answer += "Has a DISCUSS. "
	    else:
		answer += "Has %d DISCUSSes. " % discuss
	if standardsTrack:
	    # For standards-track, need positions from 2/3 of the
	    # non-recused current IESG.
	    needed = ( active_iesg.count() - recuse ) * 2 / 3
	else:
	    # Info and experimental only need one position.
	    needed = 1
	have = yes + noobj + discuss
	if have < needed:
            more = needed - have
            if more == 1:
                answer += "Needs %d more position. " % more
            else:
                answer += "Needs %d more positions. " % more
	else:
	    answer += "Has enough positions to pass"
	    if discuss:
		answer += " once DISCUSSes are resolved"
	    answer += ". "

	return answer.rstrip()

    class Meta:
        db_table = 'ballot_info'

def format_document_state(state, substate):
    if substate:
        return state.state + "::" + substate.sub_state
    else:
        return state.state

class IDInternal(models.Model):
    """
    An IDInternal represents a document that has been added to the
    I-D tracker.  It can be either an Internet Draft or an RFC.
    The table has only a single primary key field, meaning that
    there is the danger of RFC number collision with low-numbered
    Internet Drafts.

    Since it's most common to be an Internet Draft, the draft
    field is defined as a FK to InternetDrafts.  One side effect
    of this is that select_related() will only work with
    rfc_flag=0.

    When searching where matches may be either I-Ds or RFCs,
    you cannot use draft__ as that will cause an INNER JOIN
    which will limit the responses to I-Ds.
    """

    ACTIVE=1
    PUBLISHED=3
    EXPIRED=2
    WITHDRAWN_SUBMITTER=4
    REPLACED=5
    WITHDRAWN_IETF=6
    INACTIVE_STATES=[99,32,42]

    draft = models.ForeignKey(InternetDraft, primary_key=True, unique=True, db_column='id_document_tag')
    rfc_flag = models.IntegerField(null=True)
    ballot = models.ForeignKey(BallotInfo, related_name='drafts', db_column="ballot_id")
    primary_flag = models.IntegerField(blank=True, null=True)
    group_flag = models.IntegerField(blank=True, default=0)
    token_name = models.CharField(blank=True, max_length=25)
    token_email = models.CharField(blank=True, max_length=255)
    note = models.TextField(blank=True)
    status_date = models.DateField(blank=True,null=True)
    email_display = models.CharField(blank=True, max_length=50)
    agenda = models.IntegerField(null=True, blank=True)
    cur_state = models.ForeignKey(IDState, db_column='cur_state', related_name='docs')
    prev_state = models.ForeignKey(IDState, db_column='prev_state', related_name='docs_prev')
    assigned_to = models.CharField(blank=True, max_length=25)
    mark_by = models.ForeignKey(IESGLogin, db_column='mark_by', related_name='marked')
    job_owner = models.ForeignKey(IESGLogin, db_column='job_owner', related_name='documents')
    event_date = models.DateField(null=True)
    area_acronym = models.ForeignKey(Area)
    cur_sub_state = BrokenForeignKey(IDSubState, related_name='docs', null=True, blank=True, null_values=(0, -1))
    prev_sub_state = BrokenForeignKey(IDSubState, related_name='docs_prev', null=True, blank=True, null_values=(0, -1))
    returning_item = models.IntegerField(null=True, blank=True)
    telechat_date = models.DateField(null=True, blank=True)
    via_rfc_editor = models.IntegerField(null=True, blank=True)
    state_change_notice_to = models.CharField(blank=True, max_length=255)
    dnp = models.IntegerField(null=True, blank=True)
    dnp_date = models.DateField(null=True, blank=True)
    noproblem = models.IntegerField(null=True, blank=True)
    resurrect_requested_by = BrokenForeignKey(IESGLogin, db_column='resurrect_requested_by', related_name='docsresurrected', null=True, blank=True)
    approved_in_minute = models.IntegerField(null=True, blank=True)
    def __str__(self):
        if self.rfc_flag:
	    return "RFC%04d" % ( self.draft_id )
	else:
	    return self.draft.filename
    def get_absolute_url(self):
	if self.rfc_flag:
	    return "/doc/rfc%d/" % ( self.draft_id )
	else:
	    return "/doc/%s/" % ( self.draft.filename )
    _cached_rfc = None
    def document(self):
	if self.rfc_flag:
	    if self._cached_rfc is None:
		self._cached_rfc = Rfc.objects.get(rfc_number=self.draft_id)
	    return self._cached_rfc
	else:
	    return self.draft
    def public_comments(self):
	return self.comments().filter(public_flag=True)
    def comments(self):
	# would filter by rfc_flag but the database is broken. (see
	# trac ticket #96) so this risks collisions.
	# return self.documentcomment_set.all().order_by('-date','-time','-id')
        #
        # the obvious code above doesn't work with django.VERSION 1.0/1.1
        # because "draft" isn't a true foreign key (when rfc_flag=1 the
        # related InternetDraft object doesn't necessarily exist).
        return DocumentComment.objects.filter(document=self.draft_id).order_by('-date','-time','-id')
    def ballot_set(self):
	return IDInternal.objects.filter(ballot=self.ballot_id).order_by('-primary_flag')
    def ballot_primary(self):
	return IDInternal.objects.filter(ballot=self.ballot_id,primary_flag=1)
    def ballot_others(self):
	return IDInternal.objects.filter(models.Q(primary_flag=0)|models.Q(primary_flag__isnull=True), ballot=self.ballot_id)
    def docstate(self):
        return format_document_state(self.cur_state, self.cur_sub_state)
    def change_state(self, state, sub_state):
        self.prev_state = self.cur_state
        self.cur_state = state
        self.prev_sub_state_id = self.cur_sub_state_id
        self.cur_sub_state = sub_state
        
    class Meta:
        db_table = 'id_internal'
	verbose_name = 'IDTracker Draft'

class DocumentComment(models.Model):
    BALLOT_DISCUSS = 1
    BALLOT_COMMENT = 2
    BALLOT_CHOICES = (
	(BALLOT_DISCUSS, 'discuss'),
	(BALLOT_COMMENT, 'comment'),
    )
    document = models.ForeignKey(IDInternal)
    # NOTE: This flag is often NULL, which complicates its correct use...
    rfc_flag = models.IntegerField(null=True, blank=True)
    public_flag = models.BooleanField()
    date = models.DateField(db_column='comment_date', default=datetime.date.today)
    time = models.CharField(db_column='comment_time', max_length=20, default=lambda: datetime.datetime.now().strftime("%H:%M:%S"))
    version = models.CharField(blank=True, max_length=3)
    comment_text = models.TextField(blank=True)
    # NOTE: This is not a true foreign key -- it sometimes has values 
    # (like 999) that do not exist in IESGLogin. So using select_related()
    # will break!    
    created_by = BrokenForeignKey(IESGLogin, db_column='created_by', null=True, null_values=(0, 999))
    result_state = BrokenForeignKey(IDState, db_column='result_state', null=True, related_name="comments_leading_to_state", null_values=(0, 99))
    origin_state = models.ForeignKey(IDState, db_column='origin_state', null=True, related_name="comments_coming_from_state")
    ballot = models.IntegerField(null=True, choices=BALLOT_CHOICES)
    def __str__(self):
        return "\"%s...\" by %s" % (self.comment_text[:20], self.get_author())
    def get_absolute_url(self):
	# use self.document.rfc_flag, since
	# self.rfc_flag is not always set properly.
	if self.document.rfc_flag:
	    return "/idtracker/rfc%d/comment/%d/" % (self.document_id, self.id)
	else:
	    return "/idtracker/%s/comment/%d/" % (self.document.draft.filename, self.id)
    def get_author(self):
	if self.created_by:
	    return str(self.created_by)
	else:
	    return "(System)"
    def get_username(self):
	if self.created_by:
	    return self.created_by.login_name
	else:
	    return "(System)"
    def get_fullname(self):
	if self.created_by:
	    return self.created_by.first_name + " " + self.created_by.last_name
	else:
	    return "(System)"
    def datetime(self):
	# this is just a straightforward combination, except that the time is
	# stored incorrectly in the database.
	return datetime.datetime.combine( self.date, datetime.time( * [int(s) for s in self.time.split(":")] ) )
    class Meta:
        db_table = 'document_comments'
        
class Position(models.Model):
    ballot = models.ForeignKey(BallotInfo, related_name='positions')
    ad = models.ForeignKey(IESGLogin)
    yes = models.IntegerField(db_column='yes_col')
    noobj = models.IntegerField(db_column='no_col')
    abstain = models.IntegerField()
    approve = models.IntegerField(default=0) # doesn't appear to be used anymore?
    discuss = models.IntegerField()
    recuse = models.IntegerField()
    def __str__(self):
	return "Position for %s on %s" % ( self.ad, self.ballot )
    def abstain_ind(self):
        if self.recuse:
            return 'R'
        if self.abstain:
            return 'X'
        else:
            return ' '
    class Meta:
        db_table = 'ballots'
	unique_together = (('ballot', 'ad'), )
	verbose_name = "IESG Ballot Position"

class IESGComment(models.Model):
    ballot = models.ForeignKey(BallotInfo, related_name="comments")
    ad = models.ForeignKey(IESGLogin)
    date = models.DateField(db_column="comment_date")
    revision = models.CharField(max_length=2)
    active = models.IntegerField() # doesn't appear to be used
    text = models.TextField(blank=True, db_column="comment_text")
    def __str__(self):
	return "Comment text by %s on %s" % ( self.ad, self.ballot )
    def is_comment(self):
        return True
    class Meta:
        db_table = 'ballots_comment'
	unique_together = (('ballot', 'ad'), )
	verbose_name = 'IESG Comment Text'
	verbose_name_plural = 'IESG Comments'

class IESGDiscuss(models.Model):
    ballot = models.ForeignKey(BallotInfo, related_name="discusses")
    ad = models.ForeignKey(IESGLogin)
    date = models.DateField(db_column="discuss_date")
    revision = models.CharField(max_length=2)
    active = models.IntegerField()
    text = models.TextField(blank=True, db_column="discuss_text")
    def __str__(self):
	return "Discuss text by %s on %s" % ( self.ad, self.ballot )
    def is_discuss(self):
        return True
    class Meta:
        db_table = 'ballots_discuss'
	unique_together = (('ballot', 'ad'), )
	verbose_name = 'IESG Discuss Text'
	verbose_name_plural = 'IESG Discusses'

class IDAuthor(models.Model):
    document = models.ForeignKey(InternetDraft, db_column='id_document_tag', related_name='authors')
    person = models.ForeignKey(PersonOrOrgInfo, db_column='person_or_org_tag')
    author_order = models.IntegerField()
    def __str__(self):
	return "%s authors %s" % ( self.person, self.document.filename )
    def email(self):
        addresses = self.person.emailaddress_set.filter(type='I-D',priority=self.document_id)
        if len(addresses) == 0:
            return None
        else:
            return addresses[0].address
    def final_author_order(self):
        # Unfortunately, multiple authors for the same draft can have
        # the same value for author_order (although they should not).
        # Sort by person_id in that case to get a deterministic ordering.
        return "%08d%08d" % (self.author_order, self.person_id)
    class Meta:
        db_table = 'id_authors'
	verbose_name = "I-D Author"
        ordering = ['document','author_order']

# PostalAddress, EmailAddress and PhoneNumber are edited in
#  the admin for the Rolodex.
# The unique_together constraint is commented out for now, because
#  of a bug in oldforms and AutomaticManipulator which fails to
#  create the isUniquefoo_bar method properly.  Since django is
#  moving away from oldforms, I have to assume that this is going
#  to be fixed by moving admin to newforms.
# must decide which field is/are core.
class PostalAddress(models.Model):
    address_type = models.CharField(max_length=4)
    address_priority = models.IntegerField(null=True)
    person_or_org = models.ForeignKey(PersonOrOrgInfo, db_column='person_or_org_tag')
    person_title = models.CharField(max_length=50, blank=True)
    affiliated_company = models.CharField(max_length=70, blank=True)
    aff_company_key = models.CharField(max_length=70, blank=True, editable=False)
    department = models.CharField(max_length=100, blank=True)
    staddr1 = models.CharField(max_length=40)
    staddr2 = models.CharField(max_length=40, blank=True)
    mail_stop = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=20, blank=True)
    state_or_prov = models.CharField(max_length=20, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=20, blank=True)
    def save(self):
	self.aff_company_key = self.affiliated_company.upper()
	super(PostalAddress, self).save()
    class Meta:
        db_table = 'postal_addresses'
	#unique_together = (('address_type', 'person_or_org'), )
	verbose_name_plural = 'Postal Addresses'

class EmailAddress(models.Model):
    person_or_org = models.ForeignKey(PersonOrOrgInfo, db_column='person_or_org_tag')
    type = models.CharField(max_length=4, db_column='email_type')
    priority = models.IntegerField(db_column='email_priority')
    address = models.CharField(max_length=255, db_column='email_address')
    comment = models.CharField(blank=True, null=True, max_length=255, db_column='email_comment')
    def __str__(self):
	return self.address
    class Meta:
        db_table = 'email_addresses'
	#unique_together = (('email_priority', 'person_or_org'), )
	# with this, I get 'ChangeManipulator' object has no attribute 'isUniqueemail_priority_person_or_org'
	verbose_name_plural = 'Email addresses'

class PhoneNumber(models.Model):
    person_or_org = models.ForeignKey(PersonOrOrgInfo, db_column='person_or_org_tag')
    phone_type = models.CharField(max_length=3)
    phone_priority = models.IntegerField()
    phone_number = models.CharField(blank=True, max_length=255)
    phone_comment = models.CharField(blank=True, max_length=255)
    class Meta:
        db_table = 'phone_numbers'
	#unique_together = (('phone_priority', 'person_or_org'), )

### Working Groups

class WGType(models.Model):
    group_type_id = models.AutoField(primary_key=True)
    type = models.CharField(max_length=25, db_column='group_type')
    def __str__(self):
	return self.type
    class Meta:
        verbose_name = "WG Type"
        db_table = 'g_type'

class WGStatus(models.Model):
    status_id = models.AutoField(primary_key=True)
    status = models.CharField(max_length=25, db_column='status_value')
    def __str__(self):
	return self.status
    class Meta:
        verbose_name = "WG Status"
        verbose_name_plural = "WG Statuses"
        db_table = 'g_status'

class IETFWG(models.Model):
    ACTIVE = 1
    group_acronym = models.OneToOneField(Acronym, primary_key=True, editable=False)
    group_type = models.ForeignKey(WGType)
    proposed_date = models.DateField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    dormant_date = models.DateField(null=True, blank=True)
    concluded_date = models.DateField(null=True, blank=True)
    status = models.ForeignKey(WGStatus)
    area_director = models.ForeignKey(AreaDirector, null=True)
    meeting_scheduled = models.CharField(blank=True, max_length=3)
    email_address = models.CharField(blank=True, max_length=60)
    email_subscribe = models.CharField(blank=True, max_length=120)
    email_keyword = models.CharField(blank=True, max_length=50)
    email_archive = models.CharField(blank=True, max_length=95)
    comments = models.TextField(blank=True)
    last_modified_date = models.DateField()
    meeting_scheduled_old = models.CharField(blank=True, max_length=3)
    area = FKAsOneToOne('areagroup', reverse=True)
    def __str__(self):
	return self.group_acronym.acronym
    def active_drafts(self):
	return self.group_acronym.internetdraft_set.all().filter(status__status="Active")
    def choices():
	return [(wg.group_acronym_id, wg.group_acronym.acronym) for wg in IETFWG.objects.all().filter(group_type__type='WG').select_related().order_by('acronym.acronym')]
    choices = staticmethod(choices)
    def area_acronym(self):
        areas = AreaGroup.objects.filter(group__exact=self.group_acronym)
        if areas:
            return areas[areas.count()-1].area.area_acronym
        else:
            return None
    def area_directors(self):
        areas = AreaGroup.objects.filter(group__exact=self.group_acronym)
        if areas:
            return areas[areas.count()-1].area.areadirector_set.all()
        else:
            return None
    def chairs(self): # return a set of WGChair objects for this work group
        return WGChair.objects.filter(group_acronym__exact=self.group_acronym)
    def secretaries(self): # return a set of WGSecretary objects for this group
        return WGSecretary.objects.filter(group_acronym__exact=self.group_acronym)
    def milestones(self): # return a set of GoalMilestone objects for this group
        return GoalMilestone.objects.filter(group_acronym__exact=self.group_acronym)
    def rfcs(self): # return a set of Rfc objects for this group
        return Rfc.objects.filter(group_acronym__exact=self.group_acronym)
    def drafts(self): # return a set of Rfc objects for this group
        return InternetDraft.objects.filter(group__exact=self.group_acronym)
    def charter_text(self): # return string containing WG description read from file
        # get file path from settings. Syntesize file name from path, acronym, and suffix
        try:
            filename = os.path.join(settings.IETFWG_DESCRIPTIONS_PATH, self.group_acronym.acronym) + ".desc.txt"
            desc_file = open(filename)
            desc = desc_file.read()
        except BaseException:    
            desc =  'Error Loading Work Group Description'
        return desc

    def additional_urls(self):
        return AreaWGURL.objects.filter(name=self.group_acronym.acronym)        
    def clean_email_archive(self):
        x = self.email_archive
        # remove "current/" and "maillist.html"
        x = re.sub("^(http://www\.ietf\.org/mail-archive/web/)([^/]+/)(current/)?([a-z]+\.html)?$", "\\1\\2", x)
        return x
    class Meta:
        db_table = 'groups_ietf'
	ordering = ['?']	# workaround django wanting to sort by acronym but not joining with it
	verbose_name = 'IETF Working Group'

class WGChair(models.Model):
    person = models.ForeignKey(PersonOrOrgInfo, db_column='person_or_org_tag')
    group_acronym = models.ForeignKey(IETFWG)
    def __str__(self):
	return "%s (%s)" % ( self.person, self.role() )
    def role(self):
	return "%s %s Chair" % ( self.group_acronym, self.group_acronym.group_type )
    class Meta:
        db_table = 'g_chairs'
	verbose_name = "WG Chair"

class WGEditor(models.Model):
    group_acronym = models.ForeignKey(IETFWG)
    person = models.ForeignKey(PersonOrOrgInfo, db_column='person_or_org_tag', unique=True)
    def __str__(self):
	return "%s (%s)" % (self.person, self.role())
    def role(self):
	return "%s Editor" % self.group_acronym
    class Meta:
        db_table = 'g_editors'
	verbose_name = "WG Editor"

# Note: there is an empty table 'g_secretary'.
# This uses the 'g_secretaries' table but is called 'GSecretary' to
# match the model naming scheme.
class WGSecretary(models.Model):
    group_acronym = models.ForeignKey(IETFWG)
    person = models.ForeignKey(PersonOrOrgInfo, db_column='person_or_org_tag')
    def __str__(self):
	return "%s (%s)" % ( self.person, self.role() )
    def role(self):
	return "%s %s Secretary" % ( self.group_acronym, self.group_acronym.group_type )
    class Meta:
        db_table = 'g_secretaries'
	verbose_name = "WG Secretary"
	verbose_name_plural = "WG Secretaries"

class WGTechAdvisor(models.Model):
    group_acronym = models.ForeignKey(IETFWG)
    person = models.ForeignKey(PersonOrOrgInfo, db_column='person_or_org_tag')
    def __str__(self):
	return "%s (%s)" % ( self.person, self.role() )
    def role(self):
	return "%s Technical Advisor" % self.group_acronym
    class Meta:
        db_table = 'g_tech_advisors'
	verbose_name = "WG Technical Advisor"

class AreaGroup(models.Model):
    area = models.ForeignKey(Area, db_column='area_acronym_id', related_name='areagroup')
    group = models.ForeignKey(IETFWG, db_column='group_acronym_id', unique=True)
    def __str__(self):
	return "%s is in %s" % ( self.group, self.area )
    class Meta:
        db_table = 'area_group'
	verbose_name = 'Area this group is in'
	verbose_name_plural = 'Area to Group mappings'

class GoalMilestone(models.Model):
    DONE_CHOICES = (
        ('Done', 'Done'),
        ('No', 'Not Done'),
    )
    gm_id = models.AutoField(primary_key=True)
    group_acronym = models.ForeignKey(IETFWG)
    description = models.TextField()
    expected_due_date = models.DateField()
    done_date = models.DateField(null=True, blank=True)
    done = models.CharField(blank=True, choices=DONE_CHOICES, max_length=4)
    last_modified_date = models.DateField()
    def __str__(self):
	return self.description
    class Meta:
        db_table = 'goals_milestones'
	verbose_name = 'IETF WG Goal or Milestone'
	verbose_name_plural = 'IETF WG Goals or Milestones'
	ordering = ['expected_due_date']


#### end wg stuff

class Role(models.Model):
    '''This table is named 'chairs' in the database, as its original
    role was to store "who are IETF, IAB and IRTF chairs?".  It has
    since expanded to store roles, such as "IAB Exec Dir" and "IAD",
    so the model is renamed.
    '''
    person = models.ForeignKey(PersonOrOrgInfo, db_column='person_or_org_tag')
    role_name = models.CharField(max_length=25, db_column='chair_name')
    
    # Role values
    IETF_CHAIR            = 1
    IAB_CHAIR             = 2
    NOMCOM_CHAIR          = 3
    IAB_EXCUTIVE_DIRECTOR = 4
    IRTF_CHAIR            = 5
    IAD_CHAIR             = 6

    # This __str__ makes it odd to use as a ForeignKey.
    def __str__(self):
	return "%s (%s)" % (self.person, self.role())
    def role(self):
	if self.role_name in ('IETF', 'IAB', 'IRTF', 'NomCom'):
	    return "%s Chair" % self.role_name
	else:
	    return self.role_name
    class Meta:
        db_table = 'chairs'

class ChairsHistory(models.Model):
    chair_type = models.ForeignKey(Role)
    present_chair = models.BooleanField()
    person = models.ForeignKey(PersonOrOrgInfo, db_column='person_or_org_tag')
    start_year = models.IntegerField()
    end_year = models.IntegerField(null=True, blank=True)
    def __str__(self):
	return str(self.person)
    class Meta:
        db_table = 'chairs_history'

#
# IRTF RG info
class IRTF(models.Model):
    irtf_id = models.AutoField(primary_key=True)
    acronym = models.CharField(blank=True, max_length=25, db_column='irtf_acronym')
    name = models.CharField(blank=True, max_length=255, db_column='irtf_name')
    charter_text = models.TextField(blank=True,null=True)
    meeting_scheduled = models.BooleanField(blank=True)
    def __str__(self):
	return self.acronym
    class Meta:
        db_table = 'irtf'
        verbose_name="IRTF Research Group"

class IRTFChair(models.Model):
    irtf = models.ForeignKey(IRTF)
    person = models.ForeignKey(PersonOrOrgInfo, db_column='person_or_org_tag')
    def __str__(self):
        return "%s is chair of %s" % (self.person, self.irtf)
    class Meta:
        db_table = 'irtf_chairs'
        verbose_name="IRTF Research Group Chair"

class IDDates(models.Model):
    FIRST_CUT_OFF = 1
    SECOND_CUT_OFF = 2
    IETF_MONDAY = 3
    ALL_IDS_PROCESSED_BY = 4
    IETF_MONDAY_AFTER = 5
    APPROVED_V00_SUBMISSIONS = 6
    
    date = models.DateField(db_column="id_date")
    description = models.CharField(max_length=255, db_column="date_name")
    f_name = models.CharField(max_length=255)
    
    class Meta:
        db_table = 'id_dates'
    
# Not a model, but it's related.
# This is used in the view to represent documents
# in "I-D Exists".
#
class DocumentWrapper(object):
    '''A wrapper for a document, used to synthesize I-D Exists.'''
    document = None
    synthetic = True
    job_owner = "Not Assigned Yet"
    docstate = "I-D Exists"
    cur_state = "I-D Exists"
    cur_state_id = 100
    primary_flag = 1
    def __init__(self, document):
	self.document = document


# changes done by convert-096.py:changed maxlength to max_length
# removed core
# removed edit_inline
# removed max_num_in_admin
# removed num_in_admin
# removed raw_id_admin
