# Copyright The IETF Trust 2011-2024, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import io
import math
import os
import re
import textwrap

from collections import defaultdict, namedtuple, Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Union
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib import messages
from django.db.models import OuterRef
from django.forms import ValidationError
from django.http import Http404
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import escape
from django.urls import reverse as urlreverse

from django_stubs_ext import QuerySetAny

import debug                            # pyflakes:ignore
from ietf.community.models import CommunityList
from ietf.community.utils import docs_tracked_by_community_list

from ietf.doc.models import Document, DocHistory, State, DocumentAuthor, DocHistoryAuthor
from ietf.doc.models import RelatedDocument, RelatedDocHistory, BallotType, DocReminder
from ietf.doc.models import DocEvent, ConsensusDocEvent, BallotDocEvent, IRSGBallotDocEvent, NewRevisionDocEvent, StateDocEvent
from ietf.doc.models import TelechatDocEvent, DocumentActionHolder, EditedAuthorsDocEvent
from ietf.name.models import DocReminderTypeName, DocRelationshipName
from ietf.group.models import Role, Group, GroupFeatures
from ietf.ietfauth.utils import has_role, is_authorized_in_doc_stream, is_individual_draft_author, is_bofreq_editor
from ietf.person.models import Email, Person
from ietf.review.models import ReviewWish
from ietf.utils import draft, log
from ietf.utils.mail import parseaddr, send_mail
from ietf.mailtrigger.utils import gather_address_lists
from ietf.utils.timezone import date_today, datetime_from_date, datetime_today, DEADLINE_TZINFO
from ietf.utils.xmldraft import XMLDraft


def save_document_in_history(doc):
    """Save a snapshot of document and related objects in the database."""
    def get_model_fields_as_dict(obj):
        return dict((field.name, getattr(obj, field.name))
                    for field in obj._meta.fields
                    if field is not obj._meta.pk)

    # copy fields
    fields = get_model_fields_as_dict(doc)
    fields["doc"] = doc
    fields["name"] = doc.name

    dochist = DocHistory(**fields)
    dochist.save()

    # copy many to many
    for field in doc._meta.many_to_many:
        if field.remote_field.through and field.remote_field.through._meta.auto_created:
            hist_field = getattr(dochist, field.name)
            hist_field.clear()
            hist_field.set(getattr(doc, field.name).all())

    # copy remaining tricky many to many
    def transfer_fields(obj, HistModel):
        mfields = get_model_fields_as_dict(item)
        # map doc -> dochist
        for k, v in mfields.items():
            if v == doc:
                mfields[k] = dochist
        HistModel.objects.create(**mfields)

    for item in RelatedDocument.objects.filter(source=doc):
        transfer_fields(item, RelatedDocHistory)

    for item in DocumentAuthor.objects.filter(document=doc):
        transfer_fields(item, DocHistoryAuthor)
                
    return dochist


def get_state_types(doc):
    res = []

    if not doc:
        return res

    res.append(doc.type_id)

    if doc.type_id == "draft":
        if doc.stream_id and doc.stream_id != "legacy":
            res.append("draft-stream-%s" % doc.stream_id)

        res.append("draft-iesg")
        res.append("draft-iana-review")
        res.append("draft-iana-action")
        res.append("draft-rfceditor")

    return res

def get_tags_for_stream_id(stream_id):
    if stream_id == "ietf":
        return ["w-expert", "w-extern", "w-merge", "need-aut", "w-refdoc", "w-refing", "rev-wg", "rev-wglc", "rev-ad", "rev-iesg", "sheph-u", "no-adopt", "other"]
    elif stream_id == "iab":
        return ["need-ed", "w-part", "w-review", "need-rev", "sh-f-up"]
    elif stream_id == "irtf":
        return ["need-ed", "need-sh", "w-dep", "need-rev", "iesg-com"]
    elif stream_id == "ise":
        return ["w-dep", "w-review", "need-rev", "iesg-com"]
    else:
        return []

def can_adopt_draft(user, doc):
    """Answers whether a user can adopt a given draft into some stream/group.
    
    This does not answer, even by implicaiton, which streams/groups the user has authority to adopt into."""

    if not user.is_authenticated:
        return False

    if has_role(user, "Secretariat"):
        return True

    #The IRTF chair can adopt a draft into any RG
    if has_role(user, "IRTF Chair"):
        return (doc.stream_id in (None, "irtf")
                and doc.group.type_id == "individ")

    for type_id, allowed_stream in (
        ("wg", "ietf"),
        ("rg", "irtf"),
        ("ag", "ietf"),
        ("rag", "irtf"),
        ("edwg", "editorial"),
    ):
        if doc.stream_id in (None, allowed_stream):
            if doc.group.type_id in ("individ", type_id):
                if Role.objects.filter(
                    name__in=GroupFeatures.objects.get(type_id=type_id).docman_roles,
                    group__type_id = type_id,
                    group__state = "active",
                    person__user = user,
                ).exists():
                    return True
                        
    return False


def can_unadopt_draft(user, doc):
    # TODO: This should use docman_roles, and this implementation probably returns wrong answers
    # For instance, should any WG chair be able to unadopt a group from any other WG
    if not user.is_authenticated:
        return False
    if has_role(user, "Secretariat"):
        return True
    if doc.stream_id == 'irtf':
        if has_role(user, "IRTF Chair"):
            return True
        return user.person.role_set.filter(name__in=('chair','delegate','secr'),group=doc.group).exists()
    elif doc.stream_id == 'ietf':
        return user.person.role_set.filter(name__in=('chair','delegate','secr'),group=doc.group).exists()
    elif doc.stream_id == 'ise':
        return user.person.role_set.filter(name='chair',group__acronym='ise').exists()
    elif doc.stream_id == 'iab':
        return False    # Right now only the secretariat can add a document to the IAB stream, so we'll
                        # leave it where only the secretariat can take it out.
    elif doc.stream_id == 'editorial':
        return user.person.role_set.filter(name='chair', group__acronym='rswg').exists()
    else:
        return False

def can_edit_docextresources(user, doc):
    return (has_role(user, ("Secretariat", "Area Director"))
            or is_authorized_in_doc_stream(user, doc)
            or is_individual_draft_author(user, doc)
            or is_bofreq_editor(user, doc))

def two_thirds_rule( recused=0 ):
    # For standards-track, need positions from 2/3 of the non-recused current IESG.
    active = Role.objects.filter(name="ad",group__type="area",group__state="active").count()
    return int(math.ceil((active - recused) * 2.0/3.0))

