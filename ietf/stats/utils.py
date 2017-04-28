import re
import requests
from collections import defaultdict

from django.conf import settings

from ietf.stats.models import AffiliationAlias, AffiliationIgnoredEnding, CountryAlias, Registration
from ietf.name.models import CountryName

def compile_affiliation_ending_stripping_regexp():
    parts = []
    for ending_re in AffiliationIgnoredEnding.objects.values_list("ending", flat=True):
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
      "Examplar International" -> "Examplar"

    - Case-folding so Examplar and EXAMPLAR is merged with the
      winner being the one with most occurrences (so input should not
      be made unique) or most upper case letters in case of ties.
      Case folding can be overridden by the aliases in the database."""

    res = {}

    ending_re = compile_affiliation_ending_stripping_regexp()

    known_aliases = { alias.lower(): name for alias, name in AffiliationAlias.objects.values_list("alias", "name") }

    affiliations_with_case_spellings = defaultdict(set)
    case_spelling_count = defaultdict(int)
    for affiliation in affiliations:
        original_affiliation = affiliation

        # check aliases from DB
        name = known_aliases.get(affiliation.lower())
        if name is not None:
            affiliation = name
            res[original_affiliation] = affiliation

        # strip ending
        name = ending_re.sub("", affiliation)
        if name != affiliation:
            affiliation = name
            res[original_affiliation] = affiliation

        # check aliases from DB
        name = known_aliases.get(affiliation.lower())
        if name is not None:
            affiliation = name
            res[original_affiliation] = affiliation

        affiliations_with_case_spellings[affiliation.lower()].add(original_affiliation)
        case_spelling_count[affiliation] += 1

    def affiliation_sort_key(affiliation):
        count = case_spelling_count[affiliation]
        uppercase_letters = sum(1 for c in affiliation if c.isupper())
        return (count, uppercase_letters)

    # now we just need to pick the most popular uppercase/lowercase
    # spelling for each affiliation with more than one
    for similar_affiliations in affiliations_with_case_spellings.itervalues():
        if len(similar_affiliations) > 1:
            most_popular = sorted(similar_affiliations, key=affiliation_sort_key, reverse=True)[0]
            for affiliation in similar_affiliations:
                if affiliation != most_popular:
                    res[affiliation] = most_popular

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
        re.compile(u"\\b{}\\b".format(re.escape(alias))): name
        for alias, name in known_aliases.iteritems()
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
        return u""

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
        for alias_re, name in known_re_aliases.iteritems():
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


def get_registration_data(meeting):
    """"Retrieve registration attendee data and summary statistics.  Returns number
    of Registration records created."""
    num_created = 0
    response = requests.get(settings.REGISTRATION_ATTENDEES_BASE_URL + meeting.number)
    if response.status_code == 200:
        for registration in response.json():
            object, created = Registration.objects.get_or_create(
                meeting_id=meeting.pk,
                first_name=registration['FirstName'],
                last_name=registration['LastName'],
                affiliation=registration['Company'],
                country=registration['Country'])
            if created:
                num_created += 1
    return num_created
    
            
    
    