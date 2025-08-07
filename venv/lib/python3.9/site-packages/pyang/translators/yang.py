"""YANG output plugin"""

import optparse

from .. import plugin
from .. import util
from .. import grammar

def pyang_plugin_init():
    plugin.register_plugin(YANGPlugin())

class YANGPlugin(plugin.PyangPlugin):
    def add_output_format(self, fmts):
        fmts['yang'] = self
        self.handle_comments = True

    def add_opts(self, optparser):
        optlist = [
            optparse.make_option("--yang-canonical",
                                 dest="yang_canonical",
                                 action="store_true",
                                 help="Print in canonical order"),
            optparse.make_option("--yang-remove-unused-imports",
                                 dest="yang_remove_unused_imports",
                                 action="store_true"),
            optparse.make_option("--yang-remove-comments",
                                 dest="yang_remove_comments",
                                 action="store_true"),
            optparse.make_option("--yang-line-length",
                                 type="int",
                                 dest="yang_line_length",
                                 help="Maximum line length"),
            ]
        g = optparser.add_option_group("YANG output specific options")
        g.add_options(optlist)

    def setup_fmt(self, ctx):
        ctx.implicit_errors = False
        ctx.keep_arg_substrings = True
        ctx.keep_comments = True
        if ctx.opts.yang_remove_comments:
            ctx.keep_comments = False

    def emit(self, ctx, modules, fd):
        module = modules[0]
        emit_yang(ctx, module, fd)

def emit_yang(ctx, module, fd):
    link_list = {}
    # make the stmt tree to a link_list, in order to peek the next stmt
    make_link_list(ctx, module, link_list)
    link_list['last'] = None

    emit_stmt(ctx, module, fd, 0, None, None, False, '', '  ', link_list)

# always add newline between keyword and argument
_force_newline_arg = ('description', 'reference', 'contact', 'organization')

# do not quote these arguments
_non_quote_arg_type = ('identifier', 'identifier-ref', 'boolean', 'integer',
                       'non-negative-integer', 'max-value',
                       'date', 'ordered-by-arg',
                       'fraction-digits-arg', 'deviate-arg', 'version',
                       'status-arg')

_maybe_quote_arg_type = ('enum-arg', )

# add extra blank line after these, when they occur on the top level
_keyword_with_trailing_blank_line_toplevel = (
    'identity',
    'feature',
    'extension',
    'rpc',
    'notification',
    'augment',
    'deviation',
    )

# always add extra blank line after these
_keyword_with_trailing_blank_line = (
    'typedef',
    'grouping',
    )

# use single quote for the arguments to these keywords (if possible)
_keyword_prefer_single_quote_arg = (
    'must',
    'when',
    'pattern',
)

_keyword_with_path_arg = (
    'augment',
    'refine',
    'deviation',
    'path',
)

_kwd_class = {
    'yang-version': 'header',
    'namespace': 'header',
    'prefix': 'header',
    'belongs-to': 'header',
    'organization': 'meta',
    'contact': 'meta',
    'description': 'meta',
    'reference': 'meta',
    'import': 'linkage',
    'include': 'linkage',
    'revision': 'revision',
    'typedef': 'defs',
    'grouping': 'defs',
    'identity': 'defs',
    'feature': 'defs',
    'extension': 'defs',
    '_comment': 'comment',
    'augment': 'augment',
    'rpc': 'rpc',
    'notification': 'notification',
    'deviation': 'deviation',
    'module': None,
    'submodule': None,
}
def get_kwd_class(keyword):
    if util.is_prefixed(keyword):
        return 'extension'
    else:
        try:
            return _kwd_class[keyword]
        except KeyError:
            return 'body'

_need_quote = (
    " ", "}", "{", ";", '"', "'",
    "\n", "\t", "\r", "//", "/*", "*/",
    )

_need_single_quote = (
    '"', "\n", "\t", "\r",
    )

def make_link_list(ctx, stmt, link_list):
    if 'last' in link_list:
        link_list[ link_list['last'] ] = stmt
    link_list['last'] = stmt

    if len(stmt.substmts) > 0:
        if ctx.opts.yang_canonical:
            substmts = grammar.sort_canonical(stmt.keyword, stmt.substmts)
        else:
            substmts = stmt.substmts
        for i, s in enumerate(substmts, start=1):
            make_link_list(ctx, s, link_list)

