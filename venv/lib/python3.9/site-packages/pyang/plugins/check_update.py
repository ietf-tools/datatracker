"""YANG module update check tool
This plugin checks if an updated version of a module follows
the rules defined in Section 10 of RFC 6020 and Section 11 of RFC 7950.
"""

import optparse
import sys
import os
import io

from pyang import context
from pyang import repository
from pyang import plugin
from pyang import statements
from pyang import error
from pyang import util
from pyang import types
from pyang.error import err_add

sxmod = 'ietf-yang-structure-ext'

def pyang_plugin_init():
    plugin.register_plugin(CheckUpdatePlugin())

class CheckUpdatePlugin(plugin.PyangPlugin):
    def add_opts(self, optparser):
        optlist = [
            optparse.make_option("--check-update-from",
                                 metavar="OLDMODULE",
                                 dest="check_update_from",
                                 help="Verify that upgrade from OLDMODULE" \
                                      " follows RFC 6020 and 7950 rules."),
            optparse.make_option("-P", "--check-update-from-path",
                                 dest="old_path",
                                 default=[],
                                 action="append",
                                 help=os.pathsep + "-separated search path" \
                                     " for yin and yang modules used by" \
                                     " OLDMODULE"),
            optparse.make_option("-D", "--check-update-from-deviation-module",
                                 dest="old_deviation",
                                 default=[],
                                 action="append",
                                 help="Old deviation module of the OLDMODULE." \
                                      " This option can be given multiple" \
                                      " times."),
            optparse.make_option("--check-update-include-structures",
                                 dest="check_update_structures",
                                 action="store_true",
                                 help="Check sx:structures."),
            ]
        optparser.add_options(optlist)

        error.add_error_code(
            'CHK_INVALID_MODULENAME', 3,
            "the module's name MUST NOT be changed"
            + " (RFC 6020: sec. 10, p3)")
        error.add_error_code(
            'CHK_INVALID_MODULENAME_v1.1', 3,
            "the module's name MUST NOT be changed"
            + " (RFC 7950: sec. 11, p3)")
        error.add_error_code(
            'CHK_INVALID_NAMESPACE', 3,
            "the module's namespace MUST NOT be changed"
            + " (RFC 6020: sec. 10, p3)")
        error.add_error_code(
            'CHK_INVALID_NAMESPACE_v1.1', 3,
            "the module's namespace MUST NOT be changed"
            + " (RFC 7950: sec. 11, p3)")
        error.add_error_code(
            'CHK_NO_REVISION', 3,
            "a revision statement MUST be present"
            + " (RFC 6020: sec. 10, p2)")
        error.add_error_code(
            'CHK_NO_REVISION_v1.1', 3,
            "a revision statement MUST be present"
            + " (RFC 7950: sec. 11, p2)")
        error.add_error_code(
            'CHK_BAD_REVISION', 3,
            "new revision %s is not newer than old revision %s"
            + " (RFC 6020: sec. 10, p2)")
        error.add_error_code(
            'CHK_BAD_REVISION_v1.1', 3,
            "new revision %s is not newer than old revision %s"
            + " (RFC 7950: sec. 11, p2)")
        error.add_error_code(
            'CHK_DEF_REMOVED', 3,
            "the %s '%s', defined at %s is illegally removed")
        error.add_error_code(
            'CHK_DEF_ADDED', 3,
            "the %s '%s' is illegally added")
        error.add_error_code(
            'CHK_DEF_ADDED2', 3,
            "the %s '%s' is illegally added in %s %s")
        error.add_error_code(
            'CHK_DEF_CHANGED', 3,
            "the %s '%s' is illegally changed from '%s'")
        error.add_error_code(
            'CHK_INVALID_STATUS', 3,
            "new status %s is not valid since the old status was %s")
        error.add_error_code(
            'CHK_CHILD_KEYWORD_CHANGED', 3,
            "the %s '%s' is illegally changed to a %s")
        error.add_error_code(
            'CHK_MANDATORY_CONFIG', 3,
            "the node %s is changed to config true, but it is mandatory")
        error.add_error_code(
            'CHK_NEW_MANDATORY', 3,
            "the mandatory node %s is illegally added")
        error.add_error_code(
            'CHK_BAD_CONFIG', 3,
            "the node %s is changed to config false")
        error.add_error_code(
            'CHK_NEW_MUST', 3,
            "a new must expression cannot be added")
        error.add_error_code(
            'CHK_UNDECIDED_MUST', 4,
            "this must expression may be more constrained than before")
        error.add_error_code(
            'CHK_NEW_WHEN', 3,
            "a new when expression cannot be added")
        error.add_error_code(
            'CHK_UNDECIDED_WHEN', 4,
            "this when expression may be different than before")
        error.add_error_code(
            'CHK_UNDECIDED_PRESENCE', 4,
            "this presence expression may be different than before")
        error.add_error_code(
            'CHK_IMPLICIT_DEFAULT', 3,
            "the leaf had an implicit default")
        error.add_error_code(
            'CHK_BASE_TYPE_CHANGED', 3,
            "the base type has illegally changed from %s to %s")
        error.add_error_code(
            'CHK_LEAFREF_PATH_CHANGED', 3,
            "the leafref's path has illegally changed")
        error.add_error_code(
            'CHK_ENUM_VALUE_CHANGED', 3,
            "the value for enum '%s', has changed from %s to %s"
            + " (RFC 6020: sec. 10, p5, bullet 1)")
        error.add_error_code(
            'CHK_ENUM_VALUE_CHANGED_v1.1', 3,
            "the value for enum '%s', has changed from %s to %s"
            + " (RFC 7950: sec. 11, p5, bullet 1)")
        error.add_error_code(
            'CHK_BIT_POSITION_CHANGED', 3,
            "the position for bit '%s', has changed from %s to %s"
            + " (RFC 6020: sec. 10, p5, bullet 2)")
        error.add_error_code(
            'CHK_BIT_POSITION_CHANGED_v1.1', 3,
            "the position for bit '%s', has changed from %s to %s"
            + " (RFC 7950: sec. 11, p5, bullet 2)")
        error.add_error_code(
            'CHK_RESTRICTION_CHANGED', 3,
            "the %s has been illegally restricted"
            + " (RFC 6020: sec. 10, p5, bullet 3)")
        error.add_error_code(
            'CHK_RESTRICTION_CHANGED_v1.1', 3,
            "the %s has been illegally restricted"
            + " (RFC 7950: sec. 11, p5, bullet 3)")
        error.add_error_code(
            'CHK_UNION_TYPES', 3,
            "the member types in the union have changed")
        error.add_error_code(
            'CHK_IO_ERROR', 1,
            "error %s: %s")

    def post_validate_ctx(self, ctx, modules):
        if not ctx.opts.check_update_from:
            return

        check_update(ctx, modules[0])

