from django import template
from django.utils.html import escape, fix_ampersands, linebreaks
from django.template.defaultfilters import linebreaksbr
try:
    from email import utils as emailutils
except ImportError:
    from email import Utils as emailutils
import re

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
