# Copyright The IETF Trust 2007, All Rights Reserved

import textwrap
from django import template
from django.utils.html import escape, fix_ampersands
from django.template.defaultfilters import linebreaksbr, wordwrap, stringfilter
from django.template import resolve_variable
from django.utils.safestring import mark_safe, SafeData
try:
    from email import utils as emailutils
except ImportError:
    from email import Utils as emailutils
import re
import datetime
import types
from django.template import RequestContext

register = template.Library()

@register.filter(name='expand_comma')
def expand_comma(value):
    """
    Adds a space after each comma, to allow word-wrapping of
    long comma-separated lists."""
    return value.replace(",", ", ")

@register.filter(name='format_charter')
def format_charter(value):
    return value.replace("\n\n", "</p><p>").replace("\n","<br/>\n")

@register.filter(name='indent')
def indent(value):
    return value.replace("\n", "\n  ");

@register.filter(name='parse_email_list')
def parse_email_list(value):
    """
    Parse a list of comma-seperated email addresses into
    a list of mailto: links.

    Splitting a string of email addresses should return a list:

    >>> unicode(parse_email_list('joe@example.org, fred@example.com'))
    u'<a href="mailto:joe@example.org">joe@example.org</a>, <a href="mailto:fred@example.com">fred@example.com</a>'

    Parsing a non-string should return the input value, rather than fail:
    
    >>> parse_email_list(['joe@example.org', 'fred@example.com'])
    ['joe@example.org', 'fred@example.com']
    
    Null input values should pass through silently:
    
    >>> parse_email_list('')
    ''

    >>> parse_email_list(None)


    """
    if value and isinstance(value, (types.StringType,types.UnicodeType)): # testing for 'value' being true isn't necessary; it's a fast-out route
        addrs = re.split(", ?", value)
        ret = []
        for addr in addrs:
            (name, email) = emailutils.parseaddr(addr)
            if not(name):
                name = email
            ret.append('<a href="mailto:%s">%s</a>' % ( fix_ampersands(email), escape(name) ))
        return ", ".join(ret)
    else:
        return value
    
# there's an "ahref -> a href" in GEN_UTIL
# but let's wait until we understand what that's for.
@register.filter(name='make_one_per_line')
def make_one_per_line(value):
    """
    Turn a comma-separated list into a carraige-return-seperated list.

    >>> make_one_per_line("a, b, c")
    'a\\nb\\nc'

    Pass through non-strings:
    
    >>> make_one_per_line([1, 2])
    [1, 2]

    >>> make_one_per_line(None)

    """
    if value and isinstance(value, (types.StringType,types.UnicodeType)):
        return re.sub(", ?", "\n", value)
    else:
        return value
        
@register.filter(name='timesum')
def timesum(value):
    """
    Sum the times in a list of dicts; used for sql query debugging info"""
    sum = 0.0
    for v in value:
        sum += float(v['time'])
    return sum

@register.filter(name='keep_spacing')
def keep_spacing(value):
    """
    Replace any two spaces with one &nbsp; and one space so that
    HTML output doesn't collapse them."""
    return value.replace('  ', '&nbsp; ')

@register.filter(name='format_textarea')
def format_textarea(value):
    """
    Escapes HTML, except for <b>, </b>, <br>.

    Adds <br> at the end like the builtin linebreaksbr.

    Also calls keep_spacing."""
    return keep_spacing(linebreaksbr(escape(value).replace('&lt;b&gt;','<b>').replace('&lt;/b&gt;','</b>').replace('&lt;br&gt;','<br>')))

@register.filter(name='sanitize_html')
def sanitize_html(value):
    """Sanitizes an HTML fragment.
    This means both fixing broken html and restricting elements and
    attributes to those deemed acceptable.  See ietf/utils/html.py
    for the details.
    """
    from ietf.utils.html import sanitize_html
    return sanitize_html(value)


# For use with ballot view
@register.filter(name='bracket')
def square_brackets(value):
    """Adds square brackets around text."""
    if isinstance(value, (types.StringType,types.UnicodeType)):
	if value == "":
	     value = " "
        return "[ %s ]" % value
    elif value > 0:
        return "[ X ]"
    elif value < 0:
        return "[ . ]"
    else:
        return "[   ]"

@register.filter(name='fill')
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

