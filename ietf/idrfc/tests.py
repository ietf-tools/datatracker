# Copyright (C) 2009 Nokia Corporation and/or its subsidiary(-ies).
# All rights reserved. Contact: Pasi Eronen <pasi.eronen@nokia.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#
#  * Neither the name of the Nokia Corporation and/or its
#    subsidiary(-ies) nor the names of its contributors may be used
#    to endorse or promote products derived from this software
#    without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import unittest
import StringIO
from ietf.utils.test_utils import SimpleUrlTestCase, RealDatabaseTest

class IdRfcUrlTestCase(SimpleUrlTestCase):
    def testUrls(self):
        self.doTestUrls(__file__)

TEST_RFC_INDEX = '''<?xml version="1.0" encoding="UTF-8"?>
<rfc-index xmlns="http://www.rfc-editor.org/rfc-index" 
           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
           xsi:schemaLocation="http://www.rfc-editor.org/rfc-index 
                               http://www.rfc-editor.org/rfc-index.xsd">
    <bcp-entry>
        <doc-id>BCP0110</doc-id>
        <is-also>
            <doc-id>RFC4170</doc-id>
        </is-also>
    </bcp-entry>
    <bcp-entry>
        <doc-id>BCP0111</doc-id>
        <is-also>
            <doc-id>RFC4181</doc-id>
            <doc-id>RFC4841</doc-id>
        </is-also>
    </bcp-entry>
    <fyi-entry>
        <doc-id>FYI0038</doc-id>
        <is-also>
            <doc-id>RFC3098</doc-id>
        </is-also>
    </fyi-entry>
    <rfc-entry>
        <doc-id>RFC1938</doc-id>
        <title>A One-Time Password System</title>
        <author>
            <name>N. Haller</name>
        </author>
        <author>
            <name>C. Metz</name>
        </author>
        <date>
            <month>May</month>
            <year>1996</year>
        </date>
        <format>
            <file-format>ASCII</file-format>
            <char-count>44844</char-count>
            <page-count>18</page-count>
        </format>
        <keywords>
            <kw>OTP</kw>
            <kw>authentication</kw>
            <kw>S/KEY</kw>
        </keywords>
        <abstract><p>This document describes a one-time password authentication system (OTP). [STANDARDS-TRACK]</p></abstract>
        <obsoleted-by>
            <doc-id>RFC2289</doc-id>
        </obsoleted-by>
        <current-status>PROPOSED STANDARD</current-status>
        <publication-status>PROPOSED STANDARD</publication-status>
        <stream>Legacy</stream>
    </rfc-entry>
    <rfc-entry>
        <doc-id>RFC2289</doc-id>
        <title>A One-Time Password System</title>
        <author>
            <name>N. Haller</name>
        </author>
        <author>
            <name>C. Metz</name>
        </author>
        <author>
            <name>P. Nesser</name>
        </author>
        <author>
            <name>M. Straw</name>
        </author>
        <date>
            <month>February</month>
            <year>1998</year>
        </date>
        <format>
            <file-format>ASCII</file-format>
            <char-count>56495</char-count>
            <page-count>25</page-count>
        </format>
        <keywords>
            <kw>ONE-PASS</kw>
            <kw>authentication</kw>
            <kw>OTP</kw>
            <kw>replay</kw>
            <kw>attach</kw>
        </keywords>
        <abstract><p>This document describes a one-time password authentication system (OTP).  The system provides authentication for system access (login) and other applications requiring authentication that is secure against passive attacks based on replaying captured reusable passwords. [STANDARDS- TRACK]</p></abstract>
        <obsoletes>
            <doc-id>RFC1938</doc-id>
        </obsoletes>
        <is-also>
            <doc-id>STD0061</doc-id>
        </is-also>
        <current-status>STANDARD</current-status>
        <publication-status>DRAFT STANDARD</publication-status>
        <stream>Legacy</stream>
    </rfc-entry>
    <rfc-entry>
        <doc-id>RFC3098</doc-id>
        <title>How to Advertise Responsibly Using E-Mail and Newsgroups or - how NOT to $$$$$  MAKE ENEMIES FAST!  $$$$$</title>
        <author>
            <name>T. Gavin</name>
        </author>
        <author>
            <name>D. Eastlake 3rd</name>
        </author>
        <author>
            <name>S. Hambridge</name>
        </author>
        <date>
            <month>April</month>
            <year>2001</year>
        </date>
        <format>
            <file-format>ASCII</file-format>
            <char-count>64687</char-count>
            <page-count>28</page-count>
        </format>
        <keywords>
            <kw>internet</kw>
            <kw>marketing</kw>
            <kw>users</kw>
            <kw>service</kw>
            <kw>providers</kw>
            <kw>isps</kw>
        </keywords>
        <abstract><p>This memo offers useful suggestions for responsible advertising techniques that can be used via the internet in an environment where the advertiser, recipients, and the Internet Community can coexist in a productive and mutually respectful fashion.  This memo provides information for the Internet community.</p></abstract>
        <draft>draft-ietf-run-adverts-02</draft>
        <is-also>
            <doc-id>FYI0038</doc-id>
        </is-also>
        <current-status>INFORMATIONAL</current-status>
        <publication-status>INFORMATIONAL</publication-status>
        <stream>Legacy</stream>
    </rfc-entry>
    <rfc-entry>
        <doc-id>RFC4170</doc-id>
        <title>Tunneling Multiplexed Compressed RTP (TCRTP)</title>
        <author>
            <name>B. Thompson</name>
        </author>
        <author>
            <name>T. Koren</name>
        </author>
        <author>
            <name>D. Wing</name>
        </author>
        <date>
            <month>November</month>
            <year>2005</year>
        </date>
        <format>
            <file-format>ASCII</file-format>
            <char-count>48990</char-count>
            <page-count>24</page-count>
        </format>
        <keywords>
            <kw>real-time transport protocol</kw>
        </keywords>
        <abstract><p>This document describes a method to improve the bandwidth utilization of RTP streams over network paths that carry multiple Real-time Transport Protocol (RTP) streams in parallel between two endpoints, as in voice trunking.  The method combines standard protocols that provide compression, multiplexing, and tunneling over a network path for the purpose of reducing the bandwidth used when multiple RTP streams are carried over that path.  This document specifies an Internet Best Current Practices for the Internet Community, and requests discussion and suggestions for improvements.</p></abstract>
        <draft>draft-ietf-avt-tcrtp-08</draft>
        <is-also>
            <doc-id>BCP0110</doc-id>
        </is-also>
        <current-status>BEST CURRENT PRACTICE</current-status>
        <publication-status>BEST CURRENT PRACTICE</publication-status>
        <stream>IETF</stream>
        <area>rai</area>
        <wg_acronym>avt</wg_acronym>
    </rfc-entry>
    <rfc-entry>
        <doc-id>RFC4181</doc-id>
        <title>Guidelines for Authors and Reviewers of MIB Documents</title>
        <author>
            <name>C. Heard</name>
            <title>Editor</title>
        </author>
        <date>
            <month>September</month>
            <year>2005</year>
        </date>
        <format>
            <file-format>ASCII</file-format>
            <char-count>102521</char-count>
            <page-count>42</page-count>
        </format>
        <keywords>
            <kw>standards-track specifications</kw>
            <kw>management information base</kw>
            <kw>review</kw>
        </keywords>
        <abstract><p>This memo provides guidelines for authors and reviewers of IETF standards-track specifications containing MIB modules.  Applicable portions may be used as a basis for reviews of other MIB documents.  This document specifies an Internet Best Current Practices for the Internet Community, and requests discussion and suggestions for improvements.</p></abstract>
        <draft>draft-ietf-ops-mib-review-guidelines-04</draft>
        <updated-by>
            <doc-id>RFC4841</doc-id>
        </updated-by>
        <is-also>
            <doc-id>BCP0111</doc-id>
        </is-also>
        <current-status>BEST CURRENT PRACTICE</current-status>
        <publication-status>BEST CURRENT PRACTICE</publication-status>
        <stream>IETF</stream>
        <area>rtg</area>
        <wg_acronym>ospf</wg_acronym>
        <errata-url>http://www.rfc-editor.org/errata_search.php?rfc=4181</errata-url>
    </rfc-entry>
    <rfc-entry>
        <doc-id>RFC4841</doc-id>
        <title>RFC 4181 Update to Recognize the IETF Trust</title>
        <author>
            <name>C. Heard</name>
            <title>Editor</title>
        </author>
        <date>
            <month>March</month>
            <year>2007</year>
        </date>
        <format>
            <file-format>ASCII</file-format>
            <char-count>4414</char-count>
            <page-count>3</page-count>
        </format>
        <keywords>
            <kw>management information base</kw>
            <kw> standards-track specifications</kw>
            <kw>mib review</kw>
        </keywords>
        <abstract><p>This document updates RFC 4181, "Guidelines for Authors and Reviewers of MIB Documents", to recognize the creation of the IETF Trust.  This document specifies an Internet Best Current Practices for the Internet Community, and requests discussion and suggestions for improvements.</p></abstract>
        <draft>draft-heard-rfc4181-update-00</draft>
        <updates>
            <doc-id>RFC4181</doc-id>
        </updates>
        <is-also>
            <doc-id>BCP0111</doc-id>
        </is-also>
        <current-status>BEST CURRENT PRACTICE</current-status>
        <publication-status>BEST CURRENT PRACTICE</publication-status>
        <stream>IETF</stream>
        <wg_acronym>NON WORKING GROUP</wg_acronym>
    </rfc-entry>
    <std-entry>
        <doc-id>STD0061</doc-id>
        <title>A One-Time Password System</title>
        <is-also>
            <doc-id>RFC2289</doc-id>
        </is-also>
    </std-entry>
</rfc-index>
'''

