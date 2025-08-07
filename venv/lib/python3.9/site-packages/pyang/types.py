"""YANG built-in types"""

import base64
import lxml.etree

from . import util
from . import syntax
from .error import err_add

class Abort(Exception):
    pass

class TypeSpec(object):
    def __init__(self, name):
        self.definition = ""
        self.name = name
        self.base = None

    def str_to_val(self, errors, pos, string, module):
        return string

    def validate(self, errors, pos, val, module, errstr=''):
        return True

    def restrictions(self):
        return []

class IntTypeSpec(TypeSpec):
    def __init__(self, name, minimum, maximum):
        TypeSpec.__init__(self, name)
        self.is_int = True
        self.min = minimum
        self.max = maximum

    def str_to_val(self, errors, pos, string, _module):
        negative = string.startswith('-')
        base = 10
        start = 0
        if len(string) > negative + 1 and string[negative] == '0':
            second = string[negative + 1]
            if second == 'x':
                base = 16
                start = 2
            else:
                base = 8
                start = 1
        try:
            absolute = int(string[negative + start:], base)
            return -absolute if negative else absolute
        except ValueError:
            err_add(errors, pos, 'TYPE_VALUE',
                    (string, self.definition, 'not an integer'))
            return None

    def validate(self, errors, pos, val, _module, errstr=''):
        if val < self.min or val > self.max:
            err_add(errors, pos, 'TYPE_VALUE',
                    (str(val), self.definition, 'range error' + errstr))
            return False
        else:
            return True

    def restrictions(self):
        return ['range']

class Decimal64Value(object):
    def __init__(self, value, s=None, fd=None):
        # must set s (string repr) OR fd (fraction-digits)
        self.value = value
        self.s = s
        if s is None:
            if fd is None:
                raise ValueError(
                    'Decimal64 must set s (string) OR fd (fraction-digits)')
            s = str(value)
            fd = int(fd)
            self.s = s[:-fd] + "." + s[-fd:]

    def __str__(self):
        return self.s

    def __cmp__(self, other):
        if not isinstance(other, Decimal64Value):
            return -1
        if self.value < other.value:
            return -1
        elif self.value == other.value:
            return 0
        else:
            return 1

    def __eq__(self, other):
        if not isinstance(other, Decimal64Value):
            return False
        return self.value == other.value

    def __ne__(self, other):
        if not isinstance(other, Decimal64Value):
            return True
        return self.value != other.value

    def __lt__(self, other):
        if not isinstance(other, Decimal64Value):
            return True
        return self.value < other.value

    def __le__(self, other):
        if not isinstance(other, Decimal64Value):
            return True
        return self.value <= other.value

    def __gt__(self, other):
        if not isinstance(other, Decimal64Value):
            return False
        return self.value > other.value

    def __ge__(self, other):
        if not isinstance(other, Decimal64Value):
            return False
        return self.value >= other.value


class Decimal64TypeSpec(TypeSpec):
    def __init__(self, fraction_digits):
        TypeSpec.__init__(self, 'decimal64')
        self.fraction_digits = int(fraction_digits.arg)
        self.min = Decimal64Value(-9223372036854775808, fd=self.fraction_digits)
        self.max = Decimal64Value(9223372036854775807, fd=self.fraction_digits)

    def str_to_val(self, errors, pos, string, _module):
        # make sure it is syntactically correct
        if syntax.re_decimal.search(string) is None:
            err_add(errors, pos, 'TYPE_VALUE',
                    (string, self.definition, 'not a decimal'))
            return None
        if string[0] == '-':
            is_negative = True
            s = string[1:]
        else:
            is_negative = False
            s = string
        p = s.find('.')
        if p == -1:
            v = int(s)
            i = self.fraction_digits
            while i > 0:
                v = v * 10
                i -= 1
        else:
            v = int(s[:p])
            i = self.fraction_digits
            j = p + 1
