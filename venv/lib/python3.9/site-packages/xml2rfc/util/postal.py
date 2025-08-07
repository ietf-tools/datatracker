# Copyright The IETF Trust 2017, All Rights Reserved
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function

import i18naddress
import lxml.etree
import pycountry
import re
import xml2rfc.log

try:
    from xml2rfc import debug
    debug.debug = True
except ImportError:
    pass

from xml2rfc.util.name import full_author_name, full_author_ascii_name, full_org_name, full_org_ascii_name

address_field_mapping = dict(i18naddress.FIELD_MAPPING)
address_field_mapping.update({'E':'extended_address', 'Y':'country_name'})

address_field_elements = {
    # mapping from address fields to element tags
#    'name':             'fullname',
#    'company_name':     'organization',
    'extended_address': '<extaddr>',
    'street_address':   '<street>',
    'sorting_code':     '<sortingcode>',
    'postal_code':      '<code>',
    'city_area':        '<cityarea>',
    'city':             '<city>',
    'country_area':     '<region>',
    'country_name':     '<country>',
}

address_hcard_properties = {
    'name':             'fn nameRole',
    'company_name':     'org',
    'extended_address': 'extended-address',
    'street_address':   'street-address',
    'sorting_code':     'postal-code',
    'postal_code':      'postal-code',
    'city_area':        'locality',
    'city':             'locality',
    'country_area':     'region',
    'country_name':     'country-name'
}

def get_value(e, latin=True):
    if latin:
        value = e.get('ascii') or e.text or ''
    else:
        value = e.text or ''
    return value

country_alias = {
    "UK": "United Kingdom",
    "Republic of Korea": "Korea, Republic of",
    "South Korea": "Korea, Republic of",
    "North Korea": "Democratic People's Republic of Korea",
    "P.R. China": "China",
    "Åland": "Åland Islands",
    # Reordering of comma-separated name components:
    "The Democratic Republic of the Congo": "Congo, The Democratic Republic of the",
    "State of Palestine": "Palestine, State of",
    "U.S. Virgin Islands": "Virgin Islands, U.S.",
}

def get_iso_country_info(e):
    country_info = None
    ascii = e.get('ascii')
    if ascii:
        name = ascii.strip()
    elif e.text:
        name = e.text.strip()
    else:
        return None
    # Special case, this is used but unknown to pycountry
    if name in country_alias:
        name = country_alias[name]
    try:
        if hasattr(pycountry.countries, 'lookup'):
            country_info = pycountry.countries.lookup(name)
        else:
            # Workaround for old versions of pycountry.  The transition from
            # using alpha2 to alpha_2 coincides with the presence of a
            # lookup() method for regular releases (there's a discrepancy for
            # rc versions 16.10.23rc*)
            if len(name) == 2:
                country_info = pycountry.countries.get(alpha2=name.upper())
            else:
                country_info = pycountry.countries.get(name=name.title())
            country_info.alpha_2 = country_info.alpha2
    except LookupError:
        estr = lxml.etree.tostring(e).replace(b' xmlns:xi="http://www.w3.org/2001/XInclude"', b'').strip().decode('utf-8')
        if e.tag == 'country':
            xml2rfc.log.warn("Country lookup failed for %s.  Use --country-help to show recognized country names and codes" % (estr, ))
        else:
            xml2rfc.log.note("Country lookup failed for %s.  Use --country-help to show recognized country names and codes" % (estr, ))
        pass
    return country_info

