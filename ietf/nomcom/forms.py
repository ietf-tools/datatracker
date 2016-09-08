from django.conf import settings
from django import forms
from django.contrib.formtools.preview import FormPreview, AUTO_ID
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.core.urlresolvers import reverse
from django.utils.html import mark_safe

from ietf.dbtemplate.forms import DBTemplateForm
from ietf.group.models import Group, Role
from ietf.ietfauth.utils import role_required
from ietf.name.models import RoleName, FeedbackTypeName
from ietf.nomcom.models import ( NomCom, Nomination, Nominee, NomineePosition,
                                 Position, Feedback, ReminderDates )
from ietf.nomcom.utils import (NOMINATION_RECEIPT_TEMPLATE, FEEDBACK_RECEIPT_TEMPLATE,
                               get_user_email, validate_private_key, validate_public_key,
                               make_nomineeposition, make_nomineeposition_for_newperson,
                               create_feedback_email)
from ietf.person.models import Email
from ietf.person.fields import SearchableEmailField, SearchablePersonField, SearchablePersonsField
from ietf.utils.fields import MultiEmailField
from ietf.utils.mail import send_mail
from ietf.mailtrigger.utils import gather_address_lists

import debug                   # pyflakes:ignore


ROLODEX_URL = getattr(settings, 'ROLODEX_URL', None)


def get_nomcom_group_or_404(year):
    return get_object_or_404(Group,
                             acronym__icontains=year,
                             state__slug='active',
                             nomcom__isnull=False)


class PositionNomineeField(forms.ChoiceField):

    def __init__(self, *args, **kwargs):
        self.nomcom = kwargs.pop('nomcom')
        positions = Position.objects.get_by_nomcom(self.nomcom).opened().order_by('name')
        results = []
        for position in positions:
            accepted_nominees = [np.nominee for np in NomineePosition.objects.filter(position=position,state='accepted').exclude(nominee__duplicated__isnull=False)]
            nominees = [('%s_%s' % (position.id, i.id), unicode(i)) for i in accepted_nominees]
            if nominees:
                results.append((position.name+" (Accepted)", nominees))
        for position in positions:
            other_nominees = [np.nominee for np in NomineePosition.objects.filter(position=position).exclude(state='accepted').exclude(nominee__duplicated__isnull=False)]
            nominees = [('%s_%s' % (position.id, i.id), unicode(i)) for i in other_nominees]
            if nominees:
                results.append((position.name+" (Declined or Pending)", nominees))
        kwargs['choices'] = results
        super(PositionNomineeField, self).__init__(*args, **kwargs)

    def clean(self, value):
        nominee = super(PositionNomineeField, self).clean(value)
        if not nominee:
            return nominee
        (position_id, nominee_id) = nominee.split('_')
        try:
            position = Position.objects.get_by_nomcom(self.nomcom).opened().get(id=position_id)
        except Position.DoesNotExist:
            raise forms.ValidationError('Invalid nominee')
        try:
            nominee = position.nominee_set.get_by_nomcom(self.nomcom).get(id=nominee_id)
        except Nominee.DoesNotExist:
            raise forms.ValidationError('Invalid nominee')
        return (position, nominee)


class MultiplePositionNomineeField(forms.MultipleChoiceField, PositionNomineeField):

    def clean(self, value):
        nominees = super(PositionNomineeField, self).clean(value) # pylint: disable=bad-super-call
        result = []
        for nominee in nominees:
            if not nominee:
                return nominee
            (position_id, nominee_id) = nominee.split('_')
            try:
                position = Position.objects.get_by_nomcom(self.nomcom).opened().get(id=position_id)
            except Position.DoesNotExist:
                raise forms.ValidationError('Invalid nominee')
            try:
                nominee = position.nominee_set.get_by_nomcom(self.nomcom).get(id=nominee_id)
            except Nominee.DoesNotExist:
                raise forms.ValidationError('Invalid nominee')
            result.append((position, nominee))
        return result


class EditMembersForm(forms.Form):

    members = MultiEmailField(label="Members email", required=False, widget=forms.Textarea)

