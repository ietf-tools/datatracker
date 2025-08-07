def get_attr_or_callable(obj, name):
    target = getattr(obj, name)
    if callable(target):
        return target()
    return target
