#!/usr/bin/python

import sys, os, re, datetime

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path = [ basedir ] + sys.path

from ietf import settings
settings.USE_DB_REDESIGN_PROXY_CLASSES = False

from django.core import management
management.setup_environ(settings)

from django.template.defaultfilters import pluralize

from ietf.doc.models import *
from ietf.doc.utils import get_tags_for_stream_id
from ietf.group.models import *
from ietf.name.models import *
from ietf.person.models import *
from ietf.person.name import name_parts
from redesign.importing.utils import old_person_to_person, person_name, dont_save_queries
from ietf.name.utils import name
from ietf.idtracker.models import InternetDraft, IDInternal, IESGLogin, DocumentComment, PersonOrOrgInfo, Rfc, IESGComment, IESGDiscuss, BallotInfo, Position, Area
from ietf.idrfc.models import RfcIndex, DraftVersions
from ietf.idrfc.mirror_rfc_index import get_std_level_mapping, get_stream_mapping
from ietf.ietfworkflows.models import StreamedID, AnnotationTag, ContentType, ObjectHistoryEntry, ObjectWorkflowHistoryEntry, ObjectAnnotationTagHistoryEntry, ObjectStreamHistoryEntry, StateObjectRelationMetadata
from ietf.wgchairs.models import ProtoWriteUp

from workflows.models import State as StateOld

import_docs_from = document_name_to_import = None
if len(sys.argv) > 1:
    try:
        import_docs_from = datetime.datetime.strptime(sys.argv[1], "%Y-%m-%d")
    except:
        document_name_to_import = sys.argv[1]

dont_save_queries()

# assumptions:
# - states have been imported
# - groups have been imported
# - IESG login emails/roles have been imported
# - IDAuthor emails/persons have been imported

# Regarding history, we currently don't try to create DocumentHistory
# objects, we just import the comments as events.

# imports drafts and RFCs, more specifically InternetDraft,
# IDInternal, BallotInfo, Position, IESGComment, IESGDiscuss,
# DocumentComment, IDAuthor, idrfc.RfcIndex, idrfc.DraftVersions,
# StreamedID


def alias_doc(name, doc):
    DocAlias.objects.filter(name=name).exclude(document=doc).delete()
    alias, _ = DocAlias.objects.get_or_create(name=name, document=doc)
    return alias

type_draft = name(DocTypeName, "draft", "Draft")

stream_mapping = get_stream_mapping()
stream_mapping["ISE"] = stream_mapping["INDEPENDENT"]

relationship_replaces = name(DocRelationshipName, "replaces", "Replaces")
relationship_updates = name(DocRelationshipName, "updates", "Updates")
relationship_obsoletes = name(DocRelationshipName, "obs", "Obsoletes")

intended_std_level_mapping = {
    "Proposed Standard": name(IntendedStdLevelName, "ps", name="Proposed Standard", order=1),
    "Draft Standard": name(IntendedStdLevelName, "ds", name="Draft Standard", order=2),
    "Standard": name(IntendedStdLevelName, "std", name="Standard", order=3),
    "BCP": name(IntendedStdLevelName, "bcp", "Best Current Practice", order=4),
    "Informational": name(IntendedStdLevelName, "inf", name="Informational", order=5),
    "Experimental": name(IntendedStdLevelName, "exp", name="Experimental", order=6),
    "Historic": name(IntendedStdLevelName, "hist", name="Historic", order=7),
    "None": None,
    "Request": None,
    }

# add aliases from rfc_intend_status 
intended_std_level_mapping["Proposed"] = intended_std_level_mapping["Proposed Standard"]
intended_std_level_mapping["Draft"] = intended_std_level_mapping["Draft Standard"]

std_level_mapping = get_std_level_mapping()

state_mapping = {
    'Active': State.objects.get(type="draft", slug="active"),
    'Expired': State.objects.get(type="draft", slug="expired"),
    'RFC': State.objects.get(type="draft", slug="rfc"),
    'Withdrawn by Submitter': State.objects.get(type="draft", slug="auth-rm"),
    'Replaced': State.objects.get(type="draft", slug="repl"),
    'Withdrawn by IETF': State.objects.get(type="draft", slug="ietf-rm"),
    }

iesg_state_mapping = {
    'RFC Published': State.objects.get(type="draft-iesg", slug="pub"),
    'Dead': State.objects.get(type="draft-iesg", slug="dead"),
    'Approved-announcement to be sent': State.objects.get(type="draft-iesg", slug="approved"),
    'Approved-announcement sent': State.objects.get(type="draft-iesg", slug="ann"),
    'AD is watching': State.objects.get(type="draft-iesg", slug="watching"),
    'IESG Evaluation': State.objects.get(type="draft-iesg", slug="iesg-eva"),
    'AD Evaluation': State.objects.get(type="draft-iesg", slug="ad-eval"),
    'Last Call Requested': State.objects.get(type="draft-iesg", slug="lc-req"),
    'In Last Call': State.objects.get(type="draft-iesg", slug="lc"),
    'Publication Requested': State.objects.get(type="draft-iesg", slug="pub-req"),
    'RFC Ed Queue': State.objects.get(type="draft-iesg", slug="rfcqueue"),
    'IESG Evaluation - Defer': State.objects.get(type="draft-iesg", slug="defer"),
    'Waiting for Writeup': State.objects.get(type="draft-iesg", slug="writeupw"),
    'Waiting for AD Go-Ahead': State.objects.get(type="draft-iesg", slug="goaheadw"),
    'Expert Review': State.objects.get(type="draft-iesg", slug="review-e"),
    'DNP-waiting for AD note': State.objects.get(type="draft-iesg", slug="nopubadw"),
    'DNP-announcement to be sent': State.objects.get(type="draft-iesg", slug="nopubanw"),
    None: None, # FIXME: consider introducing the ID-exists state
    }

ballot_position_mapping = {
    'Yes': name(BallotPositionName, 'yes', 'Yes', order=1),
    'No Objection': name(BallotPositionName, 'noobj', 'No Objection', order=2),
    'Discuss': name(BallotPositionName, 'discuss', 'Discuss', order=3),
    'Abstain': name(BallotPositionName, 'abstain', 'Abstain', order=4),
    'Recuse': name(BallotPositionName, 'recuse', 'Recuse', order=5),
    'No Record': name(BallotPositionName, 'norecord', 'No Record', order=6),
    }
ballot_position_mapping["no"] = ballot_position_mapping['No Objection']
ballot_position_mapping["yes"] = ballot_position_mapping['Yes']
ballot_position_mapping["discuss"] = ballot_position_mapping['Discuss']
ballot_position_mapping["abstain"] = ballot_position_mapping['Abstain']
ballot_position_mapping["recuse"] = ballot_position_mapping['Recuse']
ballot_position_mapping[None] = ballot_position_mapping["No Record"]
ballot_position_mapping["Undefined"] = ballot_position_mapping["No Record"]

