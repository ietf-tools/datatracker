import copy
import os.path

### struct to keep track of position for error messages

class Position(object):
    __slots__ = (
        'ref',
        'line',
        'top',
        'uses_pos',
    )

    def __init__(self, ref):
        self.ref = ref
        self.line = 0
        self.top = None
        self.uses_pos = None

    def __str__(self):
        return self.label()

    def label(self, basename=False):
        ref = self.ref
        if basename:
            ref = os.path.basename(ref)
        s = ref + ':' + str(self.line)
        if self.uses_pos is None:
            return s
        else:
            return str(self.uses_pos) + ' (at ' + s + ')'

### Exceptions

class Abort(Exception):
    """used for non-recoverable errors to abort parsing"""
    pass

class Eof(Exception):
    """raised by tokenizer when end of file is detected"""
    pass

class TransformError(Exception):
    """raised by plugins to fail the transform() function"""

    def __init__(self, msg="", exit_code=1):
        self.msg = msg
        self.exit_code = exit_code

class EmitError(Exception):
    """raised by plugins to fail the emit() function"""
    def __init__(self, msg="", exit_code=1):
        self.msg = msg
        self.exit_code = exit_code

### error codes

## level:
##    1: critical error, can not be made into a warning
##    2: major error, can not be made into a warning
##    3: minor error, can be made into warning with -W
##    4: warning
error_codes = \
    {
    'READ_ERROR':
      (1,
       'read error: %s'),
    'EOF_ERROR':
      (1,
       'premature end of file'),
    'EXPECTED_QUOTED_STRING':
      (1,
       'expected quoted string after \'+\' operator'),
    'UNKNOWN_KEYWORD':
      (1,
       'unknown keyword "%s"'),
    'INCOMPLETE_STATEMENT':
      (1,
       'unterminated statement definition for keyword "%s", looking at %s'),
    'EXPECTED_KEYWORD':
      (1,
       'expected keyword "%s"'),
    'EXPECTED_KEYWORD_2':
      (1,
       'expected keyword "%s" as child to "%s"'),
    'EXPECTED_DATA_DEF':
      (1,
       'expected a data definition statement as child to "%s"'),
    'UNEXPECTED_KEYWORD':
      (1,
       'unexpected keyword "%s"'),
    'UNEXPECTED_KEYWORD_1':
      (1,
       'unexpected keyword "%s", expected "%s"'),
    'UNEXPECTED_KEYWORD_N':
      (1,
       'unexpected keyword "%s", expected one of %s'),
    'UNEXPECTED_KEYWORD_CANONICAL':
      (1,
       'keyword "%s" not in canonical order (see RFC 6020, Section 12)'),
    'UNEXPECTED_KEYWORD_CANONICAL_1':
      (1,
       'keyword "%s" not in canonical order, ' \
       'expected "%s" (see RFC 6020, Section 12)'),
    'UNEXPECTED_KEYWORD_CANONICAL_v1.1':
      (1,
       'keyword "%s" not in canonical order (see RFC 7950, Section 14)'),
    'UNEXPECTED_KEYWORD_CANONICAL_1_v1.1':
      (1,
       'keyword "%s" not in canonical order, ' \
       'expected "%s" (see RFC 7950, Section 14)'),
    'UNEXPECTED_KEYWORD_USES':
      (1,
       'unexpected keyword "%s" under "%s", defined at %s'),
    'UNEXPECTED_KEYWORD_AUGMENT':
      (1,
       'unexpected keyword "%s" under "%s", defined at %s'),
    'EXPECTED_ARGUMENT':
      (1,
       'expected an argument for keyword "%s"'),
    'UNEXPECTED_ARGUMENT':
      (1,
       'did not expect an argument, got "%s"'),
    'XML_IDENTIFIER':
      (3,
       'illegal identifier "%s", must not start with [xX][mM][lL] in' \
       ' YANG version 1 (see RFC 6020, Section 12)'),
    'TRAILING_GARBAGE':
      (2,
       'trailing garbage after module'),
    'BAD_VALUE':
      (1,
       'bad value "%s" (should be %s)'),
    'CIRCULAR_DEPENDENCY':
      (1,
       'circular dependency for %s "%s"'),
    'MODULE_NOT_FOUND':
      (1,
       'module "%s" not found in search path'),
    'MODULE_NOT_FOUND_REV':
      (1,
       'module "%s" revision "%s" not found in search path'),
    'MODULE_NOT_IMPORTED':
      (1,
       'no module with the namespace "%s" is imported'),
    'BAD_IMPORT':
      (1,
       'cannot import %s "%s", must be a module'),
    'BAD_IMPORT_YANG_VERSION':
      (1,
       'a version %s module cannot import a version %s module by revision'),
    'BAD_INCLUDE':
      (1,
       'cannot include %s "%s", must be a submodule'),
    'BAD_INCLUDE_YANG_VERSION':
      (1,
       'cannot include a version %s submodule in a version %s module'),
    'BAD_MODULE_NAME':
      (2,
       'unexpected modulename "%s" in %s, should be "%s"'),
    'WBAD_MODULE_NAME':
      (4,
       'unexpected modulename "%s" in %s, should be "%s"'),
    'FILENAME_BAD_MODULE_NAME':
      (4,
       'filename "%s" suggests invalid module name "%s", should match "%s"'),
    'BAD_REVISION':
      (3,
       'unexpected latest revision "%s" in %s, should be "%s"'),
    'WBAD_REVISION':
      (4,
       'unexpected latest revision "%s" in %s, should be "%s"'),
    'FILENAME_BAD_REVISION':
      (4,
       'filename "%s" suggests invalid revision "%s", should match "%s"'),
    'BAD_SUB_BELONGS_TO':
      (1,
       'module "%s" includes "%s", but "%s" does not specify a ' \
       'correct belongs-to'),
    'MISSING_INCLUDE':
      (1,
       'submodule %s is included by %s, but not by the module %s'),
    'PREFIX_ALREADY_USED':
      (1,
       'prefix "%s" already used for module %s'),
    'PREFIX_NOT_DEFINED':
      (1,
       'prefix "%s" is not defined (reported only once)'),
    'WPREFIX_NOT_DEFINED':
      (4,
       '"%s" looks like a prefix but is not defined'),
    'NODE_NOT_FOUND':
      (1,
       'node %s::%s is not found'),
    'BAD_NODE_IN_AUGMENT':
      (1,
       'node %s::%s of type %s cannot be augmented'),
    'BAD_TARGET_NODE':
      (1,
       'node %s::%s of type %s cannot be target node'),
    'BAD_NODE_IN_REFINE':
      (1,
       'node %s::%s cannot be refined'),
    'BAD_REFINEMENT':
      (1,
       '"%s" node "%s::%s" cannot be refined with "%s"'),
    'BAD_DEVIATE_KEY':
      (2,
       'key node "%s::%s" cannot be deviated with "not-supported"'),
    'BAD_DEVIATE_ADD':
      (2,
       'the "%s" property already exists in node "%s::%s"'),
    'BAD_DEVIATE_REP':
      (2,
       'the "%s" property does not exist in node "%s::%s"'),
    'BAD_DEVIATE_DEL':
      (2,
       'the "%s" property does not exist in node "%s::%s"'),
    'BAD_DEVIATE_DEL2':
      (2,
       'the "%s" property cannot be deviate deleted in node "%s::%s"'),
    'BAD_DEVIATE_TYPE':
      (2,
       'the "%s" property cannot be added'),
    'BAD_DEVIATE_WITH_NOT_SUPPORTED':
      (2,
       'cannot have other deviate statement together with "not-supported"'),
    'EXTENSION_NOT_DEFINED':
      (1,
       'extension "%s" is not defined in module %s'),
    'TYPE_NOT_FOUND':
      (1,
       'type "%s" not found in module "%s"'),
    'FEATURE_NOT_FOUND':
      (1,
       'feature "%s" not found in module "%s"'),
    'IDENTITY_NOT_FOUND':
      (1,
       'identity "%s" not found in module "%s"'),
    'GROUPING_NOT_FOUND':
      (1,
       'grouping "%s" not found in module "%s"'),
    'DEFAULT_CASE_NOT_FOUND':
      (1,
       'the default case "%s" is not found"'),
    'MANDATORY_NODE_IN_DEFAULT_CASE':
      (1,
       'mandatory node in default case'),
    'MULTIPLE_REFINE':
      (1,
       'the node "%s" is already refined at %s'),
    'RANGE_BOUNDS':
      (2,
       'range error: "%s" is not larger than "%s"'),
    'LENGTH_BOUNDS':
      (2,
       'length error: "%s" is not larger than "%s"'),
    'TYPE_VALUE':
      (2,
       'the value "%s" does not match its base type %s- %s'),
    'DUPLICATE_ENUM_NAME':
      (1,
       'the enum name "%s" has already been used for the ' \
       'enumeration at %s'),
    'DUPLICATE_ENUM_VALUE':
      (1,
       'the integer value "%d" has already been used for the ' \
       'enumeration at %s'),
    'ENUM_VALUE':
      (1,
       'the enumeration value "%s" is not an 32 bit integer'),
    'BAD_ENUM_VALUE':
      (1,
       'the given value "%s" does not match the base enum value "%d"'),
    'DUPLICATE_BIT_POSITION':
      (1,
       'the position "%d" has already been used for the bit at %s'),
    'BIT_POSITION':
      (1,
       'the position value "%s" is not valid'),
    'BAD_BIT_POSITION':
      (1,
       'the given position "%s" does not match the base bit position "%d"'),
    'NEED_KEY':
      (1,
       'the list needs at least one key'),
    'NEED_KEY_USES':
      (1,
       'the list at "%s" needs at least one key because it is used as config'),
    'KEY_BAD_CONFIG':
      (1,
       'the key "%s" does not have same "config" as its list'),
    'BAD_KEY':
      (1,
       'the key "%s" does not reference an existing leaf'),
    'BAD_UNIQUE':
      (1,
       'the unique argument "%s" does not reference an existing leaf'),
    'BAD_UNIQUE_PART':
      (1,
       'the identifier "%s" in the unique argument does not reference '
       'an existing container'),
    'BAD_UNIQUE_PART_LIST':
      (1,
       'the identifier "%s" in the unique argument references a list; '
       'this is not legal'),
    'BAD_UNIQUE_CONFIG':
      (1,
       'the identifer "%s" has not the same config property as the'
       ' other nodes in the unique expression'),
    'ILLEGAL_ESCAPE':
      (1,
       'the escape sequence "\\%s" is illegal in double quoted strings'),
    'ILLEGAL_ESCAPE_WARN':
      (4,
       'the escape sequence "\\%s" is unsafe in double quoted strings' \
       ' - pass the flag --lax-quote-checks to avoid this warning'),
    'UNIQUE_IS_KEY':
      (4,
       'all keys in the list are redundantly present in the unique statement'),
    'DUPLICATE_KEY':
      (2,
       'the key "%s" must not be listed more than once'),
    'DUPLICATE_UNIQUE':
      (3,
       'the leaf "%s" occurs more than once in the unique expression'),
    'PATTERN_ERROR':
      (2,
       'syntax error in pattern: %s'),
    'LEAFREF_TOO_MANY_UP':
      (1,
       'the path for %s at %s has too many ".."'),
    'LEAFREF_IDENTIFIER_NOT_FOUND':
      (1,
       '"%s:%s" in the path for %s at %s is not found'),
    'LEAFREF_IDENTIFIER_BAD_NODE':
      (1,
       '"%s:%s" in the path for %s at %s references a %s node'),
    'LEAFREF_BAD_PREDICATE':
      (1,
       '"%s:%s" in the path for %s at %s has a predicate, '
       'but is not a list'),
    'LEAFREF_BAD_PREDICATE_PTR':
      (1,
       '"%s:%s" in the path\'s predicate for %s at %s is compared '
       'with a node that is not a leaf'),
    'LEAFREF_NOT_LEAF':
      (1,
       'the path for %s at %s does not refer to a leaf'),
    'LEAFREF_NO_KEY':
      (1,
       '"%s:%s" in the path for %s at %s is not the name of a key leaf'),
    'LEAFREF_MULTIPLE_KEYS':
      (1,
       '"%s:%s" in the path for %s at %s is referenced more than once'),
    'LEAFREF_BAD_CONFIG':
      (1,
       'the path for %s is config but refers to a '
       'non-config leaf "%s" defined at %s'),
    'LEAFREF_DEREF_NOT_LEAFREF':
      (1,
       'the deref argument refers to node "%s" at %s which is'
       ' not a leafref leaf'),
    'LEAFREF_DEREF_NOT_KEY':
      (1,
       'the deref argument refers to node "%s" at %s which'
       ' does not refer to a key (%s at %s)'),
    'LEAFREF_TO_NOT_IMPLEMENTED':
      (1,
       'the leafref refer to a node that is not implemented'),
    'DUPLICATE_CHILD_NAME':
      (1,
       'there is already a child node to "%s" at %s with the name "%s" '
       'defined at %s'),
    'BAD_ANCESTOR':
      (1,
       '"%s" node cannot have an ancestor list node without a key'),
    'BAD_ANCESTOR2':
      (1,
       '"%s" node cannot have an ancestor "%s" node'),
    'BAD_TYPE_NAME':
      (1,
       'illegal type name "%s"'),
    'TYPE_ALREADY_DEFINED':
      (1,
       'type name "%s" is already defined at %s'),
    'GROUPING_ALREADY_DEFINED':
      (1,
       'grouping name "%s" is already defined at %s'),
    'FEATURE_ALREADY_DEFINED':
      (1,
       'feature name "%s" is already defined at %s'),
    'IDENTITY_ALREADY_DEFINED':
      (1,
       'identity name "%s" is already defined at %s'),
    'EXTENSION_ALREADY_DEFINED':
      (1,
       'extension name "%s" is already defined at %s'),
    'BAD_RESTRICTION':
      (1,
       'restriction "%s" not allowed for this base type'),
    'BAD_DEFAULT_VALUE':
      (1,
       'the type "%s" cannot have a default value'),
    'MISSING_TYPE_SPEC':
      (1,
       'a type "%s" must have at least one "%s" statement'),
    'MISSING_TYPE_SPEC_1':
      (1,
       'a type "%s" must have a "%s" statement'),
    'BAD_TYPE_IN_UNION':
      (1,
       'the type "%s" (defined at %s) cannot be part of a union'),
    'BAD_TYPE_IN_KEY':
      (1,
       'the type "%s" cannot be part of a key, used by leaf "%s"'),
    'KEY_BAD_SUBSTMT':
      (1,
       'the statement "%s" cannot be given for a key'),
    'DEFAULT_AND_IFFEATURE':
      (1,
       'a \'default\' value cannot be given in leaf node when'
       ' \'if-feature\' is existing'),
    'DEFAULT_AND_MANDATORY':
      (1,
       'a \'default\' value cannot be given when \'mandatory\' is "true"'),
    'DEFAULT_AND_MIN_ELEMENTS':
      (1,
       'a \'default\' value cannot be given when \'min-elements\' is'
       ' greater than 0'),
    'MAX_ELEMENTS_AND_MIN_ELEMENTS':
      (1,
       'a \'min-elements\' value cannot be greater than \'max-elements\' value'),
    'DUPLICATE_DEFAULT':
        (1,
         'the default value "%s" is given twice in the leaf list'),
    'BAD_STATUS_REFERENCE':
      (2,
       'the "%s" definition is %s, but the "%s" it references is %s'),
    'REVISION_ORDER':
      (4,
       'the revision statements are not given in reverse chronological order'),
    'EXTENSION_ARGUMENT_PRESENT':
      (1,
       'unexpected argument for extension "%s"'),
    'EXTENSION_NO_ARGUMENT_PRESENT':
      (1,
       'expected argument for extension "%s"'),
    'SYNTAX_ERROR':
      (1,
       'syntax error: %s'),
    'DUPLICATE_NAMESPACE':
      (1,
       'duplicate namespace uri "%s" found in modules "%s"'),
    'MISSING_ARGUMENT_ATTRIBUTE':
      (1,
       'missing argument attribute "%s" for "%s"'),
    'MISSING_ARGUMENT_ELEMENT':
      (1,
       'missing argument element "%s" for "%s"'),
    'UNEXPECTED_ATTRIBUTE':
      (1,
       'unexpected attribute %s'),
    'INVALID_CONFIG':
      (2,
       'config true cannot be set when the parent is config false'),
    'XPATH_SYNTAX_ERROR':
      (2,
       'XPath syntax error: %s'),
    'XPATH_VARIABLE':
      (2,
       'XPath variable "%s" is not defined in the XPath context'),
    'XPATH_FUNCTION':
      (2,
       'XPath function "%s" is not defined in the XPath context'),
    'XPATH_FUNC_ARGS':
      (2,
       'XPath function "%s" takes %s arguments but called with %s.'),
    'XPATH_NODE_NOT_FOUND1':
      (4,
       'node "%s::%s" is not found in "%s::%s"'),
    'XPATH_NODE_NOT_FOUND2':
      (4,
       'node "%s::%s" is not found in module "%s"'),
    'XPATH_ANCESTOR_NOT_FOUND':
      (4,
       'node "%s::%s" is not found as ancestor to "%s::%s"'),
    'XPATH_MULTIPLE_ANCESTORS':
      (4,
       'node "%s::%s" has multiple ancestors called "%s::%s"'),
    'XPATH_REF_CONFIG_FALSE':
      (4,
       'node "%s::%s" is config false and is not part of the accessible tree'),
    'XPATH_PATH_TOO_MANY_UP':
      (2,
       'the path has too many ".."'),
    'XPATH_FUNCTION_RET_VAL':
      (2,
       'XPath function "%s" does not return a %s'),
    'XPATH_DEREF_TARGET':
      (4,
       'XPath deref target "%s" is not an leafref or instance-identifier, '\
       'will return an empty node-set'),
    'AUGMENT_MANDATORY':
      (1,
       'cannot augment with mandatory node "%s"'),

    'LONG_IDENTIFIER':
      (3,
       'identifier "%s" exceeds %s characters'),

    'CONFIG_IGNORED':
      (4,
       'explicit config statement is ignored'),

    'UNUSED_IMPORT':
      (4,
       'imported module "%s" not used'),

    'UNUSED_TYPEDEF':
      (4,
       'locally scoped typedef "%s" not used'),

    'UNUSED_GROUPING':
      (4,
       'locally scoped grouping "%s" not used'),

    'KEY_HAS_DEFAULT':
      (4,
       'default value for a key leaf is ignored'),

    'KEY_HAS_MANDATORY_FALSE':
      (4,
       '"mandatory" statement for a key leaf is ignored'),

    'LONG_LINE':
      (4,
       'line length %s exceeds %s characters'),

    'STRICT_XPATH_FUNCTION':
      (2,
       'XPath function "%s" is not allowed for strict YANG compliance'),
    }

def add_error_code(tag, level, fmt):
    """Add an error code to the framework.

    Can be used by plugins to add special errors."""
    error_codes[tag] = (level, fmt)

def err_level(tag):
    try:
        (level, fmt) = error_codes[tag]
        return level
    except KeyError:
        return 0

def err_to_str(tag, args):
    try:
        (level, fmt) = error_codes[tag]
        return fmt % args
    except KeyError:
        return 'unknown error %s' % tag

def err_add(errors, pos, tag, args):
    error = (copy.copy(pos), tag, args)
    # surely this can be done more elegant??
    for p, t, a in errors:
        if (p.line == pos.line and p.ref == pos.ref and
            p.top == pos.top and t == tag and a == args):
            return
    errors.append(error)

def is_warning(level):
    return not is_error(level)

def is_error(level):
    return level < 4

def allow_warning(level):
    return level > 2