def needed_ballot_positions(doc, active_positions):
    '''Returns text answering the question "what does this document
    need to pass?".  The return value is only useful if the document
    is currently in IESG evaluation.'''
    yes = [p for p in active_positions if p and p.pos_id == "yes"]
    noobj = [p for p in active_positions if p and p.pos_id == "noobj"]
    blocking = [p for p in active_positions if p and p.pos.blocking]
    recuse = [p for p in active_positions if p and p.pos_id == "recuse"]

    answer = []
    if len(yes) < 1:
        answer.append("Needs a YES.")
    if blocking:
        if len(blocking) == 1:
            answer.append("Has a %s." % blocking[0].pos.name.upper())
        else:
            if blocking[0].pos.name.upper().endswith('S'):
                answer.append("Has %d %ses." % (len(blocking), blocking[0].pos.name.upper()))
            else:
                answer.append("Has %d %ss." % (len(blocking), blocking[0].pos.name.upper()))
    needed = 1
    if doc.type_id == "draft" and doc.intended_std_level_id in ("bcp", "ps", "ds", "std"):
        needed = two_thirds_rule(recused=len(recuse))
    elif doc.type_id == "statchg":
        if isinstance(doc,Document):
            related_set = doc.relateddocument_set
        elif isinstance(doc,DocHistory):
            related_set = doc.relateddochistory_set
        else:
            related_set = RelatedDocHistory.objects.none()
        for rel in related_set.filter(relationship__slug__in=['tops', 'tois', 'tohist', 'toinf', 'tobcp', 'toexp']):
            if (rel.target.std_level_id in ['bcp','ps','ds','std']) or (rel.relationship_id in ['tops','tois','tobcp']):
                needed = two_thirds_rule(recused=len(recuse))
                break
    else:
        if len(yes) < 1:
            return " ".join(answer)

    have = len(yes) + len(noobj)
    if have < needed:
        more = needed - have
        if more == 1:
            answer.append("Needs one more YES or NO OBJECTION position to pass.")
        else:
            answer.append("Needs %d more YES or NO OBJECTION positions to pass." % more)
    else:
        if blocking:
            answer.append("Has enough positions to pass once %s positions are resolved." % blocking[0].pos.name.upper())
        else:
            answer.append("Has enough positions to pass.")

    return " ".join(answer)

def irsg_needed_ballot_positions(doc, active_positions):
    '''Returns text answering the question "what does this document
    need to pass?".  The return value is only useful if the document
    is currently in IRSG evaluation.'''
    yes = [p for p in active_positions if p and p.pos_id == "yes"]
    needmoretime = [p for p in active_positions if p and p.pos_id == "moretime"]
    notready = [p for p in active_positions if p and p.pos_id == "notready"]

    answer = []
    needed = 2

    have = len(yes)
    if len(notready) > 0:
        answer.append("Has a Not Ready position.")
    if have < needed:
        more = needed - have
        if more == 1:
            answer.append("Needs one more YES position to pass.")
        else:
            answer.append("Needs %d more YES positions to pass." % more)
    else:
        answer.append("Has enough positions to pass.")
    if len(needmoretime) > 0:
        answer.append("Has a Need More Time position.")

    return " ".join(answer)

def rsab_needed_ballot_positions(doc, active_positions):
    count = Counter([p.pos_id if p else 'none' for p in active_positions])
    answer = []
    if count["concern"] > 0:
        answer.append("Has a Concern position.")
        # note RFC9280 section 3.2.2 item 12
        # the "vote" mentioned there is a separate thing from ballot position.
    if count["yes"] == 0:
        # This is _implied_ by 9280 - a document shouldn't be
        # approved if all RSAB members recuse
        answer.append("Needs a YES position.")
    if count["none"] > 0:
        answer.append("Some members have have not taken a position.")
    return " ".join(answer)
        
def create_ballot(request, doc, by, ballot_slug, time=None):
    closed = close_open_ballots(doc, by)
    for e in closed:
        messages.warning(request, "Closed earlier open ballot created %s on '%s' for %s" % (e.time.strftime('%Y-%m-%d %H:%M'), e.ballot_type, e.doc.name, ))
    if time:
        e = BallotDocEvent(type="created_ballot", by=by, doc=doc, rev=doc.rev, time=time)
    else:
        e = BallotDocEvent(type="created_ballot", by=by, doc=doc, rev=doc.rev)
    e.ballot_type = BallotType.objects.get(doc_type=doc.type, slug=ballot_slug)
    e.desc = 'Created "%s" ballot' % e.ballot_type.name
    e.save()

def create_ballot_if_not_open(request, doc, by, ballot_slug, time=None, duedate=None):
    ballot_type = BallotType.objects.get(doc_type=doc.type, slug=ballot_slug)
    if not doc.ballot_open(ballot_slug):
        kwargs = dict(type="created_ballot", by=by, doc=doc, rev=doc.rev)
        if time:
            kwargs['time'] = time
        if doc.stream_id == 'irtf':
            kwargs['duedate'] = duedate
            e = IRSGBallotDocEvent(**kwargs)
        else:
            e = BallotDocEvent(**kwargs)
        e.ballot_type = ballot_type
        e.desc = 'Created "%s" ballot' % e.ballot_type.name
        e.save()
        return e
    else:
        if request:
            messages.warning(request, "There already exists an open '%s' ballot for %s.  No new ballot created." % (ballot_type, doc.name))
        return None

def close_ballot(doc, by, ballot_slug):
    b = doc.ballot_open(ballot_slug)
    if b:
        e = BallotDocEvent(type="closed_ballot", doc=doc, rev=doc.rev, by=by)
        e.ballot_type = BallotType.objects.get(doc_type=doc.type,slug=ballot_slug)
        e.desc = 'Closed "%s" ballot' % e.ballot_type.name
        e.save()
    return b

def close_open_ballots(doc, by):
    closed = []
    for t in BallotType.objects.filter(doc_type=doc.type_id):
        e = close_ballot(doc, by, t.slug )
        if e:
            closed.append(e)
    return closed

def get_chartering_type(doc):
    chartering = ""
    if doc.get_state_slug() not in ("notrev", "approved"):
        if doc.group.state_id in ("proposed", "bof"):
            chartering = "initial"
        elif doc.group.state_id == "active":
            chartering = "rechartering"

    return chartering

def augment_events_with_revision(doc, events):
    """Take a set of events for doc and add a .rev attribute with the
    revision they refer to by checking NewRevisionDocEvents."""

    # Need QuerySetAny instead of QuerySet until django-stubs 5.0.1
    if isinstance(events, QuerySetAny):
        qs = events.filter(newrevisiondocevent__isnull=False)
    else:
        qs = NewRevisionDocEvent.objects.filter(doc=doc)
    event_revisions = list(qs.order_by('time', 'id').values('id', 'rev', 'time'))

    for e in sorted(events, key=lambda e: (e.time, e.id), reverse=True):
        while event_revisions and (e.time, e.id) < (event_revisions[-1]["time"], event_revisions[-1]["id"]):
            event_revisions.pop()
            
        # Check for all subtypes which have 'rev' fields:
        for sub in ['newrevisiondocevent', 'submissiondocevent', ]:
            if hasattr(e, sub):
                e = getattr(e, sub)
                break
        if not hasattr(e, 'rev'):
            if event_revisions:
                cur_rev = event_revisions[-1]["rev"]
            else:
                cur_rev = "00"
            e.rev = cur_rev


def add_events_message_info(events):
    for e in events:
        if not e.type == "added_message":
            continue

        e.message = e.addedmessageevent.message
        e.msgtype = e.addedmessageevent.msgtype
        e.in_reply_to = e.addedmessageevent.in_reply_to


