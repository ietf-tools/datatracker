import pyparsing as pp

from .bibdatabase import BibDataStringExpression


# General helpers

def _strip_after_new_lines(s):
    """Removes leading and trailing whitespaces in all but first line."""
    lines = s.splitlines()
    if len(lines) > 1:
        lines = [lines[0]] + [l.lstrip() for l in lines[1:]]
    return '\n'.join(lines)


def strip_after_new_lines(s):
    """Removes leading and trailing whitespaces in all but first line.

    :param s: string or BibDataStringExpression
    """
    if isinstance(s, BibDataStringExpression):
        s.apply_on_strings(_strip_after_new_lines)
        return s
    else:
        return _strip_after_new_lines(s)


def add_logger_parse_action(expr, log_func):
    """Register a callback on expression parsing with the adequate message."""
    def action(s, l, t):
        log_func("Found {}: {}".format(expr.resultsName, t))
    expr.addParseAction(action)


# Parse action helpers
# Helpers for returning values from the parsed tokens. Shaped as pyparsing's
# parse actions. See pyparsing documentation for the arguments.

def first_token(string_, location, token):
    # TODO Handle this case correctly!
    assert(len(token) == 1)
    return token[0]


def remove_trailing_newlines(string_, location, token):
    if token[0]:
        return token[0].rstrip('\n')


def remove_braces(string_, location, token):
    if len(token[0]) < 1:
        return ''
    else:
        start = 1 if token[0][0] == '{' else 0
        end = -1 if token[0][-1] == '}' else None
        return token[0][start:end]


def field_to_pair(string_, location, token):
    """
    Looks for parsed element named 'Field'.

    :returns: (name, value).
    """
    field = token.get('Field')
    value = field.get('Value')
    if isinstance(value, pp.ParseResults):
        # For pyparsing >= 2.3.1 (see #225 and API change note in pyparsing's
        # Changelog).
        value = value[0]
    return (field.get('FieldName'),
            strip_after_new_lines(value))


# Expressions helpers

def in_braces_or_pars(exp):
    """
    exp -> (exp)|{exp}
    """
    return ((pp.Suppress('{') + exp + pp.Suppress('}')) |
            (pp.Suppress('(') + exp + pp.Suppress(')')))


