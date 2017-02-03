import pprint
import re
from collections import defaultdict

from django.contrib import admin
from django.contrib.auth.models import User
from ietf.person.models import Person, AffiliationAlias, AffiliationIgnoredEnding

def merge_persons(source,target,stream):
    
    # merge emails
    for email in source.email_set.all():
        print >>stream, "Merging email: {}".format(email.address)
        email.person = target
        email.save()
    
    # merge aliases
    target_aliases = [ a.name for a in target.alias_set.all() ]
    for alias in source.alias_set.all():
        if alias.name in target_aliases:
            alias.delete()
        else:
            print >>stream,"Merging alias: {}".format(alias.name)
            alias.person = target
            alias.save()
    
    # merge DocEvents
    for docevent in source.docevent_set.all():
        docevent.by = target
        docevent.save()
        
    # merge SubmissionEvents
    for subevent in source.submissionevent_set.all():
        subevent.by = target
        subevent.save()
    
    # merge Messages
    for message in source.message_set.all():
        message.by = target
        message.save()
    
    # merge Constraints
    for constraint in source.constraint_set.all():
        constraint.person = target
        constraint.save()
    
    # merge Roles
    for role in source.role_set.all():
        role.person = target
        role.save()
    
    # merge Nominees
    for nominee in source.nominee_set.all():
        target_nominee = target.nominee_set.get(nomcom=nominee.nomcom)
        if not target_nominee:
            target_nominee = target.nominee_set.create(nomcom=nominee.nomcom, email=target.email())
        nominee.nomination_set.all().update(nominee=target_nominee)
        for fb in nominee.feedback_set.all():
            fb.nominees.remove(nominee)
            fb.nominees.add(target_nominee)
        for np in nominee.nomineeposition_set.all():
            existing_target_np = target_nominee.nomineeposition_set.filter(position=np.position).first()
            if existing_target_np:
                if existing_target_np.state.slug=='pending':
                    existing_target_np.state = np.state
                    existing_target_np.save()
                np.delete()
            else:
                np.nominee=target_nominee
                np.save()
        nominee.delete()
    
    # check for any remaining relationships and delete if none
    objs = [source]
    opts = Person._meta
    user = User.objects.filter(is_superuser=True).first()
    admin_site = admin.site
    using = 'default'

    deletable_objects, model_count, perms_needed, protected = (
        admin.utils.get_deleted_objects(objs, opts, user, admin_site, using) )
        
    if len(deletable_objects) > 1:
        print >>stream, "Not Deleting Person: {}({})".format(source.ascii,source.pk)
        print >>stream, "Related objects remain:"
        pprint.pprint(deletable_objects[1],stream=stream)
    
    else:
        print >>stream, "Deleting Person: {}({})".format(source.ascii,source.pk)
        source.delete()


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
        alias = known_aliases.get(affiliation.lower())
        if alias is not None:
            affiliation = alias
            res[original_affiliation] = affiliation

        # strip ending
        alias = ending_re.sub("", affiliation)
        if alias != affiliation:
            affiliation = alias
            res[original_affiliation] = affiliation

        # check aliases from DB
        alias = known_aliases.get(affiliation.lower())
        if alias is not None:
            affiliation = alias
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
            print similar_affiliations, most_popular
            for affiliation in similar_affiliations:
                if affiliation != most_popular:
                    res[affiliation] = most_popular
                    print affiliation, "->", most_popular

    return res



