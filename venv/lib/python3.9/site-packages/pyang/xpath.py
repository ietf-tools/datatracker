from . import xpath_lexer
from . import xpath_parser
from . import types
from .error import err_add
from .util import prefix_to_module, search_data_node, data_node_up
from .syntax import re_identifier

core_functions = {
    'last': ([], 'number'),
    'position': ([], 'number'),
    'count': (['node-set'], 'number'),
    'id': (['object'], 'node-set'),
    'local-name': (['node-set', '?'], 'string'),
    'namespace-uri': (['node-set', '?'], 'string'),
    'name': (['node-set', '?'], 'string'),
    'string': (['object'], 'string'),
    'concat': (['string', 'string', '*'], 'string'),
    'starts-with': (['string', 'string'], 'boolean'),
    'contains': (['string', 'string'], 'boolean'),
    'substring-before': (['string', 'string'], 'string'),
    'substring-after': (['string', 'string'], 'string'),
    'substring': (['string', 'number', 'number', '?'], 'string'),
    'string-length': (['string', '?'], 'number'),
    'normalize-space': (['string', '?'], 'string'),
    'translate': (['string', 'string', 'string'], 'string'),
    'boolean': (['object'], 'boolean'),
    'not': (['boolean'], 'boolean'),
    'true': ([], 'boolean'),
    'false': ([], 'boolean'),
    'lang': (['string'], 'boolean'),
    'number': (['object'], 'number'),
    'sum': (['node-set'], 'number'),
    'floor': (['number'], 'number'),
    'ceiling': (['number'], 'number'),
    'round': (['number'], 'number'),
    }

yang_xpath_functions = {
    'current': ([], 'node-set')
    }

yang_1_1_xpath_functions = {
    'bit-is-set': (['node-set', 'string'], 'boolean'),
    'enum-value': (['string'], 'number'),
    'deref': (['node-set'], 'node-set'),
    'derived-from': (['node-set', 'qstring'], 'boolean'),
    'derived-from-or-self': (['node-set', 'qstring'], 'boolean'),
    're-match': (['string', 'string'], 'boolean'),
    }

extra_xpath_functions = {
    'deref': (['node-set'], 'node-set'), # pyang extension for 1.0
    }

def add_extra_xpath_function(name, input_params, output_param):
    extra_xpath_functions[name] = (input_params, output_param)

def add_prefix(prefix, s):
    "Add `prefix` to all unprefixed names in `s`"
    # tokenize the XPath expression
    toks = xpath_lexer.scan(s)
    # add default prefix to unprefixed names
    toks2 = [_add_prefix(prefix, tok) for tok in toks]
    # build a string of the patched expression
    ls = [x.value for x in toks2]
    return ''.join(ls)

def _add_prefix(prefix, tok):
    if tok.type == 'name':
        m = xpath_lexer.re_ncname.match(tok.value)
        if m.group(2) is None:
            tok.value = prefix + ':' + tok.value
    return tok

## TODO: validate must/when after deviate

# node is the initial context node or None if it is not known
def v_xpath(ctx, stmt, node):
    try:
        if hasattr(stmt, 'i_xpath') and stmt.i_xpath is not None:
            q = stmt.i_xpath
        else:
            q = xpath_parser.parse(stmt.arg)
            stmt.i_xpath = q
        chk_xpath_expr(ctx, stmt.i_orig_module, stmt.pos, node, node, q, None)
    except xpath_lexer.XPathError as e:
        err_add(ctx.errors, stmt.pos, 'XPATH_SYNTAX_ERROR', e.msg)
        stmt.i_xpath = None
    except SyntaxError as e:
        err_add(ctx.errors, stmt.pos, 'XPATH_SYNTAX_ERROR', e.msg)
        stmt.i_xpath = None

