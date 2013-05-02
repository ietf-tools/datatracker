import datetime

from django.conf import settings
from django import forms
from django.contrib.formtools.preview import FormPreview, AUTO_ID
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.core.urlresolvers import reverse
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.contrib.sites.models import Site

from ietf.dbtemplate.forms import DBTemplateForm
from ietf.utils import unaccent
from ietf.utils.mail import send_mail, send_mail_text
from ietf.ietfauth.decorators import role_required
from ietf.utils import fields as custom_fields
from ietf.group.models import Group, Role
from ietf.name.models import RoleName, FeedbackType
from ietf.person.models import Email, Person
from ietf.nomcom.models import NomCom, Nomination, Nominee, NomineePosition, \
                               Position, Feedback
from ietf.nomcom.utils import QUESTIONNAIRE_TEMPLATE, NOMINATION_EMAIL_TEMPLATE, \
                              INEXISTENT_PERSON_TEMPLATE, NOMINEE_EMAIL_TEMPLATE, \
                              NOMINATION_RECEIPT_TEMPLATE, FEEDBACK_RECEIPT_TEMPLATE, \
                              get_user_email, get_hash_nominee_position, get_year_by_nomcom, \
                              HEADER_QUESTIONNAIRE_TEMPLATE
from ietf.nomcom.decorators import member_required

ROLODEX_URL = getattr(settings, 'ROLODEX_URL', None)


def get_group_or_404(year):
    return get_object_or_404(Group,
                             acronym__icontains=year,
                             state__slug='active',
                             nomcom__isnull=False)


def get_list(string):
        return map(unicode.strip, string.replace('\r\n', '').split(','))


class PositionNomineeField(forms.ChoiceField):

    def __init__(self, *args, **kwargs):
        self.nomcom = kwargs.pop('nomcom')
        positions = Position.objects.get_by_nomcom(self.nomcom).opened().order_by('name')
        results = []
        for position in positions:
            nominees = [('%s_%s' % (position.id, i.id), unicode(i)) for i in Nominee.objects.get_by_nomcom(self.nomcom).not_duplicated().filter(nominee_position=position)]
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
                    if field_name in self.fields.keyOrder:
                        fieldset_dict['fields'].append(self[field_name])
                    if not fieldset_dict['fields']:
                        # if there is no fields in this fieldset, we continue to next fieldset
                        continue
                yield fieldset_dict


class EditMembersForm(BaseNomcomForm, forms.Form):

    members = custom_fields.MultiEmailField(label="Members email", required=False)

    fieldsets = [('Members', ('members',))]


class EditMembersFormPreview(FormPreview):
    form_template = 'nomcom/edit_members.html'
    preview_template = 'nomcom/edit_members_preview.html'

    @method_decorator(member_required(role='chair'))
    def __call__(self, request, *args, **kwargs):
        year = kwargs['year']
        group = get_group_or_404(year)
        self.state['group'] = group
        self.state['rolodex_url'] = ROLODEX_URL
        self.group = group
        self.year = year

        return super(EditMembersFormPreview, self).__call__(request, *args, **kwargs)

    def preview_get(self, request):
        "Displays the form"
        f = self.form(auto_id=AUTO_ID)
        return render_to_response(self.form_template,
                                  {'form': f,
                                  'stage_field': self.unused_name('stage'),
                                  'state': self.state,
                                  'year': self.year,
                                  'selected': 'edit_members'},
                                  context_instance=RequestContext(request))

    def parse_params(self, *args, **kwargs):
        members = self.group.role_set.filter(name__slug='member')

        if members:
            self.form.base_fields['members'].initial = ',\r\n'.join([role.email.address for role in members])

    def process_preview(self, request, form, context):
        members_email = get_list(form.cleaned_data['members'])

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
        if f.is_valid():
            if self.security_hash(request, f) != request.POST.get(self.unused_name('hash')):
                return self.failed_hash(request)  # Security hash failed.
            return self.done(request, f.cleaned_data)
        else:
            return render_to_response(self.form_template,
                {'form': f, 'stage_field': self.unused_name('stage'), 'state': self.state,
                 'year': self.year},
                context_instance=RequestContext(request))

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

        return HttpResponseRedirect(reverse('nomcom_edit_members', kwargs={'year': self.year}))


class EditChairForm(BaseNomcomForm, forms.Form):

    chair = forms.EmailField(label="Chair email", required=False,
                             widget=forms.TextInput(attrs={'size': '40'}))

    fieldsets = [('Chair info', ('chair',))]


