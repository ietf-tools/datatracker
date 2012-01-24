# Copyright The IETF Trust 2007, All Rights Reserved

import re
import models
import ietf.utils
from django import forms

from datetime import datetime
from django.shortcuts import render_to_response as render, get_object_or_404
from django.template import RequestContext
from django.http import Http404
from django.conf import settings
from ietf.utils import log
from ietf.utils.mail import send_mail
from ietf.ipr.view_sections import section_table
from ietf.idtracker.models import Rfc, InternetDraft

# ----------------------------------------------------------------
# Create base forms from models
# ----------------------------------------------------------------    

phone_re = re.compile(r'^\+?[0-9 ]*(\([0-9]+\))?[0-9 -]+( ?x ?[0-9]+)?$')
phone_error_message = """Phone numbers may have a leading "+", and otherwise only contain numbers [0-9]; dash, period or space; parentheses, and an optional extension number indicated by 'x'."""

from django.forms import ModelForm

class BaseIprForm(ModelForm):
    licensing_option = forms.IntegerField(widget=forms.RadioSelect(choices=models.LICENSE_CHOICES), required=False)
    is_pending = forms.IntegerField(widget=forms.RadioSelect(choices=((1, "YES"), (2, "NO"))), required=False)
    applies_to_all = forms.IntegerField(widget=forms.RadioSelect(choices=((1, "YES"), (2, "NO"))), required=False)
    class Meta:
        model = models.IprDetail
        exclude = ('rfc_document', 'id_document_tag') # 'legacy_url_0','legacy_url_1','legacy_title_1','legacy_url_2','legacy_title_2')
        
class BaseContactForm(ModelForm):
    telephone = forms.RegexField(phone_re, error_message=phone_error_message)
    fax = forms.RegexField(phone_re, error_message=phone_error_message, required=False)
    class Meta:
        model = models.IprContact
        exclude = ('ipr', 'contact_type')

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


# ----------------------------------------------------------------
# Form processing
# ----------------------------------------------------------------

