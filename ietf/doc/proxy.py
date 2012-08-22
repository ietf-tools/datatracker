from ietf.doc.models import *
from ietf.person.models import Email 
from ietf.utils.proxy import TranslatingManager
from ietf.name.proxy import *

from django.conf import settings

import glob, os


class InternetDraft(Document):
    objects = TranslatingManager(dict(filename="name",
                                      filename__contains="name__contains",
                                      id_document_tag="pk",
                                      status=lambda v: ("states__slug", { 1: 'active', 2: 'expired', 3: 'rfc', 4: 'auth-rm', 5: 'repl', 6: 'ietf-rm'}[v], "states__type", "draft"),
                                      job_owner="ad",
                                      rfc_number=lambda v: ("docalias__name", "rfc%s" % v),
                                      cur_state=lambda v: ("states__order", v, 'states__type', 'draft-iesg'),
                                      idinternal__primary_flag=None,
                                      idinternal__cur_state__state=lambda v: ("states__name", v, 'states__type', 'draft-iesg'),
                                      ), always_filter=dict(type="draft"))

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
        from ietf.group.proxy import Acronym as AcronymProxy
        g = super(InternetDraft, self).group
        return AcronymProxy().from_object(g) if g else None
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
        if hasattr(self, "new_revision"):
            e = self.new_revision
        else:
            e = self.latest_event(type="new_revision")
        return e.time.date() if e else None
    # helper function
    def get_file_type_matches_from(self, base_path):
        possible_types = [".txt", ".pdf", ".xml", ".ps"]
        res = []
        for m in glob.glob(base_path + '.*'):
            for t in possible_types:
                if base_path + t == m:
                    res.append(t)
        return ",".join(res)
    #file_type = models.CharField(max_length=20)
    @property
    def file_type(self):
        return self.get_file_type_matches_from(os.path.join(settings.INTERNET_DRAFT_PATH, self.name + "-" + self.rev)) or ".txt"
    #txt_page_count = models.IntegerField()
    @property
    def txt_page_count(self):
        return self.pages
    #local_path = models.CharField(max_length=255, blank=True) # unused
    #start_date = models.DateField()
    @property
    def start_date(self):
        e = NewRevisionDocEvent.objects.filter(doc=self).order_by("time")[:1]
        return e[0].time.date() if e else None
    #expiration_date = models.DateField()
    @property
    def expiration_date(self):
        e = self.latest_event(type__in=('expired_document', 'new_revision', "completed_resurrect"))
        return e.time.date() if e and e.type == "expired_document" else None
    #abstract = models.TextField() # same name
    #dunn_sent_date = models.DateField(null=True, blank=True) # unused
    #extension_date = models.DateField(null=True, blank=True) # unused
    #status = models.ForeignKey(IDStatus)
    @property
    def status(self):
        s = self.get_state()
        return IDStatus().from_object(s) if s else None

    @property
    def status_id(self):
        return { 'active': 1, 'repl': 5, 'expired': 2, 'rfc': 3, 'auth-rm': 4, 'ietf-rm': 6 }[self.get_state_slug()]
        
    #intended_status = models.ForeignKey(IDIntendedStatus)
    @property
    def intended_status(self):
        return self.intended_std_level
        
    #lc_sent_date = models.DateField(null=True, blank=True)
    @property
    def lc_sent_date(self):
        e = self.latest_event(type="sent_last_call")
        return e.time.date() if e else None
        
    #lc_changes = models.CharField(max_length=3) # used in DB, unused in Django code?
        
    #lc_expiration_date = models.DateField(null=True, blank=True)
    @property
    def lc_expiration_date(self):
        e = self.latest_event(LastCallDocEvent, type="sent_last_call")
        return e.expires.date() if e else None
        
    #b_sent_date = models.DateField(null=True, blank=True)
    @property
    def b_sent_date(self):
        e = self.latest_event(type="sent_ballot_announcement")
        return e.time.date() if e else None
        
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
        n = self.canonical_name()
        return int(n[3:]) if n.startswith("rfc") else None
        
    #comments = models.TextField(blank=True) # unused

    #last_modified_date = models.DateField()
    @property
    def last_modified_date(self):
        return self.time.date()
        
    #replaced_by = models.ForeignKey('self', db_column='replaced_by', blank=True, null=True, related_name='replaces_set')
    @property
    def replaced_by(self):
        r = InternetDraft.objects.filter(relateddocument__target__document=self, relateddocument__relationship="replaces")
        return r[0] if r else None

    @property
    def replaced_by_id(self):
        r = self.replaced_by
        return r.id_document_tag if r else None
        
    #replaces = FKAsOneToOne('replaces', reverse=True)
    @property
    def replaces(self):
        r = self.replaces_set
        return r[0] if r else None

    @property
    def replaces_set(self):
        return InternetDraft.objects.filter(docalias__relateddocument__source=self, docalias__relateddocument__relationship="replaces")
        
    #review_by_rfc_editor = models.BooleanField()
    @property
    def review_by_rfc_editor(self):
        return bool(self.tags.filter(slug='rfc-rev'))
        
    #expired_tombstone = models.BooleanField()
    @property
    def expired_tombstone(self):
        return False

    #shepherd = BrokenForeignKey('PersonOrOrgInfo', null=True, blank=True, null_values=(0, )) # same name

    #idinternal = FKAsOneToOne('idinternal', reverse=True, query=models.Q(rfc_flag = 0))
    @property
    def idinternal(self):
        # since IDInternal is now merged into the document, we try to
        # guess here
        if hasattr(self, "changed_ballot_position"):
            e = self.changed_ballot_position
        else:
            e = self.latest_event(type="changed_ballot_position")
        return self if e or self.get_state("draft-iesg") else None

    # reverse relationship
    @property
    def authors(self):
        return IDAuthor.objects.filter(document=self)

    @property
    def protowriteup_set(self):
        from ietf.wgchairs.models import ProtoWriteUpProxy
        return ProtoWriteUpProxy.objects.filter(doc=self, type="changed_protocol_writeup")

    # methods from InternetDraft
    def displayname(self):
        return self.name
    def file_tag(self):
        return "<%s>" % self.filename_with_rev()
    def filename_with_rev(self):
        return "%s-%s.txt" % (self.filename, self.revision_display())
    def group_acronym(self):
        g = super(Document, self).group
        if g.type_id == "area":
            return "none"
        else:
            return g.acronym
    def group_ml_archive(self):
	return self.group.list_archive
    def idstate(self):
	return self.docstate()
    def revision_display(self):
        return self.rev
    def expiration(self):
        return self.expires.date()
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

    @property
    def draft_id(self):
        return self.name
        
    #rfc_flag = models.IntegerField(null=True)
    @property
    def rfc_flag(self):
        return self.get_state_slug() == "rfc"
    
    #ballot = models.ForeignKey(BallotInfo, related_name='drafts', db_column="ballot_id")
    @property
    def ballot(self):
        if not self.idinternal:
            raise BallotInfo.DoesNotExist()
        return self
    @property
    def ballot_id(self):
        return self.ballot.name
    
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
        return self.ad.plain_name()

    #token_email = models.CharField(blank=True, max_length=255)
    @property
    def token_email(self):
        return self.ad.role_email("ad")
    
    #note = models.TextField(blank=True) # same name
    
    #status_date = models.DateField(blank=True,null=True)
    @property
    def status_date(self):
        return self.time.date()

    #email_display = models.CharField(blank=True, max_length=50) # unused
    #agenda = models.IntegerField(null=True, blank=True)
    @property
    def agenda(self):
        e = self.latest_event(TelechatDocEvent, type="scheduled_for_telechat")
        return bool(e and e.telechat_date and e.telechat_date >= datetime.date.today())
    
    #cur_state = models.ForeignKey(IDState, db_column='cur_state', related_name='docs')
    @property
    def cur_state(self):
        s = self.get_state("draft-iesg")
        return IDState().from_object(s) if s else None
    
    @property
    def cur_state_id(self):
        s = self.get_state("draft-iesg")
        return s.order if s else None
    
    #prev_state = models.ForeignKey(IDState, db_column='prev_state', related_name='docs_prev')
    @property
    def prev_state(self):
        ds = self.history_set.exclude(states=self.get_state("draft-iesg")).order_by('-time')[:1]
        if ds:
            s = ds[0].get_state("draft-iesg")
            if s:
                return IDState().from_object(s) if ds else None
        return None
    
    #assigned_to = models.CharField(blank=True, max_length=25) # unused

    #mark_by = models.ForeignKey(IESGLogin, db_column='mark_by', related_name='marked')
    @property
    def mark_by(self):
        e = self.latest_event()
        from ietf.person.proxy import IESGLogin as IESGLoginProxy
        return IESGLoginProxy().from_object(e.by) if e else None

    # job_owner = models.ForeignKey(IESGLogin, db_column='job_owner', related_name='documents')
    @property
    def job_owner(self):
        from ietf.person.proxy import IESGLogin as IESGLoginProxy
        return IESGLoginProxy().from_object(self.ad) if self.ad else None
    
    #event_date = models.DateField(null=True)
    @property
    def event_date(self):
        e = self.latest_event()
        return e.time if e else None
    
    #area_acronym = models.ForeignKey(Area)
    @property
    def area_acronym(self):
        from ietf.group.proxy import Area
        g = super(InternetDraft, self).group # be careful with group which is proxied
        if g:
            if g.type_id == "area":
                return Area().from_object(g)
            elif g.type_id != "individ":
                return Area().from_object(g.parent)
        else:
            return None
        
    #cur_sub_state = BrokenForeignKey(IDSubState, related_name='docs', null=True, blank=True, null_values=(0, -1))
    @property
    def cur_sub_state(self):
        s = self.tags.filter(slug__in=['extpty', 'need-rev', 'ad-f-up', 'point'])
        return IDSubState().from_object(s[0]) if s else None
    @property
    def cur_sub_state_id(self):
        s = self.cur_sub_state
        return s.order if s else None
    
    #prev_sub_state = BrokenForeignKey(IDSubState, related_name='docs_prev', null=True, blank=True, null_values=(0, -1))
    @property
    def prev_sub_state(self):
        ds = self.history_set.all().order_by('-time')[:1]
        substates = ds[0].tags.filter(slug__in=['extpty', 'need-rev', 'ad-f-up', 'point']) if ds else None
        return IDSubState().from_object(substates[0]) if substates else None
    @property
    def prev_sub_state_id(self):
        s = self.prev_sub_state
        return s.order if s else None
    
    #returning_item = models.IntegerField(null=True, blank=True)
    @property
    def returning_item(self):
        e = self.latest_event(TelechatDocEvent, type="scheduled_for_telechat")
        return e.returning_item if e else None

    #telechat_date = models.DateField(null=True, blank=True)
    @property
    def telechat_date(self):
        e = self.latest_event(TelechatDocEvent, type="scheduled_for_telechat")
        return e.telechat_date if e else None

    #via_rfc_editor = models.IntegerField(null=True, blank=True)
    @property
    def via_rfc_editor(self):
        return self.stream_id in ('ise','irtf')
    
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
        from ietf.person.proxy import IESGLogin as IESGLoginProxy
        return IESGLoginProxy().from_object(e.by) if e and e.type == "requested_resurrect" else None
    
    #approved_in_minute = models.IntegerField(null=True, blank=True)
    @property
    def approved_in_minute(self):
        return self.latest_event(type="approved_in_minute")
        
    
    def get_absolute_url(self):
	if self.rfc_flag and self.rfc_number:
	    return "/doc/rfc%d/" % self.rfc_number
	else:
	    return "/doc/%s/" % self.name
        
    def document(self):
        return self
    
    def comments(self):
        return DocumentComment.objects.filter(doc=self).order_by('-time')

    def public_comments(self):
        return self.comments()
    
    def ballot_set(self):
        return [self]
    def ballot_primary(self):
        return [self]
    def ballot_others(self):
        return []
    def docstate(self):
        s = self.get_state("draft-iesg")
        if s:
            subs = self.cur_sub_state
            if subs:
                return "%s::%s" % (s.name, subs)
            return s.name
        else:
            return "I-D Exists"

    # things from BallotInfo
    #active = models.BooleanField()
    @property
    def active(self):
        # taken from BallotWrapper
        s = self.get_state("draft-iesg")
        return self.latest_event(type="sent_ballot_announcement") and s and s.name in ['In Last Call', 'Waiting for Writeup', 'Waiting for AD Go-Ahead', 'IESG Evaluation', 'IESG Evaluation - Defer'] and (self.get_state_slug() in ("rfc", "active"))

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
        from ietf.person.proxy import IESGLogin as IESGLoginProxy
        return IESGLoginProxy().from_object(e.by) if e else None

    #defer = models.BooleanField()
    @property
    def defer(self):
        # we're deferred if we're in the deferred state
        return self.get_state_slug("draft-iesg") == "defer"

    #defer_by = models.ForeignKey(IESGLogin, db_column='defer_by', related_name='deferred', null=True)
    @property
    def defer_by(self):
        e = self.latest_event(type="changed_document", desc__startswith="State changed to <b>IESG Evaluation - Defer</b>")
        from ietf.person.proxy import IESGLogin as IESGLoginProxy
        return IESGLoginProxy().from_object(e.by) if e else None
    
    #defer_date = models.DateField(null=True, blank=True)
    @property
    def defer_date(self):
        e = self.latest_event(type="changed_document", desc__startswith="State changed to <b>IESG Evaluation - Defer</b>")
        return e.time.date() if e else None

    #approval_text = models.TextField(blank=True)
    @property
    def approval_text(self):
        e = self.latest_event(WriteupDocEvent, type="changed_ballot_approval_text")
        return e.text if e else ""
    
    #last_call_text = models.TextField(blank=True)
    @property
    def last_call_text(self):
        e = self.latest_event(WriteupDocEvent, type="changed_last_call_text")
        return e.text if e else ""
    
    #ballot_writeup = models.TextField(blank=True)
    @property
    def ballot_writeup(self):
        e = self.latest_event(WriteupDocEvent, type="changed_ballot_writeup_text")
        return e.text if e else ""

    #ballot_issued = models.IntegerField(null=True, blank=True)
    @property
    def ballot_issued(self):
        return bool(self.latest_event(type="sent_ballot_announcement"))
    
    # def remarks(self): # apparently not used
    #     remarks = list(self.discusses.all()) + list(self.comments.all())
    #     return remarks
    def active_positions(self):
        """Returns a list of dicts, with AD and Position tuples"""
        from ietf.person.proxy import IESGLogin as IESGLoginProxy

        res = []
        for ad, pos in self.active_ballot().active_ad_positions().iteritems():
            res.append(dict(ad=IESGLoginProxy().from_object(ad), pos=Position().from_object(pos) if pos else None))

        res.sort(key=lambda x: x["ad"].last_name)

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
            p = position.pos_id
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
        if hasattr(self, 'published_rfc'):
            e = self.published_rfc
        else:
            e = self.latest_event(type="published_rfc")
        return e.time.date() if e else datetime.date(1990,1,1)
    
    #current_status = models.CharField(max_length=50,null=True)
    @property
    def current_status(self):
        if self.std_level:
            return self.std_level.name
        else:
            return u"(None)"

    #updates = models.CharField(max_length=200,blank=True,null=True)
    @property
    def updates(self):
        return ",".join("RFC%s" % n for n in sorted(d.rfc_number for d in InternetDraft.objects.filter(docalias__relateddocument__source=self, docalias__relateddocument__relationship="updates")))

    #updated_by = models.CharField(max_length=200,blank=True,null=True)
    @property
    def updated_by(self):
        if not hasattr(self, "updated_by_list"):
            self.updated_by_list = [d.rfc_number for d in InternetDraft.objects.filter(relateddocument__target__document=self, relateddocument__relationship="updates")]
        return ",".join("RFC%s" % n for n in sorted(self.updated_by_list))

    #obsoletes = models.CharField(max_length=200,blank=True,null=True)
    @property
    def obsoletes(self):
        return ",".join("RFC%s" % n for n in sorted(d.rfc_number for d in InternetDraft.objects.filter(docalias__relateddocument__source=self, docalias__relateddocument__relationship="obs")))

    #obsoleted_by = models.CharField(max_length=200,blank=True,null=True)
    @property
    def obsoleted_by(self):
        if not hasattr(self, "obsoleted_by_list"):
            self.obsoleted_by_list = [d.rfc_number for d in InternetDraft.objects.filter(relateddocument__target__document=self, relateddocument__relationship="obs")]
        return ",".join("RFC%s" % n for n in sorted(self.obsoleted_by_list))

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
        s = super(InternetDraft, self).stream
        return s.name if s else None

    #wg = models.CharField(max_length=15,blank=True,null=True)
    @property
    def wg(self):
        return self.group.acronym

    #file_formats = models.CharField(max_length=20,blank=True,null=True)
    @property
    def file_formats(self):
        return self.get_file_type_matches_from(os.path.join(settings.RFC_PATH, "rfc" + str(self.rfc_number))).replace(".", "").replace("txt", "ascii")

    @property
    def positions(self):
	res = []
        found = set()
	for pos in Position.objects.filter(doc=self, type="changed_ballot_position").select_related('ad').order_by("-time", "-id"):
            if pos.ad not in found:
                found.add(pos.ad)
                res.append(pos)

        class Dummy:
            def all(self):
                return self.res
        d = Dummy()
        d.res = res
        return d

    @property
    def ipr(self):
        from ietf.ipr.models import IprDraftProxy
        return IprDraftProxy.objects.filter(doc_alias__document=self.pk)
    
    class Meta:
        proxy = True

