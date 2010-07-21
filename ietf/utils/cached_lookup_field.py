from django.core.exceptions import ObjectDoesNotExist

class CachedLookupField(object):
    """Django field for looking up and caching another object, like a
    ForeignKey only you must supply a function for doing the lookup
    yourself (and there's no reverse magic). Useful in case a real foreign
    key is missing. "lookup" is called on the first access to the field
    and gets the instance as sole argument; it should return an object
    or throw a DoesNotExist exception (which is normalized to None), e.g.

    class A(django.db.models.Model):
       foo = CachedLookupField(lookup=lambda self: Foo.objects.get(key=self.key))
       key = CharField()
    """
    
    def __init__(self, lookup):
        self.lookup = lookup
        self.value = None
        self.value_cached = False

    def __get__(self, instance, instance_type=None):
        if not instance_type:
            return self

        if not self.value_cached:
            try:
                self.value = self.lookup(instance)
            except ObjectDoesNotExist:
                self.value = None
            self.value_cached = True
            
        return self.value

        
