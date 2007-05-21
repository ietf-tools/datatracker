import re
import models
import ietf.utils
import django.utils.html
import django.newforms as forms
from django.shortcuts import render_to_response as render
from ietf.utils import log
from ietf.ipr.view_sections import section_table

# ----------------------------------------------------------------
# Callback methods for special field cases.
# ----------------------------------------------------------------

def ipr_detail_form_callback(field, **kwargs):
    if field.name == "licensing_option":
        return forms.IntegerField(widget=forms.RadioSelect(choices=models.LICENSE_CHOICES), required=True)
    if field.name in ["selecttype", "selectowned"]:
        return forms.IntegerField(widget=forms.RadioSelect(choices=((1, "YES"), (2, "NO"))), required=False)
    if field.name in ["rfc_number", "id_document_tag"]:
        log(field.name)
        return forms.CharFieldField(required=False)
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
    # TODO:
    #   Add rfc existence validation for RFC field
    #   Add draft existence validation for Drafts field

# ----------------------------------------------------------------
# Classes
# ----------------------------------------------------------------    

# Get a form class which renders fields using a given template
CustomForm = ietf.utils.makeFormattingForm(template="ipr/formfield.html")

# Get base form classes for our models
BaseIprForm = forms.form_for_model(models.IprDetail, form=CustomForm, formfield_callback=ipr_detail_form_callback)
BaseContactForm = forms.form_for_model(models.IprContact, form=CustomForm, formfield_callback=ipr_contact_form_callback)

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


# ----------------------------------------------------------------
# Form processing
# ----------------------------------------------------------------

def new(request, type):
    """Make a new IPR disclosure.

    This is a big function -- maybe too big.  Things would be easier if we didn't have
    one form containing fields from 4 tables -- don't build something like this again...

    """
    debug = ""

    section_list = section_table[type].copy()
    section_list.update({"title":False, "new_intro":False, "form_intro":True,
        "form_submit":True, "form_legend": True, })

    class IprForm(BaseIprForm):
        holder_contact = None
        rfclist = forms.CharField(required=False)
        draftlist = forms.CharField(required=False)
        stdonly_license = forms.BooleanField(required=False)
        hold_contact_is_submitter = forms.BooleanField(required=False)
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
            self.base_fields["rfclist"] = forms.CharField(required=False)
            self.base_fields["draftlist"] = forms.CharField(required=False)
            if "holder_contact" in section_list:
                self.base_fields["hold_contact_is_submitter"] = forms.BooleanField(required=False)
            if "ietf_contact" in section_list:
                self.base_fields["ietf_contact_is_submitter"] = forms.BooleanField(required=False)
            self.base_fields["stdonly_license"] = forms.BooleanField(required=False)

            BaseIprForm.__init__(self, *args, **kw)
        # Special validation code
        def clean(self):
            # Required:
            # Submitter form filled in or 'same-as-ietf-contact' marked
            # Only one of rfc, draft, and other info fields filled in
            # RFC exists or draft exists and has right rev. or ...
            pass

    if request.method == 'POST':
        data = request.POST.copy()
        for src in ["hold", "ietf"]:
            if "%s_contact_is_submitter" % src in data:
                for subfield in ["name", "title", "department", "address1", "address2", "telephone", "fax", "email"]:
                    try:
                        data[ "subm_%s" % subfield ] = data[ "%s_%s" % (src,subfield) ]
                    except Exception, e:
                        #log("Caught exception: %s"%e)
                        pass
        form = IprForm(data)
        if form.ietf_contact_is_submitter:
            form.ietf_contact_is_submitter_checked = "checked"
        if form.is_valid():
            #instance = form.save()
            #return HttpResponseRedirect("/ipr/ipr-%s" % instance.ipr_id)
            #return HttpResponseRedirect("/ipr/")
        
            pass
        else:
            for error in form.errors:
                log("Form error for field: %s"%error)
            # Fall through, and let the partially bound form, with error
            # indications, be rendered again.
            pass
    else:
        form = IprForm()
        form.unbound_form = True

    # ietf.utils.log(dir(form.ietf_contact_is_submitter))
    return render("ipr/details.html", {"ipr": form, "section_list":section_list, "debug": debug})
