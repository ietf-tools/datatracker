# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from typing import List, Tuple      # pyflakes:ignore

from django.conf import settings
from django import forms
from django.urls import reverse
from django.utils.html import mark_safe # type:ignore
from django.forms.widgets import FileInput

from ietf.dbtemplate.forms import DBTemplateForm
from ietf.name.models import FeedbackTypeName, NomineePositionStateName
from ietf.nomcom.models import ( NomCom, Nomination, Nominee, NomineePosition,
                                 Position, Feedback, ReminderDates, Topic, Volunteer )
from ietf.nomcom.utils import (NOMINATION_RECEIPT_TEMPLATE, FEEDBACK_RECEIPT_TEMPLATE,
                               get_user_email, validate_private_key, validate_public_key,
                               make_nomineeposition, make_nomineeposition_for_newperson,
                               create_feedback_email)
from ietf.person.models import Email
from ietf.person.fields import (SearchableEmailField, SearchableEmailsField,
                                SearchablePersonField, SearchablePersonsField )
from ietf.utils.mail import send_mail
from ietf.mailtrigger.utils import gather_address_lists

import debug                   # pyflakes:ignore


ROLODEX_URL = getattr(settings, 'ROLODEX_URL', None)


class PositionNomineeField(forms.ChoiceField):

    def __init__(self, *args, **kwargs):
        self.nomcom = kwargs.pop('nomcom')
        positions = Position.objects.get_by_nomcom(self.nomcom).filter(is_open=True).order_by('name')
        results = []
        for position in positions:
            accepted_nominees = [np.nominee for np in NomineePosition.objects.filter(position=position,state='accepted').exclude(nominee__duplicated__isnull=False)]
            nominees = [('%s_%s' % (position.id, i.id), str(i)) for i in accepted_nominees]
            if nominees:
                results.append((position.name+" (Accepted)", nominees))
        for position in positions:
            other_nominees = [np.nominee for np in NomineePosition.objects.filter(position=position).exclude(state='accepted').exclude(nominee__duplicated__isnull=False)]
            nominees = [('%s_%s' % (position.id, i.id), str(i)) for i in other_nominees]
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
            position = Position.objects.get_by_nomcom(self.nomcom).filter(is_open=True).get(id=position_id)
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
                position = Position.objects.get_by_nomcom(self.nomcom).filter(is_open=True).get(id=position_id)
            except Position.DoesNotExist:
                raise forms.ValidationError('Invalid nominee')
            try:
                nominee = position.nominee_set.get_by_nomcom(self.nomcom).get(id=nominee_id)
            except Nominee.DoesNotExist:
                raise forms.ValidationError('Invalid nominee')
            result.append((position, nominee))
        return result


class NewEditMembersForm(forms.Form):

    members = SearchableEmailsField(only_users=True,all_emails=True)

class EditNomcomForm(forms.ModelForm):


    def __init__(self, *args, **kwargs):
        super(EditNomcomForm, self).__init__(*args, **kwargs)

        if self.instance:
            if self.instance.public_key:
                help_text = "The nomcom already has a public key. Previous data will remain encrypted with the old key"
            else:
                help_text = "The nomcom does not have a public key yet"
            self.fields['public_key'].help_text = help_text

    class Meta:
        model = NomCom
        fields = ('public_key', 'initial_text', 'show_nominee_pictures', 'show_accepted_nominees',
                  'send_questionnaire', 'reminder_interval')
        widgets = {'public_key':FileInput, }

    def clean_public_key(self):
        public_key = self.cleaned_data.get('public_key', None)
        if not public_key:
            return
        (validation, error) = validate_public_key(public_key)
        if validation:
            return public_key
        raise forms.ValidationError('Invalid public key. Error was: %s' % error)


class MergeNomineeForm(forms.Form):

    primary_email = SearchableEmailField(
        help_text="Select the email of the Nominee record you want to use as the primary record.",
        all_emails = True,
    )
    secondary_emails = SearchableEmailsField(
        help_text="Select all the duplicates that should be consolidated with the primary "
            "Nominee record.  Nominations already received with any of these email address "
            "will be moved to show under the primary address.",
        all_emails = True,
        )

    def __init__(self, *args, **kwargs):
        self.nomcom = kwargs.pop('nomcom', None)
        super(MergeNomineeForm, self).__init__(*args, **kwargs)

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

