# Copyright The IETF Trust 2025, All Rights Reserved

from django.db import migrations

def forward(apps, schema_editor):
    State = apps.get_model("doc","State")
    for name, desc in [
        ("WG Document","The document has been adopted by the Working Group (WG) and is under development.  A document can only be adopted by one WG at a time.  However, a document may be transferred between WGs."),
        ("Parked WG Document","The Working Group (WG) document is in a temporary state where it will not be actively developed.  The reason for the pause is explained via a datatracker comments section."),
        ("Dead WG Document","The Working Group (WG) document has been abandoned by the WG.  No further development is planned in this WG.  A decision to resume work on this document and move it out of this state is possible."),
        ("In WG Last Call","The Working Group (WG) document is currently subject to an active WG Last Call (WGLC) review per Section 7.4 of RFC2418."),
        ("Waiting for Implementation","The progression of this Working Group (WG) document towards publication is paused as it awaits implementation. The process governing the approach to implementations is WG-specific."),
        ("Held by WG","Held by Working Group (WG) chairs for administrative reasons.  See document history for details."),
        ("Waiting for WG Chair Go-Ahead","The Working Group (WG) document has completed Working Group Last Call (WGLC), but the WG chair(s) are not yet ready to call consensus on the document. The reasons for this may include comments from the WGLC need to be responded to, or a revision to the document is needed"),
        ("WG Consensus: Waiting for Write-Up","The Working Group (WG) document has consensus to proceed to publication.  However, the document is waiting for a document shepherd write-up per RFC4858."),
        ("Submitted to IESG for Publication","The Working Group (WG) document has left the WG and been submitted to the Internet Engineering Steering Group (IESG) for evaluation and publication.  See the “IESG State” or “RFC Editor State” for further details on the state of the document."),
        ("Candidate for WG Adoption","The individual submission document has been marked by the Working Group (WG) chairs as a candidate for adoption by the WG, but no adoption call has been started."),
        ("Call For Adoption By WG Issued","A call for adoption of the individual submission document has been issued by the Working Group (WG) chairs.  This call is still running but the WG has not yet reached consensus for adoption."),
        ("Adopted by a WG","The individual submission document has been adopted by the Working Group (WG), but a WG document replacing this document with the typical naming convention of 'draft- ietf-wgname-topic-nn' has not yet been submitted."),
        ("Adopted for WG Info Only","The document is adopted by the Working Group (WG) for its internal use.  The WG has decided that it will not pursue publication of it as an RFC."),
    ]:
        State.objects.filter(name=name).update(desc=desc)