def check_update(ctx, newmod):
    oldpath = os.pathsep.join(ctx.opts.old_path)
    olddir = os.path.dirname(ctx.opts.check_update_from)
    if olddir == '':
        olddir = '.'
    oldpath += os.pathsep + olddir
    oldrepo = repository.FileRepository(oldpath, use_env=False)
    oldctx = context.Context(oldrepo)
    oldctx.opts = ctx.opts
    oldctx.lax_xpath_checks = ctx.lax_xpath_checks
    oldctx.lax_quote_checks = ctx.lax_quote_checks

    if ctx.opts.verbose:
        print("Loading old modules from:")
        for d in oldrepo.dirs:
            print("  %s" % d)
        print("")

    for p in plugin.plugins:
        p.setup_ctx(oldctx)

    for oldfilename in [ctx.opts.check_update_from] + ctx.opts.old_deviation:
        try:
            fd = io.open(oldfilename, "r", encoding="utf-8")
            text = fd.read()
        except IOError as ex:
            pos = error.Position(oldfilename)
            err_add(ctx.errors, pos, "CHK_IO_ERROR", (oldfilename, ex))
            return
        if oldfilename in ctx.opts.old_deviation:
            oldctx.add_module(oldfilename, text)
        else:
            oldmod = oldctx.add_module(oldfilename, text)
    oldctx.validate()

    ctx.errors.extend(oldctx.errors)

    if oldmod is None:
        return

    for epos, etag, eargs in ctx.errors:
        if (epos.ref in (newmod.pos.ref, oldmod.pos.ref)
            and error.is_error(error.err_level(etag))):
            return

    if ctx.opts.verbose:
        print("Loaded old modules:")
        for x in oldrepo.get_modules_and_revisions(oldctx):
            (m, r, (fmt, filename)) = x
            print("  %s" % filename)
        print("")

    chk_module(ctx, oldmod, newmod)