def new(request, type, update=None, submitter=None):
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
        if section_list.get("holder_contact", False):
            holder_contact = ContactForm(prefix="hold")
        if section_list.get("ietf_contact", False):
            ietf_contact = ContactForm(prefix="ietf")
        if section_list.get("submitter", False):
            submitter = ContactForm(prefix="subm")
        def __init__(self, *args, **kw):
            contact_type = {1:"holder_contact", 2:"ietf_contact", 3:"submitter"}
            contact_initial = {}
            if update:
                for contact in update.contact.all():
                    contact_initial[contact_type[contact.contact_type]] = contact.__dict__
		if submitter:
		    if type == "third-party":
			contact_initial["ietf_contact"] = submitter
		    else:
			contact_initial["submitter"] = submitter
            kwnoinit = kw.copy()
            kwnoinit.pop('initial', None)
            for contact in ["holder_contact", "ietf_contact", "submitter"]:
                if section_list.get(contact, False):
                    setattr(self, contact, ContactForm(prefix=contact[:4], initial=contact_initial.get(contact, {}), *args, **kwnoinit))
            rfclist_initial = ""
            if update:
                if settings.USE_DB_REDESIGN_PROXY_CLASSES:
                    from ietf.ipr.models import IprDocAlias
                    rfclist_initial = " ".join(a.doc_alias.name.upper() for a in IprDocAlias.objects.filter(doc_alias__name__startswith="rfc", ipr=update))
                else:
                    rfclist_initial = " ".join(["RFC%d" % rfc.document_id for rfc in update.rfcs.all()])
            self.base_fields["rfclist"] = forms.CharField(required=False, initial=rfclist_initial)
            draftlist_initial = ""
            if update:
                if settings.USE_DB_REDESIGN_PROXY_CLASSES:
                    from ietf.ipr.models import IprDocAlias
                    draftlist_initial = " ".join(a.doc_alias.name + ("-%s" % a.rev if a.rev else "") for a in IprDocAlias.objects.filter(ipr=update).exclude(doc_alias__name__startswith="rfc"))
                else:
                    draftlist_initial = " ".join([draft.document.filename + (draft.revision and "-%s" % draft.revision or "") for draft in update.drafts.all()])
            self.base_fields["draftlist"] = forms.CharField(required=False, initial=draftlist_initial)
            if section_list.get("holder_contact", False):
                self.base_fields["hold_contact_is_submitter"] = forms.BooleanField(required=False)
            if section_list.get("ietf_contact", False):
                self.base_fields["ietf_contact_is_submitter"] = forms.BooleanField(required=False)
            self.base_fields["stdonly_license"] = forms.BooleanField(required=False)

            BaseIprForm.__init__(self, *args, **kw)
        # Special validation code
        def clean(self):
            if section_list.get("ietf_doc", False):
                # would like to put this in rfclist to get the error
                # closer to the fields, but clean_data["draftlist"]
                # isn't set yet.
                rfclist = self.cleaned_data.get("rfclist", None)
                draftlist = self.cleaned_data.get("draftlist", None)
                other = self.cleaned_data.get("other_designations", None)
                if not rfclist and not draftlist and not other:
                    raise forms.ValidationError("One of the Document fields below must be filled in")
            return self.cleaned_data
        def clean_rfclist(self):
            rfclist = self.cleaned_data.get("rfclist", None)
            if rfclist:
                rfclist = re.sub("(?i) *[,;]? *rfc[- ]?", " ", rfclist)
                rfclist = rfclist.strip().split()
                for rfc in rfclist:
                    try:
                        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
                            from ietf.doc.models import DocAlias
                            DocAlias.objects.get(name="rfc%s" % int(rfc))
                        else:
                            Rfc.objects.get(rfc_number=int(rfc))
                    except:
                        raise forms.ValidationError("Unknown RFC number: %s - please correct this." % rfc)
                rfclist = " ".join(rfclist)
            return rfclist
        def clean_draftlist(self):
            draftlist = self.cleaned_data.get("draftlist", None)
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
                        if settings.USE_DB_REDESIGN_PROXY_CLASSES:
                            from ietf.doc.models import DocAlias
                            id = DocAlias.objects.get(name=filename)
                            # proxy attribute for code below
                            id.revision = id.document.rev
                        else:
                            id = InternetDraft.objects.get(filename=filename)
                    except Exception, e:
                        log("Exception: %s" % e)
                        raise forms.ValidationError("Unknown Internet-Draft: %s - please correct this." % filename)
                    if rev and id.revision != rev:
                        raise forms.ValidationError("Unexpected revision '%s' for draft %s - the current revision is %s.  Please check this." % (rev, filename, id.revision))
                    drafts.append("%s-%s" % (filename, id.revision))
                return " ".join(drafts)
            return ""
        def clean_licensing_option(self):
            licensing_option = self.cleaned_data['licensing_option']
            if section_list.get('licensing', False):
                if licensing_option in (None, ''):
                    raise forms.ValidationError, 'This field is required.'
            return licensing_option
        def is_valid(self):
            if not BaseIprForm.is_valid(self):
                return False
            for contact in ["holder_contact", "ietf_contact", "submitter"]:
                if hasattr(self, contact) and getattr(self, contact) != None and not getattr(self, contact).is_valid():
                    return False
            return True

    # If we're POSTed, but we got passed a submitter, it was the
    # POST of the "get updater" form, so we don't want to validate
    # this one.  When we're posting *this* form, submitter is None,
    # even when updating.
    if (request.method == 'POST' or '_testpost' in request.REQUEST) and not submitter:
        if request.method == 'POST':
            data = request.POST.copy()
        else:
            data = request.GET.copy()
        data["submitted_date"] = datetime.now().strftime("%Y-%m-%d")
        data["third_party"] = section_list["third_party"]
        data["generic"] = section_list["generic"]
        data["status"] = "0"
        data["comply"] = "1"
        
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
            #   IprDetail, IprUpdate, IprContact+, IprDraft+, IprRfc+, IprNotification

            # Save IprDetail
            instance = form.save(commit=False)

	    legal_name_genitive = data['legal_name'] + "'" if data['legal_name'].endswith('s') else data['legal_name'] + "'s"
            if type == "generic":
                instance.title = legal_name_genitive + " General License Statement" 
            if type == "specific":
                data["ipr_summary"] = get_ipr_summary(form.cleaned_data)
                instance.title = legal_name_genitive + """ Statement about IPR related to %(ipr_summary)s""" % data
            if type == "third-party":
                data["ipr_summary"] = get_ipr_summary(form.cleaned_data)
		ietf_name_genitive = data['ietf_name'] + "'" if data['ietf_name'].endswith('s') else data['ietf_name'] + "'s"
                instance.title = ietf_name_genitive + """ Statement about IPR related to %(ipr_summary)s belonging to %(legal_name)s""" % data

            # A long document list can create a too-long title;
            # saving a too-long title raises an exception,
            # so prevent truncation in the database layer by
            # performing it explicitly.
            if len(instance.title) > 255:
                instance.title = instance.title[:252] + "..."

            instance.save()

            if update:
                updater = models.IprUpdate(ipr=instance, updated=update, status_to_be=1, processed=0)
                updater.save()
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
                contact = models.IprContact(**dict([(str(a),b) for a,b in cdata.items()]))
                contact.save()
                # store this contact in the instance for the email
                # similar to what views.show() does
                if   prefix == "hold":
                    instance.holder_contact = contact
                elif prefix == "ietf":
                    instance.ietf_contact = contact
                elif prefix == "subm":
                    instance.submitter = contact
