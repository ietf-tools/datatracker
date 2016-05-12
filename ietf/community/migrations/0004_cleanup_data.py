# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models

def port_rules_to_typed_system(apps, schema_editor):
    SearchRule = apps.get_model("community", "SearchRule")
    State = apps.get_model("doc", "State")
    Group = apps.get_model("group", "Group")
    Person = apps.get_model("person", "Person")

    draft_active = State.objects.get(type="draft", slug="active")
    draft_rfc = State.objects.get(type="draft", slug="rfc")

    def try_to_uniquify_person(rule, person_qs):
        if rule.community_list.user and len(person_qs) > 1:
            user_specific_qs = person_qs.filter(user=rule.community_list.user)
            if len(user_specific_qs) > 0 and len(user_specific_qs) < len(person_qs):
                return user_specific_qs

        return person_qs


    for rule in SearchRule.objects.all().iterator():
        handled = False

        if rule.rule_type in ['wg_asociated', 'area_asociated', 'wg_asociated_rfc', 'area_asociated_rfc']:
            try:
                rule.group = Group.objects.get(acronym=rule.value)

                if rule.rule_type in ['wg_asociated_rfc', 'area_asociated_rfc']:
                    rule.state = draft_rfc
                else:
                    rule.state = draft_active
                handled = True
            except Group.DoesNotExist:
                pass


        elif rule.rule_type in ['in_iab_state', 'in_iana_state', 'in_iesg_state', 'in_irtf_state', 'in_ise_state', 'in_rfcEdit_state', 'in_wg_state']:
            state_types = {
                'in_iab_state': 'draft-stream-iab',
                'in_iana_state': 'draft-iana-review',
                'in_iesg_state': 'draft-iesg',
                'in_irtf_state': 'draft-stream-irtf',
                'in_ise_state': 'draft-stream-ise',
                'in_rfcEdit_state': 'draft-rfceditor',
                'in_wg_state': 'draft-stream-ietf',
            }

            try:
                rule.state = State.objects.get(type=state_types[rule.rule_type], slug=rule.value)
                handled = True
            except State.DoesNotExist:
                pass


        elif rule.rule_type in ["author", "author_rfc"]:
            found_persons = list(try_to_uniquify_person(rule, Person.objects.filter(email__documentauthor__id__gte=1).filter(name__icontains=rule.value).distinct()))

            if found_persons:
                rule.person = found_persons[0]
                rule.state = draft_active

                for p in found_persons[1:]:
                    SearchRule.objects.create(
                        community_list=rule.community_list,
                        rule_type=rule.rule_type,
                        state=rule.state,
                        person=p,
                    )
                    #print "created", rule.rule_type, p.name

                handled = True

        elif rule.rule_type == "ad_responsible":
            try:
                rule.person = Person.objects.get(id=rule.value)
                rule.state = draft_active
                handled = True
            except Person.DoesNotExist:
                pass


        elif rule.rule_type == "shepherd":
            found_persons = list(try_to_uniquify_person(rule, Person.objects.filter(email__shepherd_document_set__type="draft").filter(name__icontains=rule.value).distinct()))

            if found_persons:
                rule.person = found_persons[0]
                rule.state = draft_active

                for p in found_persons[1:]:
                    SearchRule.objects.create(
                        community_list=rule.community_list,
                        rule_type=rule.rule_type,
                        state=rule.state,
                        person=p,
                    )
                    #print "created", rule.rule_type, p.name

                handled = True

        elif rule.rule_type == "with_text":
            rule.state = draft_active

            if rule.value:
                rule.text = rule.value
                handled = True

        if handled:
            rule.save()
        else:
            rule.delete()
            #print "NOT HANDLED", rule.pk, rule.rule_type, rule.value

def delete_extra_person_rules(apps, schema_editor):
    SearchRule = apps.get_model("community", "SearchRule")
    SearchRule.objects.exclude(person=None).filter(value="").delete()

RENAMED_RULES = [
    ('wg_asociated', 'group'),
    ('area_asociated', 'area'),
    ('wg_asociated_rfc', 'group_rfc'),
    ('area_asociated_rfc', 'area_rfc'),

    ('in_iab_state', 'state_iab'),
    ('in_iana_state', 'state_iana'),
    ('in_iesg_state', 'state_iesg'),
    ('in_irtf_state', 'state_irtf'),
    ('in_ise_state', 'state_ise'),
    ('in_rfcEdit_state', 'state_rfceditor'),
    ('in_wg_state', 'state_ietf'),

    ('ad_responsible', 'ad'),

    ('with_text', 'name_contains'),
]