class EditMembersFormPreview(FormPreview):
    form_template = 'nomcom/edit_members.html'
    preview_template = 'nomcom/edit_members_preview.html'

    @method_decorator(role_required("Nomcom Chair", "Nomcom Advisor"))
    def __call__(self, request, *args, **kwargs):
        year = kwargs['year']
        group = get_nomcom_group_or_404(year)
        self.state['group'] = group
        self.state['rolodex_url'] = ROLODEX_URL
        groups = group.nomcom_set.all()
        self.nomcom = groups and groups[0] or None
        self.group = group
        self.year = year

        return super(EditMembersFormPreview, self).__call__(request, *args, **kwargs)

    def preview_get(self, request):
        "Displays the form"
        f = self.form(auto_id=self.get_auto_id(), initial=self.get_initial(request))
        return render_to_response(self.form_template,
                                  {'form': f,
                                  'stage_field': self.unused_name('stage'),
                                  'state': self.state,
                                  'year': self.year,
                                  'nomcom': self.nomcom,
                                  'selected': 'edit_members'},
                                  context_instance=RequestContext(request))

    def get_initial(self, request):
        members = self.group.role_set.filter(name__slug='member')
        if members:
            return { "members": ",\r\n".join(role.email.address for role in members) }
        return {}

    def process_preview(self, request, form, context):
        members_email = form.cleaned_data['members']

        members_info = []
        emails_not_found = []

        for email in members_email:
            try:
                email_obj = Email.objects.get(address=email)
                person = email_obj.person
            except Email.DoesNotExist:
                person = None
            if person:
                members_info.append({'email': email,
                                     'email_obj': email_obj,
                                     'person': person})
            else:
                emails_not_found.append(email)
        self.state.update({'members_info': members_info,
                           'emails_not_found': emails_not_found})

    def preview_post(self, request):
        "Validates the POST data. If valid, displays the preview page. Else, redisplays form."
        f = self.form(request.POST, auto_id=AUTO_ID)
        context = {'form': f, 'stage_field': self.unused_name('stage'), 'state': self.state,
                   'year': self.year}
        if f.is_valid():
            self.process_preview(request, f, context)
            context['hash_field'] = self.unused_name('hash')
            context['hash_value'] = self.security_hash(request, f)
            return render_to_response(self.preview_template, context, context_instance=RequestContext(request))
        else:
            return render_to_response(self.form_template, context, context_instance=RequestContext(request))

    def post_post(self, request):
        "Validates the POST data. If valid, calls done(). Else, redisplays form."
        f = self.form(request.POST, auto_id=AUTO_ID)
        context = {'form': f, 'stage_field': self.unused_name('stage'), 'state': self.state,
                   'year': self.year}
        if f.is_valid():
            if self.security_hash(request, f) != request.POST.get(self.unused_name('hash')):
                return self.failed_hash(request)  # Security hash failed.
            self.process_preview(request, f, context)
            return self.done(request, f.cleaned_data)
        else:
            return render_to_response(self.form_template, context, context_instance=RequestContext(request))

    def done(self, request, cleaned_data):
        members_info = self.state['members_info']
        members_email = [member['email'] for member in self.state['members_info']]
        members_excluded = self.group.role_set.filter(name__slug='member').exclude(email__address__in=members_email)
        members_excluded.delete()
        for member in members_info:
            Role.objects.get_or_create(name=RoleName.objects.get(slug="member"),
                                       group=self.group,
                                       person=member['person'],
                                       email=member['email_obj'])

        return redirect('nomcom_edit_members', year=self.year)


class EditNomcomForm(forms.ModelForm):


    def __init__(self, *args, **kwargs):
        super(EditNomcomForm, self).__init__(*args, **kwargs)

        if self.instance:
            if self.instance.public_key:
                help_text = "The nomcom already has a public key. Previous data will remain encrypted with the old key"
            else:
                help_text = "The nomcom has not a public key yet"
            self.fields['public_key'].help_text = help_text

    class Meta:
        model = NomCom
        fields = ('public_key', 'initial_text',
                  'send_questionnaire', 'reminder_interval')

    def clean_public_key(self):
        public_key = self.cleaned_data.get('public_key', None)
        if not public_key:
            return
        (validation, error) = validate_public_key(public_key)
        if validation:
            return public_key
        raise forms.ValidationError('Invalid public key. Error was: %s' % error)


