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
from redesign.doc.models import *

# import states for documents from workflows.Workflow and
# ietfworkflows.StateDescription

# state types
ietf_state_type, _ = StateType.objects.get_or_create(slug="draft-stream-ietf", label="WG state")
irtf_state_type, _ = StateType.objects.get_or_create(slug="draft-stream-irtf", label="RG state")
ise_state_type, _ = StateType.objects.get_or_create(slug="draft-stream-ise", label="ISE state")
iab_state_type, _ = StateType.objects.get_or_create(slug="draft-stream-iab", label="IAB state")

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
    s, _ = State.objects.get_or_create(type=ietf_state_type, slug=wg_doc_state_slug[o.state.name], name=o.state.name)
    s.desc = o.definition.replace("  ", " ").replace("\n ", "\n").replace("\n\n", "DUMMY").replace("\n", "").replace("DUMMY", "\n\n") # get rid of linebreaks, but keep paragraphs
    s.order = o.order
    s.save()

# IAB
print "importing IAB stream states"
State.objects.get_or_create(type=iab_state_type, slug="candidat", name="Candidate IAB Document", desc="A document being considered for the IAB stream.", order=1)
State.objects.get_or_create(type=iab_state_type, slug="active", name="Active IAB Document", desc="This document has been adopted by the IAB and is being actively developed.", order=2)
State.objects.get_or_create(type=iab_state_type, slug="parked", name="Parked IAB Document", desc="This document has lost its author or editor, is waiting for another document to be written, or cannot currently be worked on by the IAB for some other reason. Annotations probably explain why this document is parked.", order=3)
State.objects.get_or_create(type=iab_state_type, slug="review-i", name="IAB Review", desc="This document is awaiting the IAB itself to come to internal consensus.", order=4)
State.objects.get_or_create(type=iab_state_type, slug="review-c", name="Community Review", desc="This document has completed internal consensus within the IAB and is now under community review.", order=5)
State.objects.get_or_create(type=iab_state_type, slug="approved", name="Approved by IAB, To Be Sent to RFC Editor", desc="The consideration of this document is complete, but it has not yet been sent to the RFC Editor for publication (although that is going to happen soon).", order=6)
State.objects.get_or_create(type=iab_state_type, slug="diff-org", name="Sent to a Different Organization for Publication", desc="The IAB does not expect to publish the document itself, but has passed it on to a different organization that might continue work on the document. The expectation is that the other organization will eventually publish the document.", order=7)
State.objects.get_or_create(type=iab_state_type, slug="rfc-edit", name="Sent to the RFC Editor", desc="The IAB processing of this document is complete and it has been sent to the RFC Editor for publication. The document may be in the RFC Editor's queue, or it may have been published as an RFC; this state doesn't distinguish between different states occurring after the document has left the IAB.", order=8)
State.objects.get_or_create(type=iab_state_type, slug="pub", name="Published RFC", desc="The document has been published as an RFC.", order=9)
State.objects.get_or_create(type=iab_state_type, slug="dead", name="Dead IAB Document", desc="This document was an active IAB document, but for some reason it is no longer being pursued for the IAB stream. It is possible that the document might be revived later, possibly in another stream.", order=10)

