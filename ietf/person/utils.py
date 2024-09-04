# Copyright The IETF Trust 2015-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import pprint 
import sys

from django.contrib import admin
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.http import Http404

import debug                            # pyflakes:ignore

from ietf.person.models import Person, Alias, Email
from ietf.utils import log
from ietf.utils.mail import send_mail

def merge_persons(request, source, target, file=sys.stdout, verbose=False):
    changes = []

    # write log
    log.log(f"Merging person records {source.pk} => {target.pk}")
    
    # handle primary emails
    for email in get_extra_primary(source,target):
        email.primary = False
        email.save()
        changes.append('EMAIL ACTION: {} no longer marked as primary'.format(email.address))

    # handle community list
    for communitylist in source.communitylist_set.all():
        source.communitylist_set.remove(communitylist)
        target.communitylist_set.add(communitylist)

    # handle feedback
    for feedback in source.feedback_set.all():
        feedback.person = target
        feedback.save()
    # handle nominations
    for nomination in source.nomination_set.all():
        nomination.person = target
        nomination.save()

    changes.append(handle_users(source, target))
    reviewer_changes = handle_reviewer_settings(source, target)
    if reviewer_changes:
        changes.extend(reviewer_changes)
    merge_nominees(source, target)
    move_related_objects(source, target, file=file, verbose=verbose)
    dedupe_aliases(target)

    # copy other attributes
    for field in ('ascii','ascii_short', 'biography', 'photo', 'photo_thumb', 'name_from_draft'):
        if getattr(source,field) and not getattr(target,field):
            setattr(target,field,getattr(source,field))
            target.save()

    # check for any remaining relationships and exit if more found
    objs = [source]
    deletable_objects = admin.utils.get_deleted_objects(objs, request, admin.site)
    deletable_objects_summary = deletable_objects[1]
    if len(deletable_objects_summary) > 1:    # should only include one object (Person)
        print("Not Deleting Person: {}({})".format(source.ascii,source.pk), file=file)
        print("Related objects remain:", file=file)
        pprint.pprint(deletable_objects[1], stream=file)
        success = False
    else:
        success = True
        print("Deleting Person: {}({})".format(source.ascii,source.pk), file=file)
        source.delete()
    
    return success, changes

def get_extra_primary(source,target):
    '''
    Inspect email addresses and return list of those that should no longer be primary
    '''
    if source.email_set.filter(primary=True) and target.email_set.filter(primary=True):
        return source.email_set.filter(primary=True)
    else:
        return []

def handle_reviewer_settings(source, target):
    '''
    Person.ReviewerSettings are restricted to one object per team. If
    both source and target have ReviewerSettings for the same team
    remove the source ReviewerSetting and report action. 
    '''
    changes = []
    for rs in source.reviewersettings_set.all():
        if target.reviewersettings_set.filter(team=rs.team):
            changes.append('REVIEWER SETTINGS ACTION: dropping duplicate ReviewSettings for team: {}'.format(rs.team))
            rs.delete()      
    return changes

def handle_users(source,target,check_only=False):
    '''
    Deactivates extra Users.  Retains target user.  If check_only == True, just return a string
    describing action, otherwise perform user changes and return string.
    '''
    if not (source.user or target.user):
        return "DATATRACKER LOGIN ACTION: none (no login defined)"
    if not source.user and target.user:
        return "DATATRACKER LOGIN ACTION: retaining login {}".format(target.user)
    if source.user and not target.user:
        message = "DATATRACKER LOGIN ACTION: retaining login {}".format(source.user)
        if not check_only:
            target.user = source.user
            source.user = None
            source.save()
            target.save()
        return message
    if source.user and target.user:
        message = "DATATRACKER LOGIN ACTION: retaining login: {}, removing login: {}".format(target.user,source.user)
        if not check_only:
            log.log(f"merge-person-records: deactivating user {source.user.username}")
            user = source.user
            source.user = None
            source.save()
            user.is_active = False
            user.save()
        return message

