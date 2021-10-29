# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import os

from django.db import models
from django.db.models.signals import post_delete
from django.conf import settings
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.template.defaultfilters import linebreaks # type: ignore

import debug                            # pyflakes:ignore

from ietf.person.models import Person,Email
from ietf.group.models import Group
from ietf.name.models import NomineePositionStateName, FeedbackTypeName, TopicAudienceName
from ietf.dbtemplate.models import DBTemplate

from ietf.nomcom.managers import (NomineePositionManager, NomineeManager, 
                                  PositionManager, FeedbackManager, )
from ietf.nomcom.utils import (initialize_templates_for_group,
                               initialize_questionnaire_for_position,
                               initialize_requirements_for_position,
                               initialize_description_for_topic,
                               delete_nomcom_templates,
                               EncryptedException,
                              )
from ietf.utils.log import log
from ietf.utils.models import ForeignKey
from ietf.utils.pipe import pipe
from ietf.utils.storage import NoLocationMigrationFileSystemStorage


def upload_path_handler(instance, filename):
    return os.path.join(instance.group.acronym, 'public.cert')


class ReminderDates(models.Model):
    date = models.DateField()
    nomcom = ForeignKey('NomCom')


class NomCom(models.Model):
    public_key = models.FileField(storage=NoLocationMigrationFileSystemStorage(location=settings.NOMCOM_PUBLIC_KEYS_DIR),
                                  upload_to=upload_path_handler, blank=True, null=True)

    group = ForeignKey(Group)
    send_questionnaire = models.BooleanField(verbose_name='Send questionnaires automatically', default=False,
                                             help_text='If you check this box, questionnaires are sent automatically after nominations.')
    reminder_interval = models.PositiveIntegerField(help_text='If the nomcom user sets the interval field then a cron command will '
                                                              'send reminders to the nominees who have not responded using '
                                                              'the following formula: (today - nomination_date) % interval == 0.',
                                                               blank=True, null=True)
    initial_text = models.TextField(verbose_name='Help text for nomination form',
                                    blank=True)
    show_nominee_pictures = models.BooleanField(verbose_name='Show nominee pictures', default=True,
                                                help_text='Display pictures of each nominee (if available) on the feedback pages')
    show_accepted_nominees = models.BooleanField(verbose_name='Show accepted nominees', default=True, 
                                                 help_text='Show accepted nominees on the public nomination page')
    is_accepting_volunteers = models.BooleanField(verbose_name="Accepting volunteers", default=False,
                                                  help_text='Is this nomcom is currently accepting volunteers?')
    first_call_for_volunteers = models.DateField(verbose_name='Date of the first call for volunteers', blank=True, null=True)

    class Meta:
        verbose_name_plural = 'NomComs'
        verbose_name = 'NomCom'

    def __str__(self):
        return self.group.acronym

    def save(self, *args, **kwargs):
        created = not self.id
        super(NomCom, self).save(*args, **kwargs)
        if created:
            initialize_templates_for_group(self)

    def year(self):
        year = getattr(self,'_cached_year',None)
        if year is None:
            if self.group and self.group.acronym.startswith('nomcom'):
                year = int(self.group.acronym[6:])
                self._cached_year = year
        return year

    def pending_email_count(self):
        return self.feedback_set.filter(type__isnull=True).count()

    def encrypt(self, cleartext):
        try:
            cert_file = self.public_key.path
        except ValueError as e:
            raise ValueError("Trying to read the NomCom public key: " + str(e))

        command = "%s smime -encrypt -in /dev/stdin %s" % (settings.OPENSSL_COMMAND, cert_file)
        code, out, error = pipe(command, cleartext.encode('utf-8'))
        if code != 0:
            log("openssl error: %s:\n  Error %s: %s" %(command, code, error))
        if not error:
            return out
        else:
            raise EncryptedException(error)

    def chair_emails(self):
        if not hasattr(self, '_cached_chair_emails'):
            if self.group:
                self._cached_chair_emails = list(
                    self.group.role_set.filter(name_id='chair').values_list('email__address', flat=True)
                )
            else:
                self._cached_chair_emails = []
        return self._cached_chair_emails