class BibtexExpression(object):
    """Gives access to pyparsing expressions.

    Attributes are pyparsing expressions for the following elements:

    * main_expression: the bibtex file
    * string_def: a string definition
    * preamble_decl: a preamble declaration
    * explicit_comment: an explicit comment
    * entry: an entry definition
    * implicit_comment: an implicit comment

    """

    ParseException = pp.ParseException

    def __init__(self):
        # Init parse action functions
        self.set_string_name_parse_action(lambda s, l, t: None)

        # Bibtex keywords

        string_def_start = pp.CaselessKeyword("@string")
        preamble_start = pp.CaselessKeyword("@preamble")
        comment_line_start = pp.CaselessKeyword('@comment')

        # String names
        string_name = pp.Word(pp.alphanums + '_-:')('StringName')
        self.set_string_name_parse_action(lambda s, l, t: None)
        string_name.addParseAction(self._string_name_parse_action)

        # Values inside bibtex fields
        # Values can be integer or string expressions. The latter may use
        # quoted or braced values.

        # Integer values
        integer = pp.Word(pp.nums)('Integer')

        # Braced values: braced values can contain nested (but balanced) braces
        braced_value_content = pp.CharsNotIn('{}')
        braced_value = pp.Forward()  # Recursive definition for nested braces
        braced_value <<= pp.originalTextFor(
            '{' + pp.ZeroOrMore(braced_value | braced_value_content) + '}'
            )('BracedValue')
        braced_value.setParseAction(remove_braces)
        # TODO add ignore for "\}" and "\{" ?
        # TODO @ are not parsed by bibtex in braces

        # Quoted values: may contain braced content with balanced braces
        brace_in_quoted = pp.nestedExpr('{', '}', ignoreExpr=None)
        text_in_quoted = pp.CharsNotIn('"{}')
        # (quotes should be escaped by braces in quoted value)
        quoted_value = pp.originalTextFor(
            '"' + pp.ZeroOrMore(text_in_quoted | brace_in_quoted) + '"'
            )('QuotedValue')
        quoted_value.addParseAction(pp.removeQuotes)

        # String expressions
        string_expr = pp.delimitedList(
            (quoted_value | braced_value | string_name), delim='#'
            )('StringExpression')
        string_expr.addParseAction(self._string_expr_parse_action)

        value = (integer | string_expr)('Value')

        # Entries

        # @EntryType { ...
        entry_type = (pp.Suppress('@') + pp.Word(pp.alphas))('EntryType')
        entry_type.setParseAction(first_token)

        # Entry key: any character up to a ',' without leading and trailing
        # spaces. Also exclude spaces and prevent it from being empty.
        key = pp.SkipTo(',')('Key')  # TODO Maybe also exclude @',\#}{~%

        def citekeyParseAction(string_, location, token):
            """Parse action for validating citekeys.

            It ensures citekey is not empty and has no space.

            :args: see pyparsing documentation.
            """
            key = first_token(string_, location, token).strip()
            if len(key) < 1:
                raise self.ParseException(
                    string_, loc=location, msg="Empty citekeys are not allowed.")
            for i, c in enumerate(key):
                if c.isspace():
                    raise self.ParseException(
                        string_, loc=(location + i),
                        msg="Whitespace not allowed in citekeys.")
            return key

        key.setParseAction(citekeyParseAction)

        # Field name: word of letters, digits, dashes and underscores
        field_name = pp.Word(pp.alphanums + '_-().+')('FieldName')
        field_name.setParseAction(first_token)

        # Field: field_name = value
        field = pp.Group(field_name + pp.Suppress('=') + value)('Field')
        field.setParseAction(field_to_pair)

        # List of fields: comma separeted fields
        field_list = (pp.delimitedList(field) + pp.Suppress(pp.Optional(','))
                      )('Fields')
        field_list.setParseAction(
            lambda s, l, t: {k: v for (k, v) in reversed(t.get('Fields'))})

        # Entry: type, key, and fields
        self.entry = (entry_type +
                      in_braces_or_pars(key + pp.Suppress(',') + field_list)
                      )('Entry')

        # Other stuff: comments, string definitions, and preamble declarations

        # Explicit comments: @comment + everything up to next valid declaration
        # starting on new line.
        not_an_implicit_comment = (pp.LineEnd() + pp.Literal('@')
                                   ) | pp.StringEnd()
        self.explicit_comment = (
            pp.Suppress(comment_line_start) +
            pp.originalTextFor(pp.SkipTo(not_an_implicit_comment),
                               asString=True))('ExplicitComment')
        self.explicit_comment.addParseAction(remove_trailing_newlines)
        self.explicit_comment.addParseAction(remove_braces)
        # Previous implementation included comment until next '}'.
        # This is however not inline with bibtex behavior that is to only
        # ignore until EOL. Brace stipping is arbitrary here but avoids
        # duplication on bibtex write.

        # Empty implicit_comments lead to infinite loop of zeroOrMore
        def mustNotBeEmpty(t):
            if not t[0]:
                raise pp.ParseException("Match must not be empty.")

        # Implicit comments: not anything else
        self.implicit_comment = pp.originalTextFor(
            pp.SkipTo(not_an_implicit_comment).setParseAction(mustNotBeEmpty),
            asString=True)('ImplicitComment')
        self.implicit_comment.addParseAction(remove_trailing_newlines)

        # String definition
        self.string_def = (pp.Suppress(string_def_start) + in_braces_or_pars(
            string_name +
            pp.Suppress('=') +
            string_expr('StringValue')
            ))('StringDefinition')

        # Preamble declaration
        self.preamble_decl = (pp.Suppress(preamble_start) +
                              in_braces_or_pars(value))('PreambleDeclaration')

        # Main bibtex expression

        self.main_expression = pp.ZeroOrMore(
                self.string_def |
                self.preamble_decl |
                self.explicit_comment |
                self.entry |
                self.implicit_comment)

    def add_log_function(self, log_fun):
        """Add notice to logger on entry, comment, preamble, string definitions.

        :param log_fun: logger function
        """
        for e in [self.entry,
                  self.implicit_comment,
                  self.explicit_comment,
                  self.preamble_decl,
                  self.string_def]:
            add_logger_parse_action(e, log_fun)

    def set_string_name_parse_action(self, fun):
        """Set the parseAction for string name expression.

        .. Note::

            For some reason pyparsing duplicates the string_name
            expression so setting its parseAction a posteriori has no effect
            in the context of a string expression. This is why this function
            should be used instead.
        """
        self._string_name_parse_action_fun = fun

    def _string_name_parse_action(self, s, l, t):
        return self._string_name_parse_action_fun(s, l, t)

    def _string_expr_parse_action(self, s, l, t):
        return BibDataStringExpression.expression_if_needed(t)

    def parseFile(self, file_obj):
        return self.main_expression.parseFile(file_obj, parseAll=True)