def chk_module(ctx, oldmod, newmod):

    chk_modulename(oldmod, newmod, ctx)

    chk_namespace(oldmod, newmod, ctx)

    chk_revision(oldmod, newmod, ctx)

    for olds in oldmod.search('feature'):
        chk_feature(olds, newmod, ctx)

    for olds in oldmod.search('identity'):
        chk_identity(olds, newmod, ctx)

    for olds in oldmod.search('typedef'):
        chk_typedef(olds, newmod, ctx)

    for olds in oldmod.search('grouping'):
        chk_grouping(olds, newmod, ctx)

    for olds in oldmod.search('rpc'):
        chk_rpc(olds, newmod, ctx)

    for olds in oldmod.search('notification'):
        chk_notification(olds, newmod, ctx)

    for olds in oldmod.search('extension'):
        chk_extension(olds, newmod, ctx)

    if ctx.opts.check_update_structures:
        for olds in oldmod.search((sxmod, 'structure')):
            chk_structure(olds, newmod, ctx)
    chk_augment(oldmod, newmod, ctx)

    chk_i_children(oldmod, newmod, ctx)

def chk_modulename(oldmod, newmod, ctx):
    if oldmod.arg != newmod.arg:
        errcode = verrcode('CHK_INVALID_MODULENAME', newmod)
        err_add(ctx.errors, newmod.pos, errcode, ())

def chk_namespace(oldmod, newmod, ctx):
    oldns = oldmod.search_one('namespace')
    newns = newmod.search_one('namespace')
    if oldns is not None and newns is not None and oldns.arg != newns.arg:
        errcode = verrcode('CHK_INVALID_NAMESPACE', newmod)
        err_add(ctx.errors, newmod.pos, 'CHK_INVALID_NAMESPACE', ())

def chk_revision(oldmod, newmod, ctx):
    oldrev = get_latest_revision(oldmod)
    newrev = get_latest_revision(newmod)
    if newrev is None:
        errcode = verrcode('CHK_NO_REVISION', newmod)
        err_add(ctx.errors, newmod.pos, errcode, ())
    elif (oldrev is not None) and (oldrev >= newrev):
        errcode = verrcode('CHK_BAD_REVISION', newmod)
        err_add(ctx.errors, newmod.pos, errcode, (newrev, oldrev))

def get_latest_revision(m):
    revs = [r.arg for r in m.search('revision')]
    revs.sort()
    if len(revs) > 0:
        return revs[-1]
    else:
        return None

def chk_feature(olds, newmod, ctx):
    chk_stmt_definitions(olds, newmod, ctx, newmod.i_features)

def chk_identity(olds, newmod, ctx):
    news = chk_stmt_definitions(olds, newmod, ctx, newmod.i_identities)
    if news is None:
        return
    # make sure the base isn't changed (other than syntactically)
    oldbases = olds.search('base')
    newbases = news.search('base')
    if newmod.i_version == '1.1':
        old_ids = [oldbase.i_identity.arg for oldbase in oldbases]
        new_ids = [newbase.i_identity.arg for newbase in newbases]
        for old_id in set(old_ids) - set(new_ids):
            err_def_removed(oldbases[old_ids.index(old_id)], news, ctx)
        for old_id in set(old_ids) & set(new_ids):
            oldbase = oldbases[old_ids.index(old_id)]
            newbase = newbases[new_ids.index(old_id)]
            if oldbase.i_identity.i_module.i_modulename != \
               newbase.i_identity.i_module.i_modulename:
                err_def_changed(oldbase, newbase, ctx)
    else:
        oldbase = next(iter(oldbases), None)
        newbase = next(iter(newbases), None)
        if oldbase is None and newbase is not None:
            err_def_added(newbase, ctx)
        elif newbase is None and oldbase is not None:
            err_def_removed(oldbase, news, ctx)
        elif oldbase is None and newbase is None:
            pass
        elif ((oldbase.i_identity.i_module.i_modulename !=
               newbase.i_identity.i_module.i_modulename)
              or (oldbase.i_identity.arg != newbase.i_identity.arg)):
            err_def_changed(oldbase, newbase, ctx)