# mod is the (sub)module where the stmt is defined, which we use to
# resolve prefixes.
def chk_xpath_expr(ctx, mod, pos, initial, node, q, t):
    if isinstance(q, list):
        chk_xpath_path(ctx, mod, pos, initial, node, q)
    elif isinstance(q, tuple):
        if q[0] == 'absolute':
            chk_xpath_path(ctx, mod, pos, initial, 'root', q[1])
        elif q[0] == 'relative':
            chk_xpath_path(ctx, mod, pos, initial, node, q[1])
        elif q[0] == 'union':
            for qa in q[1]:
                chk_xpath_path(ctx, mod, pos, initial, node, qa)
        elif q[0] == 'comp':
            chk_xpath_expr(ctx, mod, pos, initial, node, q[2], None)
            chk_xpath_expr(ctx, mod, pos, initial, node, q[3], None)
        elif q[0] == 'arith':
            chk_xpath_expr(ctx, mod, pos, initial, node, q[2], None)
            chk_xpath_expr(ctx, mod, pos, initial, node, q[3], None)
        elif q[0] == 'bool':
            chk_xpath_expr(ctx, mod, pos, initial, node, q[2], None)
            chk_xpath_expr(ctx, mod, pos, initial, node, q[3], None)
        elif q[0] == 'negative':
            chk_xpath_expr(ctx, mod, pos, initial, node, q[1], None)
        elif q[0] == 'function_call':
            chk_xpath_function(ctx, mod, pos, initial, node, q[1], q[2])
        elif q[0] == 'path_expr':
            chk_xpath_expr(ctx, mod, pos, initial, node, q[1], t)
        elif q[0] == 'path': # q[1] == 'filter'
            chk_xpath_expr(ctx, mod, pos, initial, node, q[2], None)
            chk_xpath_expr(ctx, mod, pos, initial, node, q[3], None)
        elif q[0] == 'var':
            # NOTE: check if the variable is known; currently we don't
            # have any variables in YANG xpath expressions
            err_add(ctx.errors, pos, 'XPATH_VARIABLE', q[1])
        elif q[0] == 'literal':
            # kind of hack to detect qnames, and mark the prefixes
            # as being used in order to avoid warnings.
            s = q[1]
            if s[0] == s[-1] and s[0] in ("'", '"'):
                s = s[1:-1]
                i = s.find(':')
                # make sure there is just one : present
                # FIXME: more colons should possibly be reported, instead
                if i != -1 and s.find(':', i + 1) == -1:
                    prefix = s[:i]
                    tag = s[i + 1:]
                    if (re_identifier.search(prefix) is not None and
                        re_identifier.search(tag) is not None):
                        # we don't want to report an error; just mark the
                        # prefix as being used.
                        my_errors = []
                        prefix_to_module(mod, prefix, pos, my_errors)
                        for pos0, code, arg in my_errors:
                            if code == 'PREFIX_NOT_DEFINED' and t == 'qstring':
                                # we know for sure that this is an error
                                err_add(ctx.errors, pos0,
                                        'PREFIX_NOT_DEFINED', arg)
                            else:
                                # this may or may not be an error;
                                # report a warning
                                err_add(ctx.errors, pos0,
                                        'WPREFIX_NOT_DEFINED', arg)

def chk_xpath_function(ctx, mod, pos, initial, node, func, args):
    signature = None
    if func in core_functions:
        signature = core_functions[func]
    elif func in yang_xpath_functions:
        signature = yang_xpath_functions[func]
    elif mod.i_version != '1' and func in yang_1_1_xpath_functions:
        signature = yang_1_1_xpath_functions[func]
    elif ctx.strict and func in extra_xpath_functions:
        err_add(ctx.errors, pos, 'STRICT_XPATH_FUNCTION', func)
        return None
    elif not ctx.strict and func in extra_xpath_functions:
        signature = extra_xpath_functions[func]

    if signature is None:
        err_add(ctx.errors, pos, 'XPATH_FUNCTION', func)
        return None

    # check that the number of arguments are correct
    nexp = len(signature[0])
    nargs = len(args)
    if nexp == 0:
        if nargs != 0:
            err_add(ctx.errors, pos, 'XPATH_FUNC_ARGS',
                    (func, nexp, nargs))
    elif signature[0][-1] == '?':
        if nargs != (nexp - 1) and nargs != (nexp - 2):
            err_add(ctx.errors, pos, 'XPATH_FUNC_ARGS',
                    (func, "%s-%s" % (nexp - 2, nexp - 1), nargs))
    elif signature[0][-1] == '*':
        if nargs < (nexp - 1):
            err_add(ctx.errors, pos, 'XPATH_FUNC_ARGS',
                    (func, "at least %s" % (nexp - 1), nargs))
    elif nexp != nargs:
        err_add(ctx.errors, pos, 'XPATH_FUNC_ARGS',
                (func, nexp, nargs))

    # check the arguments - FIXME check type
    i = 0
    args_signature = signature[0][:]
    if func == 'deref':
        arg = args[0]
        tgt = chk_xpath_path(ctx, mod, pos, initial, node, arg)

        if tgt is not None:
            if not hasattr(tgt, 'i_leafref_ptr') or tgt.i_leafref_ptr is None:
                # not a leafref;
                type_ = tgt.search_one('type')
                if (type_ is None or
                    not isinstance(type_.i_type_spec,
                                   types.InstanceIdentifierTypeSpec)):
                    err_add(ctx.errors, pos, 'XPATH_DEREF_TARGET', tgt)
                tgt = None
        return (signature[1], tgt)
    else:
        for arg in args:
            chk_xpath_expr(ctx, mod, pos, initial, node, arg, args_signature[i])
            if args_signature[i] == '*':
                args_signature.append('*')
            i = i + 1
        return (signature[1], None)