#            slen = len(s.rstrip('0')) # ignore trailing zeroes
# No, do not ignore trailing zeroes!
            slen = len(s)
            while i > 0:
                v *= 10
                i -= 1
                if j < slen:
                    v += int(s[j])
                j += 1
            if j < slen:
                err_add(errors, pos, 'TYPE_VALUE',
                        (s, self.definition, 'too many fraction digits'))
                return None
        if is_negative:
            v = -v
        return Decimal64Value(v, s=string)

    def validate(self, errors, pos, val, _module, errstr=''):
        if val < self.min or val > self.max:
            err_add(errors, pos, 'TYPE_VALUE',
                    (str(val), self.definition, 'range error' + errstr))
            return False
        else:
            return True

    def restrictions(self):
        return ['range']

class BooleanTypeSpec(TypeSpec):
    def __init__(self):
        TypeSpec.__init__(self, 'boolean')

    def str_to_val(self, errors, pos, string, _module):
        if string == 'true':
            return True
        elif string == 'false':
            return False
        else:
            err_add(errors, pos, 'TYPE_VALUE',
                    (string, self.definition, 'not a boolean'))
            return None

class StringTypeSpec(TypeSpec):
    def __init__(self):
        TypeSpec.__init__(self, 'string')
        self.min = 0
        self.max = 18446744073709551615

    def validate(self, errors, pos, val, _module, errstr=''):
        val = val if isinstance(val, util.int_types) else len(val)
        if val < self.min or val > self.max:
            err_add(errors, pos, 'TYPE_VALUE',
                    (str(val), self.definition, 'lengths error' + errstr))
            return False
        else:
            return True

    def restrictions(self):
        return ['pattern', 'length']

class BinaryTypeSpec(TypeSpec):
    def __init__(self):
        TypeSpec.__init__(self, 'binary')
        self.min = 0
        self.max = 18446744073709551615

    def str_to_val(self, errors, pos, string, _module):
        try:
            return base64.b64decode(string)
        except:
            err_add(errors, pos, 'TYPE_VALUE',
                    (string, '', 'bad base64 value'))

    def validate(self, errors, pos, val, _module, errstr=''):
        val = val if isinstance(val, util.int_types) else len(val)
        if val < self.min or val > self.max:
            err_add(errors, pos, 'TYPE_VALUE',
                    (str(val), self.definition, 'lengths error' + errstr))
            return False
        else:
            return True

    def restrictions(self):
        return ['length']

class EmptyTypeSpec(TypeSpec):
    def __init__(self):
        TypeSpec.__init__(self, 'empty')

    def str_to_val(self, errors, pos, string, _module):
        err_add(errors, pos, 'BAD_DEFAULT_VALUE', 'empty')
        return None

class IdentityrefTypeSpec(TypeSpec):
    def __init__(self, idbases):
        TypeSpec.__init__(self, 'identityref')
        self.idbases = idbases

    def str_to_val(self, errors, pos, string, module):
        if string.find(":") == -1:
            prefix = None
            name = string
        else:
            [prefix, name] = string.split(':', 1)
        if prefix is None or module.i_prefix == prefix:
            # check local identities
            pmodule = module
        else:
            # this is a prefixed name, check the imported modules
            pmodule = util.prefix_to_module(module, prefix, pos, errors)
            if pmodule is None:
                return None
        if name not in pmodule.i_identities:
            err_add(errors, pos, 'TYPE_VALUE',
                    (string, self.definition, 'identityref not found'))
            return None
        val = pmodule.i_identities[name]
        for idbase in self.idbases:
            my_identity = idbase.i_identity
            if not is_derived_from(val, my_identity):
                err_add(errors, pos, 'TYPE_VALUE',
                        (string, self.definition,
                         'identityref not derived from %s' % my_identity.arg))
                return None
        return val

def is_derived_from(a, b):
    if a == b:
        # an identity is not derived from itself
        return False
    else:
        return is_derived_from_or_self(a, b, [])

def is_derived_from_or_self(a, b, visited):
    # return True if a is derived from b
    if a == b:
        return True
    for p in a.search('base'):
        if hasattr(p, 'i_identity'):
            val = p.i_identity
            if val not in visited:
                visited.append(val)
                if is_derived_from_or_self(val, b, visited):
                    return True
    return False

## type restrictions

