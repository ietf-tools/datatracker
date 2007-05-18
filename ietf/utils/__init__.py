from listop import orl, flattenl
from log import log

from django.utils.html import escape
# look at snippets 59, 148, 99 for newforms helpers


# Caching accessor for the reverse of a ForeignKey relatinoship
# Started by axiak on #django
class FKAsOneToOne(object):
    def __init__(self, field, reverse = False, query = None):
        self.field = field
        self.reverse = reverse
	self.query = query
    
    def __get_attr(self, instance):
        if self.reverse:
            field_name = '%s_set' % self.field
        else:
            field_name = self.field
        return getattr(instance, field_name)

    def __get__(self, instance, Model):
        if not hasattr(instance, '_field_values'):
            instance._field_values = {}
        try:
            return instance._field_values[self.field]
	except KeyError:
	    pass

        if self.reverse:
            value_set = self.__get_attr(instance).all()
	    if self.query:
		value_set = value_set.filter(self.query)
	    try:
                instance._field_values[self.field] = value_set[0]
	    except IndexError:
                instance._field_values[self.field] = None
        else:
            instance._field_values[self.field] = self.__get_attr(instance)

        return instance._field_values[self.field]

    def __set__(self, instance, value):
        if self.reverse:
            # this is dangerous
            #other_instance = self.__get_attr(instance).all()[0]
            #setattr(other_instance, self.field, value)
            #other_instance.save()
	    raise NotImplemented
        else:
            setattr(instance, self.field, value)


def makeFormattingForm(template=None):
    """Create a form class which formats its fields using the provided template

    The template is provided with a dictionary containing the following keys, value
    pairs:

        "label":        field label, if any,
        "errors":       list of errors, if any,
        "field":        widget rendering for an unbound form / field value for a bound form,
        "help_text":    field help text, if any

    """
    from django.template import loader
    import django.newforms as forms

    class FormattingForm(forms.BaseForm):
        _template = template
        def __getitem__(self, name):
            "Returns a BoundField with the given name."
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
    return FormattingForm
