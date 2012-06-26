def find_history_active_at(obj, time):
    """Assumes obj has a corresponding history object (e.g. obj could
    be Person with a corresponding PersonHistory model), then returns
    the history object active at time, or None if the object itself
    was active at the time.

    For this to work, the history model must use
    related_name="history_set" for the foreign key connecting to the
    live model, both models must have a "time" DateTimeField and a
    history object must be saved with a copy of the old values and
    old time when the time field changes.
    """
    if obj.time <= time:
        return None

    histories = obj.history_set.order_by('-time')

    for h in histories:
        if h.time <= time:
            return h

    return None

def get_history_object_for(obj):
    """Construct history object for obj, i.e. instantiate history
    object, copy relevant attributes and set a link to obj, but done
    save. Any customizations can be done by the caller afterwards.
    Many-to-many fields are not copied.

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