def emit_stmt(ctx, stmt, fd, level, prev_kwd, prev_kwd_class, islast,
              indent, indentstep, link_list):
    if is_line_end_comment(stmt):
        # line end comments has been printed after last meaningful statement
        return

    if ctx.opts.yang_remove_unused_imports and stmt.keyword == 'import':
        for p in stmt.parent.i_unused_prefixes:
            if stmt.parent.i_unused_prefixes[p] == stmt:
                return

    max_line_len = ctx.opts.yang_line_length
    if util.is_prefixed(stmt.raw_keyword):
        (prefix, identifier) = stmt.raw_keyword
        keywordstr = prefix + ':' + identifier
    else:
        keywordstr = stmt.keyword

    kwd_class = get_kwd_class(stmt.keyword)
    if ((level == 1 and
         kwd_class != prev_kwd_class and kwd_class != 'extension') and
        not ((level == 1 and prev_kwd in
              _keyword_with_trailing_blank_line_toplevel) or
             prev_kwd in _keyword_with_trailing_blank_line)):
        fd.write('\n')

    if stmt.keyword == '_comment':
        emit_comment(stmt.arg, fd, indent)
        return

    fd.write(indent + keywordstr)
    arg_on_new_line = False
    if len(stmt.substmts) == 0:
        eol = ';'
    else:
        eol = ' {'
    if stmt.arg is not None:
        # line_len is length of line w/o arg but with quotes and space before
        # the arg
        line_len = len(indent) + len(keywordstr) + 1 + 2 + len(eol)
        if (stmt.keyword in _keyword_prefer_single_quote_arg
            and "'" not in stmt.arg
            and '\n' not in stmt.arg):
            # print with single quotes
            if hasattr(stmt, 'arg_substrings') and len(stmt.arg_substrings) > 1:
                # the arg was already split into multiple lines, keep them
                emit_multi_str_arg(keywordstr, stmt.arg_substrings, fd, "'",
                                   indent, indentstep, max_line_len, line_len)
            elif not need_new_line(max_line_len, line_len, stmt.arg):
                # fits into a single line
                fd.write(" '" + stmt.arg + "'")
            else:
                # otherwise, print on new line, don't check line length
                # since we can't break the string into multiple lines
                fd.write('\n' + indent + indentstep)
                fd.write("'" + stmt.arg + "'")
                arg_on_new_line = True
        elif hasattr(stmt, 'arg_substrings') and len(stmt.arg_substrings) > 1:
            # the arg was already split into multiple lines, keep them
            emit_multi_str_arg(keywordstr, stmt.arg_substrings, fd, '"',
                               indent, indentstep, max_line_len, line_len)
        elif '\n' in stmt.arg:
            # the arg string contains newlines; print it as double quoted
            arg_on_new_line = emit_arg(keywordstr, stmt, fd, indent, indentstep,
                                       max_line_len, line_len - 1 - len(eol))
        elif stmt.keyword in _keyword_with_path_arg:
            # special code for path argument; pretty-prints a long path with
            # line breaks
           arg_on_new_line = emit_path_arg(keywordstr, stmt.arg, fd,
                                           indent, max_line_len, line_len, eol)
        elif stmt.keyword in grammar.stmt_map:
            (arg_type, _subspec) = grammar.stmt_map[stmt.keyword]
            if (arg_type in _non_quote_arg_type or
                (arg_type in _maybe_quote_arg_type and
                 not need_quote(stmt.arg))):
                # minus 2 since we don't quote
                if not need_new_line(max_line_len, line_len-2, stmt.arg):
                    fd.write(' ' + stmt.arg)
                else:
                    fd.write('\n' + indent + indentstep + stmt.arg)
                    arg_on_new_line = True
            else:
                arg_on_new_line = emit_arg(keywordstr, stmt, fd,
                                           indent, indentstep,
                                           max_line_len, line_len)
        else:
            arg_on_new_line = emit_arg(keywordstr, stmt, fd, indent, indentstep,
                                       max_line_len, line_len)
    fd.write(eol)

    next_stmt = link_list.get(stmt, None)
    emit_line_end_comments(stmt, next_stmt, link_list, fd, False)
    fd.write('\n')

    if len(stmt.substmts) > 0:
        if ctx.opts.yang_canonical:
            substmts = grammar.sort_canonical(stmt.keyword, stmt.substmts)
        else:
            substmts = stmt.substmts
        if level == 0:
            kwd_class = 'header'
        prev_kwd = None
        for i, s in enumerate(substmts, start=1):
            n = 1
            if arg_on_new_line:
                # arg was printed on a new line, increase indentation
                ## The idea here was to do:
                ##    some-keyword
                ##      "arg-on-new-line" {
                ##        some-other-keyword
                ##      ^^ <- extra indentation here
                ## But this is not a good idea.
                pass
