import re
import cgi
import urllib

def markup(text, path=".", script="", extra=""):

        # ------------------------------------------------------------------------
        # Start of markup handling

        # Convert \r which is not followed or preceded by a \n to \n
        #  (in case this is a mac document)
        text = re.sub("([^\n])\r([^\n])", "\g<1>\n\g<2>", text)
        # Strip \r (in case this is a ms format document):
        text = text.replace("\r","")

        # -------------
        # Normalization

        # Remove whitespace at the end of lines
        text = re.sub("[\t ]+\n", "\n", text)

        # Remove whitespace (including formfeeds) at the end of the document.
        # (Trailing formfeeds will result in trailing blank pages.)
        text = re.sub("[\t \r\n\f]+$", "\n", text)

        text = text.expandtabs()

        # Remove extra blank lines at the start of the document
        text = re.sub("^\n*", "", text, 1)

        # Fix up page breaks:
        # \f should aways be preceeded and followed by \n
        text = re.sub("([^\n])\f", "\g<1>\n\f", text)
        text = re.sub("\f([^\n])", "\f\n\g<1>", text)
        # Limit the number of blank lines after page break
        text = re.sub("\f\n+", "\f\n", text)

        # [Page nn] should be followed by \n\f\n
        text = re.sub("(?i)(\[Page [0-9ivxlc]+\])[\n\f\t ]*(\n *[^\n\f\t ])", "\g<1>\n\f\g<2>", text)
        
        # Normalize indentation
        linestarts = re.findall("(?m)^([ ]*)\S", text);
        prefixlen = 72
        for start in linestarts:
            if len(start) < prefixlen:
                prefixlen = len(start)
        if prefixlen:
            text = re.sub("\n"+(" "*prefixlen), "\n", text)

        # reference name tag markup
        reference = {}
        ref_url = {}

        ## Locate the start of the References section as the first reference
        ## definition after the last reference usage
        ## Incomplete 05 Aug 2010 17:05:27 XXXX Complete this!!

        ref_start = re.search("(?im)^(\d+(\.\d+)*)(\.?[ ]+)(References?|Normative References?|Informative References?)", text)
        ref_text = text[ref_start.end():] if ref_start else text
        

        ##ref_usages = re.findall("(\W)(\[)([-\w.]+)((, ?[-\w.]+)*\])", text)
        ref_defs = re.findall("(?sm)^( *\n *)\[([-\w.]+?)\]( +)(.*?)(\n *)$", ref_text)

        ##ref_pos = [ match.start() for match in ref_usages ]
        ##def_pos = [ match.start() for match in ref_defs ]
        ##ref_pos = [ pos for pos in ref_pos if not pos in ref_defs ]
        ##last_ref_pos = ref_pos[-1] if ref_pos else None

        #sys.stderr.write("ref_defs: %s\n" % repr(ref_defs))        
        for tuple in ref_defs:
            title_match = re.search("(?sm)^(.*?(\"[^\"]+?\").+?|.*?(,[^,]+?,)[^,]+?)$", tuple[3])
            if title_match:
                reftitle = title_match.group(2) or title_match.group(3).strip("[ ,]+")
                # Get rid of page break information inside the title
                reftitle = re.sub("(?s)\n\n\S+.*\n\n", "", reftitle)
                reftitle = cgi.escape(reftitle, quote=True)
                reftitle = re.sub("[\n\t ]+", " ", reftitle) # Remove newlines and tabs
                reference[tuple[1]] = reftitle if not re.search(r'(?i)(page|section|appendix)[- ]', reftitle) else ''
            url_match = re.search(r"(http|https|ftp)://\S+", tuple[3])
            if url_match:
                ref_url[tuple[1]] = url_match.group(0)
                
        # -------------
        # escape any html significant characters
        text = cgi.escape(text);


        # -------------
        # Adding markup

        text = "<pre>"+text+"</pre>"

        # Typewriter-style underline:
        text = re.sub("_[\b](.)", "<u>\g<1></u>", text)

        # Line number markup goes here


        # Obsoletes: ... markup
        
        def rfclist_replace(keyword, text):
            def replacement(match):
                group = list(match.groups(""))
                group[3] = re.sub("\d+", """<a href=\"%s?%srfc=\g<0>\">\g<0></a>""" % (script, extra), group[3])
                if group[8]:
                    group[8] = re.sub("\d+", """<a href=\"%s?%srfc=\g<0>\">\g<0></a>""" % (script, extra), group[8])
                else:
                    group[8] = ""
                return "\n%s%s%s\n%s%s" % (group[0], group[3], group[5], group[7], group[8])
            text = re.sub("\n(%s( RFCs| RFC)?: ?( RFCs| RFC)?)(( \d+,| \d+)+)(.*)\n(( *)((\d+, )*(\d+)))*" % keyword, replacement, text, 1)
            return text

        text = rfclist_replace("Obsoletes", text)
        text = rfclist_replace("Updates", text)
        
        lines = text.splitlines(True)
        head  = "".join(lines[:28])
        rest  = "".join(lines[28:])

        # title markup
        head = re.sub("""(?im)(([12][0-9][0-9][0-9]|^Obsoletes.*|^Category: (Standards Track|Informational|Experimental|Best Current Practice)) *\n\n+ +)([A-Z][^\n]+)$""", """\g<1><span class=\"h1\">\g<4></span>""", head, 1)
        head = re.sub("""(?i)(<span class="h1".+</span>)(\n +)([^<\n]+)\n""", """\g<1>\g<2><span class="h1">\g<3></span>\n""", head, 1)
        head = re.sub("""(?i)(<span class="h1".+</span>)(\n +)([^<\n]+)\n""", """\g<1>\g<2><span class="h1">\g<3></span>\n""", head, 1)

        text = head + rest

        # http link markup
        # link crossing a line.  Not permitting ":" after the line break will
        # result in some URLs broken across lines not being recognized, but
        # will on the other hand correctly handle a series of URL listed line
        # by line, one on each line.
        #  Link crossing a line, where the continuation contains '.' or '/'
	text = re.sub("(?im)(\s|^|[^=]\"|\()((http|https|ftp)://([:A-Za-z0-9_./@%&?#~=-]+)?)(\n +)([A-Za-z0-9_./@%&?#~=-]+[./][A-Za-z0-9_./@%&?#~=-]+[A-Za-z0-9_/@%&?#~=-])([.,)\"\s]|$)",
                        "\g<1><a href=\"\g<2>\g<6>\">\g<2></a>\g<5><a href=\"\g<2>\g<6>\">\g<6></a>\g<7>", text)
	text = re.sub("(?im)(&lt;)((http|https|ftp)://([:A-Za-z0-9_./@%&?#~=-]+)?)(\n +)([A-Za-z0-9_./@%&?#~=-]+[A-Za-z0-9_/@%&?#~=-])(&gt;)",
                        "\g<1><a href=\"\g<2>\g<6>\">\g<2></a>\g<5><a href=\"\g<2>\g<6>\">\g<6></a>\g<7>", text)
        #  Link crossing a line, where first line ends in '-' or '/'
	text = re.sub("(?im)(\s|^|[^=]\"|\()((http|https|ftp)://([:A-Za-z0-9_./@%&?#~=-]+)?[-/])(\n +)([A-Za-z0-9_./@%&?#~=-]+[A-Za-z0-9_/@%&?#~=-])([.,)\"\s]|$)",
                        "\g<1><a href=\"\g<2>\g<6>\">\g<2></a>\g<5><a href=\"\g<2>\g<6>\">\g<6></a>\g<7>", text)
	text = re.sub("(?im)(&lt;)((http|https|ftp)://([:A-Za-z0-9_./@%&?#~=-]+)?)(\n +)([A-Za-z0-9_./@%&?#~=-]+[A-Za-z0-9_/@%&?#~=-])(&gt;)",
                        "\g<1><a href=\"\g<2>\g<6>\">\g<2></a>\g<5><a href=\"\g<2>\g<6>\">\g<6></a>\g<7>", text)
        # link crossing a line, enclosed in "<" ... ">"
	text = re.sub("(?im)<((http|https|ftp)://([:A-Za-z0-9_./@%&?#~=-]+)?)(\n +)([A-Za-z0-9_./@%&?#~=-]+[A-Za-z0-9_/@%&?#~=-])>",
                        "<\g<1><a href=\"\g<1>\g<5>\">\g<1></a>\g<4><a href=\"\g<1>\g<5>\">\g<5></a>>", text)
	text = re.sub("(?im)(&lt;)((http|https|ftp)://([:A-Za-z0-9_./@%&?#~=-]+)?)(\n +)([A-Za-z0-9_./@%&;?#~=-]+[A-Za-z0-9_/@%&;?#~=-])(&gt;)",
                        "\g<1><a href=\"\g<2>\g<6>\">\g<2></a>\g<5><a href=\"\g<2>\g<6>\">\g<6></a>\g<7>", text)
        # link crossing two lines, enclosed in "<" ... ">"
	text = re.sub("(?im)<((http|https|ftp)://([:A-Za-z0-9_./@%&?#~=-]+)?)(\n +)([A-Za-z0-9_./@%&?#~=-]+[A-Za-z0-9_/@%&?#~=-])(\n +)([A-Za-z0-9_./@%&?#~=-]+[A-Za-z0-9_/@%&?#~=-])>",
                        "<\g<1><a href=\"\g<1>\g<5>\g<7>\">\g<1></a>\g<4><a href=\"\g<1>\g<5>\g<7>\">\g<5></a>\g<6><a href=\"\g<1>\g<5>\g<7>\">\g<7></a>>", text)
	text = re.sub("(?im)(&lt;)((http|https|ftp)://([:A-Za-z0-9_./@%&?#~=-]+)?)(\n +)([A-Za-z0-9_./@%&?#~=-]+[A-Za-z0-9_/@%&?#~=-])(\n +)([A-Za-z0-9_./@%&;?#~=-]+[A-Za-z0-9_/@%&;?#~=-])(&gt;)",
                        "\g<1><a href=\"\g<2>\g<6>\g<8>\">\g<2></a>\g<5><a href=\"\g<2>\g<6>\g<8>\">\g<6></a>\g<7><a href=\"\g<2>\g<6>\g<8>\">\g<8></a>\g<9>", text)
        # link on a single line
	text = re.sub("(?im)(\s|^|[^=]\"|&lt;|\()((http|https|ftp)://[:A-Za-z0-9_./@%&?#~=-]+[A-Za-z0-9_/@%&?#~=-])([.,)\"\s]|&gt;|$)",
                        "\g<1><a href=\"\g<2>\">\g<2></a>\g<4>", text)
