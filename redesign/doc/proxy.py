from models import *
from redesign.person.models import Email 
from redesign.proxy_utils import TranslatingManager

from django.conf import settings

import glob, os


class InternetDraft(Document):
    objects = TranslatingManager(dict(filename="name",
                                      id_document_tag="id",
                                      status="state",
                                      rfc_number=lambda v: ("docalias__name", "rfc%s" % v)))

    DAYS_TO_EXPIRE=185

    # things from InternetDraft
    
    #id_document_tag = models.AutoField(primary_key=True)
    @property
    def id_document_tag(self):
        return self.name              # Will only work for some use cases
    #title = models.CharField(max_length=255, db_column='id_document_name') # same name
    #id_document_key = models.CharField(max_length=255, editable=False)
    @property
    def id_document_key(self):
        return self.title.upper()
    #group = models.ForeignKey(Acronym, db_column='group_acronym_id')
    @property
    def group(self):
        from group.proxy import Acronym as AcronymProxy
        return AcronymProxy(super(self.__class__, self).group)
    #filename = models.CharField(max_length=255, unique=True)
    @property
    def filename(self):
        return self.name
    #revision = models.CharField(max_length=2)
    @property
    def revision(self):
        return self.rev
    #revision_date = models.DateField()
    @property
    def revision_date(self):
        e = self.latest_event(type="new_revision")
        return e.time.date() if e else None
    # helper function
    def get_file_type_matches_from(self, glob_path):
        possible_types = [".txt", ".pdf", ".xml", ".ps"]
        res = []
        for m in glob.glob(glob_path):
            for t in possible_types:
                if m.endswith(t):
                    res.append(t)
        return ",".join(res)
    #file_type = models.CharField(max_length=20)
    @property
    def file_type(self):
        return self.get_file_type_matches_from(os.path.join(settings.INTERNET_DRAFT_PATH, self.name + "-" + self.rev + ".*")) or ".txt"
    #txt_page_count = models.IntegerField()
    @property
    def txt_page_count(self):
        return self.pages
    #local_path = models.CharField(max_length=255, blank=True) # unused
    #start_date = models.DateField()
    @property
    def start_date(self):
        e = NewRevision.objects.filter(doc=self).order_by("time")[:1]
        return e[0].time.date() if e else None
    #expiration_date = models.DateField()
    @property
    def expiration_date(self):
        return self.expiration()
    #abstract = models.TextField() # same name
    #dunn_sent_date = models.DateField(null=True, blank=True) # unused
    #extension_date = models.DateField(null=True, blank=True) # unused
    #status = models.ForeignKey(IDStatus)
    @property
    def status(self):
        from redesign.name.proxy import IDStatus
        return IDStatus(self.state)

    @property
    def status_id(self):
        from redesign.name.proxy import IDStatus
        return { 'active': 1, 'repl': 5, 'expired': 2, 'rfc': 3, 'auth-rm': 4, 'ietf-rm': 6 }[self.state_id]
        
    #intended_status = models.ForeignKey(IDIntendedStatus)
    @property
    def intended_status(self):
        return self.intended_std_level
        
    #lc_sent_date = models.DateField(null=True, blank=True)
    @property
    def lc_sent_date(self):
        e = self.latest_event(type="sent_last_call")
        return e.time if e else None
        
    #lc_changes = models.CharField(max_length=3) # used in DB, unused in Django code?
        
    #lc_expiration_date = models.DateField(null=True, blank=True)
    @property
    def lc_expiration_date(self):
        e = self.latest_event(type="sent_last_call")
        return e.expiration.expires if e else None
        
    #b_sent_date = models.DateField(null=True, blank=True)
    @property
    def b_sent_date(self):
        e = self.latest_event(type="sent_ballot_announcement")
        return e.time if e else None
        
    #b_discussion_date = models.DateField(null=True, blank=True) # unused
        
    #b_approve_date = models.DateField(null=True, blank=True)
    @property
    def b_approve_date(self):
        e = self.latest_event(type="iesg_approved")
        return e.time.date() if e else None
        
    #wgreturn_date = models.DateField(null=True, blank=True) # unused
        
    #rfc_number = models.IntegerField(null=True, blank=True, db_index=True)
    @property
    def rfc_number(self):
        aliases = self.docalias_set.filter(name__startswith="rfc")
        return int(aliases[0].name[3:]) if aliases else None
        
    #comments = models.TextField(blank=True) # unused
        
    #last_modified_date = models.DateField()
    @property
    def last_modified_date(self):
        return self.time
        
    #replaced_by = models.ForeignKey('self', db_column='replaced_by', blank=True, null=True, related_name='replaces_set')
    @property
    def replaced_by(self):
        r = InternetDraft.objects.filter(relateddocument__doc_alias__document=self, relateddocument__relationship="replaces")
        return r[0] if r else None
        
    #replaces = FKAsOneToOne('replaces', reverse=True)
    @property
    def replaces(self):
        r = self.replaces_set()
        return r[0] if r else None

    @property
    def replaces_set(self):
        return InternetDraft.objects.filter(docalias__relateddocument__document=self, docalias__relateddocument__relationship="replaces")
        
    #review_by_rfc_editor = models.BooleanField()
    @property
    def review_by_rfc_editor(self):
        return bool(self.tags.filter(slug='rfc-rev'))
        
    #expired_tombstone = models.BooleanField()
    @property
    def expired_tombstone(self):
        return bool(self.tags.filter(slug='exp-tomb'))
        
    #idinternal = FKAsOneToOne('idinternal', reverse=True, query=models.Q(rfc_flag = 0))
    @property
    def idinternal(self):
        # since IDInternal is now merged into the document, we try to
        # guess here
        return self if self.iesg_state or self.latest_event(type="changed_ballot_position") else None

    # reverse relationship
    @property
    def authors(self):
        from person.models import Person
        return IDAuthor.objects.filter(document=self)
    
    # methods from InternetDraft
    def displayname(self):
        return self.name
    def file_tag(self):
        return "<%s-%s.txt>" % (self.name, self.revision_display())
    def group_acronym(self):
	return self.group.acronym
    def idstate(self):
	return self.docstate()
    def revision_display(self):
	r = int(self.revision)
	if self.state_id != 'active' and not self.expired_tombstone:
	   r = max(r - 1, 0)
	return "%02d" % r
    def expiration(self):
        e = self.latest_event(type__in=("completed_resurrect", "new_revision"))
        return e.time.date() + datetime.timedelta(self.DAYS_TO_EXPIRE)
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
        import re
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

    
    # things from IDInternal
    
    #draft = models.ForeignKey(InternetDraft, primary_key=True, unique=True, db_column='id_document_tag')
    @property
    def draft(self):
        return self
        
    #rfc_flag = models.IntegerField(null=True)
    @property
    def rfc_flag(self):
        return self.state_id == "rfc"
    
    #ballot = models.ForeignKey(BallotInfo, related_name='drafts', db_column="ballot_id")
    @property
    def ballot(self):
        return self # FIXME: raise BallotInfo.DoesNotExist?
    
    #primary_flag = models.IntegerField(blank=True, null=True)
    @property
    def primary_flag(self):
        # left-over from multi-ballot documents which we don't really
        # support anymore, just pretend we're always primary
        return True
    
    #group_flag = models.IntegerField(blank=True, default=0) # not used anymore, contained the group acronym_id once upon a time (so it wasn't a flag)

    #token_name = models.CharField(blank=True, max_length=25)
    @property
    def token_name(self):
        return self.ad.get_name()

    #token_email = models.CharField(blank=True, max_length=255)
    @property
    def token_email(self):
        return self.ad.address
    
    #note = models.TextField(blank=True) # same name
    
    #status_date = models.DateField(blank=True,null=True)
    @property
    def status_date(self):
        e = self.latest_event(Status, type="changed_status_date")
        return e.date if e else None

    #email_display = models.CharField(blank=True, max_length=50) # unused
    #agenda = models.IntegerField(null=True, blank=True)
    @property
    def agenda(self):
        return bool(self.latest_event(type="scheduled_for_telechat"))
    
    #cur_state = models.ForeignKey(IDState, db_column='cur_state', related_name='docs')
    @property
    def cur_state(self):
        return self.iesg_state
    
    #prev_state = models.ForeignKey(IDState, db_column='prev_state', related_name='docs_prev')
    @property
    def prev_state(self):
        ds = self.dochistory_set.exclude(iesg_state=self.iesg_state).order_by('-time')[:1]
        return ds[0].iesg_state if ds else None
    
    #assigned_to = models.CharField(blank=True, max_length=25) # unused

    #mark_by = models.ForeignKey(IESGLogin, db_column='mark_by', related_name='marked')
    @property
    def mark_by(self):
        e = self.latest_event()
        from person.proxy import IESGLogin as IESGLoginProxy
        return IESGLoginProxy(e.by) if e else None

    # job_owner = models.ForeignKey(IESGLogin, db_column='job_owner', related_name='documents')
    @property
    def job_owner(self):
        from person.proxy import IESGLogin as IESGLoginProxy
        return IESGLoginProxy(self.ad)
    
    #event_date = models.DateField(null=True)
    @property
    def event_date(self):
        e = self.latest_event()
        return e.time if e else None
    
    #area_acronym = models.ForeignKey(Area)
    @property
    def area_acronym(self):
        if self.group:
            return self.group.parent
        elif self.ad:
            # return area for AD
            return ad.role_set.get(type="ad", group__state="active").group
        else:
            return None
        
    #cur_sub_state = BrokenForeignKey(IDSubState, related_name='docs', null=True, blank=True, null_values=(0, -1))
    @property
    def cur_sub_state(self):
        s = self.tags.filter(slug__in=['extpty', 'need-rev', 'ad-f-up', 'point'])
        return s[0] if s else None
    @property
    def cur_sub_state_id(self):
        s = self.cur_sub_state
        return 1 if s else 0 # need to return something numeric
    
    #prev_sub_state = BrokenForeignKey(IDSubState, related_name='docs_prev', null=True, blank=True, null_values=(0, -1))
    @property
    def prev_sub_state(self):
        ds = self.dochistory_set.all().order_by('-time')[:1]
        return "|".join(ds[0].tags.all()) if ds else None
    @property
    def prev_sub_state_id(self):
        return 0
    
    #returning_item = models.IntegerField(null=True, blank=True)
    @property
    def returning_item(self):
        e = self.latest_event(type="scheduled_for_telechat")
        return e.telechat.returning_item if e else None

    #telechat_date = models.DateField(null=True, blank=True)
    @property
    def telechat_date(self):
        e = self.latest_event(type="scheduled_for_telechat")
        return e.telechat.telechat_date if e else None

    #via_rfc_editor = models.IntegerField(null=True, blank=True)
    @property
    def via_rfc_editor(self):
        return bool(self.tags.filter(slug='via-rfc'))
    
    #state_change_notice_to = models.CharField(blank=True, max_length=255)
    @property
    def state_change_notice_to(self):
        return self.notify
    
    #dnp = models.IntegerField(null=True, blank=True)
    @property
    def dnp(self):
        e = self.latest_event(type__in=("iesg_disapproved", "iesg_approved"))
        return e != None and e.type == "iesg_disapproved"
    
    #dnp_date = models.DateField(null=True, blank=True)
    @property
    def dnp_date(self):
        e = self.latest_event(type__in=("iesg_disapproved", "iesg_approved"))
        return e.time.date() if e != None and e.type == "iesg_disapproved" else None
    
    #noproblem = models.IntegerField(null=True, blank=True)
    @property
    def noproblem(self):
        e = self.latest_event(type__in=("iesg_disapproved", "iesg_approved"))
        return e != None and e.type == "iesg_approved"
    
    #resurrect_requested_by = BrokenForeignKey(IESGLogin, db_column='resurrect_requested_by', related_name='docsresurrected', null=True, blank=True)
    @property
    def resurrect_requested_by(self):
        e = self.latest_event(type__in=("requested_resurrect", "completed_resurrect"))
        from person.proxy import IESGLogin as IESGLoginProxy
        return IESGLoginProxy(e.by) if e and e.type == "requested_resurrect" else None
    
    #approved_in_minute = models.IntegerField(null=True, blank=True)
    @property
    def approved_in_minute(self):
        return self.latest_event(type="approved_in_minute")
        
    
    def get_absolute_url(self):
	if self.rfc_flag:
	    return "/doc/rfc%d/" % self.rfc_number
	else:
	    return "/doc/%s/" % self.name
        
    def document(self):
        return self
    
    def comments(self):
        return self.event_set.all().order_by('-time')

    def ballot_set(self):
        return [self]
    def ballot_primary(self):
        return [self]
    def ballot_others(self):
        return []
    def docstate(self):
        if self.iesg_state:
            return self.iesg_state.name
        else:
            return "I-D Exists"
    def change_state(self, state, sub_state):
        self.iesg_state = state
    

    # things from BallotInfo
    #active = models.BooleanField()
    @property
    def active(self):
        # taken from BallotWrapper
        return self.latest_event(type="sent_ballot_announcement") and self.iesg_state and self.iesg_state.name in ['In Last Call', 'Waiting for Writeup', 'Waiting for AD Go-Ahead', 'IESG Evaluation', 'IESG Evaluation - Defer'] and (self.state_id == "rfc" or self.state_id == "active")

    #an_sent = models.BooleanField()
    @property
    def an_sent(self):
        return bool(self.latest_event(type="iesg_approved"))

    #an_sent_date = models.DateField(null=True, blank=True)
    @property
    def an_sent_date(self):
        e = self.latest_event(type="iesg_approved")
        return e.time if e else None
    
    #an_sent_by = models.ForeignKey(IESGLogin, db_column='an_sent_by', related_name='ansent', null=True)
    @property
    def an_sent_by(self):
        e = self.latest_event(type="iesg_approved")
        from person.proxy import IESGLogin as IESGLoginProxy
        return IESGLoginProxy(e.by) if e else None

    #defer = models.BooleanField()
    @property
    def defer(self):
        # we're deferred if we're in the deferred state
        return self.iesg_state and self.iesg_state.name == "IESG Evaluation - Defer"

    #defer_by = models.ForeignKey(IESGLogin, db_column='defer_by', related_name='deferred', null=True)
    @property
    def defer_by(self):
        e = self.latest_event(type="changed_document", desc__startswith="State changed to <b>IESG Evaluation - Defer</b>")
        from person.proxy import IESGLogin as IESGLoginProxy
        return IESGLoginProxy(e.by) if e else None
    
    #defer_date = models.DateField(null=True, blank=True)
    @property
    def defer_date(self):
        e = self.latest_event(type="changed_document", desc__startswith="State changed to <b>IESG Evaluation - Defer</b>")
        return e.time.date() if e else None

    #approval_text = models.TextField(blank=True)
    @property
    def approval_text(self):
        e = self.latest_event(Text, type="changed_ballot_approval_text")
        return e.content if e else ""
    
    #last_call_text = models.TextField(blank=True)
    @property
    def last_call_text(self):
        e = self.latest_event(Text, type="changed_last_call_text")
        return e.content if e else ""
    
    #ballot_writeup = models.TextField(blank=True)
    @property
    def ballot_writeup(self):
        e = self.latest_event(Text, type="changed_ballot_writeup_text")
        return e.content if e else ""

    #ballot_issued = models.IntegerField(null=True, blank=True)
    @property
    def ballot_issued(self):
        return bool(self.latest_event(type="sent_ballot_announcement"))
    
    # def remarks(self): # apparently not used
    #     remarks = list(self.discusses.all()) + list(self.comments.all())
    #     return remarks
    def active_positions(self):
        """Returns a list of dicts, with AD and Position tuples"""
        active_ads = Email.objects.filter(role__name="ad", role__group__state="active")

	res = []
        def add(ad, pos):
            # FIXME: ad and pos don't emulate old interface
            res.append(dict(ad=ad, pos=pos))
        
        found = set()
	for pos in self.event_set.filter(type="changed_ballot_position", ballotposition__ad__in=active_ads).select_related('ad').order_by("-time"):
            if not pos.ballotposition.ad in found:
                found.add(pos.ballotposition.ad)
                add(pos.ballotposition.ad, pos)

        for ad in active_ads:
            if ad not in found:
                add(ad, None)
                
	return res
    
    def needed(self, standardsTrack=True):
	"""Returns text answering the question what does this document
	need to pass?.  The return value is only useful if the document
	is currently in IESG evaluation."""
        tmp = self.active_positions()
        positions = [x["pos"] for x in tmp if x["pos"]]
        ads = [x["ad"] for x in tmp]
        
	yes = noobj = discuss = recuse = 0
	for position in positions:
            p = position.ballotposition.pos_id
            if p == "yes":
                yes += 1
            if p == "noobj":
                noobj += 1
            if p == "discuss":
                discuss += 1
            if p == "recuse":
                recuse += 1
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
	    needed = int((len(ads) - recuse) * 2 / 3)
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
    

    # things from RfcIndex
    
    #rfc_number = models.IntegerField(primary_key=True) # already taken care of
    #title = models.CharField(max_length=250) # same name
    #authors = models.CharField(max_length=250) # exists already
    #rfc_published_date = models.DateField()
    @property
    def rfc_published_date(self):
        e = self.latest_event(type="published_rfc")
        return e.time.date() if e else None
    
    #current_status = models.CharField(max_length=50,null=True)
    @property
    def current_status(self):
        return self.std_level.name

    #updates = models.CharField(max_length=200,blank=True,null=True)
    @property
    def updates(self):
        return ",".join(sorted("RFC%s" % d.rfc_number for d in InternetDraft.objects.filter(docalias__relateddocument__document=self, docalias__relateddocument__relationship="updates")))

    #updated_by = models.CharField(max_length=200,blank=True,null=True)
    @property
    def updated_by(self):
        return ",".join(sorted("RFC%s" % d.rfc_number for d in InternetDraft.objects.filter(relateddocument__doc_alias__document=self, relateddocument__relationship="updates")))

    #obsoletes = models.CharField(max_length=200,blank=True,null=True)
    @property
    def obsoletes(self):
        return ",".join(sorted("RFC%s" % d.rfc_number for d in InternetDraft.objects.filter(docalias__relateddocument__document=self, docalias__relateddocument__relationship="obs")))

    #obsoleted_by = models.CharField(max_length=200,blank=True,null=True)
    @property
    def obsoleted_by(self):
        return ",".join(sorted("RFC%s" % d.rfc_number for d in InternetDraft.objects.filter(relateddocument__doc_alias__document=self, relateddocument__relationship="obs")))

    #also = models.CharField(max_length=50,blank=True,null=True)
    @property
    def also(self):
        aliases = self.docalias_set.filter(models.Q(name__startswith="bcp") |
                                           models.Q(name__startswith="std") |
                                           models.Q(name__startswith="bcp"))
        return aliases[0].name.upper() if aliases else None
    
    #draft = models.CharField(max_length=200,null=True) # have to ignore this, it's already implemented
        
    #has_errata = models.BooleanField()
    @property
    def has_errata(self):
        return bool(self.tags.filter(slug="errata"))

    #stream = models.CharField(max_length=15,blank=True,null=True)
    @property
    def stream(self):
        return super(InternetDraft, self).stream.name

    #wg = models.CharField(max_length=15,blank=True,null=True)
    @property
    def wg(self):
        return self.group.acronym

    #file_formats = models.CharField(max_length=20,blank=True,null=True)
    @property
    def file_formats(self):
        return self.get_file_type_matches_from(os.path.join(settings.RFC_PATH, "rfc" + str(self.rfc_number) + ".*")).replace(".", "").replace("txt", "ascii")

    class Meta:
        proxy = True

IDInternal = InternetDraft
BallotInfo = InternetDraft
RfcIndex = InternetDraft


class IDAuthor(DocumentAuthor):
    #document = models.ForeignKey(InternetDraft, db_column='id_document_tag', related_name='authors') # same name
    #person = models.ForeignKey(PersonOrOrgInfo, db_column='person_or_org_tag')
    @property
    def person(self):
        return self.author.person
    
    #author_order = models.IntegerField()
    @property
    def author_order(self):
        return self.order
    
    def email(self):
        return None if self.author.address.startswith("unknown-email") else self.author.address
    
    def final_author_order(self):
        return self.order
    
    class Meta:
        proxy = True