def validate_range_expr(errors, stmt, type_):

    is_int = hasattr(type_.i_type_spec, 'is_int')

    # break the expression apart
    def convert(string):
        if not string:
            # this means that a single number was in the range, e.g.
            # "4 | 5..6" - the high value match group is empty.
            val = None
        elif string in ('min', 'max'):
            val = string
        else:
            if is_int and syntax.re_integer.search(string) is None:
                err_add(errors, stmt.pos, 'TYPE_VALUE',
                        (string, type_.i_type_spec.definition,
                         'not an integer'))
            val = type_.i_type_spec.str_to_val(errors, stmt.pos, string, None)
        return val

    ranges = [(convert(m[1]), convert(m[6]))
              for m in syntax.re_range_part.findall(stmt.arg)]
    return validate_ranges(errors, stmt.pos, ranges, type_)

def validate_ranges(errors, pos, ranges, type_):
    # make sure the range values are of correct type and increasing
    cur_lo = None
    for lo, hi in ranges:
        if isinstance(type_.i_type_spec, RangeTypeSpec):
            type_.i_type_spec.validate(errors, pos, (lo, hi),
                                       type_.i_module, "")
        else:
            if lo is not None and lo != 'min' and lo != 'max':
                type_.i_type_spec.validate(errors, pos, lo,
                                           type_.i_module, "")
            if hi is not None and hi != 'min' and hi != 'max':
                type_.i_type_spec.validate(errors, pos, hi,
                                           type_.i_module, "")
        # check that cur_lo < lo < hi
        if not is_smaller(cur_lo, lo):
            err_add(errors, pos, 'RANGE_BOUNDS', (str(lo), cur_lo))
            return None
        if not is_smaller(lo, hi):
            err_add(errors, pos, 'RANGE_BOUNDS', (str(hi), str(lo)))
            return None
        if (lo == 'max' and cur_lo is not None and cur_lo != 'min'
                and cur_lo >= type_.i_type_spec.max):
            err_add(errors, pos, 'RANGE_BOUNDS', (str(lo), str(cur_lo)))
            return None
        if (lo == 'min' and hi is not None and
                hi != 'max' and hi < type_.i_type_spec.min):
            err_add(errors, pos, 'RANGE_BOUNDS', (str(lo), str(hi)))
            return None
        if hi is None:
            cur_lo = lo
        else:
            cur_lo = hi
    return (ranges, pos)

class RangeTypeSpec(TypeSpec):
    def __init__(self, base, range_spec):
        TypeSpec.__init__(self, base.name)
        self.base = base
        (ranges, ranges_pos) = range_spec
        self.ranges = ranges
        self.ranges_pos = ranges_pos
        if ranges:
            self.min = ranges[0][0]
            if self.min == 'min':
                self.min = base.min
            self.max = ranges[-1][1]
            if self.max is None: # single range
                self.max = ranges[-1][0]
            if self.max == 'max':
                self.max = base.max
        else:
            self.min = base.min
            self.max = base.max
        if hasattr(base, 'fraction_digits'):
            self.fraction_digits = base.fraction_digits

    def str_to_val(self, errors, pos, string, module):
        return self.base.str_to_val(errors, pos, string, module)

    def validate(self, errors, pos, val, module, errstr=''):
        def inner_validate(errors, pos, val, module, errstr):
            if self.base.validate(errors, pos, val, module, errstr) is False:
                return False, None
            for lo, hi in self.ranges:
                cur_hi = self.max if hi == 'max' else hi
                if lo == 'min':
                    cur_lo = self.min
                elif lo == 'max':
                    cur_lo = self.max
                else:
                    cur_lo = lo
                if ((lo == 'min' or lo == 'max' or val >= cur_lo) and
                        ((hi is None and val == cur_lo) or hi == 'max' or
                         (hi is not None and val <= cur_hi))):
                    return True, (lo, hi)
            err_add(errors, pos, 'TYPE_VALUE',
                    (str(val), self.definition, 'range error' + errstr +
                     ' for range defined at ' + str(self.ranges_pos)))
            return False, None

        if isinstance(val, tuple):
            common_restriction(errors, pos, val, module, self, 'range',
                               inner_validate, errstr)
        else:
            res, ranges = inner_validate(errors, pos, val, module, errstr)
            return res

    def restrictions(self):
        return self.base.restrictions()

