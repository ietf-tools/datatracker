# Copyright The IETF Trust 2007, All Rights Reserved

from django.utils.html import escape

def makeTemplatedForm(template=None):
    """Create a form class which formats its fields using the provided template

    The template is provided with a dictionary containing the following key-value
    pairs:

        "label":        field label, if any,
        "errors":       list of errors, if any,
        "text":         widget rendering for an unbound form / field value for a bound form,
        "help_text":    field help text, if any
    """
    from django.template import loader
    import django.newforms as forms

    class TemplatedForm(forms.BaseForm):
        _template = template
        def __getitem__(self, name):
            "Returns a rendered field with the given name."
            #syslog.syslog("FormattingForm.__getitem__(%s)" % (name, ))
            try:
                field = self.fields[name]
            except KeyError:
                raise KeyError('Key %r not found in Form' % name)
            if not isinstance(field, forms.fields.Field):
                return field
            bf = forms.forms.BoundField(self, field, name)
            errors = [escape(error) for error in bf.errors]
            rendering = loader.render_to_string(self._template, { "errors": errors, "label": bf.label, "text": unicode(bf), "help_text": field.help_text, "field":field })
            return rendering
    return TemplatedForm
