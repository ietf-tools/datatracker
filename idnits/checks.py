# Copyright 2018-2019 IETF Trust, All Rights Reserved
# -*- coding: utf-8 indent-with-tabs: 0 -*-

from __future__ import unicode_literals, print_function, division

import lxml
import re
import sys

from collections import namedtuple
from idnits import default_options
from idnits.utils import normalize_paragraph
from xml2rfc.boilerplate_tlp import boilerplate_tlp
from xml2rfc.writers.base import deprecated_element_tags
from xml2rfc.writers.preptool import PrepToolWriter

try:
    import debug
    debug.debug = True
except ImportError:
    debug = None
    pass


Check = namedtuple('Check', [ 'fmt', 'type', 'norm', 'easy', 'subm', 'func', ])
Nit   = namedtuple('Nit',   [ 'num', 'msg', ])

tlp_keys = [ (float(k), k) for k in boilerplate_tlp.keys() ]
tlp_keys.sort()
latest = tlp_keys[-1][1]
tlp = boilerplate_tlp[latest]

bplist = [ tlp[i][p] for i in tlp for p in range(len(tlp[i])) ]
bpkeys = set()

for i in range(len(bplist)):
    para = bplist[i]
    para = normalize_paragraph(para)
    key  = para[:14]
    para = re.sub(r'([(|).*+])', r'\\\1', para)
    para = para.format(
            year='(19\d\d|20\d\d)',
            scheme='(http|https)',
            )
    bplist[i] = para
    bpkeys.add(key)

def plural(l):
    n = len(l)
    return n, ('' if n==1 else 's')

def nit(nits, e, s):
    nits.append(Nit(e.sourceline, s))

