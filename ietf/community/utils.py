# Copyright The IETF Trust 2016-2023, All Rights Reserved
# -*- coding: utf-8 -*-


import re

from django.db.models import Q
from django.conf import settings

import debug                            # pyflakes:ignore

from ietf.community.models import CommunityList, EmailSubscription, SearchRule
from ietf.doc.models import Document, State
from ietf.group.models import Role
from ietf.person.models import Person
from ietf.ietfauth.utils import has_role

from ietf.utils.mail import send_mail

def states_of_significant_change():
    return State.objects.filter(used=True).filter(
        Q(type="draft-stream-ietf", slug__in=['adopt-wg', 'wg-lc', 'writeupw', 'parked', 'dead']) |
        Q(type="draft-iesg", slug__in=['pub-req', 'lc', 'iesg-eva', 'rfcqueue']) |
        Q(type="draft-stream-iab", slug__in=['active', 'review-c', 'rfc-edit']) |
        Q(type="draft-stream-irtf", slug__in=['active', 'rg-lc', 'irsg-w', 'iesg-rev', 'rfc-edit', 'iesghold']) |
        Q(type="draft-stream-ise", slug__in=['receive', 'ise-rev', 'iesg-rev', 'rfc-edit', 'iesghold']) |
        Q(type="draft", slug__in=['rfc', 'dead'])
    )

def can_manage_community_list(user, clist):
    if not user or not user.is_authenticated:
        return False

    if clist.person:
        return user == clist.person.user
    elif clist.group:
        if has_role(user, 'Secretariat'):
            return True

        if clist.group.type_id in ['area', 'wg', 'rg', 'ag', 'rag', 'program', ]:
            return Role.objects.filter(name__slug__in=clist.group.features.groupman_roles, person__user=user, group=clist.group).exists()

    return False

def reset_name_contains_index_for_rule(rule):
    if not rule.rule_type == "name_contains":
        return

    rule.name_contains_index.set(Document.objects.filter(name__regex=rule.text))

def update_name_contains_indexes_with_new_doc(doc):
    for r in SearchRule.objects.filter(rule_type="name_contains"):
        # in theory we could use the database to do this query, but
        # Django doesn't support a reversed regex operator, and regexp
        # support needs backend-specific code so custom SQL is a bit
        # cumbersome too
        if re.search(r.text, doc.name) and not doc in r.name_contains_index.all():
            r.name_contains_index.add(doc)


def docs_matching_community_list_rule(rule):
    docs = Document.objects.all()
    
    if rule.rule_type.endswith("_rfc"):
        docs = docs.filter(type_id="rfc")  # rule.state is ignored for RFCs
    else:
        docs = docs.filter(type_id="draft", states=rule.state)
    
    if rule.rule_type in ['group', 'area', 'group_rfc', 'area_rfc']:
        return docs.filter(Q(group=rule.group_id) | Q(group__parent=rule.group_id))
    elif rule.rule_type in ['group_exp']:
        return docs.filter(group=rule.group_id)
    elif rule.rule_type.startswith("state_"):
        return docs
    elif rule.rule_type == "author": 
        return docs.filter(documentauthor__person=rule.person)
    elif rule.rule_type == "author_rfc":
        return docs.filter(Q(rfcauthor__person=rule.person)|Q(rfcauthor__isnull=True,documentauthor__person=rule.person))
    elif rule.rule_type == "ad":
        return docs.filter(ad=rule.person)
    elif rule.rule_type == "shepherd":
        return docs.filter(shepherd__person=rule.person)
    elif rule.rule_type == "name_contains":
        return docs.filter(searchrule=rule)

    raise NotImplementedError


def community_list_rules_matching_doc(doc):
    rules = SearchRule.objects.none()
    if doc.type_id not in ["draft", "rfc"]:
        return rules  # none
    states = list(doc.states.values_list("pk", flat=True))

    # group and area rules
    if doc.group_id:
        groups = [doc.group_id]
        if doc.group.parent_id:
            groups.append(doc.group.parent_id)
        rules_to_add = SearchRule.objects.filter(group__in=groups)
        if doc.type_id == "rfc":
            rules_to_add = rules_to_add.filter(rule_type__in=["group_rfc", "area_rfc"])
        else:
            rules_to_add = rules_to_add.filter(
                rule_type__in=["group", "area", "group_exp"],
                state__in=states,
            )
        rules |= rules_to_add

    # state rules (only relevant for I-Ds)
    if doc.type_id == "draft":
        rules |= SearchRule.objects.filter(
            rule_type__in=[
                "state_iab",
                "state_iana",
                "state_iesg",
                "state_irtf",
                "state_ise",
                "state_rfceditor",
                "state_ietf",
            ],
            state__in=states,
        )

    # author rules
    if doc.type_id == "rfc":
        # this will over-return but will be least likely to surprise
        rules |= SearchRule.objects.filter(
            rule_type="author_rfc",
            person__in=list(Person.objects.filter(Q(documentauthor__document=doc)|Q(rfcauthor__document=doc))),
        )
    else:
        rules |= SearchRule.objects.filter(
            rule_type="author",
            state__in=states,
            person__in=list(Person.objects.filter(documentauthor__document=doc)),
        )

    # Other draft-only rules rules
    if doc.type_id == "draft":
        if doc.ad_id:
            rules |= SearchRule.objects.filter(
                rule_type="ad",
                state__in=states,
                person=doc.ad_id,
            )

        if doc.shepherd_id:
            rules |= SearchRule.objects.filter(
                rule_type="shepherd",
                state__in=states,
                person__email=doc.shepherd_id,
            )

        rules |= SearchRule.objects.filter(
            rule_type="name_contains",
            state__in=states,
            name_contains_index=doc,  # search our materialized index to avoid full scan
        )

    return rules


def docs_tracked_by_community_list(clist):
    if clist.pk is None:
        return Document.objects.none()

    # in theory, we could use an OR query, but databases seem to have
    # trouble with OR queries and complicated joins so do the OR'ing
    # manually
    doc_ids = set()
    for doc in clist.added_docs.all():
        doc_ids.add(doc.pk)
        doc_ids.update(rfc.pk for rfc in doc.related_that_doc("became_rfc"))

    for rule in clist.searchrule_set.all():
        doc_ids = doc_ids | set(docs_matching_community_list_rule(rule).values_list("pk", flat=True))

    return Document.objects.filter(pk__in=doc_ids)

def community_lists_tracking_doc(doc):
    return CommunityList.objects.filter(Q(added_docs=doc) | Q(searchrule__in=community_list_rules_matching_doc(doc)))


def notify_event_to_subscribers(event):
    try:
        significant = event.type == "changed_state" and event.state_id in [s.pk for s in states_of_significant_change()]
    except AttributeError:
        significant = False

    subscriptions = EmailSubscription.objects.filter(community_list__in=community_lists_tracking_doc(event.doc)).distinct()

    if not significant:
        subscriptions = subscriptions.filter(notify_on="all")

    for sub in subscriptions.select_related("community_list", "email"):
        clist = sub.community_list
        subject = '%s notification: Changes to %s' % (clist.long_name(), event.doc.name)

        send_mail(None, sub.email.address, settings.DEFAULT_FROM_EMAIL, subject, 'community/notification_email.txt',
                  context = {
                      'event': event,
                      'clist': clist,
                  })
