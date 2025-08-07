""" This module implements a generic YANG parser.

The parser does not check any keywords or grammar.
"""
import collections
import sys
from . import error
from . import util
from . import statements
from . import syntax

class YangTokenizer(object):
    def __init__(self, text, pos, errors,
                 max_line_len=None, keep_comments=False,
                 strict_quoting = False):
        self.lines = collections.deque(text.splitlines(True))
        self.pos = pos
        self.buf = ''
        self.offset = 0
        """Position on line.  Used to remove leading whitespace from strings."""

        self.max_line_len = max_line_len
        if self.max_line_len == 0:
            self.max_line_len = None
        # if keep_comments is True, we return comments as separate statements.
        # we currently only keep comments between statement, i.e., we always
        # ignore comments between a keyword and its argument, and within
        # concatenated strings.
        self.keep_comments = keep_comments
        self.errors = errors
        self.is_1_1 = False
        self.strict_quoting = strict_quoting

    def readline(self):
        if len(self.lines) == 0:
            raise error.Eof
        self.buf = self.lines.popleft()
        self.pos.line += 1
        self.offset = 0
        if self.max_line_len is not None:
            curlen = len(self.buf)
            if curlen >= 1 and self.buf[-1] == '\n':
                if curlen >= 2 and self.buf[-2] == '\r':
                    curlen -= 2
                else:
                    curlen -= 1
            if curlen > self.max_line_len:
                error.err_add(self.errors, self.pos, 'LONG_LINE',
                              (curlen, self.max_line_len))

    def set_buf(self, i):
        self.offset = self.offset + i
        self.buf = self.buf[i:]

    def skip(self, keep_comments=False):
        """Skip whitespace and count position"""
        buflen = len(self.buf)

        while True:
            self.buf = self.buf.lstrip()
            if self.buf == '':
                self.readline()
                buflen = len(self.buf)
            else:
                self.offset += (buflen - len(self.buf))
                break

        # do not keep comments in the syntax tree
        if not keep_comments:
            # skip line comment
            if self.buf[0] == '/':
                if self.buf[1] == '/':
                    self.readline()
                    return self.skip(keep_comments=keep_comments)
            # skip block comment
                elif self.buf[1] == '*':
                    i = self.buf.find('*/')
                    while i == -1:
                        self.readline()
                        i = self.buf.find('*/')
                    self.set_buf(i+2)
                    return self.skip(keep_comments=keep_comments)

    def get_comment(self, last_line):
        """ret: string()"""
        is_multi_line = False
        is_line_end = False
        self.skip(keep_comments=True)
        offset = self.offset
        m = syntax.re_comment.match(self.buf)
        if m is None:
            return None, is_line_end, is_multi_line
        else:
            cmt = m.group(0)
            self.set_buf(m.end())
            is_line_end = (last_line == self.pos.line)
            # look for a multiline comment
            if cmt[:2] == '/*' and cmt[-2:] != '*/':
                i = self.buf.find('*/')
                is_multi_line = True
                while i == -1:
                    self.readline()
                    # remove at most the same number of whitespace as
                    # the comment start was indented
                    j = 0
                    while (j < offset and j < len(self.buf) and
                           self.buf[j].isspace()):
                        j = j + 1
                    self.buf = self.buf[j:]
                    cmt += '\n'+self.buf.replace('\n','')
                    i = self.buf.find('*/')
                self.set_buf(i+2)
            return cmt, is_line_end, is_multi_line

    def get_keyword(self):
        """ret: identifier | (prefix, identifier)"""
        self.skip()

        m = syntax.re_keyword.match(self.buf)
        if m is None:
            error.err_add(self.errors, self.pos,
                          'SYNTAX_ERROR', 'illegal keyword: ' + self.buf)
            raise error.Abort
        else:
            self.set_buf(m.end())
            # check the separator
            if (self.buf[0].isspace() or
                (self.buf[0] == '/' and self.buf[1] in ('/', '*')) or
                (self.buf[0] in (';','{'))):
                pass
            else:
                error.err_add(self.errors, self.pos,
                              'SYNTAX_ERROR', 'expected separator, got: "' +
                              self.buf[:6] + '..."')
                raise error.Abort

            if m.group(2) is None: # no prefix
                return m.group(3)
            else:
                return (m.group(2), m.group(3))

    def peek(self):
        """Return next real character in input stream.

        Skips whitespace and comments, and returns next character
        without consuming it.  Use skip_tok() to consume the characater.
        """
        self.skip(self.keep_comments)
        try:
            return self.buf[0]
        except:
            raise error.Eof

    def skip_tok(self):
        self.skip(self.keep_comments)
        self.set_buf(1)

    def get_strings(self, need_quote=False):
        """ret: string"""
        self.skip()

        if self.buf[0] == ';' or self.buf[0] == '{' or self.buf[0] == '}':
            error.err_add(self.errors, self.pos,
                          'EXPECTED_ARGUMENT', self.buf[0])
            raise error.Abort
        if self.buf[0] == '"' or self.buf[0] == "'":
            # for double-quoted string,  loop over string and translate
            # escaped characters.  also strip leading whitespace as
            # necessary.
            # for single-quoted string, keep going until end quote is found.
            quote_char = self.buf[0]
            # collect output in strs (list of strings)
            strs = []
            res = []
            # remember position of " character
            indentpos = self.offset
            i = 1
            while True:
                buflen = len(self.buf)
                start = i
                while i < buflen:
                    if self.buf[i] == quote_char:
                        # end-of-string; copy the buf to output
                        res.append(self.buf[start:i])
                        strs.append((''.join(res), quote_char))
                        # and trim buf
                        self.set_buf(i+1)
                        # check for '+' operator
                        self.skip()
                        if self.buf[0] == '+':
                            self.set_buf(1)
                            self.skip()
                            nstrs = self.get_strings(need_quote=True)
                            strs.extend(nstrs)
                        return strs
                    elif (quote_char == '"' and
                          self.buf[i] == '\\' and i < (buflen-1)):
                        # check for special characters
                        special = None
                        if self.buf[i+1] == 'n':
                            special = '\n'
                        elif self.buf[i+1] == 't':
                            special = '\t'
                        elif self.buf[i+1] == '\"':
                            special = '\"'
                        elif self.buf[i+1] == '\\':
                            special = '\\'
                        elif self.strict_quoting and self.is_1_1:
                            error.err_add(self.errors, self.pos,
                                          'ILLEGAL_ESCAPE', self.buf[i+1])
                            raise error.Abort
                        elif self.strict_quoting:
                            error.err_add(self.errors, self.pos,
                                          'ILLEGAL_ESCAPE_WARN', self.buf[i+1])
                        if special is not None:
                            res.append(self.buf[start:i])
                            res.append(special)
                            i = i + 1
                            start = i + 1
                    i = i + 1
                # end-of-line
                # first strip trailing whitespace in double quoted strings
                # pre: self.buf[i-1] == '\n'
                if i > 2 and self.buf[i-2] == '\r':
                    j = i - 3
                else:
                    j = i - 2
                k = j
                while j >= 0 and self.buf[j].isspace():
                    j = j - 1
                if j != k: # we found trailing whitespace
                    s = self.buf[start:j+1] + self.buf[k+1:i]
                else:
                    s = self.buf[start:i]
                res.append(s)
                self.readline()
                i = 0
                indent = 0
                if quote_char == '"':
                    # skip whitespace used for indentation
                    buflen = len(self.buf)
                    while (i < buflen and self.buf[i].isspace() and
                           indent <= indentpos):
                        if self.buf[i] == '\t':
                            indent = indent + 8
                        else:
                            indent = indent + 1
                        i = i + 1
                    if indent > indentpos + 1:
                        res.append(' ' * (indent - indentpos - 1))
                    elif i == buflen:
                        # whitespace only on this line; keep it as is
                        i = 0
        elif need_quote is True:
            error.err_add(self.errors, self.pos, 'EXPECTED_QUOTED_STRING', ())
            raise error.Abort
        else:
            # unquoted string
            buflen = len(self.buf)
            i = 0
            while i < buflen:
                if (self.buf[i].isspace() or self.buf[i] == ';' or
                    self.buf[i] == '"' or self.buf[i] == "'" or
                    self.buf[i] == '{' or self.buf[i] == '}' or
                    self.buf[i:i+2] == '//' or self.buf[i:i+2] == '/*' or
                    self.buf[i:i+2] == '*/'):
                    res = self.buf[:i]
                    self.set_buf(i)
                    return [(res, '')]
                i = i + 1

