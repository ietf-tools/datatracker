# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import os
import re
from pyquery import PyQuery
from urllib.parse import urlparse, urlsplit, urlunsplit


from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, URLValidator, EmailValidator, _lazy_re_compile, BaseValidator
from django.template.defaultfilters import filesizeformat
from django.utils.deconstruct import deconstructible
from django.utils.ipv6 import is_valid_ipv6_address
from django.utils.translation import gettext_lazy as _

import debug                            # pyflakes:ignore

from ietf.utils.mime import get_mime_type

# Note that this is an instantiation of the regex validator, _not_ the
# regex-string validator defined right below
validate_no_control_chars = RegexValidator(
                                    regex="^[^\x00-\x1f]*$",
                                    message="Please enter a string without control characters." )


@deconstructible
class RegexStringValidator(object):
    "Validates that a given regular expression can be compiled."

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
                                    % (value, e))
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

def validate_file_size(file, missing_ok=False):
    try:
        size = file.size
    except FileNotFoundError:
        if missing_ok:
            return
        else:
            raise

    if size > settings.SECR_MAX_UPLOAD_SIZE:
        raise ValidationError('Please keep filesize under %s. Requested upload size was %s' % (filesizeformat(settings.SECR_MAX_UPLOAD_SIZE), filesizeformat(file.size)))

def validate_mime_type(file, valid, missing_ok=False):
    try:
        file.open()
    except FileNotFoundError:
        if missing_ok:
            return None, None
        else:
            raise
    raw = file.read()
    mime_type, encoding = get_mime_type(raw)
    # work around mis-identification of text where a line has 'virtual' as
    # the first word:
    if mime_type == 'text/x-c++' and re.search(br'(?m)^virtual\s', raw):
        mod = raw.replace(b'virtual', b' virtual')
        mime_type, encoding = get_mime_type(mod)
    if valid and not mime_type in valid:
        raise ValidationError('Found content with unexpected mime type: %s.  Expected one of %s.' %
                                    (mime_type, ', '.join(valid) ))
    return mime_type, encoding

@deconstructible
class WrappedValidator:
    """Helper for attaching a validate function with parameters to a model

    This captures extra arguments to migration functions in a way that is compatible
    with Django's migrations. E.g., WrappedValidator(validate_mime_type, valid_type_list)
    will arrange to call validate_mime_type.
    """
    def __init__(self, validate_method, *args):
        self.validate_method = validate_method
        self.args = args

    def __call__(self, inst):
        return self.validate_method(inst, *self.args)

    def __eq__(self, other):
        return all([
            isinstance(other, WrappedValidator),
            (self.validate_method == other.validate_method),
            (self.kwargs == other.kwargs)
        ])

def validate_file_extension(file, valid):
    name, ext = os.path.splitext(file.name)
    if ext.lower() not in valid:
        raise ValidationError('Found an unexpected extension: %s.  Expected one of %s' % (ext, ','.join(valid)))
    return ext

def validate_no_html_frame(file):
    file.open()
    q = PyQuery(file.read())
    if q("frameset") or q("frame") or q("iframe"):
        raise ValidationError('Found content with html frames.  Please upload a file that does not use frames')

# instantiations of sub-validiators used by the external_resource validator

validate_url = URLValidator()
validate_http_url = URLValidator(schemes=['http','https'])
validate_email = EmailValidator()

def validate_ipv6_address(value):
    if not is_valid_ipv6_address(value):
        raise ValidationError(_('Enter a valid IPv6 address.'), code='invalid')