def get_unicode_document_content(key, filename, codec='utf-8', errors='ignore'):
    try:
        with io.open(filename, 'rb') as f:
            raw_content = f.read().decode(codec,errors)
    except IOError:
        if settings.DEBUG:
            error = "Error; cannot read ("+filename+")"
        else:
            error = "Error; cannot read ("+key+")"
        return error

    return raw_content


def tags_suffix(tags):
    return ("::" + "::".join(t.name for t in tags)) if tags else ""


def new_state_change_event(doc, by, prev_state, new_state, prev_tags=None, new_tags=None, timestamp=None):
    """Create unsaved doc event to explain that state change just happened
    
    Returns None if no state change occurred.
    """
    if prev_state and new_state:
        assert prev_state.type_id == new_state.type_id

    # convert default args to empty lists
    prev_tags = prev_tags or []
    new_tags = new_tags or []

    if prev_state == new_state and set(prev_tags) == set(new_tags):
        return None

    e = StateDocEvent(doc=doc, rev=doc.rev, by=by)
    e.type = "changed_state"
    e.state_type = (prev_state or new_state).type
    e.state = new_state
    e.desc = "%s changed to <b>%s</b>" % (e.state_type.label, new_state.name + tags_suffix(new_tags))
    if prev_state:
        e.desc += " from %s" % (prev_state.name + tags_suffix(prev_tags))
    if timestamp:
        e.time = timestamp
    return e  # not saved!


def add_state_change_event(doc, by, prev_state, new_state, prev_tags=None, new_tags=None, timestamp=None):
    """Add doc event to explain that state change just happened.
    
    Returns None if no state change occurred.
    
    Note: Creating a state change DocEvent will trigger notifications to be sent to people subscribed
    to the doc via a CommunityList on its first save(). If you need to adjust the event (say, changing
    its desc) before that notification is sent, use new_state_change_event() instead and save the
    event after making your changes. 
    """
    e = new_state_change_event(doc, by, prev_state, new_state, prev_tags, new_tags, timestamp)
    if e is not None:
        e.save()
    return e


def add_action_holder_change_event(doc, by, prev_set, reason=None):
    set_changed = False
    if doc.documentactionholder_set.exclude(person__in=prev_set).exists():
        set_changed = True  # doc has an action holder not in the old set
    # If set_changed is still False, then all of the current action holders were in
    # prev_set. Either the sets are the same or the prev_set contains at least one 
    # Person not in the current set, so just check length.
    if doc.documentactionholder_set.count() != len(prev_set):
        set_changed = True

    if not set_changed:
        return None
    
    if doc.action_holders.exists():
        ah_names = [person.plain_name() for person in doc.action_holders.all()]
        description = 'Changed action holders to %s' % ', '.join(ah_names)
    else:
        description = 'Removed all action holders'
    if reason:
        description += ' (%s)' % reason

    return DocEvent.objects.create(
        type='changed_action_holders',
        doc=doc,
        by=by,
        rev=doc.rev,
        desc=description,
    )


@dataclass
class TagSetComparer:
    before: set[str]
    after: set[str]

    def changed(self):
        return self.before != self.after

    def added(self, tag):
        return tag in self.after and tag not in self.before

    def removed(self, tag):
        return tag in self.before and tag not in self.after


def update_action_holders(doc, prev_state=None, new_state=None, prev_tags=None, new_tags=None):
    """Update the action holders for doc based on state transition
    
    Returns an event describing the change which should be passed to doc.save_with_history()
    
    Only cares about draft-iesg state changes and draft expiration. 
    Places where other state types are updated may not call this method. 
    If you add rules for updating action holders on other state
    types, be sure this is called in the places that change that state.
    """
    # Should not call this with different state types
    if prev_state and new_state:
        assert prev_state.type_id == new_state.type_id

    # Convert tags to sets of slugs
    tags = TagSetComparer(
        before={t.slug for t in (prev_tags or [])},
        after={t.slug for t in (new_tags or [])},
    )

    # Do nothing if state / tag have not changed
    if (prev_state == new_state) and not tags.changed():
        return None
    
    # Remember original list of action holders to later check if it changed
    prev_set = list(doc.action_holders.all())

    if new_state and new_state.type_id=="draft" and new_state.slug=="expired":
        doc.action_holders.clear()
        return add_action_holder_change_event(
            doc, 
            Person.objects.get(name='(System)'), 
            prev_set,
            reason='draft expired',
        )
    else:
        # Update the action holders. To get this right for people with more
        # than one relationship to the document, do removals first, then adds.
        # Remove outdated action holders
        iesg_state_changed = (prev_state != new_state) and (getattr(new_state, "type_id", None) == "draft-iesg") 
        if iesg_state_changed:
            # Clear the action_holders list on a state change. This will reset the age of any that get added back.
            doc.action_holders.clear()
        if tags.removed("need-rev"):
            # Removed the 'need-rev' tag - drop authors from the action holders list
            DocumentActionHolder.objects.filter(document=doc, person__in=doc.authors()).delete()
        elif tags.added("need-rev"):
            # Remove the AD if we're asking for a new revision
            DocumentActionHolder.objects.filter(document=doc, person=doc.ad).delete()

        # Add new action holders
        if doc.ad:
            # AD is an action holder unless specified otherwise for the new state
            if iesg_state_changed and new_state.slug not in DocumentActionHolder.CLEAR_ACTION_HOLDERS_STATES:
                doc.action_holders.add(doc.ad)
            # If AD follow-up is needed, make sure they are an action holder 
            if tags.added("ad-f-up"):
                doc.action_holders.add(doc.ad)
        # Authors get the action if a revision is needed
        if tags.added("need-rev"):
            for auth in doc.authors():
                doc.action_holders.add(auth)

        # Now create an event if we changed the set
        return add_action_holder_change_event(
            doc, 
            Person.objects.get(name='(System)'), 
            prev_set,
            reason='IESG state changed',
        )