@register.filter(name='rfcspace')
def rfcspace(string):
    """
    If the string is an RFC designation, and doesn't have
    a space between 'RFC' and the rfc-number, a space is
    added
    """
    string = str(string)
    if string[:3].lower() == "rfc" and string[3] != " ":
        return string[:3] + " " + string[3:]
    else:
        return string

@register.filter(name='rfcnospace')
def rfcnospace(string):
    """
    If the string is an RFC designation, and does have
    a space between 'RFC' and the rfc-number, remove it.
    """
    string = str(string)
    if string[:3].lower() == "rfc" and string[3] == " ":
        return string[:3] + string[4:]
    else:
        return string

@register.filter(name='rfcurl')
def rfclink(string):
    """
    This takes just the RFC number, and turns it into the
    URL for that RFC.
    """
    string = str(string);
    return "http://tools.ietf.org/html/rfc" + string;

@register.filter(name='urlize_ietf_docs')
def urlize_ietf_docs(string, autoescape=None):
    """
    Make occurrences of RFC NNNN and draft-foo-bar links to /doc/.
    """
    if autoescape and not isinstance(string, SafeData):
        string = escape(string)
    string = re.sub("(?<!>)(RFC ?)0{0,3}(\d+)", "<a href=\"/doc/rfc\\2/\">\\1\\2</a>", string)
    string = re.sub("(?<!>)(BCP ?)0{0,3}(\d+)", "<a href=\"http://tools.ietf.org/html/bcp\\2/\">\\1\\2</a>", string)
    string = re.sub("(?<!>)(STD ?)0{0,3}(\d+)", "<a href=\"http://tools.ietf.org/html/std\\2/\">\\1\\2</a>", string)
    string = re.sub("(?<!>)(FYI ?)0{0,3}(\d+)", "<a href=\"http://tools.ietf.org/html/fyi\\2/\">\\1\\2</a>", string)
    string = re.sub("(?<!>)(draft-[-0-9a-zA-Z._+]+)", "<a href=\"/doc/\\1/\">\\1</a>", string)
    return mark_safe(string)
urlize_ietf_docs.is_safe = True
urlize_ietf_docs.needs_autoescape = True
urlize_ietf_docs = stringfilter(urlize_ietf_docs)

@register.filter(name='dashify')
def dashify(string):
    """
    Replace each character in string with '-', to produce
    an underline effect for plain text files.
    """
    return re.sub('.', '-', string)

@register.filter(name='lstrip')
def lstripw(string, chars):
    """Strip matching leading characters from words in string"""
    return " ".join([word.lstrip(chars) for word in string.split()])

@register.filter(name='timesince_days')
def timesince_days(date):
    """Returns the number of days since 'date' (relative to now)"""
    if date.__class__ is not datetime.datetime:
        date = datetime.datetime(date.year, date.month, date.day)
    delta = datetime.datetime.now() - date
    return delta.days

@register.filter(name='truncate_ellipsis')
def truncate_ellipsis(text, arg):
    num = int(arg)
    if len(text) > num:
        return escape(text[:num-1])+"&hellip;"
    else:
        return escape(text)
    
@register.filter(name="wrap_long_lines")
def wrap_long_lines(text):
    """Wraps long lines without loosing the formatting and indentation
       of short lines"""
    if not isinstance(text, (types.StringType,types.UnicodeType)):
        return text
    text = re.sub(" *\r\n", "\n", text) # get rid of DOS line endings
    text = re.sub(" *\r", "\n", text)   # get rid of MAC line endings
    text = re.sub("( *\n){3,}", "\n\n", text) # get rid of excessive vertical whitespace
    lines = text.split("\n")
    filled = []
    wrapped = False
    for line in lines:
        if wrapped and line.strip() != "":
            line = filled[-1] + " " + line
            filled = filled[:-1]
        else:
            wrapped = False
        while (len(line) > 80) and (" " in line[:80]):
            wrapped = True
            breakpoint = line.rfind(" ",0,80)
            filled += [ line[:breakpoint] ]
            line = line[breakpoint+1:]
        filled += [ line.rstrip() ]
    return "\n".join(filled)