class MergeForm(forms.Form):

    primary_person = SearchablePersonField(help_text="Select the person you want the datatracker to keep")
    duplicate_persons = SearchablePersonsField(help_text="Select all the duplicates that should be merged into the primary person record")

    def __init__(self, *args, **kwargs):
        self.nomcom = kwargs.pop('nomcom', None)
        super(MergeForm, self).__init__(*args, **kwargs)

    def clean(self):
        primary_person = self.cleaned_data.get("primary_person")
        duplicate_persons = self.cleaned_data.get("duplicate_persons")
        if primary_person and duplicate_persons:
            if primary_person in duplicate_persons:
                msg = "The primary person must not also be listed as a duplicate person"
                self._errors["primary_person"] = self.error_class([msg])
        return self.cleaned_data

    def save(self):
        primary_person = self.cleaned_data.get("primary_person")
        duplicate_persons = self.cleaned_data.get("duplicate_persons")

        subject = "Request to merge Person records"
        from_email = settings.NOMCOM_FROM_EMAIL
        (to_email, cc) = gather_address_lists('person_merge_requested')
        context = {'primary_person':primary_person, 'duplicate_persons':duplicate_persons}
        send_mail(None, to_email, from_email, subject, 'nomcom/merge_request.txt', context, cc=cc)

class NominateForm(forms.ModelForm):
    searched_email = SearchableEmailField(only_users=False)
    qualifications = forms.CharField(label="Candidate's qualifications for the position",
                               widget=forms.Textarea())
    confirmation = forms.BooleanField(label='Email comments back to me as confirmation.',
                                      help_text="If you want to get a confirmation mail containing your feedback in cleartext, please check the 'email comments back to me as confirmation'.",
                                      required=False)

    def __init__(self, *args, **kwargs):
        self.nomcom = kwargs.pop('nomcom', None)
        self.user = kwargs.pop('user', None)
        self.public = kwargs.pop('public', None)

        super(NominateForm, self).__init__(*args, **kwargs)

        new_person_url_name = 'nomcom_%s_nominate_newperson' % ('public' if self.public else 'private' )
        self.fields['searched_email'].label = 'Candidate email'
        self.fields['searched_email'].help_text = 'Search by name or email address. Click <a href="%s">here</a> if the search does not find the candidate you want to nominate.' % reverse(new_person_url_name,kwargs={'year':self.nomcom.year()})
        self.fields['nominator_email'].label = 'Nominator email'
        if self.nomcom:
            self.fields['position'].queryset = Position.objects.get_by_nomcom(self.nomcom).opened()
            self.fields['qualifications'].help_text = self.nomcom.initial_text

        if not self.public:
            self.fields.pop('confirmation')
            author = get_user_email(self.user)
            if author:
                self.fields['nominator_email'].initial = author.address
                help_text = """(Nomcom Chair/Member: please fill this in. Use your own email address if the person making the
                               nomination wishes to be anonymous. The confirmation email will be sent to the address given here,
                               and the address will also be captured as part of the registered nomination.)"""
                self.fields['nominator_email'].help_text = help_text
                self.fields['share_nominator'].help_text = """(Nomcom Chair/Member: Check this box if the person providing this nomination
                                                              has indicated they will allow NomCom to share their name as one of the people
                                                              nominating this candidate."""
        else:
            self.fields.pop('nominator_email')


    def save(self, commit=True):
        # Create nomination
        nomination = super(NominateForm, self).save(commit=False)
        nominator_email = self.cleaned_data.get('nominator_email', None)
        searched_email = self.cleaned_data['searched_email']
        position = self.cleaned_data['position']
        qualifications = self.cleaned_data['qualifications']
        confirmation = self.cleaned_data.get('confirmation', False)
        share_nominator = self.cleaned_data['share_nominator']
        nomcom_template_path = '/nomcom/%s/' % self.nomcom.group.acronym

        nomination.candidate_name = searched_email.person.plain_name()
        nomination.candidate_email = searched_email.address

        author = None
        if self.public:
            author = get_user_email(self.user)
        else:
            if nominator_email:
                emails = Email.objects.filter(address=nominator_email)
                author = emails and emails[0] or None
        nominee = make_nomineeposition(self.nomcom, searched_email.person, position, author)

        # Complete nomination data
        feedback = Feedback.objects.create(nomcom=self.nomcom,
                                           comments=qualifications,
                                           type=FeedbackTypeName.objects.get(slug='nomina'),
                                           user=self.user)
        feedback.positions.add(position)
        feedback.nominees.add(nominee)

        if author:
            nomination.nominator_email = author.address
            feedback.author = author.address
            feedback.save()

        nomination.nominee = nominee
        nomination.comments = feedback
        nomination.share_nominator = share_nominator
        nomination.user = self.user

        if commit:
            nomination.save()

        # send receipt email to nominator
        if confirmation:
            if author:
                subject = 'Nomination receipt'
                from_email = settings.NOMCOM_FROM_EMAIL
                (to_email, cc) = gather_address_lists('nomination_receipt_requested',nominator=author.address)
                context = {'nominee': nominee.email.person.name,
                          'comments': qualifications,
                          'position': position.name}
                path = nomcom_template_path + NOMINATION_RECEIPT_TEMPLATE
                send_mail(None, to_email, from_email, subject, path, context, cc=cc)

        return nomination

    class Meta:
        model = Nomination
        fields = ('share_nominator', 'position', 'nominator_email', 'searched_email', 
                  'candidate_phone', 'qualifications', 'confirmation')