class Checker(PrepToolWriter):
    # We subclass PrepToolWriter in order to use the checks it provides.  Have to override
    # .warn(), .err() and .die().

    def __init__(self, doc, options=default_options):
        if hasattr(doc, 'xmlrfc'):
            super(Checker, self).__init__(doc.xmlrfc)
        self.doc = doc
        self.options = options
        self.nits = dict(err=[], warn=[], comm=[])
        self.tmpnits = []
        #

    def get_checks(self):
        checks = self.checks
        fmt = 'xml' if self.doc.type in ['application/xml', 'text/xml', ] else 'txt' if self.doc.type in ['text/plain', ] else None
        if fmt is None:
            self.nits['err'].append(([Nit(None,"Found input type %s" % self.doc.type)], "Input type text or xml is required"))
            return []
        checks = [ c for c in checks if c.fmt in ['any', fmt] ]
        type = 'rfc' if self.doc.name.startswith('rfc') or self.doc.root != None and self.doc.root.get('number') != None else 'ids'
        checks = [ c for c in checks if c.type in ['any', type] ]
        if   self.options.mode == 'normal':
            checks = [ c for c in checks if c.norm != 'none' ]
        elif self.options.mode == 'lenient':
            checks = [ c for c in checks if c.easy != 'none' ]
        elif self.options.mode == 'submission':
            checks = [ c for c in checks if c.subm != 'none' ]
        else:
            raise RuntimeError("Internal error: Unexpected mode: %s" % self.options.mode)
        return checks

    def warn(self, e, text):
        self.tmpnits.append(Nit(e.sourceline, text))
    err = warn
    die = warn

    def check(self):
        mode = self.options.mode
        checks = self.get_checks()
        blank  = 0
        done   = 0

        if any([ c.fmt == 'xml' for c in checks]) and self.doc.root != None:
            ver = self.doc.root.get('version')
            if ver != '3':
                self.nits['err'].append(([Nit(self.doc.root.sourceline, 'Expected <rfc ... version="3" ...>, found %s'%ver),], "For xml checks, version 3 is required"))
                self.doc.root = None

        for check in checks:
            severity = check.norm if mode == 'normal' else check.easy if mode == 'lenient' else check.subm
            if check.fmt == 'xml' and not self.doc.root != None:
                continue
            res = check.func(self)
            if res is None:
                blank += 1
            else:
                done  += 1
                assert len(res) == 2
                nits, msg = res
                if nits:
                    self.nits[severity].append((nits, msg))

        if blank:
            pass
            #sys.stdout.write("Checks: ran %d, %d unimplemented\n" % (done, blank))
        return self.nits


    def any_text_has_control_char(self):
        # Control characters other than CR, NL, or FF appear (0x01-0x09,0x0b,0x0e-0x1f) 
        nits = []
        for l in self.doc.lines:
            match = re.search(r'[\x01-\x09\x0b\x0e-\x1f]', l.txt)
            if match:
                nits.append(Nit(l.num, "Found control character 0x%02x in column %d" % (ord(match.group()), match.start(), )))
        return nits, "Found %s line%s with control characters" % plural(nits)
        
    def any_text_has_invalid_utf8(self):
        # Byte sequences that are not valid UTF-8 appear 
        nits = []
        if not self.doc.encoding in ['ascii', 'us-ascii', 'utf-8', ]:
            for num, txt in enumerate(self.doc.raw.splitlines()):
                try:
                    txt.decode('utf-8')
                except UnicodeDecodeError as e:
                    code = ord(e.args[1][e.start])
                    nits.append(Nit(num, "Invalid UTF-8 characters starting in column %d: 0x%x" % (e.start, code)))
        return nits, "File encoding is not utf-8 (seems to be %s)" % self.doc.encoding

    def any_text_has_nonascii_char(self):
        # Non-ASCII UTF-8 appear (comment will point to guidance in draft-iab-rfc-nonascii or
        # its successor) 
        nits = []
        if not self.doc.encoding in ['ascii', 'us-ascii', ]:
            if self.doc.encoding in ['utf-8', ]:
                for num, txt in enumerate(self.doc.raw.splitlines()):
                    try:
                        txt.decode('ascii')
                    except UnicodeDecodeError as e:
                        code = ord(e.args[1][e.start])
                        nits.append(Nit(num, "Non-ASCII characters starting in column %d: 0x%x" % (e.start, code)))
        return nits, "Found %s line%s with non-ASCII characters" % plural(nits)

    def any_abstract_missing(self):
        # Missing Abstract section 
        nits = []

    def any_introduction_missing(self):
        # Missing Introduction section 
        nits = []

    def any_security_considerations_missing(self):
        # Missing Security Considerations section 
        nits = []

    def any_author_address_missing(self):
        # Missing Author Address section 
        nits = []

    def any_references_no_category(self):
        # References (if any present) are not categorized as Normative or Informative 
        nits = []

    def any_abstract_with_reference(self):
        # Abstract contains references 
        nits = []

    def any_fqdn_not_example(self):
        # FQDN appears (other than www.ietf.org) not meeting RFC2606/RFC6761 recommendations 
        nits = []

    def any_ipv4_private_not_example(self):
        # Private IPv4 address appears that doesn't meet RFC5735 recommendations 
        nits = []

    def any_ipv4_multicast_not_example(self):
        # Multicast IPv4 address appears that doesn't meet RFC5771/RFC6676 recommendations 
        nits = []

    def any_ipv4_generic_not_example(self):
        # Other IPv4 address appears that doesn't meet RFC5735 recommendations 
        nits = []

    def any_ipv6_local_not_example(self):
        # Unique Local IPv6 address appears that doesn't meet RFC3849/RFC4291 recommendations 
        nits = []

    def any_ipv6_link_not_example(self):
        # Link Local IPv6 address appears that doesn't meet RFC3849/RFC4291 recommendations 
        nits = []

    def any_ipv6_generic_not_example(self):
        # Other IPv6 address appears that doesn't meet RFC3849/RFC4291 recommendations 
        nits = []

    def any_text_code_comment(self):
        # A possible code comment is detected outside of a marked code block 
        nits = []

    def any_rfc2119_info_missing(self):
        # 2119 keywords occur, but neither the matching boilerplate nor a reference to 2119 is
        # missing 
        nits = []

    def any_rfc2119_boilerplate_missing(self):
        # 2119 keywords occur, a reference to 2119 exists, but matching boilerplate is missing 
        nits = []

    def any_rfc2119_boilerplate_extra(self):
        # 2119 boilerplate is present, but document doesn't use 2119 keywords 
        nits = []

    def any_rfc2119_bad_keyword_combo(self):
        # badly formed combination of 2119 words occurs (MUST not, SHALL not, SHOULD not, not
        # RECOMMENDED, MAY NOT, NOT REQUIRED, NOT OPTIONAL) 
        nits = []

    def any_rfc2119_boilerplate_lookalike(self):
        # text similar to 2119 boilerplate occurs, but doesn't reference 2119 
        nits = []

    def any_rfc2119_keyword_lookalike(self):
        # NOT RECOMMENDED appears, but is not included in 2119-like boilerplate 
        nits = []

    def any_abstract_update_info_missing(self):
        # Abstract doesn't directly state it updates or obsoletes each document so affected
        # (Additional comment if Abstract mentions the document some other way) 
        nits = []

    def any_abstract_update_info_extra(self):
        # Abstract states it updates or obsoletes a document not declared in the relevant field
        # previously 
        nits = []

    def any_authors_addresss_grammar(self):
        # Author's address section title misuses possessive mark or uses a character other than
        # a single quote 
        nits = []

    def any_reference_not_used(self):
        # a reference is declared, but not used in the document 
        nits = []

    def any_reference_is_downref(self):
        # a reference appears to be a downref (noting if reference appears in the downref
        # registry) 
        nits = []

    def any_reference_status_unknown(self):
        # a normative reference to an document of unknown status appears (possible downref) 
        nits = []

    def any_reference_is_obsolete_norm(self):
        # a normative or unclassified reference is to an obsolete document 
        nits = []

    def any_reference_is_obsolete_info(self):
        # an informative reference is to an obsolete document 
        nits = []

    def any_reference_is_draft_rfc(self):
        # a reference is to a draft that has already been published as an rfc 
        nits = []

    def any_sourcecode_no_license(self):
        # A code-block is detected, but the block does not contain a license declaration 
        nits = []

    def any_filename_base_bad_characters(self):
        # filename's base name contains characters other than digits, lowercase alpha, and dash 
        nits = []

    def any_filename_ext_mismatch(self):
        # filename's extension doesn't match format type (.txt, .xml) 
        nits = []

    def any_filename_base_not_docname_(self):
        # filename's base name doesn't match the name declared in the document 
        nits = []

    def any_filename_too_long(self):
        # filename (including extension) is more than 50 characters 
        nits = []

    def any_obsoletes_obsolete_rfc(self):
        # Document claims to obsolete an RFC that is already obsolete 
        nits = []

    def any_updates_obsolete_rfc(self):
        # Document claims to update an RFC that is obsolete 
        nits = []

    def any_doc_status_info_bad(self):
        # Document's status or intended status is not found or not recognized 
        nits = []

    def any_doc_date_bad(self):
        # Document's date can't be determined or is too far in the past or the future (see
        # existing implementation for "too far") 
        nits = []

    def any_section_iana_missing(self):
        # Missing IANA considerations section 
        nits = []

    def any_docname_malformed(self):
        # filename's base name doesn't begin with 'draft', contains two consecutive hyphens, or
        # doesn't have enough structure to contain the individual or stream, potentially a wg name, and
        # a distinguishing name. (draft-example-00 is an error, but draft-example-filename is
        # acceptable) 
        nits = []

    def any_section_iana_missing(self):
        # Missing IANA considerations section 
        nits = []

    def any_doc_rev_unexpected(self):
        # version of document is unexpected (already exists, or leaves a gap) 
        nits = []

    def xml_element_deprecated(self):
        # any deprecated elements or attributes appear 
        nits = []
        for e in self.doc.root.iter(*list(deprecated_element_tags)):
            nits.append(Nit(e.sourceline, "Deprecated element: %s" % e.tag))
        return nits, "Found %s deprecated xml element%s" % plural(nits)

    def xml_stream_contradiction(self):
        # metadata and document's 'submissionType' attribute state different streams 
        self.tmpnits = []
        self.check_series_and_submission_type(self.doc.root, None)
        return self.tmpnits, "Found inconsistent stream settings"

    def xml_source_code_in_sourcecode(self):
        # The text inside a <sourcecode> tag contains the string '<CODE BEGINS>' (Warn that the
        # string is unnecessary and may duplicate what a presentation format converter will produce.) 
        nits = []
        for e in self.doc.root.iter('sourcecode'):
            if e.text and ('<CODE BEGINS>' in e.text) and (e.get('markers')=='true'):
                nits.append(Nit(e.sourceline, 'Found "<SOURCE BEGINS>" in <sourcecode> element with markers="true"'))
        return nits, 'Found %s instance%s of "<SOURCE BEGINS>" in <sourcecode> which will cause duplicate markers in the output' % plural(nits)

    def xml_source_code_in_text(self):
        # The text inside any other tag contains the string '<CODE BEGINS>' (Warn that if the
        # text is a code block, it should appear in a <sourcecode> element) 
        nits = []
        for e in self.doc.root.iter('t'):
            text = ' '.join(e.itertext())
            if text and ('<CODE BEGINS>' in text):
                nits.append(Nit(e.sourceline, 'Found "<SOURCE BEGINS>" in text'))
        return nits, 'Found %s instance%s of "<SOURCE BEGINS>" in text.  If this is the start of a code block, it should be put in a <sourcecode> element' % plural(nits)

    def xml_text_looks_like_ref(self):
        # text occurs that looks like a text-document reference (e.g. [1], or [RFC...])  (if the
        # text was really a reference it should be in an <xref> tag) 
        nits = []
        ref_format = r"\[(([0-9A-Z]|I-?D.)[0-9A-Za-z-]*( [0-9A-Z-]+)?|(IEEE|ieee)[A-Za-z0-9.-]+|(ITU ?|ITU-T ?|G\\.)[A-Za-z0-9.-]+)\]"
        tags = list(self.text_tags - set(['sourcecode', 'artwork', ]))
        for e in self.doc.root.iter(tags):
            text = ' '.join([ t for t in [e.text, e.tail] if t and t.strip() ])
            match = re.search(ref_format, text)
            if match:
                nits.append(Nit(e.sourceline, "Found text that looks like a citation: %s" % match.group(0)))
        return nits, "Found %s instance%s of text that looks like a citation and maybe should use <xref> instead" % plural(nits)

    def xml_ipr_attrib_missing(self):
        # <rfc> ipr attribute is missing or not recognized 
        nits = []
        ipr = self.doc.root.get('ipr')
        if ipr is None:
            nits.append(Nit(self.doc.root.sourceline, "Expected an ipr attribute on <rfc>, but found none"))
        return nits, "Found no ipr attribute on <rfc>"

    def xml_ipr_attrib_unknown(self):
        # ipr attribute is not one of "trust200902", "noModificationTrust200902",
        # "noDerivativesTrust200902", or "pre5378Trust200902" 
        nits = []
        supported_ipr = [
            'trust200902',
            'noModificationTrust200902',
            'noDerivativesTrust200902',
            'pre5378Trust200902',
        ]
        ipr = self.doc.root.get('ipr')
        if not ipr in supported_ipr:
            nits.append(Nit(self.doc.root.sourceline, "Found an unrecognized ipr attribute on <rfc>: %s" % ipr))
        return nits, "Found an unrecognized ipr attribute: %s" % ipr

    def xml_ipr_attrib_disallowed(self):
        # document is ietf stream and ipr attribute is one of "noModificationTrust200902" or
        # "noDerivativesTrust200902" 
        nits = []
        disallowed_ipr = [
            'noModificationTrust200902',
            'noDerivativesTrust200902',
        ]
        ipr = self.doc.root.get('ipr')
        stream = self.doc.root.get('submissionType', 'IETF')
        if stream=='IETF' and ipr in disallowed_ipr:
            nits.append(Nit(self.doc.root.sourceline, "Found a disallowed ipr attribute: %s" % ipr))
        return nits, "Found a disallowed ipr attribute for stream IETF: %s" % ipr

    def xml_workgroup_not_group(self):
        # <workgroup> content doesn't end with "Group" 
        nits = []
        e = self.doc.root.find('./front/workgroup')
        wg = ''
        if e != None:
            wg = e.text.strip()
            if not wg.endswith('Group'):
                nits.append(Nit(e.sourceline, "Expected a <workgroup> entry ending in 'Group', but found '%s'" % wg))
        return nits, "Found a bad <workgroup> value: %s" % wg

    def xml_update_info_bad(self):
        # The "obsoletes" or "updates" attribute values of the <rfc> element are not comma
        # separated strings of digits 
        nits = []
        for a in 'obsoletes', 'updates':
            l = self.doc.root.get(a)
            if l and l.strip():
                nums = [ n.strip() for n in l.split(',') ]


        return nits, "Found malformed updates / obsoletes information"

    def xml_update_info_noref(self):
        # The rfcs indicated by the "obsoletes" and "updates" attribute values of the <rfc>
        # element are not included in the references section 
        nits = []
        for a in 'obsoletes', 'updates':
            l = self.doc.root.get(a)
            if l and l.strip():
                nums = [ n.strip() for n in l.split(',') if n.strip().isdigit() ]
                for num in nums:
                    ref = self.doc.root.find('./back/references//reference/seriesInfo[@name="RFC"][@value="%s"]' % num)
                    debug.show('ref')
                    if ref is None:
                        nits.append(Nit(self.doc.root.sourceline,
                            "Did not find RFC %s, listed in '%s', in the references" %(num, a)))
        return nits, "Found updates / obsoletes RFC numbers not included in a References section"

    def xml_xref_target_missing(self):
        # <xref> has no target attribute 
        nits = []
        for e in self.doc.root.xpath('.//xref'):
            if not e.get('target'):
                nits.append(Nit(e.sourceline, "Found <xref> without a target attribute: %s" % lxml.etree.tostring(e)))
        return nits, "Found %s instance%s of <xref> with no target" % plural(nits)

    def xml_xref_target_not_anchor(self):
        # <xref> target attribute does not appear as an anchor of another element 
        nits = []
        for e in self.doc.root.xpath('.//xref[@target]'):
            target = e.get('target')
            t = self.doc.root.find('.//*[@anchor="%s"]' % target)
            if t is None:
                t = self.doc.root.find('.//*[@pn="%s"]' % target)
                if t is None:
                    t = self.doc.root.find('.//*[@slugifiedName="%s"]' % target)
            if t is None:
                nits.append(Nit(e.sourceline, "Found <xref> with a target without matching anchor: %s" % lxml.etree.tostring(e)))
        return nits, "Found %s instance%s of <xref> with unmatched target" % plural(nits)


    def xml_relref_target_missing(self):
        # <relref> has no target attribute 
        nits = []
        for e in self.doc.root.xpath('.//relref'):
            if not e.get('target'):
                nits.append(Nit(e.sourceline, "Found <relref> without a target attribute: %s" % lxml.etree.tostring(e)))
        return nits, "Found %s instance%s of <relref> with no target" % plural(nits)

    def xml_relref_target_not_anchor(self):
        # <relref> target attribute does not appear as an anchor of a <reference> element 
        nits = []
        for e in self.doc.root.xpath('.//relref[@target]'):
            target = e.get('target')
            t = self.doc.root.find('./back//reference[@anchor="%s"]' % target)
            if t is None:
                nits.append(Nit(e.sourceline, "Found <relref> with a target that is not a <reference>: %s" % lxml.etree.tostring(e)))
        return nits, "Found %s instance%s of <relref> bad target" % plural(nits)

    def xml_relref_target_no_target(self):
        # A <reference> element pointed to by a <relref> target attribute does not itself have a
        # target attribute 
        nits = []
        for e in self.doc.root.xpath('.//relref[@target]'):
            target = e.get('target')
            t = self.doc.root.find('./back//reference[@anchor="%s"]' % target)
            if t != None:
                ttarget = t.get('target')
                if not (ttarget and ttarget.strip()):
                    nits.append(Nit(t.sourceline,
                        'Found a <relref> target without its own target attribute: <reference anchor="%s"...>' % target))
        return nits, "Found %s instance%s of <relref> target without its own target attribute" % plural(nits)

    def xml_artwork_multiple_content(self):
        # An element (particularly <artwork> or <sourcecode>) contains both a src attribute, and
        # content 
        nits = []

    def xml_element_src_bad_schema(self):
        # The src attribute of an element contains a URI scheme other than data:, file:, http:,
        # or https: 
        nits = []

    def xml_link_has_bad_content(self):
        # <link> exists with DOI or RFC-series ISDN for this document when the document is an
        # <Internet-Draft 
        nits = []

    def xml_section_bad_numbered_false(self):
        # <section> with a numbered attribute of 'false' is not a child of <boilerplate>,
        # <<middle>, or <back>, or has a subsequent <section> sibling with a numbered attribute of
        # <'true' 
        nits = []

    def xml_xref_counter_bad_target(self):
        # An <xref> element with no content and a 'format' attribute of 'counter' has a 'target'
        # attribute whose value is not a section, figure, table or ordered list number 
        nits = []

    def xml_relref_target_missing_anchor(self):
        # A <relref> element whose 'target' attribute points to a document in xml2rfcv3 format,
        # and whose 'relative' attribute value (or the derived value from a 'section' attribute) does
        # not appear as an anchor in that document 
        nits = []

    def xml_artwork_svg_wrong_media_type(self):
        # An <artwork> element with type 'svg' has a 'src' attribute with URI scheme 'data:' and
        # the mediatype of the data: URI is not 'image/svg+xml' 
        nits = []

    def xml_sourcecode_multiple_content(self):
        # A <sourcecode> element has both a 'src' attribute and non-empty content 
        nits = []

    def xml_rfc_note_remove_true(self):
        # A <note> element has a 'removeInRFC' attribute with a value of 'true' 
        nits = []

    def xml_rfc_artwork_wrong_type(self):
        # An <artwork> element has type other than 'ascii-art','call-flow','hex-dump', or 'svg' 
        nits = []

    def xml_text_has_boilerplate(self):
        # The text inside any tag sufficiently matches any of the boilerplate in the IETF-TLP-4
        # section 6a-6d (such text should probably be removed and the ipr attribute of the rfc
        # tag should be verified) 
        nits = []
        for t in self.doc.root.xpath('./middle//section//t'):
            text = normalize_paragraph(' '.join(t.itertext()))
            key = text[:14]
            if key in bpkeys:
                for regex in bplist:
                    if re.match(regex, text):
                        nits.append(Nit(getattr(t, 'sourceline'), "Found what looks like a boilerplate paragraph in xml text: %s..." % text[:20]))
        return nits, "Found % cases of what looks like boilerplate in xml <t> element%s; this should be removed" % plural(nits)

    def xml_boilerplate_mismatch(self):
        # The value of the <boilerplate> element, if non-empty, does not match what the ipr,
        # category, submission, and consensus <rfc> attributes would cause to be generated 
        nits = []

    def xml_rfc_generated_attrib_wrong(self):
        # The value of any present pn or slugifiedName attributes do not match what would be
        # regenerated 
        nits = []

    def txt_text_added_whitespace(self):
        # document does not appear to be ragged-right (more than 50 lines of intra-line extra
        # spacing) 
        nits = []

    def txt_text_lines_too_long(self):
        # document contains over-long lines (cut-off is 72 characters. Report longest line, and
        # count of long lines) 
        nits = []

    def txt_text_line_break_hyphens(self):
        # document has hyphenated line-breaks 
        nits = []

    def txt_text_hyphen_space(self):
        # document has a hyphen followed immediately by a space within a line 
        nits = []

    def txt_update_info_extra_text(self):
        # Updates or Obsoletes line on first page has more than just numbers of RFCs (such as
        # the character sequence 'RFC') 
        nits = []

    def txt_update_info_not_in_order(self):
        # Updates or Obsoletes numbers do not appear in ascending order 
        nits = []

    def txt_doc_bad_magic(self):
        # document starts with PK or BM 
        nits = []

    def txt_reference_style_mixed(self):
        # document appears to use numeric references, but contains something that looks like a
        # text-style reference (or vice-versa) 
        nits = []

    def txt_text_ref_unused_(self):
        # a string that looks like a reference appears but does not occur in any reference
        # section 
        nits = []

    def txt_abstract_numbered(self):
        # Abstract section is numbered 
        nits = []

    def txt_status_of_memo_numbered(self):
        # 'Status of this memo' section is numbered 
        nits = []

    def txt_copyright_notice_numbered(self):
        # Copyright Notice section is numbered 
        nits = []

    def txt_boilerplate_copyright_missing(self):
        # TLP-4 6.b.i copyright line is not present 
        nits = []

    def txt_boilerplate_copyright_year_wrong(self):
        # TLP-4 6.b.i copyright date is not this (or command-line specified) year 
        nits = []

    def txt_boilerplate_licence_missing(self):
        # TLP-4 6.b.i or b.ii license notice is not present, or doesn't match stream 
        nits = []

    def txt_boilerplate_restrictions_found(self):
        # IETF stream document sufficiently matches TLP-4 6.c.i or 6.c.ii text (restrictions on
        # publication or derivative works) 
        nits = []

    def txt_boilerplate_copyright_duplicate(self):
        # More than one instance of text sufficiently matching the TLP-4 6.b.i copyright line
        # occurs 
        nits = []

    def txt_boilerplate_licence_duplicate(self):
        # More than one instance of text sufficiently matching either the TLP4 6.b.i or 6.b.ii
        # license notice occurs 
        nits = []

    def txt_boilerplate_pre5378_missing_upd(self):
        # Document obsoletes or updates any pre-5378 document, and doesn't contain the pre-5378
        # material of TLP4 6.c.iii 
        nits = []

    def txt_boilerplate_pre5378_missing_prev(self):
        # Any prior version of the document might be pre-5378 and the document doesn't contain
        # the pre-5378 material of TLP4 6.c.iii 
        nits = []

    def txt_pages_too_long(self):
        # contains over-long pages (report count of pages with more than 58 lines)
        nits = []

    def txt_head_label_missing(self):
        # doesn't say INTERNET DRAFT in the upper left of the first page 
        nits = []

    def txt_head_expiration_missing(self):
        # doesn't have expiration date on first and last page 
        nits = []

    def txt_boilerplate_working_doc_missing(self):
        # doesn't have an acceptable paragraph noting that IDs are working documents 
        nits = []

    def txt_boilerplate_6month_missing(self):
        # doesn't have an acceptable paragraph calling out 6 month validity 
        nits = []

    def txt_boilerplate_current_ids_missing(self):
        # doesn't have an acceptable paragraph pointing to the list of current ids 
        nits = []

    def txt_boilerplate_current_ids_duplicate(self):
        # has multiple occurrences of current id text 
        nits = []

    def txt_head_docname_missing(self):
        # document name doesn't appear on first page 
        nits = []

    def txt_table_of_contents_missing(self):
        # has no Table of Contents 
        nits = []

    def txt_boilerplate_ipr_missing(self):
        # IPR disclosure text (TLP 4.0 6.a) does not appear 
        nits = []

    def txt_boilerplate_ipr_not_first_page(self):
        # IPR disclosure text (TLP 4.0 6.a) appears after first page 
        nits = []

    def txt_pages_missing_formfeed(self):
        # pages are not separated by formfeeds 
        nits = []

    def txt_pages_formfeed_misplaced(self):
        # 'FORMFEED' and '[Page...]' occur on a line, possibly separated by spaces (indicates
        # 'NROFF post-processing wasn't successful) 
        nits = []

    def txt_text_bad_section_indentation(self):
        # section title occurs at an unexpected indentation 
        nits = []

    checks = [

    #3.1 Conditions to check for any input type
    #--------------------------------------

        # fmt    type   norm    easy    subm
        # xml    rfc
        # txt    ids
        Check('any', 'any', 'err',  'warn', 'none', any_text_has_control_char), # Control characters other than CR, NL, or FF appear (0x01-0x09,0x0b,0x0e-0x1f) 
        Check('any', 'any', 'err',  'warn', 'none', any_text_has_invalid_utf8), # Byte sequences that are not valid UTF-8 appear 
        Check('any', 'any', 'comm', 'comm', 'none', any_text_has_nonascii_char), # Non-ASCII UTF-8 appear (comment will point to guidance in draft-iab-rfc-nonascii or its successor) 
        Check('any', 'any', 'err',  'err',  'err',  any_abstract_missing), # Missing Abstract section 
        Check('any', 'any', 'err',  'warn', 'none', any_introduction_missing), # Missing Introduction section 
        Check('any', 'any', 'err',  'warn', 'none', any_security_considerations_missing), # Missing Security Considerations section 
        Check('any', 'any', 'err',  'warn', 'none', any_author_address_missing), # Missing Author Address section 
        Check('any', 'any', 'err',  'warn', 'none', any_references_no_category), # References (if any present) are not categorized as Normative or Informative 
        Check('any', 'any', 'err',  'warn', 'none', any_abstract_with_reference), # Abstract contains references 
        Check('any', 'any', 'warn', 'warn', 'none', any_fqdn_not_example), # FQDN appears (other than www.ietf.org) not meeting RFC2606/RFC6761 recommendations 
        Check('any', 'any', 'warn', 'warn', 'none', any_ipv4_private_not_example), # Private IPv4 address appears that doesn't meet RFC5735 recommendations 
        Check('any', 'any', 'warn', 'warn', 'none', any_ipv4_multicast_not_example), # Multicast IPv4 address appears that doesn't meet RFC5771/RFC6676 recommendations 
        Check('any', 'any', 'warn', 'warn', 'none', any_ipv4_generic_not_example), # Other IPv4 address appears that doesn't meet RFC5735 recommendations 
        Check('any', 'any', 'warn', 'warn', 'none', any_ipv6_local_not_example), # Unique Local IPv6 address appears that doesn't meet RFC3849/RFC4291 recommendations 
        Check('any', 'any', 'warn', 'warn', 'none', any_ipv6_link_not_example), # Link Local IPv6 address appears that doesn't meet RFC3849/RFC4291 recommendations 
        Check('any', 'any', 'warn', 'warn', 'none', any_ipv6_generic_not_example), # Other IPv6 address appears that doesn't meet RFC3849/RFC4291 recommendations 
        Check('any', 'any', 'warn', 'warn', 'warn', any_text_code_comment), # A possible code comment is detected outside of a marked code block 
        Check('any', 'any', 'err',  'warn', 'none', any_rfc2119_info_missing), # 2119 keywords occur, but neither the matching boilerplate nor a reference to 2119 is missing 
        Check('any', 'any', 'warn', 'warn', 'none', any_rfc2119_boilerplate_missing), # 2119 keywords occur, a reference to 2119 exists, but matching boilerplate is missing 
        Check('any', 'any', 'warn', 'warn', 'none', any_rfc2119_boilerplate_extra), # 2119 boilerplate is present, but document doesn't use 2119 keywords 
        Check('any', 'any', 'comm', 'comm', 'none', any_rfc2119_bad_keyword_combo), # badly formed combination of 2119 words occurs (MUST not, SHALL not, SHOULD not, not RECOMMENDED, MAY NOT, NOT REQUIRED, NOT OPTIONAL) 
        Check('any', 'any', 'err',  'err',  'none', any_rfc2119_boilerplate_lookalike), # text similar to 2119 boilerplate occurs, but doesn't reference 2119 
        Check('any', 'any', 'warn', 'warn', 'none', any_rfc2119_keyword_lookalike), # NOT RECOMMENDED appears, but is not included in 2119-like boilerplate 
        Check('any', 'any', 'comm', 'comm', 'none', any_abstract_update_info_missing), # Abstract doesn't directly state it updates or obsoletes each document so affected (Additional comment if Abstract mentions the document some other way) 
        Check('any', 'any', 'comm', 'comm', 'none', any_abstract_update_info_extra), # Abstract states it updates or obsoletes a document not declared in the relevant field previously 
        Check('any', 'any', 'warn', 'warn', 'none', any_authors_addresss_grammar), # Author's address section title misuses possessive mark or uses a character other than a single quote 
        Check('any', 'any', 'warn', 'warn', 'warn', any_reference_not_used), # a reference is declared, but not used in the document 
        Check('any', 'any', 'err',  'warn', 'none', any_reference_is_downref), # a reference appears to be a downref (noting if reference appears in the downref registry) 
        Check('any', 'any', 'comm', 'comm', 'none', any_reference_status_unknown), # a normative reference to an document of unknown status appears (possible downref) 
        Check('any', 'any', 'err',  'warn', 'none', any_reference_is_obsolete_norm), # a normative or unclassified reference is to an obsolete  document 
        Check('any', 'any', 'comm', 'comm', 'none', any_reference_is_obsolete_info), # an informative reference is to an obsolete document 
        Check('any', 'any', 'warn', 'warn', 'none', any_reference_is_draft_rfc), # a reference is to a draft that has already been published as an rfc 
        Check('any', 'any', 'warn', 'warn', 'none', any_sourcecode_no_license), # A code-block is detected, but the block does not contain a license declaration 

    #3.1.1 Filename Checks
    #---------------------

        Check('any', 'any', 'err',  'err',  'err',  any_filename_base_bad_characters), # filename's base name contains characters other than digits, lowercase alpha, and dash 
        Check('any', 'any', 'err',  'err',  'err',  any_filename_ext_mismatch), # filename's extension doesn't match format type (.txt, .xml) 
        Check('any', 'any', 'err',  'err',  'err',  any_filename_base_not_docname_), # filename's base name doesn't match the name declared in the document 
        Check('any', 'any', 'err',  'err',  'err',  any_filename_too_long), # filename (including extension) is more than 50 characters 

    #3.1.2 Metadata checks
    #---------------------

        Check('any', 'any', 'warn', 'warn', 'none', any_obsoletes_obsolete_rfc), # Document claims to obsolete an RFC that is already obsolete 
        Check('any', 'any', 'warn', 'warn', 'none', any_updates_obsolete_rfc), # Document claims to update an RFC that is obsolete 
        Check('any', 'any', 'warn', 'warn', 'warn', any_doc_status_info_bad), # Document's status or intended status is not found or not recognized 
        Check('any', 'any', 'warn', 'warn', 'warn', any_doc_date_bad), # Document's date can't be determined or is too far in the past or the future (see existing implementation for "too far") 

    #3.1.3 If the document is an RFC
    #-------------------------------

        Check('any', 'rfc', 'comm', 'comm', 'none', any_section_iana_missing),  # Missing IANA considerations section 

    #3.1.4 If the document is an Internet-Draft (that is, not an RFC)
    #----------------------------------------------------------------

        Check('any', 'ids', 'err',  'err',  'err',  any_docname_malformed), # filename's base name  doesn't begin with 'draft', contains two consecutive hyphens, or doesn't have enough structure to contain the individual or stream, potentially a wg name, and a distinguishing name. (draft-example-00 is an error, but draft-example-filename is acceptable) 
        Check('any', 'ids', 'err',  'warn', 'none', any_section_iana_missing), # Missing IANA considerations section 

    #3.1.4.1 Additional metadata check
    #---------------------------------

        Check('any', 'ids', 'warn', 'warn', 'warn', any_doc_rev_unexpected), # version of document is unexpected (already exists, or leaves a gap) 

    #3.2 XML Input Specific Conditions
    #---------------------------------

        Check('xml', 'any', 'warn', 'warn', 'warn', xml_element_deprecated), # any deprecated elements or attributes appear 
        Check('xml', 'any', 'err',  'err',  'err',  xml_stream_contradiction), # metadata and document's 'submissionType' attribute state different streams 
        Check('xml', 'any', 'warn', 'warn', 'none', xml_source_code_in_sourcecode), # The text inside a <sourcecode> tag contains the string '<CODE BEGINS>' (Warn that the string is unnecessary and may duplicate what a presentation format converter will produce.) 
        Check('xml', 'any', 'warn', 'warn', 'none', xml_source_code_in_text), # The text inside any other tag contains the string '<CODE BEGINS>' (Warn that if the text is a code block, it should appear in a <sourcecode> element) 
        Check('xml', 'any', 'warn', 'warn', 'none', xml_text_looks_like_ref), # text occurs that looks like a text-document reference (e.g. [1], or [RFC...])  (if the text was really a reference it should be in an <xref> tag) 
        Check('xml', 'any', 'err',  'err',  'err',  xml_ipr_attrib_missing), # <rfc> ipr attribute is missing or not recognized 
        Check('xml', 'any', 'warn', 'warn', 'warn', xml_ipr_attrib_unknown), # ipr attribute is not one of "trust200902", "noModificationTrust200902", "noDerivativesTrust200902", or "pre5378Trust200902" 
        Check('xml', 'any', 'err',  'err',  'err',  xml_ipr_attrib_disallowed), # document is ietf stream and ipr attribute is one of "noModificationTrust200902" or "noDerivativesTrust200902" 
        Check('xml', 'any', 'warn', 'warn', 'warn', xml_workgroup_not_group), # <workgroup> content doesn't end with "Group" 
        Check('xml', 'any', 'err',  'warn', 'err',  xml_update_info_bad),  # The "obsoletes" or "updates" attribute values of the <rfc> element are not comma separated strings of digits 
        Check('xml', 'any', 'err',  'err',  'err',  xml_update_info_noref), # The rfcs indicated by the "obsoletes" and "updates" attribute values of the <rfc> element are not included in the references section 
        Check('xml', 'any', 'err',  'warn', 'err',  xml_xref_target_missing), # <xref> has no target attribute 
        Check('xml', 'any', 'err',  'warn', 'err',  xml_xref_target_not_anchor), # <xref> target attribute does not appear as an anchor of another element 
        Check('xml', 'any', 'err',  'warn', 'err',  xml_relref_target_missing), # <relref> has no target attribute 
        Check('xml', 'any', 'err',  'warn', 'err',  xml_relref_target_not_anchor), # <relref> target attribute does not appear as an anchor of a <reference> element 
        Check('xml', 'any', 'err',  'warn', 'err',  xml_relref_target_no_target), # A <reference> element pointed to by a <relref> target attribute does not itself have a target attribute 
        Check('xml', 'any', 'warn', 'warn', 'warn', xml_artwork_multiple_content), # An element (particularly <artwork> or <sourcecode>) contains both a src attribute, and content 
        Check('xml', 'any', 'err',  'warn', 'err',  xml_element_src_bad_schema), # The src attribute of an element contains a URI scheme other than data:, file:, http:, or https: 
        Check('xml', 'any', 'warn', 'warn', 'warn', xml_link_has_bad_content), # <link> exists with DOI or RFC-series ISDN for this document when the document is an Internet-Draft 
        Check('xml', 'any', 'err',  'warn', 'err',  xml_section_bad_numbered_false), # <section> with a numbered attribute of 'false' is not a child of <boilerplate>, <middle>, or <back>, or has a subsequent <section> sibling with a numbered attribute of 'true' 
        Check('xml', 'any', 'err',  'warn', 'err',  xml_xref_counter_bad_target), # An <xref> element with no content and a 'format' attribute of 'counter' has a 'target' attribute whose value is not a section, figure, table or ordered list number 
        Check('xml', 'any', 'err',  'warn', 'err',  xml_relref_target_missing_anchor), # A <relref> element whose 'target' attribute points to a document in xml2rfcv3 format, and whose 'relative' attribute value (or the derived value from a 'section' attribute) does not appear as an anchor in that document 
        Check('xml', 'any', 'err',  'warn', 'err',  xml_artwork_svg_wrong_media_type), # An <artwork> element with type 'svg' has a 'src' attribute with URI scheme 'data:' and the mediatype of the data: URI is not 'image/svg+xml' 
        Check('xml', 'any', 'err',  'err',  'err',  xml_sourcecode_multiple_content), # A <sourcecode> element has both a 'src' attribute and non-empty content 
    #    Check('xml', 'any', 'err',  'err',  'err',  xml_artwork_binary_notempty), # An <artwork> element has type 'binary-art' and non-empty content 

    #3.2.1 If the document is an RFC
    #-------------------------------

        Check('xml', 'rfc', 'err',  'err',  'err',  xml_rfc_note_remove_true), # A <note> element has a 'removeInRFC' attribute with a value of 'true' 
        Check('xml', 'rfc', 'err',  'warn', 'err',  xml_rfc_artwork_wrong_type), # An <artwork> element has type other than 'ascii-art','call-flow','hex-dump', or 'svg' 

    #3.2.2 Boilerplate checks
    #------------------------

        Check('xml', 'any', 'warn', 'warn', 'warn', xml_text_has_boilerplate), # The text inside any tag sufficiently matches any of the boilerplate in the IETF-TLP-4 section 6a-6d  (such text should probably be removed and the ipr attribute of the rfc tag should be verified) 
        Check('xml', 'any', 'warn', 'warn', 'err',  xml_boilerplate_mismatch), # The value of the <boilerplate> element, if non-empty, does not match what the ipr, category, submission, and consensus <rfc> attributes would cause to be generated 

    #3.2.3 Autogenerated identifier checks
    #-------------------------------------

        Check('xml', 'rfc', 'warn', 'comm', 'warn', xml_rfc_generated_attrib_wrong), # The value of any present pn or slugifiedName attributes do not match what would be regenerated 

    #3.3 Text Input Specific Conditions
    #----------------------------------

        Check('txt', 'any', 'err',  'warn', 'none', txt_text_added_whitespace), # document does not appear to be ragged-right (more than 50 lines of intra-line extra spacing) 
        Check('txt', 'any', 'err',  'warn', 'warn', txt_text_lines_too_long), # document contains over-long lines (cut-off is 72 characters. Report longest line, and count of long lines) 
        Check('txt', 'any', 'warn', 'warn', 'none', txt_text_line_break_hyphens), # document has hyphenated line-breaks 
        Check('txt', 'any', 'warn', 'warn', 'none', txt_text_hyphen_space), # document has a hyphen followed immediately by a space within a line 
        Check('txt', 'any', 'warn', 'warn', 'none', txt_update_info_extra_text), # Updates or Obsoletes line on first page has more than just numbers of RFCs (such as the character sequence 'RFC') 
        Check('txt', 'any', 'warn', 'warn', 'none', txt_update_info_not_in_order), # Updates or Obsoletes numbers do not appear in ascending order 
        Check('txt', 'any', 'comm', 'comm', 'none', txt_doc_bad_magic), # document starts with PK or BM 
        Check('txt', 'any', 'comm', 'comm', 'none', txt_reference_style_mixed), # document appears to use numeric references, but contains something that looks like a text-style reference (or vice-versa) 
        Check('txt', 'any', 'warn', 'warn', 'warn', txt_text_ref_unused_), # a string that looks like a reference appears but does not occur in any reference section 
        Check('txt', 'any', 'err',  'err',  'err',  txt_abstract_numbered), # Abstract section is numbered 
        Check('txt', 'any', 'err',  'err',  'err',  txt_status_of_memo_numbered), # 'Status of this memo' section is numbered 
        Check('txt', 'any', 'err',  'err',  'err',  txt_copyright_notice_numbered), # Copyright Notice section is numbered 

    # 3.3.1 Boilerplate checks
    # ------------------------

        Check('txt', 'any', 'err',  'err',  'err',  txt_boilerplate_copyright_missing), # TLP-4 6.b.i copyright line is not present 
        Check('txt', 'any', 'warn', 'warn', 'warn', txt_boilerplate_copyright_year_wrong), # TLP-4 6.b.i copyright date is not this (or command-line specified) year 
        Check('txt', 'any', 'err',  'err',  'err',  txt_boilerplate_licence_missing), # TLP-4 6.b.i  or b.ii license notice is not present, or doesn't match stream 
        Check('txt', 'any', 'err',  'err',  'err',  txt_boilerplate_restrictions_found), # IETF stream document sufficiently matches TLP-4 6.c.i or 6.c.ii text (restrictions on publication or derivative works) 
        Check('txt', 'any', 'warn', 'warn', 'warn', txt_boilerplate_copyright_duplicate), # More than one instance of text sufficiently matching the TLP-4 6.b.i copyright line occurs 
        Check('txt', 'any', 'warn', 'warn', 'warn', txt_boilerplate_licence_duplicate), # More than one instance of text sufficiently matching either the TLP4 6.b.i or 6.b.ii license notice occurs 
        Check('txt', 'any', 'warn', 'warn', 'warn', txt_boilerplate_pre5378_missing_upd), # Document obsoletes or updates any pre-5378 document, and doesn't contain the pre-5378 material of TLP4 6.c.iii 
        Check('txt', 'any', 'warn', 'warn', 'warn', txt_boilerplate_pre5378_missing_prev), # Any prior version of the document might be pre-5378 and the document doesn't contain the pre-5378 material of TLP4 6.c.iii 

    #3.3.2 If the document is an Internet-Draft (i.e not an RFC)
    #-----------------------------------------------------------

        Check('txt', 'ids', 'warn', 'warn', 'none', txt_pages_too_long), # contains over-long pages (report count of pages with more than 58 lines)
        Check('txt', 'ids', 'err',  'err',  'err',  txt_head_label_missing), # doesn't say INTERNET DRAFT in the upper left of the first page 
        Check('txt', 'ids', 'err',  'err',  'err',  txt_head_expiration_missing), # doesn't have expiration date on first and last page 
        Check('txt', 'ids', 'err',  'err',  'err',  txt_boilerplate_working_doc_missing), # doesn't have an acceptable paragraph noting that IDs are working documents 
        Check('txt', 'ids', 'err',  'err',  'err',  txt_boilerplate_6month_missing), # doesn't have an acceptable paragraph calling out 6 month validity 
        Check('txt', 'ids', 'err',  'err',  'err',  txt_boilerplate_current_ids_missing), # doesn't have an acceptable paragraph pointing to the list of current ids 
        Check('txt', 'ids', 'err',  'err',  'err',  txt_boilerplate_current_ids_duplicate), # has multiple occurrences of current id text 
        Check('txt', 'ids', 'err',  'err',  'err',  txt_head_docname_missing), # document name doesn't appear on first page 
        Check('txt', 'ids', 'err',  'err',  'warn', txt_table_of_contents_missing), # has no Table of Contents 
        Check('txt', 'ids', 'err',  'err',  'err',  txt_boilerplate_ipr_missing), # IPR disclosure text (TLP 4.0 6.a) does not appear 
        Check('txt', 'ids', 'err',  'err',  'err',  txt_boilerplate_ipr_not_first_page), # IPR disclosure text (TLP 4.0 6.a) appears after first page 
        Check('txt', 'ids', 'warn', 'warn', 'none', txt_pages_missing_formfeed), # pages are not separated by formfeeds 
        Check('txt', 'ids', 'comm', 'comm', 'comm', txt_pages_formfeed_misplaced), # 'FORMFEED' and '[Page...]' occur on a line, possibly separated by spaces (indicates NROFF post-processing wasn't successful) 
        Check('txt', 'ids', 'warn', 'warn', 'none', txt_text_bad_section_indentation), # section title occurs at an unexpected indentation 

    ]
