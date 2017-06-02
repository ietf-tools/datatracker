"""
We have a plethora of different wrapping functions in use, and probably should
reduce the number. In some cases, we should not wrap at all, instead letting
the browser wrap, using for instance this css:

    .pasted {
        white-space: pre-wrap;
        word-break: keep-all;
    }

In order to get a grasp of what we have got, and how the different variations
behave, here are some doctests to verify the output of each function, and
a __main__ which will print all the examples if this file is run as
  $ python ietf/utils/text.py


This is the input text, with long lines in all 4 paragraphs.  2 Paragraphs are
indented:

>>> text = '''
... Lorem ipsum dolor sit amet, consectetur adipiscing elit.
... Aliquam euismod semper hendrerit. Morbi fringilla semper
... libero, eu auctor mauris ullamcorper et. Phasellus quis dolor in nibh pretium cursus et molestie lacus. Morbi ut
... magna mauris. Sed feugiat maximus finibus. Nullam dapibus
... aliquam nibh sed varius. Curabitur elit nunc, lacinia
... gravida lectus non, interdum porttitor magna.
... 
...     Sed suscipit, libero vel ullamcorper malesuada, enim odio vestibulum quam,
...     nec luctus ligula diam eget sapien. Proin a lectus at eros ullamcorper
...     mollis.  Aenean vehicula lacinia arcu, sed auctor mi cursus ut.
... 
...     
...     Pellentesque porta felis nec odio tincidunt pellentesque luctus in massa.  Duis lacus augue, facilisis eu congue eu, ultricies eget urna. In id risus
...     vestibulum, suscipit lorem sit amet, tempus libero.
... 
... Etiam a purus pretium, mollis elit at, iaculis odio. Donec imperdiet lacinia odio at ultrices. Duis hendrerit consequat augue ac efficitur. Etiam vel placerat arcu. Aenean sodales lorem ut auctor rutrum. Vestibulum auctor fringilla felis ac tempor. Nullam tincidunt pellentesque sapien, non facilisis lectus sagittis ac. Vivamus tempus nibh a laoreet hendrerit. Suspendisse tempor neque erat, quis commodo ex aliquam ut. Duis egestas dignissim risus, non semper lectus commodo non. 
... 
... '''


Some preliminary setup for the tests ...

>>> import os
>>> os.environ["DJANGO_SETTINGS_MODULE"] = "ietf.settings"
>>> import django
>>> django.setup()
>>> 
>>> from ietf.doc.templatetags.ietf_filters import wrap_text, wrap_long_lines
>>> from django.utils.text import wrap as django_wrap
>>> from ietf.utils.text import fill, wrap, wrap_text_if_unwrapped
>>>

The first two tests here give reasonable results.  The difference lies in
how they deal with remaining lines in a paragraph where there's been a
too long line:


>>> # ----------------------------------------------------------------------
>>> print(wrap_text(text, width=80))
<BLANKLINE>
Lorem ipsum dolor sit amet, consectetur adipiscing elit.
Aliquam euismod semper hendrerit. Morbi fringilla semper
libero, eu auctor mauris ullamcorper et. Phasellus quis dolor in nibh pretium
cursus et molestie lacus. Morbi ut magna mauris. Sed feugiat maximus finibus.
Nullam dapibus aliquam nibh sed varius. Curabitur elit nunc, lacinia gravida
lectus non, interdum porttitor magna.
<BLANKLINE>
    Sed suscipit, libero vel ullamcorper malesuada, enim odio vestibulum quam,
    nec luctus ligula diam eget sapien. Proin a lectus at eros ullamcorper
    mollis.  Aenean vehicula lacinia arcu, sed auctor mi cursus ut.
<BLANKLINE>
    Pellentesque porta felis nec odio tincidunt pellentesque luctus in massa. 
    Duis lacus augue, facilisis eu congue eu, ultricies eget urna. In id risus
    vestibulum, suscipit lorem sit amet, tempus libero.
<BLANKLINE>
Etiam a purus pretium, mollis elit at, iaculis odio. Donec imperdiet lacinia
odio at ultrices. Duis hendrerit consequat augue ac efficitur. Etiam vel
placerat arcu. Aenean sodales lorem ut auctor rutrum. Vestibulum auctor
fringilla felis ac tempor. Nullam tincidunt pellentesque sapien, non facilisis
lectus sagittis ac. Vivamus tempus nibh a laoreet hendrerit. Suspendisse tempor
neque erat, quis commodo ex aliquam ut. Duis egestas dignissim risus, non
semper lectus commodo non.
<BLANKLINE>
<BLANKLINE>
>>> # ----------------------------------------------------------------------

>>> # ----------------------------------------------------------------------
>>> print(wrap(text, width=80))
<BLANKLINE>
Lorem ipsum dolor sit amet, consectetur adipiscing elit.
Aliquam euismod semper hendrerit. Morbi fringilla semper
libero, eu auctor mauris ullamcorper et. Phasellus quis dolor in nibh pretium
cursus et molestie lacus. Morbi ut
magna mauris. Sed feugiat maximus finibus. Nullam dapibus
aliquam nibh sed varius. Curabitur elit nunc, lacinia
gravida lectus non, interdum porttitor magna.
<BLANKLINE>
    Sed suscipit, libero vel ullamcorper malesuada, enim odio vestibulum quam,
    nec luctus ligula diam eget sapien. Proin a lectus at eros ullamcorper
    mollis.  Aenean vehicula lacinia arcu, sed auctor mi cursus ut.
<BLANKLINE>
<BLANKLINE>
    Pellentesque porta felis nec odio tincidunt pellentesque luctus in massa.
    Duis lacus augue, facilisis eu congue eu, ultricies eget urna. In id risus
    vestibulum, suscipit lorem sit amet, tempus libero.
<BLANKLINE>
Etiam a purus pretium, mollis elit at, iaculis odio. Donec imperdiet lacinia
odio at ultrices. Duis hendrerit consequat augue ac efficitur. Etiam vel
placerat arcu. Aenean sodales lorem ut auctor rutrum. Vestibulum auctor
fringilla felis ac tempor. Nullam tincidunt pellentesque sapien, non facilisis
lectus sagittis ac. Vivamus tempus nibh a laoreet hendrerit. Suspendisse tempor
neque erat, quis commodo ex aliquam ut. Duis egestas dignissim risus, non semper
lectus commodo non.
<BLANKLINE>
<BLANKLINE>
>>> # ----------------------------------------------------------------------

In the next few functions, things start to go more or less awry:


>>> # ----------------------------------------------------------------------
>>> print(wrap_long_lines(text, width=80))
<BLANKLINE>
Lorem ipsum dolor sit amet, consectetur adipiscing elit.
Aliquam euismod semper hendrerit. Morbi fringilla semper
libero, eu auctor mauris ullamcorper et. Phasellus quis dolor in nibh pretium
cursus et molestie lacus. Morbi ut magna mauris. Sed feugiat maximus finibus.
Nullam dapibus aliquam nibh sed varius. Curabitur elit nunc, lacinia gravida
lectus non, interdum porttitor magna.
<BLANKLINE>
    Sed suscipit, libero vel ullamcorper malesuada, enim odio vestibulum quam,
    nec luctus ligula diam eget sapien. Proin a lectus at eros ullamcorper
    mollis.  Aenean vehicula lacinia arcu, sed auctor mi cursus ut.
<BLANKLINE>
    Pellentesque porta felis nec odio tincidunt pellentesque luctus in massa. 
Duis lacus augue, facilisis eu congue eu, ultricies eget urna. In id risus    
vestibulum, suscipit lorem sit amet, tempus libero.
<BLANKLINE>
Etiam a purus pretium, mollis elit at, iaculis odio. Donec imperdiet lacinia
odio at ultrices. Duis hendrerit consequat augue ac efficitur. Etiam vel
placerat arcu. Aenean sodales lorem ut auctor rutrum. Vestibulum auctor
fringilla felis ac tempor. Nullam tincidunt pellentesque sapien, non facilisis
lectus sagittis ac. Vivamus tempus nibh a laoreet hendrerit. Suspendisse tempor
neque erat, quis commodo ex aliquam ut. Duis egestas dignissim risus, non
semper lectus commodo non.
<BLANKLINE>
<BLANKLINE>
>>> # ----------------------------------------------------------------------


>>> # ----------------------------------------------------------------------
>>> print(fill(text, width=80))
<BLANKLINE>
Lorem ipsum dolor sit amet, consectetur adipiscing elit.
Aliquam euismod semper
hendrerit. Morbi fringilla semper
libero, eu auctor mauris ullamcorper et.
Phasellus quis dolor in nibh pretium cursus et molestie lacus. Morbi ut
magna
mauris. Sed feugiat maximus finibus. Nullam dapibus
aliquam nibh sed varius.
Curabitur elit nunc, lacinia
gravida lectus non, interdum porttitor magna.
<BLANKLINE>
    Sed suscipit, libero vel ullamcorper malesuada, enim odio vestibulum quam,
    nec luctus ligula diam eget sapien. Proin a lectus at eros ullamcorper
    mollis.  Aenean vehicula lacinia arcu, sed auctor mi cursus ut.
<BLANKLINE>
<BLANKLINE>
    Pellentesque porta felis nec odio tincidunt pellentesque luctus in
massa.  Duis lacus augue, facilisis eu congue eu, ultricies eget urna. In id
risus
    vestibulum, suscipit lorem sit amet, tempus libero.
<BLANKLINE>
Etiam a purus pretium, mollis elit at, iaculis odio. Donec imperdiet lacinia
odio at ultrices. Duis hendrerit consequat augue ac efficitur. Etiam vel
placerat arcu. Aenean sodales lorem ut auctor rutrum. Vestibulum auctor
fringilla felis ac tempor. Nullam tincidunt pellentesque sapien, non facilisis
lectus sagittis ac. Vivamus tempus nibh a laoreet hendrerit. Suspendisse tempor
neque erat, quis commodo ex aliquam ut. Duis egestas dignissim risus, non semper
lectus commodo non.
>>> # ----------------------------------------------------------------------


>>> # ----------------------------------------------------------------------
>>> print(django_wrap(text, width=80))
<BLANKLINE>
Lorem ipsum dolor sit amet, consectetur adipiscing elit.
Aliquam euismod semper hendrerit. Morbi fringilla semper
libero, eu auctor mauris ullamcorper et. Phasellus quis dolor in nibh pretium
cursus et molestie lacus. Morbi ut
magna mauris. Sed feugiat maximus finibus. Nullam dapibus
aliquam nibh sed varius. Curabitur elit nunc, lacinia
gravida lectus non, interdum porttitor magna.
<BLANKLINE>
    Sed suscipit, libero vel ullamcorper malesuada, enim odio vestibulum quam,
    nec luctus ligula diam eget sapien. Proin a lectus at eros ullamcorper
    mollis.  Aenean vehicula lacinia arcu, sed auctor mi cursus ut.
<BLANKLINE>
<BLANKLINE>
    Pellentesque porta felis nec odio tincidunt pellentesque luctus in massa. 
Duis lacus augue, facilisis eu congue eu, ultricies eget urna. In id risus
    vestibulum, suscipit lorem sit amet, tempus libero.
<BLANKLINE>
Etiam a purus pretium, mollis elit at, iaculis odio. Donec imperdiet lacinia
odio at ultrices. Duis hendrerit consequat augue ac efficitur. Etiam vel
placerat arcu. Aenean sodales lorem ut auctor rutrum. Vestibulum auctor
fringilla felis ac tempor. Nullam tincidunt pellentesque sapien, non facilisis
lectus sagittis ac. Vivamus tempus nibh a laoreet hendrerit. Suspendisse tempor
neque erat, quis commodo ex aliquam ut. Duis egestas dignissim risus, non semper
lectus commodo non. 
<BLANKLINE>
<BLANKLINE>
>>> # ----------------------------------------------------------------------

This last one is just a wrapper around django.utils.text.wrap() above, so
has the same deficiencies as that one.  Using one of the two first options
instead of the django.wrap() here might be better:

>>> # ----------------------------------------------------------------------
>>> print(wrap_text_if_unwrapped(text, width=80))
<BLANKLINE>
Lorem ipsum dolor sit amet, consectetur adipiscing elit.
Aliquam euismod semper hendrerit. Morbi fringilla semper
libero, eu auctor mauris ullamcorper et. Phasellus quis dolor in nibh pretium
cursus et molestie lacus. Morbi ut
magna mauris. Sed feugiat maximus finibus. Nullam dapibus
aliquam nibh sed varius. Curabitur elit nunc, lacinia
gravida lectus non, interdum porttitor magna.
<BLANKLINE>
    Sed suscipit, libero vel ullamcorper malesuada, enim odio vestibulum quam,
    nec luctus ligula diam eget sapien. Proin a lectus at eros ullamcorper
    mollis.  Aenean vehicula lacinia arcu, sed auctor mi cursus ut.
<BLANKLINE>
<BLANKLINE>
    Pellentesque porta felis nec odio tincidunt pellentesque luctus in massa. 
Duis lacus augue, facilisis eu congue eu, ultricies eget urna. In id risus
    vestibulum, suscipit lorem sit amet, tempus libero.
<BLANKLINE>
Etiam a purus pretium, mollis elit at, iaculis odio. Donec imperdiet lacinia
odio at ultrices. Duis hendrerit consequat augue ac efficitur. Etiam vel
placerat arcu. Aenean sodales lorem ut auctor rutrum. Vestibulum auctor
fringilla felis ac tempor. Nullam tincidunt pellentesque sapien, non facilisis
lectus sagittis ac. Vivamus tempus nibh a laoreet hendrerit. Suspendisse tempor
neque erat, quis commodo ex aliquam ut. Duis egestas dignissim risus, non semper
lectus commodo non. 
<BLANKLINE>
<BLANKLINE>
>>> # ----------------------------------------------------------------------
"""

