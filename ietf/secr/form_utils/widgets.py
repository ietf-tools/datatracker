"""
widgets for django-form-utils

parts of this code taken from http://www.djangosnippets.org/snippets/934/
 - thanks baumer1122

"""
import os
import posixpath

from django import forms
from django.conf import settings
from django.utils.functional import curry
from django.utils.safestring import mark_safe
from django.core.files.uploadedfile import SimpleUploadedFile as UploadedFile

from form_utils.settings import JQUERY_URL, FORM_UTILS_MEDIA_URL

try:
    from sorl.thumbnail.main import DjangoThumbnail
    def thumbnail(image_path, width, height):
        t = DjangoThumbnail(relative_source=image_path, requested_size=(width,height))
        return u'<img src="%s" alt="%s" />' % (t.absolute_url, image_path)
except ImportError:
    def thumbnail(image_path, width, height):
        absolute_url = posixpath.join(settings.MEDIA_URL, image_path)
        return u'<img src="%s" alt="%s" />' % (absolute_url, image_path)

class ImageWidget(forms.FileInput):
    template = '%(input)s<br />%(image)s'

    def __init__(self, attrs=None, template=None, width=200, height=200):
        if template is not None:
            self.template = template
        self.width = width
        self.height = height
        super(ImageWidget, self).__init__(attrs)

    def render(self, name, value, attrs=None):
        input_html = super(forms.FileInput, self).render(name, value, attrs)
        if hasattr(value, 'width') and hasattr(value, 'height'):
            image_html = thumbnail(value.name, self.width, self.height)
            output = self.template % {'input': input_html,
                                      'image': image_html}
        else:
            output = input_html
        return mark_safe(output)

class ClearableFileInput(forms.MultiWidget):
    default_file_widget_class = forms.FileInput
    template = '%(input)s Clear: %(checkbox)s'

    def __init__(self, file_widget=None,
                 attrs=None, template=None):
        if template is not None:
            self.template = template
        file_widget = file_widget or self.default_file_widget_class()
        super(ClearableFileInput, self).__init__(
            widgets=[file_widget, forms.CheckboxInput()],
            attrs=attrs)

    def render(self, name, value, attrs=None):
        if isinstance(value, list):
            self.value = value[0]
        else:
            self.value = value
        return super(ClearableFileInput, self).render(name, value, attrs)

    def decompress(self, value):
        # the clear checkbox is never initially checked
        return [value, None]

    def format_output(self, rendered_widgets):
        if self.value:
            return self.template % {'input': rendered_widgets[0],
                                    'checkbox': rendered_widgets[1]}
        return rendered_widgets[0]

root = lambda path: posixpath.join(FORM_UTILS_MEDIA_URL, path)

class AutoResizeTextarea(forms.Textarea):
    """
    A Textarea widget that automatically resizes to accomodate its contents.

    """
    class Media:

        js = (JQUERY_URL,
              root('form_utils/js/jquery.autogrow.js'),
              root('form_utils/js/autoresize.js'))

    def __init__(self, *args, **kwargs):
        attrs = kwargs.setdefault('attrs', {})
        try:
            attrs['class'] = "%s autoresize" % (attrs['class'],)
        except KeyError:
            attrs['class'] = 'autoresize'
        attrs.setdefault('cols', 80)
        attrs.setdefault('rows', 5)
        super(AutoResizeTextarea, self).__init__(*args, **kwargs)

class InlineAutoResizeTextarea(AutoResizeTextarea):
    def __init__(self, *args, **kwargs):
        attrs = kwargs.setdefault('attrs', {})
        try:
            attrs['class'] = "%s inline" % (attrs['class'],)
        except KeyError:
            attrs['class'] = 'inline'
        attrs.setdefault('cols', 40)
        attrs.setdefault('rows', 2)
        super(InlineAutoResizeTextarea, self).__init__(*args, **kwargs)

