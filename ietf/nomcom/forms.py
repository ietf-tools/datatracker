from django.conf import settings
from django import forms
from django.contrib.formtools.preview import FormPreview, AUTO_ID
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.shortcuts import render_to_response
from django.template.context import RequestContext

from ietf.dbtemplate.forms import DBTemplateForm
from ietf.group.models import Group, Role
from ietf.ietfauth.utils import role_required
from ietf.name.models import RoleName, FeedbackTypeName, NomineePositionStateName
from ietf.nomcom.models import ( NomCom, Nomination, Nominee, NomineePosition,
                                 Position, Feedback, ReminderDates )
from ietf.nomcom.utils import (NOMINATION_RECEIPT_TEMPLATE, FEEDBACK_RECEIPT_TEMPLATE,
                               get_user_email, validate_private_key, validate_public_key,
                               get_or_create_nominee, create_feedback_email)
from ietf.person.models import Email
from ietf.person.fields import SearchableEmailField
from ietf.utils.fields import MultiEmailField
from ietf.utils.mail import send_mail
from ietf.mailtrigger.utils import gather_address_lists


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
            nominees = [('%s_%s' % (position.id, i.id), unicode(i)) for i in Nominee.objects.get_by_nomcom(self.nomcom).not_duplicated().filter(nominee_position=position).select_related("email", "email__person")]
            if nominees:
                results.append((position.name, nominees))
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
        nominees = super(PositionNomineeField, self).clean(value)
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


class BaseNomcomForm(object):
    def __unicode__(self):
        return self.as_div()

    def as_div(self):
        return render_to_string('nomcom/nomcomform.html', {'form': self})

    def get_fieldsets(self):
        if not self.fieldsets:
            yield dict(name=None, fields=self)
        else:
            for fieldset, fields in self.fieldsets:
                fieldset_dict = dict(name=fieldset, fields=[])
                for field_name in fields:
                    if field_name in self.fields:
                        fieldset_dict['fields'].append(self[field_name])
                    if not fieldset_dict['fields']:
                        # if there is no fields in this fieldset, we continue to next fieldset
                        continue
                yield fieldset_dict


class EditMembersForm(BaseNomcomForm, forms.Form):

    members = MultiEmailField(label="Members email", required=False, widget=forms.Textarea)

    fieldsets = [('Members', ('members',))]


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


class EditNomcomForm(BaseNomcomForm, forms.ModelForm):

    fieldsets = [('Edit nomcom settings', ('public_key', 'initial_text',
                                           'send_questionnaire', 'reminder_interval'))]

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


class MergeForm(BaseNomcomForm, forms.Form):

    secondary_emails = MultiEmailField(label="Secondary email addresses",
        help_text="Provide a comma separated list of email addresses. Nominations already received with any of these email address will be moved to show under the primary address.", widget=forms.Textarea)
    primary_email = forms.EmailField(label="Primary email address",
                                     widget=forms.TextInput(attrs={'size': '40'}))

    fieldsets = [('Emails', ('primary_email', 'secondary_emails'))]

    def __init__(self, *args, **kwargs):
        self.nomcom = kwargs.pop('nomcom', None)
        super(MergeForm, self).__init__(*args, **kwargs)

    def clean_primary_email(self):
        email = self.cleaned_data['primary_email']
        nominees = Nominee.objects.get_by_nomcom(self.nomcom).not_duplicated().filter(email__address=email)
        if not nominees:
            msg = "No nominee with this email exists"
            self._errors["primary_email"] = self.error_class([msg])

        return email

    def clean_secondary_emails(self):
        emails = self.cleaned_data['secondary_emails']
        for email in emails:
            nominees = Nominee.objects.get_by_nomcom(self.nomcom).not_duplicated().filter(email__address=email)
            if not nominees:
                msg = "No nominee with email %s exists" % email
                self._errors["primary_email"] = self.error_class([msg])
            break

        return emails

    def clean(self):
        primary_email = self.cleaned_data.get("primary_email")
        secondary_emails = self.cleaned_data.get("secondary_emails")
        if primary_email and secondary_emails:
            if primary_email in secondary_emails:
                msg = "Primary and secondary email address must be differents"
                self._errors["primary_email"] = self.error_class([msg])
        return self.cleaned_data

    def save(self):
        primary_email = self.cleaned_data.get("primary_email")
        secondary_emails = self.cleaned_data.get("secondary_emails")

        primary_nominee = Nominee.objects.get_by_nomcom(self.nomcom).get(email__address=primary_email)
        while primary_nominee.duplicated:
            primary_nominee = primary_nominee.duplicated
        secondary_nominees = Nominee.objects.get_by_nomcom(self.nomcom).filter(email__address__in=secondary_emails)
        for nominee in secondary_nominees:
            # move nominations
            nominee.nomination_set.all().update(nominee=primary_nominee)
            # move feedback
            for fb in nominee.feedback_set.all():
                fb.nominees.remove(nominee)
                fb.nominees.add(primary_nominee)
            # move nomineepositions
            for nominee_position in nominee.nomineeposition_set.all():
                primary_nominee_positions = NomineePosition.objects.filter(position=nominee_position.position,
                                                                           nominee=primary_nominee)
                primary_nominee_position = primary_nominee_positions and primary_nominee_positions[0] or None

                if primary_nominee_position:
                    # if already a nomineeposition object for a position and nominee,
                    # update the nomineepostion of primary nominee with the state
                    if nominee_position.state.slug == 'accepted' or primary_nominee_position.state.slug == 'accepted':
                        primary_nominee_position.state = NomineePositionStateName.objects.get(slug='accepted')
                        primary_nominee_position.save()
                    if nominee_position.state.slug == 'declined' and primary_nominee_position.state.slug == 'pending':
                        primary_nominee_position.state = NomineePositionStateName.objects.get(slug='declined')
                        primary_nominee_position.save()
                else:
                    # It is not allowed two or more nomineeposition objects with same position and nominee
                    # move nominee_position object to primary nominee
                    nominee_position.nominee = primary_nominee
                    nominee_position.save()

            nominee.duplicated = primary_nominee
            nominee.save()

        secondary_nominees.update(duplicated=primary_nominee)