def chk_typedef(olds, newmod, ctx):
    news = chk_stmt_definitions(olds, newmod, ctx, newmod.i_typedefs)
    if news is None:
        return
    chk_type(olds.search_one('type'), news.search_one('type'), ctx)

def chk_grouping(olds, newmod, ctx):
    news = chk_stmt_definitions(olds, newmod, ctx, newmod.i_groupings)
    if news is None:
        return
    chk_i_children(olds, news, ctx)

def chk_rpc(olds, newmod, ctx):
    news = chk_stmt(olds, newmod, ctx)
    if news is None:
        return
    chk_i_children(olds, news, ctx)

def chk_notification(olds, newmod, ctx):
    news = chk_stmt(olds, newmod, ctx)
    if news is None:
        return
    chk_i_children(olds, news, ctx)

def chk_structure(olds, newmod, ctx):
    news = chk_stmt(olds, newmod, ctx)
    if news is None:
        return
    chk_i_children(olds, news, ctx)

def chk_extension(olds, newmod, ctx):
    news = chk_stmt_definitions(olds, newmod, ctx, newmod.i_extensions)
    if news is None:
        return
    oldarg = olds.search_one('argument')
    newarg = news.search_one('argument')
    if oldarg is None and newarg is not None:
        err_def_added(newarg, ctx)
    elif oldarg is not None and newarg is None:
        err_def_removed(oldarg, newmod, ctx)
    elif oldarg is not None and newarg is not None:
        oldyin = oldarg.search_one('yin-element')
        newyin = newarg.search_one('yin-element')
        if oldyin is None and newyin is not None and newyin.arg != 'false':
            err_def_added(newyin, ctx)
        elif oldyin is not None and newyin is None and oldyin.arg != 'false':
            err_def_removed(oldyin, newarg, ctx)
        elif (oldyin is not None and newyin is not None and
              newyin.arg != oldyin.arg):
            err_def_changed(oldyin, newyin, ctx)


def chk_augment(oldmod, newmod, ctx):
    # group augment of same target together, and compare with all
    # augment of same target in newmod
    targets = {}
    for olds in oldmod.search('augment'):
        if olds.arg in targets:
            targets[olds.arg].extend(olds.i_children)
        else:
            targets[olds.arg] = list(olds.i_children) # copy
    for t in targets:
        newchs = []
        # this is not quite correct; it should be ok to change the
        # prefix, so augmenting /x:a in the old module, but /y:a in the
        # new module, if x and y are prefixes to the same module, should
        # be ok.
        for news in newmod.search('augment', arg=t):
            newchs.extend(news.i_children)

        if len(newchs) == 0:
            for olds in oldmod.search('augment', arg=t):
                err_def_removed(olds, newmod, ctx)
        else:
            for oldch in targets[t]:
                chk_children(oldch, newchs, newmod, ctx)

def chk_stmt_definitions(olds, newp, ctx, definitions):
    news = None
    if olds.arg in definitions:
        news = definitions[olds.arg]
    if news is None:
        err_def_removed(olds, newp, ctx)
        return None
    chk_status(olds, news, ctx)
    chk_if_feature(olds, news, ctx)
    return news

def chk_stmt(olds, newp, ctx):
    news = newp.search_one(olds.keyword, arg = olds.arg)
    if news is None:
        err_def_removed(olds, newp, ctx)
        return None
    chk_status(olds, news, ctx)
    chk_if_feature(olds, news, ctx)
    return news

def chk_i_children(old, new, ctx):
    for oldch in old.i_children:
        chk_child(oldch, new, ctx)

    old_child_args = [oldch.arg for oldch in old.i_children]
    added_new_children = [new_child for new_child in new.i_children if new_child.arg not in old_child_args]
    for newch in added_new_children:
        if statements.is_mandatory_node(newch):
            err_add(ctx.errors, newch.pos, 'CHK_NEW_MANDATORY', newch.arg)

def chk_child(oldch, newp, ctx):
    chk_children(oldch, newp.i_children, newp, ctx)

