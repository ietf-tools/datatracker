from django.db import models

class InvalidToNoneOverrider(object):
    """Converts invalid ids to None before returning them to Django."""
    def __init__(self, cls, fieldname, null_values):
        self.fieldname = fieldname
        self.real_field = getattr(cls, fieldname)
        self.null_values = null_values

    def __get__(self, instance, instance_type=None):
        if instance is None: # calls on the class
            return self

        v = getattr(instance, u"%s_id" % self.fieldname)
        if v == None or v in self.null_values:
            return None
        else:
            # forward to real field
            return self.real_field.__get__(instance, instance_type)
        
    def __set__(self, instance, value):
        # forward to real field
        self.real_field.__set__(instance, value)

class BrokenForeignKey(models.ForeignKey):
    """ForeignKey for when some null values aren't NULL in the database.

    Django is strict with foreign keys, invalid ids result in
    DoesNotExist in inconvenient places. With this field, invalid ids
    are overridden to return None. Takes a keyword argument
    'null_values' to determine which ids should be considered
    invalid and equivalent to NULL."""
    
    def __init__(self, *args, **kwargs):
        self.broken_null_values = kwargs.pop('null_values', (0,))
        super(self.__class__, self).__init__(*args, **kwargs)

def broken_foreign_key_class_prepared_handler(sender, **kwargs):
    for f in sender._meta.fields:
        if type(f) == BrokenForeignKey:
            setattr(sender, f.name, InvalidToNoneOverrider(sender, f.name, f.broken_null_values))

models.signals.class_prepared.connect(broken_foreign_key_class_prepared_handler)
