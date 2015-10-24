# -*- coding: utf-8 -*-
import os

from django.db import models
from django.db.models.signals import post_delete
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.contrib.auth.models import User
from django.template.loader import render_to_string

from ietf.nomcom.fields import EncryptedTextField
from ietf.person.models import Email
from ietf.group.models import Group
from ietf.name.models import NomineePositionStateName, FeedbackTypeName
from ietf.dbtemplate.models import DBTemplate

from ietf.nomcom.managers import NomineePositionManager, NomineeManager, \
                                 PositionManager, FeedbackManager
from ietf.nomcom.utils import (initialize_templates_for_group,
                               initialize_questionnaire_for_position,
                               initialize_requirements_for_position,
                               delete_nomcom_templates)


def upload_path_handler(instance, filename):
    return os.path.join(instance.group.acronym, 'public.cert')


class ReminderDates(models.Model):
    date = models.DateField()
    nomcom = models.ForeignKey('NomCom')


class NoLocationMigrationFileSystemStorage(FileSystemStorage):

    def deconstruct(obj):
        path, args, kwargs = FileSystemStorage.deconstruct(obj)
        kwargs["location"] = None
        return (path, args, kwargs)
    

class NomCom(models.Model):
    public_key = models.FileField(storage=NoLocationMigrationFileSystemStorage(location=settings.NOMCOM_PUBLIC_KEYS_DIR),
                                  upload_to=upload_path_handler, blank=True, null=True)

    group = models.ForeignKey(Group)
    send_questionnaire = models.BooleanField(verbose_name='Send questionnaires automatically', default=False,
                                             help_text='If you check this box, questionnaires are sent automatically after nominations.')
    reminder_interval = models.PositiveIntegerField(help_text='If the nomcom user sets the interval field then a cron command will '
                                                              'send reminders to the nominees who have not responded using '
                                                              'the following formula: (today - nomination_date) % interval == 0.',
                                                               blank=True, null=True)
    initial_text = models.TextField(verbose_name='Help text for nomination form',
                                    blank=True)

    class Meta:
        verbose_name_plural = 'NomComs'
        verbose_name = 'NomCom'

    def __unicode__(self):
        return self.group.acronym

    def save(self, *args, **kwargs):
        created = not self.id
        super(NomCom, self).save(*args, **kwargs)
        if created:
            initialize_templates_for_group(self)


def delete_nomcom(sender, **kwargs):
    nomcom = kwargs.get('instance', None)
    delete_nomcom_templates(nomcom)
    storage, path = nomcom.public_key.storage, nomcom.public_key.path
    storage.delete(path)
post_delete.connect(delete_nomcom, sender=NomCom)


class Nomination(models.Model):
    position = models.ForeignKey('Position')
    candidate_name = models.CharField(verbose_name='Candidate name', max_length=255)
    candidate_email = models.EmailField(verbose_name='Candidate email', max_length=255)
    candidate_phone = models.CharField(verbose_name='Candidate phone', blank=True, max_length=255)
    nominee = models.ForeignKey('Nominee')
    comments = models.ForeignKey('Feedback')
    nominator_email = models.EmailField(verbose_name='Nominator Email', blank=True)
    user = models.ForeignKey(User, editable=False)
    time = models.DateTimeField(auto_now_add=True)
    share_nominator = models.BooleanField(verbose_name='Share nominator name with candidate', default=False,
                                          help_text='Check this box to allow the NomCom to let the '
                                                    'person you are nominating know that you were '
                                                    'one of the people who nominated them. If you '
                                                    'do not check this box, your name will be confidential '
                                                    'and known only within NomCom.')

    class Meta:
        verbose_name_plural = 'Nominations'

    def __unicode__(self):
        return u"%s (%s)" % (self.candidate_name, self.candidate_email)


class Nominee(models.Model):

    email = models.ForeignKey(Email)
    nominee_position = models.ManyToManyField('Position', through='NomineePosition')
    duplicated = models.ForeignKey('Nominee', blank=True, null=True)
    nomcom = models.ForeignKey('NomCom')

    objects = NomineeManager()

    class Meta:
        verbose_name_plural = 'Nominees'
        unique_together = ('email', 'nomcom')

    def __unicode__(self):
        if self.email.person and self.email.person.name:
            return u'%s <%s>' % (self.email.person.plain_name(), self.email.address)
        else:
            return self.email.address


class NomineePosition(models.Model):

    position = models.ForeignKey('Position')
    nominee = models.ForeignKey('Nominee')
    state = models.ForeignKey(NomineePositionStateName)
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

    def __unicode__(self):
        return u"%s - %s" % (self.nominee, self.position)

    @property
    def questionnaires(self):
        return Feedback.objects.questionnaires().filter(positions__in=[self.position],
                                                        nominees__in=[self.nominee])


class Position(models.Model):
    nomcom = models.ForeignKey('NomCom')
    name = models.CharField(verbose_name='Name', max_length=255)
    description = models.TextField(verbose_name='Description')
    requirement = models.ForeignKey(DBTemplate, related_name='requirement', null=True, editable=False)
    questionnaire = models.ForeignKey(DBTemplate, related_name='questionnaire', null=True, editable=False)
    is_open = models.BooleanField(verbose_name='Is open', default=False)
    incumbent = models.ForeignKey(Email, null=True, blank=True)

    objects = PositionManager()

    class Meta:
        verbose_name_plural = 'Positions'

    def __unicode__(self):
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
            return self._templates
        from ietf.dbtemplate.models import DBTemplate
        self._templates = DBTemplate.objects.filter(group=self.nomcom.group).filter(path__contains='/%s/position/' % self.id).order_by('title')
        return self._templates

    def get_questionnaire(self):
        return render_to_string(self.questionnaire.path, {'position': self})

    def get_requirement(self):
        return render_to_string(self.requirement.path, {'position': self})


class Feedback(models.Model):
    nomcom = models.ForeignKey('NomCom')
    author = models.EmailField(verbose_name='Author', blank=True)
    positions = models.ManyToManyField('Position', blank=True, null=True)
    nominees = models.ManyToManyField('Nominee', blank=True, null=True)
    subject = models.TextField(verbose_name='Subject', blank=True)
    comments = EncryptedTextField(verbose_name='Comments')
    type = models.ForeignKey(FeedbackTypeName, blank=True, null=True)
    user = models.ForeignKey(User, editable=False, blank=True, null=True)
    time = models.DateTimeField(auto_now_add=True)

    objects = FeedbackManager()

    def __unicode__(self):
        return u"from %s" % self.author

    class Meta:
        ordering = ['time']


