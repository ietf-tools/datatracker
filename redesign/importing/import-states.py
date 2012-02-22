#!/usr/bin/python

import sys, os, datetime

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path = [ basedir ] + sys.path

from ietf import settings
settings.USE_DB_REDESIGN_PROXY_CLASSES = False

from django.core import management
management.setup_environ(settings)


import workflows.models
from ietf.ietfworkflows.models import StateDescription
from ietf.idrfc.mirror_rfc_editor_queue import get_rfc_state_mapping
from ietf.doc.models import *

# adds states for documents and import states from workflows.Workflow
# and ietfworkflows.StateDescription

# state types
draft_type, _ = StateType.objects.get_or_create(slug="draft", label="State")
draft_iesg_type, _ = StateType.objects.get_or_create(slug="draft-iesg", label="IESG state")
draft_iana_type, _ = StateType.objects.get_or_create(slug="draft-iana", label="IANA state")
draft_rfc_type, _ = StateType.objects.get_or_create(slug="draft-rfceditor", label="RFC Editor state")
ietf_type, _ = StateType.objects.get_or_create(slug="draft-stream-ietf", label="IETF state")
irtf_type, _ = StateType.objects.get_or_create(slug="draft-stream-irtf", label="IRTF state")
ise_type, _ = StateType.objects.get_or_create(slug="draft-stream-ise", label="ISE state")
iab_type, _ = StateType.objects.get_or_create(slug="draft-stream-iab", label="IAB state")

slides_type, _ = StateType.objects.get_or_create(slug="slides", label="State")
minutes_type, _ = StateType.objects.get_or_create(slug="minutes", label="State")
agenda_type, _ = StateType.objects.get_or_create(slug="agenda", label="State")
liaison_att_type, _ = StateType.objects.get_or_create(slug="liai-att", label="State")
charter_type, _ = StateType.objects.get_or_create(slug="charter", label="State")

# draft states
print "importing draft states"
State.objects.get_or_create(type=draft_type, slug="active", name="Active", order=1)
State.objects.get_or_create(type=draft_type, slug="expired", name="Expired", order=2)
State.objects.get_or_create(type=draft_type, slug="rfc", name="RFC", order=3)
State.objects.get_or_create(type=draft_type, slug="repl", name="Replaced", order=4)
State.objects.get_or_create(type=draft_type, slug="auth-rm", name="Withdrawn by Submitter", order=5)
State.objects.get_or_create(type=draft_type, slug="ietf-rm", name="Withdrawn by IETF", order=6)