def common_restriction(errors, pos, val, module, obj, type_name, handler, errstr):
    res = True
    lowRange = None
    highRange = None
    ranges_pos = None
    low, high = val
    if isinstance(obj, RangeTypeSpec):
        ranges_pos = obj.ranges_pos
    else:
        ranges_pos = obj.length_pos

    if low is not None and low == 'max':
        if high is not None:
            err_add(errors, pos, 'TYPE_VALUE',
                    (str(val), obj.definition, type_name + ' error' + errstr +
                     ' for ' + type_name + ' defined at ' + str(ranges_pos)))
            return False
        return True

    if low is not None and low == 'min':
        low = obj.min
    res, lowRange = handler(errors, pos, low, module, errstr)
    if high is None:
        return res
    elif high == 'max':
        high = obj.max
    elif high == 'min':
        return False

    if res is True and lowRange is not None:
        check = False
        if lowRange[1] is None:
            check = high != lowRange[0]
        elif lowRange[1] != 'max':
            check = high > lowRange[1]
        if check:
            err_add(errors, pos, 'TYPE_VALUE',
                    (str(val[1]), obj.definition, type_name + ' error' + errstr +
                     ' for ' + type_name + ' defined at ' + str(ranges_pos)))
            return False
    return res

def get_ancestor_typespec_skip_pattern(type_spec):
    if type_spec is None:
        return None
    if isinstance(type_spec, PatternTypeSpec):
        return get_ancestor_typespec_skip_pattern(type_spec.base)
    return type_spec

def validate_length_expr(errors, stmt, type_stmt):
    def f(lostr, histr):
        try:
            if lostr in ['min', 'max']:
                lo = lostr
            else:
                lo = int(lostr)
        except ValueError:
            err_add(errors, stmt.pos, 'TYPE_VALUE',
                    (lostr, '', 'not an integer'))
            return (None, None)
        try:
            if histr == '':
                # this means that a single number was in the length, e.g.
                # "4 | 5..6".
                return (lo, None)
            if histr in ['min', 'max']:
                hi = histr
            else:
                hi = int(histr)
        except ValueError:
            err_add(errors, stmt.pos, 'TYPE_VALUE',
                    (histr, '', 'not an integer'))
            return None
        return (lo, hi)

    lengths = [f(m[1], m[3]) for m in syntax.re_length_part.findall(stmt.arg)]
    length_typespec = get_ancestor_typespec_skip_pattern(type_stmt.i_type_spec)
    # make sure the length values are of correct type and increasing
    cur_lo = None
    for lo, hi in lengths:
        if isinstance(length_typespec, LengthTypeSpec):
            length_typespec.validate(errors, stmt.pos, (lo, hi), None)
        else:
            if lo is not None and lo != 'min' and lo != 'max':
                length_typespec.validate(errors, stmt.pos, lo, None)
            if hi is not None and hi != 'min' and hi != 'max':
                length_typespec.validate(errors, stmt.pos, hi, None)
        # check that cur_lo < lo < hi
        if not is_smaller(cur_lo, lo):
            err_add(errors, stmt.pos, 'LENGTH_BOUNDS', (str(lo), cur_lo))
            return None
        if not is_smaller(lo, hi):
            err_add(errors, stmt.pos, 'LENGTH_BOUNDS', (str(hi), str(lo)))
            return None
        if (lo == 'max' and cur_lo is not None and cur_lo != 'min'
                and cur_lo >= length_typespec.max):
            err_add(errors, stmt.pos, 'LENGTH_BOUNDS', (str(lo), str(cur_lo)))
            return None
        if (lo == 'min' and hi is not None and
                hi != 'max' and hi < length_typespec.min):
            err_add(errors, stmt.pos, 'LENGTH_BOUNDS', (str(lo), str(hi)))
            return None
        if hi is None:
            cur_lo = lo
        else:
            cur_lo = hi
    return (lengths, stmt.pos)