TEST_QUEUE = '''<rfc-editor-queue xmlns="http://www.rfc-editor.org/rfc-editor-queue">
<section name="IETF STREAM: WORKING GROUP STANDARDS TRACK">
<entry xml:id="draft-ietf-sipping-app-interaction-framework">
<draft>draft-ietf-sipping-app-interaction-framework-05.txt</draft>
<date-received>2005-10-17</date-received>
<state>EDIT</state>
<normRef>
<ref-name>draft-ietf-sip-gruu</ref-name>
<ref-state>IN-QUEUE</ref-state>
</normRef>
<authors>J. Rosenberg</authors>
<title>
A Framework for Application Interaction in the Session Initiation Protocol (SIP)
</title>
<bytes>94672</bytes>
<source>Session Initiation Proposal Investigation</source>
</entry>
</section>
<section name="IETF STREAM: NON-WORKING GROUP STANDARDS TRACK">
<entry xml:id="draft-ietf-sip-gruu">
<draft>draft-ietf-sip-gruu-15.txt</draft>
<date-received>2007-10-15</date-received>
<state>MISSREF</state>
<normRef>
<ref-name>draft-ietf-sip-outbound</ref-name>
<ref-state>NOT-RECEIVED</ref-state>
</normRef>
<authors>J. Rosenberg</authors>
<title>
Obtaining and Using Globally Routable User Agent (UA) URIs (GRUU) in the Session Initiation Protocol (SIP)
</title>
<bytes>95501</bytes>
<source>Session Initiation Protocol</source>
</entry>
</section>
<section name="IETF STREAM: WORKING GROUP INFORMATIONAL/EXPERIMENTAL/BCP">
</section>
<section name="IETF STREAM: NON-WORKING GROUP INFORMATIONAL/EXPERIMENTAL/BCP">
<entry xml:id="draft-thomson-beep-async">
<draft>draft-thomson-beep-async-02.txt</draft>
<date-received>2009-05-12</date-received>
<state>EDIT</state>
<state>IANA</state>
<authors>M. Thomson</authors>
<title>
Asynchronous Channels for the Blocks Extensible Exchange Protocol (BEEP)
</title>
<bytes>17237</bytes>
<source>IETF - NON WORKING GROUP</source>
</entry>
</section>
<section name="IAB STREAM">
</section>
<section name="IRTF STREAM">
</section>
<section name="INDEPENDENT SUBMISSIONS">
</section>
</rfc-editor-queue>
'''

class MirrorScriptTestCases(unittest.TestCase,RealDatabaseTest):

    def setUp(self):
        self.setUpRealDatabase()
    def tearDown(self):
        self.tearDownRealDatabase()

    def testRfcIndex(self):
        print "Testing rfc-index.xml parsing"
        from ietf.idrfc.mirror_rfc_index import parse
        data = parse(StringIO.StringIO(TEST_RFC_INDEX))
        self.assertEquals(len(data), 6)
        print "OK"

    def testRfcEditorQueue(self):
        print "Testing queue2.xml parsing"
        from ietf.idrfc.mirror_rfc_editor_queue import parse_all
        (drafts,refs) = parse_all(StringIO.StringIO(TEST_QUEUE))
        self.assertEquals(len(drafts), 3)
        self.assertEquals(len(refs), 3)
        print "OK"

