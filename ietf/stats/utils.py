# Copyright The IETF Trust 2017-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import re
from collections import defaultdict

import debug                            # pyflakes:ignore

from ietf.stats.models import AffiliationAlias, AffiliationIgnoredEnding, AffiliationMainName, CountryAlias
from ietf.name.models import CountryName

import logging
logger = logging.getLogger('django')


def compile_affiliation_ending_stripping_regexp():
    parts = []
    for ending_re in AffiliationIgnoredEnding.objects.values_list("ending", flat=True):
        # Try to compile as a syntax check
        try:
            re.compile(ending_re)
        except re.error:
            pass

        parts.append(ending_re)

    re_str = ",? *({}) *$".format("|".join(parts))

    return re.compile(re_str, re.IGNORECASE)


def get_aliased_affiliations(affiliations):
    """Given non-unique sequence of affiliations, returns dictionary with
    aliases needed.

    We employ the following strategies, interleaved:

    - Stripping company endings like Inc., GmbH etc. from database

    - Looking up aliases stored directly in the database, like
      "Examplar International" -> "Examplar" """

    res = {}

    ending_re = compile_affiliation_ending_stripping_regexp()

    known_aliases = { alias.lower(): name for alias, name in AffiliationAlias.objects.values_list("alias", "name") }
    # Let's prepare a dict for things like "Google Inc." -> "Google" adding a space to the end of the main name 
    # so we only match it at the beginning of the affiliation and not in the middle of it, e.g. "Google Analytics"
    affiliation_main_names = [(main_name.lower() + ' ', main_name) for main_name in AffiliationMainName.objects.values_list("main_name", flat=True)]

    for affiliation in affiliations:
        original_affiliation = affiliation
        affiliation_plus_space = affiliation + " " # to match main names with a space added to the end of them

        # check aliases from Aliases DB
        name = known_aliases.get(affiliation.lower())
        if name is not None:
            affiliation = name
            res[original_affiliation] = affiliation

        # strip ending
        name = ending_re.sub("", affiliation)
        if name != affiliation:
            affiliation = name
            res[original_affiliation] = affiliation

        # check again aliases from Aliases DB ???
        name = known_aliases.get(affiliation.lower())
        if name is not None:
            affiliation = name
            res[original_affiliation] = affiliation

        # check aliases from Main Names DB 
        name = next((original for lower, original in affiliation_main_names if affiliation.lower().startswith(lower) or affiliation_plus_space.lower().startswith(lower)), None)
        if name is not None:
            affiliation = name
            res[original_affiliation] = affiliation

    return res


def get_aliased_countries(countries):
    known_aliases = dict(CountryAlias.objects.values_list("alias", "country__name"))

    # add aliases for known countries
    for slug, name in CountryName.objects.values_list("slug", "name"):
        known_aliases[name.lower()] = name

    def lookup_alias(possible_alias):
        name = known_aliases.get(possible_alias)
        if name is not None:
            return name

        name = known_aliases.get(possible_alias.lower())
        if name is not None:
            return name

        return possible_alias

    known_re_aliases = {
        re.compile("\\b{}\\b".format(re.escape(alias))): name
        for alias, name in known_aliases.items()
    }

    # specific hack: check for zip codes from the US since in the
    # early days, the addresses often didn't include the country
    us_zipcode_re = re.compile(r"\b(AL|AK|AZ|AR|CA|CO|CT|DE|DC|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|AS|GU|MP|PR|VI|UM|FM|MH|PW|Ca|Cal.|California|CALIFORNIA|Colorado|Georgia|Illinois|Ill|Maryland|Ma|Ma.|Mass|Massachuss?etts|Michigan|Minnesota|New Jersey|New York|Ny|N.Y.|North Carolina|NORTH CAROLINA|Ohio|Oregon|Pennsylvania|Tx|Texas|Tennessee|Utah|Vermont|Virginia|Va.|Washington)[., -]*[0-9]{5}\b")

    us_country_name = CountryName.objects.get(slug="US").name

    def last_text_part_stripped(split):
        for t in reversed(split):
            t = t.strip()
            if t:
                return t
        return ""

    known_countries = set(CountryName.objects.values_list("name", flat=True))

    res = {}

    for country in countries:
        if country in res or country in known_countries:
            continue

        original_country = country

        # aliased name
        country = lookup_alias(country)
        if country in known_countries:
            res[original_country] = country
            continue

        # contains US zipcode
        if us_zipcode_re.search(country):
            res[original_country] = us_country_name
            continue

        # do a little bit of cleanup
        if len(country) > 1 and country[-1] == "." and not country[-2].isupper():
            country = country.rstrip(".")

        country = country.strip("-,").strip()

        # aliased name
        country = lookup_alias(country)
        if country in known_countries:
            res[original_country] = country
            continue

        # country name at end, separated by comma
        last_part = lookup_alias(last_text_part_stripped(country.split(",")))
        if last_part in known_countries:
            res[original_country] = last_part
            continue

        # country name at end, separated by whitespace
        last_part = lookup_alias(last_text_part_stripped(country.split()))
        if last_part in known_countries:
            res[original_country] = last_part
            continue

        # country name anywhere
        country_lower = country.lower()
        found = False
        for alias_re, name in known_re_aliases.items():
            if alias_re.search(country) or alias_re.search(country_lower):
                res[original_country] = name
                found = True
                break

        if found:
            continue

        # unknown country
        res[original_country] = ""

    return res


def clean_country_name(country_name):
    if country_name:
        country_name = get_aliased_countries([country_name]).get(country_name, country_name)
        if country_name and CountryName.objects.filter(name=country_name).exists():
            return country_name

    return ""


def compute_hirsch_index(citation_counts):
    """Computes the h-index given a sequence containing the number of
    citations for each document."""

    i = 0

    for count in sorted(citation_counts, reverse=True):
        if i + 1 > count:
            break

        i += 1

    return i
