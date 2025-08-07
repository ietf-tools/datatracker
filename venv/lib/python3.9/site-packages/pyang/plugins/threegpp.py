"""3GPP usage guidelines plugin
See 3GPP TS 32.160 clause 6.2

Copyright Ericsson 2020
Author balazs.lengyel@ericsson.com
Revision 2020-11-25

Checks implemented
6.2.1.2     Module name starts with _3gpp-
6.2.1.3     namespace pattern urn:3gpp:sa5:<module-name>
6.2.1.4-a   prefix ends with 3gpp
6.2.1.4-b   prefix.length <= 10 char
6.2.1.5     yang 1.1 missing
6.2.1.5     yang 1.1 incorrect
6.2.1.6-a   anydata
6.2.1.6-b   anyxml
6.2.1.6-c   rpc
6.2.1.6-d   deviation
6.2.1.9     description not needed for enum, bit, choice, container, 
              leaf-list, leaf, typedef, grouping, augment, uses
6.2.1.b-a   module-description-missing
6.2.1.b-b   module-organization-missing
6.2.1.b-c   module-organization includes 3gpp
6.2.1.b-d   module-contact-missing
6.2.1.b-d   module-contact-incorrect
6.2.1.c     module-reference-missing
6.2.1.c     module-reference-incorrect
6.2.1.d-a   module-revision-missing
6.2.1.d-a   module-revision-reference-missing
6.2.1.e     default meaning
6.2.1.f-a   linelength > 80
6.2.1.f-b   no-tabs
6.2.1.f-c   no-strange-chars
6.2.1.f-d   no-CR-chars
6.2-a       no-containers
"""

import optparse
import re
import io
import sys

from pyang import plugin
from pyang import statements
from pyang import error
from pyang.error import err_add
from pyang.plugins import lint

def pyang_plugin_init():
    plugin.register_plugin(THREEGPPlugin())

