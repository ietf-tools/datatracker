# Copyright The IETF Trust 2007-2023, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import re
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from django import template
from django.conf import settings
from django.utils.html import escape
from django.template.defaultfilters import truncatewords_html, linebreaksbr, stringfilter, striptags
from django.utils.safestring import mark_safe, SafeData
from django.utils.html import strip_tags
from django.utils.encoding import force_str
from django.urls import reverse as urlreverse
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.urls import NoReverseMatch
from django.utils import timezone

import debug                            # pyflakes:ignore

from ietf.doc.models import BallotDocEvent, Document
from ietf.doc.models import ConsensusDocEvent
from ietf.ietfauth.utils import can_request_rfc_publication as utils_can_request_rfc_publication
from ietf.utils.html import sanitize_fragment
from ietf.utils import log
from ietf.doc.utils import prettify_std_name
from ietf.utils.text import wordwrap, fill, wrap_text_if_unwrapped, bleach_linker, bleach_cleaner, validate_url

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

@register.filter
def prettystdname(string, space=" "):
    from ietf.doc.utils import prettify_std_name
    return prettify_std_name(force_str(string or ""), space)

@register.filter
def rfceditor_info_url(rfcnum : str):
    """Link to the RFC editor info page for an RFC"""
    return urljoin(settings.RFC_EDITOR_INFO_BASE_URL, f'rfc{rfcnum}')


def doc_name(name):
    """Check whether a given document exists, and return its canonical name"""

    def find_unique(n):
        key = hash(n)
        found = cache.get(key)
        if not found:
            exact = Document.objects.filter(name=n).first()
            found = exact.name if exact else "_"
            # TODO review this cache policy (and the need for these entire function)
            cache.set(key, found, timeout=60*60*24)  # cache for one day
        return None if found == "_" else found

    # chop away extension
    extension_split = re.search(r"^(.+)\.(txt|ps|pdf|html)$", name)
    if extension_split:
        name = extension_split.group(1)

    if find_unique(name):
        return name

    # check for embedded rev - this may be ambiguous, so don't
    # chop it off if we don't find a match
    rev_split = re.search(r"^(charter-.+)-(\d{2}-\d{2})$", name) or re.search(
        r"^(.+)-(\d{2}|[1-9]\d{2,})$", name
    )
    if rev_split:
        name = rev_split.group(1)
        if find_unique(name):
            return name

    return ""


def link_charter_doc_match(match):
    if not doc_name(match[0]):
        return match[0]
    url = urlreverse(
        "ietf.doc.views_doc.document_main",
        kwargs=dict(name=match[1][:-1], rev=match[2]),
    )
    return f'<a href="{url}">{match[0]}</a>'


def link_non_charter_doc_match(match):
    name = match[0]
    # handle "I-D.*"" reference-style matches
    name = re.sub(r"^i-d\.(.*)", r"draft-\1", name, flags=re.IGNORECASE)
    cname = doc_name(name)
    if not cname:
        return match[0]
    if name == cname:
        url = urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=cname))
        return f'<a href="{url}">{match[0]}</a>'

    # if we get here, the name probably has a version number and/or extension at the end
    rev_split = re.search(r"^(" + re.escape(cname) + r")-(\d{2,})", name)
    if rev_split:
        name = rev_split.group(1)
    else:
        url = urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=cname))
        return f'<a href="{url}">{match[0]}</a>'

    cname = doc_name(name)
    if not cname:
        return match[0]
    if name == cname:
        try:
            url = urlreverse(
                "ietf.doc.views_doc.document_main",
                kwargs=dict(name=cname, rev=rev_split.group(2)),
            )
        except NoReverseMatch:
            return match[0]
        return f'<a href="{url}">{match[0]}</a>'

    # if we get here, we can't linkify
    return match[0]


def link_other_doc_match(match):
    doc = match[2].strip().lower()
    rev = match[3]
    if not doc_name(doc + rev):
        return match[0]
    url = urlreverse("ietf.doc.views_doc.document_main", kwargs=dict(name=doc + rev))
    return f'<a href="{url}">{match[1]}</a>'