class EditChairFormPreview(FormPreview):
    form_template = 'nomcom/edit_chair.html'
    preview_template = 'nomcom/edit_chair_preview.html'

    @method_decorator(role_required("Secretariat"))
    def __call__(self, request, *args, **kwargs):
        year = kwargs['year']
        group = get_group_or_404(year)
        self.state['group'] = group
        self.state['rolodex_url'] = ROLODEX_URL
        self.group = group
        self.year = year

        return super(EditChairFormPreview, self).__call__(request, *args, **kwargs)

    def parse_params(self, *args, **kwargs):
        chair = self.group.get_chair()
        if chair:
            self.form.base_fields['chair'].initial = chair.email.address

    def process_preview(self, request, form, context):
        chair_email = form.cleaned_data['chair']
        try:
            chair_email_obj = Email.objects.get(address=chair_email)
            chair_person = chair_email_obj.person
        except Email.DoesNotExist:
            chair_person = None
            chair_email_obj = None
        chair_info = {'email': chair_email,
                      'email_obj': chair_email_obj,
                      'person': chair_person}

        self.state.update({'chair_info': chair_info})

    def done(self, request, cleaned_data):
        chair_info = self.state['chair_info']
        chair_exclude = self.group.role_set.filter(name__slug='chair').exclude(email__address=chair_info['email'])
        chair_exclude.delete()
        if chair_info['email_obj'] and chair_info['person']:
            Role.objects.get_or_create(name=RoleName.objects.get(slug="chair"),
                                      group=self.group,
                                      person=chair_info['person'],
                                      email=chair_info['email_obj'])

        return HttpResponseRedirect(reverse('nomcom_edit_chair', kwargs={'year': self.year}))


class EditNomcomForm(BaseNomcomForm, forms.ModelForm):

    fieldsets = [('Edit nomcom', ('public_key', 'send_questionnaire', 'reminder_interval'))]

    class Meta:
        model = NomCom
        fields = ('public_key', 'send_questionnaire', 'reminder_interval')