class NominateForm(BaseNomcomForm, forms.ModelForm):
    comments = forms.CharField(label="Candidate's qualifications for the position",
                               widget=forms.Textarea())
    confirmation = forms.BooleanField(label='Email comments back to me as confirmation',
                                      help_text="If you want to get a confirmation mail containing your feedback in cleartext, please check the 'email comments back to me as confirmation'.",
                                      required=False)

    fieldsets = [('Candidate Nomination', ('share_nominator','position', 'candidate_name',
                  'candidate_email', 'candidate_phone', 'comments', 'confirmation'))]

    def __init__(self, *args, **kwargs):
        self.nomcom = kwargs.pop('nomcom', None)
        self.user = kwargs.pop('user', None)
        self.public = kwargs.pop('public', None)

        super(NominateForm, self).__init__(*args, **kwargs)

        fieldset = ['share_nominator',
                    'position',
                    'candidate_name',
                    'candidate_email', 'candidate_phone',
                    'comments']

        self.fields['nominator_email'].label = 'Nominator email'
        if self.nomcom:
            self.fields['position'].queryset = Position.objects.get_by_nomcom(self.nomcom).opened()
            self.fields['comments'].help_text = self.nomcom.initial_text

        if not self.public:
            fieldset = ['nominator_email'] + fieldset
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
            fieldset.append('confirmation')

        self.fieldsets = [('Candidate Nomination', fieldset)]

    def save(self, commit=True):
        # Create nomination
        nomination = super(NominateForm, self).save(commit=False)
        nominator_email = self.cleaned_data.get('nominator_email', None)
        candidate_email = self.cleaned_data['candidate_email']
        candidate_name = self.cleaned_data['candidate_name']
        position = self.cleaned_data['position']
        comments = self.cleaned_data['comments']
        confirmation = self.cleaned_data['confirmation']
        share_nominator = self.cleaned_data['share_nominator']
        nomcom_template_path = '/nomcom/%s/' % self.nomcom.group.acronym

        author = None
        if self.public:
            author = get_user_email(self.user)
        else:
            if nominator_email:
                emails = Email.objects.filter(address=nominator_email)
                author = emails and emails[0] or None
        nominee = get_or_create_nominee(self.nomcom, candidate_name, candidate_email, position, author)

        # Complete nomination data
        feedback = Feedback.objects.create(nomcom=self.nomcom,
                                           comments=comments,
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
                          'comments': comments,
                          'position': position.name}
                path = nomcom_template_path + NOMINATION_RECEIPT_TEMPLATE
                send_mail(None, to_email, from_email, subject, path, context, cc=cc)

        return nomination

    class Meta:
        model = Nomination
        fields = ('share_nominator', 'position', 'nominator_email', 'candidate_name',
                  'candidate_email', 'candidate_phone')


