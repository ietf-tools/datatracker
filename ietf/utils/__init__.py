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




def split_form(html, blocks):
    """Split the rendering of a form into a dictionary of named blocks.

    Takes the html of the rendered form as the first argument.

    Expects a dictionary as the second argument, with desired block
    name and a field specification as key:value pairs.

    The field specification can be either a list of field names, or
    a string with the field names separated by whitespace.

    The return value is a new dictionary, with the same keys as the
    block specification dictionary, and the form rendering matching
    the specified keys as the value.

    Any line in the rendered form which doesn't match any block's
    field list will cause an exception to be raised.
    """
    import re
    output = dict([(block,[]) for block in blocks])
    # handle field lists in string form
    for block in blocks:
        if type(blocks[block]) == type(""):
            blocks[block] = blocks[block].split()

    # collapse radio button html to one line
    html = re.sub('\n(.*type="radio".*\n)', "\g<1>", html)
    html = re.sub('(?m)^(.*type="radio".*)\n', "\g<1>", html)

    for line in html.split('\n'):
        found = False
        for block in blocks:
            for field in blocks[block]:
                if ('name="%s"' % field) in line:
                    output[block].append(line)
                    found = True
        if not found:
            raise LookupError("Could not place line in any section: '%s'" % line)

    for block in output:
        output[block] = "\n".join(output[block])

    return output

def mk_formatting_form(format="<span>%(label)s</span><span><ul>%(errors)s</ul>%(field)s%(help_text)s</span>",
                  labelfmt="%s:", fieldfmt="%s", errfmt="<li>%s</li>", error_wrap="<ul>%s</ul>", helpfmt="%s"):
    """Create a form class which formats its fields using the provided format string(s).

    The format string may use these format specifications:
        %(label)s
        %(errors)s
        %(field)s
        %(help_text)s

    The individual sub-formats must contain "%s" if defined.
    """
    class FormattingForm(forms.BaseForm):
        _format = format
        _labelfmt = labelfmt
        _fieldfmt = fieldfmt
        _errfmt   = errfmt
        _errwrap  = error_wrap
        _helpfmt = helpfmt
        def __getitem__(self, name):
            "Returns a BoundField with the given name."
            # syslog.syslog("FormattingForm.__getitem__(%s)" % (name))
            try:
                field = self.fields[name]
            except KeyError:
                # syslog.syslog("Exception: FormattingForm.__getitem__: Key %r not found" % (name))
                raise KeyError('Key %r not found in Form' % name)

            if not isinstance(field, forms.fields.Field):
                return field

            try:
                bf = forms.forms.BoundField(self, field, name)
            except Exception, e:
                # syslog.syslog("Exception: FormattingForm.__getitem__: %s" % (e))
                raise Exception(e)

            try:
                error_txt = "".join([self._errfmt % escape(error) for error in bf.errors])
                error_txt = error_txt and self._errwrap % error_txt
                label_txt = bf.label and self._labelfmt % bf.label_tag(escape(bf.label)) or ''
                field_txt = self._fieldfmt % unicode(bf)
                help_txt  = field.help_text and self._helpfmt % field.help_text or u''

            except Exception, e:
                # syslog.syslog("Exception: FormattingForm.__getitem__: %s" % (e))
                raise Exception(e)
                
            return self._format % {"label":label_txt, "errors":error_txt, "field":field_txt, "help_text":help_txt}

        def add_prefix(self, field_name):
            return self.prefix and ('%s_%s' % (self.prefix, field_name)) or field_name
        

    # syslog.syslog("Created new FormattingForm class: %s" % FormattingForm)

    return FormattingForm


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
