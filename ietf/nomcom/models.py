import os

from django.db import models
from django.conf import settings
from django.core.files.storage import FileSystemStorage

from south.modelsinspector import add_introspection_rules

from ietf.nomcom.fields import EncriptedTextField
from ietf.person.models import Email
from ietf.group.models import Group
from ietf.name.models import NomineePositionState, FeedbackType
from ietf.dbtemplate.models import DBTemplate

from ietf.nomcom.utils import (initialize_templates_for_group,
                               initialize_questionnaire_for_position,
                               initialize_requirements_for_position)


def upload_path_handler(instance, filename):
    return os.path.join(instance.group.acronym, filename)


class NomCom(models.Model):
    public_key = models.FileField(storage=FileSystemStorage(location=settings.PUBLIC_KEYS_URL),
                                  upload_to=upload_path_handler, blank=True, null=True)

    group = models.ForeignKey(Group)
    send_questionnaire = models.BooleanField(verbose_name='Send automatically questionnaires"',
                                            help_text='If you check this box, questionnaires are sent automatically after nominations')

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


class Nomination(models.Model):
    position = models.ForeignKey('Position')
    candidate_name = models.CharField(verbose_name='Candidate name', max_length=255)
    candidate_email = models.EmailField(verbose_name='Candidate email', max_length=255)
    candidate_phone = models.CharField(verbose_name='Candidate phone', blank=True, max_length=255)
    nominee = models.ForeignKey('Nominee')
    comments = models.ForeignKey('Feedback')
    nominator_email = models.EmailField(verbose_name='Nominator Email', blank=True)

    class Meta:
        verbose_name_plural = 'Nominations'

    def __unicode__(self):
        return u"%s (%s)" % (self.candidate_name, self.candidate_email)


class Nominee(models.Model):

    email = models.ForeignKey(Email)
    nomine_position = models.ManyToManyField('Position', through='NomineePosition')

    class Meta:
        verbose_name_plural = 'Nominees'

    def __unicode__(self):
        return u'%s' % self.email


def get_state_default():
    try:
        return NomineePositionState.objects.get(slug='pending').slug
    except NomineePositionState.DoesNotExist:
        return None


class NomineePosition(models.Model):

    position = models.ForeignKey('Position')
    nominee = models.ForeignKey('Nominee')
    state = models.ForeignKey(NomineePositionState, default=get_state_default())
    questionnaire = models.ForeignKey('Feedback',
                                      related_name='questionnaire',
                                      blank=True, null=True)
    feedback = models.ManyToManyField('Feedback', blank=True, null=True)

    class Meta:
        verbose_name = 'Nominee position'
        verbose_name_plural = 'Nominee positions'
        unique_together = ('position', 'nominee')

    def __unicode__(self):
        return u"%s - %s" % (self.nominee, self.position)


class Position(models.Model):
    nomcom = models.ForeignKey('NomCom')
    name = models.CharField(verbose_name='Name', max_length=255)
    description = models.TextField(verbose_name='Despcription')
    initial_text = models.TextField(verbose_name='Initial text for nominations',
                                    blank=True)
    requirement = models.ForeignKey(DBTemplate, related_name='requirement', null=True)
    questionnaire = models.ForeignKey(DBTemplate, related_name='questionnaire', null=True)
    is_open = models.BooleanField(verbose_name='Is open')
    incumbent = models.ForeignKey(Email)

    class Meta:
        verbose_name_plural = 'Positions'

    def __unicode__(self):
        return u"%s: %s" % (self.nomcom, self.name)

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


class Feedback(models.Model):
    author = models.EmailField(verbose_name='Author', blank=True)
    position = models.ForeignKey('Position')
    nominee = models.ForeignKey('Nominee')
    comments = EncriptedTextField(verbose_name='Comments')
    type = models.ForeignKey(FeedbackType)
    time = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return u"%s - %s" % (self.author, self.nominee)

# ----- adding south rules to help introspection -----

add_introspection_rules([], ["^ietf\.nomcom\.fields\.EncriptedTextField"])