#                n = 2

            link_list['last'] = s
            emit_stmt(ctx, s, fd, level + 1, prev_kwd, kwd_class,
                      i == len(substmts),
                      indent + (indentstep * n), indentstep, link_list)
            if not is_line_end_comment(s):
                kwd_class = get_kwd_class(s.keyword)
                prev_kwd = s.keyword
        fd.write(indent + '}')
        last_substmt = link_list['last']
        if last_substmt in link_list:
            last_substmt = link_list[last_substmt]
        emit_line_end_comments(stmt, last_substmt, link_list, fd, True)
        fd.write('\n')

    if (not islast and
        ((level == 1 and stmt.keyword in
          _keyword_with_trailing_blank_line_toplevel) or
         stmt.keyword in _keyword_with_trailing_blank_line)):
        fd.write('\n')

def emit_line_end_comments(stmt, next_stmt, link_list, fd, same_level):
    """
    emit line end comment stmts, there are some cases:
    1. after "{"
    2. after "}"
    3. multi line end comments should be printed in oneline
    """
    while next_stmt is not None:
        is_sub_level = False
        if not same_level:
            is_sub_level = next_stmt.stmt_parent == stmt
        if (is_line_end_comment(next_stmt) and
                (next_stmt.stmt_parent == stmt.stmt_parent or (not same_level and is_sub_level))):
            fd.write(' ' + next_stmt.arg)
            if next_stmt in link_list:
                next_stmt = link_list[next_stmt]
            else:
                return
        else:
            return

def is_line_end_comment(stmt):
    return stmt.keyword == '_comment' and stmt.is_line_end and not stmt.is_multi_line

def need_new_line(max_line_len, line_len, arg):
    eol = arg.find('\n')
    if eol == -1:
        eol = len(arg)
    if max_line_len is not None and line_len + eol > max_line_len:
        return True
    else:
        return False

def emit_multi_str_arg(keywordstr, strs, fd, pref_q,
                       indent, indentstep, max_line_len,
                       line_len):
    # we want to align all strings on the same column; check if
    # we can print w/o a newline
    need_new_line = False
    if max_line_len is not None:
        for s, q in strs:
            q = select_quote(s, q, pref_q)
            if q == '"':
                s = escape_str(s)
            if line_len + len(s) > max_line_len:
                need_new_line = True
                break
    if need_new_line:
        fd.write('\n' + indent + indentstep)
        prefix = (len(indent) - 2) * ' ' + indentstep + '+ '
    else:
        fd.write(' ')
        prefix = indent + ((len(keywordstr) - 1) * ' ') + '+ '
    # print first substring
    (s, q) = strs[0]
    q = select_quote(s, q, pref_q)
    if q == '"':
        s = escape_str(s)
    fd.write("%s%s%s\n" % (q, s, q))
    # then print the rest with the prefix and a newline at the end
    for s, q in strs[1:-1]:
        q = select_quote(s, q, pref_q)
        if q == '"':
            s = escape_str(s)
        fd.write("%s%s%s%s\n" % (prefix, q, s, q))
    # then print last substring with prefix but no newline
    (s, q) = strs[-1]
    q = select_quote(s, q, pref_q)
    if q == '"':
        s = escape_str(s)
    fd.write("%s%s%s%s" % (prefix, q, s, q))

    return need_new_line

