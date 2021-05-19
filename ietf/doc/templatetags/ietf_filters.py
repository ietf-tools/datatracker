# Copyright The IETF Trust 2007-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import bleach
import datetime
import re

from email.utils import parseaddr

from django import template
from django.conf import settings
from django.utils.html import escape
from django.template.defaultfilters import truncatewords_html, linebreaksbr, stringfilter, striptags
from django.utils.safestring import mark_safe, SafeData
from django.utils.html import strip_tags
from django.utils.encoding import force_text
from django.utils.encoding import force_str # pyflakes:ignore force_str is used in the doctests
from django.urls import reverse as urlreverse

import debug                            # pyflakes:ignore

from ietf.doc.models import BallotDocEvent
from ietf.doc.models import ConsensusDocEvent
from ietf.utils.html import sanitize_fragment
from ietf.utils import log
from ietf.doc.utils import prettify_std_name
from ietf.utils.text import wordwrap, fill, wrap_text_if_unwrapped

register = template.Library()

def collapsebr(html):
    return re.sub('(<(br ?/|/p)>[ \n]*)(<(br) ?/?>[ \n]*)*(<(br|p) ?/?>[ \n]*)', '\\1\\5', html)

@register.filter
def indent(value, numspaces=2):
    replacement = "\n" + " " * int(numspaces)
    res = value.replace("\n", replacement)
    if res.endswith(replacement):
        res = res[:-int(numspaces)] # fix up superfluous spaces
    return res

@register.filter
def unindent(value):
    """Remove indentation from string."""
    return re.sub("\n +", "\n", value)

@register.filter(name='parse_email_list')
def parse_email_list(value):
    """
    Parse a list of comma-seperated email addresses into
    a list of mailto: links.

    Splitting a string of email addresses should return a list:

    >>> force_str(parse_email_list('joe@example.org, fred@example.com'))
    '<a href="mailto:joe@example.org">joe@example.org</a>, <a href="mailto:fred@example.com">fred@example.com</a>'

    Parsing a non-string should return the input value, rather than fail:

    >>> [ force_str(e) for e in parse_email_list(['joe@example.org', 'fred@example.com']) ]
    ['joe@example.org', 'fred@example.com']

    Null input values should pass through silently:

    >>> force_str(parse_email_list(''))
    ''

    >>> parse_email_list(None)


    """
    if value and isinstance(value, str): # testing for 'value' being true isn't necessary; it's a fast-out route
        addrs = re.split(", ?", value)
        ret = []
        for addr in addrs:
            (name, email) = parseaddr(addr)
            if not(name):
                name = email
            ret.append('<a href="mailto:%s">%s</a>' % ( email.replace('&', '&amp;'), escape(name) ))
        return mark_safe(", ".join(ret))
    elif value and isinstance(value, bytes):
        log.assertion('isinstance(value, str)')        
    else:
        return value

@register.filter
def strip_email(value):
    """Get rid of email part of name/email string like 'Some Name <email@example.com>'."""
    if not value:
        return ""
    if "@" not in value:
        return value
    return parseaddr(value)[0]

@register.filter(name='fix_angle_quotes')
def fix_angle_quotes(value):
    if "<" in value:
        value = re.sub(r"<([\w\-\.]+@[\w\-\.]+)>", "&lt;\1&gt;", value)
    return value

# there's an "ahref -> a href" in GEN_UTIL
# but let's wait until we understand what that's for.
@register.filter(name='make_one_per_line')
def make_one_per_line(value):
    """
    Turn a comma-separated list into a carriage-return-seperated list.

    >>> force_str(make_one_per_line("a, b, c"))
    'a\\nb\\nc'

    Pass through non-strings:

    >>> make_one_per_line([1, 2])
    [1, 2]

    >>> make_one_per_line(None)

    """
    if value and isinstance(value, str):
        return re.sub(", ?", "\n", value)
    elif value and isinstance(value, bytes):
        log.assertion('isinstance(value, str)')
    else:
        return value

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

@register.filter(name='sanitize')
def sanitize(value):
    """Sanitizes an HTML fragment.
    This means both fixing broken html and restricting elements and
    attributes to those deemed acceptable.  See ietf/utils/html.py
    for the details.
    """
    return mark_safe(sanitize_fragment(value))