class YangParser(object):
    def __init__(self, extra=None):
        pass

    def parse(self, ctx, ref, text):
        """Parse the string `text` containing a YANG statement.

        Return a Statement on success or None on failure
        """

        self.ctx = ctx
        self.pos = error.Position(ref)
        self.last_line = 0
        self.top = None
        try:
            self.tokenizer = YangTokenizer(text, self.pos, ctx.errors,
                                           ctx.max_line_len, ctx.keep_comments,
                                           not ctx.lax_quote_checks)
            stmt = self._parse_statement(None)
        except error.Abort:
            return None
        except error.Eof as e:
            error.err_add(self.ctx.errors, self.pos, 'EOF_ERROR', ())
            return None
        try:
            # we expect a error.Eof or CommentStmt at this point, everything else is an error
            stmt2 = self._parse_statement(None)
            if stmt2.keyword != '_comment':
                error.err_add(self.ctx.errors, self.pos, 'TRAILING_GARBAGE', ())
        except error.Eof:
            return stmt
        except:
            error.err_add(self.ctx.errors, self.pos, 'TRAILING_GARBAGE', ())
            pass
        return None

    def _parse_statement(self, parent):
        # modification: when the --keep-comments flag is provided,
        # we would like to see if a statement is a comment, and if so
        # treat it differently than we treat keywords further down
        if self.ctx.keep_comments:
            cmt, is_line_end, is_multi_line = self.tokenizer.get_comment(self.last_line)
            if cmt is not None:
                stmt = statements.new_statement(self.top,
                                                parent,
                                                self.pos,
                                                '_comment',
                                                cmt)
                stmt.is_line_end = is_line_end
                stmt.is_multi_line = is_multi_line
                # just ignore Comments outside the module
                if parent is not None:
                    return stmt

        keywd = self.tokenizer.get_keyword()
        # check for argument
        tok = self.tokenizer.peek()
        if tok == '{' or tok == ';':
            arg = None
            argstrs = None
        else:
            argstrs = self.tokenizer.get_strings()
            arg = ''.join([a[0] for a in argstrs])
        # check for YANG 1.1
        if keywd == 'yang-version' and arg == '1.1':
            self.tokenizer.is_1_1 = True
            self.tokenizer.strict_quoting = True

        stmt = statements.new_statement(self.top, parent, self.pos, keywd, arg)

        if self.ctx.keep_arg_substrings and argstrs is not None:
            stmt.arg_substrings = argstrs
        if self.top is None:
            self.pos.top = stmt
            self.top = stmt

        # check for substatements
        tok = self.tokenizer.peek()
        if tok == '{':
            self.tokenizer.skip_tok() # skip the '{'
            self.last_line = self.pos.line
            while self.tokenizer.peek() != '}':
                substmt = self._parse_statement(stmt)
                stmt.substmts.append(substmt)
            self.tokenizer.skip_tok() # skip the '}'
        elif tok == ';':
            self.tokenizer.skip_tok() # skip the ';'
        else:
            error.err_add(self.ctx.errors, self.pos, 'INCOMPLETE_STATEMENT',
                          (keywd, tok))
            raise error.Abort
        self.last_line = self.pos.line
        return stmt

# FIXME: tmp debug
def ppkeywd(tok):
    if util.is_prefixed(tok):
        return tok[0] + ':' + tok[1]
    else:
        return tok

def pp(s, indent=0):
    sys.stdout.write(" " * indent + ppkeywd(s.raw_keyword))
    if s.arg is not None:
        sys.stdout.write(" '" + s.arg + "'")
    if not s.substmts:
        sys.stdout.write(";\n")
    else:
        sys.stdout.write(" {\n")
        for ss in s.substmts:
            pp(ss, indent+4)
        sys.stdout.write(" " * indent + "}\n")
