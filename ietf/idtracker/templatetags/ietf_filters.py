# Copyright The IETF Trust 2007, All Rights Reserved

import textwrap
from django import template
from django.utils.html import escape, fix_ampersands, linebreaks
from django.template.defaultfilters import linebreaksbr
try:
    from email import utils as emailutils
except ImportError:
    from email import Utils as emailutils
import re
import datetime
#from ietf.utils import log

register = template.Library()

@register.filter(name='expand_comma')
def expand_comma(value):
    """
    Adds a space after each comma, to allow word-wrapping of
    long comma-separated lists."""
    return value.replace(",", ", ")

@register.filter(name='parse_email_list')
def parse_email_list(value):
    """
    Parse a list of comma-seperated email addresses into
    a list of mailto: links.

    Splitting a string of email addresses should return a list:

    >>> parse_email_list('joe@example.org, fred@example.com')
    '<a href="mailto:joe@example.org">joe@example.org</a>, <a href="mailto:fred@example.com">fred@example.com</a>'

    Parsing a non-string should return the input value, rather than fail:
    
    >>> parse_email_list(['joe@example.org', 'fred@example.com'])
    ['joe@example.org', 'fred@example.com']
    
    Null input values should pass through silently:
    
    >>> parse_email_list('')
    ''

    >>> parse_email_list(None)


    """
    if value and type(value) == type(""): # testing for 'value' being true isn't necessary; it's a fast-out route
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
    if value and type(value) == type(""):
        return re.sub(", ?", "\n", value)
    else:
        return value
        
@register.filter(name='link_if_url')
def link_if_url(value):
    """
    If the argument looks like a url, return a link; otherwise, just
    return the argument."""
    if (re.match('(https?|mailto):', value)):
	return "<a href=\"%s\">%s</a>" % ( fix_ampersands(value), escape(value) )
    else:
	return escape(value)

# This replicates the nwg_list.cgi method.
# It'd probably be better to check for the presence of
# a scheme with a better RE.
@register.filter(name='add_scheme')
def add_scheme(value):
    if (re.match('www', value)):
	return "http://" + value
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

@register.filter(name='text_to_html')
def text_to_html(value):
    return keep_spacing(linebreaks(escape(value)))

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

# For use with ballot view
@register.filter(name='bracket')
def square_brackets(value):
    """Adds square brackets around text."""
    if   type(value) == type(""):
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

@register.filter(name='allononeline')
def allononeline(text):
    """Simply removes CRs, LFs, leading and trailing whitespace from the given string."""
    return text.replace("\r", "").replace("\n", "").strip()

@register.filter(name='allononelinew')
def allononelinew(text):
    """Map runs of whitespace to a single space and strip leading and trailing whitespace from the given string."""
    return re.sub("[\r\n\t ]+", " ", text).strip()

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

@register.filter(name='thisyear')
def thisyear(date):
    """Returns a boolean of whether or not the argument is this year."""
    if date:
	return date.year == datetime.date.today().year
    return True

@register.filter(name='inpast')
def inpast(date):
    """Returns a boolean of whether or not the argument is in the past."""
    if date:
	return date < datetime.datetime.now()
    return True

@register.filter(name='timesince_days')
def timesince_days(date):
    """Returns the number of days since 'date' (relative to now)"""
    if date.__class__ is not datetime.datetime:
        date = datetime.datetime(date.year, date.month, date.day)
    delta = datetime.datetime.now() - date
    return delta.days

@register.filter(name='truncatemore')
def truncatemore(text, arg):
    """Truncate the text if longer than 'words', and if truncated,
    add a link to the full text (given in 'link').
    """
    from django.utils.text import truncate_words
    args = arg.split(",")
    if len(args) == 3:
        count, link, format = args
    elif len(args) == 2:
        format = "[<a href='%s'>more</a>]"
        count, link = args
    else:
        return text
    try:
        length = int(count)
    except ValueError: # invalid literal for int()
        return text # Fail silently.
    if not isinstance(text, basestring):
        text = str(text)
    words = text.split()
    if len(words) > length:
        words = words[:length]
        words.append(format % link)
    return ' '.join(words)

@register.filter(name="wrap_long_lines")
def wrap_long_lines(text):
    """Wraps long lines without loosing the formatting and indentation
       of short lines"""
    if type(text) != type(""):
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

@register.filter(name='greater_than')
def greater_than(x, y):
    return x > int(y)

@register.filter(name='less_than')
def less_than(x, y):
    return x < int(y)

@register.filter(name='equal')
def equal(x, y):
    return str(x)==str(y)

# based on http://www.djangosnippets.org/snippets/847/ by 'whiteinge'
@register.filter
def in_group(user, groups):
    return user and user.is_authenticated() and bool(user.groups.filter(name__in=groups.split(',')).values('name'))

def _test():
    import doctest
    doctest.testmod()

if __name__ == "__main__":
    _test()

    