# For use with ballot view
@register.filter(name='bracket')
def square_brackets(value):
    """Adds square brackets around text."""
    if isinstance(value, str):
        if value == "":
             value = " "
        return "[ %s ]" % value
    elif isinstance(value, bytes):
        log.assertion('isinstance(value, str)')
    elif value > 0:
        return "[ X ]"
    elif value < 0:
        return "[ . ]"
    else:
        return "[   ]"

@register.filter(name='bracketpos')
def bracketpos(pos,posslug):
    if pos.pos.slug==posslug:
        return "[ X ]"
    elif posslug in [x.slug for x in pos.old_positions]:
        return "[ . ]"
    else:
        return "[   ]"

register.filter('fill', fill)

@register.filter(name='rfcspace')
def rfcspace(string):
    """
    If the string is an RFC designation, and doesn't have
    a space between 'RFC' and the rfc-number, a space is
    added
    """
    string = str(string)
    if string[:3].lower() == "rfc" and string[3] != " ":
        return string[:3].upper() + " " + string[3:]
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

@register.filter
def prettystdname(string):
    from ietf.doc.utils import prettify_std_name
    return prettify_std_name(force_text(string or ""))

@register.filter(name='rfcurl')
def rfclink(string):
    """
    This takes just the RFC number, and turns it into the
    URL for that RFC.
    """
    string = str(string);
    return "https://datatracker.ietf.org/doc/html/rfc" + string;

@register.filter(name='urlize_ietf_docs', is_safe=True, needs_autoescape=True)
def urlize_ietf_docs(string, autoescape=None):
    """
    Make occurrences of RFC NNNN and draft-foo-bar links to /doc/.
    """
    if autoescape and not isinstance(string, SafeData):
        string = escape(string)
    string = re.sub(r"(?<!>)(RFC ?)0{0,3}(\d+)", "<a href=\"/doc/rfc\\2/\">\\1\\2</a>", string)
    string = re.sub(r"(?<!>)(BCP ?)0{0,3}(\d+)", "<a href=\"/doc/bcp\\2/\">\\1\\2</a>", string)
    string = re.sub(r"(?<!>)(STD ?)0{0,3}(\d+)", "<a href=\"/doc/std\\2/\">\\1\\2</a>", string)
    string = re.sub(r"(?<!>)(FYI ?)0{0,3}(\d+)", "<a href=\"/doc/fyi\\2/\">\\1\\2</a>", string)
    string = re.sub(r"(?<!>)(draft-[-0-9a-zA-Z._+]+)", "<a href=\"/doc/\\1/\">\\1</a>", string)
    string = re.sub(r"(?<!>)(conflict-review-[-0-9a-zA-Z._+]+)", "<a href=\"/doc/\\1/\">\\1</a>", string)
    string = re.sub(r"(?<!>)(status-change-[-0-9a-zA-Z._+]+)", "<a href=\"/doc/\\1/\">\\1</a>", string)
    return mark_safe(string)
urlize_ietf_docs = stringfilter(urlize_ietf_docs)

@register.filter(name='urlize_doc_list', is_safe=True, needs_autoescape=True)
def urlize_doc_list(docs, autoescape=None):
    """Convert a list of DocAliases into list of links using canonical name"""
    links = []
    for doc in docs:
        name=doc.document.canonical_name()
        title = doc.document.title
        url = urlreverse('ietf.doc.views_doc.document_main', kwargs=dict(name=name))
        if autoescape:
            name = escape(name)
            title = escape(title)
        links.append(mark_safe(
            '<a href="%(url)s" title="%(title)s">%(name)s</a>' % dict(name=prettify_std_name(name),
                                                                      title=title,
                                                                      url=url)
        ))
    return links
        
@register.filter(name='dashify')
def dashify(string):
    """
    Replace each character in string with '-', to produce
    an underline effect for plain text files.
    """
    return re.sub('.', '-', string)

@register.filter
def underline(string):
    """Return string with an extra line underneath of dashes, for plain text underlining."""
    return string + "\n" + ("-" * len(string))

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

@register.filter
def split(text, splitter=None):
    return text.split(splitter)

register.filter("maybewordwrap", stringfilter(wrap_text_if_unwrapped))

register.filter("wordwrap", stringfilter(wordwrap))

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
    days = int(settings.USER_PREFERENCE_DEFAULTS["new_enough"])
    value = request.COOKIES.get("new_enough", None)
    if value and value.isdigit():
        days = int(value)
    return x < days

