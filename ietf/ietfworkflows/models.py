from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import ugettext_lazy as _

from ietf.idtracker.models import PersonOrOrgInfo, InternetDraft
from workflows.models import Workflow, State, StateObjectRelation
from permissions.models import Permission


class ObjectHistoryEntry(models.Model):
    content_type = models.ForeignKey(ContentType, verbose_name=_(u"Content type"), related_name="workflow_history", blank=True, null=True)
    content_id = models.PositiveIntegerField(_(u"Content id"), blank=True, null=True)
    content = generic.GenericForeignKey(ct_field="content_type", fk_field="content_id")

    date = models.DateTimeField(_('Date'), auto_now_add=True)
    comment = models.TextField(_('Comment'))
    person = models.ForeignKey(PersonOrOrgInfo)

    class Meta:
        ordering = ('-date', )

    def get_real_instance(self):
        if hasattr(self, '_real_instance'):
            return self._real_instance
        for i in ('objectworkflowhistoryentry', 'objectannotationtaghistoryentry', 'objectstreamhistoryentry'):
            try:
                real_instance = getattr(self, i, None)
                if real_instance:
                    self._real_instance = real_instance
                    return real_instance
            except models.ObjectDoesNotExist:
                continue
        self._real_instance = self
        return self


class ObjectWorkflowHistoryEntry(ObjectHistoryEntry):
    from_state = models.CharField(_('From state'), max_length=100)
    to_state = models.CharField(_('To state'), max_length=100)

    def describe_change(self):
        html = '<p class="describe_state_change">'
        html += 'Changed state <i>%s</i> to <b>%s</b>' % (self.from_state, self.to_state)
        html += '</p>'
        return html


class ObjectAnnotationTagHistoryEntry(ObjectHistoryEntry):
    setted = models.TextField(_('Setted tags'), blank=True, null=True)
    unsetted = models.TextField(_('Unsetted tags'), blank=True, null=True)

    def describe_change(self):
        html = ''
        if self.setted:
            html += '<p class="describe_tags_set">'
            html += 'Annotation tags set: '
            html += self.setted
            html += '</p>'
        if self.unsetted:
            html += '<p class="describe_tags_reset">'
            html += 'Annotation tags reset: '
            html += self.unsetted
            html += '</p>'
        return html


class ObjectStreamHistoryEntry(ObjectHistoryEntry):
    from_stream = models.TextField(_('From stream'), blank=True, null=True)
    to_stream = models.TextField(_('To stream'), blank=True, null=True)

    def describe_change(self):
        html = '<p class="describe_stream_change">'
        html += 'Changed doc from stream <i>%s</i> to <b>%s</b>' % (self.from_stream, self.to_stream)
        html += '</p>'
        return html


class StateDescription(models.Model):
    state = models.ForeignKey(State)
    definition = models.TextField()
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ('order', )

    def __unicode__(self):
        return unicode(self.state)


class AnnotationTag(models.Model):
    name = models.CharField(_(u"Name"), max_length=100)
    workflow = models.ForeignKey(Workflow, verbose_name=_(u"Workflow"), related_name="annotation_tags")
    permission = models.ForeignKey(Permission, verbose_name=_(u"Permission"), blank=True, null=True)

    class Meta:
        ordering = ('name', )

    def __unicode__(self):
        return self.name


class AnnotationTagObjectRelation(models.Model):
    content_type = models.ForeignKey(ContentType, verbose_name=_(u"Content type"), related_name="annotation_tags", blank=True, null=True)
    content_id = models.PositiveIntegerField(_(u"Content id"), blank=True, null=True)
    content = generic.GenericForeignKey(ct_field="content_type", fk_field="content_id")

    annotation_tag = models.ForeignKey(AnnotationTag, verbose_name=_(u"Annotation tag"))


class StateObjectRelationMetadata(models.Model):
    relation = models.ForeignKey(StateObjectRelation)
    from_date = models.DateTimeField(_('Initial date'), blank=True, null=True)
    estimated_date = models.DateTimeField(_('Estimated date'), blank=True, null=True)


class WGWorkflow(Workflow):
    selected_states = models.ManyToManyField(State, blank=True, null=True)
    selected_tags = models.ManyToManyField(AnnotationTag, blank=True, null=True)

    class Meta:
        verbose_name = 'IETF Workflow'
        verbose_name_plural = 'IETF Workflows'

    def get_tags(self):
        tags = self.annotation_tags.all()
        if tags.count():
            return tags
        else:
            return self.selected_tags.all()

    def get_states(self):
        states = self.states.all()
        if states.count():
            return states
        else:
            return self.selected_states.all()


class Stream(models.Model):
    name = models.CharField(_(u"Name"), max_length=100)
    with_groups = models.BooleanField(_(u'With groups'), default=False)
    group_model = models.CharField(_(u'Group model'), max_length=100, blank=True, null=True)
    group_chair_model = models.CharField(_(u'Group chair model'), max_length=100, blank=True, null=True)
    workflow = models.ForeignKey(WGWorkflow)

    def __unicode__(self):
        return u'%s stream' % self.name


class StreamedID(models.Model):
    draft = models.OneToOneField(InternetDraft)
    stream = models.ForeignKey(Stream, blank=True, null=True)

    content_type = models.ForeignKey(ContentType, verbose_name=_(u"Content type"), related_name="streamed_id", blank=True, null=True)
    content_id = models.PositiveIntegerField(_(u"Content id"), blank=True, null=True)
    group = generic.GenericForeignKey(ct_field="content_type", fk_field="content_id")