def select_quote(s, q, pref_q):
    if pref_q == q:
        return q
    elif pref_q == "'":
        if "'" not in s:
            # the string was double quoted, but it wasn't necessary,
            # use preferred single quote
            return "'"
        else:
            # the string was double quoted for a reason, keep it
            return '"'
    elif q == "'":
        if need_single_quote(s):
            # the string was single quoted for a reason, keep it
            return "'"
        else:
            # the string was single quoted but it wasn't necessary,
            # use preferred double quote
            return '"'

def escape_str(s):
    s = s.replace('\\', r'\\')
    s = s.replace('"', r'\"')
    s = s.replace('\t', r'\t')
    return s

def emit_path_arg(keywordstr, arg, fd, indent, max_line_len, line_len, eol):
    """Heuristically pretty print a path argument"""

    quote = '"'

    arg = escape_str(arg)

    if not need_new_line(max_line_len, line_len, arg):
        fd.write(" " + quote + arg + quote)
        return False

    num_chars = max_line_len - line_len
    if num_chars <= 0:
        # really small max_line_len; we give up
        fd.write(" " + quote + arg + quote)
        return False

    while num_chars > 2 and arg[num_chars - 1:num_chars] != '/':
        num_chars -= 1
    if arg[num_chars - 1:num_chars] == '/':
        num_chars -= 1
    fd.write(" " + quote + arg[:num_chars] + quote)
    arg = arg[num_chars:]
    keyword_cont = ((len(keywordstr) - 1) * ' ') + '+'
    while arg != '':
        line_len = len(
            "%s%s %s%s%s%s" % (indent, keyword_cont, quote, arg, quote, eol))
        if line_len <= max_line_len:
            fd.write('\n' + indent + keyword_cont + " " +
                     quote + arg + quote)
            arg = ''
        else:
            # we need to split
            num_chars = len(arg) - (line_len - max_line_len)
            while num_chars > 2 and arg[num_chars - 1:num_chars] != '/':
                num_chars -= 1
            if arg[num_chars - 1:num_chars] == '/':
                # split on /
                num_chars -= 1
            else:
                # print as much as possible
                num_chars = len(arg) - (line_len - max_line_len)
            fd.write('\n' + indent + keyword_cont + " " +
                     quote + arg[:num_chars] + quote)
            arg = arg[num_chars:]

def emit_arg(keywordstr, stmt, fd, indent, indentstep, max_line_len, line_len):
    """Heuristically pretty print the argument string with double quotes"""
    arg = escape_str(stmt.arg)
    lines = arg.splitlines(True)
    if len(lines) <= 1:
        if len(arg) > 0 and arg[-1] == '\n':
            arg = arg[:-1] + r'\n'
        if (stmt.keyword in _force_newline_arg or
            need_new_line(max_line_len, line_len, arg)):
            fd.write('\n' + indent + indentstep + '"' + arg + '"')
            return True
        else:
            fd.write(' "' + arg + '"')
            return False
    else:
        need_nl = False
        if stmt.keyword in _force_newline_arg:
            need_nl = True
        elif len(keywordstr) > 8:
            # Heuristics: multi-line after a "long" keyword looks better
            # than after a "short" keyword (compare 'when' and 'error-message')
            need_nl = True
        else:
            for line in lines:
                if need_new_line(max_line_len, line_len, line):
                    need_nl = True
                    break
        if need_nl:
            fd.write('\n' + indent + indentstep)
            prefix = indent + indentstep
        else:
            fd.write(' ')
            prefix = indent + len(keywordstr) * ' ' + ' '
        fd.write('"' + lines[0])
        for line in lines[1:-1]:
            if line[0] == '\n':
                fd.write('\n')
            else:
                fd.write(prefix + ' ' + line)
        # write last line
        fd.write(prefix + ' ' + lines[-1])
        if lines[-1][-1] == '\n':
            # last line ends with a newline, indent the ending quote
            fd.write(prefix + '"')
        else:
            fd.write('"')
        return True

def emit_comment(comment, fd, indent):
    lines = comment.splitlines(True)
    for x in lines:
        if x[0] == '*':
            fd.write(indent + ' ' + x)
        else:
            fd.write(indent + x)
    fd.write('\n')

def need_quote(arg):
    for ch in _need_quote:
        if arg.find(ch) != -1:
            return True
    return False

def need_single_quote(arg):
    for ch in _need_single_quote:
        if arg.find(ch) != -1:
            return True
    return False