def chk_children(oldch, newchs, newp, ctx):
    newch = None
    for ch in newchs:
        if ch.arg == oldch.arg:
            newch = ch
            break
    if newch is None:
        err_def_removed(oldch, newp, ctx)
        return

    if newch.keyword != oldch.keyword:
        err_add(ctx.errors, newch.pos, 'CHK_CHILD_KEYWORD_CHANGED',
                (oldch.keyword, newch.arg, newch.keyword))
        return
    chk_status(oldch, newch, ctx)
    chk_if_feature(oldch, newch, ctx)
    chk_config(oldch, newch, ctx)
    chk_must(oldch, newch, ctx)
    chk_when(oldch, newch, ctx)
    if newch.keyword == 'leaf':
        chk_leaf(oldch, newch, ctx)
    elif newch.keyword == 'leaf-list':
        chk_leaf_list(oldch, newch, ctx)
    elif newch.keyword == 'container':
        chk_container(oldch, newch, ctx)
    elif newch.keyword == 'list':
        chk_list(oldch, newch, ctx)
    elif newch.keyword == 'choice':
        chk_choice(oldch, newch, ctx)
    elif newch.keyword == 'case':
        chk_case(oldch, newch, ctx)
    elif newch.keyword == 'input':
        chk_input_output(oldch, newch, ctx)
    elif newch.keyword == 'output':
        chk_input_output(oldch, newch, ctx)

def chk_status(old, new, ctx):
    oldstatus = old.search_one('status')
    newstatus = new.search_one('status')
    if oldstatus is None or oldstatus.arg == 'current':
        # any new status is ok
        return
    if newstatus is None:
        err_add(ctx.errors, new.pos, 'CHK_INVALID_STATUS',
                ("(implicit) current", oldstatus.arg))
    elif ((newstatus.arg == 'current') or
          (oldstatus.arg == 'obsolete' and newstatus.arg != 'obsolete')):
        err_add(ctx.errors, newstatus.pos, 'CHK_INVALID_STATUS',
                (newstatus.arg, oldstatus.arg))

def chk_if_feature(old, new, ctx):
    # make sure no if-features are removed if node is mandatory
    for s in old.search('if-feature'):
        if new.search_one('if-feature', arg=s.arg) is None:
            if statements.is_mandatory_node(new):
                err_def_removed(s, new, ctx)

    # make sure no if-features are added
    for s in new.search('if-feature'):
        if old.search_one('if-feature', arg=s.arg) is None:
            err_def_added2(s, new, ctx)

def chk_config(old, new, ctx):
    if not old.i_config and new.i_config:
        if statements.is_mandatory_node(new):
            err_add(ctx.errors, new.pos, 'CHK_MANDATORY_CONFIG', new.arg)
    elif old.i_config and not new.i_config:
        err_add(ctx.errors, new.pos, 'CHK_BAD_CONFIG', new.arg)

def chk_must(old, new, ctx):
    oldmust = old.search('must')
    newmust = new.search('must')
    # remove all common musts
    for oldm in old.search('must'):
        newm = new.search_one('must', arg = oldm.arg)
        if newm is not None:
            newmust.remove(newm)
            oldmust.remove(oldm)
    if len(newmust) == 0:
        # this is good; maybe some old musts were removed
        pass
    elif len(oldmust) == 0:
        for newm in newmust:
            err_add(ctx.errors, newm.pos, 'CHK_NEW_MUST', ())
    else:
        for newm in newmust:
            err_add(ctx.errors, newm.pos, 'CHK_UNDECIDED_MUST', ())

def chk_when(old, new, ctx):
    oldwhen = old.search('when')
    newwhen = new.search('when')
    # remove all common whens
    for oldw in old.search('when'):
        neww = new.search_one('when', arg = oldw.arg)
        if neww is not None:
            newwhen.remove(neww)
            oldwhen.remove(oldw)
    if new.i_module.i_version == '1.1':
        if len(newwhen) == 0:
            # this is good; maybe some old whens were removed
            return
    if len(oldwhen) == 0:
        for neww in newwhen:
            err_add(ctx.errors, neww.pos, 'CHK_NEW_WHEN', ())
    else:
        for neww in newwhen:
            err_add(ctx.errors, neww.pos, 'CHK_UNDECIDED_WHEN', ())