#         # Special case for licensing boilerplate
#         text = text.replace('<a href="http://trustee.ietf.org/">http://trustee.ietf.org/</a>\n   license-info',
#                             '<a href="http://trustee.ietf.org/licence-info">http://trustee.ietf.org/</a>\n   <a href="http://trustee.ietf.org/licence-info">licence-info</a>')

        # undo markup if RFC2606 domain
        text = re.sub("""(?i)<a href="[a-z]*?://([a-z0-9_-]+?\.)?example(\.(com|org|net))?(/.*?)?">(.*?)</a>""", "\g<5>", text) 
  
        # draft markup
        # draft name crossing line break
	text = re.sub("([^/#=\?\w-])(draft-([-a-zA-Z0-9]+-)?)(\n +)([-a-zA-Z0-9]+[a-zA-Z0-9](.txt)?)",
                        "\g<1><a href=\"%s?%sdraft=\g<2>\g<5>\">\g<2></a>\g<4><a href=\"%s?%sdraft=\g<2>\g<5>\">\g<5></a>" % (script, extra, script, extra), text)
        # draft name on one line (but don't mess with what we just did above)
	text = re.sub("([^/#=\?\w>=-])(draft-[-a-zA-Z0-9]+[a-zA-Z0-9](.txt)?)",
                        "\g<1><a href=\"%s?%sdraft=\g<2>\">\g<2></a>" % (script, extra), text)

        # rfc markup
        # rfc and number on the same line
	text = re.sub("""(?i)([^[/>\w-])(rfc([- ]?))([0-9]+)(\W)""",
                        """\g<1><a href=\"%s?%srfc=\g<4>\">\g<2>\g<4></a>\g<5>""" % (script, extra), text)
        # rfc and number on separate lines
	text = re.sub("(?i)([^[/>\w-])(rfc([-]?))(\n +)([0-9]+)(\W)",
                        "\g<1><a href=\"%s?%srfc=\g<5>\">\g<2></a>\g<4><a href=\"%s?%srfc=\g<5>\">\g<5></a>\g<6>" % (script, extra, script, extra), text)
        # spelled out Request For Comments markup
	text = re.sub("(?i)(\s)(Request\s+For\s+Comments\s+\([^)]+\)\s+)([0-9]+)",
                        "\g<1>\g<2><a href=\"%s?%srfc=\g<3>\">\g<3></a>" % (script, extra), text)
        # bcp markup
	text = re.sub("(?i)([^[/>\w.-])(bcp([- ]?))([0-9]+)(\W)",
                        "\g<1><a href=\"%s?%sbcp=\g<4>\">\g<2>\g<4></a>\g<5>" % (script, extra), text)
	text = re.sub("(?i)([^[/>\w.-])(bcp([-]?))(\n +)([0-9]+)(\W)",
                        "\g<1><a href=\"%s?%sbcp=\g<5>\">\g<2></a>\g<4><a href=\"%s?%sbcp=\g<5>\">\g<5></a>\g<6>" % (script, extra, script, extra), text)

        def workinprogress_replacement(match):
            g1 = match.group(1)
            g2 = match.group(2)
            g3 = match.group(3)
            # eliminate embedded hyperlinks in text we'll use as anchor text
            g4 = match.group(4)
            g4 = re.sub("<a.+?>(.+?)</a>", "\g<1>", g4)
            g4url = urllib.quote_plus(g4)
            g5 = match.group(5)
            return """%s[<a id=\"ref-%s\">%s</a>]%s<a style=\"text-decoration: none\" href='https://www.google.com/search?sitesearch=datatracker.ietf.org%%2Fdoc%%2Fhtml%%2F&amp;q=inurl:draft-+%s'>%s</a>%s""" % (g1, g2, g2, g3, g4url, g4, g5)

        text = re.sub("(\n *\n *)\[([-\w.]+)\](\s+.*?)(\".+\")(,\s+Work\s+in\s+Progress.)", workinprogress_replacement, text)
        text = re.sub("(\n *\n *)\[([-\w.]+)\](\s)", "\g<1>[<a id=\"ref-\g<2>\">\g<2></a>]\g<3>", text)

        text = re.sub("(\n *\n *)\[(RFC [-\w.]+)\](\s)", "\g<1>[<a id=\"ref-\g<2>\">\g<2></a>]\g<3>", text)

        ref_targets = re.findall('<a id="ref-(.*?)"', text)

        # reference link markup
        def reference_replacement(match):
            pre = match.group(1)
            beg = match.group(2)
            tag = match.group(3)
            end = match.group(4)
            isrfc = re.match("(?i)^rfc[ -]?([0-9]+)$", tag)
            if isrfc:
                rfcnum = isrfc.group(1)
                if tag in reference:
                    return """%s%s<a href="%s?%srfc=%s" title="%s">%s</a>%s""" % (pre, beg, script, extra, rfcnum, reference[tag], tag, end)
                else:
                    return """%s%s<a href="%s?%srfc=%s">%s</a>%s""" % (pre, beg, script, extra, rfcnum , tag, end)
            else:
                if tag in ref_targets:
                    if tag in reference:
                        return """%s%s<a href="#ref-%s" title="%s">%s</a>%s""" % (pre, beg, tag, reference[tag], tag, end)
                    else:
                        return """%s%s<a href="#ref-%s">%s</a>%s""" % (pre, beg, tag, tag, end)
                else:
                    return match.group(0)

        # Group:       1   2   3        45
        text = re.sub("(\W)(\[)([-\w.]+)((, ?[-\w.]+)*\])", reference_replacement, text)
        text = re.sub("(\W)(\[)(RFC [0-9]+)((, ?RFC [0-9]+)*\])", reference_replacement, text)
        while True:
            old = text
            text = re.sub("(\W)(\[(?:<a.*?>.*?</a>, ?)+)([-\w.]+)((, ?[-\w.]+)*\])", reference_replacement, text)
            if text == old:
                break
        while True:
            old = text
            text = re.sub("(\W)(\[(?:<a.*?>.*?</a>, ?)+)(RFC [-\w.]+)((, ?RFC [-\w.]+)*\])", reference_replacement, text)
            if text == old:
                break

	# greying out the page headers and footers
	text = re.sub("\n(.+\[Page \w+\])\n\f\n(.+)\n", """\n<span class="grey">\g<1></span>\n\f\n<span class="grey">\g<2></span>\n""", text)

        # contents link markup: section links
        #                   1    2   3        4        5        6         7
        text = re.sub("(?m)^(\s*)(\d+(\.\d+)*)(\.?[ ]+)(.*[^ .])( *\. ?\.)(.*[0-9])$", """\g<1><a href="#section-\g<2>">\g<2></a>\g<4>\g<5>\g<6>\g<7>""", text)
        text = re.sub("(?m)^(\s*)(Appendix |)([A-Z](\.\d+)*)(\.?[ ]+)(.*[^ .])( *\. ?\.)(.*[0-9])$", """\g<1><a href="#appendix-\g<3>">\g<2>\g<3></a>\g<5>\g<6>\g<7>\g<8>""", text)

        # page number markup
        multidoc_separator = "========================================================================"
        if re.search(multidoc_separator, text):
            parts = re.split(multidoc_separator, text)
            for i in range(len(parts)):
                parts[i] = re.sub("(?si)(\f)([^\f]*\[Page (\w+)\])", "\g<1><span id=\"%(page)s-\g<3>\" ></span>\g<2>"%{"page": "page-%s"%(i+1)}, parts[i])
                parts[i] = re.sub("(?i)(\. ?\. +|\. \. \.|\.\.\. *)([0-9ivxlc]+)( *\n)", "\g<1><a href=\"#%(page)s-\g<2>\">\g<2></a>\g<3>"%{"page": "page-%s"%(i+1)}, parts[i])
            text = multidoc_separator.join(parts)
        else:
            # page name tag markup
            text = re.sub("(?si)(\f)([^\f]*\[Page (\w+)\])", "\g<1><span id=\"page-\g<3>\" ></span>\g<2>", text)
            # contents link markup: page numbers
            text = re.sub("(?i)(\. ?\. +|\. \. \.|\.\.\. *)([0-9ivxlc]+)( *\n)", "\g<1><a href=\"#page-\g<2>\">\g<2></a>\g<3>", text)

        # section number tag markup
        def section_anchor_replacement(match):
            # exclude TOC entries
            mstring = match.group(0)
            if " \. \. " in mstring or "\.\.\." in mstring:
                return mstring

            level = len(re.findall("[^\.]+", match.group(1)))+1
	    if level > 6:
		level = 6
	    html = """<span class="h%s"><a class=\"selflink\" id=\"section-%s\" href=\"#section-%s\">%s</a>%s</span>""" % (level, match.group(1), match.group(1), match.group(1), match.group(3))
            html = html.replace("\n", """</span>\n<span class="h%s">""" % level)
            return html
                

        text = re.sub("(?im)^(\d+(\.\d+)*)(\.?[ ]+\S.*?(\n +\w+.*)?(  |$))", section_anchor_replacement, text)
	#text = re.sub("(?i)(\n *\n *)(\d+(\.\d+)*)(\.?[ ].*)", section_replacement, text)
	# section number link markup
        text = re.sub("(?i)(section\s)(\d+(\.\d+)*)", "<a href=\"#section-\g<2>\">\g<1>\g<2></a>", text)
        text = re.sub("(?i)(section)\n(\s+)(\d+(\.\d+)*)", "<a href=\"#section-\g<3>\">\g<1></a>\n\g<2><a href=\"#section-\g<3>\">\g<3></a>", text)

        # Special cases for licensing boilerplate
        text = text.replace('<a href="#section-4">Section 4</a>.e of the Trust Legal Provisions',
                            'Section 4.e of the <a href="https://trustee.ietf.org/license-info">Trust Legal Provisions</a>')

        while True:
            old = text
            text = re.sub("(?i)(sections\s(<a.*?>.*?</a>(,\s|\s?-\s?|\sthrough\s|\sor\s|\sto\s|,?\sand\s))*)(\d+(\.\d+)*)", "\g<1><a href=\"#section-\g<4>\">\g<4></a>", text)
            if text == old:
                break

        # appendix number tag markup
        def appendix_replacement(match):
            # exclude TOC entries
            mstring = match.group(0)
            if " \. \. " in mstring or "\.\.\." in mstring:
                return mstring

            txt = match.group(4)
            num = match.group(2).rstrip('.')
            if num != match.group(2):
                txt = "." + txt
            level = len(re.findall("[^\.]+", num))+1
            if level > 6:
                level = 6
            return """<span class="h%s"><a class=\"selflink\" id=\"appendix-%s\" href=\"#appendix-%s\">%s%s</a>%s</span>""" % (level, num, num, match.group(1), num, txt)

        text = re.sub("(?m)^(Appendix |)([A-Z](\.|\.\d+)+)(\.?[ ].*)$", appendix_replacement, text)
	#text = re.sub("(?i)(\n *\n *)(\d+(\.\d+)*)(\.?[ ].*)", appendix_replacement, text)
	# appendix number link markup                          
        text = re.sub(" ([Aa]ppendix\s)([A-Z](\.\d+)*)", " <a href=\"#appendix-\g<2>\">\g<1>\g<2></a>", text)
        text = re.sub(" ([Aa]ppendix)\n(\s+)([A-Z](\.\d+)*)", " <a href=\"#appendix-\g<3>\">\g<1></a>\n\g<2><a href=\"#appendix-\g<3>\">\g<3></a>", text)