class LengthTypeSpec(TypeSpec):
    def __init__(self, base, length_spec):
        TypeSpec.__init__(self, base.name)
        self.base = base
        (lengths, length_pos) = length_spec
        self.lengths = lengths
        self.length_pos = length_pos
        length_base = get_ancestor_typespec_skip_pattern(base)
        if lengths:
            self.min = lengths[0][0]
            if self.min == 'min':
                self.min = length_base.min
            self.max = lengths[-1][1]
            if self.max is None:  # single range
                self.max = lengths[-1][0]
            if self.max == 'max':
                self.max = length_base.max
        else:
            self.min = length_base.min
            self.max = length_base.max

    def str_to_val(self, errors, pos, string, module):
        return self.base.str_to_val(errors, pos, string, module)

    def validate(self, errors, pos, val, module, errstr=''):
        def inner_validate(errors, pos, val, module, errstr):
            vallen = None
            if isinstance(val, util.int_types):
                # check whether the lengths value meets the specs
                cur_base = get_ancestor_typespec_skip_pattern(self.base)
                if (cur_base is not None
                        and cur_base.validate(errors, pos, val,
                                              module, errstr) is False):
                    return False, None
                vallen = val
            else:
                # check whether the default value meets the specs
                if self.base.validate(errors, pos, val,
                                      module, errstr) is False:
                    return False, None
                vallen = len(val)
            for lo, hi in self.lengths:
                cur_hi = self.max if hi == 'max' else hi
                if lo == 'min':
                    cur_lo = self.min
                elif lo == 'max':
                    cur_lo = self.max
                else:
                    cur_lo = lo
                if ((lo == 'min' or lo == 'max' or vallen >= cur_lo) and
                    ((hi is None and vallen == cur_lo) or hi == 'max' or
                     (hi is not None and vallen <= cur_hi))):
                    return True, (lo, hi)
            err_add(errors, pos, 'TYPE_VALUE',
                    (val, self.definition, 'length error' + errstr +
                     ' for length defined at ' + str(self.length_pos)))
            return False, None

        if isinstance(val, tuple):
            common_restriction(errors, pos, val, module, self, 'length',
                               inner_validate, errstr)
        else:
            res, ranges = inner_validate(errors, pos, val, module, errstr)
            return res

    def restrictions(self):
        return self.base.restrictions()


class XSDPattern(object):

    SCHEMA = '''<?xml version="1.0"?>
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="a">
                  <xs:simpleType>
                    <xs:restriction base="xs:string">
                      <xs:pattern value=""/>
                    </xs:restriction>
                  </xs:simpleType>
                </xs:element>
                </xs:schema>'''

    AVALUE = '<a/>'

    # Shared etree elements initialized with first instance
    _schema = None
    _pattern = None
    _avalue = None

    @classmethod
    def _prepare_documents(cls):
        if cls._schema is None:
            cls._schema = lxml.etree.fromstring(cls.SCHEMA)
            cls._avalue = lxml.etree.fromstring(cls.AVALUE)
            cls._pattern = cls._schema[0][0][0][0]

    def __init__(self, spec, pos, invert_match):
        self._prepare_documents()
        self.spec = spec
        self.pos = pos
        self.invert_match = invert_match

        self._pattern.set('value', spec)
        try:
            self.schema = lxml.etree.XMLSchema(etree=self._schema)
        except lxml.etree.XMLSchemaParseError as err:
            self.schema = None
            self.error = err
        else:
            self.error = None

    def __call__(self, value):
        if self.schema is None:
            return None
        self._avalue.text = value
        return self.schema.validate(self._avalue) is not self.invert_match

    def __str__(self):
        return self.spec

    def __repr__(self):
        return repr(self.spec)

    def __bool__(self):
        return self.error is None
    __nonzero__ = __bool__


def validate_pattern_expr(errors, stmt):
    invert_match = stmt.search_one('modifier', arg='invert-match') is not None
    pattern = XSDPattern(stmt.arg, stmt.pos, invert_match)
    if pattern:
        return pattern
    else:
        err_add(errors, stmt.pos, 'PATTERN_ERROR', pattern.error)
        return None


class PatternTypeSpec(TypeSpec):
    def __init__(self, base, pattern_specs):
        TypeSpec.__init__(self, base.name)
        self.base = base
        self.res = pattern_specs

    def str_to_val(self, errors, pos, string, module):
        return self.base.str_to_val(errors, pos, string, module)

    def validate(self, errors, pos, val, module, errstr=''):
        if self.base.validate(errors, pos, val, module, errstr) is False:
            return False
        for pattern in self.res:
            if pattern(val) is False:
                msg = ('pattern mismatch {errstr} for pattern defined at {pos}'
                       .format(errstr=errstr, pos=pattern.pos))
                err_add(errors, pos, 'TYPE_VALUE', (val, self.definition, msg))
                return False
        return True

    def restrictions(self):
        return self.base.restrictions()