# IESG draft states
State.objects.get_or_create(type=draft_iesg_type, slug="pub", name="RFC Published", desc='The ID has been published as an RFC.', order=32)
State.objects.get_or_create(type=draft_iesg_type, slug="dead", name="Dead", desc='Document is "dead" and is no longer being tracked. (E.g., it has been replaced by another document with a different name, it has been withdrawn, etc.)', order=99)
State.objects.get_or_create(type=draft_iesg_type, slug="approved", name="Approved-announcement to be sent", desc='The IESG has approved the document for publication, but the Secretariat has not yet sent out on official approval message.', order=27)
State.objects.get_or_create(type=draft_iesg_type, slug="ann", name="Approved-announcement sent", desc='The IESG has approved the document for publication, and the Secretariat has sent out the official approval message to the RFC editor.', order=30)
State.objects.get_or_create(type=draft_iesg_type, slug="watching", name="AD is watching", desc='An AD is aware of the document and has chosen to place the document in a separate state in order to keep a closer eye on it (for whatever reason). Documents in this state are still not being actively tracked in the sense that no formal request has been made to publish or advance the document. The sole difference between this state and "I-D Exists" is that an AD has chosen to put it in a separate state, to make it easier to keep track of (for the AD\'s own reasons).', order=42)
State.objects.get_or_create(type=draft_iesg_type, slug="iesg-eva", name="IESG Evaluation", desc='The document is now (finally!) being formally reviewed by the entire IESG. Documents are discussed in email or during a bi-weekly IESG telechat. In this phase, each AD reviews the document and airs any issues they may have. Unresolvable issues are documented as "discuss" comments that can be forwarded to the authors/WG. See the description of substates for additional details about the current state of the IESG discussion.', order=20)
State.objects.get_or_create(type=draft_iesg_type, slug="ad-eval", name="AD Evaluation", desc='A specific AD (e.g., the Area Advisor for the WG) has begun reviewing the document to verify that it is ready for advancement. The shepherding AD is responsible for doing any necessary review before starting an IETF Last Call or sending the document directly to the IESG as a whole.', order=11)
State.objects.get_or_create(type=draft_iesg_type, slug="lc-req", name="Last Call Requested", desc='The AD has requested that the Secretariat start an IETF Last Call, but the the actual Last Call message has not been sent yet.', order=15)
State.objects.get_or_create(type=draft_iesg_type, slug="lc", name="In Last Call", desc='The document is currently waiting for IETF Last Call to complete. Last Calls for WG documents typically last 2 weeks, those for individual submissions last 4 weeks.', order=16)
State.objects.get_or_create(type=draft_iesg_type, slug="pub-req", name="Publication Requested", desc='A formal request has been made to advance/publish the document, following the procedures in Section 7.5 of RFC 2418. The request could be from a WG chair, from an individual through the RFC Editor, etc. (The Secretariat (iesg-secretary@ietf.org) is copied on these requests to ensure that the request makes it into the ID tracker.) A document in this state has not (yet) been reviewed by an AD nor has any official action been taken on it yet (other than to note that its publication has been requested.', order=10)
State.objects.get_or_create(type=draft_iesg_type, slug="rfcqueue", name="RFC Ed Queue", desc='The document is in the RFC editor Queue (as confirmed by http://www.rfc-editor.org/queue.html).', order=31)
State.objects.get_or_create(type=draft_iesg_type, slug="defer", name="IESG Evaluation - Defer", desc='During a telechat, one or more ADs requested an additional 2 weeks to review the document. A defer is designed to be an exception mechanism, and can only be invoked once, the first time the document comes up for discussion during a telechat.', order=21)
State.objects.get_or_create(type=draft_iesg_type, slug="writeupw", name="Waiting for Writeup", desc='Before a standards-track or BCP document is formally considered by the entire IESG, the AD must write up a protocol action. The protocol action is included in the approval message that the Secretariat sends out when the document is approved for publication as an RFC.', order=18)
State.objects.get_or_create(type=draft_iesg_type, slug="goaheadw", name="Waiting for AD Go-Ahead", desc='As a result of the IETF Last Call, comments may need to be responded to and a revision of the ID may be needed as well. The AD is responsible for verifying that all Last Call comments have been adequately addressed and that the (possibly revised) document is in the ID directory and ready for consideration by the IESG as a whole.', order=19)
State.objects.get_or_create(type=draft_iesg_type, slug="review-e", name="Expert Review", desc='An AD sometimes asks for an external review by an outside party as part of evaluating whether a document is ready for advancement. MIBs, for example, are reviewed by the "MIB doctors". Other types of reviews may also be requested (e.g., security, operations impact, etc.). Documents stay in this state until the review is complete and possibly until the issues raised in the review are addressed. See the "note" field for specific details on the nature of the review.', order=12)
State.objects.get_or_create(type=draft_iesg_type, slug="nopubadw", name="DNP-waiting for AD note", desc='Do Not Publish: The IESG recommends against publishing the document, but the writeup explaining its reasoning has not yet been produced. DNPs apply primarily to individual submissions received through the RFC editor.  See the "note" field for more details on who has the action item.', order=33)
State.objects.get_or_create(type=draft_iesg_type, slug="nopubanw", name="DNP-announcement to be sent", desc='The IESG recommends against publishing the document, the writeup explaining its reasoning has been produced, but the Secretariat has not yet sent out the official "do not publish" recommendation message.', order=34)