def update_documentauthors(doc, new_docauthors, by=None, basis=None):
    """Update the list of authors for a document

    Returns an iterable of events describing the change. These must be saved by the caller if
    they are to be kept.

    The new_docauthors argument should be an iterable containing objects that
    have person, email, affiliation, and country attributes. An easy way to create
    these objects is to use DocumentAuthor(), but e.g., a named tuple could be
    used. These objects will not be saved, their attributes will be used to create new
    DocumentAuthor instances. (The document and order fields will be ignored.)
    """
    def _change_field_and_describe(auth, field, newval):
        # make the change
        oldval = getattr(auth, field)
        setattr(auth, field, newval)
        
        was_empty = oldval is None or len(str(oldval)) == 0
        now_empty = newval is None or len(str(newval)) == 0
        
        # describe the change
        if oldval == newval:
            return None
        else:
            if was_empty and not now_empty:
                return 'set {field} to "{new}"'.format(field=field, new=newval)
            elif now_empty and not was_empty:
                return 'cleared {field} (was "{old}")'.format(field=field, old=oldval)
            else:
                return 'changed {field} from "{old}" to "{new}"'.format(
                    field=field, old=oldval, new=newval
                )

    persons = []
    changes = []  # list of change descriptions

    for order, docauthor in enumerate(new_docauthors):
        # If an existing DocumentAuthor matches, use that
        auth = doc.documentauthor_set.filter(person=docauthor.person).first()
        is_new_auth = auth is None
        if is_new_auth:
            # None exists, so create a new one (do not just use docauthor here because that
            # will modify the input and might cause side effects)
            auth = DocumentAuthor(document=doc, person=docauthor.person)
            changes.append('Added "{name}" as author'.format(name=auth.person.name))

        author_changes = []
        # Now fill in other author details
        author_changes.append(_change_field_and_describe(auth, 'email', docauthor.email))
        author_changes.append(_change_field_and_describe(auth, 'affiliation', docauthor.affiliation or ''))
        author_changes.append(_change_field_and_describe(auth, 'country', docauthor.country or ''))
        author_changes.append(_change_field_and_describe(auth, 'order', order + 1))
        auth.save()
        log.assertion('auth.email_id != "none"')
        persons.append(docauthor.person)
        if not is_new_auth:
            all_author_changes = ', '.join([ch for ch in author_changes if ch is not None])
            if len(all_author_changes) > 0:
                changes.append('Changed author "{name}": {changes}'.format(
                    name=auth.person.name, changes=all_author_changes
                ))

    # Finally, remove any authors no longer in the list
    removed_authors = doc.documentauthor_set.exclude(person__in=persons) 
    changes.extend(['Removed "{name}" as author'.format(name=auth.person.name)
                    for auth in removed_authors])
    removed_authors.delete()

    # Create change events - one event per author added/changed/removed.
    # Caller must save these if they want them persisted.
    return [
        EditedAuthorsDocEvent(
            type='edited_authors', by=by, doc=doc, rev=doc.rev, desc=change, basis=basis
        ) for change in changes
    ] 

def update_reminder(doc, reminder_type_slug, event, due_date):
    reminder_type = DocReminderTypeName.objects.get(slug=reminder_type_slug)

    try:
        reminder = DocReminder.objects.get(event__doc=doc, type=reminder_type, active=True)
    except DocReminder.DoesNotExist:
        reminder = None

    if due_date:
        # activate/update reminder
        if not reminder:
            reminder = DocReminder(type=reminder_type)

        reminder.event = event
        reminder.due = due_date
        reminder.active = True
        reminder.save()
    else:
        # deactivate reminder
        if reminder:
            reminder.active = False
            reminder.save()

def prettify_std_name(n, spacing=" "):
    if re.match(r"(rfc|bcp|fyi|std)[0-9]+", n):
        return n[:3].upper() + spacing + n[3:]
    else:
        return n

def default_consensus(doc):
    # if someone edits the consensus return that, otherwise
    # ietf stream => true and irtf stream => false
    consensus = None
    e = doc.latest_event(ConsensusDocEvent, type="changed_consensus")
    if (e):
        return e.consensus
    if doc.stream_id == "ietf":
        consensus = True
    elif doc.stream_id == "irtf":
        consensus = False
    else:                               # ise, iab, legacy
        return consensus

def nice_consensus(consensus):
    mapping = {
        None: "Unknown",
        True: "Yes",
        False: "No"
        }
    return mapping[consensus]

def has_same_ballot(doc, date1, date2=None):
    """ Test if the most recent ballot created before the end of date1
        is the same as the most recent ballot created before the
        end of date 2. """
    datetime1 = datetime_from_date(date1, DEADLINE_TZINFO)
    if date2 is None:
        datetime2 = datetime_today(DEADLINE_TZINFO)
    else:
        datetime2 = datetime_from_date(date2, DEADLINE_TZINFO)
    ballot1 = doc.latest_event(
        BallotDocEvent,
        type='created_ballot',
        time__lt=datetime1 + datetime.timedelta(days=1),
    )
    ballot2 = doc.latest_event(
        BallotDocEvent,
        type='created_ballot',
        time__lt=datetime2 + datetime.timedelta(days=1),
    )
    return ballot1 == ballot2

def make_notify_changed_event(request, doc, by, new_notify, time=None):

    # FOR REVIEW: This preserves the behavior from when
    # drafts and charters had separate edit_notify
    # functions. If it should be unified, there should
    # also be a migration function cause historic
    # events to match
    if doc.type.slug=='charter':
        event_type = 'changed_document'
    else:
        event_type = 'added_comment'

    e = DocEvent(type=event_type, doc=doc, rev=doc.rev, by=by)
    e.desc = "Notification list changed to %s" % (escape(new_notify) or "none")
    if doc.notify:
        e.desc += " from %s" % escape(doc.notify)
    if time:
        e.time = time
    e.save()

    return e

def update_telechat(request, doc, by, new_telechat_date, new_returning_item=None):
    on_agenda = bool(new_telechat_date)

    prev = doc.latest_event(TelechatDocEvent, type="scheduled_for_telechat")
    prev_returning = bool(prev and prev.returning_item)
    prev_telechat = prev.telechat_date if prev else None
    prev_agenda = bool(prev_telechat)

    if new_returning_item == None:
        returning = prev_returning
    else:
        returning = new_returning_item

    if returning == prev_returning and new_telechat_date == prev_telechat:
        # fully updated, nothing to do
        return

    # auto-set returning item _ONLY_ if the caller did not provide a value
    if (     new_returning_item != None
         and on_agenda
         and prev_agenda
         and new_telechat_date != prev_telechat
         and prev_telechat < date_today(DEADLINE_TZINFO)
         and has_same_ballot(doc,prev.telechat_date)
       ):
        returning = True

    e = TelechatDocEvent()
    e.type = "scheduled_for_telechat"
    e.by = by
    e.doc = doc
    e.rev = doc.rev
    e.returning_item = returning
    e.telechat_date = new_telechat_date

    if on_agenda != prev_agenda:
        if on_agenda:
            e.desc = "Placed on agenda for telechat - %s" % (new_telechat_date)
        else:
            e.desc = "Removed from agenda for telechat"
    elif on_agenda and new_telechat_date != prev_telechat:
        e.desc = "Telechat date has been changed to <b>%s</b> from <b>%s</b>" % (
            new_telechat_date, prev_telechat)
    else:
        # we didn't reschedule but flipped returning item bit - let's
        # just explain that
        if returning:
            e.desc = "Set telechat returning item indication"
        else:
            e.desc = "Removed telechat returning item indication"

    e.save()

    has_short_fuse = doc.type_id=='draft' and new_telechat_date and (( new_telechat_date - date_today() ) < datetime.timedelta(days=13))

    from ietf.doc.mails import email_update_telechat

    if has_short_fuse:
       email_update_telechat(request, doc, e.desc+"\n\nWARNING: This may not leave enough time for directorate reviews!\n")
    else:
       email_update_telechat(request, doc, e.desc)

    return e