def chk_xpath_path(ctx, mod, pos, initial, node, path):
    if len(path) == 0:
        return node
    head = path[0]
    if head == 'relative':
        return chk_xpath_path(ctx, mod, pos, initial, node, path[1])
    if head[0] == 'var':
        # check if the variable is known as a node-set
        # currently we don't have any variables, so this fails
        err_add(ctx.errors, pos, 'XPATH_VARIABLE', head[1])
    elif head[0] == 'function_call':
        func = head[1]
        args = head[2]
        (rettype, tgt) = chk_xpath_function(ctx, mod, pos, initial,
                                            node, func, args)
        if rettype is not None:
            # known function, check that it returns a node set
            if rettype != 'node-set':
                err_add(ctx.errors, pos, 'XPATH_FUNCTION_RET_VAL',
                        (func, 'node-set'))
        if func == 'current':
            return chk_xpath_path(ctx, mod, pos, initial, initial, path[1:])
        elif func == 'deref':
            t = None
            if tgt is not None:
                (t, _pos) = tgt.i_leafref_ptr
            return chk_xpath_path(ctx, mod, pos, initial, t, path[1:])
    elif head[0] == 'step':
        axis = head[1]
        nodetest = head[2]
        preds = head[3]
        node1 = None
        if axis == 'self':
            node1 = node
            pass
        elif nodetest[0] == 'name':
            prefix = nodetest[1]
            name = nodetest[2]
            if prefix is None:
                if initial is None:
                    pmodule = None
                elif initial.keyword == 'module':
                    pmodule = initial
                else:
                    pmodule = initial.i_module
            else:
                pmodule = prefix_to_module(mod, prefix, pos, ctx.errors)
            # if node and initial are None, it means we're checking an XPath
            # expression when it is defined in a grouping or augment, i.e.,
            # when the full tree is not expanded.  in this case we can't check
            # the paths
            if pmodule is not None and node is not None and initial is not None:
                if axis == 'child':
                    if node == 'root':
                        children = pmodule.i_children
                    else:
                        children = getattr(node, 'i_children', None) or []
                    child = search_data_node(children, pmodule.i_modulename,
                                             name)
                    if child is None and node == 'root':
                        err_add(ctx.errors, pos, 'XPATH_NODE_NOT_FOUND2',
                                (pmodule.i_modulename, name, pmodule.arg))
                    elif child is None and node.i_module is not None:
                        err_add(ctx.errors, pos, 'XPATH_NODE_NOT_FOUND1',
                                (pmodule.i_modulename, name,
                                 node.i_module.i_modulename, node.arg))
                    elif child is None:
                        err_add(ctx.errors, pos, 'XPATH_NODE_NOT_FOUND2',
                                (pmodule.i_modulename, name, node.arg))
                    elif (getattr(initial, 'i_config', None) is True
                          and getattr(child, 'i_config', None) is False):
                        err_add(ctx.errors, pos, 'XPATH_REF_CONFIG_FALSE',
                                (pmodule.i_modulename, name))
                    else:
                        node1 = child
                elif axis == 'ancestor' or axis == 'ancestor-or-self':
                    p = node
                    if axis == 'ancestor':
                        if node == 'root':
                            err_add(ctx.errors, pos, 'XPATH_ANCESTOR_NOT_FOUND',
                                    (pmodule.i_modulename, name,
                                     node.i_module.i_modulename, node.arg))
                        else:
                            p = data_node_up(node)
                    while (p is not None and
                           not(p.arg == name and
                               p.i_module and
                               p.i_module.i_modulename == pmodule.i_modulename)):
                        p = data_node_up(p)
                    if p is None:
                        err_add(ctx.errors, pos, 'XPATH_ANCESTOR_NOT_FOUND',
                                (pmodule.i_modulename, name,
                                 node.i_module.i_modulename, node.arg))
                    else:
                        node1 = p
                        # we have now found one matching ancestor.
                        # NOTE: we don't handle multiple matching ancestors,
                        # so we check for this
                        p = data_node_up(p)
                        while (p is not None and
                               not(p.arg == name and
                                   p.i_module and
                                   p.i_module.i_modulename ==
                                   pmodule.i_modulename)):
                            p = data_node_up(p)
                        if p is not None:
                            # multiple ancestors; give a warning and continue
                            err_add(ctx.errors, pos, 'XPATH_MULTIPLE_ANCESTORS',
                                    (node.i_module.i_modulename, node.arg,
                                     pmodule.i_modulename, name))
                            node1 = None
                else:
                    # we can't validate the steps on other axis, but we can
                    # validate functions etc.
                    pass
        elif axis == 'parent' and nodetest == ('node_type', 'node'):
            if node is None:
                pass
            elif node == 'root':
                err_add(ctx.errors, pos, 'XPATH_PATH_TOO_MANY_UP', ())
            else:
                p = data_node_up(node)
                if p is None:
                    err_add(ctx.errors, pos, 'XPATH_PATH_TOO_MANY_UP', ())
                else:
                    node1 = p
        else:
            # we can't validate the steps on other axis, but we can
            # validate functions etc.
            pass
        for p in preds:
            chk_xpath_expr(ctx, mod, pos, initial, node1, p, None)
        return chk_xpath_path(ctx, mod, pos, initial, node1, path[1:])
