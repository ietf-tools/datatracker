"""XPath 1.0 lexer / scanner

Used with the PLY-based parser xpath_parser.py.

See http://www.w3.org/TR/1999/REC-xpath-19991116
"""

import re

class XPathError(Exception):
    def __init__(self, msg, line, pos):
        self.msg = msg
        self.line = line
        self.pos = pos

class XPathTok(object):
    def __init__(self, t, v, line, pos):
        self.type = t
        self.value = v
        self.lineno = line
        self.lexpos = pos

class XPathLexer(object):
    def input(self, s):
        self.toks = []
        self.error = None
        try:
            self.toks = scan(s)
        except SyntaxError as e:
            self.error = e

    def token(self):
        while len(self.toks) > 0:
            tok = self.toks[0]
            self.toks = self.toks[1:]
            if tok.type != '_whitespace':
                return tok

        if self.error is not None:
            raise self.error
        else:
            return None

# not 100% XPath / XML, but good enough for YANG
namestr=r'[a-zA-Z_][a-zA-Z0-9_\-.]*'
ncnamestr = '((' + namestr + '):)?(' + namestr + ')'
prefixteststr = '((' + namestr + r'):)?\*'

re_ncname = re.compile(ncnamestr)

patterns = [
    # special token used when we need to preserve whitespace,
    # not used in normal parsing
    ('_whitespace', re.compile(r'\s+')),
    # Expr tokens
    ('LPAREN', re.compile(r'\(')),
    ('RPAREN', re.compile(r'\)')),
    ('LBRACKET', re.compile(r'\[')),
    ('RBRACKET', re.compile(r'\]')),
    ('DOTDOT', re.compile(r'\.\.')),
    ('DOT', re.compile(r'\.')),
    ('COMMA', re.compile(r'\,')),
    ('AT', re.compile(r'\@')),
    ('DOLLAR', re.compile(r'\$')),
    ('DOUBLECOLON', re.compile(r'::')),
    # operators
    ('DOUBLESLASH', re.compile(r'\/\/')),
    ('SLASH', re.compile(r'\/')),
    ('BAR', re.compile(r'\|')),
    ('PLUS', re.compile(r'\+')),
    ('MINUS', re.compile(r'-')),
    ('EQ', re.compile(r'=')),
    ('NEQ', re.compile(r'!=')),
    ('LTE', re.compile(r'<=')),
    ('GTE', re.compile(r'>=')),
    ('GT', re.compile(r'>')),
    ('LT', re.compile(r'<')),
    ('STAR', re.compile(r'\*')),
    # others
    ('number', re.compile(r'[0-9]+(\.[0-9]+)?')),
    ('prefix_test', re.compile(prefixteststr)),
    ('name', re_ncname),
    ('literal', re.compile(r'(\".*?\")|(\'.*?\')')),
    ]

operators = {
    'div': 'DIV',
    'and': 'AND',
    'or': 'OR',
    'mod': 'MOD',
}

meta_tokens = ['node_type', 'axis', 'function_name', 'wildcard']

node_types = [ 'comment', 'text', 'processing-instruction', 'node' ]
axes = [ 'ancestor-or-self', 'ancestor', 'attribute', 'child',
         'descendant-or-self', 'descendant', 'following-sibling',
         'following', 'namespace', 'parent', 'preceding-sibling',
         'preceding', 'self' ]

def token_defs():
    toks = [p[0] for p in patterns]
    toks.extend(meta_tokens)
    toks.extend([operators[op] for op in operators])
    # remove spc
    toks.remove('_whitespace')
    return toks

re_open_para = re.compile(r'\s*\(')
re_axis = re.compile(r'\s*::')

def scan(s):
    """Return a list of tokens, or throw SyntaxError on failure.
    """
    line = 1
    linepos = 1
    pos = 0
    toks = []
    while pos < len(s):
        matched = False
        for tokname, r in patterns:
            m = r.match(s, pos)
            if m is not None:
                # found a matching token
                v = m.group(0)
                prec = _preceding_token(toks)
                if tokname == 'STAR' and prec is not None and _is_special(prec):
                    # XPath 1.0 spec, 3.7 special rule 1a
                    # interpret '*' as a wildcard
                    tok = XPathTok('wildcard', v, line, linepos)
                elif (tokname == 'name' and
                      prec is not None and not _is_special(prec) and
                      v in operators):
                    # XPath 1.0 spec, 3.7 special rule 1b
                    # interpret the name as an operator
                    tok = XPathTok(operators[v], v, line, linepos)
                elif tokname == 'name':
                    # check if next token is '('
                    if re_open_para.match(s, pos + len(v)):
                        # XPath 1.0 spec, 3.7 special rule 2
                        if v in node_types:
                            # XPath 1.0 spec, 3.7 special rule 2a
                            tok = XPathTok('node_type', v, line, linepos)
                        else:
                            # XPath 1.0 spec, 3.7 special rule 2b
                            tok = XPathTok('function_name', v, line, linepos)
                    # check if next token is '::'
                    elif re_axis.match(s, pos + len(v)):
                        # XPath 1.0 spec, 3.7 special rule 3
                        if v in axes:
                            tok = XPathTok('axis', v, line, linepos)
                        else:
                            e = "unknown axis %s" % v
                            raise XPathError(e, line, linepos)
                    else:
                        tok = XPathTok('name', v, line, linepos)
                else:
                    tok = XPathTok(tokname, v, line, linepos)
                if tokname == '_whitespace':
                    n = v.count('\n')
                    if n > 0:
                        line = line + n
                        linepos = len(v) - v.rfind('\n')
                    else:
                        linepos += len(v)
                else:
                    linepos += len(v)
                pos += len(v)
                toks.append(tok)
                matched = True
                break
        if not matched:
            # no patterns matched
            raise XPathError('syntax error', line, linepos)
    return toks

def _preceding_token(toks):
    if len(toks) > 1 and toks[-1].type == '_whitespace':
        return toks[-2]
    if len(toks) > 0 and toks[-1].type != '_whitespace':
        return toks[-1]
    return None

_special_tok_types = ['AT', 'DOUBLECOLON', 'LPAREN', 'LBRACKET',
                      'SLASH', 'DOUBLESLASH', 'BAR', 'PLUS', 'MINUS',
                      'EQ', 'NEQ', 'LT', 'LTE', 'GT', 'GTE',
                      'AND', 'OR', 'MOD', 'DIV' ]

def _is_special(tok):
    return tok.type in _special_tok_types