class FeedbackForm(BaseNomcomForm, forms.ModelForm):
    position_name = forms.CharField(label='Position',
                                    widget=forms.TextInput(attrs={'size': '40'}))
    nominee_name = forms.CharField(label='Nominee name',
                                   widget=forms.TextInput(attrs={'size': '40'}))
    nominee_email = forms.CharField(label='Nominee email',
                                    widget=forms.TextInput(attrs={'size': '40'}))
    nominator_email = forms.CharField(label='Commenter email')

    comments = forms.CharField(label='Comments on this nominee',
                               widget=forms.Textarea())
    confirmation = forms.BooleanField(label='Email comments back to me as confirmation',
                                      help_text="If you want to get a confirmation mail containing your feedback in cleartext, please check the 'email comments back to me as confirmation'.",
                                      required=False)

    def __init__(self, *args, **kwargs):
        self.nomcom = kwargs.pop('nomcom', None)
        self.user = kwargs.pop('user', None)
        self.public = kwargs.pop('public', None)
        self.position = kwargs.pop('position', None)
        self.nominee = kwargs.pop('nominee', None)

        super(FeedbackForm, self).__init__(*args, **kwargs)

        readonly_fields = ['position_name',
                           'nominee_name',
                           'nominee_email']

        fieldset = ['position_name',
                    'nominee_name',
                    'nominee_email',
                    'nominator_email',
                    'comments']

        if self.public:
            readonly_fields += ['nominator_email']
            fieldset.append('confirmation')
        else:
            help_text = """(Nomcom Chair/Member: please fill this in. Use your own email address if the person making the
                            comments wishes to be anonymous. The confirmation email will be sent to the address given here,
                            and the address will also be captured as part of the registered nomination.)"""
            self.fields['nominator_email'].help_text = help_text
            self.fields['nominator_email'].required = False

        author = get_user_email(self.user)
        if author:
            self.fields['nominator_email'].initial = author.address

        if self.position and self.nominee:
            self.fields['position_name'].initial = self.position.name
            self.fields['nominee_name'].initial = self.nominee.email.person.name
            self.fields['nominee_email'].initial = self.nominee.email.address
        else:
            help_text = "Please pick a name on the nominees list"
            self.fields['position_name'].initial = help_text
            self.fields['nominee_name'].initial = help_text
            self.fields['nominee_email'].initial = help_text
            self.fields['comments'].initial = help_text
            readonly_fields += ['comments']
            self.fields['confirmation'].widget.attrs['disabled'] = "disabled"

        for field in readonly_fields:
            self.fields[field].widget.attrs['readonly'] = True

        self.fieldsets = [('Provide comments', fieldset)]

    def clean(self):
        if not NomineePosition.objects.accepted().filter(nominee=self.nominee,
                                                    position=self.position):
            msg = "There isn't a accepted nomination for %s on the %s position" % (self.nominee, self.position)
            self._errors["nominee_email"] = self.error_class([msg])
        return self.cleaned_data

    def save(self, commit=True):
        feedback = super(FeedbackForm, self).save(commit=False)
        confirmation = self.cleaned_data['confirmation']
        comments = self.cleaned_data['comments']
        nominator_email = self.cleaned_data['nominator_email']
        nomcom_template_path = '/nomcom/%s/' % self.nomcom.group.acronym

        author = None
        if self.public:
            author = get_user_email(self.user)
        else:
            if nominator_email:
                emails = Email.objects.filter(address=nominator_email)
                author = emails and emails[0] or None

        if author:
            feedback.author = author

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
        fields = ('nominee_name',
                  'nominee_email',
                  'nominator_email',
                  'confirmation',
                  'comments')

class FeedbackEmailForm(BaseNomcomForm, forms.Form):

    email_text = forms.CharField(label='Email text', widget=forms.Textarea())

    fieldsets = [('Feedback email', ('email_text',))]

    def __init__(self, *args, **kwargs):
        self.nomcom = kwargs.pop('nomcom', None)
        super(FeedbackEmailForm, self).__init__(*args, **kwargs)

    def save(self, commit=True):
        create_feedback_email(self.nomcom, self.cleaned_data['email_text'])

class QuestionnaireForm(BaseNomcomForm, forms.ModelForm):

    comments = forms.CharField(label='Questionnaire response from this candidate',
                               widget=forms.Textarea())
    fieldsets = [('New questionnaire response', ('nominee', 'comments'))]

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

class NomComTemplateForm(BaseNomcomForm, DBTemplateForm):
    content = forms.CharField(label="Text", widget=forms.Textarea(attrs={'cols': '120', 'rows':'40', }))
    fieldsets = [('Template content', ('content', )), ]