for s in State.objects.filter(type=draft_iesg_type):
    n = {
        "pub-req": ("ad-eval", "watching", "dead"),
        "ad-eval": ("watching", "lc-req", "review-e", "iesg-eva"),
        "review-e": ("ad-eval", ),
        "lc-req": ("lc", ),
        "lc": ("writeupw", "goaheadw"),
        "writeupw": ("goaheadw", ),
        "goaheadw": ("iesg-eva", ),
        "iesg-eva": ("nopubadw", "defer", "approved"),
        "defer": ("iesg-eva", ),
        "approved": ("ann", ),
        "ann": ("rfcqueue", ),
        "rfcqueue": ("pub", ),
        "pub": ("dead", ),
        "nopubadw": ("nopubanw", ),
        "nopubanw": ("dead", ),
        "watching": ("pub-req", ),
        "dead": ("pub-req", ),
    }

    s.next_states = State.objects.filter(type=draft_iesg_type, slug__in=n[s.slug])

# import RFC Editor queue states
print "importing RFC Editor states"
get_rfc_state_mapping()

# WG states, we can get them from the state descriptions
wg_doc_state_slug = {
    "Call For Adoption By WG Issued": 'c-adopt',
    "Adopted by a WG": 'adopt-wg',
    "Adopted for WG Info Only": 'info',
    "WG Document": 'wg-doc',
    "Parked WG Document": 'parked',
    "Dead WG Document": 'dead',
    "In WG Last Call": 'wg-lc',
    "Waiting for WG Chair Go-Ahead": 'chair-w',
    "WG Consensus: Waiting for Write-Up": 'writeupw',
    "Submitted to IESG for Publication": 'sub-pub',
    }

for o in StateDescription.objects.all().order_by('order'):
    print "importing StateDescription", o.state.name
    s, _ = State.objects.get_or_create(type=ietf_type, slug=wg_doc_state_slug[o.state.name], name=o.state.name)
    s.desc = o.definition.replace("  ", " ").replace("\n ", "\n").replace("\n\n", "DUMMY").replace("\n", "").replace("DUMMY", "\n\n") # get rid of linebreaks, but keep paragraphs
    s.order = o.order
    s.save()

# IAB
print "importing IAB stream states"
State.objects.get_or_create(type=iab_type, slug="candidat", name="Candidate IAB Document", desc="A document being considered for the IAB stream.", order=1)
State.objects.get_or_create(type=iab_type, slug="active", name="Active IAB Document", desc="This document has been adopted by the IAB and is being actively developed.", order=2)
State.objects.get_or_create(type=iab_type, slug="parked", name="Parked IAB Document", desc="This document has lost its author or editor, is waiting for another document to be written, or cannot currently be worked on by the IAB for some other reason. Annotations probably explain why this document is parked.", order=3)
State.objects.get_or_create(type=iab_type, slug="review-i", name="IAB Review", desc="This document is awaiting the IAB itself to come to internal consensus.", order=4)
State.objects.get_or_create(type=iab_type, slug="review-c", name="Community Review", desc="This document has completed internal consensus within the IAB and is now under community review.", order=5)
State.objects.get_or_create(type=iab_type, slug="approved", name="Approved by IAB, To Be Sent to RFC Editor", desc="The consideration of this document is complete, but it has not yet been sent to the RFC Editor for publication (although that is going to happen soon).", order=6)
State.objects.get_or_create(type=iab_type, slug="diff-org", name="Sent to a Different Organization for Publication", desc="The IAB does not expect to publish the document itself, but has passed it on to a different organization that might continue work on the document. The expectation is that the other organization will eventually publish the document.", order=7)
State.objects.get_or_create(type=iab_type, slug="rfc-edit", name="Sent to the RFC Editor", desc="The IAB processing of this document is complete and it has been sent to the RFC Editor for publication. The document may be in the RFC Editor's queue, or it may have been published as an RFC; this state doesn't distinguish between different states occurring after the document has left the IAB.", order=8)
State.objects.get_or_create(type=iab_type, slug="pub", name="Published RFC", desc="The document has been published as an RFC.", order=9)
State.objects.get_or_create(type=iab_type, slug="dead", name="Dead IAB Document", desc="This document was an active IAB document, but for some reason it is no longer being pursued for the IAB stream. It is possible that the document might be revived later, possibly in another stream.", order=10)

