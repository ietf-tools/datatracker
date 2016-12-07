# -*- python -*-
# Copyright The IETF Trust 2007, All Rights Reserved
from __future__ import unicode_literals

import re

from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible

@deconstructible
class RegexStringValidator(object):

    def __init__(self):
        pass

    def __call__(self, value):
        """
        Validates that the given regular expression can be compiled.
        """
        try:
            re.compile(value)
        except Exception as e:
            raise ValidationError('Please enter a valid regular expression.  '
                                    'Got an error when trying to compile this: "%s" : "%s"'
                                    % (self.message, value, e))
        if '-*' in value:
            raise ValidationError('Did you really mean that?  The regular expression '
                                    'contains "-*" which will match zero or more dashes.  '
                                    'Maybe you meant to write "-.*"?  If you actually meant "-*", '
                                    'you can use "[-]*" instead to get past this error.')

    def __eq__(self, other):
        return isinstance(other, RegexStringValidator)

    def __ne__(self, other):
        return not (self == other)

validate_regular_expression_string = RegexStringValidator()
