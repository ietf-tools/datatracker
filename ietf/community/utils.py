from django.db.models import Q
from django.conf import settings
from django.contrib.sites.models import Site
from django.http import Http404
import django.core.signing

from ietf.community.models import CommunityList, EmailSubscription, SearchRule
from ietf.doc.models import Document, State
from ietf.group.models import Role
from ietf.person.models import Person

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
    if not user or not user.is_authenticated():
        return False

    if clist.user:
        return user == clist.user
    elif clist.group:
        if clist.group.type_id == 'area':
            return Role.objects.filter(name__slug='ad', person__user=user, group=clist.group).exists()
        elif clist.group.type_id in ('wg', 'rg'):
            return Role.objects.filter(name__slug='chair', person__user=user, group=clist.group).exists()

    return False

def augment_docs_with_tracking_info(docs, user):
    """Add attribute to each document with whether the document is tracked
    by the user or not."""

    tracked = set()

    if user and user.is_authenticated():
        clist = CommunityList.objects.filter(user=user).first()
        if clist:
            tracked.update(docs_tracked_by_community_list(clist).filter(pk__in=docs).values_list("pk", flat=True))

    for d in docs:
        d.tracked_in_personal_community_list = d.pk in tracked

def docs_matching_community_list_rule(rule):
    docs = Document.objects.all()
    if rule.rule_type in ['group', 'area', 'group_rfc', 'area_rfc']:
        return docs.filter(Q(group=rule.group_id) | Q(group__parent=rule.group_id), states=rule.state)
    elif rule.rule_type.startswith("state_"):
        return docs.filter(states=rule.state)
    elif rule.rule_type in ["author", "author_rfc"]:
        return docs.filter(states=rule.state, documentauthor__author__person=rule.person)
    elif rule.rule_type == "ad":
        return docs.filter(states=rule.state, ad=rule.person)
    elif rule.rule_type == "shepherd":
        return docs.filter(states=rule.state, shepherd__person=rule.person)
    elif rule.rule_type == "name_contains":
        return docs.filter(states=rule.state, name__icontains=rule.text)

    raise NotImplementedError

def community_list_rules_matching_doc(doc):
    from django.db import connection

    states = list(doc.states.values_list("pk", flat=True))

    rules = SearchRule.objects.none()

    if doc.group_id:
        groups = [doc.group_id]
        if doc.group.parent_id:
            groups.append(doc.group.parent_id)
        rules |= SearchRule.objects.filter(
            rule_type__in=['group', 'area', 'group_rfc', 'area_rfc'],
            state__in=states,
            group__in=groups
        )

    rules |= SearchRule.objects.filter(
        rule_type__in=['state_iab', 'state_iana', 'state_iesg', 'state_irtf', 'state_ise', 'state_rfceditor', 'state_ietf'],
        state__in=states,
    )

    rules |= SearchRule.objects.filter(
        rule_type__in=["author", "author_rfc"],
        state__in=states,
        person__in=list(Person.objects.filter(email__documentauthor__document=doc)),
    )

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
    ).extra(
        # we need a reverse icontains here, unfortunately this means we need concatenation which isn't quite cross-platform
        where=["%s like '%%' || text || '%%'" if connection.vendor == "sqlite" else "%s like concat('%%', text, '%%')"],
        params=[doc.name]
    )

    return rules


def docs_tracked_by_community_list(clist):
    if clist.pk is None:
        return Document.objects.none()

    # in theory, we could use an OR query, but databases seem to have
    # trouble with OR queries and complicated joins so do the OR'ing
    # manually
    doc_ids = set(clist.added_docs.values_list("pk", flat=True))
    for rule in clist.searchrule_set.all():
        doc_ids = doc_ids | set(docs_matching_community_list_rule(rule).values_list("pk", flat=True))

    return Document.objects.filter(pk__in=doc_ids)

def community_lists_tracking_doc(doc):
    return CommunityList.objects.filter(Q(added_docs=doc) | Q(searchrule__in=community_list_rules_matching_doc(doc)))


def notify_event_to_subscribers(event):
    significant = event.type == "changed_state" and event.state_id in [s.pk for s in states_of_significant_change()]

    subscriptions = EmailSubscription.objects.filter(community_list__in=community_lists_tracking_doc(event.doc)).distinct()

    if not significant:
        subscriptions = subscriptions.filter(significant=False)

    for sub in subscriptions.select_related("community_list"):
        clist = sub.community_list
        subject = '%s notification: Changes to %s' % (clist.long_name(), event.doc.name)

        send_mail(None, sub.email, settings.DEFAULT_FROM_EMAIL, subject, 'community/notification_email.txt',
                  context = {
                      'event': event,
                      'clist': clist,
                  })

def confirmation_salt(operation, clist):
    return ":".join(["community",
                     operation,
                     "personal" if clist.user else "group",
                     clist.user.username if clist.user else clist.group.acronym])

def send_subscription_confirmation_email(request, clist, operation, to_email, significant):
    domain = Site.objects.get_current().domain
    subject = 'Confirm list subscription: %s' % clist
    from_email = settings.DEFAULT_FROM_EMAIL

    auth = django.core.signing.dumps([to_email, 1 if significant else 0], salt=confirmation_salt("subscribe", clist))

    send_mail(request, to_email, from_email, subject, 'community/confirm_email.txt', {
        'domain': domain,
        'clist': clist,
        'auth': auth,
        'operation': operation,
    })

def verify_confirmation_data(auth, clist, operation):
    try:
        data = django.core.signing.loads(auth, salt=confirmation_salt(operation, clist), max_age=24 * 60 * 60)
    except django.core.signing.BadSignature:
        raise Http404("Invalid or expired auth")

    try:
        to_email, significant = data[:2]
    except ValueError:
        raise Http404("Invalid data")

    return to_email, bool(significant)

    
