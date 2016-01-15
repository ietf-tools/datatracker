import pprint 

from django.contrib import admin
from django.contrib.auth.models import User
from ietf.person.models import Person

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
    
    deletable_objects, perms_needed, protected = admin.utils.get_deleted_objects(
        objs, opts, user, admin_site, using)
        
    if len(deletable_objects) > 1:
        print >>stream, "Not Deleting Person: {}({})".format(source.ascii,source.pk)
        print >>stream, "Related objects remain:"
        pprint.pprint(deletable_objects[1],stream=stream)
    
    else:
        print >>stream, "Deleting Person: {}({})".format(source.ascii,source.pk)
        source.delete()