# tags
substate_mapping = {
    "External Party": name(DocTagName, 'extpty', "External Party", 'The document is awaiting review or input from an external party (i.e, someone other than the shepherding AD, the authors, or the WG). See the "note" field for more details on who has the action.', 3),
    "Revised ID Needed": name(DocTagName, 'need-rev', "Revised ID Needed", 'An updated ID is needed to address the issues that have been raised.', 5),
    "AD Followup": name(DocTagName, 'ad-f-up', "AD Followup", """A generic substate indicating that the shepherding AD has the action item to determine appropriate next steps. In particular, the appropriate steps (and the corresponding next state or substate) depend entirely on the nature of the issues that were raised and can only be decided with active involvement of the shepherding AD. Examples include:

- if another AD raises an issue, the shepherding AD may first iterate with the other AD to get a better understanding of the exact issue. Or, the shepherding AD may attempt to argue that the issue is not serious enough to bring to the attention of the authors/WG.

- if a documented issue is forwarded to a WG, some further iteration may be needed before it can be determined whether a new revision is needed or whether the WG response to an issue clarifies the issue sufficiently.

- when a new revision appears, the shepherding AD will first look at the changes to determine whether they believe all outstanding issues have been raised satisfactorily, prior to asking the ADs who raised the original issues to verify the changes.""", 2),
    "Point Raised - writeup needed": name(DocTagName, 'point', "Point Raised - writeup needed", 'IESG discussions on the document have raised some issues that need to be brought to the attention of the authors/WG, but those issues have not been written down yet. (It is common for discussions during a telechat to result in such situations. An AD may raise a possible issue during a telechat and only decide as a result of that discussion whether the issue is worth formally writing up and bringing to the attention of the authors/WG). A document stays in the "Point Raised - Writeup Needed" state until *ALL* IESG comments that have been raised have been documented.', 1)
    }

tag_review_by_rfc_editor = name(DocTagName, 'rfc-rev', "Review by RFC Editor")
tag_via_rfc_editor = name(DocTagName, 'via-rfc', "Via RFC Editor")
tag_approved_in_minute = name(DocTagName, 'app-min', "Approved in minute")
tag_has_errata = name(DocTagName, 'errata', "Has errata")

name(DocTagName, "w-expert", "Awaiting Expert Review/Resolution of Issues Raised", order=1)
name(DocTagName, "w-extern", "Awaiting External Review/Resolution of Issues Raised", order=2)
name(DocTagName, "w-merge", "Awaiting Merge with Other Document", order=3)
name(DocTagName, "need-aut", "Author or Editor Needed", order=4)
name(DocTagName, "w-refdoc", "Waiting for Referenced Document", order=5)
name(DocTagName, "w-refing", "Waiting for Referencing Document", order=6)
name(DocTagName, "rev-wglc", "Revised I-D Needed - Issue raised by WGLC", order=7)
name(DocTagName, "rev-ad", "Revised I-D Needed - Issue raised by AD", order=8)
name(DocTagName, "rev-iesg", "Revised I-D Needed - Issue raised by IESG", order=9)
name(DocTagName, "sheph-u", "Doc Shepherd Follow-up Underway", order=10)
name(DocTagName, "other", "Other - see Comment Log", order=11)
name(DocTagName, "need-ed", "Editor Needed", order=1)
name(DocTagName, "w-part", "Waiting for Partner Feedback", order=2)
name(DocTagName, "w-review", "Awaiting Reviews", order=3)
name(DocTagName, "sh-f-up", "Document Shepherd Followup", order=4)
name(DocTagName, "need-sh", "Shepherd Needed")
name(DocTagName, "w-dep", "Waiting for Dependency on Other Document")
name(DocTagName, "iesg-com", "IESG Review Completed")

stream_state_reminder_type = name(DocReminderTypeName, "stream-s", "Stream state should change")

#tag_mapping = dict((t.name, t) for t in DocTagName.objects.all())


# helpers
def extract_authors_from_dump():
    authors_re = re.compile(r"docauthors='([^']*);....-..-..'")
    name_email_re = re.compile(r"(.*) <([^>]+)>")
    email_brackets_re = re.compile(r" <[^>]*>")
    comma_re = re.compile(r".*,")
    colon_re = re.compile(r".*:")

    email_mapping = {
        "barryleiba@computer.org": "barryleiba@gmail.com",
        "greg.daley@eng.monash.edu.au": "gdaley@netstarnetworks.com",
        "radia.perlman@sun.com": "radia@alum.mit.edu",
        "lisa@osafoundation.org": "lisa.dusseault@gmail.com",
        "lisa.dusseault@messagingarchitects.com": "lisa.dusseault@gmail.com",
        "scott.lawrence@nortel.com": "scottlawrenc@avaya.com",
        "charliep@computer.org": "charliep@computer.org, charles.perkins@earthlink.net",
        "yaronf@checkpoint.com": "yaronf.ietf@gmail.com",
        "mary.barnes@nortel.com": "mary.ietf.barnes@gmail.com",
        "scottlawrenc@avaya.com": "xmlscott@gmail.com",
        "henk@ripe.net": "henk@uijterwaal.nl",
        "jonne.soininen@nsn.com": "jonne.soininen@renesasmobile.com",
        "tom.taylor@rogers.com": "tom.taylor.stds@gmail.com",
        "rahul@juniper.net": "raggarwa_1@yahoo.com",
        "dward@juniper.net": "dward@cisco.com",
        "alan.ford@roke.co.uk": "alanford@cisco.com",
        }

    res = {}

    if not os.path.exists(ALL_IDS_STATE):
        print "WARNING: proceeding without author information in all_ids.state"
        return res

    with open(ALL_IDS_STATE, "r") as author_source:
        for line in author_source:
            if line.startswith("#"):
                continue

            draft_name = line.split(" ")[1]

            m = authors_re.search(line)
            if not m:
                continue

            l = []
            reliable = True
            for a in m.group(1).replace("\\x27", "'").replace("\\'", "'").decode("latin-1").split(", "):
                n = name_email_re.match(a)
                if n:
                    name = n.group(1)
                    email = n.group(2)
                else:
                    name = a
                    email = ""

                if "@" not in email or not email:
                    reliable = False

                name = email_brackets_re.sub("", name)
                name = comma_re.sub("", name)
                name = colon_re.sub("", name)
                name = name.strip()

                if "VCARD" in name or len(name.split()) > 5:
                    reliable = False

                if not reliable:
                    break

                email = email_mapping.get(email, email)

                l.append((name, email))

            if reliable:
                res[draft_name] = l

    return res

author_dump = extract_authors_from_dump()

def save_docevent(doc, event, comment):
    event.time = comment.datetime()
    event.by = iesg_login_to_person(comment.created_by)
    event.doc = doc
    if not event.desc:
        event.desc = comment.comment_text # FIXME: consider unquoting here
    event.save()

