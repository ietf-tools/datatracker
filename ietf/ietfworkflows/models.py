from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import ugettext_lazy as _

from ietf.idtracker.models import PersonOrOrgInfo, InternetDraft
from workflows.models import Workflow, State, StateObjectRelation
from permissions.models import Permission


class ObjectWorkflowHistoryEntry(models.Model):
    content_type = models.ForeignKey(ContentType, verbose_name=_(u"Content type"), related_name="workflow_history", blank=True, null=True)
    content_id = models.PositiveIntegerField(_(u"Content id"), blank=True, null=True)
    content = generic.GenericForeignKey(ct_field="content_type", fk_field="content_id")

    from_state = models.CharField(_('From state'), max_length=100)
    to_state = models.CharField(_('To state'), max_length=100)
    transition_date = models.DateTimeField(_('Transition date'))
    comment = models.TextField(_('Comment'))
    person = models.ForeignKey(PersonOrOrgInfo)


class AnnotationTag(models.Model):
    name = models.CharField(_(u"Name"), max_length=100)
    workflow = models.ForeignKey(Workflow, verbose_name=_(u"Workflow"), related_name="annotation_tags")
    permission = models.ForeignKey(Permission, verbose_name=_(u"Permission"), blank=True, null=True)

    def __unicode__(self):
        return self.name


class AnnotationTagObjectRelation(models.Model):
    content_type = models.ForeignKey(ContentType, verbose_name=_(u"Content type"), related_name="annotation_tags", blank=True, null=True)
    content_id = models.PositiveIntegerField(_(u"Content id"), blank=True, null=True)
    content = generic.GenericForeignKey(ct_field="content_type", fk_field="content_id")

    annotation_tag = models.ForeignKey(AnnotationTag, verbose_name=_(u"Annotation tag"))


class ObjectAnnotationTagHistoryEntry(models.Model):
    content_type = models.ForeignKey(ContentType, verbose_name=_(u"Content type"), related_name="annotation_tags_history", blank=True, null=True)
    content_id = models.PositiveIntegerField(_(u"Content id"), blank=True, null=True)
    content = generic.GenericForeignKey(ct_field="content_type", fk_field="content_id")

    setted = models.TextField(_('Setted tags'), blank=True, null=True)
    unsetted = models.TextField(_('Unsetted tags'), blank=True, null=True)
    change_date = models.DateTimeField(_('Change date'))
    comment = models.TextField(_('Comment'))
    person = models.ForeignKey(PersonOrOrgInfo)


class StateObjectRelationMetadata(models.Model):
    relation = models.ForeignKey(StateObjectRelation)
    from_date = models.DateTimeField(_('Initial date'))
    estimated_date = models.DateTimeField(_('Estimated date'), blank=True, null=True)


class WGWorkflow(Workflow):
    selected_states = models.ManyToManyField(State, blank=True, null=True)
    selected_tags = models.ManyToManyField(AnnotationTag, blank=True, null=True)

    class Meta:
        verbose_name = 'IETF Workflow'
        verbose_name_plural = 'IETF Workflows'