class PositionForm(BaseNomcomForm, forms.ModelForm):

    fieldsets = [('Position', ('name', 'description',
                               'is_open', 'incumbent'))]

    incumbent = SearchableEmailField(required=False)

    class Meta:
        model = Position
        fields = ('name', 'description', 'is_open', 'incumbent')

    def __init__(self, *args, **kwargs):
        self.nomcom = kwargs.pop('nomcom', None)
        super(PositionForm, self).__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        self.instance.nomcom = self.nomcom
        super(PositionForm, self).save(*args, **kwargs)


class PrivateKeyForm(BaseNomcomForm, forms.Form):

    key = forms.CharField(label='Private key', widget=forms.Textarea(), required=False)

    fieldsets = [('Private key', ('key',))]

    def clean_key(self):
        key = self.cleaned_data.get('key', None)
        if not key:
            return
        (validation, error) = validate_private_key(key)
        if validation:
            return key
        raise forms.ValidationError('Invalid private key. Error was: %s' % error)


class PendingFeedbackForm(BaseNomcomForm, forms.ModelForm):

    type = forms.ModelChoiceField(queryset=FeedbackTypeName.objects.all().order_by('pk'), widget=forms.RadioSelect, empty_label='Unclassified', required=False)

    class Meta:
        model = Feedback
        fields = ('type', )

    def __init__(self, *args, **kwargs):
        super(PendingFeedbackForm, self).__init__(*args, **kwargs)
        try:
            self.default_type = FeedbackTypeName.objects.get(slug=settings.DEFAULT_FEEDBACK_TYPE)
        except FeedbackTypeName.DoesNotExist:
            self.default_type = None

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

    def move_to_default(self):
        if not self.default_type or self.cleaned_data.get('type', None):
            return None
        feedback = super(PendingFeedbackForm, self).save(commit=False)
        feedback.nomcom = self.nomcom
        feedback.user = self.user
        feedback.type = self.default_type
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
                                                                  widget=forms.SelectMultiple,
                                                                  help_text='Hold down "Control", or "Command" on a Mac, to select more than one.')
        else:
            self.fields['position'] = forms.ModelChoiceField(queryset=Position.objects.get_by_nomcom(self.nomcom).opened(), label="Position")
            self.fields['candidate_name'] = forms.CharField(label="Candidate name")
            self.fields['candidate_email'] = forms.EmailField(label="Candidate email")
            self.fields['candidate_phone'] = forms.CharField(label="Candidate phone", required=False)

    def save(self, commit=True):
        feedback = super(MutableFeedbackForm, self).save(commit=False)
        if self.instance.type.slug == 'nomina':
            candidate_email = self.cleaned_data['candidate_email']
            candidate_name = self.cleaned_data['candidate_name']
            candidate_phone = self.cleaned_data['candidate_phone']
            position = self.cleaned_data['position']

            nominator_email = feedback.author
            feedback.save()

            emails = Email.objects.filter(address=nominator_email)
            author = emails and emails[0] or None

            nominee = get_or_create_nominee(self.nomcom, candidate_name, candidate_email, position, author)
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

    nominee_email = forms.EmailField(label="Nominee email",
                                     widget=forms.TextInput(attrs={'size': '40'}))

    def __init__(self, *args, **kwargs):
        super(EditNomineeForm, self).__init__(*args, **kwargs)
        self.fields['nominee_email'].initial = self.instance.email.address

    def save(self, commit=True):
        nominee = super(EditNomineeForm, self).save(commit=False)
        nominee_email = self.cleaned_data.get("nominee_email")
        if nominee_email != nominee.email.address:
            # create a new nominee with the new email
            new_email, created_email = Email.objects.get_or_create(address=nominee_email)
            new_email.person = nominee.email.person
            new_email.save()

            # Chage emails between nominees
            old_email = nominee.email
            nominee.email = new_email
            nominee.save()
            new_nominee = Nominee.objects.create(email=old_email, nomcom=nominee.nomcom)

            # new nominees point to old nominee
            new_nominee.duplicated = nominee
            new_nominee.save()

        return nominee

    class Meta:
        model = Nominee
        fields = ('nominee_email',)

    def clean_nominee_email(self):
        nominee_email = self.cleaned_data['nominee_email']
        nominees = Nominee.objects.exclude(email__address=self.instance.email.address).filter(email__address=nominee_email)
        if nominees:
            raise forms.ValidationError('This emails already does exists in another nominee, please go to merge form')
        return nominee_email