def sync_tag(d, include, tag):
    if include:
        d.tags.add(tag)
    else:
        d.tags.remove(tag)

buggy_iesg_logins_cache = {}

system = Person.objects.get(name="(System)")

def iesg_login_to_person(l):
    if not l:
        return system
    else:
         # there's a bunch of old weird comments made by "IESG
         # Member", transform these into "System" instead
        if l.id == 2:
            return system
        
        # fix logins without the right person
        if not l.person:
            if l.id not in buggy_iesg_logins_cache:
                logins = IESGLogin.objects.filter(first_name=l.first_name, last_name=l.last_name).exclude(id=l.id)
                if logins:
                    buggy_iesg_logins_cache[l.id] = logins[0]
                else:
                    persons = PersonOrOrgInfo.objects.filter(first_name=l.first_name, last_name=l.last_name)
                    if persons:
                        l.person = persons[0]
                        buggy_iesg_logins_cache[l.id] = l
                    else:
                        buggy_iesg_logins_cache[l.id] = None
            l = buggy_iesg_logins_cache[l.id]

        if not l:
            return system
            
        try:
            return old_person_to_person(l.person)
        except Person.DoesNotExist:
            print "MISSING IESG LOGIN", l.person, l.person.email()
            return None

def iesg_login_is_secretary(l):
    # Amy has two users, for some reason, we sometimes get the wrong one
    return l.user_level == IESGLogin.SECRETARIAT_LEVEL or (l.first_name == "Amy" and l.last_name == "Vezza")

old_internetdraft_content_type_id = ContentType.objects.using("legacy").get(app_label="idtracker", model="internetdraft").pk

# regexps for parsing document comments

date_re_str = "(?P<year>[0-9][0-9][0-9][0-9])-(?P<month>[0-9][0-9]?)-(?P<day>[0-9][0-9]?)"
def date_in_match(match):
    y = int(match.group('year'))
    m = int(match.group('month'))
    d = int(match.group('day'))
    if d == 35: # borked status date
        d = 25
    return datetime.date(y, m, d)

re_telechat_agenda = re.compile(r"(Placed on|Removed from) agenda for telechat( - %s|)" % date_re_str)
re_telechat_changed = re.compile(r"Telechat date (was|has been) changed to (<b>)?%s(</b>)? from" % date_re_str)
re_ballot_position = re.compile(r"\[Ballot Position Update\] (New position, (?P<position>.*), has been recorded( for (?P<for>\w+ \w+) |)|Position (|for (?P<for2>.*) )has been changed to (?P<position2>.*) from .*)(by (?P<by>.*)|)")
re_ballot_issued = re.compile(r"Ballot has been issued")
re_state_changed = re.compile(r"(State (has been changed|changed|Changes) to <b>(?P<to>.*)</b> from (<b>|)(?P<from>.*)(</b> by|)|Sub state has been changed to (?P<tosub>.*) from (?P<fromsub>.*))")
re_note_changed = re.compile(r"(\[Note\]: .*'.*'|Note field has been cleared)", re.DOTALL)
re_draft_added = re.compile(r"Draft [Aa]dded (by .*)?( in state (?P<state>.*))?")
re_last_call_requested = re.compile(r"Last Call was requested")
re_document_approved = re.compile(r"IESG has approved and state has been changed to")
re_document_disapproved = re.compile(r"(Do Not Publish|DNP) note has been sent to RFC Editor and state has been changed to")
re_resurrection_requested = re.compile(r"(I-D |)Resurrection was requested")
re_completed_resurrect = re.compile(r"(This document has been resurrected|This document has been resurrected per RFC Editor's request|Resurrection was completed)")

re_status_date_changed = re.compile(r"Status [dD]ate has been changed to (<b>)?" + date_re_str)
re_responsible_ad_changed = re.compile(r"(Responsible AD|Shepherding AD|responsible) has been changed to (<b>)?")
re_intended_status_changed = re.compile(r"Intended [sS]tatus has been changed to (<b>)?")
re_state_change_notice = re.compile(r"State Change Notice email list (have been change|has been changed) (<b>)?")
re_area_acronym_changed = re.compile(r"Area acronymn? has been changed to \w+ from \w+(<b>)?")

re_comment_discuss_by_tag = re.compile(r" by [\w-]+ [\w-]+$")