from __future__ import unicode_literals

import re
import unicodedata
import textwrap

from django.utils.functional import allow_lazy
from django.utils import six
from django.utils.safestring import mark_safe

if __name__ == '__main__':
    print __doc__.replace('<BLANKLINE>','')


def xslugify(value):
    """
    Converts to ASCII. Converts spaces to hyphens. Removes characters that
    aren't alphanumerics, underscores, slash, or hyphens. Converts to
    lowercase.  Also strips leading and trailing whitespace.
    (I.e., does the same as slugify, but also converts slashes to dashes.)
    """
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub('[^\w\s/-]', '', value).strip().lower()
    return mark_safe(re.sub('[-\s/]+', '-', value))
xslugify = allow_lazy(xslugify, six.text_type)

def strip_prefix(text, prefix):
    if text.startswith(prefix):
        return text[len(prefix):]
    else:
        return text

def strip_suffix(text, suffix):
    if text.endswith(suffix):
        return text[:-len(suffix)]
    else:
        return text    

def fill(text, width):
    """Wraps each paragraph in text (a string) so every line
    is at most width characters long, and returns a single string
    containing the wrapped paragraph.
    """
    width = int(width)
    paras = text.replace("\r\n","\n").replace("\r","\n").split("\n\n")
    wrapped = []
    for para in paras:
        if para:
            lines = para.split("\n")
            maxlen = max([len(line) for line in lines])
            if maxlen > width:
                para = textwrap.fill(para, width, replace_whitespace=False)
            wrapped.append(para)
    return "\n\n".join(wrapped)
        
def wrap(text, width=80):

    textLines = text.split('\n')
    wrapped_lines = []
    # Preserve any indent (after the general indent)
    for line in textLines:
        preservedIndent = ''
        existIndent = re.search(r'^(\W+)', line)
        # Change the existing wrap indent to the original one
        if (existIndent):
            preservedIndent = existIndent.groups()[0]
        wrapped_lines.append(textwrap.fill(line, width=80, subsequent_indent=preservedIndent))
    text = '\n'.join(wrapped_lines)
    return text

def wrap_text_if_unwrapped(text, width=72, max_tolerated_line_length=100): 
    from django.utils.text import wrap
    text = re.sub(" *\r\n", "\n", text) # get rid of DOS line endings 
    text = re.sub(" *\r", "\n", text)   # get rid of MAC line endings 

    contains_long_lines = any(" " in l and len(l) > max_tolerated_line_length 
                              for l in text.split("\n")) 

    if contains_long_lines: 
        return wrap(text, width) 
    else: 
        return text 

def isascii(text):
    try:
        text.encode('ascii')
        return True
    except UnicodeEncodeError:
        return False
        
