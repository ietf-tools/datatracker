from django.forms.widgets import Select, Widget
from django.utils.safestring import mark_safe


class FromWidget(Select):

    def render(self, name, value, attrs=None, choices=()):
        all_choices = list(self.choices) + list(choices)
        if len(all_choices)!=1:
            base = super(FromWidget, self).render(name, value, attrs, choices)
        else:
            base = u'<input type="hidden" value="%s" />%s' % all_choices[0]
        base += u' (<a class="from_mailto" href="">' + self.submitter + u'</a>)'
        return mark_safe(base)


class ReadOnlyWidget(Widget):

    def render(self, name, value, attrs=None):
        html = u'<div id="id_%s">%s</div>' % (name, value or '')
        return mark_safe(html)
