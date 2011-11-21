def find_history_active_at(obj, time):
    """Assumes obj has a corresponding history object (e.g. obj could
    be Person with a corresponding PersonHistory model), then returns
    the history object active at time, or None if the object itself
    was active at the time.

    For this to work, the history model must use
    related_name="history_set" for the foreign key connecting to the
    live model, both models must have a "time" DateTimeField and a
    history object must be saved with a copy of the old values and
    time when the time field changes.
    """
    if obj.time <= time:
        return None

    histories = obj.history_set.order_by('-time')

    for h in histories:
        if h.time <= time:
            return h

    return None
