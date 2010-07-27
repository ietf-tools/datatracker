from django.forms.widgets import Select, Widget
from django.utils.safestring import mark_safe


class FromWidget(Select):

    def render(self, name, value, attrs=None, choices=()):
        all_choices = list(self.choices) + list(choices)
        if len(all_choices)!=1 or \
            (isinstance(all_choices[0], (list, tuple)) and \
             len(all_choices[0][1])!=1):
            base = super(FromWidget, self).render(name, value, attrs, choices)
        else:
            base = u'<input type="hidden" value="%s" />%s' % all_choices[0]
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
        if not value:
            html += u'<div class="attachedFiles">No files attached</div>' 
        else:
            pass
        html += u'</div>'
        return mark_safe(html)
