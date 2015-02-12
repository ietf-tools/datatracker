import re
from typogrify.packages.titlecase import titlecase  # NOQA

class TypogrifyError(Exception):
    """ A base error class so we can catch or scilence typogrify's errors in templates """
    pass

def process_ignores(text, ignore_tags=None):
    """ Creates a list of tuples based on tags to be ignored.
    Tags can be added as a list in the `ignore_tags`. Tags
    can also be filtered on id and class using CSS notation.
    For example, div#test (div with id='test'), div.test
    (div with class='test'), #test (any tag with id='test')
    or .test (any tag with class='test'). 
    
    Returns in the following format:

    [
        ('Text here', <should text be processed? True|False>),
        ('Text here', <should text be processed? True|False>),
    ]

    >>> process_ignores('<pre>processed</pre><p>processed</p>')
    [('<pre>processed</pre>', False), ('<p>processed</p>', True)]
    >>> process_ignores('<code>processed</code><p>processed<pre>processed</pre></p>')
    [('<code>processed</code>', False), ('<p>processed', True), ('<pre>processed</pre>', False), ('</p>', True)]
    >>> process_ignores('<code>processed</code><p>processed<pre>processed</pre></p>',['p'])
    [('<code>processed</code>', False), ('<p>processed<pre>processed</pre></p>', False)]
    >>> process_ignores('<span class="test">processed</span><span>processed<div>processed</div></span>',['div', 'span.test'])
    [('<span class="test">processed</span>', False), ('<span>processed', True), ('<div>processed</div>', False), ('</span>', True)]
    >>> process_ignores('<span class="TeSt">processed</span><span>processed<div>processed</div></span>',['div', '.test'])
    [('<span class="TeSt">processed</span>', False), ('<span>processed', True), ('<div>processed</div>', False), ('</span>', True)]
    >>> process_ignores('<span class="test">processed</span><span>processed<div>processed</div></span>',['div', '#test'])
    [('<span class="test">processed</span><span>processed', True), ('<div>processed</div>', False), ('</span>', True)]
    >>> process_ignores('<span id = "test">processed</span><span>processed<div>processed</div></span>',['div', 'span#test'])
    [('<span id = "test">processed</span>', False), ('<span>processed', True), ('<div>processed</div>', False), ('</span>', True)]
    >>> process_ignores('<span extra class="test" extra>processed</span><span>processed<div class="test">processed</div></span>',['div', 'span.test'])
    [('<span extra class="test" extra>processed</span>', False), ('<span>processed', True), ('<div class="test">processed</div>', False), ('</span>', True)]
    >>> process_ignores('<span e x t r a class="test" extra>processed</span><span>processed<div class="test">processed</div></span>',['.test'])
    [('<span e x t r a class="test" extra>processed</span>', False), ('<span>processed', True), ('<div class="test">processed</div>', False), ('</span>', True)]
    """

    def _filter_tag(match):
        """Process user tag filters in regex sub"""

        tag = match.group(1) if match.group(1) != '' else '[^\s.#<>]+'
        attribute = 'class' if match.group(2)[0] == '.' else 'id'
        attribute_value = match.group(2)[1:]
        _filter_tag.group += 1

        result = r"""
                 (?: {tag}
                 (?= [^>]*?
                 {attribute} \s*=\s*
                 (['"]) {attribute_value} \{0}
                 ))""".format(_filter_tag.group, **locals())
       
        return result
    
    _filter_tag.group = 1
    position = 0
    sections = []

    if ignore_tags is None:
        ignore_tags = []

    # make ignore_tags unique and have 'pre' and 'code' as default
    ignore_tags = set(map(lambda x: x.strip(), ignore_tags)) | set(['pre', 'code'])

    # classify tags
    non_filtered_tags = set(filter(lambda x: '.' not in x and '#' not in x, ignore_tags))
    generic_filtered_tags = set(filter(lambda x: x.startswith(('.','#')), ignore_tags))
    filtered_tags = ignore_tags-(non_filtered_tags | generic_filtered_tags)

    # remove redundancy from filtered_tags
    filtered_tags = filter(lambda x: not any(tag in x for tag in generic_filtered_tags),
                    filtered_tags)
    filtered_tags = filter(lambda x: not any(tag in x for tag in non_filtered_tags),
                    filtered_tags)

    # alter the tags that must be filtered for the regex
    sub = lambda tag: re.sub(r'^([^\s.#<>]*)([.#][^\s.#<>]+)$', _filter_tag, tag)
    generic_filtered_tags = list(map(sub, generic_filtered_tags))
    filtered_tags = list(map(sub, filtered_tags))

    # create regex
    ignore_tags = list(non_filtered_tags | set(generic_filtered_tags) | set(filtered_tags))
    ignore_regex = r'(?:<(%s)[^>]*>.*?</\1>)' % '|'.join(ignore_tags)
    ignore_finder = re.compile(ignore_regex, re.IGNORECASE | re.DOTALL | re.VERBOSE)

    # process regex
    for section in ignore_finder.finditer(text):
        start, end = section.span()

        if position != start:
            # if the current position isn't the match we
            # need to process everything in between
            sections.append((text[position:start], True))

        # now we mark the matched section as ignored
        sections.append((text[start:end], False))

        position = end

    # match the rest of the text if necessary
    # (this could in fact be the entire string)
    if position < len(text):
        sections.append((text[position:len(text)], True))

    return sections