def move_related_objects(source, target, file, verbose=False):
    '''Find all related objects and migrate'''
    related_objects = [  f for f in source._meta.get_fields()
        if (f.one_to_many or f.one_to_one)
        and f.auto_created and not f.concrete ]
    for related_object in related_objects:
        accessor = related_object.get_accessor_name()
        field_name = related_object.field.name
        queryset = getattr(source, accessor).all()
        if verbose:
            print("Merging {}:{}".format(accessor,queryset.count()), file=file)
        kwargs = { field_name:target }
        queryset.update(**kwargs)

def dedupe_aliases(person):
    '''Check person for duplicate aliases and purge'''
    seen = []
    for alias in person.alias_set.all():
        if alias.name in seen:
            alias.delete()
        else:
            seen.append(alias.name)

def merge_nominees(source, target):
    '''Move nominees and feedback to target'''
    for nominee in source.nominee_set.all():
        try:
            target_nominee = target.nominee_set.get(nomcom=nominee.nomcom)
        except ObjectDoesNotExist:
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

def send_merge_notification(person,changes):
    '''
    Send an email to the merge target (Person) notifying them of the changes
    '''
    send_mail(request = None,
              to       = person.email_address(),
              frm      = "IETF Secretariat <ietf-secretariat@ietf.org>",
              subject  = "IETF Datatracker records merged",
              template = "utils/merge_person_records.txt",
              context  = dict(person=person,changes='\n'.join(changes)),
              extra    = {}
             )

def determine_merge_order(source,target):
    '''
    Determine merge order.  Select Person that has related User.  If both have Users
    select one with most recent login
    '''
    if source.user and not target.user:
        source,target = target,source   # swap merge order
    if source.user and target.user:
        source,target = sorted([source,target],key=lambda a: a.user.last_login if a.user.last_login else datetime.datetime.min)
    return source,target

def get_active_balloters(ballot_type):
    if ballot_type.slug == 'irsg-approve':
        return get_active_irsg()
    elif ballot_type.slug == 'rsab-approve':
        return get_active_rsab()
    else:
        return get_active_ads()


def get_active_ads():
    cache_key = "doc:active_ads"
    active_ads = cache.get(cache_key)
    if not active_ads:
        active_ads = list(Person.objects.filter(role__name="ad", role__group__state="active", role__group__type="area").distinct())
        cache.set(cache_key, active_ads)
    return active_ads

def get_active_irsg():
    cache_key = "doc:active_irsg_balloters"
    active_irsg_balloters = cache.get(cache_key)
    if not active_irsg_balloters:
        active_irsg_balloters = list(Person.objects.filter(role__group__acronym='irsg',role__name__in=['chair','member','atlarge']).distinct())
        cache.set(cache_key, active_irsg_balloters)
    return active_irsg_balloters

def get_active_rsab():
    cache_key = "doc:active_rsab_balloters"
    active_rsab_balloters = cache.get(cache_key)
    if not active_rsab_balloters:
        active_rsab_balloters = list(Person.objects.filter(role__group__acronym='rsab', role__name="member").distinct())
        cache.set(cache_key, active_rsab_balloters)
    return active_rsab_balloters

def get_dots(person):
        roles = person.role_set.filter(group__state_id__in=('active','bof','proposed'))
        dots = []
        if roles.filter(group__type_id='wg',name_id='chair').exists():
            dots.append('chair')
        if roles.filter(Q(group__acronym='iesg',name_id='ad')|Q(group__acronym='iab',name_id='chair')).exists():
            dots.append('iesg')
        if roles.filter(group__acronym='iab',name_id='member').exists():
            dots.append('iab')
        if roles.filter(group__acronym='irsg').exists():
            dots.append('irsg')
        if roles.filter(group__acronym='llc-board').exists():
            dots.append('llc')
        if roles.filter(group__acronym='ietf-trust').exists():
            dots.append('trust')
        if roles.filter(group__acronym__startswith='nomcom', name_id__in=('chair','member')).exists():
            dots.append('nomcom')
        return dots

def lookup_persons(email_or_name):
    aliases = Alias.objects.filter(name__iexact=email_or_name)
    persons = set(a.person for a in aliases)

    if '@' in email_or_name:
        emails = Email.objects.filter(address__iexact=email_or_name)
        persons.update(e.person for e in emails)

    persons = [p for p in persons if p and p.id]
    if not persons:
        raise Http404
    persons.sort(key=lambda p: p.id)
    return persons
