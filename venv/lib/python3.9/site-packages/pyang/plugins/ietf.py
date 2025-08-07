"""IETF usage guidelines plugin
See RFC 8407
"""

import optparse
import sys
import re

from pyang import plugin
from pyang import statements
from pyang import error
from pyang.error import err_add
from pyang.plugins import lint

def pyang_plugin_init():
    plugin.register_plugin(IETFPlugin())

class IETFPlugin(lint.LintPlugin):
    def __init__(self):
        self.found_2119_keywords = False
        self.found_8174 = False
        self.found_tlp = False
        self.mmap = {}

        lint.LintPlugin.__init__(self)
        self.namespace_prefixes = ['urn:ietf:params:xml:ns:yang:']
        self.modulename_prefixes = ['ietf', 'iana']

    def add_opts(self, optparser):
        optlist = [
            optparse.make_option("--ietf",
                                 dest="ietf",
                                 action="store_true",
                                 help="Validate the module(s) according to " \
                                 "IETF rules."),
            optparse.make_option("--ietf-help",
                                 dest="ietf_help",
                                 action="store_true",
                                 help="Print help on the IETF checks and exit"),
            ]
        optparser.add_options(optlist)

    def setup_ctx(self, ctx):
        if ctx.opts.ietf_help:
            print_help()
            sys.exit(0)
        if not ctx.opts.ietf:
            return
        self._setup_ctx(ctx)

        statements.add_validation_fun(
            'grammar', ['description'],
            lambda ctx, s: self.v_chk_description(ctx, s))

        # register our error codes
        error.add_error_code(
            'IETF_MISSING_RFC8174', 4,
            'the module seems to use RFC 2119 keywords, but the required'
            + ' text from RFC 8174 is not found or is not correct'
            + ' (see pyang --ietf-help for details).')

        error.add_error_code(
            'IETF_MISSING_TRUST_LEGAL_PROVISIONING', 4,
            'RFC 8407: 3.1: '
            + 'The IETF Trust Copyright statement seems to be'
            + ' missing or is not correct'
            + ' (see pyang --ietf-help for details).')

        error.add_error_code(
            'IETF_MISSING_RFC_TEXT', 4,
            'RFC 8407: Appendix B: '
            + 'The text about which RFC this module is part of seems to be'
            + ' missing or is not correct'
            + ' (see pyang --ietf-help for details).')

    def pre_validate_ctx(self, ctx, modules):
        for mod in modules:
            self.mmap[mod.arg] = {
                'found_2119_keywords': False,
                'found_8174': False}

    def v_chk_description(self, ctx, s):
        if s.i_module.arg not in self.mmap:
            return
        arg = re.sub(r'\s+', ' ', s.arg)
        if s.parent.keyword == 'module' or s.parent.keyword == 'submodule':
            m = re_rfc8174.search(arg)
            if m is not None:
                self.mmap[s.i_module.arg]['found_8174'] = True
                arg = arg[:m.start()] + arg[m.end():]
            m = re_tlp.search(arg)
            if m is None:
                err_add(ctx.errors, s.pos,
                        'IETF_MISSING_TRUST_LEGAL_PROVISIONING', ())
            else:
                # the statement was changed to "Revised BSD License" in
                # september 2021.  allow both for old docs; require "Revised"
                # for new.
                y = int(m.group(1))
                if y >= 2022 and arg.find("Simplified") > 0:
                    err_add(ctx.errors, s.pos,
                            'IETF_MISSING_TRUST_LEGAL_PROVISIONING', ())
            if s.parent.arg.startswith('ietf-'):
                m = re_ietf_rfc.search(arg)
                if m is None:
                    err_add(ctx.errors, s.pos,
                        'IETF_MISSING_RFC_TEXT', ())
        if not self.mmap[s.i_module.arg]['found_2119_keywords']:
            if re_2119_keywords.search(arg) is not None:
                self.mmap[s.i_module.arg]['found_2119_keywords'] = True
                self.mmap[s.i_module.arg]['description_pos'] = s.pos

    def post_validate_ctx(self, ctx, modules):
        if not ctx.opts.ietf:
            return
        for mod in modules:
            if (self.mmap[mod.arg]['found_2119_keywords']
                and not self.mmap[mod.arg]['found_8174']):
                pos = self.mmap[mod.arg]['description_pos']
                err_add(ctx.errors, pos, 'IETF_MISSING_RFC8174', ())

def print_help():
    print("""
Validates the module or submodule according to the IETF rules found
in RFC 8407.

The module's or submodule's description statement must contain the
following text:

     Copyright (c) <year> IETF Trust and the persons identified as
     authors of the code.  All rights reserved.

     Redistribution and use in source and binary forms, with or
     without modification, is permitted pursuant to, and subject to
     the license terms contained in, the Revised BSD License set
     forth in Section 4.c of the IETF Trust's Legal Provisions
     Relating to IETF Documents
     (https://trustee.ietf.org/license-info).

An IETF module (but not an IANA module) must also contain the
following text:

     This version of this YANG module is part of RFC XXXX
     (https://www.rfc-editor.org/info/rfcXXXX); see the RFC itself
     for full legal notices.

If any description statement in the module or submodule contains
RFC 2119 key words, the module's or submodule's description statement
must contain the following text:

     The key words 'MUST', 'MUST NOT', 'REQUIRED', 'SHALL', 'SHALL
     NOT', 'SHOULD', 'SHOULD NOT', 'RECOMMENDED', 'NOT RECOMMENDED',
     'MAY', and 'OPTIONAL' in this document are to be interpreted as
     described in BCP 14 (RFC 2119) (RFC 8174) when, and only when,
     they appear in all capitals, as shown here.
""")

rfc8174_str = \
r"""The key words 'MUST', 'MUST NOT', 'REQUIRED', 'SHALL', 'SHALL
NOT', 'SHOULD', 'SHOULD NOT', 'RECOMMENDED', 'NOT RECOMMENDED',
'MAY', and 'OPTIONAL' in this document are to be interpreted as
described in BCP 14 \(RFC 2119\) \(RFC 8174\) when, and only when,
they appear in all capitals, as shown here."""

re_rfc8174 = re.compile(re.sub(r'\s+', ' ', rfc8174_str))

tlp_str = \
r"""Copyright \(c\) ([0-9]+) IETF Trust and the persons identified as
authors of the code\.  All rights reserved\.

Redistribution and use in source and binary forms, with or
without modification, is permitted pursuant to, and subject
to the license terms contained in, the (Revised|Simplified) BSD License
set forth in Section 4\.c of the IETF Trust's Legal Provisions
Relating to IETF Documents
\(https?://trustee.ietf.org/license-info\)\."""

re_tlp = re.compile(re.sub(r'\s+', ' ', tlp_str))

ietf_rfc_str = \
r"""This version of this YANG module is part of
RFC .+(\s+\(https?://www.rfc-editor.org/info/rfc.+\))?; see
the RFC itself for full legal notices\."""

re_ietf_rfc = re.compile(re.sub(r'\s+', ' ', ietf_rfc_str))

re_2119_keywords = re.compile(
    r"\b(MUST|REQUIRED|SHOULD|SHALL|RECOMMENDED|MAY|OPTIONAL)\b")
