#!/usr/bin/env python
# -*- coding: utf-8 indent-with-tabs: 0 -*-
# Copyright 2018-2019 IETF Trust, All Rights Reserved

from __future__ import unicode_literals, print_function, division

from unittest import TestCase
from idnits import *


# This is a stub.  Needs a large number of test cases, to cover individual
# htmlization features.

class MarkupTestCase(TestCase):

    def test_text_has_control_char(self):
        # Control characters other than CR, NL, or FF appear (0x01-0x09,0x0b,0x0e-0x1f) 
        pass

    def test_text_has_invalid_utf8(self):
        # Byte sequences that are not valid UTF-8 appear 
        pass

    def test_text_has_nonascii_char(self):
        # Non-ASCII UTF-8 appear (comment will point to guidance in draft-iab-rfc-nonascii or its successor) 
        pass

    def test_abstract_missing(self):
        # Missing Abstract section 
        pass

    def test_introduction_missing(self):
        # Missing Introduction section 
        pass

    def test_security_considerations_missing(self):
        # Missing Security Considerations section 
        pass

    def test_author_address_missing(self):
        # Missing Author Address section 
        pass

    def test_references_no_category(self):
        # References (if any present) are not categorized as Normative or Informative 
        pass

    def test_abstract_with_reference(self):
        # Abstract contains references 
        pass

    def test_fqdn_not_example(self):
        # FQDN appears (other than www.ietf.org) not meeting RFC2606/RFC6761 recommendations 
        pass

    def test_ipv4_private_not_example(self):
        # Private IPv4 address appears that doesn't meet RFC5735 recommendations 
        pass

    def test_ipv4_multicast_not_example(self):
        # Multicast IPv4 address appears that doesn't meet RFC5771/RFC6676 recommendations 
        pass

    def test_ipv4_generic_not_example(self):
        # Other IPv4 address appears that doesn't meet RFC5735 recommendations 
        pass

    def test_ipv6_local_not_example(self):
        # Unique Local IPv6 address appears that doesn't meet RFC3849/RFC4291 recommendations 
        pass

    def test_ipv6_link_not_example(self):
        # Link Local IPv6 address appears that doesn't meet RFC3849/RFC4291 recommendations 
        pass

    def test_ipv6_generic_not_example(self):
        # Other IPv6 address appears that doesn't meet RFC3849/RFC4291 recommendations 
        pass

    def test_text_code_comment(self):
        # A possible code comment is detected outside of a marked code block 
        pass

    def test_rfc2119_info_missing(self):
        # 2119 keywords occur, but neither the matching boilerplate nor a reference to 2119 is missing 
        pass

    def test_rfc2119_boilerplate_missing(self):
        # 2119 keywords occur, a reference to 2119 exists, but matching boilerplate is missing 
        pass

    def test_rfc2119_boilerplate_extra(self):
        # 2119 boilerplate is present, but document doesn't use 2119 keywords 
        pass

    def test_rfc2119_bad_keyword_combo(self):
        # badly formed combination of 2119 words occurs (MUST not, SHALL not, SHOULD not, not RECOMMENDED, MAY NOT, NOT REQUIRED, NOT OPTIONAL) 
        pass

    def test_rfc2119_boilerplate_lookalike(self):
        # text similar to 2119 boilerplate occurs, but doesn't reference 2119 
        pass

    def test_rfc2119_keyword_lookalike(self):
        # NOT RECOMMENDED appears, but is not included in 2119-like boilerplate 
        pass

    def test_abstract_update_info_missing(self):
        # Abstract doesn't directly state it updates or obsoletes each document so affected (Additional comment if Abstract mentions the document some other way) 
        pass

    def test_abstract_update_info_extra(self):
        # Abstract states it updates or obsoletes a document not declared in the relevant field previously 
        pass

    def test_authors_addresss_grammar(self):
        # Author's address section title misuses possessive mark or uses a character other than a single quote 
        pass

    def test_reference_not_used(self):
        # a reference is declared, but not used in the document 
        pass

    def test_reference_is_downref(self):
        # a reference appears to be a downref (noting if reference appears in the downref registry) 
        pass

    def test_reference_status_unknown(self):
        # a normative reference to an document of unknown status appears (possible downref) 
        pass

    def test_reference_is_obsolete_norm(self):
        # a normative or unclassified reference is to an obsolete  document 
        pass

    def test_reference_is_obsolete_info(self):
        # an informative reference is to an obsolete document 
        pass

    def test_reference_is_draft_rfc(self):
        # a reference is to a draft that has already been published as an rfc 
        pass

    def test_sourcecode_no_license(self):
        # A code-block is detected, but the block does not contain a license declaration 
        pass


    def test_filename_base_bad_characters(self):
        # filename's base name contains characters other than digits, lowercase alpha, and dash 
        pass

    def test_filename_ext_mismatch(self):
        # filename's extension doesn't match format type (.txt, .xml) 
        pass

    def test_filename_base_not_docname_(self):
        # filename's base name doesn't match the name declared in the document 
        pass

    def test_filename_too_long(self):
        # filename (including extension) is more than 50 characters 
        pass


    def test_obsoletes_obsolete_rfc(self):
        # Document claims to obsolete an RFC that is already obsolete 
        pass

    def test_updates_obsolete_rfc(self):
        # Document claims to update an RFC that is obsolete 
        pass

    def test_doc_status_info_bad(self):
        # Document's status or intended status is not found or not recognized 
        pass

    def test_doc_date_bad(self):
        # Document's date can't be determined or is too far in the past or the future (see existing implementation for "too far") 
        pass


    def test_section_iana_missing(self):
        # Missing IANA considerations section 
        pass


    def test_docname_malformed(self):
        # filename's base name  doesn't begin with 'draft', contains two consecutive hyphens, or doesn't have enough structure to contain the individual or stream, potentially a wg name, and a distinguishing name. (draft-example-00 is an error, but draft-example-filename is acceptable) 
        pass

    def test_section_iana_missing(self):
        # Missing IANA considerations section 
        pass


    def test_doc_rev_unexpected(self):
        # version of document is unexpected (already exists, or leaves a gap) 
        pass


    def test_element_deprecated(self):
        # any deprecated elements or attributes appear 
        pass

    def test_stream_contradiction(self):
        # metadata and document's 'submissionType' attribute state different streams 
        pass

    def test_source_code_in_sourcecode(self):
        # The text inside a <sourcecode> tag contains the string '<CODE BEGINS>' (Warn that the string is unnecessary and may duplicate what a presentation format converter will produce.) 
        pass

    def test_source_code_in_text(self):
        # The text inside any other tag contains the string '<CODE BEGINS>' (Warn that if the text is a code block, it should appear in a <sourcecode> element) 
        pass

    def test_text_looks_like_ref(self):
        # text occurs that looks like a text-document reference (e.g. [1], or [RFC...])  (if the text was really a reference it should be in an <xref> tag) 
        pass

    def test_ipr_attrib_missing(self):
        # <rfc> ipr attribute is missing or not recognized 
        pass

    def test_ipr_attrib_unknown(self):
        # ipr attribute is not one of "trust200902", "noModificationTrust200902", "noDerivativesTrust200902", or "pre5378Trust200902" 
        pass

    def test_ipr_attrib_disallowed(self):
        # document is ietf stream and ipr attribute is one of "noModificationTrust200902" or "noDerivativesTrust200902" 
        pass

    def test_workgroup_not_group(self):
        # <workgroup> content doesn't end with "Group" 
        pass

    def test_update_info_bad(self):
        # The "obsoletes" or "updates" attribute values of the <rfc> element are not comma separated strings of digits 
        pass

    def test_update_info_noref(self):
        # The rfcs indicated by the "obsoletes" and "updates" attribute values of the <rfc> element are not included in the references section 
        pass

    def test_xref_target_missing(self):
        # <xref> has no target attribute 
        pass

    def test_xref_target_not_anchor(self):
        # <xref> target attribute does not appear as an anchor of another element 
        pass

    def test_relref_target_missing(self):
        # <relref> has no target attribute 
        pass

    def test_relref_target_not_anchor(self):
        # <relref> target attribute does not appear as an anchor of a <reference> element 
        pass

    def test_relref_target_no_target(self):
        # A <reference> element pointed to by a <relref> target attribute does not itself have a target attribute 
        pass

    def test_artwork_multiple_content(self):
        # An element (particularly <artwork> or <sourcecode>) contains both a src attribute, and content 
        pass

    def test_element_src_bad_schema(self):
        # The src attribute of an element contains a URI scheme other than data:, file:, http:, or https: 
        pass

    def test_link_has_bad_content(self):
        # <link> exists with DOI or RFC-series ISDN for this document when the document is an Internet-Draft 
        pass

    def test_section_bad_numbered_false(self):
        # <section> with a numbered attribute of 'false' is not a child of <boilerplate>, <middle>, or <back>, or has a subsequent <section> sibling with a numbered attribute of 'true' 
        pass

    def test_xref_counter_bad_target(self):
        # An <xref> element with no content and a 'format' attribute of 'counter' has a 'target' attribute whose value is not a section, figure, table or ordered list number 
        pass

    def test_relref_target_missing_anchor(self):
        # A <relref> element whose 'target' attribute points to a document in xml2rfcv3 format, and whose 'relative' attribute value (or the derived value from a 'section' attribute) does not appear as an anchor in that document 
        pass

    def test_artwork_svg_wrong_media_type(self):
        # An <artwork> element with type 'svg' has a 'src' attribute with URI scheme 'data:' and the mediatype of the data: URI is not 'image/svg+xml' 
        pass

    def test_sourcecode_multiple_content(self):
        # A <sourcecode> element has both a 'src' attribute and non-empty content 
        pass

    def test_artwork_binary_notempty(self):
         # An <artwork> element has type 'binary-art' and non-empty content 
         pass


    def test_rfc_note_remove_true(self):
        # A <note> element has a 'removeInRFC' attribute with a value of 'true' 
        pass

    def test_rfc_artwork_wrong_type(self):
        # An <artwork> element has type other than 'ascii-art','call-flow','hex-dump', or 'svg' 
        pass


    def test_text_has_boilerplate(self):
        # The text inside any tag sufficiently matches any of the boilerplate in the IETF-TLP-4 section 6a-6d  (such text should probably be removed and the ipr attribute of the rfc tag should be verified) 
        pass

    def test_boilerplate_mismatch(self):
        # The value of the <boilerplate> element, if non-empty, does not match what the ipr, category, submission, and consensus <rfc> attributes would cause to be generated 
        pass


    def test_rfc_generated_attrib_wrong(self):
        # The value of any present pn or slugifiedName attributes do not match what would be regenerated 
        pass


    def test_text_added_whitespace(self):
        # document does not appear to be ragged-right (more than 50 lines of intra-line extra spacing) 
        pass

    def test_text_lines_too_long__(self):
        # document contains over-long lines (cut-off is 72 characters. Report longest line, and count of long lines) 
        pass

    def test_text_line_break_hyphens__(self):
        # document has hyphenated line-breaks 
        pass

    def test_text_hyphen_space__(self):
        # document has a hyphen followed immediately by a space within a line 
        pass

    def test_update_info_extra_text__(self):
        # Updates or Obsoletes line on first page has more than just numbers of RFCs (such as the character sequence 'RFC') 
        pass

    def test_update_info_not_in_order__(self):
        # Updates or Obsoletes numbers do not appear in ascending order 
        pass

    def test_doc_bad_magic__(self):
        # document starts with PK or BM 
        pass

    def test_reference_style_mixed__(self):
        # document appears to use numeric references, but contains something that looks like a text-style reference (or vice-versa) 
        pass

    def test_text_ref_unused___(self):
        # a string that looks like a reference appears but does not occur in any reference section 
        pass

    def test_abstract_numbered__(self):
        # Abstract section is numbered 
        pass

    def test_status_of_memo_numbered__(self):
        # 'Status of this memo' section is numbered 
        pass

    def test_copyright_notice_numbered__(self):
        # Copyright Notice section is numbered 
        pass


    def test_boilerplate_copyright_missing__(self):
        # TLP-4 6.b.i copyright line is not present 
        pass

    def test_boilerplate_copyright_year_wrong__(self):
        # TLP-4 6.b.i copyright date is not this (or command-line specified) year 
        pass

    def test_boilerplate_licence_missing__(self):
        # TLP-4 6.b.i  or b.ii license notice is not present, or doesn't match stream 
        pass

    def test_boilerplate_restrictions_found__(self):
        # IETF stream document sufficiently matches TLP-4 6.c.i or 6.c.ii text (restrictions on publication or derivative works) 
        pass

    def test_boilerplate_copyright_duplicate__(self):
        # More than one instance of text sufficiently matching the TLP-4 6.b.i copyright line occurs 
        pass

    def test_boilerplate_licence_duplicate__(self):
        # More than one instance of text sufficiently matching either the TLP4 6.b.i or 6.b.ii license notice occurs 
        pass

    def test_boilerplate_pre5378_missing_upd(self):
        # Document obsoletes or updates any pre-5378 document, and doesn't contain the pre-5378 material of TLP4 6.c.iii 
        pass

    def test_boilerplate_pre5378_missing_prev(self):
        # Any prior version of the document might be pre-5378 and the document doesn't contain the pre-5378 material of TLP4 6.c.iii 
        pass


    def test_pages_too_long__(self):
        # contains over-long pages (report count of pages with more than 58 lines)
        pass

    def test_head_label_missing__(self):
        # doesn't say INTERNET DRAFT in the upper left of the first page 
        pass

    def test_head_expiration_missing(self):
        # doesn't have expiration date on first and last page 
        pass

    def test_boilerplate_working_doc_missing(self):
        # doesn't have an acceptable paragraph noting that IDs are working documents 
        pass

    def test_boilerplate_6month_missing__(self):
        # doesn't have an acceptable paragraph calling out 6 month validity 
        pass

    def test_boilerplate_current_ids_missing__(self):
        # doesn't have an acceptable paragraph pointing to the list of current ids 
        pass

    def test_boilerplate_current_ids_duplicate__(self):
        # has multiple occurrences of current id text 
        pass

    def test_head_docname_missing__(self):
        # document name doesn't appear on first page 
        pass

    def test_table_of_contents_missing__(self):
        # has no Table of Contents 
        pass

    def test_boilerplate_ipr_missing__(self):
        # IPR disclosure text (TLP 4.0 6.a) does not appear 
        pass

    def test_boilerplate_ipr_not_first_page__(self):
        # IPR disclosure text (TLP 4.0 6.a) appears after first page 
        pass

    def test_pages_missing_formfeed(self):
        # pages are not separated by formfeeds 
        pass

    def test_pages_formfeed_misplaced(self):
        # 'FORMFEED' and '[Page...]' occur on a line, possibly separated by spaces (indicates NROFF post-processing wasn't successful) 
        pass

    def test_text_bad_section_indentation(self):
        # section title occurs at an unexpected indentation 
        pass






if __name__ == '__main__':
    unittest.main()