def validate_enums(errors, enums, stmt):
    # make sure all names and values given are unique
    names = {}
    values = {}
    auto = 0
    for e in enums:
        # for derived enumerations, make sure the enum is defined
        # in the base
        stmt.i_type_spec.validate(errors, e.pos, e.arg, stmt.i_module, "")
        e.i_value = None
        value = e.search_one('value')
        if value is not None:
            try:
                x = int(value.arg)
                # for derived enumerations, make sure the value isn't changed
                oldval = stmt.i_type_spec.get_value(e.arg)
                if oldval is not None and oldval != x:
                    err_add(errors, value.pos, 'BAD_ENUM_VALUE',
                            (value.arg, oldval))
                e.i_value = x
                if x < -2147483648 or x > 2147483647:
                    raise ValueError
                if x >= auto:
                    auto = x + 1
                if x in values:
                    err_add(errors, value.pos, 'DUPLICATE_ENUM_VALUE',
                            (x, values[x]))
                else:
                    values[x] = value.pos

            except ValueError:
                err_add(errors, value.pos, 'ENUM_VALUE', value.arg)
        else:
            # auto-assign a value
            values[auto] = e.pos
            if auto > 2147483647:
                err_add(errors, e.pos, 'ENUM_VALUE', str(auto))
            e.i_value = auto
            auto = auto + 1
        if e.arg in names:
            err_add(errors, e.pos, 'DUPLICATE_ENUM_NAME', (e.arg, names[e.arg]))
        else:
            names[e.arg] = e.pos

    # check status (here??)
    return enums

class EnumerationTypeSpec(TypeSpec):
    def __init__(self):
        TypeSpec.__init__(self, 'enumeration')

    def get_value(self, val):
        return None

    def restrictions(self):
        return ['enum']

class EnumTypeSpec(TypeSpec):
    def __init__(self, base, enums):
        TypeSpec.__init__(self, base.name)
        self.base = base
        self.enums = [(e.arg, e.i_value) for e in enums]

    def validate(self, errors, pos, val, _module, errstr=''):
        if util.keysearch(val, 0, self.enums) is None:
            err_add(errors, pos, 'TYPE_VALUE',
                    (val, self.definition, 'enum not defined' + errstr))
            return False
        else:
            return True

    def get_value(self, val):
        r  = util.keysearch(val, 0, self.enums)
        if r is not None:
            return r[1]
        else:
            return None

    def restrictions(self):
        return self.base.restrictions()

def validate_bits(errors, bits, stmt):
    # make sure all names and positions given are unique
    names = {}
    values = {}
    auto = 0
    for b in bits:
        # for derived bits, make sure the bit is defined
        # in the base
        stmt.i_type_spec.validate(errors, b.pos, [b.arg], stmt.i_module, "")
        position = b.search_one('position')
        if position is not None:
            try:
                x = int(position.arg)
                # for derived bits, make sure the position isn't changed
                oldpos = stmt.i_type_spec.get_position(b.arg)
                if oldpos is not None and oldpos != x:
                    err_add(errors, position.pos, 'BAD_BIT_POSITION',
                            (position.arg, oldpos))
                b.i_position = x
                if x < 0 or x > 4294967295:
                    raise ValueError
                if x >= auto:
                    auto = x + 1
                if x in values:
                    err_add(errors, position.pos, 'DUPLICATE_BIT_POSITION',
                            (x, values[x]))
                else:
                    values[x] = position.pos
            except ValueError:
                err_add(errors, position.pos, 'BIT_POSITION', position.arg)
        else:
            # auto-assign a value
            if auto > 4294967295:
                err_add(errors, b.pos, 'BIT_POSITION', str(auto))
            values[auto] = b.pos
            b.i_position = auto
            auto = auto + 1
        if b.arg in names:
            err_add(errors, b.pos, 'DUPLICATE_BIT_NAME', (b.arg, names[b.arg]))
        else:
            names[b.arg] = b.pos

    # check status (here??)
    return bits

