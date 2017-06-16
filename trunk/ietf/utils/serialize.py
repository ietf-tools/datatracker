from django.db import models

def object_as_shallow_dict(obj):
    """Turn a Django model object into a dict suitable for passing to
    create and for serializing to JSON."""

    d = {}
    for f in obj._meta.fields:
        n = f.name
        if isinstance(f, models.ForeignKey):
            n = f.name + "_id"

        v = getattr(obj, n)
        if isinstance(f, models.ManyToManyField):
            v = list(v.values_list("pk", flat=True))
        elif isinstance(f, models.DateTimeField):
            v = v.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(f, models.DateField):
            v = v.strftime('%Y-%m-%d')

        d[n] = v

    return d
