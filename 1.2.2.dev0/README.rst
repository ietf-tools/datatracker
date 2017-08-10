Internet-Draft text to XML Conversion Tool
==========================================

This tool, 'id2xml', is intended for use by the RFC-Editor staff, in order to
produce a first xml2rfc-compatible XML version from text-only Internet-Draft
submissions.

id2xml may also be useful for Internet-Draft authors who wish to start working
on a new version of an older draft or RFC, for which no xml2rfc-compatible XML
source is available.

Version 1.0.x can process the drafts specified in the development Statement of
Work to XML files acceptable to xml2rfc, and can also process a number of
other test files to acceptable XML.  Missing is internal <xref/> links to
figures and tables.

The XML produced follows RFC 7749 [1]_ in version 1.x of the tool, and will
follow RFC 7991 [2]_ in version 2.x, which will be released once support is
available to process XML sources which follows the RFC 7991 vocabulary.


.. [1] Reschke, J., "The "xml2rfc" Version 2 Vocabulary", RFC 7749, DOI
   10.17487/RFC7749, February 2016, <http://www.rfc-editor.org/info/rfc7749>.

.. [2] Hoffman, P., "The "xml2rfc" Version 3 Vocabulary", RFC 7991, DOI
   10.17487/RFC7991, December 2016, http://www.rfc-editor.org/info/rfc7991>.

