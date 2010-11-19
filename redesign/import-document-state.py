#!/usr/bin/python

import sys, os, re, datetime

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path = [ basedir ] + sys.path

from ietf import settings
settings.USE_DB_REDESIGN_PROXY_CLASSES = False

from django.core import management
management.setup_environ(settings)

from redesign.doc.models import *
from redesign.group.models import *
from redesign.name.models import *
from ietf.idtracker.models import InternetDraft, IESGLogin, DocumentComment

# assumptions:
# - groups have been imported
# - iesglogin emails have been imported

# FIXME: what about RFCs

def name(name_class, slug, name, desc=""):
    # create if it doesn't exist, set name
    obj, _ = name_class.objects.get_or_create(slug=slug)
    obj.name = name
    obj.desc = desc
    obj.save()
    return obj

type_draft = name(DocTypeName, "draft", "Draft")
stream_ietf = name(DocStreamName, "ietf", "IETF")

intended_status_mapping = {
    "BCP": name(IntendedStatusName, "bcp", "Best Current Practice"),
    "Draft Standard": name(IntendedStatusName, "ds", name="Draft Standard"),
    "Experimental": name(IntendedStatusName, "exp", name="Experimental"),
    "Historic": name(IntendedStatusName, "hist", name="Historic"),
    "Informational": name(IntendedStatusName, "inf", name="Informational"),
    "Proposed Standard": name(IntendedStatusName, "ps", name="Proposed Standard"),
    "Standard": name(IntendedStatusName, "std", name="Standard"),
    "None": None,
    "Request": None, # FIXME: correct? from idrfc_wrapper.py
    }

status_mapping = {
    'Active': name(DocStateName, "active", "Active"),
    'Expired': name(DocStateName, "expired", "Expired"),
    'RFC': name(DocStateName, "rfc", "RFC"),
    'Withdrawn by Submitter': name(DocStateName, "auth-rm", "Withdrawn by Submitter"),
    'Replaced': name(DocStateName, "repl", "Replaced"),
    'Withdrawn by IETF': name(DocStateName, "ietf-rm", "Withdrawn by IETF"),
    }