@register.filter(name="wrap_text")
def wrap_text(text, width=72):
    """Wraps long lines without loosing the formatting and indentation
       of short lines"""
    if not isinstance(text, (types.StringType,types.UnicodeType)):
        return text
    text = re.sub(" *\r\n", "\n", text) # get rid of DOS line endings
    text = re.sub(" *\r", "\n", text)   # get rid of MAC line endings
    text = re.sub("( *\n){3,}", "\n\n", text) # get rid of excessive vertical whitespace
    lines = text.split("\n")
    filled = []
    wrapped = False
    for line in lines:
        line = line.expandtabs()
        indent = " " * (len(line) - len(line.lstrip()))
        if wrapped and line.strip() != "" and indent == prev_indent:
            line = filled[-1] + " " + line.lstrip()
            filled = filled[:-1]
        else:
            wrapped = False
        while (len(line) > width) and (" " in line[:width]):
            wrapped = True
            breakpoint = line.rfind(" ",0,width)
            filled += [ line[:breakpoint] ]
            line = indent + line[breakpoint+1:]
        filled += [ line.rstrip() ]
        prev_indent = indent
    return "\n".join(filled)

@register.filter(name="id_index_file_types")
def id_index_file_types(text):
    r = ".txt"
    if text.find("txt") < 0:
        return r
    if text.find("ps") >= 0:
        r = r + ",.ps"
    if text.find("pdf") >= 0:
        r = r + ",.pdf"
    return r

@register.filter(name="id_index_wrap")
def id_index_wrap(text):
    x = wordwrap(text, 72)
    x = x.replace("\n", "\n  ")
    return "  "+x.strip()

@register.filter(name="compress_empty_lines")
def compress_empty_lines(text):
    text = re.sub("( *\n){3,}", "\n\n", text)
    return text

@register.filter(name="remove_empty_lines")
def remove_empty_lines(text):
    text = re.sub("( *\n){2,}", "\n", text)
    return text

@register.filter(name='linebreaks_crlf')
def linebreaks_crlf(text):
    """
    Normalize all linebreaks to CRLF.
    """
    # First, map CRLF to LF
    text = text.replace("\r\n", "\n")
    # Next, map lone CRs to LFs
    text = text.replace("\r", "\n")
    # Finally, map LFs to CRLFs
    text = text.replace("\n", "\r\n")
    return text

@register.filter(name='linebreaks_lf')
def linebreaks_lf(text):
    """
    Normalize all linebreaks to LF.
    """
    # First, map CRLF to LF
    text = text.replace("\r\n", "\n")
    # Finally, map lone CRs to LFs
    text = text.replace("\r", "\n")
    return text

@register.filter(name='clean_whitespace')
def clean_whitespace(text):
    """
    Map all ASCII control characters (0x00-0x1F) to spaces, and 
    remove unnecessary spaces.
    """
    text = re.sub("[\000-\040]+", " ", text)
    return text.strip()

@register.filter(name='unescape')
def unescape(text):
    """
    Unescape &nbsp;/&gt;/&lt; 
    """
    text = text.replace("&gt;", ">")
    text = text.replace("&lt;", "<")
    text = text.replace("&amp;", "&")
    text = text.replace("<br>", "\n")
    text = text.replace("<br/>", "\n")
    return text

@register.filter(name='new_enough')
def new_enough(x,request):
    if "new_enough" in request.COOKIES:
        days = int(request.COOKIES["new_enough"])
    else:
        days = 14
    return x < days

@register.filter(name='expires_soon')
def expires_soon(x,request):
    if "expires_soon" in request.COOKIES:
        days = int(request.COOKIES["expires_soon"])
    else:
        days = 14
    return x > -days

@register.filter(name='greater_than')
def greater_than(x, y):
    return x > int(y)

@register.filter(name='less_than')
def less_than(x, y):
    return x < int(y)

@register.filter(name='equal')
def equal(x, y):
    return str(x)==str(y)

@register.filter(name='startswith')
def startswith(x, y):
    return unicode(x).startswith(y)

# based on http://www.djangosnippets.org/snippets/847/ by 'whiteinge'
@register.filter
def in_group(user, groups):
    return user and user.is_authenticated() and bool(user.groups.filter(name__in=groups.split(',')).values('name'))

@register.filter
def stable_dictsort(value, arg):
    """
    Like dictsort, except it's stable (preserves the order of items 
    whose sort key is the same). See also bug report
    http://code.djangoproject.com/ticket/12110
    """
    decorated = [(resolve_variable('var.' + arg, {'var' : item}), item) for item in value]
    decorated.sort(lambda a, b: cmp(a[0], b[0]) if a[0] and b[0] else -1 if b[0] else 1 if a[0] else 0)
    return [item[1] for item in decorated]

def _test():
    import doctest
    doctest.testmod()

if __name__ == "__main__":
    _test()