@register.filter(name="urlize_ietf_docs", is_safe=True, needs_autoescape=True)
def urlize_ietf_docs(string, autoescape=None):
    """
    Make occurrences of RFC NNNN and draft-foo-bar links to the doc pages.
    """
    if autoescape and not isinstance(string, SafeData):
        if "<" in string:
            string = escape(string)
        else:
            string = mark_safe(string)
    string = re.sub(
        r"\b(?<![/\-:=#\"\'])(charter-(?:[\d\w\.+]+-)*)(\d{2}(?:-\d{2}))(\.(?:txt|ps|pdf|html))?\b",
        link_charter_doc_match,
        string,
        flags=re.IGNORECASE | re.ASCII,
    )
    string = re.sub(
        r"\b(?<![/\-:=#\"\'])((?:draft-|i-d\.|bofreq-|conflict-review-|status-change-)[\d\w\.+-]+(?![-@]))",
        link_non_charter_doc_match,
        string,
        flags=re.IGNORECASE | re.ASCII,
    )
    string = re.sub(
        r"\b(?<![/\-:=#\"\'])((RFC|BCP|STD|FYI) *\n? *0*(\d+))\b",
        link_other_doc_match,
        string,
        flags=re.IGNORECASE | re.ASCII,
    )

    return mark_safe(string)


urlize_ietf_docs = stringfilter(urlize_ietf_docs)

@register.filter(name='urlize_related_source_list', is_safe=True, document_html=False)
def urlize_related_source_list(related, document_html=False):
    """Convert a list of RelatedDocuments into list of links using the source document's canonical name"""
    links = []
    names = set()
    titles = set()
    for rel in related:
        name=rel.source.name
        title = rel.source.title
        if name in names and title in titles:
            continue
        names.add(name)
        titles.add(title)
        url = urlreverse('ietf.doc.views_doc.document_main' if document_html is False else 'ietf.doc.views_doc.document_html', kwargs=dict(name=name))
        name = escape(name)
        title = escape(title)
        links.append(mark_safe(
            '<a href="%(url)s" title="%(title)s">%(name)s</a>' % dict(name=prettify_std_name(name),
                                                                      title=title,
                                                                      url=url)
        ))
    return links
        
@register.filter(name='urlize_related_target_list', is_safe=True, document_html=False)
def urlize_related_target_list(related, document_html=False):
    """Convert a list of RelatedDocuments into list of links using the target document's canonical name"""
    links = []
    for rel in related:
        name=rel.target.name
        title = rel.target.title
        url = urlreverse('ietf.doc.views_doc.document_main' if document_html is False else 'ietf.doc.views_doc.document_html', kwargs=dict(name=name))
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

@register.filter(name='timesince_days')
def timesince_days(date):
    """Returns the number of days since 'date' (relative to now)

    >>> timesince_days(timezone.now() - datetime.timedelta(days=2))
    2

    >>> tz = ZoneInfo(settings.TIME_ZONE)
    >>> timesince_days(timezone.now().astimezone(tz).date() - datetime.timedelta(days=2))
    2

    """
    if date.__class__ is not datetime.datetime:
        date = datetime.datetime(date.year, date.month, date.day, tzinfo=ZoneInfo(settings.TIME_ZONE))
    delta = timezone.now() - date
    return delta.days

@register.filter
def split(text, splitter=None):
    return text.split(splitter)

register.filter("maybewordwrap", stringfilter(wrap_text_if_unwrapped))

register.filter("wordwrap", stringfilter(wordwrap))

@register.filter(name="compress_empty_lines")
def compress_empty_lines(text):
    text = re.sub("( *\n){3,}", "\n\n", text)
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


@register.filter(name='removeprefix', is_safe=False)
def removeprefix(value, prefix):
    """Remove an exact-match prefix
    
    The is_safe flag is False because indiscriminate use of this could result in non-safe output.
    See https://docs.djangoproject.com/en/2.2/howto/custom-template-tags/#filters-and-auto-escaping
    which describes the possibility that removing characters from an escaped string may introduce
    HTML-unsafe output.
    """
    base = str(value)
    if base.startswith(prefix):
        return base[len(prefix):]
    else:
        return base


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
    full = mark_safe(bleach_cleaner.clean(text))
    full = bleach_linker.linkify(urlize_ietf_docs(full))

    return format_snippet(full, trunc_words)

@register.filter
def format_snippet(text, trunc_words=25): 
    # urlize if there aren't already links present
    text = bleach_linker.linkify(text)
    full = keep_spacing(collapsebr(linebreaksbr(mark_safe(sanitize_fragment(text)))))
    snippet = truncatewords_html(full, trunc_words)
    if snippet != full:
        return mark_safe('<div class="snippet">%s<button type="button" aria-label="Expand" class="btn btn-sm btn-primary show-all"><i class="bi bi-caret-down"></i></button></div><div class="d-none full">%s</div>' % (snippet, full))
    return mark_safe(full)