class NominateNewPersonForm(forms.ModelForm):
    qualifications = forms.CharField(label="Candidate's qualifications for the position",
                               widget=forms.Textarea())
    confirmation = forms.BooleanField(label='Email comments back to me as confirmation.',
                                      help_text="If you want to get a confirmation mail containing your feedback in cleartext, please check the 'email comments back to me as confirmation'.",
                                      required=False)

    def __init__(self, *args, **kwargs):
        self.nomcom = kwargs.pop('nomcom', None)
        self.user = kwargs.pop('user', None)
        self.public = kwargs.pop('public', None)

        super(NominateNewPersonForm, self).__init__(*args, **kwargs)

        self.fields['nominator_email'].label = 'Nominator email'
        if self.nomcom:
            self.fields['position'].queryset = Position.objects.get_by_nomcom(self.nomcom).opened()
            self.fields['qualifications'].help_text = self.nomcom.initial_text

        if not self.public:
            self.fields.pop('confirmation')
            author = get_user_email(self.user)
            if author:
                self.fields['nominator_email'].initial = author.address
                help_text = """(Nomcom Chair/Member: please fill this in. Use your own email address if the person making the
                               nomination wishes to be anonymous. The confirmation email will be sent to the address given here,
                               and the address will also be captured as part of the registered nomination.)"""
                self.fields['nominator_email'].help_text = help_text
                self.fields['share_nominator'].help_text = """(Nomcom Chair/Member: Check this box if the person providing this nomination
                                                              has indicated they will allow NomCom to share their name as one of the people
                                                              nominating this candidate."""
        else:
            self.fields.pop('nominator_email')


    def clean_candidate_email(self):
        candidate_email = self.cleaned_data['candidate_email']
        if Email.objects.filter(address=candidate_email).exists():
            normal_url_name = 'nomcom_%s_nominate' % 'public' if self.public else 'private'
            msg = '%s is already in the datatracker. \
                   Use the <a href="%s">normal nomination form</a> to nominate the person \
                   with this address.\
                  ' % (candidate_email,reverse(normal_url_name,kwargs={'year':self.nomcom.year()}))
            raise forms.ValidationError(mark_safe(msg))
        return candidate_email

    def save(self, commit=True):
        # Create nomination
        nomination = super(NominateNewPersonForm, self).save(commit=False)
        nominator_email = self.cleaned_data.get('nominator_email', None)
        candidate_email = self.cleaned_data['candidate_email']
        candidate_name = self.cleaned_data['candidate_name']
        position = self.cleaned_data['position']
        qualifications = self.cleaned_data['qualifications']
        confirmation = self.cleaned_data.get('confirmation', False)
        share_nominator = self.cleaned_data['share_nominator']
        nomcom_template_path = '/nomcom/%s/' % self.nomcom.group.acronym


        author = None
        if self.public:
            author = get_user_email(self.user)
        else:
            if nominator_email:
                emails = Email.objects.filter(address=nominator_email)
                author = emails and emails[0] or None
        ## This is where it should change - validation of the email field should fail if the email exists
        ## The function should become make_nominee_from_newperson)
        nominee = make_nomineeposition_for_newperson(self.nomcom, candidate_name, candidate_email, position, author)

        # Complete nomination data
        feedback = Feedback.objects.create(nomcom=self.nomcom,
                                           comments=qualifications,
                                           type=FeedbackTypeName.objects.get(slug='nomina'),
                                           user=self.user)
        feedback.positions.add(position)
        feedback.nominees.add(nominee)

        if author:
            nomination.nominator_email = author.address
            feedback.author = author.address
            feedback.save()

        nomination.nominee = nominee
        nomination.comments = feedback
        nomination.share_nominator = share_nominator
        nomination.user = self.user

        if commit:
            nomination.save()

        # send receipt email to nominator
        if confirmation:
            if author:
                subject = 'Nomination receipt'
                from_email = settings.NOMCOM_FROM_EMAIL
                (to_email, cc) = gather_address_lists('nomination_receipt_requested',nominator=author.address)
                context = {'nominee': nominee.email.person.name,
                          'comments': qualifications,
                          'position': position.name}
                path = nomcom_template_path + NOMINATION_RECEIPT_TEMPLATE
                send_mail(None, to_email, from_email, subject, path, context, cc=cc)

        return nomination

    class Meta:
        model = Nomination
        fields = ('share_nominator', 'position', 'nominator_email', 'candidate_name',
                  'candidate_email', 'candidate_phone', 'qualifications', 'confirmation')


