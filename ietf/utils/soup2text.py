#!/usr/bin/env python
# Copyright The IETF Trust 2007, All Rights Reserved

import re
import textwrap
try:
    from ietf.contrib.BeautifulSoup import Tag, BeautifulSoup, NavigableString
except:
    from BeautifulSoup import Tag, BeautifulSoup, NavigableString

block_tags = ["[document]", "html", "body", "div", "blockquote", "table", "tr", "p", "pre", "h1", "h2", "h3", "h4", "h5", "h6", "li", "option"]
space_tags = ["th", "td"]
break_tags = ["br"]
ignore_tags = ["head", "script", "style"]
pre_tags = ["pre", "option"]
entities = [("&lt;", "<"),   ("&gt;", ">"),
            ("&quot;", '"'), ("&apos;", "'"),
            ("&nbsp;", " "),
            ("&amp;", "&"), ]           # ampersand last

def unescape(text):
    # Unescape character codes (if possible)
    start = 0
    while True:
        try:
            pos = text.index("&#", start)
        except ValueError:
            break
        match = re.match("&#\d+;", text[pos:])
        if match:
            str = match.group()
            num = int(str[2:-1])
            if num < 256:
                text = text[:pos] + chr(num) + text[pos+len(str):]
                start = pos + 1
            else:
                start = pos + len(str)
        else:
            start = pos + 2
    # unescape character entities
    for entity, char in entities:
        text = text.replace(entity, char) # replace ampersand last
    return text

def para(words, pre, fill):
    text = "".join(words)
    text = unescape(text)
    if not pre:
        text = text.strip("\n")
        text = text.lstrip()
        text = re.sub("[\t\n ]+", " ", text)
        if fill:
            text = textwrap.fill(text)  
    return text

def normalize(str):
    # Normalize whitespace at the beginning and end of the string
    str = re.sub("^[ \t]+", " ", str)
    str = re.sub("[ \t]+$", " ", str)
    # remove xml PIs and metainformation
    str = re.sub("<![^>]*>", "", str)
    str = re.sub("<\?[^>]*\?>", "", str)
    return str

def render(node, encoding='latin-1', pre=False, fill=True, clean=True):
    blocks = []
    words = []
    node.pre = pre or node.name in pre_tags
    node.is_block = node.name in block_tags
    for child in node:
        if isinstance(child, NavigableString):
            str = child.__str__(encoding)
            if str and not node.pre:
                str = normalize(str)
            if str:
                words.append(str)
        elif isinstance(child, Tag):
            if child.name in ignore_tags:
                pass
            else:
                child = render(child, encoding, node.pre, fill, clean)
                if child.text:
                    if child.is_block:
                        if words :
                            blocks.append(para(words, node.pre, fill)+"\n")
                            words = []
                        blocks.append(child.text+"\n\n")
                        node.is_block = True
                    else:
                        words.append(child.text)
                        if child.text[-1] not in [" ", "\t", "\n"]:
                            if child.name in space_tags:
                                words.append(" ")
                            if child.name in break_tags:
                                words.append("\n")
        else:
            raise ValueError("Unexpected node type: '%s'" % child)
    if words:
        blocks.append(para(words, node.pre, fill))

    node.text = ''.join(blocks)
    return node

class TextSoup(BeautifulSoup):

    def as_text(self, encoding='latin-1', pre=False, fill=True, clean=True):
        node = render(self, encoding, pre, fill, clean)
        str = node.text
        if clean:
            str = re.sub("[ \t]+", " ", str)
            str = re.sub("\n\n+", "\n\n", str)
        return str

    def __str__(self, encoding='latin-1',
                prettyPrint=False, indentLevel=0):
        node = render(self, encoding, fill=False)
        str = node.text
        str = re.sub("[ \t]+", " ", str)
        str = re.sub("\n\n+", "\n\n", str)
        return str

def soup2text(html, encoding='latin-1', pre=False, fill=True):
    soup = TextSoup(html)
    return soup.as_text(encoding, pre, fill)

if __name__ == "__main__":
    import sys
    import urllib2 as urllib
    for arg in sys.argv[1:]:
        if arg[:6] in ["http:/", "https:", "ftp://"]:
            file = urllib.urlopen(arg)
        else:
            file = open(arg)
        html = file.read()
        file.close()
        print soup2text(html)