iesg_state_mapping = {
    'RFC Published': name(IesgDocStateName, "pub", "RFC Published", 'The ID has been published as an RFC.'),
    'Dead': name(IesgDocStateName, "dead", "Dead", 'Document is "dead" and is no longer being tracked. (E.g., it has been replaced by another document with a different name, it has been withdrawn, etc.)'),
    'Approved-announcement to be sent': name(IesgDocStateName, "approved", "Approved-announcement to be sent", 'The IESG has approved the document for publication, but the Secretariat has not yet sent out on official approval message.'),
    'Approved-announcement sent': name(IesgDocStateName, "ann", "Approved-announcement sent", 'The IESG has approved the document for publication, and the Secretariat has sent out the official approval message to the RFC editor.'),
    'AD is watching': name(IesgDocStateName, "watching", "AD is watching", 'An AD is aware of the document and has chosen to place the document in a separate state in order to keep a closer eye on it (for whatever reason). Documents in this state are still not being actively tracked in the sense that no formal request has been made to publish or advance the document. The sole difference between this state and "I-D Exists" is that an AD has chosen to put it in a separate state, to make it easier to keep track of (for the AD\'s own reasons).'),
    'IESG Evaluation': name(IesgDocStateName, "iesg-eva", "IESG Evaluation", 'The document is now (finally!) being formally reviewed by the entire IESG. Documents are discussed in email or during a bi-weekly IESG telechat. In this phase, each AD reviews the document and airs any issues they may have. Unresolvable issues are documented as "discuss" comments that can be forwarded to the authors/WG. See the description of substates for additional details about the current state of the IESG discussion.'),
    'AD Evaluation': name(IesgDocStateName, "ad-eval", "AD Evaluation", 'A specific AD (e.g., the Area Advisor for the WG) has begun reviewing the document to verify that it is ready for advancement. The shepherding AD is responsible for doing any necessary review before starting an IETF Last Call or sending the document directly to the IESG as a whole.'),
    'Last Call Requested': name(IesgDocStateName, "lc-req", "Last Call requested", 'The AD has requested that the Secretariat start an IETF Last Call, but the the actual Last Call message has not been sent yet.'),
    'In Last Call': name(IesgDocStateName, "lc", "In Last Call", 'The document is currently waiting for IETF Last Call to complete. Last Calls for WG documents typically last 2 weeks, those for individual submissions last 4 weeks.'),
    'Publication Requested': name(IesgDocStateName, "pub-req", "Publication Requested", 'A formal request has been made to advance/publish the document, following the procedures in Section 7.5 of RFC 2418. The request could be from a WG chair, from an individual through the RFC Editor, etc. (The Secretariat (iesg-secretary@ietf.org) is copied on these requests to ensure that the request makes it into the ID tracker.) A document in this state has not (yet) been reviewed by an AD nor has any official action been taken on it yet (other than to note that its publication has been requested.'),
    'RFC Ed Queue': name(IesgDocStateName, "rfcqueue", "RFC Ed Queue", 'The document is in the RFC editor Queue (as confirmed by http://www.rfc-editor.org/queue.html).'),
    'IESG Evaluation - Defer': name(IesgDocStateName, "defer", "IESG Evaluation - Defer", 'During a telechat, one or more ADs requested an additional 2 weeks to review the document. A defer is designed to be an exception mechanism, and can only be invoked once, the first time the document comes up for discussion during a telechat.'),
    'Waiting for Writeup': name(IesgDocStateName, "writeupw", "Waiting for Writeup", 'Before a standards-track or BCP document is formally considered by the entire IESG, the AD must write up a protocol action. The protocol action is included in the approval message that the Secretariat sends out when the document is approved for publication as an RFC.'),
    'Waiting for AD Go-Ahead': name(IesgDocStateName, "goaheadw", "Waiting for AD Go-Ahead", 'As a result of the IETF Last Call, comments may need to be responded to and a revision of the ID may be needed as well. The AD is responsible for verifying that all Last Call comments have been adequately addressed and that the (possibly revised) document is in the ID directory and ready for consideration by the IESG as a whole.'),
    'Expert Review': name(IesgDocStateName, "review-e", "Expert Review", 'An AD sometimes asks for an external review by an outside party as part of evaluating whether a document is ready for advancement. MIBs, for example, are reviewed by the "MIB doctors". Other types of reviews may also be requested (e.g., security, operations impact, etc.). Documents stay in this state until the review is complete and possibly until the issues raised in the review are addressed. See the "note" field for specific details on the nature of the review.'),
    'DNP-waiting for AD note': name(IesgDocStateName, "nopubadw", "DNP-waiting for AD note", 'Do Not Publish: The IESG recommends against publishing the document, but the writeup explaining its reasoning has not yet been produced. DNPs apply primarily to individual submissions received through the RFC editor.  See the "note" field for more details on who has the action item.'),
    'DNP-announcement to be sent': name(IesgDocStateName, "nopubanw", "DNP-announcement to be sent", 'The IESG recommends against publishing the document, the writeup explaining its reasoning has been produced, but the Secretariat has not yet sent out the official "do not publish" recommendation message.'),
    None: None, # FIXME: consider introducing the ID-exists state
    }

ballot_position_mapping = {
    'No Objection': name(BallotPositionName, 'noobj', 'No Objection'),
    'Yes': name(BallotPositionName, 'yes', 'Yes'),
    'Abstain': name(BallotPositionName, 'abstain', 'Abstain'),
    'Discuss': name(BallotPositionName, 'discuss', 'Discuss'),
    'Recuse': name(BallotPositionName, 'recuse', 'Recuse'),
    'Undefined': name(BallotPositionName, 'norecord', 'No record'),
    None: name(BallotPositionName, 'norecord', 'No record'),
    }

