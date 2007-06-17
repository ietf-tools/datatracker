import re
import django.utils.html
from django.shortcuts import render_to_response as render
from django.utils.html import escape
from ietf.idtracker.models import IETFWG, InternetDraft, Rfc
from ietf.ipr.models import IprRfc, IprDraft, IprDetail, SELECT_CHOICES, LICENSE_CHOICES
from ietf.ipr.view_sections import section_table
from ietf.ipr.view_new import new
from ietf.utils import log


def linebreaks(value):
    if value:
        return django.utils.html.linebreaks(value)
    else:
        return value

def default(request):
    """Default page, with links to sub-pages"""
    return render("ipr/disclosure.html", {})

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
        } )

# Details views

def show(request, ipr_id=None):
    """Show a specific IPR disclosure"""
    assert ipr_id != None
    ipr = IprDetail.objects.get(ipr_id=ipr_id)
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
    # do escaping and line-breaking here instead of in the template,
    # so that we can use the template for the form display, too.
    ipr.p_notes = linebreaks(escape(ipr.p_notes))
    ipr.discloser_identify = linebreaks(escape(ipr.discloser_identify))
    ipr.comments = linebreaks(escape(ipr.comments))
    ipr.other_notes = linebreaks(escape(ipr.other_notes))

    if ipr.licensing_option:
        ipr.licensing_option = dict(LICENSE_CHOICES)[ipr.licensing_option]
    if ipr.selecttype:
        ipr.selecttype = dict(SELECT_CHOICES)[ipr.selecttype]
    if ipr.selectowned:
        ipr.selectowned = dict(SELECT_CHOICES)[ipr.selectowned]
    return render("ipr/details.html",  {"ipr": ipr, "section_list": section_list})

def update(request, ipr_id=None):
    """Update a specific IPR disclosure"""
    # TODO: replace the placeholder code with the appropriate update code
    return show(request, ipr_id)


inverse = {
            'updates': 'is_updated_by',
            'is_updated_by': 'updates',
            'obsoletes': 'is_obsoleted_by',
            'is_obsoleted_by': 'obsoletes',
            'replaces': 'is_replaced_by',
            'is_replaced_by': 'replaces',            
            'is_rfc_of': 'is_draft_of',
            'is_draft_of': 'is_rfc_of',
        }

display_relation = {
            'updates':          'that updated',
            'is_updated_by':    'that was updated by',
            'obsoletes':        'that obsoleted',
            'is_obsoleted_by':  'that was obsoleted by',
            'replaces':         'that replaced',
            'is_replaced_by':   'that was replaced by',
            'is_rfc_of':        'which came from',
            'is_draft_of':      'that was published as',
        }

def set_related(obj, rel, target):
    #print obj, rel, target
    # remember only the first relationship we find.
    if not hasattr(obj, "related"):
        obj.related = target
        obj.relation = display_relation[rel]

def set_relation(first, rel, second):
    set_related(first, rel, second)
    set_related(second, inverse[rel], first)

def related_docs(doc, found = []):    
    """Get a list of document related to the given document.
    """
    #print "\nrelated_docs(%s, %s)" % (doc, found) 
    found.append(doc)
    if isinstance(doc, Rfc):
        try:
            item = InternetDraft.objects.get(rfc_number=doc.rfc_number)
            if not item in found:
                set_relation(doc, 'is_rfc_of', item)
                found = related_docs(item, found)
        except InternetDraft.DoesNotExist:
            pass
        for entry in doc.updated_or_obsoleted_by.all():
            item = entry.rfc
            if not item in found:
                action = inverse[entry.action.lower()]
                set_relation(doc, action, item)
                found = related_docs(item, found)
        for entry in doc.updates_or_obsoletes.all():
            item = entry.rfc_acted_on
            if not item in found:
                action = entry.action.lower()
                set_relation(doc, action, item)
                found = related_docs(item, found)
    if isinstance(doc, InternetDraft):
        if doc.replaced_by_id:
            item = doc.replaced_by
            if not item in found:
                set_relation(doc, 'is_replaced_by', item)
                found = related_docs(item, found)
        for item in doc.replaces_set.all():
            if not item in found:
                set_relation(doc, 'replaces', item)
                found = related_docs(item, found)
        if doc.rfc_number:
            item = Rfc.objects.get(rfc_number=doc.rfc_number)
            if not item in found:
                set_relation(doc, 'is_draft_of', item)
                found = related_docs(item, found)
    return found

def search(request, type="", q="", id=""):
    wgs = IETFWG.objects.filter(group_type__group_type_id=1).exclude(group_acronym__acronym='2000').select_related().order_by('acronym.acronym')
    args = request.REQUEST.items()
    if args:
        for key, value in args:
            if key == "option":
                type = value
            if re.match(".*search", key):
                q = value
            if re.match(".*id", key):
                id = value
        if type and q or id:
            log("Got query: type=%s, q=%s, id=%s" % (type, q, id))
            if type in ["document_search", "rfc_search"]:
                if type == "document_search":
                    if q:
                        start = InternetDraft.objects.filter(filename__contains=q)
                    if id:
                        start = InternetDraft.objects.filter(id_document_tag=id)
                if type == "rfc_search":
                    if q:
                        start = Rfc.objects.filter(rfc_number=q)
                if start.count() == 1:
                    first = start[0]
                    # get all related drafts, then search for IPRs on all

                    docs = related_docs(first, [])
                    #docs = get_doclist.get_doclist(first)
                    iprs = []
                    for doc in docs:
                        if isinstance(doc, InternetDraft):
                            disclosures = [ item.ipr for item in IprDraft.objects.filter(document=doc, ipr__status__in=[1,3]) ]
                        elif isinstance(doc, Rfc):
                            disclosures = [ item.ipr for item in IprRfc.objects.filter(document=doc, ipr__status__in=[1,3]) ]
                        else:
                            raise ValueError("Doc type is neither draft nor rfc: %s" % doc)
                        if disclosures:
                            doc.iprs = disclosures
                            iprs += disclosures
                    iprs = list(set(iprs))
                    return render("ipr/search_doc_result.html", {"first": first, "iprs": iprs, "docs": docs})
                elif start.count():
                    return render("ipr/search_doc_list.html", {"docs": start })
                else:
                    raise ValueError("Missing or malformed search parameters, or internal error")
            elif type == "patent_search":
                pass
            elif type == "patent_info_search":
                pass
            elif type == "wg_search":
                pass
            elif type == "title_search":
                pass
            elif type == "ip_title_search":
                pass
            else:
                raise ValueError("Unexpected search type in IPR query: %s" % type)
        return django.http.HttpResponseRedirect(request.path)
    return render("ipr/search.html", {"wgs": wgs})

def form(request):
    wgs = IETFWG.objects.filter(group_type__group_type_id=1).exclude(group_acronym__acronym='2000').select_related().order_by('acronym.acronym')
    log("Search form")
    return render("ipr/search.html", {"wgs": wgs})
        


# ---- Helper functions ------------------------------------------------------

def get_section_list(ipr):
    if   ipr.old_ipr_url:
        return section_table["legacy"]
    elif ipr.generic:
        #assert not ipr.third_party
        return section_table["generic"]
    elif ipr.third_party:
        return section_table["third-party"]
    else:
        return section_table["specific"]
