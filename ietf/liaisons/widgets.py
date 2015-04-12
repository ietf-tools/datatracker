from django.conf import settings
from django.db.models.query import QuerySet
from django.forms.widgets import Select, Widget
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape


class FromWidget(Select):

    def __init__(self, *args, **kwargs):
        super(FromWidget, self).__init__(*args, **kwargs)
        self.full_power_on = []
        self.reduced_to_set = []

    def render(self, name, value, attrs=None, choices=()):
        all_choices = list(self.choices) + list(choices)
        if (len(all_choices) != 1 or
            (isinstance(all_choices[0][1], (list, tuple)) and
             len(all_choices[0][1]) != 1)):
            base = super(FromWidget, self).render(name, value, attrs, choices)
        else:
            option = all_choices[0]
            if isinstance(option[1], (list, tuple)):
                option = option[1][0]
            value = option[0]
            text = option[1]
            base = u'<input type="hidden" value="%s" id="id_%s" name="%s" />%s' % (conditional_escape(value), conditional_escape(name), conditional_escape(name), conditional_escape(text))
        base += u' <a class="from_mailto form-control" href="">' + conditional_escape(self.submitter) + u'</a>'
        if self.full_power_on:
            base += '<div style="display: none;" class="reducedToOptions">'
            for from_code in self.full_power_on:
                base += '<span class="full_power_on_%s"></span>' % conditional_escape(from_code)
            for to_code in self.reduced_to_set:
                base += '<span class="reduced_to_set_%s"></span>' % conditional_escape(to_code)
            base += '</div>'
        return mark_safe(base)


class ReadOnlyWidget(Widget):
    def render(self, name, value, attrs=None):
        html = u'<div id="id_%s" class="form-control" style="height: auto; min-height: 34px;">%s</div>' % (conditional_escape(name), conditional_escape(value or ''))
        return mark_safe(html)


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
        html += u'<span style="display: none" class="showAttachmentsEmpty form-control" style="height: auto; min-height: 34px;">No files attached</span>'
        html += u'<div class="attachedFiles form-control" style="height: auto; min-height: 34px;">'
        if value and isinstance(value, QuerySet):
            for attachment in value:
                html += u'<a class="initialAttach" href="%s%s">%s</a><br />' % (settings.LIAISON_ATTACH_URL, conditional_escape(attachment.external_url), conditional_escape(attachment.title))
        else:
            html += u'No files attached'
        html += u'</div></div>'
        return mark_safe(html)