# regexps for parsing document comments

date_re_str = "(?P<year>[0-9][0-9][0-9][0-9])-(?P<month>[0-9][0-9])-(?P<day>[0-9][0-9])"
def date_in_match(match):
    return datetime.date(int(match.group('year')), int(match.group('month')), int(match.group('day')))

re_telechat_agenda = re.compile(r"(Placed on|Removed from) agenda for telechat - %s by" % date_re_str)
re_ballot_position = re.compile(r"\[Ballot Position Update\] (New position, (?P<position>.*), has been recorded (|for (?P<for>.*) )|Position (|for (?P<for2>.*) )has been changed to (?P<position2>.*) from .*)by (?P<by>.*)")
re_ballot_issued = re.compile(r"Ballot has been issued by")

# helpers for events

def save_event(doc, event, comment):
    event.time = comment.datetime()
    event.by = iesg_login_to_email(comment.created_by)
    event.doc = doc
    event.desc = comment.comment_text # FIXME: consider unquoting here
    event.save()

def iesg_login_to_email(l):
    if not l:
        return None
    else:
        try:
            return Email.objects.get(address=l.person.email()[1])
        except Email.DoesNotExist:
            print "MISSING IESG LOGIN", l.person.email()
            return None

    
        
all_drafts = InternetDraft.objects.all().select_related()
all_drafts = all_drafts.filter(filename="draft-arkko-townsley-coexistence")
#all_drafts = all_drafts[all_drafts.count() - 1000:]

for o in all_drafts:
    try:
        d = Document.objects.get(name=o.filename)
    except Document.DoesNotExist:
        d = Document(name=o.filename)
        
    d.time = o.idinternal.event_date if o.idinternal else o.revision_date
    d.type = type_draft
    d.title = o.title
    d.state = status_mapping[o.status.status]
    d.group = Group.objects.get(acronym=o.group.acronym)
#    d.tags =
    d.stream = stream_ietf
    d.wg_state = None
    d.iesg_state = iesg_state_mapping[o.idinternal.cur_state.state if o.idinternal else None]
    d.iana_state = None
#    d.rfc_state =
    d.rev = o.revision
    d.abstract = o.abstract
    d.pages = o.txt_page_count
    d.intended_std_level = intended_status_mapping[o.intended_status.intended_status]