def get_normalized_address_info(writer, x, latin=False):
    author = x.getparent().getparent()
    name = full_author_ascii_name(author) if latin else full_author_name(author)
    role = author.get('role')
    company = full_org_ascii_name(author) if latin else full_org_name(author)
    country_info = None
    country_element = x.find('country')
    if country_element != None and country_element.text:
        country_info = get_iso_country_info(country_element)
    if not country_info:
        for c in x.getchildren():
            if c.tag == "postalLine":
                country_info = get_iso_country_info(c)
                if country_info:
                    country_element = c
                    break
    if country_info:
        country_name = get_value(country_element, latin=latin)
        if country_name in ['US', 'USA']:
            country_name = country_info.official_name
        elif re.match('[A-Z]{2,3}', country_name):
            country_name = country_info.name
        adr = {
                'name': name,
                'role': role,
                'company_name': company,
                'extended_address': [],
                'street_address': [],
                'sorting_code': '',
                'postal_code': '',
                'city_area': '',
                'city': '',
                'country_area': '',
                'country_code': country_info.alpha_2,
                'country_name': country_name,
            }
    else:
        adr = {
                'name': name,
                'role': role,
                'company_name': company,
                'extended_address': [],
                'street_address': [],
                'sorting_code': '',
                'postal_code': '',
                'city_area': '',
                'city': '',
                'country_area': '',
                'country_code': '',
                'country_name': ''
            }
    for c in x.getchildren():
        if c == country_element:
            continue
        # Some of these will overwrite data if there are multiple elements
        value = get_value(c, latin=latin)
        if value:
            if   c.tag == 'extaddr':
                adr['extended_address'].append(value)
            elif c.tag in ['street', 'postalLine', 'pobox']:
                adr['street_address'].append(value)
            elif c.tag == 'cityarea':
                adr['city_area'] = value
            elif c.tag == 'city':
                adr['city'] = value
            elif c.tag == 'region':
                adr['country_area'] = value
            elif c.tag == 'code':
                adr['postal_code'] = value
            elif c.tag == 'sortingcode':
                adr['sorting_code'] = value
    for a in adr:
        if isinstance(adr[a], list):
            adr[a] = '\u2028'.join(adr[a])
    if country_info:
        # Address validation
        address_format, rules = get_address_format_rules(adr, latin)
        parts = [ address_field_mapping[c] for c in re.findall(r'%([A-Z])', address_format)  if not c in ['N', 'O'] ]
        elements = [ address_field_elements[p] for p in parts ]
        list_parts = False
        for e in adr:
            if adr[e] and not (e in parts or e in ['name', 'role', 'company_name', 'country_code', ]):
                list_parts = True
                writer.warn(x, "Postal address part filled in, but not used: %s: %s\n"
                               " Available elements for %s are: %s" % (address_field_elements[e], adr[e], country_info.name, ', '.join(elements)))
        try:
            i18naddress.normalize_address(adr)
        except i18naddress.InvalidAddressError as e:
            list_parts = True
            writer.note(x, "Postal address check failed for author %s." % full_author_name(author, latin))
            for item in e.errors:
                if adr[item]:
                    writer.note(x, "  Postal address has an unexpected address field or field value: %s: %s" % (address_field_elements[item], (adr[item])), label='')
                else:
                    writer.note(x, "  Postal address is missing an address element: %s" % (address_field_elements[item], ), label='')
        if list_parts:
            writer.note(x, "Recognized postal address elements for %s are: %s" % (rules.country_name.title(), ', '.join(elements)))
    return adr

# These are copied from i18address in order to remove uppercasing


def get_address_format_rules(address, latin=False, normalize=False):
    rules = i18naddress.get_validation_rules(address)
    address_format = rules.address_latin_format if latin else rules.address_format
    if rules.address_latin_format != rules.address_format:
        # don't normalize the line order if the country provides
        # a latin-specific address format
        normalize = False
    address_format = enhance_address_format(address, address_format)
    if normalize:
        address_format = normalize_address_format(address_format)
    return address_format, rules

def enhance_address_format(adr, address_format):
    #     'A': 'street_address'
    #     'C': 'city'
    #     'D': 'city_area'
    #     'E': 'extended_address'
    #     'N': 'name'
    #     'O': 'company_name'
    #     'S': 'country_area'
    #     'X': 'sorting_code'
    #     'Y': 'country_name '
    #     'Z': 'postal_code'

    # Add extended address field '%E' (the code fails for 4 countries: Guinea,
    # Hungary, Iran and China, which won't have %E support):
    address_format = address_format.replace('%N%n%O%n%A', '%N%n%O%n%E%n%A')
    address_format = address_format.replace('%A%n%O%n%N', '%A%n%E%n%O%n%N')
    address_format = address_format.replace('%O%n%N%n%A', '%O%n%N%n%E%n%A')
    if '%E%n%O%n%N' in address_format or '%A%n%O%n%N' in address_format:
        address_format = '%Y%n' + address_format
    else:
        address_format = address_format + '%n%Y'
    # This is incorrect, but suits us better when listing authors
    # in the Authors' Addresses section: move the name to the first line
    address_format = '%N%n' + re.sub(r'%N(%n)?', '', address_format)
    # Get rid of any trailing newlines we might have created
    address_format = re.sub(r'%n$', '', address_format)
    # Add some spacing, for a few special cases
    address_format = re.sub(r'%([A-Z])%([A-Z])', r'%\1 %\2', address_format)
    address_format = re.sub(r'%([A-Z])%([A-Z])', r'%\1 %\2', address_format)
    # country-specific fixes, if any
    if adr['country_code'] == 'SE':
        if not adr['postal_code']:
            address_format = re.sub(r'SE-%Z ', r'', address_format)            
    return address_format

    
def normalize_address_format(address_format):
    #     'N': 'name'
    #     'O': 'company_name'
    #     'E': 'extended_address'
    #     'A': 'street_address'
    #     'X': 'sorting_code'
    #     'D': 'city_area'
    #     'C': 'city'
    #     'Z': 'postal_code'
    #     'S': 'country_area'
    #     'Y': 'country_name '
    old = address_format
    normalized_order = list("NOEAXDCZSY")
    lines = address_format.split('%n')
    norm = []
    # iterate through the desired field order, but don't mess with the address
    # element order within a line:
    for code in normalized_order:
        code = '%'+code
        found = None
        for i, line in enumerate(lines):
            if code in line:
                norm.append(line)
                found = i
                break
        if found:
            del lines[found]
    address_format = '%n'.join(norm)
    new = address_format
    if old != new:
        debug.show('old')
        debug.show('new')
    return address_format
