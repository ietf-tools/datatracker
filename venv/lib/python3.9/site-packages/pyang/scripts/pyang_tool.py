#!/usr/bin/env python
from __future__ import absolute_import
import sys
import os
import optparse
import io
import shutil
import codecs
from pathlib import Path

import pyang
from pyang import plugin
from pyang import error
from pyang import util
from pyang import hello
from pyang import context
from pyang import repository
from pyang import statements
from pyang import syntax


def run():

    usage = """%prog [options] [<filename>...]

Validates the YANG module in <filename> (or stdin), and all its dependencies."""

    plugindirs = []
    # check for --plugindir
    args = iter(sys.argv[1:])
    for arg in args:
        if arg.startswith('--plugindir'):
            if arg == '--plugindir':
                path = next(args)
            elif arg.startswith('--plugindir='):
                path = arg[arg.index('=')+1:]
            else:
                continue
            plugindirs.append(path)
    plugin.init(plugindirs)

    fmts = {}
    xforms = {}
    for p in plugin.plugins:
        p.add_output_format(fmts)
        p.add_transform(xforms)

    optlist = [
        # use capitalized versions of std options help and version
        optparse.make_option("-h", "--help",
                             action="help",
                             help="Show this help message and exit"),
        optparse.make_option("-v", "--version",
                             action="version",
                             help="Show version number and exit"),
        optparse.make_option("-V", "--verbose",
                             action="store_true"),
        optparse.make_option("-e", "--list-errors",
                             dest="list_errors",
                             action="store_true",
                             help="Print a listing of all error and warning " \
                                 "codes and exit."),
        optparse.make_option("--print-error-code",
                             dest="print_error_code",
                             action="store_true",
                             help="On errors, print the error code instead " \
                             "of the error message."),
        optparse.make_option("--print-error-basename",
                             dest="print_error_basename",
                             action="store_true",
                             help="On errors, print the basename of files " \
                             "of the error message."),
        optparse.make_option("--msg-template",
                             dest="msg_template",
                             type="string",
                             help="Template used to display error messages. " \
                             "This is a python new-style format string used " \
                             "to format the message information with keys " \
                             "file, line, code, type and msg. " \
                             "Example: --msg-template='{file} || {line} || " \
                             "{code} || {type} || {level} || {msg}'"),
        optparse.make_option("-W",
                             dest="warnings",
                             action="append",
                             default=[],
                             metavar="WARNING",
                             help="If WARNING is 'error', treat all warnings " \
                                 "as errors, except any listed WARNING. " \
                                 "If WARNING is 'none', do not report any " \
                                 "warnings."),
        optparse.make_option("-E",
                             dest="errors",
                             action="append",
                             default=[],
                             metavar="WARNING",
                             help="Treat each WARNING as an error.  For a " \
                                 "list of warnings, use --list-errors."),
        optparse.make_option("--ignore-error",
                             dest="ignore_error_tags",
                             action="append",
                             default=[],
                             metavar="ERROR",
                             help="Ignore ERROR.  Use with care.  For a " \
                                 "list of errors, use --list-errors."),
        optparse.make_option("--ignore-errors",
                             dest="ignore_errors",
                             action="store_true",
                             help="Ignore all errors.  Use with care."),
        optparse.make_option("--canonical",
                             dest="canonical",
                             action="store_true",
                             help="Validate the module(s) according to the " \
                             "canonical YANG order."),
        optparse.make_option("--verify-revision-history",
                             dest="verify_revision_history",
                             action="store_true",
                             help="Ensure that all old revisions in the " \
                             "revision history can be found in the " \
                             "module search path."),
        optparse.make_option("--max-line-length",
                             type="int",
                             dest="max_line_len"),
        optparse.make_option("--max-identifier-length",
                             type="int",
                             dest="max_identifier_len"),
        optparse.make_option("-t", "--transform", dest="transforms",
                             default=[], action="append",
                             help="Apply transform TRANSFORM.  Supported " \
                                  "transforms are: " + ', '.join(xforms)),
        optparse.make_option("-f", "--format",
                             dest="format",
                             help="Convert to FORMAT.  Supported formats " \
                             "are: " +  ', '.join(fmts)),
        optparse.make_option("-o", "--output",
                             dest="outfile",
                             help="Write the output to OUTFILE instead " \
                             "of stdout."),
        optparse.make_option("-O", "--overwrite",
                             dest="overwrite_output_file",
                             action="store_true",
                             default=False,
                             help="Overwrite the output file, if it already exists."),
        optparse.make_option("-F", "--features",
                             metavar="FEATURES",
                             dest="features",
                             default=[],
                             action="append",
                             help="Features to support, default all. " \
                             "<modname>:[<feature>,]*"),
        optparse.make_option("-X", "--exclude-features",
                             metavar="EXCLUDE_FEATURES",
                             dest="exclude_features",
                             default=[],
                             action="append",
                             help="Features not to support, default none. " \
                                  "<modname>:[<feature>,]*"),
        optparse.make_option("", "--max-status",
                             metavar="MAXSTATUS",
                             dest="max_status",
                             help="Max status to support, one of: " \
                             "current, deprecated, obsolete"),
        optparse.make_option("", "--deviation-module",
                             metavar="DEVIATION",
                             dest="deviations",
                             default=[],
                             action="append",
                             help="Deviation module"),
        optparse.make_option("-p", "--path",
                             dest="path",
                             default=[],
                             action="append",
                             help=os.pathsep + "-separated search path for yin"
                             " and yang modules"),
        optparse.make_option("--plugindir",
                             dest="plugindir",
                             help="Load pyang plugins from PLUGINDIR"),
        optparse.make_option("--strict",
                             dest="strict",
                             action="store_true",
                             help="Force strict YANG compliance."),
        optparse.make_option("--lax-quote-checks",
                             dest="lax_quote_checks",
                             action="store_true",
                             help="Lax check of backslash in quoted strings."),
        optparse.make_option("--lax-xpath-checks",
                             dest="lax_xpath_checks",
                             action="store_true",
                             help="Lax check of XPath expressions."),
        optparse.make_option("--trim-yin",
                             dest="trim_yin",
                             action="store_true",
                             help="In YIN input modules, trim whitespace "
                             "in textual arguments."),
        optparse.make_option("-L", "--hello",
                             dest="hello",
                             action="store_true",
                             help="Filename of a server's hello message is "
                             "given instead of module filename(s)."),
        optparse.make_option("--implicit-hello-deviations",
                             dest="implicit_hello_deviations",
                             action="store_true",
                             help="Attempt to parse all deviations from hello "
                             "message regardless of declaration."),
        optparse.make_option("--keep-comments",
                             dest="keep_comments",
                             action="store_true",
                             help="Pyang will not discard comments; \
                                   has effect if the output plugin can \
                                   handle comments."),
        optparse.make_option("--no-path-recurse",
                             dest="no_path_recurse",
                             action="store_true",
                             help="Do not recurse into directories in the \
                                   yang path."),
        ]

    optparser = optparse.OptionParser(usage, add_help_option = False)
    optparser.version = '%prog ' + pyang.__version__
    optparser.add_options(optlist)

    for p in plugin.plugins:
        p.add_opts(optparser)

    (o, args) = optparser.parse_args()

    if o.outfile is not None and o.format is None:
        sys.stderr.write("no format specified\n")
        sys.exit(1)

    filenames = args

    # Parse hello if present
    if o.hello:
        if len(filenames) > 1:
            sys.stderr.write("multiple hello files given\n")
            sys.exit(1)
        if filenames:
            try:
                fd = open(filenames[0], "rb")
            except IOError as ex:
                sys.stderr.write("error %s: %s\n" % (filenames[0], ex))
                sys.exit(1)
        else:
            fd = sys.stdin.buffer
        hel = hello.HelloParser().parse(fd)

    path = os.pathsep.join(o.path)

    # add standard search path
    if len(o.path) == 0:
        path = "."
    else:
        path += os.pathsep + "."

    repos = repository.FileRepository(path, no_path_recurse=o.no_path_recurse,
                                      verbose=o.verbose)

    ctx = context.Context(repos)

    ctx.opts = o
    ctx.canonical = o.canonical
    ctx.verify_revision_history = o.verify_revision_history
    ctx.max_line_len = o.max_line_len
    ctx.max_identifier_len = o.max_identifier_len
    ctx.trim_yin = o.trim_yin
    ctx.lax_xpath_checks = o.lax_xpath_checks
    ctx.lax_quote_checks = o.lax_quote_checks
    ctx.strict = o.strict
    ctx.max_status = o.max_status

    # make a map of features to support, per module
    if o.hello:
        for mn, rev in hel.yang_modules():
            ctx.features[mn] = hel.get_features(mn)
    for f in ctx.opts.features:
        (modulename, features) = parse_features_string(f)
        ctx.features[modulename] = features
    for f in ctx.opts.exclude_features:
        (modulename, features) = parse_features_string(f)
        if modulename in ctx.features:
            sys.stderr.write("module %s can't have both --hello / --features "
                             "and --exclude-features\n" % modulename)
            sys.exit(1)
        ctx.exclude_features[modulename] = features

    for p in plugin.plugins:
        p.setup_ctx(ctx)

    if o.list_errors is True:
        for tag in error.error_codes:
            (level, fmt) = error.error_codes[tag]
            if error.is_warning(level):
                print("Warning: %s" % tag)
            elif error.allow_warning(level):
                print("Minor Error:   %s" % tag)
            else:
                print("Error:   %s" % tag)
            print("Message: %s" % fmt)
            print("")
        sys.exit(0)

    # patch the error spec so that -W errors are treated as warnings
    for w in o.warnings:
        if w in error.error_codes:
            (level, wstr) = error.error_codes[w]
            if error.allow_warning(level):
                error.error_codes[w] = (4, wstr)

    xform_objs = []
    for transform in o.transforms:
        if transform not in xforms:
            sys.stderr.write("unsupported transform '%s'\n" % transform)
        else:
            xform_obj = xforms[transform]
            xform_obj.setup_xform(ctx)
            xform_objs.append(xform_obj)
    if len(xform_objs) != len(o.transforms):
        sys.exit(1)

    if o.format is not None:
        if o.format not in fmts:
            sys.stderr.write("unsupported format '%s'\n" % o.format)
            sys.exit(1)
        emit_obj = fmts[o.format]
        if o.keep_comments and emit_obj.handle_comments:
            ctx.keep_comments = True
        emit_obj.setup_fmt(ctx)
    else:
        emit_obj = None

    xform_and_emit_objs = xform_objs[:]
    if emit_obj is not None:
        xform_and_emit_objs.append(emit_obj)

    for p in plugin.plugins:
        p.pre_load_modules(ctx)

    exit_code = 0
    modules = []

    if o.hello:
        ctx.capabilities = hel.registered_capabilities()
        modules_missing = False
        for mn, rev in hel.yang_modules():
            mod = ctx.search_module(error.Position(''), mn, rev)
            if mod is None:
                emarg = mn
                if rev:
                    emarg += "@" + rev
                sys.stderr.write(
                    "module '%s' specified in hello not found.\n" % emarg)
                modules_missing = True
            else:
                modules.append(mod)
        if modules_missing is True:
            sys.exit(1)
    else:
        if len(filenames) == 0:
            text = sys.stdin.read()
            module = ctx.add_module('<stdin>', text)
            if module is None:
                exit_code = 1
            else:
                modules.append(module)
        if (len(filenames) > 1 and
            emit_obj is not None and
            not emit_obj.multiple_modules):
            sys.stderr.write("too many files to convert\n")
            sys.exit(1)

        for filename in filenames:
            try:
                fd = io.open(filename, "r", encoding="utf-8")
                text = fd.read()
                if o.verbose:
                    util.report_file_read(filename, "(CL)")
            except IOError as ex:
                sys.stderr.write("error %s: %s\n" % (filename, ex))
                sys.exit(1)
            except UnicodeDecodeError as ex:
                s = str(ex).replace('utf-8', 'utf8')
                sys.stderr.write("%s: unicode error: %s\n" % (filename, s))
                sys.exit(1)
            m = syntax.re_filename.search(Path(filename).name)
            ctx.yin_module_map = {}
            if m is not None:
                name, rev, in_format = m.groups()
                name = os.path.basename(name)
                module = ctx.add_module(filename, text, in_format, name, rev,
                                        expect_failure_error=False,
                                        primary_module=True)
            else:
                module = ctx.add_module(filename, text, primary_module=True)
            if module is None:
                exit_code = 1
            else:
                modules.append(module)

    modulenames = []
    for m in modules:
        modulenames.append(m.arg)
        for s in m.search('include'):
            modulenames.append(s.arg)

    # apply deviations
    for filename in ctx.opts.deviations:
        try:
            fd = io.open(filename, "r", encoding="utf-8")
            text = fd.read()
        except IOError as ex:
            sys.stderr.write("error %s: %s\n" % (filename, ex))
            sys.exit(1)
        except UnicodeDecodeError as ex:
            s = str(ex).replace('utf-8', 'utf8')
            sys.stderr.write("%s: unicode error: %s\n" % (filename, s))
            sys.exit(1)
        m = ctx.add_module(filename, text)
        if m is not None:
            ctx.deviation_modules.append(m)
    if o.hello and o.implicit_hello_deviations:
        for deviation_module in hel.yang_implicit_deviation_modules():
            m = ctx.search_module(error.Position(''), deviation_module)
            if m is not None:
                ctx.deviation_modules.append(m)

    for p in plugin.plugins:
        p.pre_validate_ctx(ctx, modules)

    if len(xform_and_emit_objs) > 0 and len(modules) > 0:
        for obj in xform_and_emit_objs:
            obj.pre_validate(ctx, modules)

    def ctx_validate_and_prune():
        ctx.validate()
        for m_ in modules:
            m_.prune()

    ctx_validate_and_prune()

    # verify the given features (also update ctx.features and ctx.exclude_
    # features to be actual included / excluded features)
    for m in modules:
        if m.arg in ctx.features:
            if m.arg not in ctx.exclude_features:
                ctx.exclude_features[m.arg] = list(m.i_features.keys())
            for f in ctx.features[m.arg]:
                if f not in m.i_features:
                    sys.stderr.write("unknown feature %s in module %s\n" %
                                     (f, m.arg))
                    sys.exit(1)
                if f in ctx.exclude_features[m.arg]:
                    ctx.exclude_features[m.arg].remove(f)
        if m.arg in ctx.exclude_features:
            if m.arg not in ctx.features:
                ctx.features[m.arg] = list(m.i_features.keys())
            for f in ctx.exclude_features[m.arg]:
                if f not in m.i_features:
                    sys.stderr.write("unknown feature %s in module %s\n" %
                                     (f, m.arg))
                    sys.exit(1)
                if f in ctx.features[m.arg]:
                    ctx.features[m.arg].remove(f)

    # transform modules
    if len(xform_objs) > 0 and len(modules) > 0:
        for xform_obj in xform_objs:
            try:
                if not xform_obj.transform(ctx, modules):
                    ctx.internal_reset()
                    for module in modules:
                        module.internal_reset()
                        ctx.add_parsed_module(module)
                        ctx_validate_and_prune()
            except error.TransformError as e:
                if e.msg != "":
                    sys.stderr.write(e.msg + '\n')
                sys.exit(e.exit_code)

    if len(xform_and_emit_objs) > 0 and len(modules) > 0:
        for obj in xform_and_emit_objs:
            obj.post_validate(ctx, modules)

    for p in plugin.plugins:
        p.post_validate_ctx(ctx, modules)

    def keyfun(e):
        if e[0].ref == filenames[0]:
            return 0
        else:
            return 1

    ctx.errors.sort(key=lambda e: (e[0].ref, e[0].line))
    if len(filenames) > 0:
        # first print error for the first filename given
        ctx.errors.sort(key=keyfun)

    if o.ignore_errors:
        ctx.errors = []

    for epos, etag, eargs in ctx.errors:
        if etag in o.ignore_error_tags:
            continue
        if (ctx.implicit_errors is False and
            epos.top is not None and
            epos.top.arg not in modulenames and
            (not hasattr(epos.top, 'i_modulename') or
             epos.top.i_modulename not in modulenames) and
            epos.ref not in filenames):
            # this module was added implicitly (by import); skip this error
            # the code includes submodules
            continue
        elevel = error.err_level(etag)
        if error.is_warning(elevel) and etag not in o.errors:
            kind = "warning"
            if 'error' in o.warnings and etag not in o.warnings:
                kind = "error"
                exit_code = 1
            elif 'none' in o.warnings:
                continue
        else:
            kind = "error"
            exit_code = 1
        emsg = etag if o.print_error_code else error.err_to_str(etag, eargs)

        if o.msg_template is not None:
            try:
                sys.stderr.write(str(o.msg_template).format(
                    file=epos.ref, line=epos.line,
                    code=etag, type=kind,
                    msg=error.err_to_str(etag, eargs),
                    level=elevel) + '\n')
            except KeyError as error_msg:
                sys.stderr.write(
                    "unsupported key %s in msg-template\n" % error_msg)
                sys.exit(1)
        else:
            sys.stderr.write('%s: %s: %s\n' %
                             (epos.label(o.print_error_basename), kind, emsg))

    if emit_obj is not None and len(modules) > 0:
        tmpfile = None
        if o.outfile is None:
            fd = sys.stdout
        else:
            tmpfile = o.outfile + ".tmp"
            fd = io.open(tmpfile, "w+", encoding="utf-8")
        try:
            emit_obj.emit(ctx, modules, fd)
        except error.EmitError as e:
            if e.msg != "":
                sys.stderr.write(e.msg + '\n')
            if tmpfile is not None:
                fd.close()
                os.remove(tmpfile)
            sys.exit(e.exit_code)
        except:
            if tmpfile is not None:
                fd.close()
                os.remove(tmpfile)
            raise
        if tmpfile is not None:
            fd.close()
            if not o.overwrite_output_file:
                os.rename(tmpfile, o.outfile)
            else:
                shutil.copyfile(tmpfile, o.outfile)
                os.remove(tmpfile)

    sys.exit(exit_code)

def parse_features_string(s):
    if s.find(':') == -1:
        return s, []
    else:
        modulename, rest = s.split(':', 1)
        if rest == '':
            return modulename, []
        else:
            features = rest.split(',')
            return modulename, features

if __name__ == '__main__':
    run()