#    d.std_level =
#    d.authors =
#    d.related =
    d.ad = iesg_login_to_email(o.idinternal.job_owner)
    d.shepherd = None
    d.notify = o.idinternal.state_change_notice_to or "" if o.idinternal else ""
    d.external_url = ""
    d.note = o.idinternal.note or "" if o.idinternal else ""
    d.internal_comments = o.comments or "" # FIXME: maybe put these somewhere else
    d.save()

    if o.idinternal:
        # clear already imported events
        d.event_set.all().delete()
        
        # extract events
        for c in o.idinternal.documentcomment_set.order_by('date', 'time', 'id'):
            # telechat agenda schedulings
            match = re_telechat_agenda.search(c.comment_text)
            if match:
                e = Telechat()
                e.type = "scheduled_for_telechat"
                e.telechat_date = date_in_match(match)
                # can't extract this from history so we just take the latest value
                e.returning_item = bool(o.idinternal.returning_item)
                save_event(d, e, c)

                
            # ballot issued
            match = re_ballot_issued.search(c.comment_text)
            if match:
                e = Text()
                e.type = "sent_ballot_announcement"
                save_event(d, e, c)

                # when you issue a ballot, you also vote yes; add that vote
                e = BallotPosition()
                e.type = "changed_ballot_position"
                e.ad = iesg_login_to_email(c.created_by)
                last_pos = d.latest_event(type="changed_ballot_position", ballotposition__ad=e.ad)
                e.pos = ballot_position_mapping["Yes"]
                e.discuss = last_pos.ballotposition.discuss if last_pos else ""
                e.discuss_time = last_pos.ballotposition.discuss_time if last_pos else None
                e.comment = last_pos.ballotposition.comment if last_pos else ""
                e.comment_time = last_pos.ballotposition.comment_time if last_pos else None
                save_event(d, e, c)
                
                
            # ballot positions
            match = re_ballot_position.search(c.comment_text)
            if match:
                position = match.group('position') or match.group('position2')
                ad_name = match.group('for') or match.group('for2') or match.group('by') # some of the old positions don't specify who it's for, in that case assume it's "by", the person who entered the position
                ad_first, ad_last = ad_name.split(' ')

                e = BallotPosition()
                e.type = "changed_ballot_position"
                e.ad = iesg_login_to_email(IESGLogin.objects.get(first_name=ad_first, last_name=ad_last))
                last_pos = d.latest_event(type="changed_ballot_position", ballotposition__ad=e.ad)
                e.pos = ballot_position_mapping[position]
                e.discuss = last_pos.ballotposition.discuss if last_pos else ""
                e.discuss_time = last_pos.ballotposition.discuss_time if last_pos else None
                e.comment = last_pos.ballotposition.comment if last_pos else ""
                e.comment_time = last_pos.ballotposition.comment_time if last_pos else None
                save_event(d, e, c)


            # ballot discusses/comments
            if c.ballot in (DocumentComment.BALLOT_DISCUSS, DocumentComment.BALLOT_COMMENT):
                e = BallotPosition()
                e.type = "changed_ballot_position"
                e.ad = iesg_login_to_email(c.created_by)
                last_pos = d.latest_event(type="changed_ballot_position", ballotposition__ad=e.ad)
                e.pos = last_pos.ballotposition.pos if last_pos else ballot_position_mapping[None]
                if c.ballot == DocumentComment.BALLOT_DISCUSS:
                    e.discuss = c.comment_text
                    e.discuss_time = c.datetime()
                    e.comment = last_pos.ballotposition.comment if last_pos else ""
                    e.comment_time = last_pos.ballotposition.comment_time if last_pos else None
                    # put header into description
                    c.comment_text = "[Ballot discuss]\n" + c.comment_text
                else:
                    e.discuss = last_pos.ballotposition.discuss if last_pos else ""
                    e.discuss_time = last_pos.ballotposition.discuss_time if last_pos else None
                    e.comment = c.comment_text
                    e.comment_time = c.datetime()
                    # put header into description
                    c.comment_text = "[Ballot comment]\n" + c.comment_text
                save_event(d, e, c)
        
    
    print "imported", d.name, "state", d.iesg_state

    

# checklist of attributes below: handled attributes are commented out

sys.exit(0)
    
class CheckListInternetDraft(models.Model):
#    id_document_tag = models.AutoField(primary_key=True)
#    title = models.CharField(max_length=255, db_column='id_document_name')
#    id_document_key = models.CharField(max_length=255, editable=False)
#    group = models.ForeignKey(Acronym, db_column='group_acronym_id')
#    filename = models.CharField(max_length=255, unique=True)
#    revision = models.CharField(max_length=2)
    revision_date = models.DateField()
    file_type = models.CharField(max_length=20)
#    txt_page_count = models.IntegerField()
    local_path = models.CharField(max_length=255, blank=True, null=True)
    start_date = models.DateField()
    expiration_date = models.DateField(null=True)
#    abstract = models.TextField()
    dunn_sent_date = models.DateField(null=True, blank=True)
    extension_date = models.DateField(null=True, blank=True)