def rename_rule_type_forwards(apps, schema_editor):
    SearchRule = apps.get_model("community", "SearchRule")

    renamings = dict(RENAMED_RULES)

    for r in SearchRule.objects.all():
        if r.rule_type in renamings:
            r.rule_type = renamings[r.rule_type]
            r.save()

def rename_rule_type_backwards(apps, schema_editor):
    SearchRule = apps.get_model("community", "SearchRule")

    renamings = dict((to, fro) for fro, to in RENAMED_RULES)

    for r in SearchRule.objects.all():
        if r.rule_type in renamings:
            r.rule_type = renamings[r.rule_type]
            r.save()

def get_rid_of_empty_lists(apps, schema_editor):
    CommunityList = apps.get_model("community", "CommunityList")

    for cl in CommunityList.objects.all():
        if not cl.added_docs.exists() and not cl.searchrule_set.exists() and not cl.emailsubscription_set.exists():
            cl.delete()

def move_email_subscriptions_to_preregistered_email(apps, schema_editor):
    EmailSubscription = apps.get_model("community", "EmailSubscription")
    Email = apps.get_model("person", "Email")
    Person = apps.get_model("person", "Person")

    for e in EmailSubscription.objects.all():
        email_obj = None
        try:
            email_obj = Email.objects.get(address=e.email)
        except Email.DoesNotExist:
            if e.community_list.user:
                person = Person.objects.filter(user=e.community_list.user).first()

                #print "creating", e.email, person.ascii
                # we'll register it on the user, on the assumption
                # that the user and the subscriber is the same person
                email_obj = Email.objects.create(
                    address=e.email,
                    person=person,
                )

        if not email_obj:
            print "deleting", e.email
            e.delete()

def fill_in_notify_on(apps, schema_editor):
    EmailSubscription = apps.get_model("community", "EmailSubscription")

    EmailSubscription.objects.filter(significant=False, notify_on="all")
    EmailSubscription.objects.filter(significant=True, notify_on="significant")

def add_group_community_lists(apps, schema_editor):
    Group = apps.get_model("group", "Group")
    Document = apps.get_model("doc", "Document")
    State = apps.get_model("doc", "State")
    CommunityList = apps.get_model("community", "CommunityList")
    SearchRule = apps.get_model("community", "SearchRule")

    active_state = State.objects.get(slug="active", type="draft")
    rfc_state = State.objects.get(slug="rfc", type="draft")

    for g in Group.objects.filter(type__in=("rg", "wg")):
        clist = CommunityList.objects.filter(group=g).first()
        if clist:
            SearchRule.objects.get_or_create(community_list=clist, rule_type="group", group=g, state=active_state)
            SearchRule.objects.get_or_create(community_list=clist, rule_type="group_rfc", group=g, state=rfc_state)
            r, _ = SearchRule.objects.get_or_create(community_list=clist, rule_type="name_contains", text=r"^draft-[^-]+-%s-" % g.acronym, state=active_state)
            r.name_contains_index = Document.objects.filter(docalias__name__regex=r.text)

        else:
            clist = CommunityList.objects.create(group=g)
            SearchRule.objects.create(community_list=clist, rule_type="group", group=g, state=active_state)
            SearchRule.objects.create(community_list=clist, rule_type="group_rfc", group=g, state=rfc_state)
            r = SearchRule.objects.create(community_list=clist, rule_type="name_contains", text=r"^draft-[^-]+-%s-" % g.acronym, state=active_state)
            r.name_contains_index = Document.objects.filter(docalias__name__regex=r.text)

def noop(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('community', '0003_cleanup'),
    ]

    operations = [
        migrations.RunPython(port_rules_to_typed_system, delete_extra_person_rules),
        migrations.RunPython(rename_rule_type_forwards, rename_rule_type_backwards),
        migrations.RunPython(move_email_subscriptions_to_preregistered_email, noop),
        migrations.RunPython(get_rid_of_empty_lists, noop),
        migrations.RunPython(fill_in_notify_on, noop),
        migrations.RunPython(add_group_community_lists, noop),
        migrations.RemoveField(
            model_name='searchrule',
            name='value',
        ),
        migrations.AlterField(
            model_name='emailsubscription',
            name='email',
            field=models.ForeignKey(to='person.Email'),
            preserve_default=True,
        ),
        migrations.RemoveField(
            model_name='emailsubscription',
            name='significant',
        ),
    ]
