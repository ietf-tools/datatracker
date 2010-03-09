# Copyright The IETF Trust 2007, All Rights Reserved

from django.shortcuts import render_to_response as render, get_object_or_404
from django.template import RequestContext
from django.template.loader import render_to_string
from django.http import HttpResponse, Http404
from django.conf import settings
from ietf.idtracker.models import IETFWG
from ietf.ipr.models import IprDetail, SELECT_CHOICES, LICENSE_CHOICES
from ietf.ipr.view_sections import section_table
from ietf.utils import log
import os


def default(request):
    """Default page, with links to sub-pages"""
    return render("ipr/disclosure.html", {}, context_instance=RequestContext(request))

def showlist(request):
    """Display a list of existing disclosures"""
    return list_all(request, 'ipr/list.html')

def updatelist(request):
    """Display a list of existing disclosures, with links to update forms"""
    return list_all(request, 'ipr/update_list.html')

def list_all(request, template):
    """Display a list of existing disclosures, using the provided template"""    
    disclosures = IprDetail.objects.all()
    generic_disclosures  = disclosures.filter(status__in=[1,3], generic=1)    
    specific_disclosures = disclosures.filter(status__in=[1,3], generic=0, third_party=0)
    thirdpty_disclosures = disclosures.filter(status__in=[1,3], generic=0, third_party=1)
    
    return render(template,
        {
            'generic_disclosures' : generic_disclosures.order_by(* ['-submitted_date', ] ),
            'specific_disclosures': specific_disclosures.order_by(* ['-submitted_date', ] ),
            'thirdpty_disclosures': thirdpty_disclosures.order_by(* ['-submitted_date', ] ),
        }, context_instance=RequestContext(request) )

def list_drafts(request):
    iprs = IprDetail.objects.filter(status=1)
    docipr = {}
    docs = []
    for ipr in iprs:
        for draft in ipr.drafts.all():
            name = draft.document.filename
            if not name in docipr:
                docipr[name] = []
            docipr[name] += [ ipr.ipr_id ]
        for rfc in ipr.rfcs.all():
            name = "RFC%04d" % rfc.document.rfc_number
            if not name in docipr:
                docipr[name] = []
            docipr[name] += [ ipr.ipr_id ]
    docs = [ {"name":key, "iprs":value, } for key,value in docipr.items() ]
    return HttpResponse(render_to_string("ipr/drafts.html", { "docs":docs, },
                    context_instance=RequestContext(request)),
                    mimetype="text/plain")

# Details views

def show(request, ipr_id=None, removed=None):
    """Show a specific IPR disclosure"""
    assert ipr_id != None
    ipr = get_object_or_404(IprDetail, ipr_id=ipr_id)
    if ipr.status == 3 and not removed:
	return render("ipr/removed.html",  {"ipr": ipr},
			context_instance=RequestContext(request))
    if removed and ipr.status != 3:
	raise Http404
    if not ipr.status == 1 and not removed:
	raise Http404        
    section_list = get_section_list(ipr)
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
            text = text[cut:] + "."
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
    return render("ipr/details.html",  {"ipr": ipr, "section_list": section_list},
                    context_instance=RequestContext(request))



def form(request):
    wgs = IETFWG.objects.filter(group_type__group_type_id=1).exclude(group_acronym__acronym='2000').select_related().order_by('acronym.acronym')
    log("Search form")
    return render("ipr/search.html", {"wgs": wgs}, context_instance=RequestContext(request))
        


# ---- Helper functions ------------------------------------------------------

def get_section_list(ipr):
    if   ipr.legacy_url_0:
        return section_table["legacy"]
    elif ipr.generic:
        #assert not ipr.third_party
        return section_table["generic"]
    elif ipr.third_party:
        return section_table["third-party"]
    else:
        return section_table["specific"]
