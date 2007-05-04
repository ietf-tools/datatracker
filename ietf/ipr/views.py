import models
from django.shortcuts import render_to_response as render
import django.newforms as forms

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

def show(request, ipr_id=None):
    """Show a specific IPR disclosure"""
    assert ipr_id != None
    ipr = models.IprDetail.objects.filter(ipr_id=ipr_id)[0]
    ipr.disclosure_type = get_disclosure_type(ipr)
    try:
        ipr.holder_contact = ipr.contact.filter(contact_type=1)[0]    
    except IndexError:
        ipr.holder_contact = ""
    try:
        ipr.ietf_contact = ipr.contact.filter(contact_type=2)[0]
    except IndexError:
        ipr.ietf_contact = ""
    try:
        ipr.submitter = ipr.contact.filter(contact_type=3)[0]
    except IndexError:
        ipr.submitter = ""

    if   ipr.generic:
        return render("ipr/details_generic.html",  {"ipr": ipr})
    if ipr.third_party:
        return render("ipr/details_thirdpty.html", {"ipr": ipr})
    else:
        return render("ipr/details_specific.html", {"ipr": ipr})
        

def update(request, ipr_id=None):
    """Update a specific IPR disclosure"""
    # TODO: replace the placeholder code with the appropriate update code
    return show(request, ipr_id)

def new(request, type):
    """Form to make a new IPR disclosure"""
    debug = ""

    IprForm = forms.form_for_model(models.IprDetail, formfield_callback=detail_field_fixup)
    # Some extra fields which will get post-processing to generate the IprRfcs
    # and IprDrafts entries which go into the database:
    IprForm.base_fields["rfclist"] = forms.CharField(required=False)
    IprForm.base_fields["draftlist"] = forms.CharField(required=False)
    IprForm.base_fields["stdonly_license"] = forms.BooleanField(required=False)

    ContactForm = forms.form_for_model(models.IprContact)

    if request.method == 'POST':
        form = IprForm(request.POST)

        form.holder_contact = ContactForm(request.POST, prefix="ph")
        form.ietf_contact = ContactForm(request.POST, prefix="ietf")
        form.submitter = ContactForm(request.POST, prefix="sub")

        if form.is_valid():
            form.save()
            return HttpResponseRedirect("/ipr/")
    else:
        form = IprForm()
        form.holder_contact = ContactForm(prefix="ph")
        form.ietf_contact = ContactForm(prefix="ietf")
        form.submitter = ContactForm(prefix="sub")

    form.unbound_form = not form.is_bound
    form.disclosure_type = type.capitalize()
    return render("ipr/new_%s.html" % type, {"ipr": form, "debug": debug, })

def detail_field_fixup(field):
    if field.name == "licensing_option":
        return forms.IntegerField(widget=forms.RadioSelect(choices=models.LICENSE_CHOICES))
    if field.name in ["selecttype", "selectowned"]:
        return forms.IntegerField(widget=forms.RadioSelect(choices=((1, "YES"), (2, "NO"))))
    return field.formfield()


# ---- Helper functions ------------------------------------------------------

def get_disclosure_type(ipr):
    if   ipr.generic:
        assert not ipr.third_party
        return "Generic"
    if ipr.third_party:
        return "Third Party"
    else:
        return "Specific"