def rebuild_reference_relations(doc, filenames):
    """Rebuild reference relations for a document

    filenames should be a dict mapping file ext (i.e., type) to the full path of each file.
    """
    if doc.type.slug != 'draft':
        return None

    # try XML first
    if 'xml' in filenames:
        refs = XMLDraft(filenames['xml']).get_refs()
    elif 'txt' in filenames:
        filename = filenames['txt']
        try:
            refs = draft.PlaintextDraft.from_file(filename).get_refs()
        except IOError as e:
            return { 'errors': ["%s :%s" %  (e.strerror, filename)] }
    else:
        return {'errors': ['No Internet-Draft text available for rebuilding reference relations. Need XML or plaintext.']}

    doc.relateddocument_set.filter(relationship__slug__in=['refnorm','refinfo','refold','refunk']).delete()

    warnings = []
    errors = []
    unfound = set()
    for ( ref, refType ) in refs.items():
        refdoc = Document.objects.filter(name=ref)
        if not refdoc and re.match(r"^draft-.*-\d{2}$", ref):
            refdoc = Document.objects.filter(name=ref[:-3])
        count = refdoc.count()
        if count == 0:
            unfound.add( "%s" % ref )
            continue
        elif count > 1:
            errors.append("Too many Document objects found for %s"%ref)
        else:
            # Don't add references to ourself
            if doc != refdoc[0]:
                RelatedDocument.objects.get_or_create( source=doc, target=refdoc[ 0 ], relationship=DocRelationshipName.objects.get( slug='ref%s' % refType ) )
    if unfound:
        warnings.append('There were %d references with no matching Document'%len(unfound))

    ret = {}
    if errors:
        ret['errors']=errors
    if warnings:
        ret['warnings']=warnings
    if unfound:
        ret['unfound']=list(unfound)

    return ret

def set_replaces_for_document(request, doc, new_replaces, by, email_subject, comment=""):
    addrs = gather_address_lists('doc_replacement_changed',doc=doc)
    to = set(addrs.to)
    cc = set(addrs.cc)

    relationship = DocRelationshipName.objects.get(slug='replaces')
    old_replaces = doc.related_that_doc("replaces")

    events = []

    e = DocEvent(doc=doc, rev=doc.rev, by=by, type='changed_document')
    new_replaces_names = ", ".join(d.name for d in new_replaces) or "None"
    old_replaces_names = ", ".join(d.name for d in old_replaces) or "None"
    e.desc = "This document now replaces <b>%s</b> instead of %s" % (new_replaces_names, old_replaces_names)
    e.save()

    events.append(e)

    if comment:
        events.append(DocEvent.objects.create(doc=doc, rev=doc.rev, by=by, type="added_comment", desc=comment))

    for d in old_replaces:
        if d not in new_replaces:
            other_addrs = gather_address_lists('doc_replacement_changed',doc=d)
            to.update(other_addrs.to)
            cc.update(other_addrs.cc)
            RelatedDocument.objects.filter(source=doc, target=d, relationship=relationship).delete()
            if not RelatedDocument.objects.filter(target=d, relationship=relationship):
                s = 'active' if d.expires > timezone.now() else 'expired'
                d.set_state(State.objects.get(type='draft', slug=s))

    for d in new_replaces:
        if d not in old_replaces:
            other_addrs = gather_address_lists('doc_replacement_changed',doc=d)
            to.update(other_addrs.to)
            cc.update(other_addrs.cc)
            RelatedDocument.objects.create(source=doc, target=d, relationship=relationship)
            d.set_state(State.objects.get(type='draft', slug='repl'))
            
            if d.stream_id in ('irtf','ise','iab'):
                repl_state = State.objects.get(type_id='draft-stream-%s'%d.stream_id, slug='repl')
                d.set_state(repl_state)
                events.append(StateDocEvent.objects.create(doc=d, rev=d.rev, by=by, type='changed_state', desc="Set stream state to Replaced",state_type=repl_state.type, state=repl_state))

    # make sure there are no lingering suggestions duplicating new replacements
    RelatedDocument.objects.filter(source=doc, target__in=new_replaces, relationship="possibly-replaces").delete()

    email_desc = e.desc.replace(", ", "\n    ")

    if comment:
        email_desc += "\n" + comment

    from ietf.doc.mails import html_to_text

    send_mail(request, list(to),
              "DraftTracker Mail System <iesg-secretary@ietf.org>",
              email_subject,
              "doc/mail/change_notice.txt",
              dict(text=html_to_text(email_desc),
                   doc=doc,
                   url=settings.IDTRACKER_BASE_URL + doc.get_absolute_url()),
              cc=list(cc))

    return events

def check_common_doc_name_rules(name):
    """Check common rules for document names for use in forms, throws
    ValidationError in case there's a problem."""

    errors = []
    if re.search("[^a-z0-9-]", name):
        errors.append("The name may only contain digits, lowercase letters and dashes.")
    if re.search("--", name):
        errors.append("Please do not put more than one hyphen between any two words in the name.")
    if re.search("-[0-9]{2}$", name):
        errors.append("This name looks like ends in a version number. -00 will be added automatically. Please adjust the end of the name.")

    if errors:
        raise ValidationError(errors)

def get_initial_notify(doc,extra=None):
    # With the mailtrigger based changes, a document's notify should start empty
    receivers = []

    if extra:
        if isinstance(extra, str):
            extra = extra.split(', ')
        receivers.extend(extra)

    return ", ".join(set([x.strip() for x in receivers]))

def uppercase_std_abbreviated_name(name):
    if re.match('(rfc|bcp|std|fyi) ?[0-9]+$', name):
        return name.upper()
    else:
        return name

def extract_complete_replaces_ancestor_mapping_for_docs(names):
    """Return dict mapping all replaced by relationships of the
    replacement ancestors to docs. So if x is directly replaced by y
    and y is in names or replaced by something in names, x in
    replaces[y]."""

    replaces = defaultdict(set)

    checked = set()
    front = names
    while True:
        if not front:
            break

        relations = ( RelatedDocument.objects.filter(source__name__in=front, relationship="replaces")
                          .select_related("target").values_list("source__name", "target__name") )
        if not relations:
            break

        checked.update(front)

        front = []
        for source_doc, target_doc in relations:
            replaces[source_doc].add(target_doc)

            if target_doc not in checked:
                front.append(target_doc)

    return replaces