class MergePersonForm(forms.Form):

    primary_person = SearchablePersonField(help_text="Select the person you want the datatracker to keep")
    duplicate_persons = SearchablePersonsField(help_text="Select all the duplicates that should be merged into the primary person record")

    def __init__(self, *args, **kwargs):
        self.nomcom = kwargs.pop('nomcom', None)
        super(MergePersonForm, self).__init__(*args, **kwargs)

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
        from_email = settings.NOMCOM_FROM_EMAIL.format(year=self.nomcom.year())
        (to_email, cc) = gather_address_lists('person_merge_requested')
        context = {'primary_person':primary_person, 'duplicate_persons':duplicate_persons, 'year': self.nomcom.year(), }
        send_mail(None, to_email, from_email, subject, 'nomcom/merge_request.txt', context, cc=cc)

class NominateForm(forms.ModelForm):
    searched_email = SearchableEmailField(only_users=False)
    qualifications = forms.CharField(label="Candidate's qualifications for the position",
                               widget=forms.Textarea(), strip=False)
    confirmation = forms.BooleanField(label='Email comments back to me as confirmation.',
                                      help_text="If you want to get a confirmation mail containing your feedback in cleartext, please check the 'email comments back to me as confirmation'.",
                                      required=False)

    def __init__(self, *args, **kwargs):
        self.nomcom = kwargs.pop('nomcom', None)
        self.user = kwargs.pop('user', None)
        self.public = kwargs.pop('public', None)

        super(NominateForm, self).__init__(*args, **kwargs)

        new_person_url_name = 'ietf.nomcom.views.%s_nominate_newperson' % ('public' if self.public else 'private' )
        self.fields['searched_email'].label = 'Candidate email'
        self.fields['searched_email'].help_text = 'Search by name or email address. Click <a href="%s">here</a> if the search does not find the candidate you want to nominate.' % reverse(new_person_url_name,kwargs={'year':self.nomcom.year()})
        self.fields['nominator_email'].label = 'Nominator email'
        if self.nomcom:
            self.fields['position'].queryset = Position.objects.get_by_nomcom(self.nomcom).filter(is_open=True)
            if self.public:
                self.fields['position'].queryset = self.fields['position'].queryset.filter(accepting_nominations=True)
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
                                           comments=self.nomcom.encrypt(qualifications),
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
                from_email = settings.NOMCOM_FROM_EMAIL.format(year=self.nomcom.year())
                (to_email, cc) = gather_address_lists('nomination_receipt_requested',nominator=author.address)
                context = {'nominee': nominee.email.person.name,
                          'comments': qualifications,
                          'position': position.name,
                          'year': self.nomcom.year(),
                      }
                path = nomcom_template_path + NOMINATION_RECEIPT_TEMPLATE
                send_mail(None, to_email, from_email, subject, path, context, cc=cc)

        return nomination

    class Meta:
        model = Nomination
        fields = ('share_nominator', 'position', 'nominator_email', 'searched_email', 
                  'candidate_phone', 'qualifications', 'confirmation')

class NominateNewPersonForm(forms.ModelForm):
    qualifications = forms.CharField(label="Candidate's qualifications for the position",
                               widget=forms.Textarea(), strip=False)
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
            self.fields['position'].queryset = Position.objects.get_by_nomcom(self.nomcom).filter(is_open=True)
            if self.public:
                self.fields['position'].queryset = self.fields['position'].queryset.filter(accepting_nominations=True)  
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
            normal_url_name = 'ietf.nomcom.views.%s_nominate' % ('public' if self.public else 'private')
            msg = (('%s is already in the datatracker. '
                    'Use the <a href="%s">normal nomination form</a> to nominate the person '
                    'with this address. ') % 
                        (candidate_email, reverse(normal_url_name, kwargs={'year':self.nomcom.year()}) )
                  )
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
                                           comments=self.nomcom.encrypt(qualifications),
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
                from_email = settings.NOMCOM_FROM_EMAIL.format(year=self.nomcom.year())
                (to_email, cc) = gather_address_lists('nomination_receipt_requested',nominator=author.address)
                context = {'nominee': nominee.email.person.name,
                          'comments': qualifications,
                          'position': position.name,
                          'year': self.nomcom.year(),
                      }
                path = nomcom_template_path + NOMINATION_RECEIPT_TEMPLATE
                send_mail(None, to_email, from_email, subject, path, context, cc=cc)

        return nomination

    class Meta:
        model = Nomination
        fields = ('share_nominator', 'position', 'nominator_email', 'candidate_name',
                  'candidate_email', 'candidate_phone', 'qualifications', 'confirmation')