class FeedbackForm(forms.ModelForm):
    nominator_email = forms.CharField(label='Commenter email',required=False)

    comments = forms.CharField(label='Comments',
                               widget=forms.Textarea())
    confirmation = forms.BooleanField(label='Email comments back to me as confirmation (if selected, your comments will be emailed to you in cleartext when you press Save).',
                                      required=False)

    def __init__(self, *args, **kwargs):
        self.nomcom = kwargs.pop('nomcom', None)
        self.user = kwargs.pop('user', None)
        self.public = kwargs.pop('public', None)
        self.position = kwargs.pop('position', None)
        self.nominee = kwargs.pop('nominee', None)

        super(FeedbackForm, self).__init__(*args, **kwargs)

        author = get_user_email(self.user)

        if self.public:
            self.fields.pop('nominator_email')
        else:
            help_text = """(Nomcom Chair/Member: please fill this in. Use your own email address if the person making the
                            comments wishes to be anonymous. The confirmation email will be sent to the address given here,
                            and the address will also be captured as part of the registered nomination.)"""
            self.fields['nominator_email'].help_text = help_text
            self.fields['confirmation'].label = 'Email these comments in cleartext to the provided commenter email address' 
            if author:
                self.fields['nominator_email'].initial = author.address


    def clean(self):
        if not NomineePosition.objects.accepted().filter(nominee=self.nominee,
                                                    position=self.position):
            msg = "There isn't a accepted nomination for %s on the %s position" % (self.nominee, self.position)
            self._errors["comments"] = self.error_class([msg])
        return self.cleaned_data

    def save(self, commit=True):
        feedback = super(FeedbackForm, self).save(commit=False)
        confirmation = self.cleaned_data['confirmation']
        comments = self.cleaned_data['comments']
        nomcom_template_path = '/nomcom/%s/' % self.nomcom.group.acronym

        author = None
        if self.public:
            author = get_user_email(self.user)
        else:
            nominator_email = self.cleaned_data['nominator_email']
            if nominator_email:
                emails = Email.objects.filter(address=nominator_email)
                author = emails and emails[0] or None

        if author:
            feedback.author = author.address

        feedback.nomcom = self.nomcom
        feedback.user = self.user
        feedback.type = FeedbackTypeName.objects.get(slug='comment')
        feedback.save()
        feedback.positions.add(self.position)
        feedback.nominees.add(self.nominee)

        # send receipt email to feedback author
        if confirmation:
            if author:
                subject = "NomCom comment confirmation"
                from_email = settings.NOMCOM_FROM_EMAIL
                (to_email, cc) = gather_address_lists('nomcom_comment_receipt_requested',commenter=author.address)
                context = {'nominee': self.nominee.email.person.name,
                           'comments': comments,
                           'position': self.position.name}
                path = nomcom_template_path + FEEDBACK_RECEIPT_TEMPLATE
                send_mail(None, to_email, from_email, subject, path, context, cc=cc)

    class Meta:
        model = Feedback
        fields = (
                  'nominator_email',
                  'comments',
                  'confirmation',
                 )

class FeedbackEmailForm(forms.Form):

    email_text = forms.CharField(label='Email text', widget=forms.Textarea())

    def __init__(self, *args, **kwargs):
        self.nomcom = kwargs.pop('nomcom', None)
        super(FeedbackEmailForm, self).__init__(*args, **kwargs)

    def save(self, commit=True):
        create_feedback_email(self.nomcom, self.cleaned_data['email_text'])