def import_from_idinternal(d, idinternal):
    d.time = idinternal.event_date
    d.ad = iesg_login_to_person(idinternal.job_owner)
    d.notify = idinternal.state_change_notice_to or ""
    d.note = (idinternal.note or "").replace('<br>', '\n').strip().replace('\n', '<br>')

    try:
        if idinternal.area_acronym and d.group.type_id == "individ":
            d.group = Group.objects.get(acronym=idinternal.area_acronym.area_acronym.acronym)
    except (Area.DoesNotExist, AttributeError):
        pass

    d.save()
    
    d.set_state(iesg_state_mapping[idinternal.cur_state.state])

    # extract events
    last_note_change_text = ""
    started_iesg_process = ""

    document_comments = DocumentComment.objects.filter(document=idinternal.draft_id).order_by('date', 'time', 'id')
    for c in document_comments:
        handled = False

        # telechat agenda schedulings
        match = re_telechat_agenda.search(c.comment_text) or re_telechat_changed.search(c.comment_text)
        if match:
            e = TelechatDocEvent()
            e.type = "scheduled_for_telechat"
            e.telechat_date = date_in_match(match) if "Placed on" in c.comment_text else None
            # can't extract this from history so we just take the latest value
            e.returning_item = bool(idinternal.returning_item)
            save_docevent(d, e, c)
            handled = True

        # ballot issued
        match = re_ballot_issued.search(c.comment_text)
        if match:
            e = DocEvent()
            e.type = "sent_ballot_announcement"
            save_docevent(d, e, c)
            handled = True

            ad = iesg_login_to_person(c.created_by)
            last_pos = d.latest_event(BallotPositionDocEvent, type="changed_ballot_position", ad=ad)
            if not last_pos and not iesg_login_is_secretary(c.created_by):
                # when you issue a ballot, you also vote yes; add that vote
                e = BallotPositionDocEvent()
                e.type = "changed_ballot_position"
                e.ad = ad
                e.desc = u"[Ballot Position Update] New position, Yes, has been recorded for %s" % e.ad.plain_name()
            
                e.pos = ballot_position_mapping["Yes"]
                e.discuss = last_pos.discuss if last_pos else ""
                e.discuss_time = last_pos.discuss_time if last_pos else None
                e.comment = last_pos.comment if last_pos else ""
                e.comment_time = last_pos.comment_time if last_pos else None
                save_docevent(d, e, c)

        # ballot positions
        match = re_ballot_position.search(c.comment_text)
        if match:
            position = ballot_position_mapping[match.group('position') or match.group('position2')]
            # some of the old positions don't specify who it's for, in
            # that case assume it's "by", the person who entered the
            # position
            ad_name = match.group('for') or match.group('for2') or match.group('by') or (u"%s %s" % (c.created_by.first_name, c.created_by.last_name) if c.created_by else "")
            ad_first, ad_last = ad_name.split(' ')
            login = IESGLogin.objects.filter(first_name=ad_first, last_name=ad_last).order_by('user_level')[0]
            if iesg_login_is_secretary(login):
                # now we're in trouble, a secretariat person isn't an
                # AD, instead try to find a position object that
                # matches and that we haven't taken yet
                positions = Position.objects.filter(ballot=idinternal.ballot)
                if position.slug == "noobj":
                    positions = positions.filter(noobj=1)
                elif position.slug == "yes":
                    positions = positions.filter(yes=1)
                elif position.slug == "abstain":
                    positions = positions.filter(models.Q(abstain=1)|models.Q(abstain=2))
                elif position.slug == "recuse":
                    positions = positions.filter(recuse=1)
                elif position.slug == "discuss":
                    positions = positions.filter(models.Q(discuss=1)|models.Q(discuss=2))
                assert position.slug != "norecord"

                found = False
                for p in positions:
                    if not BallotPositionDocEvent.objects.filter(doc=d, type="changed_ballot_position", pos=position, ad=iesg_login_to_person(p.ad)):
                        login = p.ad
                        found = True
                        break

                if not found:
                    # in even more trouble, we can try and see if it
                    # belongs to a nearby discuss
                    if position.slug == "discuss":
                        index_c = list(document_comments).index(c)
                        start = c.datetime()
                        end = c.datetime() + datetime.timedelta(seconds=30 * 60)
                        for i, x in enumerate(document_comments):
                            if (x.ballot == DocumentComment.BALLOT_DISCUSS
                                and (c.datetime() <= x.datetime() <= end
                                     or abs(index_c - i) <= 2)
                                and not iesg_login_is_secretary(x.created_by)):
                                login = x.created_by
                                found = True

                if not found:
                    print "BALLOT BY SECRETARIAT", login
                

            e = BallotPositionDocEvent()
            e.type = "changed_ballot_position"
            e.ad = iesg_login_to_person(login)
            last_pos = d.latest_event(BallotPositionDocEvent, type="changed_ballot_position", ad=e.ad)
            e.pos = position
            e.discuss = last_pos.discuss if last_pos else ""
            e.discuss_time = last_pos.discuss_time if last_pos else None
            if e.pos_id == "discuss" and not e.discuss_time:
                # in a few cases, we don't have the discuss
                # text/time, fudge the time so it's not null
                e.discuss_time = c.datetime()
            e.comment = last_pos.comment if last_pos else ""
            e.comment_time = last_pos.comment_time if last_pos else None
            save_docevent(d, e, c)
            handled = True

        # ballot discusses/comments
        if c.ballot in (DocumentComment.BALLOT_DISCUSS, DocumentComment.BALLOT_COMMENT):
            skip = False

            e = BallotPositionDocEvent()
            e.type = "changed_ballot_position"
            e.ad = iesg_login_to_person(c.created_by)
            last_pos = d.latest_event(BallotPositionDocEvent, type="changed_ballot_position", ad=e.ad)
            e.pos = last_pos.pos if last_pos else ballot_position_mapping[None]
            c.comment_text = re_comment_discuss_by_tag.sub("", c.comment_text).strip()
            if c.ballot == DocumentComment.BALLOT_DISCUSS:
                e.discuss = c.comment_text

                if not e.discuss and (not last_pos or not last_pos.discuss):
                    skip = True # skip some bogus empty entries

                e.discuss_time = c.datetime()
                e.comment = last_pos.comment if last_pos else ""
                e.comment_time = last_pos.comment_time if last_pos else None
                # put header into description
                c.comment_text = "[Ballot discuss]\n" + c.comment_text
            else:
                e.discuss = last_pos.discuss if last_pos else ""
                e.discuss_time = last_pos.discuss_time if last_pos else None
                if e.pos_id == "discuss" and not e.discuss_time:
                    # in a few cases, we don't have the discuss
                    # text/time, fudge the time so it's not null
                    e.discuss_time = c.datetime()
                e.comment = c.comment_text
                if not e.comment and (not last_pos or not last_pos.comment):
                    skip = True # skip some bogus empty entries

                e.comment_time = c.datetime()
                # put header into description
                c.comment_text = "[Ballot comment]\n" + c.comment_text

            # there are some bogus copies where a secretary has the
            # same discuss comment as an AD
            if iesg_login_is_secretary(c.created_by) and DocumentComment.objects.filter(ballot=c.ballot, document=c.document).exclude(created_by=c.created_by):
                skip = True

            if not skip:
                save_docevent(d, e, c)
                
            handled = True

        # last call requested
        match = re_last_call_requested.search(c.comment_text)
        if match:
            e = DocEvent(type="requested_last_call")
            save_docevent(d, e, c)
            handled = True

        # state changes
        match = re_state_changed.search(c.comment_text)
        if match:
            e = DocEvent(type="changed_document")
            save_docevent(d, e, c)
            handled = True

        # note changed
        match = re_note_changed.search(c.comment_text)
        if match:
            # watch out for duplicates of which the old data's got many
            if c.comment_text != last_note_change_text:
                last_note_change_text = c.comment_text
                e = DocEvent(type="changed_document")
                save_docevent(d, e, c)
            handled = True

        # draft added 
        match = re_draft_added.search(c.comment_text)
        if match:
            # watch out for extraneous starts, the old data contains
            # some phony ones
            if not started_iesg_process:
                started_iesg_process = c.comment_text
                e = DocEvent(type="started_iesg_process")
                save_docevent(d, e, c)
            handled = True

        # new version
        if c.comment_text == "New version available":
            e = NewRevisionDocEvent(type="new_revision", rev=c.version)
            c.comment_text = "Added new revision"
            save_docevent(d, e, c)
            handled = True

        # resurrect requested
        match = re_resurrection_requested.search(c.comment_text)
        if match:
            e = DocEvent(type="requested_resurrect")
            save_docevent(d, e, c)
            handled = True

        # completed resurrect
        match = re_completed_resurrect.search(c.comment_text)
        if match:
            e = DocEvent(type="completed_resurrect")
            save_docevent(d, e, c)
            handled = True

        # document expiration
        if c.comment_text == "Document is expired by system":
            e = DocEvent(type="expired_document")
            c.comment_text = "Document has expired"
            save_docevent(d, e, c)
            handled = True

        # approved document 
        match = re_document_approved.search(c.comment_text)
        if match:
            e = DocEvent(type="iesg_approved")
            save_docevent(d, e, c)
            handled = True

        # disapproved document
        match = re_document_disapproved.search(c.comment_text)
        if match:
            e = DocEvent(type="iesg_disapproved")
            save_docevent(d, e, c)
            handled = True


        # some changes can be bundled - this is not entirely
        # convenient, especially since it makes it hard to give
        # each a type, so unbundle them
        if not handled:
            unhandled_lines = []
            for line in c.comment_text.split("<br>"):
                line = line.replace("&nbsp;", " ")
                # status date changed
                match = re_status_date_changed.search(line)
                if match:
                    e = DocEvent(type="added_comment")
                    e.desc = line
                    save_docevent(d, e, c)
                    handled = True

                # AD/job owner changed
                match = re_responsible_ad_changed.search(line)
                if match:
                    e = DocEvent(type="changed_document")
                    e.desc = line
                    save_docevent(d, e, c)
                    handled = True

                # intended standard level changed
                match = re_intended_status_changed.search(line)
                if match:
                    e = DocEvent(type="changed_document")
                    e.desc = line
                    save_docevent(d, e, c)
                    handled = True

                # state change notice
                match = re_state_change_notice.search(line)
                if match:
                    e = DocEvent(type="changed_document")
                    e.desc = line
                    save_docevent(d, e, c)
                    handled = True

                # area acronym
                match = re_area_acronym_changed.search(line)
                if match:
                    e = DocEvent(type="changed_document")
                    e.desc = line
                    save_docevent(d, e, c)
                    handled = True

                # multiline change bundles end with a single "by xyz" that we skip
                if not handled and not line.startswith("by <b>"):
                    unhandled_lines.append(line)

            if handled:
                c.comment_text = "<br>".join(unhandled_lines)

                if c.comment_text:
                    if "Due date has been changed" not in c.comment_text:
                        print "DID NOT HANDLE multi-line comment %s '%s'" % (c.id, c.comment_text.replace("\n", " ").replace("\r", "")[0:80])

        # all others are added as comments
        if not handled:
            e = DocEvent(type="added_comment")
            save_docevent(d, e, c)

            # stop typical comments from being output
            typical_comments = [
                "Document Shepherd Write-up for %s" % d.name,
                "Who is the Document Shepherd for this document",
                "We understand that this document doesn't require any IANA actions",
                "IANA questions",
                "IANA has questions",
                "IANA comments",
                "IANA Comments",
                "IANA Evaluation Comment",
                "IANA Last Call Comments",
                "ublished as RFC",
                "A new comment added",
                "Due date has been changed",
                "Due&nbsp;date&nbsp;has&nbsp;been&nbsp;changed",
                "by&nbsp;<b>",
                "AD-review comments",
                "IANA Last Call",
                "Subject:",
                "Merged with",
                                ]
            for t in typical_comments:
                if t in c.comment_text:
                    handled = True
                    break

        if not handled:
            print (u"DID NOT HANDLE comment %s '%s' by %s" % (c.id, c.comment_text.replace("\n", " ").replace("\r", "")[0:80], c.created_by)).encode("utf-8")

    e = d.latest_event()
    if e:
        made_up_date = e.time
    else:
        made_up_date = d.time
    made_up_date += datetime.timedelta(seconds=1)

    e = d.latest_event(TelechatDocEvent, type="scheduled_for_telechat")
    telechat_date = e.telechat_date if e else None
    if not idinternal.agenda:
        idinternal.telechat_date = None # normalize

    if idinternal.telechat_date != telechat_date:
        e = TelechatDocEvent(type="scheduled_for_telechat",
                          telechat_date=idinternal.telechat_date,
                          returning_item=bool(idinternal.returning_item))
        # a common case is that it has been removed from the
        # agenda automatically by a script without a notice in the
        # comments, in that case the time is simply the day after
        # the telechat
        e.time = telechat_date + datetime.timedelta(days=1) if telechat_date and not idinternal.telechat_date else made_up_date
        e.by = system
        args = ("Placed on", idinternal.telechat_date) if idinternal.telechat_date else ("Removed from", telechat_date)
        e.doc = d
        e.desc = "%s agenda for telechat - %s" % args
        e.save()

    try:
        # sad fact: some ballots haven't been generated yet
        ballot = idinternal.ballot
    except BallotInfo.DoesNotExist:
        ballot = None
        
    if ballot:
        e = d.docevent_set.filter(type__in=("changed_ballot_position", "sent_ballot_announcement", "requested_last_call")).order_by('-time')[:1]
        if e:
            position_date = e[0].time + datetime.timedelta(seconds=1)
        else:
            position_date = made_up_date

        # make sure we got all the positions
        existing = BallotPositionDocEvent.objects.filter(doc=d, type="changed_ballot_position").order_by("-time", '-id')
        
        for p in Position.objects.filter(ballot=ballot):
            # there are some bogus ones
            if iesg_login_is_secretary(p.ad):
                continue
            
            ad = iesg_login_to_person(p.ad)
            if p.noobj > 0:
                pos = ballot_position_mapping["No Objection"]
            elif p.yes > 0:
                pos = ballot_position_mapping["Yes"]
            elif p.abstain > 0:
                pos = ballot_position_mapping["Abstain"]
            elif p.recuse > 0:
                pos = ballot_position_mapping["Recuse"]
            elif p.discuss > 0:
                pos = ballot_position_mapping["Discuss"]
            else:
                pos = ballot_position_mapping[None]

            found = False
            for x in existing:
                if x.ad == ad and x.pos == pos:
                    found = True
                    break

            if not found:
                e = BallotPositionDocEvent()
                e.type = "changed_ballot_position"
                e.doc = d
                e.time = position_date
                e.by = system
                e.ad = ad
                last_pos = d.latest_event(BallotPositionDocEvent, type="changed_ballot_position", ad=e.ad)
                e.pos = pos
                e.discuss = last_pos.discuss if last_pos else ""
                e.discuss_time = last_pos.discuss_time if last_pos else None
                if e.pos_id == "discuss" and not e.discuss_time:
                    # in a few cases, we don't have the discuss
                    # text/time, fudge the time so it's not null
                    e.discuss_time = e.time
                e.comment = last_pos.comment if last_pos else ""
                e.comment_time = last_pos.comment_time if last_pos else None
                if last_pos:
                    e.desc = u"[Ballot Position Update] Position for %s has been changed to %s from %s" % (ad.plain_name(), pos.name, last_pos.pos.name)
                else:
                    e.desc = u"[Ballot Position Update] New position, %s, has been recorded for %s" % (pos.name, ad.plain_name())
                e.save()

        # make sure we got the ballot issued event
        if ballot.ballot_issued and not d.docevent_set.filter(type="sent_ballot_announcement"):
            position = d.docevent_set.filter(type=("changed_ballot_position")).order_by('time', 'id')[:1]
            if position:
                sent_date = position[0].time
            else:
                sent_date = made_up_date
            
            e = DocEvent()
            e.type = "sent_ballot_announcement"
            e.doc = d
            e.time = sent_date
            e.by = system
            e.desc = "Ballot has been issued"
            e.save()
            
        # make sure the comments and discusses are updated
        positions = list(BallotPositionDocEvent.objects.filter(doc=d).order_by("-time", '-id'))
        for c in IESGComment.objects.filter(ballot=ballot):
            ad = iesg_login_to_person(c.ad)
            for p in positions:
                if p.ad == ad:
                    if p.comment != c.text:
                        p.comment = c.text
                        p.comment_time = c.date if p.time.date() != c.date else p.time
                        p.save()
                    break
                
        for c in IESGDiscuss.objects.filter(ballot=ballot):
            ad = iesg_login_to_person(c.ad)
            for p in positions:
                if p.ad == ad:
                    if p.discuss != c.text:
                        p.discuss = c.text
                        p.discuss_time = c.date if p.time.date() != c.date else p.time
                        p.save()
                    break
                        
        # if any of these events have happened, they're closer to
        # the real time
        e = d.docevent_set.filter(type__in=("requested_last_call", "sent_last_call", "sent_ballot_announcement", "iesg_approved", "iesg_disapproved")).order_by('time')[:1]
        if e:
            text_date = e[0].time - datetime.timedelta(seconds=1)
        else:
            text_date = made_up_date

        if idinternal.ballot.approval_text:
            e, _ = WriteupDocEvent.objects.get_or_create(type="changed_ballot_approval_text", doc=d,
                                                      defaults=dict(by=system))
            e.text = idinternal.ballot.approval_text
            e.time = text_date
            e.desc = "Ballot approval text was added"
            e.save()

        if idinternal.ballot.last_call_text:
            e, _ = WriteupDocEvent.objects.get_or_create(type="changed_last_call_text", doc=d,
                                                      defaults=dict(by=system))
            e.text = idinternal.ballot.last_call_text
            e.time = text_date
            e.desc = "Last call text was added"
            e.save()

        if idinternal.ballot.ballot_writeup:
            e, _ = WriteupDocEvent.objects.get_or_create(type="changed_ballot_writeup_text", doc=d,
                                                      defaults=dict(by=system))
            e.text = idinternal.ballot.ballot_writeup
            e.time = text_date
            e.desc = "Ballot writeup text was added"
            e.save()

    ballot_set = idinternal.ballot_set()
    if len(ballot_set) > 1:
        others = sorted(b.draft.filename for b in ballot_set if b != idinternal)
        desc = u"This was part of a ballot set with: %s" % ",".join(others)
        DocEvent.objects.get_or_create(type="added_comment", doc=d, desc=desc,
                                    defaults=dict(time=made_up_date,
                                                  by=system))

    # fix tags
    sync_tag(d, idinternal.via_rfc_editor, tag_via_rfc_editor)

    n = idinternal.cur_sub_state and idinternal.cur_sub_state.sub_state
    for k, v in substate_mapping.iteritems():
        sync_tag(d, k == n, v)
        # currently we ignore prev_sub_state

    sync_tag(d, idinternal.approved_in_minute, tag_approved_in_minute)



