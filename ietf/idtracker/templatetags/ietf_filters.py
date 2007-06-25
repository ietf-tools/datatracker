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
    a list of mailto: links."""
    addrs = re.split(", ?", value)
    ret = []
    for addr in addrs:
	(name, email) = emailutils.parseaddr(addr)
	if not(name):
	    name = email
	ret.append('<a href="mailto:%s">%s</a>' % ( fix_ampersands(email), escape(name) ))
    return ", ".join(ret)

# there's an "ahref -> a href" in GEN_UTIL
# but let's wait until we understand what that's for.
@register.filter(name='make_one_per_line')
def make_one_per_line(value):
    """
    Turn a comma-separated list into a carraige-return-seperated list."""
    return re.sub(", ?", "\n", value)

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