def delete_nomcom(sender, **kwargs):
    nomcom = kwargs.get('instance', None)
    delete_nomcom_templates(nomcom)
    storage, path = nomcom.public_key.storage, nomcom.public_key.path
    storage.delete(path)
post_delete.connect(delete_nomcom, sender=NomCom)


class Nomination(models.Model):
    position = ForeignKey('Position')
    candidate_name = models.CharField(verbose_name='Candidate name', max_length=255)
    candidate_email = models.EmailField(verbose_name='Candidate email', max_length=255)
    candidate_phone = models.CharField(verbose_name='Candidate phone', blank=True, max_length=255)
    nominee = ForeignKey('Nominee')
    comments = ForeignKey('Feedback')
    nominator_email = models.EmailField(verbose_name='Nominator Email', blank=True)
    user = ForeignKey(User, editable=False, null=True, on_delete=models.SET_NULL)
    time = models.DateTimeField(auto_now_add=True)
    share_nominator = models.BooleanField(verbose_name='Share nominator name with candidate', default=False,
                                          help_text='Check this box to allow the NomCom to let the '
                                                    'person you are nominating know that you were '
                                                    'one of the people who nominated them. If you '
                                                    'do not check this box, your name will be confidential '
                                                    'and known only within NomCom.')

    class Meta:
        verbose_name_plural = 'Nominations'

    def __str__(self):
        return "%s (%s)" % (self.candidate_name, self.candidate_email)


class Nominee(models.Model):

    email = ForeignKey(Email)
    person = ForeignKey(Person, blank=True, null=True)
    nominee_position = models.ManyToManyField('Position', through='NomineePosition')
    duplicated = ForeignKey('Nominee', blank=True, null=True)
    nomcom = ForeignKey('NomCom')

    objects = NomineeManager()

    class Meta:
        verbose_name_plural = 'Nominees'
        unique_together = ('email', 'nomcom')
        ordering = ['-nomcom__group__acronym', 'person__name', ]

    def __str__(self):
        if self.email.person and self.email.person.name:
            return "%s <%s> %s" % (self.email.person.plain_name(), self.email.address, self.nomcom.year())
        else:
            return "%s %s" % (self.email.address, self.nomcom.year())

    def name(self):
        if self.email.person and self.email.person.name:
            return '%s' % (self.email.person.plain_name(),)
        else:
            return self.email.address

class NomineePosition(models.Model):

    position = ForeignKey('Position')
    nominee = ForeignKey('Nominee')
    state = ForeignKey(NomineePositionStateName)
    time = models.DateTimeField(auto_now_add=True)

    objects = NomineePositionManager()

    class Meta:
        verbose_name = 'Nominee position'
        verbose_name_plural = 'Nominee positions'
        unique_together = ('position', 'nominee')
        ordering = ['nominee']

    def save(self, **kwargs):
        if not self.pk and not self.state_id:
            self.state = NomineePositionStateName.objects.get(slug='pending')
        super(NomineePosition, self).save(**kwargs)

    def __str__(self):
        return "%s - %s - %s" % (self.nominee, self.state, self.position)

    @property
    def questionnaires(self):
        return Feedback.objects.questionnaires().filter(positions__in=[self.position],
                                                        nominees__in=[self.nominee])