all_drafts = InternetDraft.objects.all().order_by('pk').select_related()
if import_docs_from:
    all_drafts = all_drafts.filter(last_modified_date__gte=import_docs_from) | all_drafts.filter(idinternal__event_date__gte=import_docs_from)

if document_name_to_import:
    if document_name_to_import.startswith("rfc"):
        all_drafts = all_drafts.filter(rfc_number=document_name_to_import[3:])
    else:
        all_drafts = all_drafts.filter(filename=document_name_to_import)


for index, o in enumerate(all_drafts.iterator()):
    print "importing", o.id_document_tag, o.filename, index, "ballot %s" % o.idinternal.ballot_id if o.idinternal and o.idinternal.ballot_id else ""
    
    try:
        d = Document.objects.get(name=o.filename)
    except Document.DoesNotExist:
        d = Document(name=o.filename)

    d.time = o.revision_date
    d.type = type_draft
    d.title = o.title
    d.group = Group.objects.get(acronym=o.group.acronym)

    d.states = []

    d.set_state(state_mapping[o.status.status])

    # try guess stream to have a default for old submissions
    d.stream = None
    if o.filename.startswith("draft-iab-"):
        d.stream = stream_mapping["IAB"]
    elif o.filename.startswith("draft-irtf-"):
        d.stream = stream_mapping["IRTF"]
    elif o.idinternal and o.idinternal.via_rfc_editor:
        d.stream = stream_mapping["INDEPENDENT"]
    elif d.name.startswith("draft-ietf-") and (d.group.type_id != "individ" or state_mapping[o.status.status].slug == "rfc" or o.idinternal):
        d.stream = stream_mapping["IETF"]

    sid = StreamedID.objects.filter(draft=o)
    if sid and sid[0].stream:
        d.stream = stream_mapping[sid[0].stream.name]

    try:
        s = StateOld.objects.get(stateobjectrelation__content_type=old_internetdraft_content_type_id,
                                 stateobjectrelation__content_id=o.pk)
    except StateOld.DoesNotExist:
        s = None

    if s:
        try:
            # there may be a mismatch between the stream type and the
            # state because of a bug in the ietfworkflows code so try
            # first without type constraint
            new_s = State.objects.get(name=s.name)
        except State.MultipleObjectsReturned:
            new_s = State.objects.get(type="draft-stream-%s" % d.stream_id, name=s.name)

        # fix some bugs in the old data
        skip = False
        if s.name == "WG Document" and d.group.type_id == "individ":
            skip = True

            if d.name.startswith("draft-ietf"):
                if d.name not in ("draft-ietf-proto-wgchair-tracker-ext", "draft-ietf-proto-iab-irtf-tracker-ext", "draft-ietf-sipping-nat-scenarios", "draft-ietf-sipping-sip-offeranswer"):
                    skip = False

                    group_acronym = d.name.split("-")[2]
                    if group_acronym == "pppext":
                        group_acronym = "trill"

                    d.group = Group.objects.get(acronym=group_acronym)

        if not skip:
            d.set_state(new_s)


        # there was a bug in ietfworkflows so the group wasn't set on adopted documents
        if s.name in ("Call for Adoption by WG Issued", "Adopted by a WG") and d.group.type_id == "individ" and o.replaced_by and o.replaced_by.group:
            d.group = Group.objects.get(acronym=o.replaced_by.group.acronym)

    d.rev = o.revision_display()
    d.abstract = o.abstract
    d.pages = o.txt_page_count
    d.intended_std_level = intended_std_level_mapping[o.intended_status.intended_status]
    d.ad = None
    d.shepherd = old_person_to_person(o.shepherd) if o.shepherd else None
    d.notify = ""
    d.external_url = ""
    d.note = ""
    d.internal_comments = o.comments or ""
    d.save()

    # make sure our alias is updated
    d_alias = alias_doc(d.name, d)

    # RFC alias
    if o.rfc_number:
        alias_doc("rfc%s" % o.rfc_number, d)

    # authors
    d.authors.clear()

    authors_from_dump = author_dump.get(d.name)
    if authors_from_dump:
        for i, a in enumerate(authors_from_dump):
            name, email = a
            try:
                e = Email.objects.get(address__iexact=email)
            except Email.DoesNotExist:
                e = Email(address=email)

                ps = Person.objects.filter(alias__name=name)
                if ps:
                    p = ps[0]
                else:
                    _, first, _, last, _ = name_parts(name)
                    first = first.replace(".", "")

                    ps = Person.objects.filter(name__regex=u".*%s.*%s.*" % (first, last))
                    if len(ps) == 1:
                        p = ps[0]
                    else:
                        from ietf.utils import unaccent
                        p = Person.objects.create(name=name, ascii=unaccent.asciify(name))
                        Alias.objects.create(name=p.name, person=p)
                        if p.ascii != p.name:
                            Alias.objects.create(name=p.ascii, person=p)

                e.person = p
                e.save()

            DocumentAuthor.objects.create(document=d, author=e, order=i)
    else:
        for i, a in enumerate(o.authors.all().select_related("person").order_by('author_order', 'person')):
            try:
                e = Email.objects.get(address__iexact=a.email() or a.person.email()[1] or u"unknown-email-%s" % person_name(a.person).replace(" ", "-"))
                # renumber since old numbers may be a bit borked
                DocumentAuthor.objects.create(document=d, author=e, order=i)
            except Email.DoesNotExist:
                print "SKIPPED author", unicode(a.person).encode('utf-8')

    # clear any already imported events
    d.docevent_set.all().delete()
    
    if o.idinternal:
        # import attributes and events
        import_from_idinternal(d, o.idinternal)

    # import missing revision changes from DraftVersions
    known_revisions = set(e.rev for e in NewRevisionDocEvent.objects.filter(doc=d, type="new_revision"))
    draft_versions = list(DraftVersions.objects.filter(filename=d.name))
    # DraftVersions is not entirely accurate, make sure we got the current one
    draft_versions.append(DraftVersions(filename=d.name, revision=o.revision_display(), revision_date=o.revision_date))
    draft_versions.sort(key=lambda v: (v.revision, v.revision_date))
    for v in draft_versions:
        if v.revision not in known_revisions:
            e = NewRevisionDocEvent(type="new_revision")
            e.rev = v.revision
            # we don't have time information in this source, so
            # hack the seconds to include the revision to ensure
            # they're ordered correctly
            e.time = datetime.datetime.combine(v.revision_date, datetime.time(0, 0, 0)) + datetime.timedelta(seconds=int(v.revision))
            e.by = system
            e.doc = d
            e.desc = "Added new revision"
            e.save()
            known_revisions.add(v.revision)

    # check that the revision number is accurate, there are some bugs
    # in the old system, presumably because of the tombstone revision
    # hack
    revs = list(sorted(known_revisions, reverse=True))
    if revs and revs[0] > d.rev:
        d.rev = revs[0]

    # ietfworkflows history entries
    for h in ObjectHistoryEntry.objects.filter(content_type=old_internetdraft_content_type_id, content_id=o.pk).order_by('date', 'id'):
        e = DocEvent(type="changed_document")
        e.time = h.date
        e.by = old_person_to_person(h.person)
        e.doc = d
        r = h.get_real_instance()
        if r:
            if isinstance(r, ObjectWorkflowHistoryEntry):
                s = State.objects.filter(type="draft-stream-%s" % d.stream_id, name=r.to_state)
                if not s:
                    s = State.objects.filter(name=r.to_state)
                start = "State changed"
                if s:
                    start = "%s changed" % s[0].type.label

                e.desc = u"%s to <b>%s</b> from %s" % (start, r.to_state, r.from_state)
            elif isinstance(r, ObjectAnnotationTagHistoryEntry):
                l = []
                if r.setted:
                    s = r.setted.split(",")
                    l.append(u"Annotation tag%s %s set." % (pluralize(s), ", ".join(s)))
                if r.unsetted:
                    s = r.unsetted.split(",")
                    l.append(u"Annotation tag%s %s cleared." % (pluralize(s), ", ".join(s)))
                e.desc = " ".join(l)
            elif isinstance(r, ObjectStreamHistoryEntry):
                e.type = "changed_stream"
                e.desc = u"Stream changed to <b>%s</b> from %s" % (r.to_stream, r.from_stream)
            else:
                raise Exception("Unknown ObjectHistoryEntry type: %s" % type(r))
        e.save()

        if r and isinstance(r, ObjectWorkflowHistoryEntry):
            # may need to add reminder
            try:
                metadata = StateObjectRelationMetadata.objects.get(relation__state__name=r.to_state,
                                                                   relation__content_id=o.pk,
                                                                   relation__content_type=ContentType.objects.get_for_model(o))
                if metadata.estimated_date:
                    try:
                        reminder = DocReminder.objects.get(event__doc=d, type=stream_state_reminder_type)
                    except DocReminder.DoesNotExist:
                        reminder = DocReminder(type=stream_state_reminder_type)

                    reminder.event = e
                    reminder.due = metadata.estimated_date
                    reminder.active = metadata.estimated_date > datetime.datetime.now()
                    reminder.save()
            except StateObjectRelationMetadata.DoesNotExist:
                pass

        if h.comment and h.comment.strip() and not d.docevent_set.filter(type="added_comment", desc=h.comment.strip(), time=h.date):
            e = DocEvent(type="added_comment")
            e.time = h.date
            e.by = old_person_to_person(h.person)
            e.doc = d
            e.desc = h.comment.strip()
            e.save()


    # wgchairs protocol writeups
    for w in ProtoWriteUp.objects.filter(draft=o).order_by('date'):
        e = WriteupDocEvent(type="changed_protocol_writeup")
        e.time = w.date
        e.by = old_person_to_person(w.person)
        e.doc = d
        e.desc = e.get_type_display()
        e.text = w.writeup
        e.save()

    # import events that might be missing, we can't be sure who did
    # them or when but if we don't generate them, we'll be missing the
    # information completely

    # make sure last decision is recorded
    e = d.latest_event(type__in=("iesg_approved", "iesg_disapproved"))
    decision_date = e.time.date() if e else None
    if o.b_approve_date != decision_date:
        disapproved = o.idinternal and o.idinternal.dnp
        e = DocEvent(type="iesg_disapproved" if disapproved else "iesg_approved")
        e.time = o.b_approve_date
        e.by = system
        e.doc = d
        e.desc = "Do Not Publish note has been sent to RFC Editor" if disapproved else "IESG has approved"
        e.save()

    if o.lc_expiration_date:
        e = LastCallDocEvent(type="sent_last_call", expires=o.lc_expiration_date)
        # let's try to find the actual change
        events = d.docevent_set.filter(type="changed_document", desc__contains=" to <b>In Last Call</b>").order_by('-time')[:1]
        # event time is more accurate with actual time instead of just
        # date, gives better sorting
        e.time = events[0].time if events else o.lc_sent_date
        e.by = events[0].by if events else system
        e.doc = d
        e.desc = "Last call sent"
        e.save()

    e = d.latest_event(type="expired_document")
    if o.expiration_date and not e:
        e = DocEvent(type="expired_document")
        e.time = o.expiration_date
        e.by = system
        e.doc = d
        e.desc = "Document has expired"
        e.save()


    # import other attributes

    # when to expire
    e = d.latest_event(type__in=("completed_resurrect", "new_revision"))
    if e:
        d.expires = e.time + datetime.timedelta(days=InternetDraft.DAYS_TO_EXPIRE)
    else:
        d.expires = None

    # tags
    sync_tag(d, o.review_by_rfc_editor, tag_review_by_rfc_editor)

    used_tags = DocTagName.objects.filter(name__in=list(AnnotationTag.objects.filter(annotationtagobjectrelation__content_type=old_internetdraft_content_type_id, annotationtagobjectrelation__content_id=o.pk).values_list('name', flat=True))).values_list('slug', flat=True)
    possible_tags = get_tags_for_stream_id(d.stream_id)
    for name in possible_tags:
        if name == "need-rev" and o.idinternal and o.idinternal.cur_sub_state and o.idinternal.cur_sub_state.sub_state == "Revised ID Needed":
            continue # don't overwrite tag from IESG substate

        sync_tag(d, name in used_tags, name)

    # replacements
    if o.replaced_by:
        replacement, _ = Document.objects.get_or_create(name=o.replaced_by.filename, defaults=dict(time=datetime.datetime(1970, 1, 1, 0, 0, 0)))
        RelatedDocument.objects.get_or_create(source=replacement, target=d_alias, relationship=relationship_replaces)
    
    # the RFC-related attributes are imported when we handle the RFCs below

    d.save()