def make_rev_history(doc):
    # return document history data for inclusion in doc.json (used by timeline)

    def get_predecessors(doc, predecessors=None):
        if predecessors is None:
            predecessors = set()
        if hasattr(doc, 'relateddocument_set'):
            for document in doc.related_that_doc('replaces'):
                if document not in predecessors:
                    predecessors.add(document)
                    predecessors.update(get_predecessors(document, predecessors))
        if doc.came_from_draft():
            predecessors.add(doc.came_from_draft())
            predecessors.update(get_predecessors(doc.came_from_draft(), predecessors))
        return predecessors

    def get_ancestors(doc, ancestors = None):
        if ancestors is None:
            ancestors = set()
        if hasattr(doc, 'relateddocument_set'):
            for document in doc.related_that('replaces'):
                if document not in ancestors:
                    ancestors.add(document)
                    ancestors.update(get_ancestors(document, ancestors))
        if doc.became_rfc():
            if doc.became_rfc() not in ancestors:
                ancestors.add(doc.became_rfc())
                ancestors.update(get_ancestors(doc.became_rfc(), ancestors))
        return ancestors

    def get_replaces_tree(doc):
        tree = get_predecessors(doc)
        tree.update(get_ancestors(doc))
        return tree

    history = {}
    docs = get_replaces_tree(doc)
    if docs is not None:
        docs.add(doc)
        for d in docs:
            if d.type_id == "rfc":
                url = urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=d))
                e = d.docevent_set.filter(type="published_rfc").order_by("-time").first()
                history[url] = {
                    "name": d.name,
                    "rev": d.name,
                    "published": e and e.time.isoformat(),
                    "url": url,
                }
            else:
                for e in d.docevent_set.filter(type='new_revision').distinct():
                    if hasattr(e, 'newrevisiondocevent'):
                        url = urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=d)) + e.newrevisiondocevent.rev + "/"
                        history[url] = {
                            'name': d.name,
                            'rev': e.newrevisiondocevent.rev,
                            'published': e.time.isoformat(),
                            'url': url,
                        }
                        if d.history_set.filter(rev=e.newrevisiondocevent.rev).exists():
                            history[url]['pages'] = d.history_set.filter(rev=e.newrevisiondocevent.rev).first().pages

    if doc.type_id == "draft":
        # Do nothing - all draft revisions are captured above already.
        e = None 
    elif doc.type_id == "rfc":
        # e.time.date() agrees with RPC publication date when shown in the RPC_TZINFO time zone
        e = doc.latest_event(type='published_rfc')
    else:
        e = doc.latest_event(type='iesg_approved')
    if e:
        url = urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=e.doc))
        history[url] = {
            'name': e.doc.name,
            'rev': e.doc.name,
            'published': e.time.isoformat(),
            'url': url
        }
        if doc.type_id != "rfc" and hasattr(e, 'newrevisiondocevent') and doc.history_set.filter(rev=e.newrevisiondocevent.rev).exists():
            history[url]['pages'] = doc.history_set.filter(rev=e.newrevisiondocevent.rev).first().pages
    history = list(history.values())
    return sorted(history, key=lambda x: x['published'])


def build_file_urls(doc: Union[Document, DocHistory]):
    if doc.type_id == "rfc":
        base_path = os.path.join(settings.RFC_PATH, doc.name + ".")
        possible_types = settings.RFC_FILE_TYPES
        found_types = [t for t in possible_types if os.path.exists(base_path + t)]

        base = "https://www.rfc-editor.org/rfc/"

        file_urls = []
        for t in found_types:
            if t == "ps": # Postscript might have been submitted but should not be displayed in the list of URLs
                continue
            label = "plain text" if t == "txt" else t
            file_urls.append((label, base + doc.name + "." + t))

        if "pdf" not in found_types and "txt" in found_types:
            file_urls.append(("pdf", base + "pdfrfc/" + doc.name + ".txt.pdf"))

        if "txt" in found_types:
            file_urls.append(("htmlized", urlreverse('ietf.doc.views_doc.document_html', kwargs=dict(name=doc.name))))
            if doc.tags.filter(slug="verified-errata").exists():
                file_urls.append(("with errata", settings.RFC_EDITOR_INLINE_ERRATA_URL.format(rfc_number=doc.rfc_number)))
        file_urls.append(("bibtex", urlreverse('ietf.doc.views_doc.document_bibtex',kwargs=dict(name=doc.name))))
    elif doc.type_id == "draft" and doc.rev != "":
        base_path = os.path.join(settings.INTERNET_ALL_DRAFTS_ARCHIVE_DIR, doc.name + "-" + doc.rev + ".")
        possible_types = settings.IDSUBMIT_FILE_TYPES
        found_types = [t for t in possible_types if os.path.exists(base_path + t)]
        base = settings.IETF_ID_ARCHIVE_URL
        file_urls = []
        for t in found_types:
            if t == "ps": # Postscript might have been submitted but should not be displayed in the list of URLs
                continue
            label = "plain text" if t == "txt" else t
            file_urls.append((label, base + doc.name + "-" + doc.rev + "." + t))

        if doc.text_exists():
            file_urls.append(("htmlized", urlreverse('ietf.doc.views_doc.document_html', kwargs=dict(name=doc.name, rev=doc.rev))))
            file_urls.append(("pdfized", urlreverse('ietf.doc.views_doc.document_pdfized', kwargs=dict(name=doc.name, rev=doc.rev))))
        file_urls.append(("bibtex", urlreverse('ietf.doc.views_doc.document_bibtex',kwargs=dict(name=doc.name,rev=doc.rev))))
        file_urls.append(("bibxml", urlreverse('ietf.doc.views_doc.document_bibxml',kwargs=dict(name=doc.name,rev=doc.rev))))
    else:
        if doc.type_id == "draft":
            # TODO: look at the state of the database post migration and update this comment, or remove the block
            # As of 2022-12-14, there are 1463 Document and 3136 DocHistory records with type='draft' and rev=''.
            # All of these are in the rfc state and are covered by the above cases.
            log.unreachable('2022-12-14')
        file_urls = []
        found_types = []
        
    return file_urls, found_types

def augment_docs_and_person_with_person_info(docs, person):
    """Add attribute to each document with whether the document is tracked
    or has a review wish by the person or not, and the review teams the person is on."""

    tracked = set()
    review_wished = set()

    # used in templates
    person.review_teams = Group.objects.filter(
        reviewteamsettings__isnull=False, role__person=person, role__name='reviewer')

    doc_pks = [d.pk for d in docs]
    clist = CommunityList.objects.filter(person=person).first()
    if clist:
        tracked.update(
            docs_tracked_by_community_list(clist).filter(pk__in=doc_pks).values_list("pk", flat=True))

    wishes = ReviewWish.objects.filter(person=person)
    wishes = wishes.filter(doc__pk__in=doc_pks).values_list("doc__pk", flat=True)
    review_wished.update(wishes)

    for d in docs:
        d.tracked_in_personal_community_list = d.pk in tracked
        d.has_review_wish = d.pk in review_wished


def update_doc_extresources(doc, new_resources, by):
    old_res_strs = '\n'.join(sorted(r.to_form_entry_str() for r in doc.docextresource_set.all()))
    new_res_strs = '\n'.join(sorted(r.to_form_entry_str() for r in new_resources))
    
    if old_res_strs == new_res_strs:
        return False  # no change

    old_res_strs = f'\n\n{old_res_strs}\n\n' if old_res_strs else ' None '
    new_res_strs = f'\n\n{new_res_strs}' if new_res_strs else ' None'

    doc.docextresource_set.all().delete()
    for new_res in new_resources:
        new_res.doc = doc
        new_res.save()
    e = DocEvent(doc=doc, rev=doc.rev, by=by, type='changed_document')
    e.desc = f"Changed document external resources from:{old_res_strs}to:{new_res_strs}"
    e.save()
    doc.save_with_history([e])
    return True