@register.simple_tag
def doc_edit_button(url_name, *args, **kwargs):
    """Given URL name/args/kwargs, looks up the URL just like "url" tag and returns a properly formatted button for the document material tables."""
    return mark_safe('<a class="btn btn-primary btn-sm" href="%s">Edit</a>' % (urlreverse(url_name, args=args, kwargs=kwargs)))

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


@register.simple_tag
def ics_date_time(dt, tzname):
    """Render a datetime as an iCalendar date-time

    dt a datetime, localized to the timezone to be displayed
    tzname is the name for this timezone

    Caller must arrange for a VTIMEZONE for the tzname to be included in the iCalendar file.
    Output includes a ':'. Use like:
      DTSTART{% ics_date_time timestamp 'America/Los_Angeles' %}
    to get
      DTSTART;TZID=America/Los_Angeles:20221021T111200

    >>> ics_date_time(datetime.datetime(2022,1,2,3,4,5), 'utc')
    ':20220102T030405Z'

    >>> ics_date_time(datetime.datetime(2022,1,2,3,4,5), 'UTC')
    ':20220102T030405Z'

    >>> ics_date_time(datetime.datetime(2022,1,2,3,4,5), 'America/Los_Angeles')
    ';TZID=America/Los_Angeles:20220102T030405'
    """
    timestamp = dt.strftime('%Y%m%dT%H%M%S')
    if tzname.lower() == 'utc':
        return f':{timestamp}Z'
    else:
        return f';TZID={ics_esc(tzname)}:{timestamp}'
    
@register.filter
def next_day(value):
    return value + datetime.timedelta(days=1)


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
def std_level_to_label_format(doc):
    """Returns valid Bootstrap classes to label a status level badge."""
    if doc.type_id == "rfc":
        if doc.related_that("obs"):
            return "obs"
        else:
            return doc.std_level_id
    else:
        return "draft"


@register.filter
def pos_to_label_format(text):
    """Returns valid Bootstrap classes to label a ballot position."""
    return {
        'Yes':          'bg-yes text-light',
        'No Objection': 'bg-noobj text-dark',
        'Abstain':      'bg-abstain text-light',
        'Discuss':      'bg-discuss text-light',
        'Block':        'bg-discuss text-light',
        'Recuse':       'bg-recuse text-light',
        'Not Ready':    'bg-discuss text-light',
        'Need More Time': 'bg-discuss text-light',
        'Concern': 'bg-discuss text-light',

    }.get(str(text), 'bg-norecord text-dark')

@register.filter
def pos_to_border_format(text):
    """Returns valid Bootstrap classes to label a ballot position border."""
    return {
        'Yes':          'border-yes',
        'No Objection': 'border-noobj',
        'Abstain':      'border-abstain',
        'Discuss':      'border-discuss',
        'Block':        'border-discuss',
        'Recuse':       'border-recuse',
        'Not Ready':    'border-discuss',
        'Need More Time': 'border-discuss',
        'Concern': 'border-discuss',
    }.get(str(text), 'border-norecord')

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
    if ballot and (doc.type_id == "draft" or doc.type_id == "conflrev" or doc.type_id=="statchg") and doc.stream_id == 'ietf' and has_role(user, 'Area Director,Secretariat'):
        return True
    else:
        return False

@register.filter()
def can_clear_ballot(user, doc):
    return can_defer(user, doc)

@register.filter()
def can_request_rfc_publication(user, doc):
    return utils_can_request_rfc_publication(user, doc)