# now process RFCs

def get_or_create_rfc_document(rfc_number):
    name = "rfc%s" % rfc_number

    # try to find a draft that can form the base of the document
    draft = None

    ids = InternetDraft.objects.filter(rfc_number=rfc_number)[:1]
    if ids:
        draft = ids[0]
    else:
        r = RfcIndex.objects.get(rfc_number=rfc_number)
        # rfcindex occasionally includes drafts that were not
        # really submitted to IETF (e.g. April 1st)
        if r.draft:
            ids = InternetDraft.objects.filter(filename=r.draft)[:1]
            if ids:
                draft = ids[0]

    if rfc_number in (2604, 3025):
        # prevent merge for some botched RFCs that are obsoleted by
        # another RFC coming from the same draft, in practice this is
        # just these two, so we hardcode rather than querying for it
        draft = None
                
    if draft:
        name = draft.filename

    d, _ = Document.objects.get_or_create(name=name, type=type_draft)
    if not name.startswith('rfc'):
        # make sure draft also got an alias
        alias_doc(name, d)
        
    alias = alias_doc("rfc%s" % rfc_number, d)
    
    return (d, alias)

    
all_rfcs = RfcIndex.objects.all().order_by("rfc_number")

if all_drafts.count() != InternetDraft.objects.count():
    if document_name_to_import and document_name_to_import.startswith("rfc"):
        # we wanted to import an RFC
        all_rfcs = all_rfcs.filter(rfc_number=document_name_to_import[3:])
    else:
        # if we didn't process all drafts, limit the RFCs to the ones we
        # did process
        rfc_numbers = set(d.rfc_number for d in all_drafts if d.rfc_number)
        if import_docs_from:
            all_rfcs = all_rfcs.filter(rfc_number__in=rfc_numbers) | all_rfcs.filter(rfc_published_date__gte=import_docs_from)
        else:
            all_rfcs = all_rfcs.filter(rfc_number__in=rfc_numbers)