class MergeForm(BaseNomcomForm, forms.Form):

    secondary_emails = custom_fields.MultiEmailField(label="Secondary email address (remove this):")
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
            msg = "Does not exist a nomiee with this email"
            self._errors["primary_email"] = self.error_class([msg])

        return email

    def clean_secondary_emails(self):
        data = self.cleaned_data['secondary_emails']
        emails = get_list(data)
        for email in emails:
            nominees = Nominee.objects.get_by_nomcom(self.nomcom).not_duplicated().filter(email__address=email)
            if not nominees:
                msg = "Does not exist a nomiee with email %s" % email
                self._errors["primary_email"] = self.error_class([msg])
            break

        return data

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
        secondary_emails = get_list(self.cleaned_data.get("secondary_emails"))

        primary_nominee = Nominee.objects.get_by_nomcom(self.nomcom).get(email__address=primary_email)
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
                    # update the nomineepostion of primary nominee with the state and questionnaire
                    if nominee_position.time > primary_nominee_position.time:
                        primary_nominee_position.state = nominee_position.state
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
    comments = forms.CharField(label="Candidate's Qualifications for the Position:",
                               widget=forms.Textarea())
    confirmation = forms.BooleanField(label='Email comments back to me as confirmation',
                                      help_text="If you want to get a confirmation mail containing your feedback in cleartext, \
                                                 please check the 'email comments back to me as confirmation'",
                                      required=False)

    fieldsets = [('Candidate Nomination', ('position', 'candidate_name',
                  'candidate_email', 'candidate_phone', 'comments', 'confirmation'))]

    def __init__(self, *args, **kwargs):
        self.nomcom = kwargs.pop('nomcom', None)
        self.user = kwargs.pop('user', None)
        self.public = kwargs.pop('public', None)

        super(NominateForm, self).__init__(*args, **kwargs)

        fieldset = ['position',
                    'candidate_name',
                    'candidate_email', 'candidate_phone',
                    'comments']

        if self.nomcom:
            self.fields['position'].queryset = Position.objects.get_by_nomcom(self.nomcom).opened()

        if not self.public:
            fieldset = ['nominator_email'] + fieldset
            author = get_user_email(self.user)
            if author:
                self.fields['nominator_email'].initial = author.address
                help_text = """(Nomcom Chair/Member: please fill this in. Use your own email address if the person making the
                               nomination wishes to be anonymous. The confirmation email will be sent to the address given here,
                               and the address will also be captured as part of the registered nomination.)"""
                self.fields['nominator_email'].help_text = help_text
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
        nomcom_template_path = '/nomcom/%s/' % self.nomcom.group.acronym
        nomcom_chair = self.nomcom.group.get_chair()
        nomcom_chair_mail = nomcom_chair and nomcom_chair.email.address or None

        # Create person and email if candidate email does't exist and send email
        email, created_email = Email.objects.get_or_create(address=candidate_email)
        if created_email:
            email.person = Person.objects.create(name=candidate_name,
                                                 ascii=unaccent.asciify(candidate_name),
                                                 address=candidate_email)
            email.save()

        # Add the nomination for a particular position
        nominee, created = Nominee.objects.get_or_create(email=email, nomcom=self.nomcom)
        nominee_position, nominee_position_created = NomineePosition.objects.get_or_create(position=position, nominee=nominee)

        # Complete nomination data
        feedback = Feedback.objects.create(nomcom=self.nomcom,
                                           comments=comments,
                                           type=FeedbackType.objects.get(slug='nomina'),
                                           user=self.user)
        feedback.positions.add(position)
        feedback.nominees.add(nominee)
        author = None
        if self.public:
            author = get_user_email(self.user)
        else:
            if nominator_email:
                emails = Email.objects.filter(address=nominator_email)
                author = emails and emails[0] or None

        if author:
            nomination.nominator_email = author.address
            feedback.author = author
            feedback.save()

        nomination.nominee = nominee
        nomination.comments = feedback
        nomination.user = self.user

        if commit:
            nomination.save()

        if created_email:
            # send email to secretariat and nomcomchair to warn about the new person
            subject = 'New person is created'
            from_email = settings.NOMCOM_FROM_EMAIL
            to_email = [settings.NOMCOM_ADMIN_EMAIL]
            context = {'email': email.address,
                       'fullname': email.person.name,
                       'person_id': email.person.id}
            path = nomcom_template_path + INEXISTENT_PERSON_TEMPLATE
            if nomcom_chair_mail:
                to_email.append(nomcom_chair_mail)
            send_mail(None, to_email, from_email, subject, path, context)

        # send email to nominee
        if nominee_position_created:
            subject = 'IETF Nomination Information'
            from_email = settings.NOMCOM_FROM_EMAIL
            to_email = email.address
            domain = Site.objects.get_current().domain
            today = datetime.date.today().strftime('%Y%m%d')
            hash = get_hash_nominee_position(today, nominee_position.id)
            accept_url = reverse('nomcom_process_nomination_status',
                                  None,
                                  args=(get_year_by_nomcom(self.nomcom),
                                  nominee_position.id,
                                  'accepted',
                                  today,
                                  hash))
            decline_url = reverse('nomcom_process_nomination_status',
                                  None,
                                  args=(get_year_by_nomcom(self.nomcom),
                                  nominee_position.id,
                                  'declined',
                                  today,
                                  hash))

            context = {'nominee': email.person.name,
                       'position': position.name,
                       'domain': domain,
                       'accept_url': accept_url,
                       'decline_url': decline_url}

            path = nomcom_template_path + NOMINEE_EMAIL_TEMPLATE
            send_mail(None, to_email, from_email, subject, path, context)

        # send email to nominee with questionnaire
        if nominee_position_created:
            if self.nomcom.send_questionnaire:
                subject = '%s Questionnaire' % position
                from_email = settings.NOMCOM_FROM_EMAIL
                to_email = email.address
                context = {'nominee': email.person.name,
                          'position': position.name}
                path = '%s%d/%s' % (nomcom_template_path,
                                    position.id, HEADER_QUESTIONNAIRE_TEMPLATE)
                body = render_to_string(path, context)
                path = '%s%d/%s' % (nomcom_template_path,
                                    position.id, QUESTIONNAIRE_TEMPLATE)
                body += '\n\n%s' % render_to_string(path, context)
                send_mail_text(None, to_email, from_email, subject, body)

        # send emails to nomcom chair
        subject = 'Nomination Information'
        from_email = settings.NOMCOM_FROM_EMAIL
        to_email = nomcom_chair_mail
        context = {'nominee': email.person.name,
                   'nominee_email': email.address,
                   'position': position.name}
        if author:
            context.update({'nominator': author.person.name,
                            'nominator_email': author.address})
        path = nomcom_template_path + NOMINATION_EMAIL_TEMPLATE
        send_mail(None, to_email, from_email, subject, path, context)

        # send receipt email to nominator
        if confirmation:
            if author:
                subject = 'Nomination Receipt'
                from_email = settings.NOMCOM_FROM_EMAIL
                to_email = author.address
                context = {'nominee': email.person.name,
                          'comments': comments,
                          'position': position.name}
                path = nomcom_template_path + NOMINATION_RECEIPT_TEMPLATE
                send_mail(None, to_email, from_email, subject, path, context)

        return nomination

    class Meta:
        model = Nomination
        fields = ('position', 'nominator_email', 'candidate_name',
                  'candidate_email', 'candidate_phone')

    class Media:
        js = ("/js/jquery-1.5.1.min.js",
              "/js/nomcom.js", )