# IRTF
print "importing IRTF stream states"
State.objects.get_or_create(type=irtf_state_type, slug="candidat", name="Candidate RG Document", desc="This document is under consideration in an RG for becoming an IRTF document. A document in this state does not imply any RG consensus and does not imply any precedence or selection.  It's simply a way to indicate that somebody has asked for a document to be considered for adoption by an RG.", order=1)
State.objects.get_or_create(type=irtf_state_type, slug="active", name="Active RG Document", desc="This document has been adopted by the RG and is being actively developed.", order=2)
State.objects.get_or_create(type=irtf_state_type, slug="parked", name="Parked RG Document", desc="This document has lost its author or editor, is waiting for another document to be written, or cannot currently be worked on by the RG for some other reason.", order=3)
State.objects.get_or_create(type=irtf_state_type, slug="rg-lc", name="In RG Last Call", desc="The document is in its final review in the RG.", order=4)
State.objects.get_or_create(type=irtf_state_type, slug="sheph-w", name="Waiting for Document Shepherd", desc="IRTF documents have document shepherds who help RG documents through the process after the RG has finished with the document.", order=5)
State.objects.get_or_create(type=irtf_state_type, slug="chair-w", name="Waiting for IRTF Chair", desc="The IRTF Chair is meant to be performing some task such as sending a request for IESG Review.", order=6)
State.objects.get_or_create(type=irtf_state_type, slug="irsg-w", name="Awaiting IRSG Reviews", desc="The document shepherd has taken the document to the IRSG and solicited reviews from one or more IRSG members.", order=7)
State.objects.get_or_create(type=irtf_state_type, slug="irsgpoll", name="In IRSG Poll", desc="The IRSG is taking a poll on whether or not the document is ready to be published.", order=8)
State.objects.get_or_create(type=irtf_state_type, slug="iesg-rev", name="In IESG Review", desc="The IRSG has asked the IESG to do a review of the document, as described in RFC5742.", order=9)
State.objects.get_or_create(type=irtf_state_type, slug="rfc-edit", name="Sent to the RFC Editor", desc="The RG processing of this document is complete and it has been sent to the RFC Editor for publication. The document may be in the RFC Editor's queue, or it may have been published as an RFC; this state doesn't distinguish between different states occurring after the document has left the RG.", order=10)
State.objects.get_or_create(type=irtf_state_type, slug="pub", name="Published RFC", desc="The document has been published as an RFC.", order=11)
State.objects.get_or_create(type=irtf_state_type, slug="iesghold", name="Document on Hold Based On IESG Request", desc="The IESG has requested that the document be held pending further review, as specified in RFC 5742, and the IRTF has agreed to such a hold.", order=12)
State.objects.get_or_create(type=irtf_state_type, slug="dead", name="Dead IRTF Document", desc="This document was an active IRTF document, but for some reason it is no longer being pursued for the IRTF stream. It is possible that the document might be revived later, possibly in another stream.", order=13)

# ISE
print "importing ISE stream states"
State.objects.get_or_create(type=ise_state_type, slug="receive", name="Submission Received", desc="The draft has been sent to the ISE with a request for publication.", order=1)
State.objects.get_or_create(type=ise_state_type, slug="find-rev", name="Finding Reviewers", desc=" The ISE is finding initial reviewers for the document.", order=2)
State.objects.get_or_create(type=ise_state_type, slug="ise-rev", name="In ISE Review", desc="The ISE is actively working on the document.", order=3)
State.objects.get_or_create(type=ise_state_type, slug="need-res", name="Response to Review Needed", desc=" One or more reviews have been sent to the author, and the ISE is awaiting response.", order=4)
State.objects.get_or_create(type=ise_state_type, slug="iesg-rev", name="In IESG Review", desc="The ISE has asked the IESG to do a review of the document, as described in RFC5742.", order=5)
State.objects.get_or_create(type=ise_state_type, slug="rfc-edit", name="Sent to the RFC Editor", desc="The ISE processing of this document is complete and it has been sent to the RFC Editor for publication. The document may be in the RFC Editor's queue, or it may have been published as an RFC; this state doesn't distinguish between different states occurring after the document has left the ISE.", order=6)
State.objects.get_or_create(type=ise_state_type, slug="pub", name="Published RFC", desc="The document has been published as an RFC.", order=7)
State.objects.get_or_create(type=ise_state_type, slug="dead", name="No Longer In Independent Submission Stream", desc="This document was actively considered in the Independent Submission stream, but the ISE chose not to publish it.  It is possible that the document might be revived later. A document in this state may have a comment explaining the reasoning of the ISE (such as if the document was going to move to a different stream).", order=8)
State.objects.get_or_create(type=ise_state_type, slug="iesghold", name="Document on Hold Based On IESG Request", desc="The IESG has requested that the document be held pending further review, as specified in RFC 5742, and the ISE has agreed to such a hold.", order=9)

# now import the next_states; we only go for the default ones, the
# WG-specific are handled in the group importer

workflows = [(ietf_state_type, workflows.models.Workflow.objects.get(name="Default WG Workflow")),
             (irtf_state_type, workflows.models.Workflow.objects.get(name="IRTF Workflow")),
             (ise_state_type, workflows.models.Workflow.objects.get(name="ISE Workflow")),
             (iab_state_type, workflows.models.Workflow.objects.get(name="IAB Workflow")),
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