#                contact = ContactForm(cdata)
#                if contact.is_valid():
#                    contact.save()
#                else:
#                    log("Invalid contact: %s" % contact)

            # Save IprDraft(s)
            for draft in form.cleaned_data["draftlist"].split():
                if settings.USE_DB_REDESIGN_PROXY_CLASSES:
                    name = draft[:-3]
                    rev = draft[-2:]
                    
                    from ietf.doc.models import DocAlias
                    models.IprDocAlias.objects.create(
                        doc_alias=DocAlias.objects.get(name=name),
                        ipr=instance,
                        rev=rev)
                else:
                    id = InternetDraft.objects.get(filename=draft[:-3])
                    iprdraft = models.IprDraft(document=id, ipr=instance, revision=draft[-2:])
                    iprdraft.save()

            # Save IprRfc(s)
            for rfcnum in form.cleaned_data["rfclist"].split():
                if settings.USE_DB_REDESIGN_PROXY_CLASSES:
                    from ietf.doc.models import DocAlias
                    models.IprDocAlias.objects.create(
                        doc_alias=DocAlias.objects.get(name="rfc%s" % int(rfcnum)),
                        ipr=instance,
                        rev="")
                else:
                    rfc = Rfc.objects.get(rfc_number=int(rfcnum))
                    iprrfc = models.IprRfc(document=rfc, ipr=instance)
                    iprrfc.save()

            send_mail(request, settings.IPR_EMAIL_TO, ('IPR Submitter App', 'ietf-ipr@ietf.org'), 'New IPR Submission Notification', "ipr/new_update_email.txt", {"ipr": instance, "update": update})
            return render("ipr/submitted.html", {"update": update}, context_instance=RequestContext(request))
        else:
            if 'ietf_contact_is_submitter' in data:
                form.ietf_contact_is_submitter_checked = True
            if 'hold_contact_is_submitter' in data:
                form.hold_contact_is_submitter_checked = True

            for error in form.errors:
                log("Form error for field: %s: %s"%(error, form.errors[error]))
            # Fall through, and let the partially bound form, with error
            # indications, be rendered again.
            pass
    else:
        if update:
            form = IprForm(initial=update.__dict__)
        else:
            form = IprForm()
        form.unbound_form = True

    # ietf.utils.log(dir(form.ietf_contact_is_submitter))
    return render("ipr/details_edit.html", {"ipr": form, "section_list":section_list, "debug": debug}, context_instance=RequestContext(request))

def update(request, ipr_id=None):
    """Update a specific IPR disclosure"""
    ipr = get_object_or_404(models.IprDetail, ipr_id=ipr_id)
    if not ipr.status in [1,3]:
	raise Http404        
    type = "specific"
    if ipr.generic:
	type = "generic"
    if ipr.third_party:
	type = "third-party"
    # We're either asking for initial permission or we're in
    # the general ipr form.  If the POST argument has the first
    # field of the ipr form, then we must be dealing with that,
    # so just pass through - otherwise, collect the updater's
    # info first.
    submitter = None
    if not(request.POST.has_key('legal_name')):
	class UpdateForm(BaseContactForm):
	    def __init__(self, *args, **kwargs):
                super(UpdateForm, self).__init__(*args, **kwargs)
                self.fields["update_auth"] = forms.BooleanField()
                
	if request.method == 'POST':
	    form = UpdateForm(request.POST)
        elif '_testpost' in request.REQUEST:
            form = UpdateForm(request.GET)
	else:
	    form = UpdateForm()

	if not(form.is_valid()):
            for error in form.errors:
                log("Form error for field: %s: %s"%(error, form.errors[error]))
	    return render("ipr/update.html", {"form": form, "ipr": ipr, "type": type}, context_instance=RequestContext(request))
	else:
	    submitter = form.cleaned_data

    return new(request, type, ipr, submitter)


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
        ipr = ", ".join(ipr[:-1]) + ", and " + ipr[-1]

    return ipr

# changes done by convert-096.py:changed newforms to forms
# cleaned_data
