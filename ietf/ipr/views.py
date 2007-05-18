import re
import models
import ietf.utils
import django.newforms as forms
from django.shortcuts import render_to_response as render
from django.utils.html import escape, linebreaks
from ietf.contrib.form_decorator import form_decorator
from ietf.utils import log as log

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

section_table = {
                "index":    {   "index": True   },
                "specific": {   "index": False, "title": True,
                                "legacy_intro": False, "new_intro": True,  "form_intro": False,
                                "holder": True, "holder_contact": True, "ietf_contact": True,
                                "ietf_doc": True, "patent_info": True, "licensing": True,
                                "submitter": True, "notes": True, "form_submit": False,
                            },
                "generic": {   "index": False, "title": True,
                                "legacy_intro": False, "new_intro": True,  "form_intro": False,
                                "holder": True, "holder_contact": True, "ietf_contact": False,
                                "ietf_doc": False, "patent_info": True, "licensing": True,
                                "submitter": True, "notes": True, "form_submit": False,
                            },
                "third_party": {"index": False, "title": True,
                                "legacy_intro": False, "new_intro": True,  "form_intro": False,
                                "holder": True, "holder_contact": False, "ietf_contact": True,
                                "ietf_doc": True, "patent_info": True, "licensing": False,
                                "submitter": False, "notes": False, "form_submit": False,
                            },
                "legacy":   {   "index": False, "title": True,
                                "legacy_intro": True, "new_intro": False,  "form_intro": False,
                                "holder": True, "holder_contact": True, "ietf_contact": False,
                                "ietf_doc": True, "patent_info": False, "licensing": False,
                                "submitter": False, "notes": False, "form_submit": False,
                            },
            }

def show(request, ipr_id=None):
    """Show a specific IPR disclosure"""
    assert ipr_id != None
    ipr = models.IprDetail.objects.filter(ipr_id=ipr_id)[0]
    ipr.disclosure_type = get_disclosure_type(ipr)
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
            raise KeyError("Unexpected contact_type in ipr_contacts: ipr_id=%s" % ipr.ipr_id)
    # do escaping and line-breaking here instead of in the template,
    # so that we can use the template for the form display, too.
    ipr.p_notes = linebreaks(escape(ipr.p_notes))
    ipr.discloser_identify = linebreaks(escape(ipr.discloser_identify))
    ipr.comments = linebreaks(escape(ipr.comments))
    ipr.other_notes = linebreaks(escape(ipr.other_notes))
    ipr.licensing_option = dict(models.LICENSE_CHOICES)[ipr.licensing_option]
    ipr.selecttype = dict(models.SELECT_CHOICES)[ipr.selecttype]
    if ipr.selectowned:
        ipr.selectowned = dict(models.SELECT_CHOICES)[ipr.selectowned]
    return render("ipr/details.html",  {"ipr": ipr, "section_list": section_list})

def update(request, ipr_id=None):
    """Update a specific IPR disclosure"""
    # TODO: replace the placeholder code with the appropriate update code
    return show(request, ipr_id)

