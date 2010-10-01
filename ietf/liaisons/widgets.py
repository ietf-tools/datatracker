from django.conf import settings
from django.core.urlresolvers import reverse
from django.db.models.query import QuerySet
from django.forms.widgets import Select, Widget, TextInput
from django.utils.safestring import mark_safe


class FromWidget(Select):

    def render(self, name, value, attrs=None, choices=()):
        all_choices = list(self.choices) + list(choices)
        if len(all_choices)!=1 or \
            (isinstance(all_choices[0][1], (list, tuple)) and \
             len(all_choices[0][1])!=1):
            base = super(FromWidget, self).render(name, value, attrs, choices)
        else:
            option = all_choices[0]
            if isinstance(option[1], (list, tuple)):
                option = option[1][0]
            value = option[0]
            text = option[1]
            base = u'<input type="hidden" value="%s" id="id_%s" name="%s" />%s' % (value, name, name, text)
        base += u' (<a class="from_mailto" href="">' + self.submitter + u'</a>)'
        return mark_safe(base)


class ReadOnlyWidget(Widget):

    def render(self, name, value, attrs=None):
        html = u'<div id="id_%s">%s</div>' % (name, value or '')
        return mark_safe(html)


class ButtonWidget(Widget):

    def __init__(self, *args, **kwargs):
        self.label = kwargs.pop('label', None)
        self.show_on = kwargs.pop('show_on', None)
        self.require = kwargs.pop('require', None)
        self.required_label = kwargs.pop('required_label', None)
        super(ButtonWidget, self).__init__(*args, **kwargs)

    def render(self, name, value, attrs=None):
        html = u'<span style="display: none" class="showAttachsOn">%s</span>' % self.show_on
        html += u'<span style="display: none" class="attachEnabledLabel">%s</span>' % self.label
        if self.require:
            for i in self.require:
                html += u'<span style="display: none" class="attachRequiredField">%s</span>' % i
            required_str = u'Please fill %s to attach a new file' % self.required_label
            html += u'<span style="display: none" class="attachDisabledLabel">%s</span>' % required_str
        html += u'<input type="button" class="addAttachmentWidget" value="%s" />' % self.label
        return mark_safe(html)


class ShowAttachmentsWidget(Widget):

    def render(self, name, value, attrs=None):
        html = u'<div id="id_%s">' % name
        html += u'<span style="display: none" class="showAttachmentsEmpty">No files attached</span>'
        html += u'<div class="attachedFiles">'
        if value and isinstance(value, QuerySet):
            for attach in value:
                html += u'<a class="initialAttach" href="%sfile%s%s">%s</a><br />' % (settings.LIAISON_ATTACH_URL, attach.file_id, attach.file_extension, attach.file_title, )
        else:
            html += u'No files attached'
        html += u'</div></div>'
        return mark_safe(html)


class RelatedLiaisonWidget(TextInput):

    def render(self, name, value, attrs=None):
        if not value:
            value = ''
            title = ''
            noliaison = 'inline'
            deselect = 'none'
        else:
            from ietf.liaisons.models import LiaisonDetail
            liaison = LiaisonDetail.objects.get(pk=value)
            title = liaison.title
            if not title:
                files = liaison.uploads_set.all()
                if files:
                    title = files[0].file_title
                else:
                    title = 'Liaison #%s' % liaison.pk
            noliaison = 'none'
            deselect = 'inline'
        html = u'<span class="noRelated" style="display: %s;">No liaison selected</span>' % noliaison
        html += u'<span class="relatedLiaisonWidgetTitle">%s</span>' % title
        html += u'<input type="hidden" name="%s" class="relatedLiaisonWidgetValue" value="%s" /> ' % (name, value)
        html += u'<span style="display: none;" class="listURL">%s</span> ' % reverse('ajax_liaison_list')
        html += u'<div style="display: none;" class="relatedLiaisonWidgetDialog" id="related-dialog" title="Select a liaison"></div> '
        html += '<input type="button" id="id_%s" value="Select liaison" /> ' % name
        html += '<input type="button" style="display: %s;" id="id_no_%s" value="Deselect liaison" />' % (deselect, name)
        return mark_safe(html)