class THREEGPPlugin(lint.LintPlugin):
    def __init__(self):
        lint.LintPlugin.__init__(self)
        self.modulename_prefixes = ['_3gpp']

    def add_opts(self, optparser):
        optlist = [
            optparse.make_option("--3gpp",
                                 dest="threegpp",
                                 action="store_true",
                                 help="Validate the module(s) according to " \
                                 "3GPP rules."),
            ]
        optparser.add_options(optlist)

    def setup_ctx(self, ctx):
        if not ctx.opts.threegpp:
            return
        self._setup_ctx(ctx)

        error.add_error_code(
           '3GPP_BAD_NAMESPACE_VALUE', 3,
           '3GPP: the namespace should be urn:3gpp:sa5:%s')

        statements.add_validation_fun(
            'grammar', ['namespace'],
            lambda ctx, s: self.v_chk_namespace(ctx, s))

        error.add_error_code(
           '3GPP_BAD_PREFIX_VALUE', 3,
           '3GPP: the prefix should end with 3gpp')

        error.add_error_code(
           '3GPP_TOO_LONG_PREFIX', 3,
           '3GPP: the prefix should not be longer than 13 characters')

        statements.add_validation_fun(
            'grammar', ['prefix'],
            lambda ctx, s: self.v_chk_prefix(ctx, s))

        error.add_error_code(
           '3GPP_BAD_YANG_VERSION', 3,
           '3GPP: the yang-version should be 1.1')

        statements.add_validation_fun(
            'grammar', ['yang-version'],
            lambda ctx, s: self.v_chk_yang_version(ctx, s))

        # check that yang-version is present. If not,
        #  it defaults to 1. which is bad for 3GPP
        statements.add_validation_fun(
            'grammar', ['module'],
            lambda ctx, s: self.v_chk_yang_version_present(ctx, s))

        error.add_error_code(
           '3GPP_STATEMENT_NOT_ALLOWED', 3,
           ('3GPP: YANG statements anydata, anyxml, deviation, rpc '
            'should not be used'))

        statements.add_validation_fun(
            'grammar', ['anydata' , 'anyxml' , 'deviation' , 'rpc'],
            lambda ctx, s: self.v_chk_not_allowed_statements(ctx, s))

        error.add_error_code(
           '3GPP_BAD_ORGANIZATION', 3,
           '3GPP: organization statement must include 3GPP')

        statements.add_validation_fun(
            'grammar', ['organization'],
            lambda ctx, s: self.v_chk_organization(ctx, s))

        error.add_error_code(
           '3GPP_BAD_CONTACT', 3,
           '3GPP: incorrect contact statement')

        statements.add_validation_fun(
            'grammar', ['contact'],
            lambda ctx, s: self.v_chk_contact(ctx, s))

        error.add_error_code(
           '3GPP_MISSING_MODULE_REFERENCE', 3,
           '3GPP: the module should have a reference substatement')

        statements.add_validation_fun(
            'grammar', ['module'],
            lambda ctx, s: self.v_chk_module_reference_present(ctx, s))

        error.add_error_code(
           '3GPP_BAD_MODULE_REFERENCE', 3,
           '3GPP: the module\'s reference substatement is incorrect')

        statements.add_validation_fun(
            'grammar', ['reference'],
            lambda ctx, s: self.v_chk_module_reference(ctx, s))

        error.add_error_code(
           '3GPP_TAB_IN_FILE', 3,
           '3GPP: tab characters should not be used in YANG modules')

        error.add_error_code(
           '3GPP_WHITESPACE_AT_END_OF_LINE', 3,
           '3GPP: extra whitespace should not be added at the end of the line')

        error.add_error_code(
           '3GPP_LONG_LINE', 3,
           '3GPP: line longer than 80 characters')

        error.add_error_code(
           '3GPP_CR_IN_FILE', 3,
           ('3GPP: Carriage-return characters should not be used. '
            'End-of-line should be just one LF character'))

        error.add_error_code(
           '3GPP_NON_ASCII', 4,
           '3GPP: the module should only use ASCII characters')

        statements.add_validation_fun(
            'grammar', ['module'],
            lambda ctx, s: self.v_chk_3gpp_format(ctx, s))

        error.add_error_code(
           '3GPP_LIMITED_CONTAINER_USE', 4,
           ('3GPP: containers should only be used to contain the attributes '
            'of a class'))

        statements.add_validation_fun(
            'grammar', ['container'],
            lambda ctx, s: self.v_chk_limited_container_use(ctx, s))


    def pre_validate_ctx(self, ctx, modules):
        if ctx.opts.threegpp:
            ctx.canonical = False
        return

    def v_chk_namespace(self, ctx, stmt):
        r = 'urn:3gpp:sa5:' + stmt.i_module.arg +'$'
        if re.match(r, stmt.arg) is None:
            err_add(ctx.errors, stmt.pos, '3GPP_BAD_NAMESPACE_VALUE',
                    stmt.i_module.arg)

    def v_chk_prefix(self, ctx, stmt):
        if stmt.parent.keyword != 'module' :
            return
        r = '.+3gpp$'
        if re.match(r, stmt.arg) is None:
            err_add(ctx.errors, stmt.pos, '3GPP_BAD_PREFIX_VALUE',())
        if len(stmt.arg) > 13   :
            err_add(ctx.errors, stmt.pos, '3GPP_TOO_LONG_PREFIX',())

    def v_chk_yang_version_present(self, ctx, stmt):
        yang_version_present = False
        for stmt in stmt.substmts:
            if stmt.keyword == 'yang-version' :
                yang_version_present = True
        if not(yang_version_present) :
            err_add(ctx.errors, stmt.pos, '3GPP_BAD_YANG_VERSION',())

    def v_chk_yang_version(self, ctx, stmt):
        r = '1.1'
        if re.match(r, stmt.arg) is None:
            err_add(ctx.errors, stmt.pos, '3GPP_BAD_YANG_VERSION',())
    
    def v_chk_not_allowed_statements(self, ctx, stmt):
        err_add(ctx.errors, stmt.pos, '3GPP_STATEMENT_NOT_ALLOWED',())

    def v_chk_organization(self, ctx, stmt):
        r = '3GPP'
        if re.search(r, stmt.arg, re.IGNORECASE) is None:
            err_add(ctx.errors, stmt.pos, '3GPP_BAD_ORGANIZATION',())

    def v_chk_contact(self, ctx, stmt):
        if stmt.arg != ('https://www.3gpp.org/DynaReport/'
                        'TSG-WG--S5--officials.htm?Itemid=464'):
            err_add(ctx.errors, stmt.pos, '3GPP_BAD_CONTACT',())

    def v_chk_module_reference_present(self, ctx, stmt):
        module_reference_present = False
        for stmt in stmt.substmts:
            if stmt.keyword == 'reference' :
                module_reference_present = True
        if not(module_reference_present) :
            err_add(ctx.errors, stmt.pos, '3GPP_MISSING_MODULE_REFERENCE',())

    def v_chk_module_reference(self, ctx, stmt):
        if stmt.parent.keyword != 'module' :
            return
        if not(stmt.arg.startswith('3GPP TS ')) :
            err_add(ctx.errors, stmt.pos, '3GPP_BAD_MODULE_REFERENCE',())

    def v_chk_3gpp_format(self, ctx, stmt):
        if (not(stmt.arg.startswith("_3gpp"))):
            return
        filename = stmt.pos.ref
        try:
            fd = io.open(filename, "r", encoding="utf-8", newline='')
            pos = error.Position(stmt.pos.ref)
            pos.top = stmt
            lineno = 0
            for line in fd:
                lineno += 1
                pos.line = lineno
                #  no tabs
                if (line.find('\t') != -1 ):
                    err_add(ctx.errors, pos, '3GPP_TAB_IN_FILE',())
                #  no whitespace after the line
                #  removed for now as there are just too many of these
                #    errors
                # if (re.search('.*\s+\n',line) != None ):
                #    err_add(ctx.errors, self.pos,
                #        '3GPP_WHITESPACE_AT_END_OF_LINE',())
                #  lines shorter then 80 char
                if (len(line) > 82 ):
                    err_add(ctx.errors, pos, '3GPP_LONG_LINE',())
                #  EOL should be just NL no CR
                if (line.find('\r') != -1 ):
                    err_add(ctx.errors, pos, '3GPP_CR_IN_FILE',())
                #  only us-ascii chars
                try:
                    line.encode('ascii')
                except UnicodeEncodeError:
                    err_add(ctx.errors, pos, '3GPP_NON_ASCII',())

        except IOError as ex:
            sys.stderr.write("error %s: %s\n" % (filename, ex))
            sys.exit(1)
        except UnicodeDecodeError as ex:
            s = str(ex).replace('utf-8', 'utf8')
            sys.stderr.write("%s: unicode error: %s\n" % (filename, s))
            sys.exit(1)

    def v_chk_limited_container_use(self, ctx, stmt):
        if stmt.arg  != 'attributes' or stmt.parent.keyword != 'list' :
            err_add(ctx.errors, stmt.pos, '3GPP_LIMITED_CONTAINER_USE',())


    def post_validate_ctx(self, ctx, modules):
        if not ctx.opts.threegpp:
            return
        """Remove some lint errors that 3GPP considers acceptable"""
        for ctx_error in ctx.errors[:]:
            if ((ctx_error[1] == "LINT_MISSING_REQUIRED_SUBSTMT"
                    or ctx_error[1] == "LINT_MISSING_RECOMMENDED_SUBSTMT")
                and ctx_error[2][2] == 'description'
                and (ctx_error[2][1] == 'enum'
                    or  ctx_error[2][1] == 'bit'
                    or  ctx_error[2][1] == 'choice'
                    or  ctx_error[2][1] == 'container'
                    or  ctx_error[2][1] == 'leaf-list'
                    or  ctx_error[2][1] == 'leaf'
                    or  ctx_error[2][1] == 'typedef'
                    or  ctx_error[2][1] == 'grouping'
                    or  ctx_error[2][1] == 'augment'
                    or  ctx_error[2][1] == 'uses')):
                # remove error from ctx
                ctx.errors.remove(ctx_error)

        return