class QuestionnaireForm(forms.ModelForm):

    comments = forms.CharField(label='Questionnaire response from this candidate',
                               widget=forms.Textarea())
    def __init__(self, *args, **kwargs):
        self.nomcom = kwargs.pop('nomcom', None)
        self.user = kwargs.pop('user', None)

        super(QuestionnaireForm, self).__init__(*args, **kwargs)
        self.fields['nominee'] = PositionNomineeField(nomcom=self.nomcom, required=True)

    def save(self, commit=True):
        feedback = super(QuestionnaireForm, self).save(commit=False)
        (position, nominee) = self.cleaned_data['nominee']

        author = get_user_email(self.user)

        if author:
            feedback.author = author

        feedback.nomcom = self.nomcom
        feedback.user = self.user
        feedback.type = FeedbackTypeName.objects.get(slug='questio')
        feedback.save()
        self.save_m2m()
        feedback.nominees.add(nominee)
        feedback.positions.add(position)

    class Meta:
        model = Feedback
        fields = ( 'comments', )

class NomComTemplateForm(DBTemplateForm):
    content = forms.CharField(label="Text", widget=forms.Textarea(attrs={'cols': '120', 'rows':'40', }))

class PositionForm(forms.ModelForm):

    class Meta:
        model = Position
        fields = ('name', 'is_open')

    def __init__(self, *args, **kwargs):
        self.nomcom = kwargs.pop('nomcom', None)
        super(PositionForm, self).__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        self.instance.nomcom = self.nomcom
        super(PositionForm, self).save(*args, **kwargs)


class PrivateKeyForm(forms.Form):

    key = forms.CharField(label='Private key', widget=forms.Textarea(), required=False)

    def clean_key(self):
        key = self.cleaned_data.get('key', None)
        if not key:
            return
        (validation, error) = validate_private_key(key)
        if validation:
            return key
        raise forms.ValidationError('Invalid private key. Error was: %s' % error)


class PendingFeedbackForm(forms.ModelForm):

    type = forms.ModelChoiceField(queryset=FeedbackTypeName.objects.all().order_by('pk'), widget=forms.RadioSelect, empty_label='Unclassified', required=False)

    class Meta:
        model = Feedback
        fields = ('type', )

    def set_nomcom(self, nomcom, user):
        self.nomcom = nomcom
        self.user = user
        #self.fields['nominee'] = MultiplePositionNomineeField(nomcom=self.nomcom,
                                                              #required=True,
                                                              #widget=forms.SelectMultiple,
                                                              #help_text='Hold down "Control", or "Command" on a Mac, to select more than one.')

    def save(self, commit=True):
        feedback = super(PendingFeedbackForm, self).save(commit=False)
        feedback.nomcom = self.nomcom
        feedback.user = self.user
        feedback.save()
        return feedback

class ReminderDatesForm(forms.ModelForm):

    class Meta:
        model = ReminderDates
        fields = ('date',)

    def __init__(self, *args, **kwargs):
        super(ReminderDatesForm, self).__init__(*args, **kwargs)
        self.fields['date'].required = False