def generate_idnits2_rfc_status():

    blob=['N']*10000

    symbols={
        'ps': 'P',
        'inf': 'I',
        'exp': 'E',
        'ds': 'D',
        'hist': 'H',
        'std': 'S',
        'bcp': 'B',
        'unkn': 'U',
    }

    rfcs = Document.objects.filter(type_id='rfc')
    for rfc in rfcs:
        offset = int(rfc.rfc_number)-1
        blob[offset] = symbols[rfc.std_level_id]
        if rfc.related_that('obs'):
            blob[offset] = 'O'

    # Workarounds for unusual states in the datatracker

    # The explanation for 6312 is from before docalias was removed
    # The workaround is still needed, even if the datatracker
    # state no longer matches what's described here:
    #   Document.get(docalias='rfc6312').rfc_number == 6342 
    #   6312 was published with the wrong rfc number in it
    #   weird workaround in the datatracker - there are two 
    #   DocAliases starting with rfc - the canonical name code
    #   searches for the lexically highest alias starting with rfc
    #   which is getting lucky.
    blob[6312 - 1] = 'O'

    # RFC200 is an old RFC List by Number
    blob[200 -1] = 'O' 

    # End Workarounds

    blob = re.sub('N*$','',''.join(blob))
    blob = textwrap.fill(blob, width=64)

    return blob

def generate_idnits2_rfcs_obsoleted():
    obsdict = defaultdict(list)
    for r in RelatedDocument.objects.filter(relationship_id='obs'):
        obsdict[int(r.target.rfc_number)].append(int(r.source.rfc_number)) # Aren't these already guaranteed to be ints?
    for k in obsdict:
        obsdict[k] = sorted(obsdict[k])
    return render_to_string('doc/idnits2-rfcs-obsoleted.txt', context={'obsitems':sorted(obsdict.items())})


def fuzzy_find_documents(name, rev=None):
    """Find a document based on name/rev

    Applies heuristics, assuming the inputs were joined by a '-' that may have been misplaced.
    If returned documents queryset is empty, matched_rev and and matched_name are meaningless.
    The rev input is not validated - it is used to find possible names if the name input does
    not match anything, but matched_rev may not correspond to an actual version of the found
    document.
    """
    # Handle special case name formats
    if re.match(r"^\s*rfc", name, flags=re.IGNORECASE):
        name = re.sub(r"\s+", "", name.lower())
    if name.startswith('rfc0'):
        name = "rfc" + name[3:].lstrip('0')
    if name.startswith('review-') and re.search(r'-\d\d\d\d-\d\d$', name):
        name = "%s-%s" % (name, rev)
        rev = None
    if rev and not name.startswith('charter-') and re.search('[0-9]{1,2}-[0-9]{2}', rev):
        name = "%s-%s" % (name, rev[:-3])
        rev = rev[-2:]
    if re.match("^[0-9]+$", name):
        name = f'rfc{name}'

    if name.startswith("rfc"):
        sought_type = "rfc"
        name = name.split("-")[0] # strip any noise (like a revision) at and after the first hyphen
        rev = None # If someone is looking for an RFC and supplies a version, ignore it.
    else:
        sought_type = "draft"

    # see if we can find a document using this name
    docs = Document.objects.filter(name=name, type_id=sought_type)
    if sought_type == "draft" and rev and not docs.exists():
        # No draft found, see if the name/rev split has been misidentified.
        # Handles some special cases, like draft-ietf-tsvwg-ieee-802-11.
        name = '%s-%s' % (name, rev)
        docs = Document.objects.filter(name=name, type_id='draft')
        if docs.exists():
            rev = None  # found a doc by name with rev = None, so update that

    FoundDocuments = namedtuple('FoundDocuments', 'documents matched_name matched_rev')
    return FoundDocuments(docs, name, rev)


def bibxml_for_draft(doc, rev=None):

    if rev is not None and rev != doc.rev:
        # find the entry in the history
        for h in doc.history_set.order_by("-time"):
            if rev == h.rev:
                doc = h
                break
    if rev and rev != doc.rev:
        raise Http404("Revision not found")

    # Build the date we want to claim for the document in the bibxml
    # For documents that have relevant NewRevisionDocEvents, use the date of the event.
    # Very old documents don't have NewRevisionDocEvents - just use the document time.
        
    latest_revision_event = doc.latest_event(NewRevisionDocEvent, type="new_revision")
    latest_revision_rev = latest_revision_event.rev if latest_revision_event else None
    best_events = NewRevisionDocEvent.objects.filter(doc__name=doc.name, rev=(rev or latest_revision_rev))
    tzinfo = ZoneInfo(settings.TIME_ZONE)
    if best_events.exists():
        # There was a period where it was possible to get more than one NewRevisionDocEvent for a revision.
        # A future data cleanup would allow this to be simplified
        best_event = best_events.order_by('time').first()
        log.assertion('doc.rev == best_event.rev')
        doc.date = best_event.time.astimezone(tzinfo).date()
    else:
        doc.date = doc.time.astimezone(tzinfo).date()      # Even if this may be incorrect, what would be better?

    name = doc.name if isinstance(doc, Document) else doc.doc.name
    if name.startswith('rfc'): # bibxml3 does not speak of RFCs
        raise Http404()
        
    return render_to_string('doc/bibxml.xml', {'name':name, 'doc':doc, 'doc_bibtype':'I-D', 'settings':settings})