# IRTF
print "importing IRTF stream states"
State.objects.get_or_create(type=irtf_type, slug="candidat", name="Candidate RG Document", desc="This document is under consideration in an RG for becoming an IRTF document. A document in this state does not imply any RG consensus and does not imply any precedence or selection.  It's simply a way to indicate that somebody has asked for a document to be considered for adoption by an RG.", order=1)
State.objects.get_or_create(type=irtf_type, slug="active", name="Active RG Document", desc="This document has been adopted by the RG and is being actively developed.", order=2)
State.objects.get_or_create(type=irtf_type, slug="parked", name="Parked RG Document", desc="This document has lost its author or editor, is waiting for another document to be written, or cannot currently be worked on by the RG for some other reason.", order=3)
State.objects.get_or_create(type=irtf_type, slug="rg-lc", name="In RG Last Call", desc="The document is in its final review in the RG.", order=4)
State.objects.get_or_create(type=irtf_type, slug="sheph-w", name="Waiting for Document Shepherd", desc="IRTF documents have document shepherds who help RG documents through the process after the RG has finished with the document.", order=5)
State.objects.get_or_create(type=irtf_type, slug="chair-w", name="Waiting for IRTF Chair", desc="The IRTF Chair is meant to be performing some task such as sending a request for IESG Review.", order=6)
State.objects.get_or_create(type=irtf_type, slug="irsg-w", name="Awaiting IRSG Reviews", desc="The document shepherd has taken the document to the IRSG and solicited reviews from one or more IRSG members.", order=7)
State.objects.get_or_create(type=irtf_type, slug="irsgpoll", name="In IRSG Poll", desc="The IRSG is taking a poll on whether or not the document is ready to be published.", order=8)
State.objects.get_or_create(type=irtf_type, slug="iesg-rev", name="In IESG Review", desc="The IRSG has asked the IESG to do a review of the document, as described in RFC5742.", order=9)
State.objects.get_or_create(type=irtf_type, slug="rfc-edit", name="Sent to the RFC Editor", desc="The RG processing of this document is complete and it has been sent to the RFC Editor for publication. The document may be in the RFC Editor's queue, or it may have been published as an RFC; this state doesn't distinguish between different states occurring after the document has left the RG.", order=10)
State.objects.get_or_create(type=irtf_type, slug="pub", name="Published RFC", desc="The document has been published as an RFC.", order=11)
State.objects.get_or_create(type=irtf_type, slug="iesghold", name="Document on Hold Based On IESG Request", desc="The IESG has requested that the document be held pending further review, as specified in RFC 5742, and the IRTF has agreed to such a hold.", order=12)
State.objects.get_or_create(type=irtf_type, slug="dead", name="Dead IRTF Document", desc="This document was an active IRTF document, but for some reason it is no longer being pursued for the IRTF stream. It is possible that the document might be revived later, possibly in another stream.", order=13)

