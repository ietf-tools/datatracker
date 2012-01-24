from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.conf import settings

from ietf.idtracker.models import PersonOrOrgInfo, InternetDraft, Role, IRTF
from ietf.utils.admin import admin_link
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
    document_group_attribute = models.CharField(_(u'Document group attribute'), max_length=255, blank=True, null=True)
    group_chair_attribute = models.CharField(_(u'Group chair attribute'), max_length=255, blank=True, null=True)
    workflow = models.ForeignKey(WGWorkflow)

    def __unicode__(self):
        return u'%s stream' % self.name
    workflow_link = admin_link('workflow')

    def _irtf_group(self, document):
        filename = document.filename.split('-')
        if len(filename) > 2 and filename[0] == 'draft' and filename[1] == 'irtf':
            try:
                return IRTF.objects.get(acronym=filename[2])
            except IRTF.DoesNotExist:
                return None
        return None

    def _irtf_chairs_for_document(self, document):
        group = self._irtf_group(document)
        if not group:
            return []
        chairs = [i.person for i in group.chairs()]
        chairs.append(Role.objects.get(pk=Role.IRTF_CHAIR).person)
        return chairs

    def _ietf_delegates_for_document(self, document):
        group = self.get_group_for_document(document)
        if not group:
            return False
        return [i.person for i in group.wgdelegate_set.all()]

    def get_group_for_document(self, document):
        if hasattr(self, '_%s_group' % self.name.lower()):
            return getattr(self, '_%s_group' % self.name.lower())(document)

        if not self.document_group_attribute:
            return None
        attr = None
        obj = document
        for attr_name in self.document_group_attribute.split('.'):
            attr = getattr(obj, attr_name, None)
            if not attr:
                return None
            if callable(attr):
                attr = attr()
            obj = attr
        return attr

    def get_chairs_for_document(self, document):
        if hasattr(self, '_%s_chairs_for_document' % self.name.lower()):
            return getattr(self, '_%s_chairs_for_document' % self.name.lower())(document)

        group = self.get_group_for_document(document)
        if not group or not self.group_chair_attribute:
            return []
        attr = None
        obj = group
        for attr_name in self.group_chair_attribute.split('.'):
            attr = getattr(obj, attr_name, None)
            if not attr:
                return None
            if callable(attr):
                attr = attr()
            obj = attr
        return attr

    def get_delegates_for_document(self, document):
        delegates = []
        if hasattr(self, '_%s_delegates_for_document' % self.name.lower()):
            delegates = getattr(self, '_%s_delegates_for_document' % self.name.lower())(document)
        delegates += [i.person for i in self.streamdelegate_set.all()]
        return delegates

    def _ise_chairs_for_document(self, document):
        return self._ise_stream_chairs()

    def _ise_stream_chairs(self):
        chairs = []
        try:
            chairs.append(Role.objects.get(role_name='ISE').person)
        except Role.DoesNotExist:
            pass
        return chairs

    def get_chairs(self):
        chairs = []
        if hasattr(self, '_%s_stream_chairs' % self.name.lower()):
            chairs += list(getattr(self, '_%s_stream_chairs' % self.name.lower())())

        role_key = getattr(Role, '%s_CHAIR' % self.name.upper(), None)
        if role_key:
            try:
                chairs.append(Role.objects.get(pk=role_key).person)
            except Role.DoesNotExist:
                pass
        return list(set(chairs))

    def get_delegates(self):
        delegates = []
        if hasattr(self, '_%s_stream_delegates' % self.name.lower()):
            delegates += list(getattr(self, '_%s_stream_delegates' % self.name.lower())())
        delegates += [i.person for i in StreamDelegate.objects.filter(stream=self)]
        return list(set(delegates))

    def check_chair(self, person):
        return person in self.get_chairs()

    def check_delegate(self, person):
        return person in self.get_delegates()


class StreamedID(models.Model):
    draft = models.OneToOneField(InternetDraft)
    stream = models.ForeignKey(Stream, blank=True, null=True)

    def get_group(self):
        return self.stream.get_group_for_document(self.draft)


class StreamDelegate(models.Model):
    stream = models.ForeignKey(Stream)
    person = models.ForeignKey(PersonOrOrgInfo)

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    from ietf.name.proxy import StreamProxy as Stream