#    status = models.ForeignKey(IDStatus)
#    intended_status = models.ForeignKey(IDIntendedStatus)
    lc_sent_date = models.DateField(null=True, blank=True)
    lc_changes = models.CharField(max_length=3,null=True)
    lc_expiration_date = models.DateField(null=True, blank=True)
    b_sent_date = models.DateField(null=True, blank=True)
    b_discussion_date = models.DateField(null=True, blank=True)
    b_approve_date = models.DateField(null=True, blank=True)
    wgreturn_date = models.DateField(null=True, blank=True)
    rfc_number = models.IntegerField(null=True, blank=True, db_index=True)
#    comments = models.TextField(blank=True,null=True)
    last_modified_date = models.DateField()
    replaced_by = BrokenForeignKey('self', db_column='replaced_by', blank=True, null=True, related_name='replaces_set')
    replaces = FKAsOneToOne('replaces', reverse=True)
    review_by_rfc_editor = models.BooleanField()
    expired_tombstone = models.BooleanField()
#    idinternal = FKAsOneToOne('idinternal', reverse=True, query=models.Q(rfc_flag = 0))
    
class CheckListIDInternal(models.Model):
#    draft = models.ForeignKey(InternetDraft, primary_key=True, unique=True, db_column='id_document_tag')
    rfc_flag = models.IntegerField(null=True)
    ballot = models.ForeignKey('BallotInfo', related_name='drafts', db_column="ballot_id")
    primary_flag = models.IntegerField(blank=True, null=True)
    group_flag = models.IntegerField(blank=True, default=0)
    token_name = models.CharField(blank=True, max_length=25)
    token_email = models.CharField(blank=True, max_length=255)
#    note = models.TextField(blank=True)
    status_date = models.DateField(blank=True,null=True)
    email_display = models.CharField(blank=True, max_length=50)
    agenda = models.IntegerField(null=True, blank=True)
#    cur_state = models.ForeignKey(IDState, db_column='cur_state', related_name='docs')
    prev_state = models.ForeignKey(IDState, db_column='prev_state', related_name='docs_prev')
    assigned_to = models.CharField(blank=True, max_length=25)
    mark_by = models.ForeignKey('IESGLogin', db_column='mark_by', related_name='marked')
#    job_owner = models.ForeignKey(IESGLogin, db_column='job_owner', related_name='documents')
    event_date = models.DateField(null=True)
    area_acronym = models.ForeignKey('Area')
    cur_sub_state = BrokenForeignKey('IDSubState', related_name='docs', null=True, blank=True, null_values=(0, -1))
    prev_sub_state = BrokenForeignKey('IDSubState', related_name='docs_prev', null=True, blank=True, null_values=(0, -1))
#    returning_item = models.IntegerField(null=True, blank=True)
#    telechat_date = models.DateField(null=True, blank=True)
    via_rfc_editor = models.IntegerField(null=True, blank=True)
#    state_change_notice_to = models.CharField(blank=True, max_length=255)
    dnp = models.IntegerField(null=True, blank=True)
    dnp_date = models.DateField(null=True, blank=True)
    noproblem = models.IntegerField(null=True, blank=True)
    resurrect_requested_by = BrokenForeignKey('IESGLogin', db_column='resurrect_requested_by', related_name='docsresurrected', null=True, blank=True)
    approved_in_minute = models.IntegerField(null=True, blank=True)

class CheckListBallotInfo(models.Model):
    ballot = models.AutoField(primary_key=True, db_column='ballot_id')
    active = models.BooleanField()
    an_sent = models.BooleanField()
    an_sent_date = models.DateField(null=True, blank=True)
    an_sent_by = models.ForeignKey('IESGLogin', db_column='an_sent_by', related_name='ansent', null=True)
    defer = models.BooleanField(blank=True)
    defer_by = models.ForeignKey('IESGLogin', db_column='defer_by', related_name='deferred', null=True)
    defer_date = models.DateField(null=True, blank=True)
    approval_text = models.TextField(blank=True)
    last_call_text = models.TextField(blank=True)
    ballot_writeup = models.TextField(blank=True)
    ballot_issued = models.IntegerField(null=True, blank=True)
