# Copyright The IETF Trust 2018, All Rights Reserved
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, division

import math

# ----------------------------------------------------------------------
# Base conversions.
# From http://tech.vaultize.com/2011/08/python-patterns-number-to-base-x-and-the-other-way/

DEFAULT_DIGITS = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
 
def num_to_baseX(num, digits=DEFAULT_DIGITS):
   if num < 0: return '-' + num_to_baseX(-num)
   if num == 0: return digits[0]
   X = len(digits)
   s = ''
   while num > 0:
        s = digits[num % X] + s
        num //= X
 
   return s
 
def baseX_to_num(s, digits=DEFAULT_DIGITS):
   if s[0] == '-': return -1 * baseX_to_num(s[1:])
   ctopos = dict([(c, pos) for pos, c in enumerate(digits)])
   X = len(digits)
   num = 0
   for c in s: num = num * X + ctopos[c]
   return num


# Use the generic base conversion to create list letters

def int2letter(num):
    return num_to_baseX(num-1, "abcdefghijklmnopqrstuvwxyz")

def int2roman(number):
    numerals = { 
        1 : "i", 
        4 : "iv", 
        5 : "v", 
        9 : "ix", 
        10 : "x", 
        40 : "xl", 
        50 : "l", 
        90 : "xc", 
        100 : "c", 
        400 : "cd", 
        500 : "d", 
        900 : "cm", 
        1000 : "m" 
    }
    if number > 3999:
        raise NotImplementedError("Can't handle roman numerals larger than 3999")
    result = ""
    for value, numeral in sorted(numerals.items(), reverse=True):
        while number >= value:
            result += numeral
            number -= value
    return result


roman_max_widths = { 1:1,  2:2,  3:3,  4:3,  5:3,  6:3,  7:3,  8:4,  9:4,
                10:4, 11:4, 12:4, 13:4, 14:4, 15:4, 16:4, 17:4, 18:5, 19:5,
                20:5, 21:5, 22:5, 23:5, 24:5, 25:5, 26:5, 27:5, 28:6, 29:6, }

def update_roman_max_widths(n):
    if n > 3999:
        raise NotImplementedError("Can't handle roman numerals larger than 3999")
    m = len(roman_max_widths)
    wmax = 0
    for i in range(n+32):
        w = len(int2roman(i))
        if w > wmax:
            wmax = w
        if n > m:
            roman_max_widths[n] = wmax

def num_width(type, num):
    """
    Return the largest width taken by the numbering of a list
    with num items (without punctuation)
    """
    if   type in ['a','A','c','C',]:
        return int(math.log(num, 26))+1
    elif type in ['1','d',]:
        return int(math.log(num, 10))+1
    elif type in ['o','O',]:
        return int(math.log(num, 8))+1
    elif type in ['x','X',]:
        return int(math.log(num, 16))+1
    elif type in ['i','I',]:
        m = len(roman_max_widths)
        if num > m:
            update_roman_max_widths(num)
        return roman_max_widths[num]
    else:
        raise ValueError("Unexpected type argument to num_width(): '%s'" % (type, ))


ol_style_formatter = {
    None:   lambda n: tuple(),
    'a':    lambda n: tuple([int2letter(n)]),
    'A':    lambda n: tuple([int2letter(n).upper()]),
    'c':    lambda n: tuple([int2letter(n)]),
    'C':    lambda n: tuple([int2letter(n).upper()]),
    '1':    lambda n: tuple([n]),
    'd':    lambda n: tuple([n]),
    'i':    lambda n: tuple([int2roman(n)]),
    'I':    lambda n: tuple([int2roman(n).upper()]),
    'o':    lambda n: tuple(['%o'%n]),
    'O':    lambda n: tuple([('%o'%n).upper()]),
    'x':    lambda n: tuple(['%x'%n]),
    'X':    lambda n: tuple(['%X'%n]),
}

