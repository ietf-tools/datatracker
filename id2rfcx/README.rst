
NAME
        id2xml - Convert text format RFCs and Internet-Drafts to .xml format

SYNOPSIS
        id2xml [OPTIONS] ARGS

DESCRIPTION
        id2xml reads text-format RFCs and IETF drafs which are reasonably
        well formatted (i.e., conforms to the text format produced by xml2rfc)
        and tries to generate a reasonably appropriate .xml file following the
        format accepted by xml2rfc, defined in RFC 7749 and its predecessors/
        successors

OPTIONS
        -h, --help                Output this help, then exit
        -2, --v2, --schema-v2     Use v2 (RFC 7749) schema (default)
        -o, --output-file         Set the output file name
        -p, --output-path         Set the output directory name
        -s, --strip-only          Don't convert, only strip headers/footers
        -v, --version             Output version information, then exit
        -V, --verbose             Be (slightly) more verbose

AUTHOR
        Written by Henrik Levkowetz, <henrik@levkowetz.com>

COPYRIGHT
        Copyright (c) 2017, The IETF Trust
        All rights reserved.

        Licenced under the 3-clause BSD license; see the file LICENSE
        for details.