def reverse(apps, schema_editor):
    State = apps.get_model("doc","State")
    for name, desc in [
       ("WG Document","""<a href="https://www.rfc-editor.org/rfc/rfc6174.html#section-4.2.4" target="_blank">4.2.4. WG Document</a>

 The "WG Document" state describes an I-D that has been adopted by an IETF WG and is being actively developed.

 A WG Chair may transition an I-D into the "WG Document" state at any time as long as the I-D is not being considered or developed in any other WG.

 Alternatively, WG Chairs may rely upon new functionality to be added to the Datatracker to automatically move version-00 drafts into the "WG Document" state as described in Section 4.1.

 Under normal conditions, it should not be possible for an I-D to be in the "WG Document" state in more than one WG at a time. This said, I-Ds may be transferred from one WG to another with the consent of the WG Chairs and the responsible ADs."""),
        ("Parked WG Document","""<a href="https://www.rfc-editor.org/rfc/rfc6174.html#section-4.2.5" target="_blank">4.2.5. Parked WG Document</a>

 A "Parked WG Document" is an I-D that has lost its author or editor, is waiting for another document to be written or for a review to be completed, or cannot be progressed by the working group for some other reason.

 Some of the annotation tags described in Section 4.3 may be used in conjunction with this state to indicate why an I-D has been parked, and/or what may need to happen for the I-D to be un-parked.

 Parking a WG draft will not prevent it from expiring; however, this state can be used to indicate why the I-D has stopped progressing in the WG.

 A "Parked WG Document" that is not expired may be transferred from one WG to another with the consent of the WG Chairs and the responsible ADs."""),
        ("Dead WG Document","""<a href="https://www.rfc-editor.org/rfc/rfc6174.html#section-4.2.6" target="_blank">4.2.6. Dead WG Document</a>

 A "Dead WG Document" is an I-D that has been abandoned. Note that 'Dead' is not always a final state for a WG I-D. If consensus is subsequently achieved, a "Dead WG Document" may be resurrected. A "Dead WG Document" that is not resurrected will eventually expire.

 Note that an I-D that is declared to be "Dead" in one WG and that is not expired may be transferred to a non-dead state in another WG with the consent of the WG Chairs and the responsible ADs."""),
        ("In WG Last Call","""<a href="https://www.rfc-editor.org/rfc/rfc6174.html#section-4.2.7" target="_blank">4.2.7. In WG Last Call</a>

 A document "In WG Last Call" is an I-D for which a WG Last Call (WGLC) has been issued and is in progress.

 Note that conducting a WGLC is an optional part of the IETF WG process, per Section 7.4 of RFC 2418 [RFC2418].

 If a WG Chair decides to conduct a WGLC on an I-D, the "In WG Last Call" state can be used to track the progress of the WGLC. The Chair may configure the Datatracker to send a WGLC message to one or more mailing lists when the Chair moves the I-D into this state. The WG Chair may also be able to select a different set of mailing lists for a different document undergoing a WGLC; some documents may deserve coordination with other WGs.

 A WG I-D in this state should remain "In WG Last Call" until the WG Chair moves it to another state. The WG Chair may configure the Datatracker to send an e-mail after a specified period of time to remind or 'nudge' the Chair to conclude the WGLC and to determine the next state for the document.

 It is possible for one WGLC to lead into another WGLC for the same document. For example, an I-D that completed a WGLC as an "Informational" document may need another WGLC if a decision is taken to convert the I-D into a Standards Track document."""),
        ("Waiting for Implementation","""In some areas, it can be desirable to wait for multiple interoperable implementations before progressing a draft to be an RFC, and in some WGs this is required.  This state should be entered after WG Last Call has completed."""),
        ("Held by WG","""Held by WG, see document history for details."""),
        ("Waiting for WG Chair Go-Ahead","""<a href="https://www.rfc-editor.org/rfc/rfc6174.html#section-4.2.8" target="_blank">4.2.8. Waiting for WG Chair Go-Ahead</a>

 A WG Chair may wish to place an I-D that receives a lot of comments during a WGLC into the "Waiting for WG Chair Go-Ahead" state. This state describes an I-D that has undergone a WGLC; however, the Chair is not yet ready to call consensus on the document.

 If comments from the WGLC need to be responded to, or a revision to the I-D is needed, the Chair may place an I-D into this state until all of the WGLC comments are adequately addressed and the (possibly revised) document is in the I-D repository."""),
        ("WG Consensus: Waiting for Write-Up","""<a href="https://www.rfc-editor.org/rfc/rfc6174.html#section-4.2.9" target="_blank">4.2.9. WG Consensus: Waiting for Writeup</a>

 A document in the "WG Consensus: Waiting for Writeup" state has essentially completed its development within the working group, and is nearly ready to be sent to the IESG for publication. The last thing to be done is the preparation of a protocol writeup by a Document Shepherd. The IESG requires that a document shepherd writeup be completed before publication of the I-D is requested. The IETF document shepherding process and the role of a WG Document Shepherd is described in RFC 4858 [RFC4858]

 A WG Chair may call consensus on an I-D without a formal WGLC and transition an I-D that was in the "WG Document" state directly into this state.

 The name of this state includes the words "Waiting for Writeup" because a good document shepherd writeup takes time to prepare."""),
        ("Submitted to IESG for Publication","""<a href="https://www.rfc-editor.org/rfc/rfc6174.html#section-4.2.10" target="_blank">4.2.10. Submitted to IESG for Publication</a>

 This state describes a WG document that has been submitted to the IESG for publication and that has not been sent back to the working group for revision.

 An I-D in this state may be under review by the IESG, it may have been approved and be in the RFC Editor's queue, or it may have been published as an RFC. Other possibilities exist too. The document may be "Dead" (in the IESG state machine) or in a "Do Not Publish" state."""),
        ("Candidate for WG Adoption","""The document has been marked as a candidate for WG adoption by the WG Chair.  This state can be used before a call for adoption is issued (and the document is put in the "Call For Adoption By WG Issued" state), to indicate that the document is in the queue for a call for adoption, even if none has been issued yet."""),
        ("Call For Adoption By WG Issued","""<a href="https://www.rfc-editor.org/rfc/rfc6174.html#section-4.2.1" target="_blank">4.2.1. Call for Adoption by WG Issued</a>

 The "Call for Adoption by WG Issued" state should be used to indicate when an I-D is being considered for adoption by an IETF WG. An I-D that is in this state is actively being considered for adoption and has not yet achieved consensus, preference, or selection in the WG.

 This state may be used to describe an I-D that someone has asked a WG to consider for adoption, if the WG Chair has agreed with the request. This state may also be used to identify an I-D that a WG Chair asked an author to write specifically for consideration as a candidate WG item [WGDTSPEC], and/or an I-D that is listed as a 'candidate draft' in the WG's charter.

 Under normal conditions, it should not be possible for an I-D to be in the "Call for Adoption by WG Issued" state in more than one working group at the same time. This said, it is not uncommon for authors to "shop" their I-Ds to more than one WG at a time, with the hope of getting their documents adopted somewhere.

 After this state is implemented in the Datatracker, an I-D that is in the "Call for Adoption by WG Issued" state will not be able to be "shopped" to any other WG without the consent of the WG Chairs and the responsible ADs impacted by the shopping.

 Note that Figure 1 includes an arc leading from this state to outside of the WG state machine. This illustrates that some I-Ds that are considered do not get adopted as WG drafts. An I-D that is not adopted as a WG draft will transition out of the WG state machine and revert back to having no stream-specific state; however, the status change history log of the I-D will record that the I-D was previously in the "Call for Adoption by WG Issued" state."""),
        ("Adopted by a WG","""<a href="https://www.rfc-editor.org/rfc/rfc6174.html#section-4.2.2" target="_blank">4.2.2. Adopted by a WG</a>

 The "Adopted by a WG" state describes an individual submission I-D that an IETF WG has agreed to adopt as one of its WG drafts.

 WG Chairs who use this state will be able to clearly indicate when their WGs adopt individual submission I-Ds. This will facilitate the Datatracker's ability to correctly capture "Replaces" information for WG drafts and correct "Replaced by" information for individual submission I-Ds that have been replaced by WG drafts.

 This state is needed because the Datatracker uses the filename of an I-D as a key to search its database for status information about the I-D, and because the filename of a WG I-D is supposed to be different from the filename of an individual submission I-D. The filename of an individual submission I-D will typically be formatted as 'draft-author-wgname-topic-nn'.

 The filename of a WG document is supposed to be formatted as 'draft- ietf-wgname-topic-nn'.

 An individual I-D that is adopted by a WG may take weeks or months to be resubmitted by the author as a new (version-00) WG draft. If the "Adopted by a WG" state is not used, the Datatracker has no way to determine that an I-D has been adopted until a new version of the I-D is submitted to the WG by the author and until the I-D is approved for posting by a WG Chair."""),
        ("Adopted for WG Info Only","""<a href="https://www.rfc-editor.org/rfc/rfc6174.html#section-4.2.3" target="_blank">4.2.3. Adopted for WG Info Only</a>

 The "Adopted for WG Info Only" state describes a document that contains useful information for the WG that adopted it, but the document is not intended to be published as an RFC. The WG will not actively develop the contents of the I-D or progress it for publication as an RFC. The only purpose of the I-D is to provide information for internal use by the WG."""),
    ]:
        State.objects.filter(name=name).update(desc=desc)

class Migration(migrations.Migration):

    dependencies = [
        ("doc", "0025_storedobject_storedobject_unique_name_per_store"),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]