class Position(models.Model):
    nomcom = ForeignKey('NomCom')
    name = models.CharField(verbose_name='Name', max_length=255, help_text='This short description will appear on the Nomination and Feedback pages. Be as descriptive as necessary. Past examples: "Transport AD", "IAB Member"')
    requirement = ForeignKey(DBTemplate, related_name='requirement', null=True, editable=False)
    questionnaire = ForeignKey(DBTemplate, related_name='questionnaire', null=True, editable=False)
    is_open = models.BooleanField(verbose_name='Is open', default=False, help_text="Set is_open when the nomcom is working on a position. Clear it when an appointment is confirmed.")
    accepting_nominations = models.BooleanField(verbose_name='Is accepting nominations', default=False)
    accepting_feedback = models.BooleanField(verbose_name='Is accepting feedback', default=False)
    # To generalize the generic requirements code, change this to a FK to a
    # NameModel subclass which enumerates the generic requirement DBtemplates
    # under /nomcom/defaults/, e.g., iesg_requirements; and use that to fetch
    # the generic template in .get_requirements():
    is_iesg_position = models.BooleanField(verbose_name='Is IESG Position', default=False)

    objects = PositionManager()

    class Meta:
        verbose_name_plural = 'Positions'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        created = not self.id
        super(Position, self).save(*args, **kwargs)
        changed = False
        if created and self.id and not self.requirement_id:
            self.requirement = initialize_requirements_for_position(self)
            changed = True
        if created and self.id and not self.questionnaire_id:
            self.questionnaire = initialize_questionnaire_for_position(self)
            changed = True
        if changed:
            self.save()

    def get_templates(self):
        if hasattr(self, '_templates'):
            return self._templates      # pylint: disable=access-member-before-definition
        from ietf.dbtemplate.models import DBTemplate
        self._templates = DBTemplate.objects.filter(group=self.nomcom.group).filter(path__contains='/%s/position/' % self.id).order_by('title')
        return self._templates

    def get_questionnaire(self):
        return render_to_string(self.questionnaire.path, {'position': self})

    def get_requirement(self):
        specific_reqs = render_to_string(self.requirement.path, {'position': self})
        if self.requirement.type_id=='plain':
            specific_reqs = linebreaks(specific_reqs)

        generic_iesg_template = DBTemplate.objects.filter(group=self.nomcom.group,path__endswith='iesg_requirements').first()

        if self.is_iesg_position and generic_iesg_template:
            generic_iesg_reqs = render_to_string(generic_iesg_template.path, {})
            if generic_iesg_template.type_id=='plain':
                generic_iesg_reqs = linebreaks(generic_iesg_reqs)
            return render_to_string("nomcom/iesg_position_requirements.html", dict(position=self, generic_iesg_reqs=generic_iesg_reqs, specific_reqs=specific_reqs))
        else:
            return specific_reqs

class Topic(models.Model):
    nomcom = ForeignKey('NomCom')
    subject = models.CharField(verbose_name='Name', max_length=255, help_text='This short description will appear on the Feedback pages.')
    description = ForeignKey(DBTemplate, related_name='description', null=True, editable=False)
    accepting_feedback = models.BooleanField(verbose_name='Is accepting feedback', default=False)
    audience = ForeignKey(TopicAudienceName, verbose_name='Who can provide feedback (intended audience)')

    class Meta:
        verbose_name_plural = 'Topics'

    def __str__(self):
        return self.subject

    def save(self, *args, **kwargs):
        created = not self.id
        super(Topic, self).save(*args, **kwargs)
        changed = False
        if created and self.id and not self.description_id:
            self.description = initialize_description_for_topic(self)
            changed = True
        if changed:
            self.save()

    def get_description(self):
        rendered = render_to_string(self.description.path, {'topic': self})
        if self.description.type_id=='plain':
            rendered = linebreaks(rendered)
        return rendered

class Feedback(models.Model):
    nomcom = ForeignKey('NomCom')
    author = models.EmailField(verbose_name='Author', blank=True)
    positions = models.ManyToManyField('Position', blank=True)
    nominees = models.ManyToManyField('Nominee', blank=True)
    topics = models.ManyToManyField('Topic', blank=True)
    subject = models.TextField(verbose_name='Subject', blank=True)
    comments = models.BinaryField(verbose_name='Comments')
    type = ForeignKey(FeedbackTypeName, blank=True, null=True)
    user = ForeignKey(User, editable=False, blank=True, null=True, on_delete=models.SET_NULL)
    time = models.DateTimeField(auto_now_add=True)

    objects = FeedbackManager()

    def __str__(self):
        return "from %s" % self.author

    class Meta:
        ordering = ['time']
        indexes = [
            models.Index(fields=['time',]),
        ]

class FeedbackLastSeen(models.Model):
    reviewer = ForeignKey(Person)
    nominee = ForeignKey(Nominee)
    time = models.DateTimeField(auto_now=True)

class TopicFeedbackLastSeen(models.Model):
    reviewer = ForeignKey(Person)
    topic = ForeignKey(Topic)
    time = models.DateTimeField(auto_now=True)

class Volunteer(models.Model):
    nomcom = ForeignKey('NomCom')
    person = ForeignKey(Person)
    affiliation = models.CharField(blank=True, max_length=255)

    def __str__(self):
        return f'{self.person} for {self.nomcom}'
    