@register.filter(name='expires_soon')
def expires_soon(x,request):
    days = int(settings.USER_PREFERENCE_DEFAULTS["expires_soon"])
    value = request.COOKIES.get("expires_soon", None)
    if value and value.isdigit():
        days = int(value)
    return x > -days

@register.filter(name='startswith')
def startswith(x, y):
    return str(x).startswith(y)

@register.filter
def has_role(user, role_names):
    from ietf.ietfauth.utils import has_role
    if not user:
        return False
    return has_role(user, role_names.split(','))

@register.filter
def ad_area(user):
    if user and user.is_authenticated:
        from ietf.group.models import Group
        g = Group.objects.filter(role__name__in=("pre-ad", "ad"), role__person__user=user)
        if g:
            return g[0].acronym
    return None

@register.filter
def format_history_text(text, trunc_words=25):
    """Run history text through some cleaning and add ellipsis if it's too long."""
    full = mark_safe(text)

    if text.startswith("This was part of a ballot set with:"):
        full = urlize_ietf_docs(full)

    return format_snippet(full, trunc_words)

@register.filter
def format_snippet(text, trunc_words=25): 
    # urlize if there aren't already links present
    if not 'href=' in text:
        # django's urlize() cannot handle adjacent parentheszised
        # expressions, for instance [REF](http://example.com/foo)
        # Use bleach.linkify instead
        text = bleach.linkify(text)
    full = keep_spacing(collapsebr(linebreaksbr(mark_safe(sanitize_fragment(text)))))
    snippet = truncatewords_html(full, trunc_words)
    if snippet != full:
        return mark_safe('<div class="snippet">%s<button class="btn btn-xs btn-default show-all"><span class="fa fa-caret-down"></span></button></div><div class="hidden full">%s</div>' % (snippet, full))
    return full

@register.simple_tag
def doc_edit_button(url_name, *args, **kwargs):
    """Given URL name/args/kwargs, looks up the URL just like "url" tag and returns a properly formatted button for the document material tables."""
    from django.urls import reverse as urlreverse
    return mark_safe('<a class="btn btn-default btn-xs" href="%s">Edit</a>' % (urlreverse(url_name, args=args, kwargs=kwargs)))

@register.filter
def textify(text):
    text = re.sub("</?b>", "*", text)
    text = re.sub("</?i>", "/", text)
    # There are probably additional conversions we should apply here
    return text

@register.filter
def state(doc, slug):
    if slug == "stream": # convenient shorthand
        slug = "%s-stream-%s" % (doc.type_id, doc.stream_id)
    return doc.get_state(slug)

@register.filter
def statehelp(state):
    "Output help icon with tooltip for state."
    from django.urls import reverse as urlreverse
    tooltip = escape(strip_tags(state.desc))
    url = urlreverse('ietf.doc.views_help.state_help', kwargs=dict(type=state.type_id)) + "#" + state.slug
    return mark_safe('<a class="state-help-icon" href="%s" title="%s">?</a>' % (url, tooltip))

@register.filter
def sectionlevel(section_number):
    return section_number.count(".") + 1

def _test():
    import doctest
    doctest.testmod()

if __name__ == "__main__":
    _test()

@register.filter
def plural(text, seq, arg='s'):
    "Similar to pluralize, but looks at the text, too"
    from django.template.defaultfilters import pluralize
    if text.endswith('s'):
        return text
    else:
        return text + pluralize(len(seq), arg)

@register.filter
def ics_esc(text):
    text = re.sub(r"([\n,;\\])", r"\\\1", text)
    return text

@register.filter
def consensus(doc):
    """Returns document consensus Yes/No/Unknown."""
    event = doc.latest_event(ConsensusDocEvent,type="changed_consensus")
    if event:
        if event.consensus:
            return "Yes"
        else:
            return "No"
    else:
        return "Unknown"

@register.filter
def pos_to_label(text):
    """Return a valid Bootstrap3 label type for a ballot position."""
    return {
        'Yes':          'success',
        'No Objection': 'pass',
        'Abstain':      'warning',
        'Discuss':      'danger',
        'Block':        'danger',
        'Recuse':       'primary',
        'Not Ready':    'danger',
        'Need More Time': 'danger',
    }.get(str(text), 'blank')

