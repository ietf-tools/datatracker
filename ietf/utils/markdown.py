# Copyright The IETF Trust 2021, All Rights Reserved
# -*- coding: utf-8 -*-
"""Markdown wrapper

Use this instead of importing markdown directly to guarantee consistent extensions / options through
the datatracker.
"""
import markdown as python_markdown
from markdown.extensions import Extension
from markdown.postprocessors import Postprocessor

from django.utils.safestring import mark_safe
from django.utils.regex_helper import _lazy_re_compile
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, EmailValidator

from ietf.doc.templatetags.ietf_filters import urlize_ietf_docs
from .html import clean_html, liberal_clean_html

import re
import xml


_validate_url = URLValidator()
_validate_email = EmailValidator()

linkable_protocols = ["http", "https", "mailto", "ftp", "xmpp"]

# Simple Markdown extension inspired by https://github.com/django-wiki/django-wiki/blob/main/src/wiki/plugins/links/mdx/urlize.py
    
URL_RE = (
    r"^(?P<begin>|.*?[\s\(\<])"
    r"(?P<url>"  
    r"(?P<protocol>([a-zA-Z:]+\/{2}|))"
    r"(?P<host>"  
    r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}|"  # IPv4
    r"\[[a-zA-Z0-9:]+\]|" # IPv6 
    r"([A-Z0-9]([A-Z0-9-]{0,61}[A-Z0-9])?\.)+([A-Z]{2,6}\.?|[A-Z]{2,}\.?)"  # FQDN
    r")"  
    r"(:(?P<port>[0-9]+))?"
    r"(/(?P<path>[^\s\[\(\]\)\<\>]*))?"
    r")"  
    r"(?P<end>[\s\)\>].*?|)$"
)

EMAIL_RE = (
    r"^(?P<begin>|.*?[\s\(\<])"
    r"(?P<email>"  
    r"[a-zA-Z0-9._-]+@[a-zA-Z0-0._]+\.[a-zA-Z]{2,4}"
    r")"  
    r"(?P<end>[\s\)\>].*?|)$"
)

class Linker(python_markdown.inlinepatterns.Pattern):
    def __init__(self, pattern, md, linker="url"):
        super().__init__(pattern, md)
        self.linker = linker
        
    def getCompiledRegExp(self):
        return _lazy_re_compile(self.pattern, re.DOTALL | re.UNICODE | re.IGNORECASE)
    
    def handleMatch(self, m):
        if self.linker == "url":
            text = m.group("url")
            protocol = m.group("protocol") 
            if protocol == "" or protocol[:-3] not in linkable_protocols:
                return None
            href = text 
            try: 
                _validate_url(text)
            except ValidationError:
                return None
                
        else:
            text = m.group("email")
            href = "mailto:" + text
            try: 
                _validate_email(text)
            except ValidationError:
                return None
                
        delimitor = m.group("begin") + m.group("end")
        tags = re.search(r"(\<([\s\S])+?\>)", delimitor)
        if tags:
            return None
          
        el = xml.etree.ElementTree.Element("a")
        el.set("href", href)
        el.set("rel", "noopener noreferrer")
        el.text = python_markdown.util.AtomicString(text)
        
        return el
        


class LinkifyExtension(Extension):
    """
    Simple Markdown extension inspired by https://github.com/daGrevis/mdx_linkify,
    but using our own linker directly. Doing the linkification on the converted
    Markdown output introduces artifacts.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def extendMarkdown(self, md):
        md.inlinePatterns.register(Linker(URL_RE, md, linker="url"), "autolink_url", 91) 
        md.inlinePatterns.register(Linker(EMAIL_RE, md, linker="email"), "autolink_email", 92)
        md.postprocessors.register(LinkifyPostprocessor(md), "linkify", 93)
        # disable automatic links via angle brackets for email addresses
        md.inlinePatterns.deregister("automail")
        # "autolink" for URLs does not seem to cause issues, so leave it on
        
        
class LinkifyPostprocessor(Postprocessor):
    def run(self, text):
        return urlize_ietf_docs(text)


def markdown(text):
    return mark_safe(
        clean_html(
            python_markdown.markdown(
                text,
                extensions=[
                    "extra",
                    "nl2br",
                    "sane_lists",
                    "toc",
                    LinkifyExtension(),
                ],
            )
        )
    )

def liberal_markdown(text):
    return mark_safe(
        liberal_clean_html(
            python_markdown.markdown(
                text,
                extensions=[
                    "extra",
                    "nl2br",
                    "sane_lists",
                    "toc",
                    LinkifyExtension(),
                ],
            )
        )
    )