def amp(text):
    """Wraps apersands in HTML with ``<span class="amp">`` so they can be
    styled with CSS. Apersands are also normalized to ``&amp;``. Requires
    ampersands to have whitespace or an ``&nbsp;`` on both sides.

    >>> amp('One & two')
    'One <span class="amp">&amp;</span> two'
    >>> amp('One &amp; two')
    'One <span class="amp">&amp;</span> two'
    >>> amp('One &#38; two')
    'One <span class="amp">&amp;</span> two'

    >>> amp('One&nbsp;&amp;&nbsp;two')
    'One&nbsp;<span class="amp">&amp;</span>&nbsp;two'

    It won't mess up & that are already wrapped, in entities or URLs

    >>> amp('One <span class="amp">&amp;</span> two')
    'One <span class="amp">&amp;</span> two'
    >>> amp('&ldquo;this&rdquo; & <a href="/?that&amp;test">that</a>')
    '&ldquo;this&rdquo; <span class="amp">&amp;</span> <a href="/?that&amp;test">that</a>'

    It should ignore standalone amps that are in attributes
    >>> amp('<link href="xyz.html" title="One & Two">xyz</link>')
    '<link href="xyz.html" title="One & Two">xyz</link>'
    """
    # tag_pattern from http://haacked.com/archive/2004/10/25/usingregularexpressionstomatchhtml.aspx
    # it kinda sucks but it fixes the standalone amps in attributes bug
    tag_pattern = '</?\w+((\s+\w+(\s*=\s*(?:".*?"|\'.*?\'|[^\'">\s]+))?)+\s*|\s*)/?>'
    amp_finder = re.compile(r"(\s|&nbsp;)(&|&amp;|&\#38;)(\s|&nbsp;)")
    intra_tag_finder = re.compile(r'(?P<prefix>(%s)?)(?P<text>([^<]*))(?P<suffix>(%s)?)' % (tag_pattern, tag_pattern))

    def _amp_process(groups):
        prefix = groups.group('prefix') or ''
        text = amp_finder.sub(r"""\1<span class="amp">&amp;</span>\3""", groups.group('text'))
        suffix = groups.group('suffix') or ''
        return prefix + text + suffix

    output = intra_tag_finder.sub(_amp_process, text)
    return output