def new(request, type):
    """Make a new IPR disclosure"""
    debug = ""

    # define callback methods for special field cases.
    def ipr_detail_form_callback(field, **kwargs):
        if field.name == "licensing_option":
            return forms.IntegerField(widget=forms.RadioSelect(choices=models.LICENSE_CHOICES))
        if field.name in ["selecttype", "selectowned"]:
            return forms.IntegerField(widget=forms.RadioSelect(choices=((1, "YES"), (2, "NO"))))
        return field.formfield(**kwargs)

    def ipr_contact_form_callback(field, **kwargs):
        phone_re = re.compile(r'^\+?[0-9 ]*(\([0-9]+\))?[0-9 -]+$')
        error_message = """Phone numbers may have a leading "+", and otherwise only contain
                    numbers [0-9]; dash, period or space; parentheses, and an optional
                    extension number indicated by 'x'. """

        if field.name == "telephone":
            return forms.RegexField(phone_re, error_message=error_message, **kwargs)
        if field.name == "fax":
            return forms.RegexField(phone_re, error_message=error_message, required=False, **kwargs)
        return field.formfield(**kwargs)

    # Get a form class which renders fields using a given template
    CustomForm = ietf.utils.makeFormattingForm(template="ipr/formfield.html")

    # Get base form classes for our models
    BaseIprForm = forms.form_for_model(models.IprDetail, form=CustomForm, formfield_callback=ipr_detail_form_callback)
    BaseContactForm = forms.form_for_model(models.IprContact, form=CustomForm, formfield_callback=ipr_contact_form_callback)

    section_list = section_table[type]
    section_list.update({"title":False, "new_intro":False, "form_intro":True, "form_submit":True, })

    # Some subclassing:

    # The contact form will be part of the IprForm, so it needs a widget.
    # Define one.
    class MultiformWidget(forms.Widget):
       def value_from_datadict(self, data, name):
           return data
       
    class ContactForm(BaseContactForm):
        widget = MultiformWidget()

        def add_prefix(self, field_name):
            return self.prefix and ('%s_%s' % (self.prefix, field_name)) or field_name
        def clean(self, *value):
            if value:
                return self.full_clean()
            else:
                return self.clean_data

    class IprForm(BaseIprForm):
        holder_contact = None
        rfclist = forms.CharField(required=False)
        draftlist = forms.CharField(required=False)
        stdonly_license = forms.BooleanField(required=False)
        ietf_contact_is_submitter = forms.BooleanField(required=False)
        if "holder_contact" in section_list:
            holder_contact = ContactForm(prefix="hold")
        if "ietf_contact" in section_list:
            ietf_contact = ContactForm(prefix="ietf")
        if "submitter" in section_list:
            submitter = ContactForm(prefix="subm")
        def __init__(self, *args, **kw):
            for contact in ["holder_contact", "ietf_contact", "submitter"]:
                if contact in section_list:
                    self.base_fields[contact] = ContactForm(prefix=contact[:4], *args, **kw)
            self.base_fields["ietf_contact_is_submitter"] = forms.BooleanField(required=False)
            BaseIprForm.__init__(self, *args, **kw)
        # Special validation code
        def clean(self):
            # Required:
            # Submitter form filled in or 'same-as-ietf-contact' marked
            # Only one of rfc, draft, and other info fields filled in
            # RFC exists or draft exists and has right rev. or ...
            if self.ietf_contact_is_submitter:
                self.submitter = self.ietf_contact
            pass

    if request.method == 'POST':
        data = request.POST.copy()
        if "ietf_contact_is_submitter" in data:
            for subfield in ["name", "title", "department", "address1", "address2", "telephone", "fax", "email"]:
                log("Fixing subfield subm_%s ..."%subfield)
                try:
                    data["subm_%s"%subfield] = data["ietf_%s"%subfield]
                    log("Set to %s"%data["ietf_%s"%subfield])
                except Exception, e:
                    log("Caught exception: %s"%e)
                    pass
        form = IprForm(data)
        if form.ietf_contact_is_submitter:
            form.ietf_contact_is_submitter_checked = "checked"
        if form.is_valid():
            #instance = form.save()
            #return HttpResponseRedirect("/ipr/ipr-%s" % instance.ipr_id)
            return HttpResponseRedirect("/ipr/")
        else:
            # Fall through, and let the partially bound form, with error
            # indications, be rendered again.
            pass
    else:
        form = IprForm()
        form.unbound_form = True

    # ietf.utils.log(dir(form.ietf_contact_is_submitter))
    return render("ipr/details.html", {"ipr": form, "section_list":section_list, "debug": debug})



# ---- Helper functions ------------------------------------------------------

def get_disclosure_type(ipr):
    if   ipr.generic:
        assert not ipr.third_party
        return "Generic"
    elif ipr.third_party:
        return "Third Party"
    else:
        return "Specific"
    
def get_section_list(ipr):
    if   ipr.old_ipr_url:
        return section_table["legacy"]
    elif ipr.generic:
        assert not ipr.third_party
        return section_table["generic"]
    elif ipr.third_party:
        return section_table["third_party"]
    else:
        return section_table["specific"]
