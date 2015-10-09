from django.conf import settings
from django.core.urlresolvers import reverse as urlreverse
from django.db.models.query import QuerySet
from django.forms.widgets import Widget
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape


class ButtonWidget(Widget):
    def __init__(self, *args, **kwargs):
        self.label = kwargs.pop('label', None)
        self.show_on = kwargs.pop('show_on', None)
        self.require = kwargs.pop('require', None)
        self.required_label = kwargs.pop('required_label', None)
        super(ButtonWidget, self).__init__(*args, **kwargs)

    def render(self, name, value, attrs=None):
        html = u'<span style="display: none" class="showAttachsOn">%s</span>' % conditional_escape(self.show_on)
        html += u'<span style="display: none" class="attachEnabledLabel">%s</span>' % conditional_escape(self.label)
        if self.require:
            for i in self.require:
                html += u'<span style="display: none" class="attachRequiredField">%s</span>' % conditional_escape(i)
            required_str = u'Please fill in %s to attach a new file' % conditional_escape(self.required_label)
            html += u'<span style="display: none" class="attachDisabledLabel">%s</span>' % conditional_escape(required_str)
        html += u'<input type="button" class="addAttachmentWidget btn btn-primary btn-sm" value="%s" />' % conditional_escape(self.label)
        return mark_safe(html)


class ShowAttachmentsWidget(Widget):
    def render(self, name, value, attrs=None):
        html = u'<div id="id_%s">' % name
        html += u'<span style="display: none" class="showAttachmentsEmpty form-control widget">No files attached</span>'
        html += u'<div class="attachedFiles form-control widget">'
        if value and isinstance(value, QuerySet):
            for attachment in value:
                html += u'<a class="initialAttach" href="%s%s">%s</a>&nbsp' % (settings.LIAISON_ATTACH_URL, conditional_escape(attachment.document.external_url), conditional_escape(attachment.document.title))
                html += u'<a class="btn btn-default btn-xs" href="{}">Edit</a>&nbsp'.format(urlreverse("ietf.liaisons.views.liaison_edit_attachment", kwargs={'object_id':attachment.statement.pk,'doc_id':attachment.document.pk}))
                html += u'<a class="btn btn-default btn-xs" href="{}">Delete</a>&nbsp'.format(urlreverse("ietf.liaisons.views.liaison_delete_attachment", kwargs={'object_id':attachment.statement.pk,'attach_id':attachment.pk}))
                html += u'<br />'
        else:
            html += u'No files attached'
        html += u'</div></div>'
        return mark_safe(html)