class FeedbackForm(forms.ModelForm):
    nominator_email = forms.CharField(label='Commenter email',required=False)
    comment_text = forms.CharField(label='Comments', widget=forms.Textarea(), strip=False)
    confirmation = forms.BooleanField(label='Email comments back to me as confirmation (if selected, your comments will be emailed to you in cleartext when you press Save).',
                                      required=False)

    def __init__(self, *args, **kwargs):
        self.nomcom = kwargs.pop('nomcom', None)
        self.user = kwargs.pop('user', None)
        self.public = kwargs.pop('public', None)
        self.position = kwargs.pop('position', None)
        self.nominee = kwargs.pop('nominee', None)
        self.topic = kwargs.pop('topic', None)

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
        if self.nominee and self.position:
            if not NomineePosition.objects.accepted().filter(nominee=self.nominee,
                                                        position=self.position):
                msg = "There isn't a accepted nomination for %s on the %s position" % (self.nominee, self.position)
                self._errors["comment_text"] = self.error_class([msg])
        return self.cleaned_data

    def save(self, commit=True):
        feedback = super(FeedbackForm, self).save(commit=False)
        confirmation = self.cleaned_data['confirmation']
        comment_text = self.cleaned_data['comment_text']
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
        feedback.comments = self.nomcom.encrypt(comment_text)
        feedback.save()
        if self.nominee and self.position:
            feedback.positions.add(self.position)
            feedback.nominees.add(self.nominee)
        if self.topic:
            feedback.topics.add(self.topic)

        # send receipt email to feedback author
        if confirmation:
            if author:
                subject = "NomCom comment confirmation"
                from_email = settings.NOMCOM_FROM_EMAIL.format(year=self.nomcom.year())
                (to_email, cc) = gather_address_lists('nomcom_comment_receipt_requested',commenter=author.address)
                if self.nominee and self.position:
                    about = '%s for the position of\n%s'%(self.nominee.email.person.name, self.position.name)
                elif self.topic:
                    about = self.topic.subject
                context = {'about': about,
                           'comments': comment_text,
                           'year': self.nomcom.year(),
                       }
                path = nomcom_template_path + FEEDBACK_RECEIPT_TEMPLATE
                # TODO - make the thing above more generic
                send_mail(None, to_email, from_email, subject, path, context, cc=cc, copy=False)

    class Meta:
        model = Feedback
        fields = (
                  'nominator_email',
                  'confirmation',
                 )

class FeedbackEmailForm(forms.Form):

    email_text = forms.CharField(label='Email text', widget=forms.Textarea(), strip=False)

    def __init__(self, *args, **kwargs):
        self.nomcom = kwargs.pop('nomcom', None)
        super(FeedbackEmailForm, self).__init__(*args, **kwargs)

    def save(self, commit=True):
        create_feedback_email(self.nomcom, self.cleaned_data['email_text'])

class QuestionnaireForm(forms.ModelForm):

    comment_text = forms.CharField(label='Questionnaire response from this candidate',
                               widget=forms.Textarea(), strip=False)

    def __init__(self, *args, **kwargs):
        self.nomcom = kwargs.pop('nomcom', None)
        self.user = kwargs.pop('user', None)

        super(QuestionnaireForm, self).__init__(*args, **kwargs)
        self.fields['nominee'] = PositionNomineeField(nomcom=self.nomcom, required=True)

    def save(self, commit=True):
        feedback = super(QuestionnaireForm, self).save(commit=False)
        comment_text = self.cleaned_data['comment_text']
        (position, nominee) = self.cleaned_data['nominee']

        author = get_user_email(self.user)

        if author:
            feedback.author = author

        feedback.nomcom = self.nomcom
        feedback.user = self.user
        feedback.type = FeedbackTypeName.objects.get(slug='questio')
        feedback.comments = self.nomcom.encrypt(comment_text)
        feedback.save()
        self.save_m2m()
        feedback.nominees.add(nominee)
        feedback.positions.add(position)

    class Meta:
        model = Feedback
        fields = []                     # type: List[str]

class NomComTemplateForm(DBTemplateForm):
    content = forms.CharField(label="Text", widget=forms.Textarea(attrs={'cols': '120', 'rows':'40', }), strip=False)