IDInternal = InternetDraft
BallotInfo = InternetDraft
RfcIndex = InternetDraft
Rfc = InternetDraft


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

class DocumentComment(DocEvent):
    objects = TranslatingManager(dict(comment_text="desc",
                                      date="time"
                                      ))

    BALLOT_DISCUSS = 1
    BALLOT_COMMENT = 2
    BALLOT_CHOICES = (
	(BALLOT_DISCUSS, 'discuss'),
	(BALLOT_COMMENT, 'comment'),
    )
    #document = models.ForeignKey(IDInternal)
    @property
    def document(self):
        return self.doc
    #rfc_flag = models.IntegerField(null=True, blank=True)
    #public_flag = models.BooleanField() #unused
    #date = models.DateField(db_column='comment_date', default=datetime.date.today)
    @property
    def date(self):
        return self.time.date()
    #time = models.CharField(db_column='comment_time', max_length=20, default=lambda: datetime.datetime.now().strftime("%H:%M:%S"))
    #version = models.CharField(blank=True, max_length=3)
    @property
    def version(self):
        e = self.doc.latest_event(NewRevisionDocEvent, type="new_revision", time__lte=self.time)
        return e.rev if e else "0"
    #comment_text = models.TextField(blank=True)
    @property
    def comment_text(self):
        return self.desc
    #created_by = BrokenForeignKey(IESGLogin, db_column='created_by', null=True, null_values=(0, 999))
    #result_state = BrokenForeignKey(IDState, db_column='result_state', null=True, related_name="comments_leading_to_state", null_values=(0, 99))
    #origin_state = models.ForeignKey(IDState, db_column='origin_state', null=True, related_name="comments_coming_from_state")
    #ballot = models.IntegerField(null=True, choices=BALLOT_CHOICES)
    def get_absolute_url(self):
        return "/doc/%s/" % self.doc.name
    def get_author(self):
        return self.by.plain_name()
    def get_username(self):
        return unicode(self.by)
    def get_fullname(self):
        return self.by.plain_name()
    def datetime(self):
        return self.time
    def doc_id(self):
        return self.doc_id
    def doc_name(self):
        return self.doc.name
    def __str__(self):
        return "\"%s...\" by %s" % (self.comment_text[:20], self.get_author())
    
    class Meta:
        proxy = True


