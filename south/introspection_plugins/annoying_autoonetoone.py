from south.modelsinspector import add_introspection_rules

try:
    from annoying.fields import AutoOneToOneField
except ImportError:
    pass
else:
    #django-annoying's AutoOneToOneField is essentially a OneToOneField.
    add_introspection_rules([], ["^annoying\.fields\.AutoOneToOneField"])
