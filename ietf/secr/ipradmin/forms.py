from copy import deepcopy
from form_utils.forms import BetterModelForm
from django import forms
from django.utils.safestring import mark_safe
from django.forms.formsets import formset_factory
from django.utils import simplejson

from ietf.ipr.models import IprDetail, IprContact, LICENSE_CHOICES, IprRfc, IprDraft, IprUpdate, SELECT_CHOICES, IprDocAlias

from ietf.doc.models import DocAlias
from ietf.secr.utils.document import get_rfc_num

def mytest(val):
    if val == '1':
        return True
        
class IprContactForm(forms.ModelForm):
    contact_type = forms.ChoiceField(widget=forms.HiddenInput, choices=IprContact.TYPE_CHOICES)
    name = forms.CharField(required=False, max_length=255)
    telephone = forms.CharField(required=False, max_length=25)
    email = forms.CharField(required=False, max_length=255)

    class Meta:
        model = IprContact
        fields = [ 'name', 'title', 'department', 'address1', 'address2', 'telephone', 'fax', 'email' ,
                   'contact_type',]

    def clean_contact_type(self):
        return str(self.cleaned_data['contact_type'])
    
    @property
    def _empty(self):
        fields = deepcopy(self._meta.fields)
        fields.remove("contact_type")
        for field in fields:
            if self.cleaned_data[field].strip():
                return False
        return True

    def save(self, ipr_detail, *args, **kwargs):
        #import ipdb; ipdb.set_trace()
        if(self.cleaned_data['contact_type'] != 1 and self._empty):
            return None
        contact = super(IprContactForm, self).save(*args, commit=False, **kwargs)
        contact.ipr = ipr_detail
        contact.save()
        return contact

IPRContactFormset = formset_factory(IprContactForm, extra=0)


