#!/usr/bin/env python

import re
import textwrap
try:
    from ietf.contrib.BeautifulSoup import Tag, BeautifulSoup, NavigableString
except:
    from BeautifulSoup import Tag, BeautifulSoup, NavigableString

block_tags = ["[document]", "html", "body", "div", "blockquote", "table", "tr", "p", "pre", "h1", "h2", "h3", "h4", "h5", "h6", ]
ignore_tags = ["head", "script", "style"]
pre_tags = ["pre"]
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

def para(words, pre):
    text = "".join(words)
    text = unescape(text)
    if not pre:
        #print "*** Text to be wrapped:"
        #print "["+text+"]"
        text = re.sub("[\t ]+", " ", text)
        text = text.strip("\n")
        text = textwrap.fill(text)  
    return text

def normalize(str):
    # Normalize whitespace at the beginning and end of the string
    str = re.sub("^[ \t]+", " ", str)
    str = re.sub("[ \t]+$", " ", str)
    # remove comments
    str = re.sub("(?s)<!--.*?-->", "", str)    
    # remove xml PIs and metainformation
    str = re.sub("<![^>]*>", "", str)
    str = re.sub("<\?[^>]*\?>", "", str)
    return str

def render(node, encoding='latin-1', pre=False):
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
    # Line ending normalization
    html = html.replace("\r\n", "\n").replace("\r", "\n")
    # some preprocessing to handle common pathological cases
    html = re.sub("<br */?>[ \t\n]*(<br */?>)+", "<p/>", html)
    html = re.sub("<br */?>([^\n])", r"<br />\n\1", html)
    html = re.sub("([^ \t\n])(</t[hd].*?>)", r"\1 \2", html)
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
        file.close()
        print soup2text(html)
