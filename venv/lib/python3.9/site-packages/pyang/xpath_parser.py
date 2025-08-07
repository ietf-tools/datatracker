"""XPath 1.0 parser

PLY-based parser to build an AST for an XPath 1.0 expression.

References are to rules in:
http://www.w3.org/TR/1999/REC-xpath-19991116
"""

from . import yacc
from . import xpath_lexer

def parse(s):
    return parser.parse(s, lexer = lexer, debug = False)

def pparse(s):
    try:
        return parse(s)
    except xpath_lexer.XPathError as e:
        print('ERROR: %s:%s: %s' % (e.line, e.pos, e.msg))
        return None
    except SyntaxError as e:
        print('ERROR: %s' % e.msg)
        return None

### Parser follows

## [1]
def p_location_path_1(p):
    'LocationPath : RelativeLocationPath'
    p[0] = ('relative', p[1])
def p_location_path_2(p):
    'LocationPath : AbsoluteLocationPath'
    p[0] = ('absolute', p[1])

## [2]
def p_abs_location_path_1(p):
    'AbsoluteLocationPath : SLASH RelativeLocationPath'
    p[0] = p[2]
def p_abs_location_path_2(p):
    'AbsoluteLocationPath : SLASH'
    p[0] = []
def p_abs_location_path_3(p):
    'AbsoluteLocationPath : AbbreviatedAbsoluteLocationPath'
    p[0] = p[1]

## [3]
def p_rel_location_path_1(p):
    'RelativeLocationPath : Step'
    p[0] = [p[1]]
def p_rel_location_path_2(p):
    'RelativeLocationPath : RelativeLocationPath SLASH Step'
    p[0] = list(p[1])
    p[0].append(p[3])
def p_rel_location_path_3(p):
    'RelativeLocationPath : AbbreviatedRelativeLocationPath'
    p[0] = p[1]

## [4]
def p_step_1(p):
    'Step : axis DOUBLECOLON NodeTest PredicateList'
    p[0] = ('step', p[1], p[3], p[4])
def p_step_2(p):
    'Step : axis DOUBLECOLON NodeTest'
    p[0] = ('step', p[1], p[3], [])
def p_step_3(p):
    'Step : AT name PredicateList'
    p[0] = ('step', 'attribute', p[2], p[3])
def p_step_4(p):
    'Step : AT name'
    p[0] = ('step', 'attribute', p[2], [])
def p_step_5(p):
    'Step : NodeTest PredicateList'
    p[0] = ('step', 'child', p[1], p[2])
def p_step_6(p):
    'Step : NodeTest'
    p[0] = ('step', 'child', p[1], [])
def p_step_7(p):
    'Step : AbbreviatedStep PredicateList'
    if p[1][1] == 'self':
        a = "."
        x = "self::node()"
    else:
        a = ".."
        x = "parent::node()"
    msg = "%s[<pred>] is illegal syntax.  use %s[<pred>] instead," % (a, x)
    raise xpath_lexer.XPathError(msg, 1, 1)
def p_step_8(p):
    'Step : AbbreviatedStep'
    p[0] = p[1]

def p_pred_list_1(p):
    'PredicateList : PredicateList Predicate'
    p[0] = list(p[1])
    p[0].append(p[2])
def p_pred_list_2(p):
    'PredicateList : Predicate'
    p[0] = [p[1]]

## [7]
def p_node_test_1(p):
    'NodeTest : NameTest'
    p[0] = p[1]
def p_node_test_2(p):
    'NodeTest : node_type LPAREN RPAREN'
    p[0] = ('node_type', p[1])
def p_node_test_3(p):
    'NodeTest : node_type LPAREN literal RPAREN'
    if p[1] != 'processing-instruction':
        raise SyntaxError
    p[0] = ('processing-instruction', p[3])

## [8]
def p_pred(p):
    'Predicate : LBRACKET PredicateExpr RBRACKET'
    p[0] = p[2]

## [9]
def p_pred_expr(p):
    'PredicateExpr : Expr'
    p[0] = p[1]

## [10]
def p_abbrev_abs_loc_path(p):
    'AbbreviatedAbsoluteLocationPath : DOUBLESLASH RelativeLocationPath'
    p[0] = [_expand_double_slash()]
    p[0].extend(p[2])

