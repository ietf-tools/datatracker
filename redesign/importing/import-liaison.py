#!/usr/bin/python

import sys, os, re, datetime, pytz

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path = [ basedir ] + sys.path

from ietf import settings
settings.USE_DB_REDESIGN_PROXY_CLASSES = False
settings.IMPORTING_FROM_OLD_SCHEMA = True

from django.core import management
management.setup_environ(settings)

from django.template.defaultfilters import slugify

from ietf.idtracker.models import Acronym, EmailAddress
from ietf.liaisons.models import *
from ietf.doc.models import Document, DocAlias
from ietf.person.models import *
from redesign.importing.utils import old_person_to_person, make_revision_event
from ietf.name.models import *
from ietf.name.utils import name


# imports LiaisonDetail, OutgoingLiaisonApproval, Uploads

# todo: LiaisonStatementManager, LiaisonManagers, SDOAuthorizedIndividual

# assumptions:
#  - persons have been imported
#  - groups have been imported

purpose_mapping = {
    1: name(LiaisonStatementPurposeName, "action", "For action", order=1),
    2: name(LiaisonStatementPurposeName, "comment", "For comment", order=2),
    3: name(LiaisonStatementPurposeName, "info", "For information", order=3),
    4: name(LiaisonStatementPurposeName, "response", "In response", order=4),
    # we drop the "other" category here, it was virtuall unused in the old schema
    }

liaison_attachment_doctype = name(DocTypeName, "liai-att", "Liaison Attachment")

purpose_mapping[None] = purpose_mapping[0] = purpose_mapping[3] # map unknown to "For information"
purpose_mapping[5] = purpose_mapping[3] # "Other" is mapped to "For information" as default

system_email = Email.objects.get(person__name="(System)")
system_person = Person.objects.get(name="(System)")
obviously_bogus_date = datetime.date(1970, 1, 1)

bodies = {
    'IESG': Group.objects.get(acronym="iesg"),
    'IETF': Group.objects.get(acronym="ietf"),
    'IETF IESG': Group.objects.get(acronym="iesg"),
    'The IETF': Group.objects.get(acronym="ietf"),
    'IAB/ISOC': Group.objects.get(acronym="iab"),
    'ISOC/IAB': Group.objects.get(acronym="iab"),
    'IAB/IESG': Group.objects.get(acronym="iab"),
    'IAB': Group.objects.get(acronym="iab"),
    'IETF IAB': Group.objects.get(acronym="iab"),
    'IETF Transport Directorate': Group.objects.get(acronym="tsvdir"),
    'Sigtran': Group.objects.get(acronym="sigtran", type="wg"),
    'IETF RAI WG': Group.objects.get(acronym="rai", type="area"),
    'IETF RAI': Group.objects.get(acronym="rai", type="area"),
    'IETF Mobile IP WG': Group.objects.get(acronym="mobileip", type="wg"),
    "IETF Operations and Management Area": Group.objects.get(acronym="ops", type="area"),
    "IETF/Operations and Management Area": Group.objects.get(acronym="ops", type="area"),
    "IETF OAM Area": Group.objects.get(acronym="ops", type="area"),
    "IETF O&M Area": Group.objects.get(acronym="ops", type="area"),
    "IETF O&M area": Group.objects.get(acronym="ops", type="area"),
    "IETF O&M": Group.objects.get(acronym="ops", type="area"),
    "IETF O&M Area Directors": Group.objects.get(acronym="ops", type="area"),
    "PWE3 Working Greoup": Group.objects.get(acronym="pwe3", type="wg"),
    "IETF PWE 3 WG": Group.objects.get(acronym="pwe3", type="wg"),
    "IETF/Routing Area": Group.objects.get(acronym="rtg", type="area"),
    "IRTF Internet Area": Group.objects.get(acronym="int", type="area"),
    "IETF Sub IP Area": Group.objects.get(acronym="sub", type="area"),
    }

