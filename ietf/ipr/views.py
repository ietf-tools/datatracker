# Copyright The IETF Trust 2007, All Rights Reserved

import os

from django.shortcuts import render_to_response as render, get_object_or_404
from django.template import RequestContext
from django.template.loader import render_to_string
from django.http import HttpResponse, Http404
from django.conf import settings

from ietf.ipr.models import IprDetail, IprDocAlias, SELECT_CHOICES, LICENSE_CHOICES
from ietf.ipr.view_sections import section_list_for_ipr
from ietf.doc.models import Document

def about(request):
    return render("ipr/disclosure.html", {}, context_instance=RequestContext(request))

def showlist(request):
    disclosures = IprDetail.objects.all()
    generic_disclosures  = disclosures.filter(status__in=[1,3], generic=1)    
    specific_disclosures = disclosures.filter(status__in=[1,3], generic=0, third_party=0)
    thirdpty_disclosures = disclosures.filter(status__in=[1,3], generic=0, third_party=1)
    
    return render("ipr/list.html",
        {
            'generic_disclosures' : generic_disclosures.order_by(* ['-submitted_date', ] ),
            'specific_disclosures': specific_disclosures.order_by(* ['-submitted_date', ] ),
            'thirdpty_disclosures': thirdpty_disclosures.order_by(* ['-submitted_date', ] ),
        }, context_instance=RequestContext(request) )

def show(request, ipr_id=None, removed=None):
    """Show a specific IPR disclosure"""
    assert ipr_id != None
    ipr = get_object_or_404(IprDetail, ipr_id=ipr_id)
    if ipr.status == 3 and not removed:
	return render("ipr/removed.html",  {"ipr": ipr},
			context_instance=RequestContext(request))
    if removed and ipr.status != 3:
	raise Http404
    if ipr.status != 1 and not removed:
	raise Http404        
    section_list = section_list_for_ipr(ipr)
    contacts = ipr.contact.all()
    for contact in contacts:
        if   contact.contact_type == 1:
            ipr.holder_contact = contact
        elif contact.contact_type == 2:
            ipr.ietf_contact = contact
        elif contact.contact_type == 3:
            ipr.submitter = contact
        else:
            raise KeyError("Unexpected contact_type (%s) in ipr_contacts for ipr_id=%s" % (contact.contact_type, ipr.ipr_id))

    if ipr.licensing_option:
        text = dict(LICENSE_CHOICES)[ipr.licensing_option]
        # Very hacky way to get rid of the last part of option 'd':
        cut = text.find(" (")
        if cut > 0:
            text = text[:cut] + "."
        # get rid of the "a) ", "b) ", etc. 
        ipr.licensing_option = text[3:]
    if ipr.is_pending:
        ipr.is_pending = dict(SELECT_CHOICES)[ipr.is_pending]
    if ipr.applies_to_all:
        ipr.applies_to_all = dict(SELECT_CHOICES)[ipr.applies_to_all]
    if ipr.legacy_url_0 and ipr.legacy_url_0.startswith("http://www.ietf.org/") and not ipr.legacy_url_0.endswith((".pdf",".doc",".html")):
        try:
            file = open(os.path.join(settings.IPR_DOCUMENT_PATH, os.path.basename(ipr.legacy_url_0)))
            ipr.legacy_text = file.read().decode("latin-1")
            file.close()
        except:
            # if file does not exist, iframe is used instead
            pass

    iprdocs = IprDocAlias.objects.filter(ipr=ipr).order_by("id").select_related("doc_alias", "doc_alias__document")

    ipr.drafts = [x for x in iprdocs if not x.doc_alias.name.startswith("rfc")]
    ipr.rfcs = [x for x in iprdocs if x.doc_alias.name.startswith("rfc")]
    
    return render("ipr/details.html",  {"ipr": ipr, "section_list": section_list},
                    context_instance=RequestContext(request))

def iprs_for_drafts_txt(request):
    docipr = {}

    for o in IprDocAlias.objects.filter(ipr__status=1).select_related("doc_alias"):
        name = o.doc_alias.name
        if name.startswith("rfc"):
            name = name.upper()

        if not name in docipr:
            docipr[name] = []

        docipr[name].append(o.ipr_id)
            
    lines = [ u"# Machine-readable list of IPR disclosures by draft name" ]
    for name, iprs in docipr.iteritems():
        lines.append(name + "\t" + "\t".join(unicode(ipr_id) for ipr_id in sorted(iprs)))

    return HttpResponse("\n".join(lines), mimetype="text/plain")