## [11]
def p_abbrev_rel_loc_path(p):
    'AbbreviatedRelativeLocationPath : RelativeLocationPath DOUBLESLASH Step'
    p[0] = list(p[1])
    p[0].append(_expand_double_slash())
    p[0].append(p[3])

## [12]
def p_abbrev_step_1(p):
    'AbbreviatedStep : DOT'
    p[0] = ('step', 'self', ('node_type', 'node'), [])
def p_abbrev_step_2(p):
    'AbbreviatedStep : DOTDOT'
    p[0] = ('step', 'parent', ('node_type', 'node'), [])

## [14]
def p_expr(p):
    'Expr : OrExpr'
    p[0] = p[1]

## [15]
def p_prim_expr_1(p):
    'PrimaryExpr : DOLLAR name'
    p[0] = ('variable', p[2])
def p_prim_expr_2(p):
    'PrimaryExpr : LPAREN Expr RPAREN'
    p[0] = p[2]
def p_prim_expr_3(p):
    'PrimaryExpr : literal'
    p[0] = ('literal', p[1])
def p_prim_expr_4(p):
    'PrimaryExpr : number'
    p[0] = ('number', p[1])
def p_prim_expr_5(p):
    'PrimaryExpr : FunctionCall'
    p[0] = p[1]

## [16]
def p_fun_call_1(p):
    'FunctionCall : function_name LPAREN RPAREN'
    p[0] = ('function_call', p[1], [])
def p_fun_call_2(p):
    'FunctionCall : function_name LPAREN ArgumentList RPAREN'
    p[0] = ('function_call', p[1], p[3])

def p_arg_list_1(p):
    'ArgumentList : ArgumentList COMMA Argument'
    p[0] = list(p[1])
    p[0].append(p[3])
def p_arg_list_2(p):
    'ArgumentList : Argument'
    p[0] = [p[1]]

## [17]
def p_arg(p):
    'Argument : Expr'
    p[0] = p[1]

## [18]
def p_union_expr_1(p):
    'UnionExpr : PathExpr'
    p[0] = p[1]
def p_union_expr_2(p):
    'UnionExpr : UnionExpr BAR PathExpr'
    p[0] = _mk_union(p[1], p[3])

## [19]
def p_path_expr_1(p):
    'PathExpr : LocationPath'
    p[0] = p[1]
def p_path_expr_2(p):
    'PathExpr : FilterExpr'
    p[0] = ('path_expr', p[1])
def p_path_expr_3(p):
    'PathExpr : FilterExpr SLASH RelativeLocationPath'
    p[0] = [p[1]]
    p[0].extend(p[3])
def p_path_expr_4(p):
    'PathExpr : FilterExpr DOUBLESLASH RelativeLocationPath'
    p[0] = [p[1]]
    p[0].append(_expand_double_slash())
    p[0].extend(p[3])

## [20]
def p_filter_expr_1(p):
    'FilterExpr : PrimaryExpr'
    p[0] = p[1]
def p_filter_expr_2(p):
    'FilterExpr : FilterExpr Predicate'
    p[0] = ('path', 'filter', p[1], p[2])

## [21]
def p_or_expr_1(p):
    'OrExpr : AndExpr'
    p[0] = p[1]
def p_or_expr_2(p):
    'OrExpr : OrExpr OR AndExpr'
    p[0] = ('bool', 'or', p[1], p[3])

## [22]
def p_and_expr_1(p):
    'AndExpr : EqualityExpr'
    p[0] = p[1]
def p_and_expr_2(p):
    'AndExpr : AndExpr AND EqualityExpr'
    p[0] = ('bool', 'and', p[1], p[3])

## [23]
def p_eq_expr_1(p):
    'EqualityExpr : RelationalExpr'
    p[0] = p[1]
def p_eq_expr_2(p):
    'EqualityExpr : EqualityExpr EQ RelationalExpr'
    p[0] = ('comp', '=', p[1], p[3])
def p_eq_expr_3(p):
    'EqualityExpr : EqualityExpr NEQ RelationalExpr'
    p[0] = ('comp', '!=', p[1], p[3])