class DraftAliasGenerator:
    days = 2 * 365

    def __init__(self, draft_queryset=None):
        if draft_queryset is not None:
            self.draft_queryset = draft_queryset.filter(type_id="draft")  # only drafts allowed
        else:
            self.draft_queryset = Document.objects.filter(type_id="draft")

    def get_draft_ad_emails(self, doc):
        """Get AD email addresses for the given draft, if any."""
        from ietf.group.utils import get_group_ad_emails  # avoid circular import
        ad_emails = set()
        # If working group document, return current WG ADs
        if doc.group and doc.group.acronym != "none":
            ad_emails.update(get_group_ad_emails(doc.group))
        # Document may have an explicit AD set
        if doc.ad:
            ad_emails.add(doc.ad.email_address())
        return ad_emails

    def get_draft_chair_emails(self, doc):
        """Get chair email addresses for the given draft, if any."""
        from ietf.group.utils import get_group_role_emails  # avoid circular import
        chair_emails = set()
        if doc.group:
            chair_emails.update(get_group_role_emails(doc.group, ["chair", "secr"]))
        return chair_emails

    def get_draft_shepherd_email(self, doc):
        """Get shepherd email addresses for the given draft, if any."""
        shepherd_email = set()
        if doc.shepherd:
            shepherd_email.add(doc.shepherd.email_address())
        return shepherd_email

    def get_draft_authors_emails(self, doc):
        """Get list of authors for the given draft."""
        author_emails = set()
        for email in Email.objects.filter(documentauthor__document=doc):
            if email.active:
                author_emails.add(email.address)
            elif email.person:
                person_email = email.person.email_address()
                if person_email:
                    author_emails.add(person_email)
        return author_emails

    def get_draft_notify_emails(self, doc):
        """Get list of email addresses to notify for the given draft."""
        ad_email_alias_regex = r"^%s.ad@(%s|%s)$" % (doc.name, settings.DRAFT_ALIAS_DOMAIN, settings.TOOLS_SERVER)
        all_email_alias_regex = r"^%s.all@(%s|%s)$" % (doc.name, settings.DRAFT_ALIAS_DOMAIN, settings.TOOLS_SERVER)
        author_email_alias_regex = r"^%s@(%s|%s)$" % (doc.name, settings.DRAFT_ALIAS_DOMAIN, settings.TOOLS_SERVER)
        notify_email_alias_regex = r"^%s.notify@(%s|%s)$" % (
        doc.name, settings.DRAFT_ALIAS_DOMAIN, settings.TOOLS_SERVER)
        shepherd_email_alias_regex = r"^%s.shepherd@(%s|%s)$" % (
        doc.name, settings.DRAFT_ALIAS_DOMAIN, settings.TOOLS_SERVER)
        notify_emails = set()
        if doc.notify:
            for e in doc.notify.split(','):
                e = e.strip()
                if re.search(ad_email_alias_regex, e):
                    notify_emails.update(self.get_draft_ad_emails(doc))
                elif re.search(author_email_alias_regex, e):
                    notify_emails.update(self.get_draft_authors_emails(doc))
                elif re.search(shepherd_email_alias_regex, e):
                    notify_emails.update(self.get_draft_shepherd_email(doc))
                elif re.search(all_email_alias_regex, e):
                    notify_emails.update(self.get_draft_ad_emails(doc))
                    notify_emails.update(self.get_draft_authors_emails(doc))
                    notify_emails.update(self.get_draft_shepherd_email(doc))
                elif re.search(notify_email_alias_regex, e):
                    pass
                else:
                    (name, email) = parseaddr(e)
                    notify_emails.add(email)
        return notify_emails

    def _yield_aliases_for_draft(self, doc)-> Iterator[tuple[str, list[str]]]:
        alias = doc.name
        all = set()

        # no suffix and .authors are the same list
        emails = self.get_draft_authors_emails(doc)
        all.update(emails)
        if emails:
            yield alias, list(emails)
            yield alias + ".authors", list(emails)

        # .chairs = group chairs
        emails = self.get_draft_chair_emails(doc)
        if emails:
            all.update(emails)
            yield alias + ".chairs", list(emails)

        # .ad = sponsoring AD / WG AD (WG document)
        emails = self.get_draft_ad_emails(doc)
        if emails:
            all.update(emails)
            yield alias + ".ad", list(emails)

        # .notify = notify email list from the Document
        emails = self.get_draft_notify_emails(doc)
        if emails:
            all.update(emails)
            yield alias + ".notify", list(emails)

        # .shepherd = shepherd email from the Document
        emails = self.get_draft_shepherd_email(doc)
        if emails:
            all.update(emails)
            yield alias + ".shepherd", list(emails)

        # .all = everything from above
        if all:
            yield alias + ".all", list(all)

    def __iter__(self) -> Iterator[tuple[str, list[str]]]:
        # Internet-Drafts with active status or expired within self.days
        show_since = timezone.now() - datetime.timedelta(days=self.days)
        drafts = self.draft_queryset

        # Look up the draft-active state properly. Doing this with
        # states__type_id, states__slug directly in the `filter()`
        # works, but it does not work as expected in `exclude()`.
        active_state = State.objects.get(type_id="draft", slug="active")
        active_pks = []  # build a static list of the drafts we actually returned as "active"
        active_drafts = drafts.filter(states=active_state)
        for this_draft in active_drafts:
            active_pks.append(this_draft.pk)
            for alias, addresses in self._yield_aliases_for_draft(this_draft):
                yield alias, addresses

        # Annotate with the draft state slug so we can check for drafts that
        # have become RFCs
        inactive_recent_drafts = (
            drafts.exclude(pk__in=active_pks)  # don't re-filter by state, states may have changed during the run!
            .filter(expires__gte=show_since)
            .annotate(
                # Why _default_manager instead of objects? See:
                # https://docs.djangoproject.com/en/4.2/topics/db/managers/#django.db.models.Model._default_manager
                draft_state_slug=Document.states.through._default_manager.filter(
                    document__pk=OuterRef("pk"),
                    state__type_id="draft"
                ).values("state__slug"),
            )
        )
        for this_draft in inactive_recent_drafts:
            # Omit drafts that became RFCs, unless they were published in the last DEFAULT_YEARS
            if this_draft.draft_state_slug == "rfc":
                rfc = this_draft.became_rfc()
                log.assertion("rfc is not None")
                if rfc.latest_event(type='published_rfc').time < show_since:
                    continue
            for alias, addresses in self._yield_aliases_for_draft(this_draft):
                yield alias, addresses


def get_doc_email_aliases(name: Optional[str] = None):
    aliases = []
    for (alias, alist) in DraftAliasGenerator(
        Document.objects.filter(type_id="draft", name=name) if name else None
    ):
        # alias is draft-name.alias_type
        doc_name, _dot, alias_type = alias.partition(".")
        aliases.append({
            "doc_name": doc_name,
            "alias_type": f".{alias_type}" if alias_type else "",
            "expansion": ", ".join(sorted(alist)),
        })
    return sorted(aliases, key=lambda a: (a["doc_name"]))


def investigate_fragment(name_fragment):
    can_verify = set()
    for root in [settings.INTERNET_DRAFT_PATH, settings.INTERNET_DRAFT_ARCHIVE_DIR]:
        can_verify.update(list(Path(root).glob(f"*{name_fragment}*")))
    archive_verifiable_names = set([p.name for p in can_verify])
    # Can also verify drafts in proceedings directories
    can_verify.update(list(Path(settings.AGENDA_PATH).glob(f"**/*{name_fragment}*")))

    # N.B. This reflects the assumption that the internet draft archive dir is in the
    # a directory with other collections (at /a/ietfdata/draft/collections as this is written)
    unverifiable_collections = set([
        p for p in
        Path(settings.INTERNET_DRAFT_ARCHIVE_DIR).parent.glob(f"**/*{name_fragment}*")
        if p.name not in archive_verifiable_names
    ])
    
    unverifiable_collections.difference_update(can_verify)

    expected_names = set([p.name for p in can_verify.union(unverifiable_collections)])
    maybe_unexpected = list(
        Path(settings.INTERNET_ALL_DRAFTS_ARCHIVE_DIR).glob(f"*{name_fragment}*")
    )
    unexpected = [p for p in maybe_unexpected if p.name not in expected_names]

    return dict(
        can_verify=can_verify,
        unverifiable_collections=unverifiable_collections,
        unexpected=unexpected,
    )


def update_or_create_draft_bibxml_file(doc, rev):
    log.assertion("doc.type_id == 'draft'")
    normalized_bibxml = re.sub(r"\r\n?", r"\n", bibxml_for_draft(doc, rev))
    ref_rev_file_path = Path(settings.BIBXML_BASE_PATH) / "bibxml-ids" / f"reference.I-D.{doc.name}-{rev}.xml"
    try:
        existing_bibxml = ref_rev_file_path.read_text(encoding="utf8")
    except IOError:
        existing_bibxml = ""
    if normalized_bibxml.strip() != existing_bibxml.strip():
        log.log(f"Writing {ref_rev_file_path}")
        ref_rev_file_path.write_text(normalized_bibxml, encoding="utf8")


def ensure_draft_bibxml_path_exists():
    (Path(settings.BIBXML_BASE_PATH) / "bibxml-ids").mkdir(exist_ok=True)