def chk_units(old, new, ctx):
    oldunits = old.search_one('units')
    if oldunits is None:
        return
    newunits = new.search_one('units')
    if newunits is None:
        err_def_removed(oldunits, new, ctx)
    elif newunits.arg != oldunits.arg:
        err_def_changed(oldunits, newunits, ctx)

def chk_default(old, new, ctx):
    newdefault = new.search_one('default')
    olddefault = old.search_one('default')
    if olddefault is None and newdefault is None:
        return
    if olddefault is not None and newdefault is None:
        err_def_removed(olddefault, new, ctx)
    elif olddefault is None and newdefault is not None:
        # default added, check old implicit default
        oldtype = old.search_one('type')
        if (oldtype.i_typedef is not None and
            hasattr(oldtype.i_typedef, 'i_default_str') and
            oldtype.i_typedef.i_default is not None and
            oldtype.i_typedef.i_default_str != newdefault.arg):
            err_add(ctx.errors, newdefault.pos, 'CHK_IMPLICIT_DEFAULT', ())
    elif olddefault.arg != newdefault.arg:
        err_def_changed(olddefault, newdefault, ctx)

def chk_mandatory(old, new, ctx):
    oldmandatory = old.search_one('mandatory')
    newmandatory = new.search_one('mandatory')
    if newmandatory is not None and newmandatory.arg == 'true':
        if oldmandatory is None:
            err_def_added(newmandatory, ctx)
        elif oldmandatory.arg == 'false':
            err_def_changed(oldmandatory, newmandatory, ctx)

def chk_min_max(old, new, ctx):
    oldmin = old.search_one('min-elements')
    newmin = new.search_one('min-elements')
    if newmin is None:
        pass
    elif oldmin is None:
        err_def_added(newmin, ctx)
    elif int(newmin.arg) > int(oldmin.arg):
        err_def_changed(oldmin, newmin, ctx)
    oldmax = old.search_one('max-elements')
    newmax = new.search_one('max-elements')
    if newmax is None:
        pass
    elif oldmax is None:
        err_def_added(newmax, ctx)
    elif int(newmax.arg) < int(oldmax.arg):
        err_def_changed(oldmax, newmax, ctx)

def chk_presence(old, new, ctx):
    oldpresence = old.search_one('presence')
    newpresence = new.search_one('presence')
    if oldpresence is None and newpresence is None:
        pass
    elif oldpresence is None and newpresence is not None:
        err_def_added(newpresence, ctx)
    elif oldpresence is not None and newpresence is None:
        err_def_removed(oldpresence, new, ctx)
    elif oldpresence.arg != newpresence.arg:
        err_add(ctx.errors, newpresence.pos, 'CHK_UNDECIDED_PRESENCE', ())

def chk_key(old, new, ctx):
    oldkey = old.search_one('key')
    newkey = new.search_one('key')
    if oldkey is None and newkey is None:
        pass
    elif oldkey is None and newkey is not None:
        err_def_added(newkey, ctx)
    elif oldkey is not None and newkey is None:
        err_def_removed(oldkey, new, ctx)
    else:
        # check the key argument string; i_key is not set in groupings
        oldks = [k for k in oldkey.arg.split() if k != '']
        newks = [k for k in newkey.arg.split() if k != '']
        if len(oldks) != len(newks):
            err_def_changed(oldkey, newkey, ctx)
        else:
            for ok, nk in zip(oldks, newks):
                if util.split_identifier(ok)[1] != util.split_identifier(nk)[1]:
                    err_def_changed(oldkey, newkey, ctx)
                    return

def chk_unique(old, new, ctx):
    # do not check the unique argument string; check the parsed unique instead
    # i_unique is not set in groupings; ignore
    if not hasattr(old, 'i_unique') or not hasattr(new, 'i_unique'):
        return
    oldunique = []
    for u, l in old.i_unique:
        oldunique.append((u, [s.arg for s in l]))
    for u, l in new.i_unique:
        # check if this unique was present before
        o = util.keysearch([s.arg for s in l], 1, oldunique)
        if o is not None:
            oldunique.remove(o)
        else:
            err_def_added(u, ctx)