class FeedbackForm(BaseNomcomForm, forms.ModelForm):
    position_name = forms.CharField(label='position',
                                    widget=forms.TextInput(attrs={'size': '40'}))
    nominee_name = forms.CharField(label='nominee name',
                                   widget=forms.TextInput(attrs={'size': '40'}))
    nominee_email = forms.CharField(label='nominee email',
                                    widget=forms.TextInput(attrs={'size': '40'}))
    nominator_name = forms.CharField(label='your name')
    nominator_email = forms.CharField(label='your email')

    comments = forms.CharField(label='Comments on this candidate',
                               widget=forms.Textarea())
    confirmation = forms.BooleanField(label='Email comments back to me as confirmation',
                                      help_text="If you want to get a confirmation mail containing your feedback in cleartext, \
                                                 please check the 'email comments back to me as confirmation'",
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
                    'nominator_name',
                    'nominator_email',
                    'comments']

        if self.public:
            readonly_fields += ['nominator_name', 'nominator_email']
            fieldset.append('confirmation')
        else:
            help_text = """(Nomcom Chair/Member: please fill this in. Use your own email address if the person making the
                            comments wishes to be anonymous. The confirmation email will be sent to the address given here,
                            and the address will also be captured as part of the registered nomination.)"""
            self.fields['nominator_email'].help_text = help_text
            self.fields['nominator_name'].required = False
            self.fields['nominator_email'].required = False

        author = get_user_email(self.user)
        if author:
            self.fields['nominator_email'].initial = author.address
            self.fields['nominator_name'].initial = author.person.name

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
        feedback.type = FeedbackType.objects.get(slug='comment')
        feedback.save()
        feedback.positions.add(self.position)
        feedback.nominees.add(self.nominee)

        # send receipt email to feedback author
        if confirmation:
            if author:
                subject = "NomCom comment confirmation"
                from_email = settings.NOMCOM_FROM_EMAIL
                to_email = author.address
                context = {'nominee': self.nominee.email.person.name,
                           'comments': comments,
                           'position': self.position.name}
                path = nomcom_template_path + FEEDBACK_RECEIPT_TEMPLATE
                send_mail(None, to_email, from_email, subject, path, context)

    class Meta:
        model = Feedback
        fields = ('author',
                  'nominee_name',
                  'nominee_email',
                  'nominator_name',
                  'nominator_email',
                  'confirmation',
                  'comments')

    class Media:
        js = ("/js/jquery-1.5.1.min.js",
              "/js/nomcom.js", )


class QuestionnaireForm(BaseNomcomForm, forms.ModelForm):

    comments = forms.CharField(label='Questionnaire response from this candidate',
                               widget=forms.Textarea())
    fieldsets = [('New questionnaire response', ('nominee',
                                             'comments'))]

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
        feedback.type = FeedbackType.objects.get(slug='questio')
        feedback.save()
        self.save_m2m()
        feedback.nominees.add(nominee)
        feedback.positions.add(position)

    class Meta:
        model = Feedback
        fields = ('nominee',
                  'positions',
                  'comments')

    class Media:
        admin_js = ['js/core.js',
                    "js/jquery.js",
                    "js/jquery.init.js",
                    'js/admin/RelatedObjectLookups.js',
                    "js/getElementsBySelector.js",
                    'js/SelectBox.js',
                    'js/SelectFilter2.js',
                    ]
        admin_js = ['%s%s' % (settings.ADMIN_MEDIA_PREFIX, url) for url in admin_js]
        js = ["/js/jquery-1.5.1.min.js", "/js/nomcom.js"] + admin_js


class NomComTemplateForm(BaseNomcomForm, DBTemplateForm):

    fieldsets = [('Template content', ('content', )), ]


class PositionForm(BaseNomcomForm, forms.ModelForm):

    fieldsets = [('Position', ('name', 'description',
                               'is_open', 'incumbent'))]

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


class PendingFeedbackForm(BaseNomcomForm, forms.ModelForm):

    class Meta:
        model = Feedback
        fields = ('author', 'type', 'nominee')

    def __init__(self, *args, **kwargs):
        super(PendingFeedbackForm, self).__init__(*args, **kwargs)
        self.fields['type'].queryset = FeedbackType.objects.exclude(slug='nomina')

    def set_nomcom(self, nomcom, user):
        self.nomcom = nomcom
        self.user = user
        self.fields['nominee'] = MultiplePositionNomineeField(nomcom=self.nomcom,
                                                              required=True,
                                                              widget=forms.SelectMultiple,
                                                              help_text='Hold down "Control", or "Command" on a Mac, to select more than one.')

    def save(self, commit=True):
        feedback = super(PendingFeedbackForm, self).save(commit=False)

        author = get_user_email(self.user)

        if author:
            feedback.author = author

        feedback.nomcom = self.nomcom
        feedback.user = self.user
        feedback.save()
        self.save_m2m()
        for (position, nominee) in self.cleaned_data['nominee']:
            feedback.nominees.add(nominee)
            feedback.positions.add(position)