class IprDetailForm(BetterModelForm):
    IS_PENDING_CHOICES = DOCUMENT_SECTIONS_CHOICES = (
        ("0", "no"),
        ("1", "yes"))
    title = forms.CharField(required=True)
    updated = forms.IntegerField(
            required=False, label='IPR ID that is updated by this IPR')
    remove_old_ipr = forms.BooleanField(required=False, label='Remove old IPR')
    rfc_num = forms.CharField(required=False, label='RFC Number', widget=forms.HiddenInput)
    id_filename = forms.CharField(
            max_length=512, required=False,
            label='I-D Filename (draft-ietf...)',
            widget=forms.HiddenInput)
    #is_pending = forms.ChoiceField(choices=IS_PENDING_CHOICES,required=False, label="B. Does your disclosure relate to an unpublished pending patent application?", widget=forms.RadioSelect)
    #is_pending = forms.BooleanField(required=False, label="B. Does your disclosure relate to an unpublished pending patent application?")
    licensing_option = forms.ChoiceField(
            widget=forms.RadioSelect, choices=LICENSE_CHOICES, required=False)
    patents = forms.CharField(widget=forms.Textarea, required=False)
    date_applied = forms.CharField(required=False)
    country = forms.CharField(required=False)
    submitted_date = forms.DateField(required=True)
    #lic_opt_c_sub = forms.BooleanField(required=False,widget=forms.CheckboxInput)
    '''
    FIXME: (stalled - comply is bool in model)
    comply = forms.MultipleChoiceField(
        choices = (('YES', 'YES'), ('NO', 'NO'), ('N/A', 'N/A')),
        widget = forms.RadioSelect()
    )
    '''

    def clean_lic_opt_sub(self, val):
        return int(val)

    def clean(self):
        #print self.data, "\n\n", self.cleaned_data
        #import ipdb;ipdb.set_trace()
        lic_opt = self.cleaned_data['licensing_option']
        for num, ltr in (('1', 'a'), ('2', 'b'), ('3', 'c')):
            opt_sub = 'lic_opt_'+ltr+'_sub'
            self._meta.fields.append(opt_sub)
            if lic_opt == num and opt_sub in self.data:
                self.cleaned_data[opt_sub] = 1
            else:
                self.cleaned_data[opt_sub] = 0
        #self.cleaned_data['lic_opt_a_sub'] = self.clean_lic_opt_sub(self.data['lic_opt_a_sub'])
        return self.cleaned_data

    def __init__(self, *args, **kwargs):
        formtype = kwargs.get('formtype')
        if formtype:
            del kwargs['formtype']
        super(IprDetailForm, self).__init__(*args, **kwargs)
        self.fields['legacy_url_0'].label='Old IPR Url'
        self.fields['title'].label='IPR Title'
        self.fields['legacy_title_1'].label='Text for Update Link'
        self.fields['legacy_url_1'].label='URL for Update Link'
        self.fields['legacy_title_2'].label='Additional Old Title 2'
        self.fields['legacy_url_2'].label='Additional Old URL 2'
        self.fields['document_sections'].label='C. If an Internet-Draft or RFC includes multiple parts and it is not reasonably apparent which part of such Internet-Draft or RFC is alleged to be covered by the patent information disclosed in Section V(A) or V(B), it is helpful if the discloser identifies here the sections of the Internet-Draft or RFC that are alleged to be so covered.' 
        self.fields['patents'].label='Patent, Serial, Publication, Registration, or Application/File number(s)'
        self.fields['date_applied'].label='Date(s) granted or applied for (YYYY-MM-DD)'
        self.fields['comments'].label='Licensing information, comments, notes or URL for further information'
        self.fields['lic_checkbox'].label='The individual submitting this template represents and warrants that all terms and conditions that must be satisfied for implementers of any covered IETF specification to obtain a license have been disclosed in this IPR disclosure statement.'
        self.fields['third_party'].label='Third Party Notification?'
        self.fields['generic'].label='Generic IPR?'
        self.fields['comply'].label='Complies with RFC 3979?'
        self.fields['is_pending'].label="B. Does your disclosure relate to an unpublished pending patent application?"
        # textarea sizes
        self.fields['patents'].widget.attrs['rows'] = 2
        self.fields['patents'].widget.attrs['cols'] = 70
        self.fields['notes'].widget.attrs['rows'] = 3
        self.fields['notes'].widget.attrs['cols'] = 70
        self.fields['document_sections'].widget.attrs['rows'] = 3
        self.fields['document_sections'].widget.attrs['cols'] = 70
        self.fields['comments'].widget.attrs['rows'] = 3
        self.fields['comments'].widget.attrs['cols'] = 70
        self.fields['other_notes'].widget.attrs['rows'] = 5
        self.fields['other_notes'].widget.attrs['cols'] = 70
        
        #self.fields['is_pending'].widget.check_test = mytest
        self.fields['is_pending'].widget = forms.Select(choices=self.IS_PENDING_CHOICES)

        if formtype == 'update':
            if self.instance.generic:
                self.fields['document_sections'] = forms.ChoiceField(
                    widget=forms.RadioSelect, 
                    choices=self.DOCUMENT_SECTIONS_CHOICES, 
                    required=False,
                    label='C. Does this disclosure apply to all IPR owned by the submitter?')
            legacy_url = self.instance.legacy_url_0
            self.fields['legacy_url_0'].label = mark_safe(
                '<a href="%s">Old IPR Url</a>' % legacy_url
            )

            updates = self.instance.updates.all()
            if updates:
                self.fields['updated'].initial = updates[0].updated.ipr_id

            rfcs = {}
            for rfc in self.instance.documents.filter(doc_alias__name__startswith='rfc'):
                rfcs[rfc.doc_alias.id] = get_rfc_num(rfc.doc_alias.document)+" "+rfc.doc_alias.document.title
                
            drafts = {}
            for draft in self.instance.documents.exclude(doc_alias__name__startswith='rfc'):
                drafts[draft.doc_alias.id] = draft.doc_alias.document.name
            self.initial['rfc_num'] = simplejson.dumps(rfcs)
            self.initial['id_filename'] = simplejson.dumps(drafts)
        
        else:
            # if this is a new IPR hide status field
            self.fields['status'].widget = forms.HiddenInput()
            
    def _fields(self, lst):
        ''' pass in list of titles, get back a list of form fields '''
        return [self.fields[k] for k in lst]

    def _fetch_objects(self, data, model):
        if data:
            ids = [int(x) for x in simplejson.loads(data)]
        else:
            return []
        objects = []
        for id in ids:
            try:
                objects.append(model.objects.get(pk=id))
            except model.DoesNotExist, e:
                raise forms.ValidationError("%s not found for id %d" %(model._meta.verbose_name, id))
        return objects

    #def clean_document_sections(self):
    #    import ipdb; ipdb.set_trace()
    #    if self.data['document_sections'] not in self.fields['document_sections'].choices:
    #        return ''
    #    else:
    #        return self.data['document_sections']

    def clean_rfc_num(self):
        return self._fetch_objects(
                self.cleaned_data['rfc_num'].strip(), DocAlias)

    def clean_licensing_option(self):
        data = self.cleaned_data['licensing_option']
        if data == "":
            return 0
        return data

    def clean_id_filename(self):
        return self._fetch_objects(
                self.cleaned_data['id_filename'].strip(), DocAlias)

    def clean_is_pending(self):
        data = self.cleaned_data['is_pending']
        if data == "":
            return 0
        return data

    def clean_updated(self):
        id = self.cleaned_data['updated']
        if id == None:
            return None
        try:
            old_ipr = IprDetail.objects.get(pk=id)
        except IprDetail.DoesNotExist:
            raise forms.ValidationError("old IPR not found for id %d" % id)
        return old_ipr

    def clean_status(self):
        status = self.cleaned_data['status']
        return 0 if status == None else status

    def save(self, *args, **kwargs):
        #import ipdb; ipdb.set_trace()
        ipr_detail = super(IprDetailForm, self).save(*args, **kwargs)
        ipr_detail.rfc_document_tag = ipr_detail.rfc_number = None

        # Force saving lic_opt_sub to override model editable=False
        lic_opt = self.cleaned_data['licensing_option']
        for num, ltr in (('1', 'a'), ('2', 'b'), ('3', 'c')):
            opt_sub = 'lic_opt_'+ltr+'_sub'
            self._meta.fields.append(opt_sub)
            if lic_opt == num and opt_sub in self.data:
                exec('ipr_detail.'+opt_sub+' = 1')
            else:
                exec('ipr_detail.'+opt_sub+' = 0')

        ipr_detail.save()
        old_ipr = self.cleaned_data['updated']

        if old_ipr:
            if self.cleaned_data['remove_old_ipr']:
                old_ipr.status = 3
                old_ipr.save()
            obj,created = IprUpdate.objects.get_or_create(ipr=ipr_detail,updated=old_ipr)
            if created:
                obj.status_to_be = old_ipr.status
                obj.processed = 0
                obj.save()
        '''
        IprRfc.objects.filter(ipr=ipr_detail).delete()
        IprDraft.objects.filter(ipr=ipr_detail).delete()
        for rfc in self.cleaned_data['rfc_num']:
            IprRfc.objects.create(ipr=ipr_detail, document=rfc)
        for draft in self.cleaned_data['id_filename']:
            IprDraft.objects.create(ipr=ipr_detail, document=draft)
        '''
        IprDocAlias.objects.filter(ipr=ipr_detail).delete()
        for doc in self.cleaned_data['rfc_num']:
            IprDocAlias.objects.create(ipr=ipr_detail,doc_alias=doc)
        for doc in self.cleaned_data['id_filename']:
            #doc_alias = DocAlias.objects.get(id=doc)
            IprDocAlias.objects.create(ipr=ipr_detail,doc_alias=doc)
            
        return ipr_detail

    class Meta:
        model = IprDetail
        fieldsets = [
            ('basic', {
                'fields': [
                    'title',
                    'legacy_url_0',
                    'legacy_title_1',
                    'legacy_url_1',
                    'legacy_title_2',
                    'legacy_url_2',
                    'submitted_date',
                ],
            }),
            ('booleans', {
                'fields': [
                    'third_party',
                    'generic',
                    'comply',
                ],
            }),
            ('old_ipr', {
                'fields': [
                    'status',
                    'updated',
                    'remove_old_ipr',
                ],
            }),
            ('legal_name', {
                'legend': 'I. Patent Holder/Applicant ("Patent Holder")',
                'fields': [
                    'legal_name',
                ],
            }),
            ('rfc', {
                'legend': 'IV. IETF Document or Working Group Contribution to Which Patent Disclosure Relates',
                'fields': [
                    'rfc_num',
                    'id_filename',
                    'other_designations',
                ],
            }),
            ('disclosure', {
                'legend': 'V. Disclosure of Patent Information (i.e., patents or patent applications required to be disclosed by Section 6 of RFC 3979)',
                'description': 'A. For granted patents or published pending patent applications, please provide the following information',
                'fields': [
                    'patents',
                    'date_applied',
                    'country',
                    'notes',
                    'is_pending',
                    'document_sections',
                ],
            }),
            ('other_notes', {
                'legend': 'VIII. Other Notes',
                'fields': [
                    'other_notes',
                ],
            }),
            ('licensing_declaration', {
                'fields': [
                    'lic_checkbox',
                    'licensing_option',
                    'comments',
                ],
            }),
        ]
 