@register.filter()
def can_ballot(user,doc):
    if doc.stream_id == "irtf" and doc.type_id == "draft":
        return has_role(user,"IRSG Member")
    elif doc.stream_id == "editorial" and doc.type_id == "draft":
        return has_role(user,"RSAB Member")
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

    >>> action_holder_badge(DocumentActionHolderFactory(time_added=timezone.now() - datetime.timedelta(days=15)))
    ''

    >>> action_holder_badge(DocumentActionHolderFactory(time_added=timezone.now() - datetime.timedelta(days=16)))
    '<span class="badge rounded-pill text-bg-danger" title="In state for 16 days; goal is &lt;15 days."><i class="bi bi-clock-fill"></i> 16</span>'

    >>> action_holder_badge(DocumentActionHolderFactory(time_added=timezone.now() - datetime.timedelta(days=30)))
    '<span class="badge rounded-pill text-bg-danger" title="In state for 30 days; goal is &lt;15 days."><i class="bi bi-clock-fill"></i> 30</span>'

    >>> settings.DOC_ACTION_HOLDER_AGE_LIMIT_DAYS = old_limit
    """
    age_limit = settings.DOC_ACTION_HOLDER_AGE_LIMIT_DAYS
    age = (timezone.now() - action_holder.time_added).days
    if age > age_limit:
        return mark_safe(
            '<span class="badge rounded-pill text-bg-danger" title="In state for %d day%s; goal is &lt;%d days."><i class="bi bi-clock-fill"></i> %d</span>'
            % (age, "s" if age != 1 else "", age_limit, age)
        )
    else:
        return ""  # no alert needed


@register.filter
def is_regular_agenda_item(assignment):
    """Is this agenda item a regular session item?

    A regular item appears as a sub-entry in a timeslot within the agenda

    >>> from collections import namedtuple  # use to build mock objects
    >>> mock_timeslot = namedtuple('t2', ['slug'])
    >>> mock_assignment = namedtuple('t1', ['slot_type'])  # slot_type must be a callable
    >>> factory = lambda t: mock_assignment(slot_type=lambda: mock_timeslot(slug=t))
    >>> is_regular_agenda_item(factory('regular'))
    True

    >>> any(is_regular_agenda_item(factory(t)) for t in ['plenary', 'break', 'reg', 'other', 'officehours'])
    False

    >>> is_regular_agenda_item(None)
    False
    """
    return assignment is not None and assignment.slot_type().slug == 'regular'

@register.filter
def is_plenary_agenda_item(assignment):
    """Is this agenda item a regular session item?

    A regular item appears as a sub-entry in a timeslot within the agenda

    >>> from collections import namedtuple  # use to build mock objects
    >>> mock_timeslot = namedtuple('t2', ['slug'])
    >>> mock_assignment = namedtuple('t1', ['slot_type'])  # slot_type must be a callable
    >>> factory = lambda t: mock_assignment(slot_type=lambda: mock_timeslot(slug=t))
    >>> is_plenary_agenda_item(factory('plenary'))
    True

    >>> any(is_plenary_agenda_item(factory(t)) for t in ['regular', 'break', 'reg', 'other', 'officehours'])
    False

    >>> is_plenary_agenda_item(None)
    False
    """
    return assignment is not None and assignment.slot_type().slug == 'plenary'

@register.filter
def is_special_agenda_item(assignment):
    """Is this agenda item a special item?

    Special items appear as top-level agenda entries with their own timeslot information.

    >>> from collections import namedtuple  # use to build mock objects
    >>> mock_timeslot = namedtuple('t2', ['slug'])
    >>> mock_assignment = namedtuple('t1', ['slot_type'])  # slot_type must be a callable
    >>> factory = lambda t: mock_assignment(slot_type=lambda: mock_timeslot(slug=t))
    >>> all(is_special_agenda_item(factory(t)) for t in ['break', 'reg', 'other', 'officehours'])
    True

    >>> any(is_special_agenda_item(factory(t)) for t in ['regular', 'plenary'])
    False

    >>> is_special_agenda_item(None)
    False
    """
    return assignment is not None and assignment.slot_type().slug in [
        'break',
        'reg',
        'other',
        'officehours',
    ]

@register.filter
def should_show_agenda_session_buttons(assignment):
    """Should this agenda item show the session buttons (chat link, etc)?

    In IETF-112 and earlier, office hours sessions were designated by a name ending
    with ' office hours' and belonged to the IESG or some other group. This led to
    incorrect session buttons being displayed. Suppress session buttons for
    when name ends with 'office hours' in the pre-112 meetings.
    >>> from collections import namedtuple  # use to build mock objects
    >>> mock_meeting = namedtuple('t3', ['number'])
    >>> mock_session = namedtuple('t2', ['name'])
    >>> mock_assignment = namedtuple('t1', ['meeting', 'session'])  # meeting must be a callable
    >>> factory = lambda num, name: mock_assignment(session=mock_session(name), meeting=lambda: mock_meeting(num))
    >>> test_cases = [('105', 'acme office hours'), ('112', 'acme office hours')]
    >>> any(should_show_agenda_session_buttons(factory(*tc)) for tc in test_cases)
    False
    >>> test_cases = [('interim-2020-acme-113', 'acme'), ('113', 'acme'), ('150', 'acme'), ('105', 'acme'),]
    >>> test_cases.extend([('112', 'acme'), ('interim-2020-acme-113', 'acme office hours')])
    >>> test_cases.extend([('113', 'acme office hours'), ('150', 'acme office hours')])
    >>> all(should_show_agenda_session_buttons(factory(*tc)) for tc in test_cases)
    True
    >>> should_show_agenda_session_buttons(None)
    False
    """
    if assignment is None:
        return False
    num = assignment.meeting().number
    if num.isdigit() and int(num) <= settings.MEETING_LEGACY_OFFICE_HOURS_END:
        return not assignment.session.name.lower().endswith(' office hours')
    else:
        return True


@register.simple_tag
def absurl(viewname, **kwargs):
    """Get the absolute URL for a view by name

    Uses settings.IDTRACKER_BASE_URL as the base.
    """
    return urljoin(settings.IDTRACKER_BASE_URL, urlreverse(viewname, kwargs=kwargs))


@register.filter
def is_valid_url(url):
    """
    Check if the given URL is syntactically valid
    """
    try:
        validate_url(url)
    except ValidationError:
        return False
    return True


@register.filter
def badgeify(blob):
    """
    Add an appropriate bootstrap badge around "text", based on its contents.
    """
    config = [
        (r"rejected|not ready|serious issues", "danger", "x-lg"),
        (r"complete|accepted|ready", "success", ""),
        (r"has nits|almost ready", "info", "info-lg"),
        (r"has issues|on the right track", "warning", "exclamation-lg"),
        (r"assigned", "info", "person-plus-fill"),
        (r"will not review|overtaken by events|withdrawn", "secondary", "dash-lg"),
        (r"no response", "warning", "question-lg"),
    ]
    text = str(blob)

    for pattern, color, icon in config:
        if re.search(pattern, text, flags=re.IGNORECASE):
            # Shorten the badge text
            text = re.sub(r"with ", "w/", text, flags=re.IGNORECASE)
            text = re.sub(r"document", "doc", text, flags=re.IGNORECASE)
            text = re.sub(r"will not", "won't", text, flags=re.IGNORECASE)

            return mark_safe(
                f"""
                <span class="badge rounded-pill text-bg-{color} text-wrap">
                    <i class="bi bi-{icon}"></i> {text.capitalize()}
                </span>
                """
            )

    return text

@register.filter
def simple_history_delta_changes(history):
    """Returns diff between given history and previous entry."""
    prev = history.prev_record
    if prev:
        delta = history.diff_against(prev)
        return delta.changes
    return []

@register.filter
def simple_history_delta_change_cnt(history):
    """Returns number of changes between given history and previous entry."""
    prev = history.prev_record
    if prev:
        delta = history.diff_against(prev)
        return len(delta.changes)
    return 0

@register.filter
def mtime(path):
    """Returns a datetime object representing mtime given a pathlib Path object"""
    return datetime.datetime.fromtimestamp(path.stat().st_mtime).astimezone(ZoneInfo(settings.TIME_ZONE))

@register.filter
def mtime_is_epoch(path):
    return path.stat().st_mtime == 0

@register.filter
def url_for_path(path):
    """Consructs a 'best' URL for web access to the given pathlib Path object.

    Assumes that the path is into the Internet-Draft archive or the proceedings.
    """
    if Path(settings.AGENDA_PATH) in path.parents:
        return (
            f"https://www.ietf.org/proceedings/{path.relative_to(settings.AGENDA_PATH)}"
        )
    elif any(
        [
            pathdir in path.parents
            for pathdir in [
                Path(settings.INTERNET_DRAFT_PATH),
                Path(settings.INTERNET_DRAFT_ARCHIVE_DIR).parent,
                Path(settings.INTERNET_ALL_DRAFTS_ARCHIVE_DIR),
            ]
        ]
    ):
        return f"{settings.IETF_ID_ARCHIVE_URL}{path.name}"
    else:
        return "#"


@register.filter
def is_in_stream(doc):
    """
    Check if the doc is in one of the states in it stream that
    indicate that is actually adopted, i.e., part of the stream.
    (There are various "candidate" states that necessitate this
    filter.)
    """
    if not doc.stream:
        return False
    stream = doc.stream.slug
    state = doc.get_state_slug(f"draft-stream-{doc.stream.slug}")
    if not state:
        return True
    if stream == "ietf":
        return state not in ["wg-cand", "c-adopt"]
    elif stream == "irtf":
        return state != "candidat"
    elif stream == "iab":
        return state not in ["candidat", "diff-org"]
    elif stream == "editorial":
        return True
    return False
