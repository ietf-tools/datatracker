#!/usr/bin/env python

# Add html markup for syntax coloring of YANG modules, or documents
# which contain YANG modules.
#
# Works on the syntax level and does thus not include any intelligent
# links or anything.
import sys
import argparse
from xml.sax.saxutils import escape

import pyang
import pyang.syntax


usage = """%(prog)s [-o OUTFILE] [-d] [-c] [filename]

Add html markup for syntax coloring of YANG modules, or documents
which contain YANG modules.

Reads a YANG module from <filename> or if no <filename> is given,
reads from stdin.  The YANG module is formatted as html.

If the option -d is given, the input contains an html document.  Everything
in a 'pre' element with the 'yang' class is converted.

  <pre class="yang">
  unformatted yang module
  </pre>
"""
def run():
    parser = argparse.ArgumentParser(usage=usage)
    parser.version = '%(prog)s ' + pyang.__version__

    parser.add_argument("file", metavar="filename", action="store", nargs='?',
                   help="Read a YANG module from filename or stdin.")

    parser.add_argument("-v", "--version", action="version",
                   help="Show version number and exit")

    parser.add_argument("-o", "--output", dest="outfile",
                   help="Write the output to OUTFILE instead of stdout.")

    parser.add_argument("-d", dest="scan_document", action="store_true",
                   help="Add markup to an existing html document")

    parser.add_argument("-c", dest="emit_css", action="store_true",
                   help="Add html markup for syntax coloring of YANG modules, or documents,"
                        "which contain YANG modules.")

    args = parser.parse_args()

    if args.file is None:
        # read the entire doc into buf
        buf = ""
        for line in sys.stdin:
            buf = buf + line
    else:
        filename = args.file
        try:
            fd = open(filename)
            buf = fd.read()
        except IOError as ex:
            sys.stderr.write("error %s: %s\n" % (filename, ex))
            sys.exit(1)

    if args.outfile is None:
        fd = sys.stdout
    else:
        fd = open(args.outfile, "w+")

    def emit_css():
        fd.write("""
<style type="text/css" media="all">
pre.yang {
  border: thin solid black;
  background-color: #eeeeee;
  color: black;
  margin: 10px 10px 10px 10px;
  padding: 10px 10px 10px 10px;
  line-height: 1.2em;
}
span.kw {
  color: blue;
}
span.cmt {
  color: red;
}
span.str {
  color: green;
}
</style>
    """)

    i = 0
    q = None
    keyword_next = True
    begin_yang = '<pre class="yang">'

    if args.scan_document:
        no_yang = True
    else:
        no_yang = False
        if args.emit_css:
            args.emit_css = False
            emit_css()
        fd.write(begin_yang)

    while i < len(buf):
        if no_yang and buf[i:].startswith(begin_yang):
            no_yang = False
            fd.write(buf[:i])
            if args.emit_css:
                args.emit_css = False
                emit_css()
            fd.write(begin_yang)
            buf = buf[i+len(begin_yang):]
            i = 0
            continue
        elif no_yang:
            i = i + 1
            continue
        elif not no_yang and buf[i:].startswith('</pre>'):
            no_yang = True
            continue
        if q == '"' and buf[i] == '\\':
            i = i + 2
            continue
        if q is not None and buf[i] == q:
            fd.write("<span class='str'>")
            fd.write(q)
            fd.write(escape(buf[:i+1]))
            fd.write("</span>")
            buf = buf[i+1:]
            q = None
            i = 0
        elif q is not None:
            i = i + 1
            continue
        if buf[i] == '/' and buf[i+1] == '/':
            end = buf.find("\n", i)
            if end == -1:
                end = len(buf)
            fd.write(buf[:i])
            fd.write("<span class='cmt'>")
            fd.write(escape(buf[i:end]))
            fd.write("</span>\n")
            buf = buf[end+1:]
            i = 0
        elif buf[i] == '/' and buf[i+1] == '*':
            end = buf.find("*/", i)
            if end == -1:
                end = len(buf)
            fd.write(buf[:i])
            fd.write("<span class='cmt'>")
            fd.write(escape(buf[i:end]))
            fd.write("*/</span>")
            buf = buf[end+2:]
            i = 0
        elif buf[i] == '"':
            fd.write(buf[:i])
            q = '"'
            buf = buf[i+1:]
            i = 0
        elif buf[i] == "'":
            fd.write(buf[:i])
            q = "'"
            buf = buf[i+1:]
            i = 0
        elif buf[i].isspace():
            i = i + 1
        elif keyword_next:
            m = pyang.syntax.re_keyword.match(buf, i)
            if m is not None:
                kw = m.group()
                if kw in pyang.syntax.yin_map:
                    fd.write(buf[:i])
                    fd.write("<span class='kw'>" + kw + "</span>")
                    buf = buf[i+len(kw):]
                    i = 0
                    keyword_next = False
                    continue
            i = i + 1
        elif buf[i] in ['{', '}', ';']:
            keyword_next = True
            i = i + 1
        else:
            i = i + 1

    fd.write(buf)

    if not args.scan_document:
        fd.write('</pre>\n')

if __name__ == "__main__":
    run()