##[24]
def p_rel_expr_1(p):
    'RelationalExpr : AdditiveExpr'
    p[0] = p[1]
def p_rel_expr_2(p):
    'RelationalExpr : RelationalExpr LT AdditiveExpr'
    p[0] = ('comp', '<', p[1], p[3])
def p_rel_expr_3(p):
    'RelationalExpr : RelationalExpr GT AdditiveExpr'
    p[0] = ('comp', '>', p[1], p[3])
def p_rel_expr_4(p):
    'RelationalExpr : RelationalExpr LTE AdditiveExpr'
    p[0] = ('comp', '<=', p[1], p[3])
def p_rel_expr_5(p):
    'RelationalExpr : RelationalExpr GTE AdditiveExpr'
    p[0] = ('comp', '>=', p[1], p[3])

## [25]
def p_add_expr_1(p):
    'AdditiveExpr : MultiplicativeExpr'
    p[0] = p[1]
def p_add_expr_2(p):
    'AdditiveExpr : AdditiveExpr PLUS MultiplicativeExpr'
    p[0] = ('arith', '+', p[1], p[3])
def p_add_expr_3(p):
    'AdditiveExpr : AdditiveExpr MINUS MultiplicativeExpr'
    p[0] = ('arith', '-', p[1], p[3])

## [26]
def p_mul_expr_1(p):
    'MultiplicativeExpr : UnaryExpr'
    p[0] = p[1]
def p_mul_expr_2(p):
    'MultiplicativeExpr : MultiplicativeExpr MultiplyOperator UnaryExpr'
    p[0] = ('arith', p[2], p[1], p[3])
def p_mul_expr_3(p):
    'MultiplicativeExpr : MultiplicativeExpr DIV UnaryExpr'
    p[0] = ('arith', 'div', p[1], p[3])
def p_mul_expr_4(p):
    'MultiplicativeExpr : MultiplicativeExpr MOD UnaryExpr'
    p[0] = ('arith', 'mod', p[1], p[3])

## [27]
def p_unary_expr_1(p):
    'UnaryExpr : UnionExpr'
    p[0] = p[1]
def p_unary_expr_2(p):
    'UnaryExpr : MINUS UnaryExpr %prec UMINUS'
    p[0] = ('negative', p[2])

## [34]
def p_mul_oper(p):
    'MultiplyOperator : STAR'
    p[0] = '*'

## [37]
def p_name_test_1(p):
    'NameTest : wildcard'
    p[0] = 'wildcard'
def p_name_test_2(p):
    'NameTest : prefix_test'
    p[0] = ('has_namespace', p[1])
def p_name_test_3(p):
    'NameTest : name'
    p[0] = _mk_name(p[1])

def p_error(tok):
    if tok:
        raise xpath_lexer.XPathError("syntax error before '%s'" % tok.value,
                                     tok.lineno, tok.lexpos)
    else:
        raise SyntaxError("unexpected end of string")

def _mk_union(a, b):
    if a[0] == 'union' and b[0] == 'union':
        v = list(a[1])
        v.extend(b[1])
        return ('union', v)
    elif a[0] == 'union':
        v = list(a[1])
        v.append(b[1])
        return ('union', v)
    elif b[0] == 'union':
        v = [b]
        v.extend(a[1])
        return ('union', v)
    else:
        return ('union', [a, b])

def _expand_double_slash():
    return ('step', 'descendant-or-self', ('node_type', 'node'), [])

def _mk_name(v):
    m = xpath_lexer.re_ncname.match(v)
    if m.group(2) is not None:
        return ('name', m.group(2), m.group(3))
    else:
        return ('name', None, v)

start = 'Expr'

precedence = (
    ('left', 'OR'),
    ('left', 'AND'),
    ('left', 'EQ', 'NEQ'),
    ('left', 'LT', 'LTE', 'GT', 'GTE'),
    ('right', 'UMINUS'), # Unary minus operator
)

tokens = xpath_lexer.token_defs()
lexer = xpath_lexer.XPathLexer()
parser = yacc.yacc(tabmodule="xpath_parsetab", debug=False, write_tables=False)