def caps(text):
    """Wraps multiple capital letters in ``<span class="caps">``
    so they can be styled with CSS.

    >>> caps("A message from KU")
    'A message from <span class="caps">KU</span>'

    Uses the smartypants tokenizer to not screw with HTML or with tags it shouldn't.

    >>> caps("<SCRIPT>CAPS</script> more CAPS")
    '<SCRIPT>CAPS</script> more <span class="caps">CAPS</span>'

    >>> caps("A message from 2KU2 with digits")
    'A message from <span class="caps">2KU2</span> with digits'

    >>> caps("Dotted caps followed by spaces should never include them in the wrap D.O.T.   like so.")
    'Dotted caps followed by spaces should never include them in the wrap <span class="caps">D.O.T.</span>  like so.'

    All caps with with apostrophes in them shouldn't break. Only handles dump apostrophes though.
    >>> caps("JIMMY'S")
    '<span class="caps">JIMMY\\'S</span>'

    >>> caps("<i>D.O.T.</i>HE34T<b>RFID</b>")
    '<i><span class="caps">D.O.T.</span></i><span class="caps">HE34T</span><b><span class="caps">RFID</span></b>'
    """
    try:
        import smartypants
    except ImportError:
        raise TypogrifyError("Error in {% caps %} filter: The Python SmartyPants library isn't installed.")

    tokens = smartypants._tokenize(text)
    result = []
    in_skipped_tag = False

    cap_finder = re.compile(r"""(
                            (\b[A-Z\d]*        # Group 2: Any amount of caps and digits
                            [A-Z]\d*[A-Z]      # A cap string much at least include two caps (but they can have digits between them)
                            [A-Z\d']*\b)       # Any amount of caps and digits or dumb apostsrophes
                            | (\b[A-Z]+\.\s?   # OR: Group 3: Some caps, followed by a '.' and an optional space
                            (?:[A-Z]+\.\s?)+)  # Followed by the same thing at least once more
                            (?:\s|\b|$))
                            """, re.VERBOSE)

    def _cap_wrapper(matchobj):
        """This is necessary to keep dotted cap strings to pick up extra spaces"""
        if matchobj.group(2):
            return """<span class="caps">%s</span>""" % matchobj.group(2)
        else:
            if matchobj.group(3)[-1] == " ":
                caps = matchobj.group(3)[:-1]
                tail = ' '
            else:
                caps = matchobj.group(3)
                tail = ''
            return """<span class="caps">%s</span>%s""" % (caps, tail)

    # Add additional tags whose content should be
    # ignored here. Note - <pre> and <code> tag are
    # ignored by default and therefore are not here
    tags_to_skip_regex = re.compile("<(/)?(?:kbd|script)[^>]*>", re.IGNORECASE)

    for token in tokens:
        if token[0] == "tag":
            # Don't mess with tags.
            result.append(token[1])
            close_match = tags_to_skip_regex.match(token[1])
            if close_match and close_match.group(1) == None:
                in_skipped_tag = True
            else:
                in_skipped_tag = False
        else:
            if in_skipped_tag:
                result.append(token[1])
            else:
                result.append(cap_finder.sub(_cap_wrapper, token[1]))
    output = "".join(result)
    return output


def initial_quotes(text):
    """Wraps initial quotes in ``class="dquo"`` for double quotes or
    ``class="quo"`` for single quotes. Works in these block tags ``(h1-h6, p, li, dt, dd)``
    and also accounts for potential opening inline elements ``a, em, strong, span, b, i``

    >>> initial_quotes('"With primes"')
    '<span class="dquo">"</span>With primes"'
    >>> initial_quotes("'With single primes'")
    '<span class="quo">\\'</span>With single primes\\''

    >>> initial_quotes('<a href="#">"With primes and a link"</a>')
    '<a href="#"><span class="dquo">"</span>With primes and a link"</a>'

    >>> initial_quotes('&#8220;With smartypanted quotes&#8221;')
    '<span class="dquo">&#8220;</span>With smartypanted quotes&#8221;'
    """
    quote_finder = re.compile(r"""((<(p|h[1-6]|li|dt|dd)[^>]*>|^)              # start with an opening p, h1-6, li, dd, dt or the start of the string
                                  \s*                                          # optional white space!
                                  (<(a|em|span|strong|i|b)[^>]*>\s*)*)         # optional opening inline tags, with more optional white space for each.
                                  (("|&ldquo;|&\#8220;)|('|&lsquo;|&\#8216;))  # Find me a quote! (only need to find the left quotes and the primes)
                                                                               # double quotes are in group 7, singles in group 8
                                  """, re.VERBOSE)

    def _quote_wrapper(matchobj):
        if matchobj.group(7):
            classname = "dquo"
            quote = matchobj.group(7)
        else:
            classname = "quo"
            quote = matchobj.group(8)
        return """%s<span class="%s">%s</span>""" % (matchobj.group(1), classname, quote)
    output = quote_finder.sub(_quote_wrapper, text)
    return output


