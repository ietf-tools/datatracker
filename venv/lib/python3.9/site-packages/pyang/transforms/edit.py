"""Edit transform plugin

This plugin currently has quite limited functionality. Only some specific
top-level items can be edited, and only existing statements are edited.
"""

import copy
import optparse
import re
import sys

from pyang import error
from pyang import plugin
from pyang import statements

plugin_name = 'edit'


# noinspection PyUnusedLocal
def check_date(option, opt, value):
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', value):
        raise optparse.OptionValueError(
                'option %s: invalid yyyy-mm-dd date: %s' % (opt, value))
    return value


class EditOption(optparse.Option):
    TYPES = optparse.Option.TYPES + ('date',)
    TYPE_CHECKER = copy.copy(optparse.Option.TYPE_CHECKER)
    TYPE_CHECKER['date'] = check_date


def pyang_plugin_init():
    plugin.register_plugin(EditPlugin())


class EditPlugin(plugin.PyangPlugin):
    def add_opts(self, optparser):
        optlist = [
            # set YANG version (this does nothing if there's no yang-version
            # statement)
            EditOption("--edit-yang-version", dest="edit_yang_version",
                       metavar="VERSION",
                       help="Set YANG version to the supplied value"),

            # set namespace (this does nothing if there's no namespace
            # statement)
            EditOption("--edit-namespace", dest="edit_namespace",
                       metavar="NAMESPACE",
                       help="Set YANG namespace to the supplied value"),

            # set imported/included module/submodule revision dates
            EditOption("--edit-update-import-dates",
                       dest="edit_update_import_dates", default=False,
                       action="store_true",
                       help="Set import/include revision-date "
                            "statements to match imported/included "
                            "modules/submodules"),
            EditOption("--edit-delete-import-dates",
                       dest="edit_delete_import_dates", default=False,
                       action="store_true",
                       help="Delete import/include revision-date "
                            "statements"),

            # set meta info (these do nothing if there's no corresponding
            # metadata statement)
            EditOption("--edit-organization", dest="edit_organization",
                       metavar="ORGANIZATION",
                       help="Set module/submodule organization "
                            "to the supplied value"),
            EditOption("--edit-contact", dest="edit_contact",
                       metavar="CONTACT", help="Set module/submodule contact "
                                               "to the supplied value"),
            EditOption("--edit-description", dest="edit_description",
                       metavar="DESCRIPTION",
                       help="Set module/submodule description "
                            "to the supplied value"),

            # set revision info (these do nothing if there's no revision
            # statement)
            EditOption("--edit-delete-revisions-after",
                       dest="edit_delete_revisions_after", type="date",
                       metavar="PREVDATE",
                       help="Delete any revisions after "
                            "the supplied yyyy-mm-dd"),
            EditOption("--edit-revision-date", dest="edit_revision_date",
                       type="date", metavar="DATE",
                       help="Set most recent revision date "
                            "to the supplied yyyy-mm-dd"),
            EditOption("--edit-revision-description",
                       dest="edit_revision_description", metavar="DESCRIPTION",
                       help="Set most recent revision description "
                            "to the supplied value"),
            EditOption("--edit-revision-reference",
                       dest="edit_revision_reference", metavar="REFERENCE",
                       help="Set most recent revision reference "
                            "to the supplied value")
        ]

        g = optparser.add_option_group("Edit transform specific options")
        g.add_options(optlist)

    def add_transform(self, xforms):
        xforms[plugin_name] = self

    def transform(self, ctx, modules):
        edit_tree(ctx, modules)


def edit_tree(ctx, modules):
    def optval(key):
        dest = ('%s-%s' % (plugin_name, key)).replace('-', '_')
        return getattr(ctx.opts, dest, None)

    for module in modules:
        for keyword in ['yang-version', 'namespace']:
            arg = optval(keyword)
            if arg is not None:
                update_or_add_stmt(module, keyword, arg)

        substmts = []
        revision_done = False
        for stmt in module.substmts:
            replstmts = None

            if stmt.keyword in ['import', 'include']:
                # XXX should check that these options aren't both set
                if ctx.opts.edit_update_import_dates:
                    update_import_date(ctx, stmt)
                elif ctx.opts.edit_delete_import_dates:
                    delete_import_date(ctx, stmt)

            elif stmt.keyword in ['organization', 'contact', 'description']:
                arg = optval(stmt.keyword)
                if arg is not None:
                    set_meta_details(ctx, stmt, arg)

            elif stmt.keyword == 'revision' and not revision_done:
                allrevs = module.search('revision')
                lastrev = stmt == allrevs[-1]
                replstmts, revision_done = set_revision_details(ctx, stmt,
                                                                lastrev)

            substmts += [stmt] if replstmts is None else replstmts

        # XXX should we tidy up any of the deleted statements?
        module.substmts = substmts


def update_import_date(ctx, stmt):
    imprev = stmt.search_one('revision-date')
    imprevdate = imprev.arg if imprev else None

    impmod = ctx.get_module(stmt.arg, imprevdate)
    impmodrev = impmod.search_one('revision') if impmod else None
    impmodrevdate = impmodrev.arg if impmodrev else None

    if not imprev or impmodrevdate > imprevdate:
        update_or_add_stmt(stmt, 'revision-date', impmodrevdate)


# noinspection PyUnusedLocal
def delete_import_date(ctx, stmt):
    imprev = stmt.search_one('revision-date')
    if imprev:
        delete_stmt(stmt, imprev)