# ISE
print "importing ISE stream states"
State.objects.get_or_create(type=ise_type, slug="receive", name="Submission Received", desc="The draft has been sent to the ISE with a request for publication.", order=1)
State.objects.get_or_create(type=ise_type, slug="find-rev", name="Finding Reviewers", desc=" The ISE is finding initial reviewers for the document.", order=2)
State.objects.get_or_create(type=ise_type, slug="ise-rev", name="In ISE Review", desc="The ISE is actively working on the document.", order=3)
State.objects.get_or_create(type=ise_type, slug="need-res", name="Response to Review Needed", desc=" One or more reviews have been sent to the author, and the ISE is awaiting response.", order=4)
State.objects.get_or_create(type=ise_type, slug="iesg-rev", name="In IESG Review", desc="The ISE has asked the IESG to do a review of the document, as described in RFC5742.", order=5)
State.objects.get_or_create(type=ise_type, slug="rfc-edit", name="Sent to the RFC Editor", desc="The ISE processing of this document is complete and it has been sent to the RFC Editor for publication. The document may be in the RFC Editor's queue, or it may have been published as an RFC; this state doesn't distinguish between different states occurring after the document has left the ISE.", order=6)
State.objects.get_or_create(type=ise_type, slug="pub", name="Published RFC", desc="The document has been published as an RFC.", order=7)
State.objects.get_or_create(type=ise_type, slug="dead", name="No Longer In Independent Submission Stream", desc="This document was actively considered in the Independent Submission stream, but the ISE chose not to publish it.  It is possible that the document might be revived later. A document in this state may have a comment explaining the reasoning of the ISE (such as if the document was going to move to a different stream).", order=8)
State.objects.get_or_create(type=ise_type, slug="iesghold", name="Document on Hold Based On IESG Request", desc="The IESG has requested that the document be held pending further review, as specified in RFC 5742, and the ISE has agreed to such a hold.", order=9)

# now import the next_states; we only go for the default ones, the
# WG-specific are handled in the group importer

workflows = [(ietf_type, workflows.models.Workflow.objects.get(name="Default WG Workflow")),
             (irtf_type, workflows.models.Workflow.objects.get(name="IRTF Workflow")),
             (ise_type, workflows.models.Workflow.objects.get(name="ISE Workflow")),
             (iab_type, workflows.models.Workflow.objects.get(name="IAB Workflow")),
             ]

for state_type, workflow in workflows:
    states = dict((s.name, s) for s in State.objects.filter(type=state_type))
    old_states = dict((s.name, s) for s in workflow.states.filter(name__in=[name for name in states]).select_related('transitions'))
    for name in states:
        print "importing workflow transitions", workflow.name, name
        s = states[name]
        try:
            o = old_states[name]
        except KeyError:
            print "MISSING state", name, "in workflow", workflow.name
            continue
        s.next_states = [states[t.destination.name] for t in o.transitions.filter(workflow=workflow)]


# meeting material states
for t in (slides_type, minutes_type, agenda_type):
    print "importing states for", t.slug
    State.objects.get_or_create(type=t, slug="active", name="Active", order=1)
    State.objects.get_or_create(type=t, slug="deleted", name="Deleted", order=2)

# charter states
print "importing states for charters"
State.objects.get_or_create(type=charter_type, slug="notrev", name="Not currently under review", desc="The proposed charter is not being considered at this time. A proposed charter will remain in this state until an AD moves it to Informal IESG review.")
State.objects.get_or_create(type=charter_type, slug="infrev", name="Informal IESG review", desc="This is the initial state when an AD proposes a new charter. The normal next state is Internal review if the idea is accepted, or Not currently under review if the idea is abandoned.")
State.objects.get_or_create(type=charter_type, slug="intrev", name="Internal review", desc="The IESG and IAB are reviewing the early draft of the charter; this is the initial IESG and IAB review. The usual next state is External review if the idea is adopted, or Informal IESG review if the IESG decides the idea needs more work, or Not currently under review is the idea is abandoned")
State.objects.get_or_create(type=charter_type, slug="extrev", name="External review", desc="The IETF community and possibly other standards development organizations (SDOs) are reviewing the proposed charter. The usual next state is IESG review, although it might move to Not currently under review is the idea is abandoned during the external review.")
State.objects.get_or_create(type=charter_type, slug="iesgrev", name="IESG review", desc="The IESG is reviewing the discussion from the external review of the proposed charter. The usual next state is Approved, or Not currently under review if the idea is abandoned.")
State.objects.get_or_create(type=charter_type, slug="approved", name="Approved", desc="The charter is approved by the IESG.")
    