def smartypants(text):
    """Applies smarty pants to curl quotes.

    >>> smartypants('The "Green" man')
    'The &#8220;Green&#8221; man'
    """
    try:
        import smartypants
    except ImportError:
        raise TypogrifyError("Error in {% smartypants %} filter: The Python smartypants library isn't installed.")
    else:
        output = smartypants.smartypants(text)
        return output


def widont(text):
    """Replaces the space between the last two words in a string with ``&nbsp;``
    Works in these block tags ``(h1-h6, p, li, dd, dt)`` and also accounts for
    potential closing inline elements ``a, em, strong, span, b, i``

    >>> widont('A very simple test')
    'A very simple&nbsp;test'

    Single word items shouldn't be changed
    >>> widont('Test')
    'Test'
    >>> widont(' Test')
    ' Test'
    >>> widont('<ul><li>Test</p></li><ul>')
    '<ul><li>Test</p></li><ul>'
    >>> widont('<ul><li> Test</p></li><ul>')
    '<ul><li> Test</p></li><ul>'

    >>> widont('<p>In a couple of paragraphs</p><p>paragraph two</p>')
    '<p>In a couple of&nbsp;paragraphs</p><p>paragraph&nbsp;two</p>'

    >>> widont('<h1><a href="#">In a link inside a heading</i> </a></h1>')
    '<h1><a href="#">In a link inside a&nbsp;heading</i> </a></h1>'

    >>> widont('<h1><a href="#">In a link</a> followed by other text</h1>')
    '<h1><a href="#">In a link</a> followed by other&nbsp;text</h1>'

    Empty HTMLs shouldn't error
    >>> widont('<h1><a href="#"></a></h1>')
    '<h1><a href="#"></a></h1>'

    >>> widont('<div>Divs get no love!</div>')
    '<div>Divs get no love!</div>'

    >>> widont('<pre>Neither do PREs</pre>')
    '<pre>Neither do PREs</pre>'

    >>> widont('<div><p>But divs with paragraphs do!</p></div>')
    '<div><p>But divs with paragraphs&nbsp;do!</p></div>'
    """

    widont_finder = re.compile(r"""((?:</?(?:a|em|span|strong|i|b)[^>]*>)|[^<>\s]) # must be proceeded by an approved inline opening or closing tag or a nontag/nonspace
                                   \s+                                             # the space to replace
                                   ([^<>\s]+                                       # must be flollowed by non-tag non-space characters
                                   \s*                                             # optional white space!
                                   (</(a|em|span|strong|i|b)>\s*)*                 # optional closing inline tags with optional white space after each
                                   ((</(p|h[1-6]|li|dt|dd)>)|$))                   # end with a closing p, h1-6, li or the end of the string
                                   """, re.VERBOSE)
    output = widont_finder.sub(r'\1&nbsp;\2', text)

    return output

def applyfilters(text):
    """Applies the following filters: smartypants, caps, amp, initial_quotes

    >>> typogrify('<h2>"Jayhawks" & KU fans act extremely obnoxiously</h2>')
    '<h2><span class="dquo">&#8220;</span>Jayhawks&#8221; <span class="amp">&amp;</span> <span class="caps">KU</span> fans act extremely&nbsp;obnoxiously</h2>'
    """
    text = amp(text)
    text = smartypants(text)
    text = caps(text)
    text = initial_quotes(text)

    return text

def typogrify(text, ignore_tags=None):
    """The super typography filter

        Applies filters to text that are not in tags contained in the
        ignore_tags list.
    """

    section_list = process_ignores(text, ignore_tags)

    rendered_text = ""
    for text_item, should_process in section_list:
        if should_process:
            rendered_text += applyfilters(text_item)
        else:
            rendered_text += text_item

    # apply widont at the end, as its already smart about tags. Hopefully.
    return widont(rendered_text)

def _test():
    import doctest
    doctest.testmod(verbose=True)

if __name__ == "__main__":
    _test()