class Position(BallotPositionDocEvent):
    def from_object(self, base):
        for f in base._meta.fields:
            if not f.name in ('discuss', 'ad', 'ballot', ): # don't overwrite properties
                setattr(self, f.name, getattr(base, f.name))

        self.orig = base
        return self
    
    #ballot = models.ForeignKey(BallotInfo, related_name='positions')
    @property
    def ballot(self):
        return self.doc # FIXME: doesn't emulate old interface
    
    # ad = models.ForeignKey(IESGLogin) # same name
    @property
    def ad(self):
        from ietf.person.proxy import IESGLogin
        return IESGLogin().from_object(self.orig.ad if hasattr(self, "orig") else super(Position, self).ad)

    #yes = models.IntegerField(db_column='yes_col')
    @property
    def yes(self):
        return self.pos_id == "yes"
    #noobj = models.IntegerField(db_column='no_col')
    @property
    def noobj(self):
        return self.pos_id == "noobj"
    #abstain = models.IntegerField()
    @property
    def abstain(self):
        return self.pos_id == "abstain"
    #approve = models.IntegerField(default=0) # unused
    #discuss = models.IntegerField()
    # needs special treatment because of clash with attribute on base class
    def get_discuss(self):
        return self.pos_id == "discuss"
    def set_discuss(self, x):
        pass
    discuss = property(get_discuss, set_discuss)
    #recuse = models.IntegerField()
    @property
    def recuse(self):
        return self.pos_id == "recuse"
    def __str__(self):
	return "Position for %s on %s" % ( self.ad, self.ballot )
    def abstain_ind(self):
        if self.recuse:
            return 'R'
        if self.abstain:
            return 'X'
        else:
            return ' '
    def name(self):
        return self.pos.name if self.pos else "No Record"
    
    class Meta:
        proxy = True

