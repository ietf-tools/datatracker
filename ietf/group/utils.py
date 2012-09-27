import os

from django.conf import settings

from ietf.group.models import *


def save_group_in_history(group):
    """This should be called before saving changes to a Group instance,
    so that the GroupHistory entries contain all previous states, while
    the Group entry contain the current state.  XXX TODO: Call this
    directly from Group.save()
    """
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

def get_charter_text(group):
    # get file path from settings. Syntesize file name from path, acronym, and suffix
    try:
        # Try getting charter from new charter tool
        c = group.charter

        # find the latest, preferably approved, revision
        for h in group.charter.history_set.exclude(rev="").order_by("time"):
            h_appr = "-" not in h.rev
            c_appr = "-" not in c.rev
            if (h.rev > c.rev and not (c_appr and not h_appr)) or (h_appr and not c_appr):
                c = h

        filename = os.path.join(c.get_file_path(), "%s-%s.txt" % (c.canonical_name(), c.rev))
        with open(filename) as f:
            return f.read()
    except IOError:
        try:
            filename = os.path.join(settings.IETFWG_DESCRIPTIONS_PATH, group.acronym) + ".desc.txt"
            desc_file = open(filename)
            desc = desc_file.read()
        except BaseException:    
            desc = 'Error Loading Work Group Description'
        return desc