for index, o in enumerate(all_rfcs.iterator()):
    print "importing rfc%s" % o.rfc_number, index
    
    d, d_alias = get_or_create_rfc_document(o.rfc_number)
    d.time = datetime.datetime.now()
    d.title = o.title
    d.std_level = std_level_mapping[o.current_status]
    d.set_state(state_mapping["RFC"])

    d.stream = stream_mapping[o.stream]
    if not d.group and o.wg:
        d.group = Group.objects.get(acronym=o.wg)

    # get some values from the rfc table
    rfcs = Rfc.objects.filter(rfc_number=o.rfc_number).select_related()
    if rfcs:
        r = rfcs[0]
        l = intended_std_level_mapping[r.intended_status.status]
        if l: # skip some bogus None values
            d.intended_std_level = l
    d.save()

    # a few RFCs have an IDInternal so we may have to import the
    # events and attributes
    internals = IDInternal.objects.filter(rfc_flag=1, draft=o.rfc_number)
    if internals:
        if d.name.startswith("rfc"):
            # clear any already imported events, we don't do it for
            # drafts as they've already been cleared above
            d.docevent_set.all().delete()
        import_from_idinternal(d, internals[0])
    
    # publication date
    e, _ = DocEvent.objects.get_or_create(doc=d, type="published_rfc",
                                       defaults=dict(by=system))
    e.time = o.rfc_published_date
    e.desc = "RFC published"
    e.save()

    # import obsoletes/updates
    def make_relation(other_rfc, rel_type, reverse):
        other_number = int(other_rfc.replace("RFC", ""))
        other, other_alias = get_or_create_rfc_document(other_number)
        if reverse:
            RelatedDocument.objects.get_or_create(source=other, target=d_alias, relationship=rel_type)
        else:
            RelatedDocument.objects.get_or_create(source=d, target=other_alias, relationship=rel_type)

    def parse_relation_list(s):
        if not s:
            return []
        res = []
        for x in s.split(","):
            if x[:3] in ("NIC", "IEN", "STD", "RTR"):
                # try translating this to RFC numbers that we can
                # handle sensibly; otherwise we'll have to ignore them
                l = ["RFC%s" % y.rfc_number for y in RfcIndex.objects.filter(also=x).order_by('rfc_number')]
                if l:
                    print "translated", x, "to", ", ".join(l)
                    for y in l:
                        if y not in res:
                            res.append(y)
                else:
                    print "SKIPPED relation to", x
            else:
                res.append(x)
        return res

    for x in parse_relation_list(o.obsoletes):
        make_relation(x, relationship_obsoletes, False)
    for x in parse_relation_list(o.obsoleted_by):
        make_relation(x, relationship_obsoletes, True)
    for x in parse_relation_list(o.updates):
        make_relation(x, relationship_updates, False)
    for x in parse_relation_list(o.updated_by):
        make_relation(x, relationship_updates, True)

    if o.also:
        for a in o.also.lower().split(","):
            alias_doc(a, d)

    sync_tag(d, o.has_errata, tag_has_errata)

    # FIXME: import RFC authors?
