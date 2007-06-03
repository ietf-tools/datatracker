import models
import django.utils.html
from django.shortcuts import render_to_response as render
from django.utils.html import escape
from ietf.ipr.view_sections import section_table
from ietf.ipr.view_new import new

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
    return list(request, 'ipr/list.html')

def updatelist(request):
    """Display a list of existing disclosures, with links to update forms"""
    return list(request, 'ipr/update_list.html')

def list(request, template):
    """Display a list of existing disclosures, using the provided template"""    
    disclosures = models.IprDetail.objects.all()
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
    ipr = models.IprDetail.objects.filter(ipr_id=ipr_id)[0]
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
        ipr.licensing_option = dict(models.LICENSE_CHOICES)[ipr.licensing_option]
    if ipr.selecttype:
        ipr.selecttype = dict(models.SELECT_CHOICES)[ipr.selecttype]
    if ipr.selectowned:
        ipr.selectowned = dict(models.SELECT_CHOICES)[ipr.selectowned]
    return render("ipr/details.html",  {"ipr": ipr, "section_list": section_list})

def update(request, ipr_id=None):
    """Update a specific IPR disclosure"""
    # TODO: replace the placeholder code with the appropriate update code
    return show(request, ipr_id)



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