#        # section x of draft-y markup
#        text = re.sub("(?i)<a href=\"[^\"]*\">(section)\s(\d+(\.\d+)*)</a>(\.?\s+(of|in)\s+)<a href=\"[^\"]*\">(draft-[-.a-zA-Z0-9]+[a-zA-Z0-9])</a>", "<a href=\"%s?%surl=%s/rfc\g<7>.txt#section-\g<2>\">\g<1>&nbsp;\g<2>\g<4>\g<6>\g<7></a>" % (script, extra, rfcs), text)
#        # draft-y, section x markup
#        text = re.sub("(?i)<a href=\"[^\"]*\">(draft-[-.a-zA-Z0-9]+[a-zA-Z0-9])</a>(,?\s)<a href=\"[^\"]*\">(section)\s(\d+(\.\d+)*)</a>", "<a href=\"%s?%surl=%s/rfc\g<2>.txt#section-\g<5>\">\g<1>\g<2>\g<3>\g<4>&nbsp;\g<5></a>" % (script, extra, rfcs), text)
#        # [draft-y], section x markup
#        text = re.sub("(?i)\[<a href=\"[^>\"]+\">(draft-[-.a-zA-Z0-9]+[a-zA-Z0-9])</a>\](,?\s)<a href=\"[^>\"]*\">(section)\s(\d+(\.\d+)*)</a>", "<a href=\"%s?%surl=%s/rfc\g<2>.txt#section-\g<5>\">[\g<1>\g<2>]\g<3>\g<4>&nbsp;\g<5></a>" % (script, extra, rfcs), text)

        for n in ['rfc', 'bcp', 'fyi', 'std']:
            # section x of rfc y markup
            text = re.sub("(?i)<a href=\"([^\"]*)\"[^>]*>(section)\s(\d+(\.\d+)*)</a>(\.?\s+(of|in)\s+)<a href=\"([^\"]*)\"[^>]*>(%s[- ]?)([0-9]+)</a>"%n,
                "<a href=\"%s?%s%s=\g<9>\g<1>\">\g<2>&nbsp;\g<3>\g<5>\g<8>\g<9></a>" % (script, extra, n), text)
            text = re.sub("(?i)<a href=\"([^\"]*)\"[^>]*>(section)</a>(\n\s+)<a href=\"(?:[^\"]*)\"[^>]*>(\d+(\.\d+)*)</a>(\.?\s+(of|in)\s+)<a href=\"([^\"]*)\"[^>]*>(%s[- ]?)([0-9]+)</a>"%n,
                "<a href=\"%s?%s%s=\g<10>\g<1>\">\g<2></a>\g<3><a href=\"%s?%s%s=\g<10>\g<1>\">\g<4>\g<6>\g<9>\g<10></a>" % (script, extra, n, script, extra, n), text)
            # appendix x of rfc y markup
            text = re.sub("(?i)<a href=\"([^\"]*)\"[^>]*>(appendix)\s([A-Z](\.\d+)*)</a>(\.?\s+(of|in)\s+)<a href=\"([^\"]*)\"[^>]*>(%s[- ]?)([0-9]+)</a>"%n,
                "<a href=\"%s?%s%s=\g<9>\g<1>\">\g<2>&nbsp;\g<3>\g<5>\g<8>\g<9></a>" % (script, extra, n), text)
            text = re.sub("(?i)<a href=\"([^\"]*)\"[^>]*>(appendix)</a>(\n\s+)<a href=\"(?:[^\"]*)\"[^>]*>([A-Z]+(\.\d+)*)</a>(\.?\s+(of|in)\s+)<a href=\"([^\"]*)\"[^>]*>(%s[- ]?)([0-9]+)</a>"%n,
                "<a href=\"%s?%s%s=\g<10>\g<1>\">\g<2></a>\g<3><a href=\"%s?%s%s=\g<10>\g<1>\">\g<4>\g<6>\g<9>\g<10></a>" % (script, extra, n, script, extra, n), text)

            # rfc y, section x markup
            text = re.sub("(?i)<a href=\"([^\"]*)\"[^>]*>(%s[- ]?)([0-9]+)</a>(,?\s+)<a href=\"([^\"]*)\"[^>]*>(section)\s?(([^<]*))</a>"%n,
                "<a href=\"%s?%s%s=\g<3>\g<5>\">\g<2>\g<3>\g<4>\g<6>&nbsp;\g<7></a>" % (script, extra, n), text)
            # rfc y, appendix x markup
            text = re.sub("(?i)<a href=\"([^\"]*)\"[^>]*>(%s[- ]?)([0-9]+)</a>(,?\s+)<a href=\"([^\"]*)\"[^>]*>(appendix)\s?(([^<]*))</a>"%n,
                "<a href=\"%s?%s%s=\g<3>\g<5>\">\g<2>\g<3>\g<4>\g<6>&nbsp;\g<7></a>" % (script, extra, n), text)

            # section x of? [rfc y] markup
            text = re.sub("(?i)<a href=\"([^\"]*)\"[^>]*>(section)\s(\d+(\.\d+)*)</a>(\.?\s+(of\s+|in\s+)?)\[<a href=\"([^\"]*)\"[^>]*>(%s[- ]?)([0-9]+)</a>\]"%n,
                "<a href=\"%s?%s%s=\g<9>\g<1>\">\g<2>&nbsp;\g<3>\g<5>[\g<8>\g<9>]</a>" % (script, extra, n), text)
            text = re.sub("(?i)<a href=\"([^\"]*)\"[^>]*>(section)</a>(\n\s+)<a href=\"(?:[^\"]*)\"[^>]*>(\d+(\.\d+)*)</a>(\.?\s+(of\s+|in\s+)?)\[<a href=\"([^\"]*)\"[^>]*>(%s[- ]?)([0-9]+)</a>\]"%n,
                "<a href=\"%s?%s%s=\g<10>\g<1>\">\g<2></a>\g<3><a href=\"%s?%s%s=\g<10>\g<1>\">\g<4>\g<6>[\g<9>\g<10>]</a>" % (script, extra, n, script, extra, n), text)
            # appendix x of? [rfc y] markup
            text = re.sub("(?i)<a href=\"([^\"]*)\"[^>]*>(appendix)\s([A-Z](\.\d+)*)</a>(\.?\s+(of\s+|in\s+)?)\[<a href=\"([^\"]*)\"[^>]*>(%s[- ]?)([0-9]+)</a>\]"%n,
                "<a href=\"%s?%s%s=\g<9>\g<1>\">\g<2>&nbsp;\g<3>\g<5>[\g<8>\g<9>]</a>" % (script, extra, n), text)
            text = re.sub("(?i)<a href=\"([^\"]*)\"[^>]*>(appendix)</a>(\n\s+)<a href=\"(?:[^\"]*)\"[^>]*>([A-Z](\.\d+)*)</a>(\.?\s+(of\s+|in\s+)?)\[<a href=\"([^\"]*)\"[^>]*>(%s[- ]?)([0-9]+)</a>\]"%n,
                "<a href=\"%s?%s%s=\g<10>\g<1>\">\g<2></a>\g<3><a href=\"%s?%s%s=\g<10>\g<1>\">\g<4>\g<6>[\g<9>\g<10>]</a>" % (script, extra, n, script, extra, n), text)

            # [rfc y], section x markup
            text = re.sub("(?i)\[<a href=\"([^>\"]+)\"[^>]*>(%s[- ]?)([0-9]+)</a>\](,?\s+)<a href=\"([^>\"]*)\"[^>]*>(section)\s(\d+(\.\d+)*)</a>"%n,
                "<a href=\"%s?%s%s=\g<3>\g<5>\">[\g<2>\g<3>]\g<4>\g<6>&nbsp;\g<7></a>" % (script, extra, n), text)
            # [rfc y], appendix x markup
            text = re.sub("(?i)\[<a href=\"([^>\"]+)\"[^>]*>(%s[- ]?)([0-9]+)</a>\](,?\s+)<a href=\"([^>\"]*)\"[^>]*>(appendix)\s([A-Z](\.\d+)*)</a>"%n,
                "<a href=\"%s?%s%s=\g<3>\g<5>\">[\g<2>\g<3>]\g<4>\g<6>&nbsp;\g<7></a>" % (script, extra, n), text)


        # remove section link for section x.x (of|in) <something else>
        old = text
	text = re.sub("(?i)<a href=\"[^\"]*\"[^>]*>(section\s)(\d+(\.\d+)*)</a>(\.?[a-z]*\s+(of|in)\s+)(\[?)<a href=\"([^\"]*)\"([^>]*)>(.*)</a>(\]?)",
            '\g<1>\g<2>\g<4>\g<6><a href="\g<7>"\g<8>>\g<9></a>\g<10>', text)
	text = re.sub('(?i)(\[?)<a href="([^"]*#ref[^"]*)"([^>]*)>(.*?)</a>(\]?,\s+)<a href="[^"]*"[^>]*>(section\s)(\d+(\.\d+)*)</a>',
            '\g<1><a href="\g<2>"\g<3>>\g<4></a>\g<5>\g<6>\g<7>', text)

        # Special fix for referring to the trust legal provisons in
        # boilerplate text:
	text = re.sub("(?i)<a href=\"[^\"]*\"[^>]*>(section\s)(\d+(\.\d+)*)</a>(\.?[a-z]*\s+(of|in)\s*\n\s*the Trust Legal Provisions)",
            '\g<1>\g<2>\g<4>', text)

	#
        #text = re.sub("\f", "<div class=\"newpage\" />", text)
        text = re.sub("\n?\f\n?", "</pre>\n<hr class='noprint'/><!--NewPage--><pre class='newpage'>", text)

        # restore indentation
        if prefixlen:
            text = re.sub("\n", "\n"+(" "*prefixlen), text)

	if path:
	    text = re.sub("%s\?(rfc|bcp|std)=" % script, "%s/\g<1>" % path, text)
	    text = re.sub("%s\?draft=" % script, "%s/" % path, text)

        return text
