# Copyright The IETF Trust 2025, All Rights Reserved
"""Utilities and customization for the bleach library"""
import bleach as _bleach
import copy

protocols = set(_bleach.sanitizer.ALLOWED_PROTOCOLS)
protocols.add("ftp")  # we still have some ftp links
protocols.add("xmpp")  # we still have some xmpp links

acceptable_tags = set(_bleach.sanitizer.ALLOWED_TAGS).union(
    {
        # fmt: off
        'a', 'abbr', 'acronym', 'address', 'b', 'big',
        'blockquote', 'body', 'br', 'caption', 'center', 'cite', 'code', 'col',
        'colgroup', 'dd', 'del', 'dfn', 'dir', 'div', 'dl', 'dt', 'em', 'font',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'head', 'hr', 'html', 'i', 'ins', 'kbd',
        'li', 'ol', 'p', 'pre', 'q', 's', 'samp', 'small', 'span', 'strike', 'style',
        'strong', 'sub', 'sup', 'table', 'title', 'tbody', 'td', 'tfoot', 'th', 'thead',
        'tr', 'tt', 'u', 'ul', 'var'
        # fmt: on
    }
)

attributes = copy.copy(_bleach.sanitizer.ALLOWED_ATTRIBUTES)
attributes["*"] = ["id"]
attributes["ol"] = ["start"]

bleach_cleaner = _bleach.sanitizer.Cleaner(
    tags=acceptable_tags, attributes=attributes, protocols=protocols, strip=True
)


liberal_tags = copy.copy(acceptable_tags)
liberal_attributes = copy.copy(attributes)
liberal_tags.update(["img", "figure", "figcaption"])
liberal_attributes["img"] = ["src", "alt"]

liberal_bleach_cleaner = _bleach.sanitizer.Cleaner(
    tags=liberal_tags, attributes=liberal_attributes, protocols=protocols, strip=True
)

def check_url_validity(attrs, new=False):
    if (None, "href") not in attrs:
        # rfc2html creates a tags without href
        return attrs
    url = attrs[(None, "href")]
    try:
        if url.startswith("http"):
            validate_url(url)
    except ValidationError:
        return None
    return attrs


bleach_linker = _bleach.Linker(
    callbacks=[check_url_validity],
    url_re=bleach.linkifier.build_url_re(tlds=tlds_sorted, protocols=protocols),
    email_re=bleach.linkifier.build_email_re(tlds=tlds_sorted),  # type: ignore
    parse_email=True,
)