def chk_ordered_by(old, new, ctx):
    oldorderedby = old.search_one('ordered-by')
    neworderedby = new.search_one('ordered-by')
    if oldorderedby is None and neworderedby is None:
        pass
    elif oldorderedby is None and neworderedby is not None and \
         neworderedby.arg == 'user':
        err_def_added(neworderedby, ctx)
    elif oldorderedby is not None and neworderedby is None and \
         oldorderedby.arg == 'user':
        err_def_removed(oldorderedby, new, ctx)
    elif oldorderedby is not None and neworderedby is not None and \
         oldorderedby.arg != neworderedby.arg:
        err_add(ctx.errors, neworderedby.pos, 'CHK_DEF_CHANGED',
                ('ordered-by', neworderedby.arg, oldorderedby.arg))

def chk_leaf(old, new, ctx):
    chk_type(old.search_one('type'), new.search_one('type'), ctx)
    chk_units(old, new, ctx)
    chk_default(old, new, ctx)
    chk_mandatory(old, new, ctx)

def chk_leaf_list(old, new, ctx):
    chk_type(old.search_one('type'), new.search_one('type'), ctx)
    chk_units(old, new, ctx)
    chk_min_max(old, new, ctx)
    chk_ordered_by(old, new, ctx)

def chk_container(old, new, ctx):
    chk_presence(old, new, ctx)
    chk_i_children(old, new, ctx)

def chk_list(old, new, ctx):
    chk_min_max(old, new, ctx)
    chk_key(old, new, ctx)
    chk_unique(old, new, ctx)
    chk_i_children(old, new, ctx)
    chk_ordered_by(old, new, ctx)

def chk_choice(old, new, ctx):
    chk_mandatory(old, new, ctx)
    chk_i_children(old, new, ctx)

def chk_case(old, new, ctx):
    chk_i_children(old, new, ctx)

def chk_input_output(old, new, ctx):
    chk_i_children(old, new, ctx)

def chk_type(old, new, ctx):
    oldts = old.i_type_spec
    newts = new.i_type_spec
    if oldts is None or newts is None:
        return
    # verify that the base type is the same
    if oldts.name != newts.name:
        err_add(ctx.errors, new.pos, 'CHK_BASE_TYPE_CHANGED',
                (oldts.name, newts.name))
        return

    # check the allowed restriction changes
    if oldts.name in chk_type_func:
        chk_type_func[oldts.name](old, new, oldts, newts, ctx)

def chk_integer(old, new, oldts, newts, ctx):
    chk_range(old, new, oldts, newts, ctx)

def chk_range(old, new, oldts, newts, ctx):
    ots = old.i_type_spec
    nts = new.i_type_spec
    if not isinstance(nts, types.RangeTypeSpec):
        return
    if isinstance(ots, types.RangeTypeSpec):
        tmperrors = []
        types.validate_ranges(tmperrors, new.pos, ots.ranges, new)
        if tmperrors:
            errcode = verrcode('CHK_RESTRICTION_CHANGED', new)
            err_add(ctx.errors, new.pos, errcode, 'range')
    else:
        err_add(ctx.errors, nts.ranges_pos, 'CHK_DEF_ADDED',
                ('range', str(nts.ranges)))

def chk_decimal64(old, new, oldts, newts, ctx):
    oldbasets = get_base_type(oldts)
    newbasets = get_base_type(newts)
    if newbasets.fraction_digits != oldbasets.fraction_digits:
        err_add(ctx.errors, new.pos, 'CHK_DEF_CHANGED',
                ('fraction-digits', newts.fraction_digits,
                 oldts.fraction_digits))
    # a decimal64 can only be restricted with range
    chk_range(old, new, oldts, newts, ctx)

def get_base_type(ts):
    if ts.base is None:
        return ts
    else:
        return get_base_type(ts.base)

def chk_string(old, new, oldts, newts, ctx):
    # FIXME: see types.py; we can't check the length
    return

def chk_enumeration(old, new, oldts, newts, ctx):
    # verify that all old enums are still in new, with the same values
    for name, val in oldts.enums:
        n = util.keysearch(name, 0, newts.enums)
        if n is None:
            err_add(ctx.errors, new.pos, 'CHK_DEF_REMOVED',
                    ('enum', name, old.pos))
        elif n[1] != val:
            errcode = verrcode('CHK_ENUM_VALUE_CHANGED', new)
            err_add(ctx.errors, new.pos, errcode,
                    (name, val, n[1]))