@register.filter
def capfirst_allcaps(text):
    """Like capfirst, except it doesn't lowercase words in ALL CAPS."""
    result = text
    i = False
    for token in re.split(r"(\W+)", striptags(text)):
        if not re.match(r"^[A-Z]+$", token):
            if not i:
                result = result.replace(token, token.capitalize())
                i = True
            else:
                result = result.replace(token, token.lower())
    return result

@register.filter
def lower_allcaps(text):
    """Like lower, except it doesn't lowercase words in ALL CAPS."""
    result = text
    for token in re.split(r"(\W+)", striptags(text)):
        if not re.match(r"^[A-Z]+$", token):
            result = result.replace(token, token.lower())
    return result

@register.filter
def emailwrap(email):
    email = str(email)
    return mark_safe(email.replace('@', '<wbr>@'))

@register.filter
def document_content(doc):
    if doc is None:
        return None
    content = doc.text_or_error()         # pyflakes:ignore
    return content

@register.filter
def format_timedelta(timedelta):
    s = timedelta.seconds
    hours, remainder = divmod(s, 3600)
    minutes, seconds = divmod(remainder, 60)
    return '{hours:02d}:{minutes:02d}'.format(hours=hours,minutes=minutes)

@register.filter()
def nbsp(value):
    return mark_safe("&nbsp;".join(value.split(' ')))

@register.filter()
def comma_separated_list(seq, end_word="and"):
    if len(seq) < 2:
        return "".join(seq)
    else:
        return ", ".join(seq[:-1]) + " %s %s"%(end_word, seq[-1])

@register.filter()
def zaptmp(s):
    return re.sub(r'/tmp/tmp[^/]+/', '', s)

@register.filter()
def rfcbis(s):
    m = re.search(r'^.*-rfc(\d+)-?bis(-.*)?$', s)
    return None if m is None else 'rfc' + m.group(1) 

@register.filter
@stringfilter
def urlize(value):
    raise RuntimeError("Use linkify from textfilters instead of urlize")
    
@register.filter
@stringfilter
def charter_major_rev(rev):
    return rev[:2]

@register.filter
@stringfilter
def charter_minor_rev(rev):
    return rev[3:5]

@register.filter()
def can_defer(user,doc):
    ballot = doc.latest_event(BallotDocEvent, type="created_ballot")
    if ballot and (doc.type_id == "draft" or doc.type_id == "conflrev") and doc.stream_id == 'ietf' and has_role(user, 'Area Director,Secretariat'):
        return True
    else:
        return False

@register.filter()
def can_ballot(user,doc):
    # Only IRSG memebers (and the secretariat, handled by code separately) can take positions on IRTF documents
    # Otherwise, an AD can take a position on anything that has a ballot open
    if doc.type_id == 'draft' and doc.stream_id == 'irtf':
        return has_role(user,'IRSG Member')
    else:
        return user.person.role_set.filter(name="ad", group__type="area", group__state="active")

@register.filter
def action_holder_badge(action_holder):
    """Add a warning tag if action holder age exceeds limit
    
    >>> from ietf.doc.factories import DocumentActionHolderFactory
    >>> old_limit = settings.DOC_ACTION_HOLDER_AGE_LIMIT_DAYS
    >>> settings.DOC_ACTION_HOLDER_AGE_LIMIT_DAYS = 15
    >>> action_holder_badge(DocumentActionHolderFactory())
    ''
    
    >>> action_holder_badge(DocumentActionHolderFactory(time_added=datetime.datetime.now() - datetime.timedelta(days=15)))
    ''

    >>> action_holder_badge(DocumentActionHolderFactory(time_added=datetime.datetime.now() - datetime.timedelta(days=16)))
    '<span class="label label-danger" title="Goal is &lt;15 days">for 16 days</span>'

    >>> action_holder_badge(DocumentActionHolderFactory(time_added=datetime.datetime.now() - datetime.timedelta(days=30)))
    '<span class="label label-danger" title="Goal is &lt;15 days">for 30 days</span>'

    >>> settings.DOC_ACTION_HOLDER_AGE_LIMIT_DAYS = old_limit
    """
    age_limit = settings.DOC_ACTION_HOLDER_AGE_LIMIT_DAYS
    age = (datetime.datetime.now() - action_holder.time_added).days
    if age > age_limit:
        return mark_safe('<span class="label label-danger" title="Goal is &lt;%d days">for %d day%s</span>' % (
            age_limit,
            age,
            's' if age != 1 else ''))
    else:
        return ''  # no alert needed