class PositionForm(forms.ModelForm):

    class Meta:
        model = Position
        fields = ('name', 'is_iesg_position', 'is_open', 'accepting_nominations', 'accepting_feedback')

    def __init__(self, *args, **kwargs):
        self.nomcom = kwargs.pop('nomcom', None)
        super(PositionForm, self).__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        self.instance.nomcom = self.nomcom
        super(PositionForm, self).save(*args, **kwargs)

class TopicForm(forms.ModelForm):

    class Meta:
        model = Topic
        fields = ('subject', 'accepting_feedback','audience')

    def __init__(self, *args, **kwargs):
        self.nomcom = kwargs.pop('nomcom', None)
        super(TopicForm, self).__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        self.instance.nomcom = self.nomcom
        super(TopicForm, self).save(*args, **kwargs)

class PrivateKeyForm(forms.Form):

    key = forms.CharField(label='Private key', widget=forms.Textarea(), required=False, strip=False)

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

    def clean(self):
        cleaned_data = super(ReminderDatesForm, self).clean()
        date = cleaned_data.get('date')
        if date is None:
            cleaned_data['date'] = ''
            cleaned_data['DELETE'] = True
        return cleaned_data

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
                                                                  widget=forms.SelectMultiple(attrs={'class':'nominee_multi_select','size':'12'}),
                                                                  required= self.feedback_type.slug != 'comment',
                                                                  help_text='Hold down "Control", or "Command" on a Mac, to select more than one.')
            if self.feedback_type.slug == 'comment':
                self.fields['topic'] = forms.ModelMultipleChoiceField(queryset=self.nomcom.topic_set.all(),
                                                                      help_text='Hold down "Control" or "Command" on a Mac, to select more than one.',
                                                                      required=False,)
        else:
            self.fields['position'] = forms.ModelChoiceField(queryset=Position.objects.get_by_nomcom(self.nomcom).filter(is_open=True), label="Position")
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
        elif self.feedback_type.slug == 'comment':
            nominees = self.cleaned_data.get('nominee')
            topics = self.cleaned_data.get('topic')
            if not (nominees or topics):
                raise forms.ValidationError("You must choose at least one Nominee or Topic to associate with this comment")
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
            if self.instance.type.slug=='comment':
                for topic in self.cleaned_data['topic']:
                    feedback.topics.add(topic)
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

    def clean(self):
        nominee_email = self.cleaned_data.get("nominee_email")
        others = Nominee.objects.filter(email=nominee_email, nomcom=self.instance.nomcom)
        if others.exists():
            msg = ( "Changing email address for %s (#%s): There already exists a nominee "
                    "with email address &lt;%s&gt;: %s -- please use the "
                    "<a href=\"%s\">Merge Nominee</a> "
                    "form instead." % (
                        self.instance.name(),
                        self.instance.pk,
                        nominee_email,
                        (", ".join( "%s (#%s)" %( n.name(), n.pk) for n in others)),
                        reverse('ietf.nomcom.views.private_merge_nominee', kwargs={'year':self.instance.nomcom.year()}),
                    ) )
            raise forms.ValidationError(mark_safe(msg))
        return self.cleaned_data

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
    comments = forms.CharField(widget=forms.Textarea,required=False,help_text="Any comments provided will be encrypted and will only be visible to the NomCom.", strip=False)

class NomcomVolunteerMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        year = obj.year()
        return f'Volunteer for the {year}/{year+1} Nominating Committee'

class VolunteerForm(forms.ModelForm):
    class Meta:
        model = Volunteer
        fields = ('affiliation',)

    nomcoms = NomcomVolunteerMultipleChoiceField(queryset=NomCom.objects.none(),widget=forms.CheckboxSelectMultiple)
    field_order = ('nomcoms','affiliation')

    def __init__(self, person, *args, **kargs):
         super().__init__(*args, **kargs)
         self.fields['nomcoms'].queryset = NomCom.objects.filter(is_accepting_volunteers=True).exclude(volunteer__person=person)
         self.fields['nomcoms'].help_text = 'You may volunteer even if the datatracker does not currently calculate that you are eligible. Eligibility will be assessed when the selection process is performed.'
         self.fields['affiliation'].help_text = 'Affiliation to show in the volunteer list'
         self.fields['affiliation'].required = True