class MutableFeedbackForm(forms.ModelForm):

    type = forms.ModelChoiceField(queryset=FeedbackTypeName.objects.all(), widget=forms.HiddenInput)

    class Meta:
        model = Feedback
        fields = ('type', )

    def set_nomcom(self, nomcom, user, instances=None):
        self.nomcom = nomcom
        self.user = user
        instances = instances or []
        self.feedback_type = None
        for i in instances:
            if i.id == self.instance.id:
                self.feedback_type = i.type
                break
        self.feedback_type = self.feedback_type or self.fields['type'].clean(self.fields['type'].widget.value_from_datadict(self.data, self.files, self.add_prefix('type')))

        self.initial['type'] = self.feedback_type

        if self.feedback_type.slug != 'nomina':
            self.fields['nominee'] = MultiplePositionNomineeField(nomcom=self.nomcom,
                                                                  required=True,
                                                                  widget=forms.SelectMultiple(attrs={'class':'nominee_multi_select','size':'12'}),
                                                                  help_text='Hold down "Control", or "Command" on a Mac, to select more than one.')
        else:
            self.fields['position'] = forms.ModelChoiceField(queryset=Position.objects.get_by_nomcom(self.nomcom).opened(), label="Position")
            self.fields['searched_email'] = SearchableEmailField(only_users=False,help_text="Try to find the candidate you are classifying with this field first. Only use the name and email fields below if this search does not find the candidate.",label="Candidate",required=False)
            self.fields['candidate_name'] = forms.CharField(label="Candidate name",help_text="Only fill in this name field if the search doesn't find the person you are classifying",required=False)
            self.fields['candidate_email'] = forms.EmailField(label="Candidate email",help_text="Only fill in this email field if the search doesn't find the person you are classifying",required=False)
            self.fields['candidate_phone'] = forms.CharField(label="Candidate phone", required=False)

    def clean(self):
        cleaned_data = super(MutableFeedbackForm,self).clean()
        if self.feedback_type.slug == 'nomina':
            searched_email = self.cleaned_data.get('searched_email')
            candidate_name = self.cleaned_data.get('candidate_name')
            if candidate_name:
                candidate_name = candidate_name.strip()
            candidate_email = self.cleaned_data.get('candidate_email') 
            if candidate_email:
                candidate_email = candidate_email.strip()
            
            if not any([ searched_email and not candidate_name and not candidate_email,
                         not searched_email and candidate_name and candidate_email,
                      ]):
                raise forms.ValidationError("You must identify either an existing person (by searching with the candidate field) and leave the name and email fields blank, or leave the search field blank and provide both a name and email address.")
            if candidate_email and Email.objects.filter(address=candidate_email).exists():
                raise forms.ValidationError("%s already exists in the datatracker. Please search within the candidate field to find it and leave both the name and email fields blank." % candidate_email)
        return cleaned_data

    def save(self, commit=True):
        feedback = super(MutableFeedbackForm, self).save(commit=False)
        if self.instance.type.slug == 'nomina':
            searched_email = self.cleaned_data['searched_email']
            candidate_email = self.cleaned_data['candidate_email']
            candidate_name = self.cleaned_data['candidate_name']
            candidate_phone = self.cleaned_data['candidate_phone']
            position = self.cleaned_data['position']

            nominator_email = feedback.author
            feedback.save()

            emails = Email.objects.filter(address=nominator_email)
            author = emails and emails[0] or None

            if searched_email:
                nominee = make_nomineeposition(self.nomcom, searched_email.person, position, author)
            else:
                nominee = make_nomineeposition_for_newperson(self.nomcom, candidate_name, candidate_email, position, author)
            feedback.nominees.add(nominee)
            feedback.positions.add(position)
            Nomination.objects.create(
                position=self.cleaned_data.get('position'),
                candidate_name=candidate_name,
                candidate_email=candidate_email,
                candidate_phone=candidate_phone,
                nominee=nominee,
                comments=feedback,
                nominator_email=nominator_email,
                user=self.user)
            return feedback
        else:
            feedback.save()
            self.save_m2m()
            for (position, nominee) in self.cleaned_data['nominee']:
                feedback.nominees.add(nominee)
                feedback.positions.add(position)
        return feedback


FullFeedbackFormSet = forms.modelformset_factory(
        model=Feedback,
        extra=0,
        max_num=0,
        form=MutableFeedbackForm,
        can_order=False,
        can_delete=False,
        fields=('type',),
    )


class EditNomineeForm(forms.ModelForm):

    nominee_email = forms.ModelChoiceField(queryset=Email.objects.none(),empty_label=None)

    def __init__(self, *args, **kwargs):
        super(EditNomineeForm, self).__init__(*args, **kwargs)
        self.fields['nominee_email'].queryset = Email.objects.filter(person=self.instance.person,active=True)
        self.fields['nominee_email'].initial = self.instance.email
        self.fields['nominee_email'].help_text = "If the address you are looking for does not appear in this list, ask the nominee (or the secretariat) to add the address to their datatracker account and ensure it is marked as active."

    def save(self, commit=True):
        nominee = super(EditNomineeForm, self).save(commit=False)
        nominee_email = self.cleaned_data.get("nominee_email")
        nominee.email = nominee_email
        nominee.save()
        return nominee

    class Meta:
        model = Nominee
        fields = ('nominee_email',)

class NominationResponseCommentForm(forms.Form):
    comments = forms.CharField(widget=forms.Textarea,required=False,help_text="Any comments provided will be encrytped and will only be visible to the NomCom.")

