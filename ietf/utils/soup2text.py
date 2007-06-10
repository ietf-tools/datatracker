#!/usr/bin/env python

import re
import textwrap
from ietf.contrib.BeautifulSoup import Tag, BeautifulSoup, NavigableString

block_tags = ["[document]", "html", "body", "div", "blockquote", "table", "tr", "p", "pre", "h1", "h2", "h3", "h4", "h5", "h6", ]
ignore_tags = ["head", "script", "style"]
pre_tags = ["pre"]
entities = [("&lt;", "<"),   ("&gt;", ">"),
            ("&quot;", '"'), ("&apos;", "'"),
            ("&nbsp;", " "),
            ("&amp;", "&"), ]

def para(words, pre):
    text = " ".join(words)
    for entity, char in entities:
        text = text.replace(entity, char)
    if not pre:
        text = re.sub("[\r\n\t ]+", " ", text)
        text = textwrap.fill(text)
    return text

def render(node, encoding='latin-1', pre=False):
    blocks = []
    words = []
    node.pre = pre or node.name in pre_tags
    node.is_block = node.name in block_tags
    for child in node:
        if isinstance(child, NavigableString):
            str = child.__str__(encoding)
            if str and not node.pre:
                str = str.strip()
            if str and not str.startswith("<!") and not str.startswith("<?"):
                words.append(str)
        elif isinstance(child, Tag):
            if child.name in ignore_tags:
                pass
            else:
                child = render(child, encoding, node.pre)
                if child.text:
                    if child.is_block:
                        if words :
                            blocks.append(para(words, node.pre)+"\n")
                            words = []
                        blocks.append(child.text+"\n\n")
                        node.is_block = True
                    else:
                        words.append(child.text)
        else:
            raise ValueError("Unexpected node type: '%s'" % child)
    if words:
        blocks.append(para(words, node.pre))

    node.text = ''.join(blocks)
    return node

class TextSoup(BeautifulSoup):

    def __str__(self, encoding='latin-1',
                prettyPrint=False, indentLevel=0):
        node = render(self, encoding)
        str = node.text
        str = re.sub("[ \t]+", " ", str)
        str = re.sub("\n\n+", "\n\n", str)
        return str

def soup2text(html):
    soup = TextSoup(html)
    return str(soup)

if __name__ == "__main__":
    import sys
    import urllib2 as urllib
    for arg in sys.argv[1:]:
        if arg[:6] in ["http:/", "https:", "ftp://"]:
            file = urllib.urlopen(arg)
        else:
            file = open(arg)
        html = file.read()
        file.close
        soup = TextSoup(html)
        print str(soup)