class BitsTypeSpec(TypeSpec):
    def __init__(self):
        TypeSpec.__init__(self, 'bits')

    def get_position(self, bit):
        return None

    def restrictions(self):
        return ['bit']

class BitTypeSpec(TypeSpec):
    def __init__(self, base, bits):
        TypeSpec.__init__(self, base.name)
        self.base = base
        self.bits = []
        for b in bits:
            if hasattr(b, "i_position"):
                self.bits.append((b.arg, b.i_position))

    def str_to_val(self, errors, pos, string, _module):
        return string.split()

    def validate(self, errors, pos, val, _module, errstr=''):
        for v in val:
            if util.keysearch(v, 0, self.bits) is None:
                err_add(errors, pos, 'TYPE_VALUE',
                        (v, self.definition, 'bit not defined' + errstr))
                return False
        return True

    def get_position(self, bit):
        r  = util.keysearch(bit, 0, self.bits)
        if r is not None:
            return r[1]
        else:
            return None

    def restrictions(self):
        return self.base.restrictions()

def validate_path_expr(errors, path):

    # FIXME: rewrite using the new xpath tokenizer

    # PRE: s matches syntax.path_arg
    # -type dn [identifier | ('predicate', identifier, up::int(), [identifier])]
    # Ret: (up::int(),
    #       dn::dn(),
    #       derefup::int(),
    #       derefdn::dn())
    def parse_keypath(s):

        def parse_dot_dot(s):
            up = 0
            i = 0
            while True:
                if s[i] == '.' and s[i+1] == '.':
                    up = up + 1
                    i = i + 3 # skip the '/'
                elif s[i] == '/':
                    i = i + 1 # skip the '/'
                    if up == 0: # absolute path
                        up = -1
                    break
                elif s[i].isspace():
                    i = i + 1
                else:
                    # s points to an identifier
                    break
            return (up, s[i:])

        def skip_space(s):
            if len(s) == 0:
                return s
            i = 0
            while s[i].isspace():
                i = i + 1
            return s[i:]

        def parse_identifier(s):
            m = syntax.re_keyword_start.match(s)
            if m is None:
                raise Abort
            s = s[m.end():]
            if m.group(2) is None:
                # no prefix
                return (m.group(3), s)
            else:
                prefix = m.group(2)
                mod = util.prefix_to_module(path.i_module, prefix,
                                            path.pos, errors)
                if mod is not None:
                    return ((m.group(2), m.group(3)), s)
                else:
                    raise Abort

        def parse_key_predicate(s):
            s = s[1:] # skip '['
            s = skip_space(s)
            (identifier, s) = parse_identifier(s)
            s = skip_space(s)
            s = s[1:] # skip '='
            s = skip_space(s)
            if s[:7] == 'current':
                s = s[7:] # skip 'current'
                s = skip_space(s)
                s = s[1:] # skip '('
                s = skip_space(s)
                s = s[1:] # skip ')'
                s = skip_space(s)
                s = s[1:] # skip '/'
                s = skip_space(s)
                (up, s) = parse_dot_dot(s)
                s = skip_space(s)
            else:
                up = -1
                b = s.find(']') + 1
                s = s[b:]
                if len(s) > 0 and s[0] == '/':
                    s = s[1:] # skip '/'
            dn = []
            while len(s) > 0:
                (xidentifier, s) = parse_identifier(s)
                dn.append(xidentifier)
                s = skip_space(s)
                if len(s) == 0:
                    break
                if s[0] == '/':
                    s = s[1:] # skip '/'
                elif s[0] == ']':
                    s = s[1:] # skip ']'
                    break
            return (('predicate', identifier, up, dn), s)

        def parse_descendant(s):
            dn = []
            # all '..'s are now parsed
            while len(s) > 0 and (not s[0].isspace()) and s[0] != ')':
                (identifier, s) = parse_identifier(s)
                dn.append(identifier)
                s = skip_space(s)
                if len(s) == 0:
                    break
                while len(s) > 0 and s[0] == '[':
                    (pred, s) = parse_key_predicate(s)
                    dn.append(pred)
                    s = skip_space(s)
                if len(s) > 0 and s[0] == '/':
                    s = s[1:] # skip '/'

            return (dn, s)

        derefup = 0
        derefdn = None
        if s.startswith('deref'):
            s = s[5:] # skip 'deref'
            s = skip_space(s)
            s = s[1:] # skip '('
            s = skip_space(s)
            (derefup, s) = parse_dot_dot(s)
            (derefdn, s) = parse_descendant(s)
            s = skip_space(s)
            s = s[1:] # skip ')'
            s = skip_space(s)
            s = s[1:] # skip '/'

        (up, s) = parse_dot_dot(s)
        (dn, s) = parse_descendant(s)
        return (up, dn, derefup, derefdn)

    try:
        return parse_keypath(path.arg)
    except Abort:
        return None

