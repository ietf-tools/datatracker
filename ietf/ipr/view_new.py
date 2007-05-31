import re
import models
import ietf.utils
import django.newforms as forms

from datetime import datetime
from django.shortcuts import render_to_response as render
from ietf.utils import log
from ietf.ipr.view_sections import section_table
from ietf.idtracker.models import Rfc, InternetDraft
from django.http import HttpResponseRedirect

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
    if field.name in ["date_applied"]:
        return forms.DateField()
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
        def clean_rfclist(self):
            rfclist = self.clean_data.get("rfclist", None)
            if rfclist:
                rfclist = re.sub("(?i) *[,;]? *rfc[- ]?", " ", rfclist)
                rfclist = rfclist.strip().split()
                for rfc in rfclist:
                    try:
                        Rfc.objects.get(rfc_number=int(rfc))
                    except:
                        raise forms.ValidationError("Unknown RFC number: %s - please correct this." % rfc)
                rfclist = " ".join(rfclist)
            else:
                # Check that not all three fields are empty.  We only need to
                # do this for one of the fields.
                draftlist = self.clean_data.get("draftlist", None)
                other = self.clean_data.get("other_designations", None)
                if not draftlist and not other:
                    raise forms.ValidationError("One of the Document fields below must be filled in")
            return rfclist
        def clean_draftlist(self):
            draftlist = self.clean_data.get("draftlist", None)
            if draftlist:
                draftlist = re.sub(" *[,;] *", " ", draftlist)
                draftlist = draftlist.strip().split()
                drafts = []
                for draft in draftlist:
                    if draft.endswith(".txt"):
                        draft = draft[:-4]
                    if re.search("-[0-9][0-9]$", draft):
                        filename = draft[:-3]
                        rev = draft[-2:]
                    else:
                        filename = draft
                        rev = None
                    try:
                        id = InternetDraft.objects.get(filename=filename)
                    except Exception, e:
                        log("Exception: %s" % e)
                        raise forms.ValidationError("Unknown Internet-Draft: %s - please correct this." % filename)
                    if rev and id.revision != rev:
                        raise forms.ValidationError("Unexpected revision '%s' for draft %s - the current revision is %s.  Please check this." % (rev, filename, id.revision))
                    drafts.append("%s-%s" % (filename, id.revision))
                return " ".join(drafts)
            return ""
        def clean_holder_contact(self):
            return self.holder_contact.full_clean()
        def clean_ietf_contact(self):
            return self.ietf_contact.full_clean()
        def clean_submitter(self):
            return self.submitter.full_clean()


    if request.method == 'POST':
        data = request.POST.copy()
        data["submitted_date"] = datetime.now().strftime("%Y-%m-%d")
        data["third_party"] = section_list["third_party"]
        data["generic"] = section_list["generic"]
        data["status"] = "0"
        data["comply"] = "1"

        if type == "general":
            data["document_title"] = """%(p_h_legal_name)s's General License Statement""" % data
        if type == "specific":
            data["ipr_summary"] = get_ipr_summary(data)
            data["document_title"] = """%(p_h_legal_name)s's Statement about IPR related to %(ipr_summary)s""" % data
        if type == "third-party":
            data["ipr_summary"] = get_ipr_summary(data)
            data["document_title"] = """%(submitter)s's Statement about IPR related to %(ipr_summary)s belonging to %(p_h_legal_name)s""" % data
        
        for src in ["hold", "ietf"]:
            if "%s_contact_is_submitter" % src in data:
                for subfield in ["name", "title", "department", "address1", "address2", "telephone", "fax", "email"]:
                    try:
                        data[ "subm_%s" % subfield ] = data[ "%s_%s" % (src,subfield) ]
                    except Exception, e:
                        #log("Caught exception: %s"%e)
                        pass
        form = IprForm(data)
        if form.is_valid():
            # Save data :
            #   IprDetail, IprContact+, IprDraft+, IprRfc+, IprNotification

            # Save IprDetail
            instance = form.save()
            contact_type = {"hold":1, "ietf":2, "subm": 3}

            # Save IprContact(s)
            for prefix in ["hold", "ietf", "subm"]:
#                cdata = {"ipr": instance.ipr_id, "contact_type":contact_type[prefix]}
                cdata = {"ipr": instance, "contact_type":contact_type[prefix]}
                for item in data:
                    if item.startswith(prefix+"_"):
                        cdata[item[5:]] = data[item]
                try:
                    del cdata["contact_is_submitter"]
                except KeyError:
                    pass
                contact = models.IprContact(**cdata)
                contact.save()
#                contact = ContactForm(cdata)
#                if contact.is_valid():
#                    contact.save()
#                else:
#                    log("Invalid contact: %s" % contact)

            # Save IprDraft(s)
            for draft in form.clean_data["draftlist"].split():
                id = InternetDraft.objects.get(filename=draft[:-3])
                iprdraft = models.IprDraft(document=id, ipr=instance, revision=draft[-2:])
                iprdraft.save()

            # Save IprRfc(s)
            for rfcnum in form.clean_data["rfclist"].split():
                rfc = Rfc.objects.get(rfc_number=int(rfcnum))
                iprrfc = models.IprRfc(rfc_number=rfc, ipr=instance)
                iprrfc.save()

            return HttpResponseRedirect("/ipr/ipr-%s" % instance.ipr_id)
            #return HttpResponseRedirect("/ipr/")
        
            pass
        else:
            if form.ietf_contact_is_submitter:
                form.ietf_contact_is_submitter_checked = "checked"

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


def get_ipr_summary(data):

    rfc_ipr = [ "RFC %s" % item for item in data["rfclist"].split() ]
    draft_ipr = data["draftlist"].split()
    ipr = rfc_ipr + draft_ipr
    if data["other_designations"]:
        ipr += [ data["other_designations"] ]

    if len(ipr) == 1:
        ipr = ipr[0]
    elif len(ipr) == 2:
        ipr = " and ".join(ipr)
    else:
        ipr = ", ".join(ipr[:-1] + ", and " + ipr[-1])

    return ipr
