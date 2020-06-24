# Copyright The IETF Trust 2010-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.urls import reverse as urlreverse
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

    def render(self, name, value, **kwargs):
        html = '<span style="display: none" class="showAttachsOn">%s</span>' % conditional_escape(self.show_on)
        html += '<span style="display: none" class="attachEnabledLabel">%s</span>' % conditional_escape(self.label)
        if self.require:
            for i in self.require:
                html += '<span style="display: none" class="attachRequiredField">%s</span>' % conditional_escape(i)
            required_str = 'Please fill in %s to attach a new file' % conditional_escape(self.required_label)
            html += '<span style="display: none" class="attachDisabledLabel">%s</span>' % conditional_escape(required_str)
        html += '<input type="button" class="addAttachmentWidget btn btn-primary btn-sm" value="%s" />' % conditional_escape(self.label)
        return mark_safe(html)


class ShowAttachmentsWidget(Widget):
    def render(self, name, value, **kwargs):
        html = '<div id="id_%s">' % name
        html += '<span style="display: none" class="showAttachmentsEmpty form-control widget">No files attached</span>'
        html += '<div class="attachedFiles form-control widget">'
        if value and isinstance(value, QuerySet):
            for attachment in value:
                html += '<a class="initialAttach" href="%s">%s</a>&nbsp' % (conditional_escape(attachment.document.get_href()), conditional_escape(attachment.document.title))
                html += '<a class="btn btn-default btn-xs" href="{}">Edit</a>&nbsp'.format(urlreverse("ietf.liaisons.views.liaison_edit_attachment", kwargs={'object_id':attachment.statement.pk,'doc_id':attachment.document.pk}))
                html += '<a class="btn btn-default btn-xs" href="{}">Delete</a>&nbsp'.format(urlreverse("ietf.liaisons.views.liaison_delete_attachment", kwargs={'object_id':attachment.statement.pk,'attach_id':attachment.pk}))
                html += '<br />'
        else:
            html += 'No files attached'
        html += '</div></div>'
        return mark_safe(html)
