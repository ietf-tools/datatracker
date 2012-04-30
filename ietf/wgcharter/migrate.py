import sys, os, re, datetime

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path = [ basedir ] + sys.path

from ietf import settings
from django.core import management
management.setup_environ(settings)

from ietf.doc.models import *

# make sure ballot positions and types are right
BallotPositionName.objects.get_or_create(slug="block",
                                         order=3,
                                         name="Block",
                                         blocking=True,
                                         )

BallotPositionName.objects.filter(slug="discuss").update(blocking=True)

charter_positions = BallotPositionName.objects.filter(slug__in=["yes", "noobj", "block", "abstain", "norecord" ])

o,_ = BallotType.objects.get_or_create(doc_type_id="charter",
                                 slug="r-extrev",
                                 name="Ready for external review",
                                 question="Is this charter ready for external review?",
                                 order=1,
                                 )

o.positions = charter_positions

o,_ = BallotType.objects.get_or_create(doc_type_id="charter",
                                       slug="r-wo-ext",
                                       name="Ready w/o external review",
                                       question="Is this charter ready for external review? Is this charter ready for approval without external review?",
                                       order=2,
                                       )
o.positions = charter_positions

o,_ = BallotType.objects.get_or_create(doc_type_id="charter",
                                       slug="approve",
                                       name="Approve",
                                       question="Do we approve of this charter?",
                                       order=3,
                                       )
o.positions = charter_positions

draft_ballot,_ = BallotType.objects.get_or_create(doc_type_id="draft",
                                     slug="approve",
                                     name="Approve",
                                     question="",
                                     order=1,
                                     )
draft_ballot.positions = BallotPositionName.objects.filter(slug__in=["yes", "noobj", "discuss", "abstain", "recuse", "norecord"])


# add events for drafts

# prevent memory from leaking when settings.DEBUG=True
from django.db import connection
class DontSaveQueries(object):
    def append(self, x):
        pass
connection.queries = DontSaveQueries()

relevant_docs = Document.objects.filter(type="draft", docevent__type__in=("changed_ballot_position", "sent_ballot_announcement")).distinct()
for d in relevant_docs.iterator():
    ballot = None
    for e in d.docevent_set.order_by("time", "id").select_related("ballotpositiondocevent"):
        if e.type == "created_ballot":
            ballot = e

        if e.type == "closed_ballot":
            ballot = None

        if not ballot and e.type in ("sent_ballot_announcement", "changed_ballot_position"):
            ballot = BallotDocEvent(doc=e.doc, by=e.by)
            ballot.type = "created_ballot"
            ballot.ballot_type = draft_ballot
            # place new event just before
            ballot.time = e.time - datetime.timedelta(seconds=1)
            ballot.desc = u'Created "%s" ballot' % draft_ballot
            ballot.save()

            if e.type == "sent_ballot_announcement":
                print "added ballot for", d.name
            else:
                print "MISSING ballot issue event, added ballot for", d.name

        if e.type == "changed_ballot_position" and not e.ballotpositiondocevent.ballot:
            e.ballotpositiondocevent.ballot_id = ballot.id
            e.ballotpositiondocevent.save()

        if e.type in ("iesg_approved", "iesg_disapproved") and ballot:
            c = BallotDocEvent(doc=e.doc, by=e.by)
            c.type = "closed_ballot"
            c.ballot_type = draft_ballot
            # place new event just before
            c.time = e.time - datetime.timedelta(seconds=1)
            c.desc = u'Closed "%s" ballot' % draft_ballot.name
            c.save()
            ballot = None

            print "closed ballot for", d.name