class DraftLikeDocAlias(DocAlias):
    # this class is mostly useful for the IPR part

    def __str__(self):
        return str(unicode(self))
    
    def __unicode__(self):
        if self.name.startswith("rfc"):
            return "RFC%04d" % int(self.name[3:])
        else:
            return self.name

    @property
    def id_document_tag(self):
        return self.name
        
    @property
    def title(self):
        return self.document.title

    @property
    def filename(self):
        return self.name

    @property
    def ipr(self):
        from ietf.ipr.models import IprDraftProxy
        return IprDraftProxy.objects.filter(doc_alias=self.pk)
    
    class Meta:
        proxy = True

class ObjectHistoryEntryProxy(DocEvent):
    #date = models.DateTimeField(_('Date'), auto_now_add=True)
    @property
    def date(self):
        return self.time
    #comment = models.TextField(_('Comment'))
    @property
    def comment(self):
        return ""
    #person = models.ForeignKey(PersonOrOrgInfo)
    @property
    def person(self):
        return self.by

    def get_real_instance(self):
        return self

    def describe_change(self):
        return u"<p>%s</p>" % self.desc

    class Meta:
        proxy = True

class IDStatus(State):
    def from_object(self, base):
        for f in base._meta.fields:
            setattr(self, f.name, getattr(base, f.name))
        return self
                
    #status_id = models.AutoField(primary_key=True)
    
    #status = models.CharField(max_length=25, db_column='status_value')
    @property
    def status(self):
        return self.name

    def __unicode__(self):
        return super(self.__class__, self).__unicode__()
    
    class Meta:
        proxy = True