def get_body(name, raw_code):
    if raw_code:
        # new tool is storing some group info directly, try decoding it
        b = None
        t = raw_code.split("_")
        if len(t) == 2:
            if t[0] == "area":
                b = lookup_group(acronym=Acronym.objects.get(pk=t[1]).acronym, type="area")
            elif t[0] == "wg":
                b = lookup_group(acronym=Acronym.objects.get(pk=t[1]).acronym, type="wg")
            elif t[0] == "sdo":
                b = lookup_group(name=SDOs.objects.get(pk=t[1]).sdo_name, type="sdo")

        if not b:
            b = lookup_group(acronym=raw_code)

        return b
    
    # the from body name is a nice case study in how inconsistencies
    # build up over time
    name = (name.replace("(", "").replace(")", "").replace(" Chairs", "")
            .replace("Working Group", "WG").replace("working group", "WG"))
    b = bodies.get(name)
    t = name.split()
    if not b and name.startswith("IETF"):
        if len(t) == 1:
            if "-" in name:
                t = name.split("-")
            elif "/" in name:
                t = name.split("/")
            b = lookup_group(acronym=t[1].lower(), type="wg")
        elif len(t) < 3 or t[2].lower() == "wg":
            b = lookup_group(acronym=t[1].lower(), type="wg")
        elif t[2].lower() in ("area", "ad"):
            b = lookup_group(acronym=t[1].lower(), type="area")
            if not b:
                b = lookup_group(name=u"%s %s" % (t[1], t[2]), type="area")

    if not b and name.endswith(" WG"):
        b = lookup_group(acronym=t[-2].lower(), type="wg")
                
    if not b:
        b = lookup_group(name=name, type="sdo")

    return b

for o in LiaisonDetail.objects.all().order_by("pk"):
    print "importing LiaisonDetail", o.pk

    try:
        l = LiaisonStatement.objects.get(pk=o.pk)
    except LiaisonStatement.DoesNotExist:
        l = LiaisonStatement(pk=o.pk)

    l.title = (o.title or "").strip()
    l.purpose = purpose_mapping[o.purpose_id]
    if o.purpose_text and not o.purpose and "action" in o.purpose_text.lower():
        o.purpose = purpose_mapping[1]
    l.body = (o.body or "").strip()
    l.deadline = o.deadline_date

    l.related_to_id = o.related_to_id # should not dangle as we process ids in turn

    def lookup_group(**kwargs):
        try:
            return Group.objects.get(**kwargs)
        except Group.DoesNotExist:
            return None

    l.from_name = o.from_body().strip()
    l.from_group = get_body(l.from_name, o.from_raw_code) # try to establish link
    if not o.person:
        l.from_contact = None
    else:
        try:
            l.from_contact = Email.objects.get(address__iexact=o.from_email().address)
        except EmailAddress.DoesNotExist:
            l.from_contact = old_person_to_person(o.person).email_set.order_by('-active')[0]

    if o.by_secretariat:
        l.to_name = o.submitter_name
        if o.submitter_email:
            l.to_name += " <%s>" % o.submitter_email
    else:
        l.to_name = o.to_body
    l.to_name = l.to_name.strip()
    l.to_group = get_body(l.to_name, o.to_raw_code) # try to establish link
    l.to_contact = (o.to_poc or "").strip()

    l.reply_to = (o.replyto or "").strip()

    l.response_contact = (o.response_contact or "").strip()
    l.technical_contact = (o.technical_contact or "").strip()
    l.cc = (o.cc1 or "").strip()
    
    l.submitted = o.submitted_date
    l.modified = o.last_modified_date
    if not l.modified and l.submitted:
        l.modified = l.submitted
    if not o.approval:
        # no approval object means it's approved alright - weird, we
        # have to fake the approved date then
        l.approved = l.modified or l.submitted or datetime.datetime.now()
    else:
        l.approved = o.approval.approval_date if o.approval.approved else None

    l.action_taken = o.action_taken
    
    l.save()

    l.attachments.all().delete()
    for i, u in enumerate(o.uploads_set.order_by("pk")):
        attachment = Document()
        attachment.title = u.file_title
        attachment.type = liaison_attachment_doctype
        attachment.name = l.name() + ("-attachment-%s" % (i + 1))
        attachment.time = l.submitted
        # we should fixup the filenames, but meanwhile, store it here
        attachment.external_url = "file%s%s" % (u.file_id, u.file_extension)
        attachment.save()

        DocAlias.objects.get_or_create(document=attachment, name=attachment.name)

        e = make_revision_event(attachment, system_person)
        if l.from_contact and l.from_contact.person:
            e.by = l.from_contact.person
            print e.by
        e.save()

        l.attachments.add(attachment)
        
    