# noinspection PyUnusedLocal
def set_meta_details(ctx, stmt, arg):
    (newarg, ignore) = get_arg_value(arg, stmt.arg)
    if newarg is not None:
        stmt.arg = newarg


# XXX note that this logic relies on there already being at least one
#     revision statement; --lint checks this so it should be OK
def set_revision_details(ctx, stmt, lastrev):
    revision_done = False

    # relevant options
    opts = {
        'olddate': ctx.opts.edit_delete_revisions_after,
        'newdate': ctx.opts.edit_revision_date,
        'description': ctx.opts.edit_revision_description,
        'reference': ctx.opts.edit_revision_reference
    }

    # the logic is quite tricky; here's what we want to achieve:
    # * 'olddate' is the date of the oldest revision to be retained; if not
    #   supplied, any existing revisions are deleted
    # * if 'newdate' is supplied, it's the date of the next published
    #   revision and is to be inserted at the start of any remaining
    #   revisions
    # * reuse rather than delete the oldest revision statement, purely in
    #   order to retain any blank lines after it

    # default action is to do nothing
    action = ''
    #sys.stderr.write('revision %s (lastrev %s)\n' % (stmt.arg, lastrev))

    # only adjust revisions if either olddate or newdate is supplied
    olddate = opts.get('olddate', None)
    newdate = opts.get('newdate', None)
    if olddate is not None or newdate is not None:

        # determine whether to delete this old revision
        if olddate is None or stmt.arg > olddate:
            action = 'delete'
            #sys.stderr.write('-> delete (olddate %s)\n' % olddate)

        # determine whether to insert the new revision
        if newdate is not None and (action != 'delete' or lastrev):
            action = 'replace' if action == 'delete' else 'insert'
            #sys.stderr.write('-> %s (newdate %s)\n' % (action, newdate))

    # if deleting, return an empty list
    replstmts = None
    if action == 'delete':
        replstmts = []

    # replace and insert logic is quite similar:
    # * if replacing, modify this statement and return a list containing
    #   only it
    # * if inserting, create a new statement and return a list containing
    #   the new and the original statement
    elif action == 'replace' or action == 'insert':
        if action == 'replace':
            revstmt = stmt
            revstmt.arg = newdate
        else:
            revstmt = statements.new_statement(stmt.top, stmt.parent, None,
                                               'revision', newdate)

        other_keywords = set(opts.keys()) - {'olddate', 'newdate'}
        for keyword in other_keywords:
            update_or_add_stmt(revstmt, keyword, opts[keyword])

        if action == 'replace':
            replstmts = [revstmt]
        else:
            replstmts = [revstmt, stmt]

        revision_done = True

    #sys.stderr.write(
    #        '= %s\n' % ([s.arg for s in replstmts] if replstmts else None))
    return replstmts, revision_done


def get_arg_value(arg, currarg=None):
    if arg is None or arg[0] not in ['%', '@']:
        return arg, True
    else:
        replace = False
        try:
            argval = ''
            specs = arg.split('+')
            for spec in specs:
                if argval != '':
                    argval += '\n\n'
                if spec[0] not in ['%', '@']:
                    argval += spec
                elif spec[0] == '%':
                    if spec == '%SUMMARY':
                        summary = get_arg_summary(currarg)
                        if summary:
                            argval += summary
                    elif spec.startswith('%SUBST/'):
                        (ignore, old, new) = spec.split('/')
                        if currarg is None:
                            if argval == '':
                                argval = None
                        else:
                            argval = currarg.replace(old, new)
                        replace = True
                    elif spec == '%DELETE':
                        argval = ''
                        replace = True
                    else:
                        argval += spec
                elif spec[0] == '@':
                    argval += open(spec[1:], 'r').read().rstrip()
            return argval, replace
        except IOError as e:
            raise error.EmitError(str(e))


def get_arg_summary(arg):
    lines = arg.splitlines()
    summary = ''
    prev = ''
    discard_prev = False
    for line in lines:
        if line.strip().startswith('Copyright '):
            if prev.strip() == '':
                discard_prev = True
            break
        if prev != '':
            summary += prev
        prev = ''
        if summary != '':
            prev += '\n'
        prev += line
    if prev and not discard_prev:
        summary += prev
    return summary if summary else 'TBD'


# XXX should insert in canonical order; currently (apart from the hack noted
#     below) just appending; should look into doing the same as yang.py, which
#     does: substmts = grammar.sort_canonical(stmt.keyword, stmt.substmts)
def update_or_add_stmt(stmt, keyword, arg, index=None):
    child = stmt.search_one(keyword)
    currarg = child.arg if child else None
    (argval, replace) = get_arg_value(arg, currarg)
    if argval is None:
        child = None
    elif child:
        if not replace and child.arg and child.arg != argval and child.arg \
                != 'TBD':
            sys.stderr.write('%s: not replacing existing %s %r with %r\n' % (
                child.pos, keyword, child.arg, argval))
        else:
            child.arg = argval
    else:
        child = statements.new_statement(stmt.top, stmt, None, keyword, argval)
        if index is None:
            index = len(stmt.substmts)
        # XXX this hack ensures that 'reference' is always last
        if index > 0 and stmt.substmts[index - 1].keyword == 'reference':
            index -= 1
        stmt.substmts.insert(index, child)
    return child


def delete_stmt(parent, stmt):
    if stmt in parent.substmts:
        idx = parent.substmts.index(stmt)
        del parent.substmts[idx]
    del stmt