def chk_bits(old, new, oldts, newts, ctx):
    # verify that all old bits are still in new, with the same positions
    for name, pos in oldts.bits:
        n = util.keysearch(name, 0, newts.bits)
        if n is None:
            err_add(ctx.errors, new.pos, 'CHK_DEF_REMOVED',
                    ('bit', name, old.pos))
        elif n[1] != pos:
            errcode = verrcode('CHK_BIT_POSITION_CHANGED', new)
            err_add(ctx.errors, new.pos, errcode,
                    (name, pos, n[1]))

def chk_binary(old, new, oldts, newts, ctx):
    # FIXME: see types.py; we can't check the length
    return

def chk_leafref(old, new, oldts, newts, ctx):
    # verify that the path refers to the same leaf
    if (not hasattr(old.parent, 'i_leafref_ptr') or
        not hasattr(new.parent, 'i_leafref_ptr')):
        return
    if (old.parent.i_leafref_ptr is None or
        new.parent.i_leafref_ptr is None):
        return
    def cmp_node(optr, nptr):
        if optr.parent is None:
            return
        if (optr.i_module.i_modulename == nptr.i_module.i_modulename and
            optr.arg == nptr.arg):
            return cmp_node(optr.parent, nptr.parent)
        else:
            err_add(ctx.errors, new.pos, 'CHK_LEAFREF_PATH_CHANGED', ())
    cmp_node(old.parent.i_leafref_ptr[0], new.parent.i_leafref_ptr[0])

def chk_identityref(old, new, oldts, newts, ctx):
    # verify that the bases are the same
    extra = [n for n in newts.idbases]
    for oidbase in oldts.idbases:
        for nidbase in newts.idbases:
            if (nidbase.i_module.i_modulename ==
                    oidbase.i_module.i_modulename and
                    nidbase.arg.split(':')[-1] == oidbase.arg.split(':')[-1]):
                extra.remove(nidbase)
    for n in extra:
        err_add(ctx.errors, n.pos, 'CHK_DEF_ADDED',
                ('base', n.arg))

def chk_instance_identifier(old, new, oldts, newts, ctx):
    # FIXME:
    return

def chk_union(old, new, oldts, newts, ctx):
    if len(newts.types) != len(oldts.types):
        err_add(ctx.errors, new.pos, 'CHK_UNION_TYPES', ())
    else:
        for o, n in zip(oldts.types, newts.types):
            chk_type(o, n, ctx)

def chk_dummy(old, new, oldts, newts, ctx):
    return

chk_type_func = \
  {'int8': chk_integer,
   'int16': chk_integer,
   'int32': chk_integer,
   'int64': chk_integer,
   'uint8': chk_integer,
   'uint16': chk_integer,
   'uint32': chk_integer,
   'uint64': chk_integer,
   'decimal64': chk_decimal64,
   'string': chk_string,
   'boolean': chk_dummy,
   'enumeration': chk_enumeration,
   'bits': chk_bits,
   'binary': chk_binary,
   'leafref': chk_leafref,
   'identityref': chk_identityref,
   'instance-identifier': chk_instance_identifier,
   'empty': chk_dummy,
   'union': chk_union}


def verrcode(basecode, stmt):
    try:
        if stmt.i_module.i_version == '1':
            return basecode
        else:
            return basecode + '_v' + stmt.i_module.i_version
    except AttributeError:
        return basecode

def err_def_added(new, ctx):
    new_arg = new.arg
    if new.keyword == 'presence':
        new_arg = new.parent.arg
    err_add(ctx.errors, new.pos, 'CHK_DEF_ADDED', (new.keyword, new_arg))

def err_def_added2(new, node, ctx):
    err_add(ctx.errors, new.pos, 'CHK_DEF_ADDED2',
            (new.keyword, new.arg, node.keyword, node.arg))

def err_def_removed(old, newp, ctx):
    old_arg = old.arg
    if old.keyword == 'presence':
        old_arg = old.parent.arg
    err_add(ctx.errors, newp.pos, 'CHK_DEF_REMOVED',
            (old.keyword, old_arg, old.pos))

def err_def_changed(old, new, ctx):
    err_add(ctx.errors, new.pos, 'CHK_DEF_CHANGED',
            (new.keyword, new.arg, old.arg))
