def find_history_active_at(obj, time):
    """Assumes obj has a corresponding history model (e.g. obj could
    be Person with a corresponding PersonHistory model), then either
    returns the object itself if it was active at time, or the history
    object active at time, or None if time predates the object and its
    history (assuming history is complete).

    For this to work, the history model must use
    related_name="history_set" for the foreign key connecting to the
    live model, both models must have a "time" DateTimeField and a
    history object must be saved with a copy of the old values and
    old time when the time field changes.
    """
    if obj.time <= time:
        return obj

    histories = obj.history_set.order_by('-time')

    for h in histories:
        if h.time <= time:
            return h

    return None

def find_history_replacements_active_at(objects, time):
    """Return dictionary mapping object pk to object or its history
    object at the time, if any.

    Same caveats as for find_history_active_at applies."""

    if not objects:
        return {}

    # automatically figure out how to query history model
    history_model = objects[0].history_set.model
    # core_filters contains something like "group__exact": obj
    relation_name = objects[0].history_set.core_filters.keys()[0].replace("__exact", "")

    # now the querying is a bit tricky - we are only interested in the
    # history version just before time, or if we can't get that, the
    # one just after, but lacking a good way of expressing that
    # through SQL we just grab all of them and sort it out ourselves
    changed_objects = [o for o in objects if o.time > time]

    histories = history_model.objects.filter(**{ relation_name + "__in": changed_objects }).order_by(relation_name, "-time", "-id")

    history_for_obj = { o.pk: o for o in objects }
    skip = None
    for h in histories:
        obj_id = getattr(h, relation_name + "_id")
        if obj_id == skip:
            continue

        history_for_obj[obj_id] = h
        if h.time <= time:
            skip = obj_id # we're far enough, go to next obj

    return history_for_obj

def get_history_object_for(obj):
    """Construct history object for obj, i.e. instantiate history
    object, copy relevant attributes and set a link to obj, but don't
    save. Any customizations can be done by the caller afterwards.
    Many-to-many fields are not copied (impossible without save).

    The history model must use related_name="history_set" for the
    foreign key connecting to the live model for this function to be
    able to discover it."""

    history_model = obj.history_set.model
    h = history_model()

    # copy attributes shared between history and obj
    history_field_names = set(f.name for f in history_model._meta.fields)

    for field in obj._meta.fields:
        if field is not obj._meta.pk and field.name in history_field_names:
            setattr(h, field.name, getattr(obj, field.name))

    # try setting foreign key to obj
    key_name = obj._meta.object_name.lower()
    if key_name in history_field_names:
        setattr(h, key_name, obj)

    # we can't copy many-to-many fields as h isn't saved yet, leave
    # that to caller

    return h

def copy_many_to_many_for_history(history_obj, obj):
    """Copy basic many-to-many fields from obj to history_obj."""
    # copy many to many
    for field in obj._meta.many_to_many:
        if field.rel.through and field.rel.through._meta.auto_created:
            setattr(history_obj, field.name, getattr(obj, field.name).all())
