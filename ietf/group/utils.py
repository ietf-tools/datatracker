from ietf.group.models import *

def save_group_in_history(group):
    def get_model_fields_as_dict(obj):
        return dict((field.name, getattr(obj, field.name))
                    for field in obj._meta.fields
                    if field is not obj._meta.pk)

    # copy fields
    fields = get_model_fields_as_dict(group)
    del fields["charter"] # Charter is saved canonically on Group
    fields["group"] = group
    
    grouphist = GroupHistory(**fields)
    grouphist.save()

    # save RoleHistory
    for role in group.role_set.all():
        rh = RoleHistory(name=role.name, group=grouphist, email=role.email, person=role.person)
        rh.save()

    # copy many to many
    for field in group._meta.many_to_many:
        if field.rel.through and field.rel.through._meta.auto_created:
            setattr(grouphist, field.name, getattr(group, field.name).all())

    return grouphist