class LeafrefTypeSpec(TypeSpec):
    def __init__(self):
        TypeSpec.__init__(self, 'leafref')
        self.require_instance = True

    def restrictions(self):
        return ['path', 'require-instance']

class InstanceIdentifierTypeSpec(TypeSpec):
    def __init__(self):
        TypeSpec.__init__(self, 'instance-identifier')
        self.require_instance = True

    def restrictions(self):
        return ['require-instance']

class PathTypeSpec(TypeSpec):
    def __init__(self, base, path_spec, path, pos):
        TypeSpec.__init__(self, base.name)
        self.require_instance = True
        self.base = base
        self.path_spec = path_spec
        self.path_ = path
        self.pos = pos


    def str_to_val(self, errors, pos, string, module):
        if hasattr(self, 'i_target_node'):
            return self.i_target_node.search_one('type').\
                i_type_spec.str_to_val(errors, pos, string, module)
        else:
            # if a default value is verified
            return string

    def validate(self, errors, pos, val, module, errstr=''):
        if hasattr(self, 'i_target_node'):
            return self.i_target_node.search_one('type').\
                i_type_spec.validate(errors, pos, val, module, errstr)
        else:
            # if a default value is verified
            return True

    def restrictions(self):
        return ['require-instance']

class UnionTypeSpec(TypeSpec):
    def __init__(self, types):
        TypeSpec.__init__(self, 'union')
        # no base - no restrictions allowed
        self.types = types

    def str_to_val(self, errors, pos, string, _module):
        return string

    def validate(self, errors, pos, val, module, errstr=''):
        # try to validate against each membertype
        for t in self.types:
            if t.i_type_spec is not None:
                t_val = t.i_type_spec.str_to_val([], pos, val, module)
                if t_val is not None:
                    if t.i_type_spec.validate([], pos, t_val, module):
                        return True
        err_add(errors, pos, 'TYPE_VALUE',
                (val, self.definition, 'no member type matched' + errstr))
        return False

yang_type_specs = {
   'int8': IntTypeSpec('int8', -128, 127),
   'int16': IntTypeSpec('int16', -32768, 32767),
   'int32': IntTypeSpec('int32', -2147483648, 2147483647),
   'int64': IntTypeSpec('int64', -9223372036854775808, 9223372036854775807),
   'uint8': IntTypeSpec('uint8', 0, 255),
   'uint16': IntTypeSpec('uint16', 0, 65535),
   'uint32': IntTypeSpec('uint32', 0, 4294967295),
   'uint64': IntTypeSpec('uint64', 0, 18446744073709551615),
   'decimal64': TypeSpec('decimal64'),
   'string': StringTypeSpec(),
   'boolean': BooleanTypeSpec(),
   'enumeration': EnumerationTypeSpec(),
   'bits': BitsTypeSpec(),
   'binary': BinaryTypeSpec(),
   'leafref': LeafrefTypeSpec(),
   'identityref': TypeSpec('identityref'),
   'instance-identifier': InstanceIdentifierTypeSpec(),
   'empty': EmptyTypeSpec(),
   'union': TypeSpec('union'),
   }

def is_base_type(typename):
    return typename in yang_type_specs

def is_smaller(lo, hi):
    if lo is None:
        return True
    if lo == 'min' and hi != 'min':
        return True
    if lo == 'max' and hi is not None:
        return False
    if hi == 'min':
        return False
    if hi is None:
        return True
    if hi == 'max':
        return True
    return lo < hi