class IDState(State):
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
    
    objects = TranslatingManager(dict(pk=lambda v: ("order", v, "type", "draft-iesg"),
                                      document_state_id=lambda v: ("order", v, "type", "draft-iesg"),
                                      document_state_id__in=lambda v: ("order__in", v, "type", "draft-iesg")),
                                 always_filter=dict(type="draft-iesg"))
    
    def from_object(self, base):
        for f in base._meta.fields:
            setattr(self, f.name, getattr(base, f.name))
        return self
                
    #document_state_id = models.AutoField(primary_key=True)
    @property
    def document_state_id(self):
        return self.order
        
    #state = models.CharField(max_length=50, db_column='document_state_val')
    @property
    def state(self):
        return self.name
    
    #equiv_group_flag = models.IntegerField(null=True, blank=True) # unused
    #description = models.TextField(blank=True, db_column='document_desc')
    @property
    def description(self):
        return self.desc

    @property
    def nextstate(self):
        # simulate related queryset
        return IDState.objects.filter(pk__in=[x.pk for x in self.next_states.all()])
    
    @property
    def next_state(self):
        # simulate IDNextState
        return self

    def __str__(self):
        return self.state

    @staticmethod
    def choices():
	return [(state.pk, state.name) for state in IDState.objects.all()]
    
    class Meta:
        proxy = True
        