@deconstructible
class XMPPURLValidator(RegexValidator):
    ul = '\u00a1-\uffff'  # unicode letters range (must not be a raw string)

    # IP patterns
    ipv4_re = r'(?:25[0-5]|2[0-4]\d|[0-1]?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3}'
    ipv6_re = r'\[[0-9a-f:\.]+\]'  # (simple regex, validated later)

    # Host patterns
    hostname_re = r'[a-z' + ul + r'0-9](?:[a-z' + ul + r'0-9-]{0,61}[a-z' + ul + r'0-9])?'
    # Max length for domain name labels is 63 characters per RFC 1034 sec. 3.1
    domain_re = r'(?:\.(?!-)[a-z' + ul + r'0-9-]{1,63}(?<!-))*'
    tld_re = (
        r'\.'                                # dot
        r'(?!-)'                             # can't start with a dash
        r'(?:[a-z' + ul + '-]{2,63}'         # domain label
        r'|xn--[a-z0-9]{1,59})'              # or punycode label
        r'(?<!-)'                            # can't end with a dash
        r'\.?'                               # may have a trailing dot
    )
    host_re = '(' + hostname_re + domain_re + tld_re + '|localhost)'

    regex = _lazy_re_compile(
        r'^(?:xmpp:)'  # Note there is no '//'
        r'(?:[^\s:@/]+(?::[^\s:@/]*)?@)?'  # user:pass authentication
        r'(?:' + ipv4_re + '|' + ipv6_re + '|' + host_re + ')'
        r'(?::\d{2,5})?'  # port
        r'(?:[/?#][^\s]*)?'  # resource path
        r'\Z', re.IGNORECASE)
    message = _('Enter a valid URL.')
    schemes = ['http', 'https', 'ftp', 'ftps']

    def __call__(self, value):
        try:
            super().__call__(value)
        except ValidationError as e:
            # Trivial case failed. Try for possible IDN domain
            if value:
                try:
                    scheme, netloc, path, query, fragment = urlsplit(value)
                except ValueError:  # for example, "Invalid IPv6 URL"
                    raise ValidationError(self.message, code=self.code)
                try:
                    netloc = netloc.encode('idna').decode('ascii')  # IDN -> ACE
                except UnicodeError:  # invalid domain part
                    raise e
                url = urlunsplit((scheme, netloc, path, query, fragment))
                super().__call__(url)
            else:
                raise
        else:
            # Now verify IPv6 in the netloc part
            host_match = re.search(r'^\[(.+)\](?::\d{2,5})?$', urlsplit(value).netloc)
            if host_match:
                potential_ip = host_match.groups()[0]
                try:
                    validate_ipv6_address(potential_ip)
                except ValidationError:
                    raise ValidationError(self.message, code=self.code)

        # The maximum length of a full host name is 253 characters per RFC 1034
        # section 3.1. It's defined to be 255 bytes or less, but this includes
        # one byte for the length of the name and one byte for the trailing dot
        # that's used to indicate absolute names in DNS.
        if len(urlsplit(value).netloc) > 253:
            raise ValidationError(self.message, code=self.code)

validate_xmpp = XMPPURLValidator()

def validate_external_resource_value(name, value):
    """ validate a resource value using its name's properties """

    if name.type_id == 'url':

        if name.slug in ( 'github_org', 'github_repo' ):
            validate_http_url(value)
            parsed_url = urlparse(value)
            hostname = parsed_url.netloc.lower()
            if not any([ hostname.endswith(x) for x in ('github.com','github.io' ) ]):
                raise ValidationError('URL must be a github url')
            if name.slug == 'github_org' and len(parsed_url.path.strip('/').split('/'))!=1:
                raise ValidationError('github path has too many components to be an organization URL')
        elif name.slug == 'jabber_room':
            validate_xmpp(value)
        else:
            validate_url(value)

    elif name.type.slug == 'email':
        validate_email(value)

    elif name.type.slug == 'string':
        pass

    else:
        raise ValidationError('Unknown resource type '+name.type.name)


@deconstructible
class MaxImageSizeValidator(BaseValidator):
    """Validate that an image is no longer than a given size"""
    message = 'Ensure this image is smaller than %(limit_value)s (it is %(show_value)s)'
    code = 'max_image_size'

    def __init__(self, max_width, max_height):
        super().__init__(limit_value=(max_width, max_height))

    def compare(self, a, b):
        return (a[0] > b[0]) or (a[1] > b[1])

    def clean(self, x):
        try:
            return x.width, x.height
        except FileNotFoundError:
            return 0, 0  # don't fail if the image is missing
